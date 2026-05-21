from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .schemas import (
    DistributedRuntimeSnapshot,
    EnterprisePolicyProfile,
    ExecutionQueueItem,
    PluginManifest,
    PluginValidationRequest,
    PluginValidationResult,
    ProductizationSnapshot,
    ReliabilityMetric,
    RuntimeRecoverySnapshot,
    StableApiContract,
    TaskSummary,
)
from .settings import Settings
from .storage import utc_now


PRODUCTIZATION_API_VERSION = "2026.05.07"
TERMINAL_TASK_STATUSES = {"completed", "failed", "canceled"}
INTERRUPTED_TASK_STATUSES = {"planning", "running", "needs_approval", "validating", "repairing", "blocked"}
QUEUE_RECOVERY_STATUSES = {"assigned", "running", "retrying", "blocked"}
HIGH_RISK_PLUGIN_PERMISSIONS = {"write_workspace", "run_commands", "network", "model_access", "provider"}
CAPABILITY_PERMISSION_HINTS: dict[str, set[str]] = {
    "agent": {"read_workspace", "model_access", "telemetry"},
    "validator": {"read_workspace", "run_validation"},
    "provider": {"provider", "model_access", "network"},
    "scaffold_template": {"scaffold", "read_workspace", "write_workspace"},
    "telemetry_processor": {"telemetry"},
    "workspace_analyzer": {"read_workspace", "analyzer"},
    "ui_panel": {"ui_panel"},
}


def _fingerprint(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ProductizationEngine:
    """Stable API, plugin SDK, recovery, enterprise policy, and reliability hardening."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def stable_api_contracts(self) -> list[StableApiContract]:
        version = PRODUCTIZATION_API_VERSION
        return [
            StableApiContract(
                id="backend.rest.v1",
                name="Backend REST API",
                version=version,
                path_prefixes=["/api/chat", "/api/files", "/api/apply", "/api/validate", "/api/config"],
                schema_refs=["AgentRequest", "AgentResponse", "ApplyRequest", "ValidateResponse", "AppConfig"],
                compatibility_notes=[
                    "Existing FastAPI endpoints remain unversioned for desktop client compatibility.",
                    "New productization endpoints expose version metadata without changing current contracts.",
                ],
            ),
            StableApiContract(
                id="task.graph.v1",
                name="Task Graph API",
                version=version,
                path_prefixes=["/api/tasks", "/api/tasks/{task_id}/timeline", "/api/tasks/{task_id}/artifacts"],
                schema_refs=["TaskSummary", "TaskCreateRequest", "TaskTimelineResponse", "TaskArtifactsResponse"],
                compatibility_notes=["Task status transitions remain governed by task_engine.validate_task_transition."],
            ),
            StableApiContract(
                id="runtime.events.v1",
                name="Structured Event Timeline",
                version=version,
                path_prefixes=["/api/tasks/{task_id}/timeline", "/api/distributed-runtime/audit"],
                schema_refs=["ToolEvent", "WorkerAuditEvent"],
                compatibility_notes=["Agents and workers communicate through persisted events rather than loose chat text."],
            ),
            StableApiContract(
                id="telemetry.v1",
                name="Telemetry And Reliability API",
                version=version,
                path_prefixes=["/api/telemetry", "/api/adaptive-intelligence", "/api/productization/reliability"],
                schema_refs=["TelemetrySnapshot", "AdaptiveIntelligenceSnapshot", "ReliabilityMetric"],
                compatibility_notes=["Telemetry snapshots are append/update records and preserve existing SQLite tables."],
            ),
            StableApiContract(
                id="distributed-runtime.v1",
                name="Distributed Runtime API",
                version=version,
                path_prefixes=["/api/distributed-runtime"],
                schema_refs=["WorkerRuntimeInfo", "ExecutionQueueItem", "DistributedRuntimeSnapshot"],
                compatibility_notes=["Local-first execution remains the offline fallback path."],
            ),
            StableApiContract(
                id="workspace.v1",
                name="Workspace And Safety API",
                version=version,
                path_prefixes=["/api/workspace", "/api/project-intelligence", "/api/workspace-intelligence", "/api/checkpoints"],
                schema_refs=["WorkspaceProfileResponse", "ProjectIntelligenceSnapshot", "WorkspaceOperationsSnapshot"],
                compatibility_notes=["Workspace paths continue to resolve through WorkspaceManager safety rules."],
            ),
            StableApiContract(
                id="plugin.sdk.v1",
                name="Plugin / Extension SDK",
                version=version,
                path_prefixes=["/api/productization/plugins", "/api/productization/stable-apis"],
                schema_refs=["PluginManifest", "PluginValidationResult", "StableApiContract"],
                compatibility_notes=[
                    "Plugins are permission-scoped and disabled by default.",
                    "Signing metadata is supported now; enterprise policy can require signatures before trust.",
                ],
            ),
        ]

    def default_enterprise_policy(self) -> EnterprisePolicyProfile:
        privacy_mode = "shared_workspace" if self.settings.aegis_shared_workspace_mode else "local_first"
        command_default = "approval_required" if self.settings.approval_tier in {"manual", "prompt", "guided"} else "allow_safe"
        return EnterprisePolicyProfile(
            id="local_first_default",
            name="Local-First Default",
            description="Production baseline that preserves offline operation, approval-gated commands, audit trails, and explicit plugin trust.",
            active=True,
            audit_trails=True,
            permission_profile=f"{self.settings.approval_tier}:{self.settings.sandbox_profile}",
            privacy_mode=privacy_mode,
            encrypted_workspace_storage=False,
            provider_allowlist=[],
            provider_blocklist=[],
            network_allowlist=["127.0.0.1", "localhost"],
            network_blocklist=[],
            enforce_local_models=not self.settings.aegis_model_api.lower().startswith("openai"),
            allow_remote_workers=False,
            telemetry_retention_days=30,
            plugin_signing_required=False,
            command_execution_default=command_default,
            metadata={
                "approval_tier": self.settings.approval_tier,
                "sandbox_profile": self.settings.sandbox_profile,
                "router_execution_enabled": self.settings.aegis_router_execution_enabled,
                "shared_workspace_mode": self.settings.aegis_shared_workspace_mode,
            },
        )

    def ensure_enterprise_policy(self, store: Any) -> EnterprisePolicyProfile:
        policy = store.active_enterprise_policy()
        if policy is not None:
            return policy
        return store.save_enterprise_policy(self.default_enterprise_policy())

    def validate_plugin(
        self,
        request: PluginValidationRequest | PluginManifest,
        *,
        policy: EnterprisePolicyProfile | None = None,
    ) -> PluginValidationResult:
        manifest = request.manifest if isinstance(request, PluginValidationRequest) else request
        require_signature = request.require_signature if isinstance(request, PluginValidationRequest) else False
        if policy and policy.plugin_signing_required:
            require_signature = True
        normalized = self._normalized_manifest(manifest)
        errors: list[str] = []
        warnings: list[str] = []

        if normalized.api_version != PRODUCTIZATION_API_VERSION:
            errors.append(
                f"Plugin API version {normalized.api_version or '[missing]'} does not match {PRODUCTIZATION_API_VERSION}."
            )
        if not normalized.version:
            errors.append("Plugin version is required.")
        if not normalized.name:
            errors.append("Plugin name is required.")
        if not normalized.capabilities:
            errors.append("At least one plugin capability is required.")
        if not normalized.entrypoint and "ui_panel" not in normalized.capabilities:
            warnings.append("No entrypoint is configured; lifecycle hooks and backend execution will be unavailable.")
        if "ui_panel" in normalized.capabilities and not normalized.ui_panel_route:
            warnings.append("UI panel plugins should declare ui_panel_route for the workspace shell.")

        permission_set = set(normalized.permissions)
        capability_hints = set().union(*(CAPABILITY_PERMISSION_HINTS.get(capability, set()) for capability in normalized.capabilities))
        unknown_permissions = permission_set - set().union(*CAPABILITY_PERMISSION_HINTS.values())
        if unknown_permissions:
            errors.append(f"Unknown plugin permission(s): {', '.join(sorted(unknown_permissions))}.")
        extra_permissions = permission_set - capability_hints
        if extra_permissions:
            warnings.append(
                "Permission scope is broader than declared capabilities: "
                + ", ".join(sorted(extra_permissions))
                + "."
            )

        risky_permissions = permission_set & HIGH_RISK_PLUGIN_PERMISSIONS
        if risky_permissions and normalized.sandbox_profile not in {"isolated", "sandbox", "restricted"}:
            errors.append("High-risk plugin permissions require isolated, sandbox, or restricted sandbox_profile.")
        if risky_permissions and normalized.enabled and not normalized.trusted:
            errors.append("Enabled plugins with high-risk permissions must be explicitly trusted.")
        if require_signature and not (normalized.signature and normalized.signing_key_fingerprint):
            errors.append("Plugin signature and signing_key_fingerprint are required by policy.")
        elif not normalized.signature:
            warnings.append("Plugin signing metadata is missing; keep this plugin untrusted in shared or enterprise workspaces.")
        expected_checksum = self._manifest_checksum(manifest)
        if manifest.checksum and manifest.checksum not in {"builtin", expected_checksum}:
            errors.append("Plugin manifest checksum does not match package metadata.")

        for hook in normalized.lifecycle_hooks:
            hook_permissions = set(hook.required_permissions)
            if hook_permissions - permission_set:
                errors.append(f"Lifecycle hook {hook.name} asks for permissions not granted by the manifest.")
            if hook.command and "run_commands" not in permission_set:
                warnings.append(f"Lifecycle hook {hook.name} declares a command but run_commands is not granted.")

        return PluginValidationResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            normalized_manifest=normalized,
        )

    def snapshot(
        self,
        store: Any,
        *,
        project_root: Path,
        checkpoints: list[Any],
        runtime: DistributedRuntimeSnapshot | None = None,
        refresh_metrics: bool = True,
    ) -> ProductizationSnapshot:
        policy = self.ensure_enterprise_policy(store)
        plugins = store.plugin_manifests(include_disabled=True)
        validation = [self.validate_plugin(plugin, policy=policy) for plugin in plugins]
        recovery = self.recovery_snapshot(store, project_root=project_root, checkpoints=checkpoints, runtime=runtime)
        metrics = self.reliability_metrics(store, project_root=project_root, recovery=recovery, runtime=runtime)
        snapshot = ProductizationSnapshot(
            workspace_root=str(project_root.resolve()),
            generated_at=utc_now(),
            api_version=PRODUCTIZATION_API_VERSION,
            stable_apis=self.stable_api_contracts(),
            plugins=plugins,
            plugin_validation=validation,
            enterprise_policy=policy,
            recovery=recovery,
            metrics=metrics,
            performance=self.performance_profile(store, project_root=project_root, runtime=runtime),
            scaling=self.scaling_profile(store, project_root=project_root),
            packaging=self.packaging_profile(),
            docs=[
                "docs/ARCHITECTURE.md",
                "docs/PRODUCTIZATION_AND_HARDENING.md",
                "docs/AGENT_RUNTIME.md",
                "docs/WORKSPACE_SAFETY.md",
                "docs/VALIDATION_AND_REPAIR.md",
                "docs/FRONTEND_STRUCTURE.md",
            ],
            recommendations=self.recommendations(metrics, recovery, validation, policy),
            warnings=self.warnings(policy, validation),
        )
        if refresh_metrics:
            store.save_reliability_metric_snapshot(snapshot)
        return snapshot

    def recovery_snapshot(
        self,
        store: Any,
        *,
        project_root: Path,
        checkpoints: list[Any],
        runtime: DistributedRuntimeSnapshot | None = None,
    ) -> RuntimeRecoverySnapshot:
        database_ok, database_message = self.database_integrity(store.db_path)
        tasks = store.list_tasks(project_root=project_root, limit=500, include_subtasks=True)
        open_tasks = [task for task in tasks if task.status not in TERMINAL_TASK_STATUSES]
        interrupted = [task for task in open_tasks if task.status in INTERRUPTED_TASK_STATUSES]
        recoverable = [
            task
            for task in interrupted
            if task.checkpoints or task.status in {"queued", "planning", "needs_approval", "blocked"}
        ]
        jobs = store.execution_jobs(project_root=project_root, limit=500)
        queue_recovery = [job for job in jobs if job.status in QUEUE_RECOVERY_STATUSES]
        workers = runtime.workers if runtime else store.runtime_workers(include_revoked=True)
        stale_workers = self._stale_worker_ids(workers)
        latest_checkpoint = checkpoints[0].id if checkpoints else ""
        recommended_actions: list[str] = []
        if not database_ok:
            recommended_actions.append("Back up the workspace and rebuild SQLite state from checkpoints and task logs.")
        if interrupted:
            recommended_actions.append(f"Review {len(interrupted)} interrupted task(s) before safe shutdown.")
        if queue_recovery:
            recommended_actions.append(f"Resume, cancel, or retry {len(queue_recovery)} queued runtime item(s).")
        if stale_workers:
            recommended_actions.append(f"Reconnect or revoke stale worker(s): {', '.join(stale_workers[:5])}.")
        if not checkpoints:
            recommended_actions.append("No checkpoints are available for this workspace yet; create one before risky changes.")

        return RuntimeRecoverySnapshot(
            generated_at=utc_now(),
            database_path=str(store.db_path),
            database_ok=database_ok,
            database_message=database_message,
            open_tasks=len(open_tasks),
            interrupted_tasks=interrupted[:25],
            recoverable_tasks=recoverable[:25],
            stale_workers=stale_workers[:25],
            queue_recovery_items=queue_recovery[:25],
            checkpoint_count=len(checkpoints),
            latest_checkpoint_id=latest_checkpoint,
            safe_shutdown_ready=database_ok and not interrupted and not queue_recovery,
            recommended_actions=recommended_actions,
        )

    def database_integrity(self, db_path: Path) -> tuple[bool, str]:
        if not db_path.exists():
            return False, "database file does not exist"
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("pragma quick_check").fetchone()
            message = str(row[0]) if row else "no quick_check result"
            return message.lower() == "ok", message
        except sqlite3.Error as exc:
            return False, str(exc)
        finally:
            if conn is not None:
                conn.close()

    def reliability_metrics(
        self,
        store: Any,
        *,
        project_root: Path,
        recovery: RuntimeRecoverySnapshot,
        runtime: DistributedRuntimeSnapshot | None = None,
    ) -> list[ReliabilityMetric]:
        tasks = store.list_tasks(project_root=project_root, limit=500, include_subtasks=True)
        outcomes = store.adaptive_task_outcomes(project_root=project_root, limit=500)
        route_quality = store.route_quality(project_root=project_root, limit=300)
        attempts = store.recent_model_attempts(project_root=project_root, limit=500)
        terminal = [task for task in tasks if task.status in TERMINAL_TASK_STATUSES]
        completed = [task for task in terminal if task.status == "completed"]
        failed = [task for task in terminal if task.status == "failed"]
        validation_runs = sum(outcome.validation_runs for outcome in outcomes)
        validation_passes = sum(outcome.validation_passes for outcome in outcomes)
        repair_tasks = [outcome for outcome in outcomes if outcome.repair_count > 0]
        repaired_successes = [outcome for outcome in repair_tasks if outcome.success]
        attempt_infos = [entry.attempt for entry in attempts]
        average_latency = mean([attempt.latency_ms for attempt in attempt_infos if attempt.latency_ms is not None] or [0])
        token_total = sum((attempt.input_tokens or 0) + (attempt.output_tokens or 0) for attempt in attempt_infos)
        runtime_observability = runtime.observability if runtime else None
        runtime_total_jobs = (
            runtime_observability.queued_jobs
            + runtime_observability.running_jobs
            + runtime_observability.failed_jobs
            + runtime_observability.succeeded_jobs
            if runtime_observability
            else len(terminal)
        )

        return [
            self._metric(
                "task_completion_rate",
                self._ratio(len(completed), len(terminal)),
                "ratio",
                target=0.8,
                detail=f"{len(completed)} completed / {len(terminal)} terminal task(s).",
            ),
            self._metric(
                "validation_success_rate",
                self._ratio(validation_passes, validation_runs),
                "ratio",
                target=0.75,
                detail=f"{validation_passes} passing validation run(s) / {validation_runs} total.",
            ),
            self._metric(
                "repair_success_rate",
                self._ratio(len(repaired_successes), len(repair_tasks)),
                "ratio",
                target=0.6,
                detail=f"{len(repaired_successes)} successful repaired task(s) / {len(repair_tasks)} repaired task(s).",
            ),
            self._metric(
                "runtime_recovery_ready",
                1.0 if recovery.safe_shutdown_ready else 0.0,
                "boolean",
                target=1.0,
                detail="Safe shutdown is ready." if recovery.safe_shutdown_ready else "Open recovery work remains.",
            ),
            self._metric(
                "database_integrity",
                1.0 if recovery.database_ok else 0.0,
                "boolean",
                target=1.0,
                detail=recovery.database_message or "SQLite quick_check pending.",
            ),
            self._metric(
                "route_reliability",
                route_quality.overview.reliability_score,
                "ratio",
                target=0.75,
                detail=f"{route_quality.overview.model_attempt_count} model attempt(s) analyzed.",
            ),
            self._metric(
                "average_model_latency_ms",
                float(average_latency),
                "ms",
                target=2500.0,
                detail=f"{len(attempts)} model attempt(s), {token_total} total token(s).",
                lower_is_better=True,
            ),
            self._metric(
                "worker_failure_rate",
                self._ratio(runtime_observability.failed_jobs if runtime_observability else len(failed), runtime_total_jobs),
                "ratio",
                target=0.15,
                detail=(
                    f"{runtime_observability.failed_jobs} failed runtime job(s) / {runtime_total_jobs} total."
                    if runtime_observability
                    else f"{len(failed)} failed terminal task(s) / {len(terminal)} terminal task(s)."
                ),
                lower_is_better=True,
            ),
        ]

    def performance_profile(
        self,
        store: Any,
        *,
        project_root: Path,
        runtime: DistributedRuntimeSnapshot | None = None,
    ) -> dict[str, Any]:
        recent_context = store.recent_context_budgets(project_root=project_root, limit=100)
        estimated_tokens = [item.estimated_context_tokens for item in recent_context if item.estimated_context_tokens]
        runtime_observability = runtime.observability if runtime else None
        return {
            "context_samples": len(recent_context),
            "average_context_tokens": round(mean(estimated_tokens), 2) if estimated_tokens else 0,
            "queue_depth": runtime_observability.queued_jobs if runtime_observability else 0,
            "running_jobs": runtime_observability.running_jobs if runtime_observability else 0,
            "sqlite_path": str(store.db_path),
            "sqlite_size_bytes": store.db_path.stat().st_size if store.db_path.exists() else 0,
        }

    def scaling_profile(self, store: Any, *, project_root: Path) -> dict[str, Any]:
        project_intelligence = store.project_intelligence(project_root=project_root)
        file_count = len(project_intelligence.file_importance) if project_intelligence else 0
        architecture_modules = len(project_intelligence.architecture.major_modules) if project_intelligence else 0
        return {
            "monorepo_ready": True,
            "multi_language_ready": True,
            "distributed_runtime_ready": True,
            "indexed_file_importance_count": file_count,
            "architecture_module_count": architecture_modules,
            "large_project_guidance": [
                "Use Project Intelligence refreshes before large edits.",
                "Keep validation jobs on local or trusted workers unless enterprise policy allows remote execution.",
                "Prefer task checkpoints for every file-changing workflow.",
            ],
        }

    def packaging_profile(self) -> dict[str, Any]:
        return {
            "signed_installers": "planned",
            "auto_updates": "planned",
            "portable_builds": "supported_by_launch_scripts",
            "offline_deployment": "local_first_runtime_supported",
            "version_migration": "sqlite additive migrations",
            "launch_contract": "launch.ps1 behavior preserved",
        }

    def recommendations(
        self,
        metrics: list[ReliabilityMetric],
        recovery: RuntimeRecoverySnapshot,
        plugin_validation: list[PluginValidationResult],
        policy: EnterprisePolicyProfile,
    ) -> list[str]:
        recommendations: list[str] = []
        degraded = [metric for metric in metrics if metric.status == "degraded"]
        if degraded:
            recommendations.append("Prioritize degraded reliability metrics: " + ", ".join(metric.name for metric in degraded[:4]) + ".")
        recommendations.extend(recovery.recommended_actions[:4])
        invalid_plugins = [result for result in plugin_validation if not result.valid]
        if invalid_plugins:
            recommendations.append(f"Fix or keep disabled {len(invalid_plugins)} invalid plugin manifest(s).")
        if not policy.audit_trails:
            recommendations.append("Enable audit trails before enterprise or shared-workspace deployment.")
        if not policy.plugin_signing_required:
            recommendations.append("Require plugin signatures for enterprise profiles before loading third-party extensions.")
        if not recommendations:
            recommendations.append("Runtime hardening baseline is healthy; continue validating packaging and recovery workflows.")
        return recommendations

    def warnings(
        self,
        policy: EnterprisePolicyProfile,
        plugin_validation: list[PluginValidationResult],
    ) -> list[str]:
        warnings: list[str] = [
            "Productization controls are additive and do not change existing chat, task, checkpoint, or provider contracts."
        ]
        if policy.allow_remote_workers:
            warnings.append("Remote workers are allowed by active policy; keep worker trust revocable and auditable.")
        if any(result.warnings for result in plugin_validation):
            warnings.append("One or more plugin manifests has non-blocking warnings.")
        return warnings

    def _normalized_manifest(self, manifest: PluginManifest) -> PluginManifest:
        now = utc_now()
        capabilities = sorted(set(manifest.capabilities))
        permissions = sorted(set(manifest.permissions))
        checksum = manifest.checksum or self._manifest_checksum(manifest)
        return manifest.model_copy(
            update={
                "id": manifest.id.strip(),
                "name": manifest.name.strip() or manifest.id.strip(),
                "version": manifest.version.strip(),
                "api_version": manifest.api_version.strip(),
                "capabilities": capabilities,
                "permissions": permissions,
                "sandbox_profile": manifest.sandbox_profile.strip() or "isolated",
                "checksum": checksum,
                "update_channel": manifest.update_channel.strip() or "local",
                "created_at": manifest.created_at or now,
                "updated_at": now,
            }
        )

    def _manifest_checksum(self, manifest: PluginManifest) -> str:
        return _fingerprint(
            {
                "id": manifest.id.strip(),
                "name": manifest.name.strip(),
                "version": manifest.version.strip(),
                "api_version": manifest.api_version.strip(),
                "capabilities": sorted(set(manifest.capabilities)),
                "permissions": sorted(set(manifest.permissions)),
                "sandbox_profile": manifest.sandbox_profile.strip() or "isolated",
                "entrypoint": manifest.entrypoint,
                "ui_panel_route": manifest.ui_panel_route,
                "update_channel": manifest.update_channel.strip() or "local",
                "lifecycle_hooks": [hook.model_dump(mode="json") for hook in manifest.lifecycle_hooks],
            }
        )

    def _stale_worker_ids(self, workers: list[Any]) -> list[str]:
        now = datetime.now(timezone.utc)
        stale: list[str] = []
        for worker in workers:
            if getattr(worker, "kind", "") == "local":
                continue
            if getattr(worker, "status", "") in {"revoked", "disabled", "offline"}:
                continue
            heartbeat = _parse_time(getattr(worker, "last_heartbeat_at", ""))
            if heartbeat is None:
                stale.append(getattr(worker, "worker_id", "unknown"))
                continue
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            if (now - heartbeat).total_seconds() > 300:
                stale.append(getattr(worker, "worker_id", "unknown"))
        return stale

    def _metric(
        self,
        name: str,
        value: float,
        unit: str,
        *,
        target: float | None,
        detail: str,
        lower_is_better: bool = False,
    ) -> ReliabilityMetric:
        status = "unknown"
        if target is not None:
            if lower_is_better:
                status = "healthy" if value <= target else "watch" if value <= target * 1.5 else "degraded"
            else:
                status = "healthy" if value >= target else "watch" if value >= target * 0.75 else "degraded"
        return ReliabilityMetric(
            name=name,
            value=round(float(value), 4),
            unit=unit,
            status=status,
            target=target,
            detail=detail,
            trend="unknown",
        )

    def _ratio(self, numerator: int | float, denominator: int | float) -> float:
        if denominator <= 0:
            return 0.0
        return max(0.0, min(1.0, float(numerator) / float(denominator)))
