from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import shlex
from pathlib import Path
from typing import Any

from ..core_bridge import (
    AegisCoreBridge,
    CoreBridgeResult,
    DEFAULT_CORE_API_URL,
    core_envelope_error,
    normalize_core_base_url,
)
from ..schemas import (
    CheckpointFileInfo,
    CheckpointSummary,
    CommandRun,
    FileChange,
    ToolEvent,
)
from ..storage import utc_now


logger = logging.getLogger(__name__)

WEBSITE_CLIENT_ID = "website-backend"
DELEGATED_WORKFLOWS = (
    "changes.apply",
    "checkpoints.create",
    "checkpoints.list",
    "checkpoints.restore",
    "validation.run",
    "repair_project.workflow",
    "model.registry",
    "model.route",
    "engineering.execution",
    "engineering.memory",
    "engineering.metrics",
    "workflows.list",
    "workflow.dashboard",
    "workflow.step",
    "agent.runtime",
    "agent.coordination",
    "agent.delegation",
    "quality.gates",
    "quality.gates.evaluate",
    "workflow.quality",
    "quality.benchmarks",
    "quality.benchmark.run",
    "quality.evaluation_report",
    "quality.evaluation_reports",
    "knowledge.search",
    "knowledge.relationships",
    "knowledge.impact_analysis",
    "knowledge.architecture_summary",
    "release.manifest",
    "release.compatibility",
    "release.migrations",
    "release.update_plan",
    "security.status",
    "onboarding.status",
    "onboarding.updated",
    "onboarding.first_workflow",
    "settings.export",
    "settings.import",
    "personal.memory",
    "personal.memory.record",
    "personal.memory.deleted",
    "personal.memory.export",
    "personal.memory.controls",
    "runtime.interaction",
    "runtime.jobs",
    "runtime.job",
    "runtime.job.mutation",
    "runtime.streams",
    "runtime.processes",
    "runtime.sessions",
    "runtime.session.mutation",
    "runtime.voice",
    "runtime.voice.command",
    "runtime.replay",
    "collaboration.dashboard",
    "collaboration.roles",
    "collaboration.member",
    "collaboration.repository",
    "collaboration.workflow",
    "collaboration.approval",
    "collaboration.roadmap",
    "collaboration.audit",
    "governance.dashboard",
    "governance.policies",
    "governance.policy",
    "governance.evaluation",
    "governance.audit",
    "governance.compliance_export",
    "autopilot.modes",
    "autopilot.run",
    "autopilot.runs",
    "autopilot.dashboard",
    "autopilot.action",
    "autopilot.supervision",
    "autopilot.observability",
    "autopilot.memory",
    "autopilot.replay",
    "autopilot.client_hooks",
)


@dataclass(frozen=True)
class CoreDelegationResult:
    """Result wrapper for Website routes that may delegate to Aegis Core."""

    delegated: bool
    ok: bool
    reachable: bool
    status_code: int | None
    kind: str
    data: dict[str, Any] | list[Any] | None = None
    envelope: dict[str, Any] | None = None
    error: str = ""

    @property
    def should_fallback(self) -> bool:
        if self.delegated:
            return False
        if not self.reachable:
            return True
        return self.status_code in {404, 405, 502, 503, 504} or (
            self.status_code is not None and self.status_code >= 500
        )


class AegisCoreClient:
    """Website-facing client for Core-owned runtime workflows.

    The Website backend remains the compatibility gateway. This adapter only
    delegates workflows that Core now owns, and leaves existing Website logic as
    fallback when Core is offline or does not expose a route yet.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_CORE_API_URL,
        *,
        delegated_workflows_enabled: bool = True,
        timeout_seconds: float = 8.0,
        transport: Any = None,
        local_auth_token: str = "",
    ) -> None:
        self.base_url = normalize_core_base_url(base_url)
        self.delegated_workflows_enabled = delegated_workflows_enabled
        self.timeout_seconds = max(0.1, timeout_seconds)
        self._bridge = AegisCoreBridge(
            self.base_url,
            timeout_seconds=self.timeout_seconds,
            transport=transport,
            local_auth_token=local_auth_token,
        )
        self._last_core_error = ""
        self._fallback_mode_active = False
        self._last_mode_by_workflow: dict[str, str] = {}

    @classmethod
    def from_settings(cls, settings: Any) -> "AegisCoreClient":
        return cls(
            getattr(settings, "aegis_core_api_url", DEFAULT_CORE_API_URL),
            delegated_workflows_enabled=bool(getattr(settings, "aegis_core_delegated_workflows_enabled", True)),
            timeout_seconds=float(getattr(settings, "aegis_core_request_timeout_seconds", 8.0)),
            local_auth_token=getattr(settings, "aegis_core_local_token", "") or getattr(settings, "aegis_local_api_token", ""),
        )

    @property
    def last_core_error(self) -> str:
        return self._last_core_error

    @property
    def fallback_mode_active(self) -> bool:
        return self._fallback_mode_active

    async def health_check(self, workspace: str | Path) -> CoreDelegationResult:
        if not self.delegated_workflows_enabled:
            return self._disabled("health")
        result = await self._bridge.health_status(workspace)
        return self._wrap_bridge_result(result, "health", workflow="health")

    async def release_manifest(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/release/manifest",
            {"workspace": _workspace_text(workspace)},
            "release.manifest",
        )

    async def security_status(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/security/status",
            {"workspace": _workspace_text(workspace)},
            "security.status",
        )

    async def onboarding_status(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/onboarding/status",
            {"workspace": _workspace_text(workspace)},
            "onboarding.status",
        )

    async def update_onboarding(
        self,
        workspace: str | Path,
        *,
        completed_steps: list[str] | None = None,
        current_step: str | None = None,
        preferences: dict[str, Any] | None = None,
        first_workflow_completed_steps: list[str] | None = None,
        reset: bool = False,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "completed_steps": completed_steps,
            "current_step": current_step,
            "preferences": preferences,
            "first_workflow_completed_steps": first_workflow_completed_steps,
            "reset": reset,
        }
        return await self._post("/v1/onboarding", payload, "onboarding.updated")

    async def run_first_workflow(
        self,
        workspace: str | Path,
        *,
        action: str,
        dry_run: bool = True,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "action": action,
            "dry_run": dry_run,
            "source_client": WEBSITE_CLIENT_ID,
        }
        return await self._post("/v1/onboarding/first-workflow", payload, "onboarding.first_workflow")

    async def export_settings(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/settings/export",
            {"workspace": _workspace_text(workspace)},
            "settings.export",
        )

    async def import_settings(
        self,
        workspace: str | Path,
        *,
        settings_payload: dict[str, Any],
        dry_run: bool = True,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "settings": settings_payload,
            "dry_run": dry_run,
        }
        return await self._post("/v1/settings/import", payload, "settings.import")

    async def check_compatibility(
        self,
        workspace: str | Path,
        *,
        client_type: str = "website",
        client_version: str = "0.1.0",
        schema_version: str = "2026.05.12",
        capabilities: list[str] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "client_type": client_type,
            "client_version": client_version,
            "schema_version": schema_version,
            "capabilities": capabilities or ["release-compatibility", "website-gateway", "core-delegation"],
        }
        return await self._post("/v1/release/compatibility", payload, "release.compatibility")

    async def release_migrations(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/release/migrations",
            {"workspace": _workspace_text(workspace)},
            "release.migrations",
        )

    async def release_update_plan(
        self,
        component_id: str,
        *,
        current_version: str = "",
        target_version: str = "",
        package_uri: str = "",
        sha256: str = "",
    ) -> CoreDelegationResult:
        payload = {
            "component_id": component_id,
            "current_version": current_version,
            "target_version": target_version,
            "package_uri": package_uri,
            "sha256": sha256,
        }
        return await self._post("/v1/release/update-plan", payload, "release.update_plan")

    async def apply_changes(
        self,
        workspace: str | Path,
        changes: list[FileChange],
        *,
        dry_run: bool = False,
        summary: str = "Website generated changes apply",
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "changes": [_change_payload(change) for change in changes],
            "apply_all": True,
            "dry_run": dry_run,
            "summary": summary,
            "source_client": WEBSITE_CLIENT_ID,
        }
        return await self._post("/v1/changes/apply", payload, "changes.apply")

    async def create_checkpoint(
        self,
        workspace: str | Path,
        *,
        paths: list[str] | None = None,
        changes: list[FileChange] | None = None,
        summary: str = "Website checkpoint",
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "paths": paths or [],
            "changes": [_change_payload(change) for change in (changes or [])],
            "summary": summary,
            "source_client": WEBSITE_CLIENT_ID,
        }
        return await self._post("/v1/checkpoints/create", payload, "checkpoints.create")

    async def list_checkpoints(self, workspace: str | Path, *, limit: int = 50) -> CoreDelegationResult:
        return await self._get(
            "/v1/checkpoints",
            {"workspace": _workspace_text(workspace), "limit": max(1, min(200, int(limit)))},
            "checkpoints.list",
        )

    async def restore_checkpoint(
        self,
        workspace: str | Path,
        checkpoint_id: str,
        *,
        dry_run: bool = False,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "checkpoint_id": checkpoint_id,
            "dry_run": dry_run,
            "source_client": WEBSITE_CLIENT_ID,
        }
        return await self._post("/v1/checkpoints/restore", payload, "checkpoints.restore")

    async def run_validation(
        self,
        workspace: str | Path,
        *,
        command: str | list[str] | None = None,
        timeout_seconds: int = 120,
        task_id: str | None = None,
    ) -> CoreDelegationResult:
        command_payload = _command_payload(command)
        payload = {
            "workspace": _workspace_text(workspace),
            "command": command_payload,
            "timeout_seconds": max(1, min(900, int(timeout_seconds))),
            "source_client": WEBSITE_CLIENT_ID,
            "task_id": task_id,
        }
        return await self._post("/v1/validation/run", payload, "validation.run")

    async def create_repair_workflow(
        self,
        workspace: str | Path,
        *,
        validation_id: str = "",
        validation_summary: str = "",
        task_id: str | None = None,
    ) -> CoreDelegationResult:
        objective = validation_summary.strip() or "Repair the latest validation failure."
        payload = {
            "workspace": _workspace_text(workspace),
            "workflow_type": "repair_project",
            "objective": objective,
            "source_client": WEBSITE_CLIENT_ID,
            "metadata": {
                "source": "website-validation",
                "validation_id": validation_id,
                "website_task_id": task_id or "",
            },
        }
        return await self._post("/v1/workflows", payload, "workflow.created", workflow="repair_project.workflow")

    async def create_engineering_execution(
        self,
        workspace: str | Path,
        *,
        goal: str,
        mode: str = "safe_assisted",
        target_files: list[str] | None = None,
        context_files: list[str] | None = None,
        constraints: list[str] | None = None,
        validation_command: str | list[str] | None = None,
        max_repair_attempts: int | None = None,
        max_file_modifications: int = 25,
        roadmap_item_id: str | None = None,
        roadmap_phase_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "goal": goal,
            "mode": mode,
            "source_client": WEBSITE_CLIENT_ID,
            "target_files": target_files or [],
            "context_files": context_files or [],
            "constraints": constraints or [],
            "validation_command": _command_payload(validation_command),
            "max_repair_attempts": max_repair_attempts,
            "max_file_modifications": max(1, min(100, int(max_file_modifications))),
            "roadmap_item_id": roadmap_item_id,
            "roadmap_phase_id": roadmap_phase_id,
            "metadata": metadata or {},
        }
        return await self._post(
            "/v1/engineering/executions",
            payload,
            "engineering.execution.created",
            workflow="engineering.execution",
        )

    async def step_engineering_execution(
        self,
        workspace: str | Path,
        execution_id: str,
        *,
        action: str = "advance",
        stage_key: str | None = None,
        approval: bool = False,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        request_payload = {
            "workspace": _workspace_text(workspace),
            "action": action,
            "stage_key": stage_key,
            "approval": approval,
            "summary": summary,
            "payload": payload or {},
        }
        return await self._post(
            f"/v1/engineering/executions/{execution_id}/step",
            request_payload,
            "engineering.execution.step",
            workflow="engineering.execution",
        )

    async def engineering_memory(self, workspace: str | Path, *, refresh: bool = False) -> CoreDelegationResult:
        return await self._get(
            "/v1/engineering/memory",
            {"workspace": _workspace_text(workspace), "refresh": refresh},
            "engineering.memory",
        )

    async def engineering_metrics(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/engineering/metrics",
            {"workspace": _workspace_text(workspace)},
            "engineering.metrics",
        )

    async def autopilot_modes(self) -> CoreDelegationResult:
        return await self._get("/v1/autopilot/modes", {}, "autopilot.modes")

    async def start_autopilot(
        self,
        workspace: str | Path,
        *,
        objective: str,
        mode: str = "semi_autonomous",
        workflow_type: str = "generate_feature",
        roadmap: list[dict[str, Any]] | None = None,
        target_files: list[str] | None = None,
        constraints: list[str] | None = None,
        validation_commands: list[dict[str, Any]] | None = None,
        execution_plan: dict[str, Any] | None = None,
        specialization: str | None = None,
        approval: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "objective": objective,
            "mode": mode,
            "workflow_type": workflow_type,
            "roadmap": roadmap or [],
            "target_files": target_files or [],
            "constraints": constraints or [],
            "validation_commands": validation_commands or [],
            "execution_plan": execution_plan or {},
            "specialization": specialization,
            "client_id": WEBSITE_CLIENT_ID,
            "approval": approval,
            "metadata": metadata or {},
        }
        return await self._post("/v1/autopilot/start", payload, "autopilot.run")

    async def list_autopilot_runs(
        self,
        workspace: str | Path,
        *,
        status: str | None = None,
        mode: str | None = None,
        workflow_type: str | None = None,
        limit: int = 50,
    ) -> CoreDelegationResult:
        params = {
            "workspace": _workspace_text(workspace),
            "status": status,
            "mode": mode,
            "workflow_type": workflow_type,
            "limit": max(1, min(200, int(limit))),
        }
        return await self._get("/v1/autopilot/runs", params, "autopilot.runs")

    async def autopilot_run(self, workspace: str | Path, autopilot_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/autopilot/runs/{autopilot_id}",
            {"workspace": _workspace_text(workspace)},
            "autopilot.dashboard",
        )

    async def autopilot_action(
        self,
        workspace: str | Path,
        autopilot_id: str,
        *,
        action: str = "advance",
        approval: bool = False,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        request_payload = {
            "workspace": _workspace_text(workspace),
            "action": action,
            "approval": approval,
            "summary": summary,
            "payload": payload or {},
            "client_id": WEBSITE_CLIENT_ID,
        }
        return await self._post(
            f"/v1/autopilot/runs/{autopilot_id}/action",
            request_payload,
            "autopilot.action",
        )

    async def autopilot_replay(self, workspace: str | Path, autopilot_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/autopilot/runs/{autopilot_id}/replay",
            {"workspace": _workspace_text(workspace)},
            "autopilot.replay",
        )

    async def autopilot_supervision(self, workspace: str | Path, autopilot_id: str | None = None) -> CoreDelegationResult:
        return await self._get(
            "/v1/autopilot/supervision",
            {"workspace": _workspace_text(workspace), "autopilot_id": autopilot_id},
            "autopilot.supervision",
        )

    async def autopilot_observability(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/autopilot/observability",
            {"workspace": _workspace_text(workspace)},
            "autopilot.observability",
        )

    async def autopilot_memory(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/autopilot/memory",
            {"workspace": _workspace_text(workspace)},
            "autopilot.memory",
        )

    async def autopilot_client_hooks(self) -> CoreDelegationResult:
        return await self._get("/v1/autopilot/client-hooks", {}, "autopilot.client_hooks")

    async def personal_memory(
        self,
        workspace: str | Path,
        *,
        category: str | None = None,
        query: str = "",
        include_archived: bool = False,
        limit: int = 100,
    ) -> CoreDelegationResult:
        params: dict[str, Any] = {
            "workspace": _workspace_text(workspace),
            "query": query,
            "include_archived": include_archived,
            "limit": max(1, min(500, int(limit))),
        }
        if category:
            params["category"] = category
        return await self._get("/v1/personal-memory", params, "personal.memory")

    async def create_personal_memory(
        self,
        workspace: str | Path,
        *,
        category: str,
        title: str,
        content: str,
        scope: str = "project",
        tags: list[str] | None = None,
        related_files: list[str] | None = None,
        pinned: bool = False,
        confidence: float = 0.75,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "category": category,
            "title": title,
            "content": content,
            "scope": scope,
            "tags": tags or [],
            "related_files": related_files or [],
            "source": WEBSITE_CLIENT_ID,
            "pinned": pinned,
            "confidence": confidence,
            "metadata": metadata or {},
        }
        return await self._post("/v1/personal-memory", payload, "personal.memory.record")

    async def update_personal_memory(
        self,
        workspace: str | Path,
        memory_id: str,
        *,
        category: str | None = None,
        title: str | None = None,
        content: str | None = None,
        scope: str | None = None,
        tags: list[str] | None = None,
        related_files: list[str] | None = None,
        pinned: bool | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "category": category,
            "title": title,
            "content": content,
            "scope": scope,
            "tags": tags,
            "related_files": related_files,
            "pinned": pinned,
            "confidence": confidence,
            "metadata": metadata,
        }
        return await self._post(f"/v1/personal-memory/records/{memory_id}", payload, "personal.memory.record")

    async def delete_personal_memory(
        self,
        workspace: str | Path,
        memory_id: str,
        *,
        hard_delete: bool = True,
        reason: str = "website memory route",
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "hard_delete": hard_delete,
            "reason": reason,
        }
        return await self._post(f"/v1/personal-memory/records/{memory_id}/delete", payload, "personal.memory.deleted")

    async def export_personal_memory(
        self,
        workspace: str | Path,
        *,
        categories: list[str] | None = None,
        include_archived: bool = False,
        redact_sensitive: bool = True,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "categories": categories or [],
            "include_archived": include_archived,
            "include_controls": True,
            "redact_sensitive": redact_sensitive,
        }
        return await self._post("/v1/personal-memory/export", payload, "personal.memory.export")

    async def update_personal_memory_controls(
        self,
        workspace: str | Path,
        *,
        category: str | None = None,
        enabled: bool | None = None,
        retention_days: int | None = None,
        include_in_orchestration: bool | None = None,
        encrypted: bool | None = None,
        local_only: bool | None = None,
        disabled_categories: list[str] | None = None,
        allowed_scopes: list[str] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "category": category,
            "enabled": enabled,
            "retention_days": retention_days,
            "include_in_orchestration": include_in_orchestration,
            "encrypted": encrypted,
            "local_only": local_only,
            "disabled_categories": disabled_categories,
            "allowed_scopes": allowed_scopes,
        }
        return await self._post("/v1/personal-memory/controls", payload, "personal.memory.controls")

    async def agent_runtime(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/agents/runtime",
            {"workspace": _workspace_text(workspace)},
            "agent.runtime",
        )

    async def list_workflows(
        self,
        workspace: str | Path,
        *,
        include_completed: bool = False,
        limit: int = 30,
    ) -> CoreDelegationResult:
        return await self._get(
            "/v1/workflows",
            {
                "workspace": _workspace_text(workspace),
                "include_completed": include_completed,
                "limit": max(1, min(200, int(limit))),
            },
            "workflows.list",
        )

    async def workflow_dashboard(self, workspace: str | Path, workflow_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/workflows/{workflow_id}",
            {"workspace": _workspace_text(workspace)},
            "workflow.dashboard",
        )

    async def workflow_agent_coordination(self, workspace: str | Path, workflow_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/workflows/{workflow_id}/agents",
            {"workspace": _workspace_text(workspace)},
            "agent.coordination",
        )

    async def step_workflow(
        self,
        workspace: str | Path,
        workflow_id: str,
        *,
        action: str = "advance",
        task_id: str | None = None,
        approval: bool = False,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        request_payload = {
            "workspace": _workspace_text(workspace),
            "action": action,
            "task_id": task_id,
            "approval": approval,
            "summary": summary,
            "payload": payload or {},
        }
        return await self._post(
            f"/v1/workflows/{workflow_id}/step",
            request_payload,
            "workflow.step",
        )

    async def delegate_agent_task(
        self,
        workspace: str | Path,
        workflow_id: str,
        *,
        task_id: str,
        agent_id: str,
        approval: bool = False,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        request_payload = {
            "workspace": _workspace_text(workspace),
            "task_id": task_id,
            "agent_id": agent_id,
            "approval": approval,
            "reason": reason,
            "metadata": metadata or {},
        }
        return await self._post(
            f"/v1/workflows/{workflow_id}/agents/delegate",
            request_payload,
            "agent.delegation",
        )

    async def quality_gates(self, workspace: str | Path, *, limit: int = 50) -> CoreDelegationResult:
        return await self._get(
            "/v1/quality-gates",
            {"workspace": _workspace_text(workspace), "limit": max(1, min(200, int(limit)))},
            "quality.gates",
        )

    async def evaluate_quality_gates(
        self,
        workspace: str | Path,
        *,
        changes: list[dict[str, Any]] | None = None,
        workflow_id: str | None = None,
        validation_id: str | None = None,
        validation: dict[str, Any] | None = None,
        approval: bool = False,
        checkpoint_id: str | None = None,
        max_files_changed: int = 25,
        restricted_paths: list[str] | None = None,
        validation_required: bool = False,
        dry_run: bool = True,
        persist: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "changes": changes or [],
            "workflow_id": workflow_id,
            "validation_id": validation_id,
            "validation": validation,
            "approval": approval,
            "checkpoint_id": checkpoint_id,
            "max_files_changed": max(1, min(250, int(max_files_changed))),
            "restricted_paths": restricted_paths or [],
            "validation_required": validation_required,
            "dry_run": dry_run,
            "persist": persist,
            "metadata": metadata or {},
        }
        return await self._post("/v1/quality-gates/evaluate", payload, "quality.gates.evaluate")

    async def workflow_quality(self, workspace: str | Path, workflow_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/workflows/{workflow_id}/quality",
            {"workspace": _workspace_text(workspace)},
            "workflow.quality",
        )

    async def benchmarks(self, workspace: str | Path, *, limit: int = 50) -> CoreDelegationResult:
        return await self._get(
            "/v1/benchmarks",
            {"workspace": _workspace_text(workspace), "limit": max(1, min(200, int(limit)))},
            "quality.benchmarks",
        )

    async def run_benchmark(
        self,
        workspace: str | Path,
        *,
        suite_ids: list[str] | None = None,
        workflow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "suite_ids": suite_ids or [],
            "workflow_id": workflow_id,
            "metadata": metadata or {},
        }
        return await self._post("/v1/benchmarks/run", payload, "quality.benchmark.run")

    async def evaluation_reports(
        self,
        workspace: str | Path,
        *,
        workflow_id: str | None = None,
        limit: int = 50,
    ) -> CoreDelegationResult:
        params = {"workspace": _workspace_text(workspace), "limit": max(1, min(200, int(limit)))}
        if workflow_id:
            params["workflow_id"] = workflow_id
        return await self._get("/v1/evaluation-reports", params, "quality.evaluation_reports")

    async def create_evaluation_report(
        self,
        workspace: str | Path,
        *,
        workflow_id: str | None = None,
        quality_run_id: str | None = None,
        title: str = "",
        changes: list[dict[str, Any]] | None = None,
        tests_run: list[str] | None = None,
        repairs_attempted: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "workflow_id": workflow_id,
            "quality_run_id": quality_run_id,
            "title": title,
            "changes": changes or [],
            "tests_run": tests_run or [],
            "repairs_attempted": repairs_attempted or [],
            "metadata": metadata or {},
        }
        return await self._post("/v1/evaluation-reports", payload, "quality.evaluation_report")

    async def knowledge_search(
        self,
        workspace: str | Path,
        *,
        query: str,
        node_type: str | None = None,
        limit: int = 25,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "query": query,
            "node_type": node_type,
            "limit": max(1, min(100, int(limit))),
        }
        return await self._post("/v1/knowledge/search", payload, "knowledge.search")

    async def knowledge_relationships(
        self,
        workspace: str | Path,
        *,
        focus: str,
        relationship: str | None = None,
        depth: int = 1,
        direction: str = "both",
        limit: int = 50,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "focus": focus,
            "relationship": relationship,
            "depth": max(1, min(4, int(depth))),
            "direction": direction,
            "limit": max(1, min(200, int(limit))),
        }
        return await self._post("/v1/knowledge/relationships", payload, "knowledge.relationships")

    async def knowledge_impact_analysis(
        self,
        workspace: str | Path,
        *,
        target: str,
        change_type: str = "modify",
        limit: int = 100,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "target": target,
            "change_type": change_type,
            "limit": max(1, min(200, int(limit))),
        }
        return await self._post("/v1/knowledge/impact-analysis", payload, "knowledge.impact_analysis")

    async def knowledge_architecture_summary(self, workspace: str | Path, *, refresh: bool = False) -> CoreDelegationResult:
        return await self._get(
            "/v1/knowledge/architecture-summary",
            {"workspace": _workspace_text(workspace), "refresh": refresh},
            "knowledge.architecture_summary",
        )

    async def model_registry(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/models/registry",
            {"workspace": _workspace_text(workspace)},
            "model.registry",
        )

    async def distributed_runtime(self, workspace: str | Path, *, include_audit: bool = True, limit: int = 100) -> CoreDelegationResult:
        return await self._get(
            "/v1/distributed-runtime",
            {"workspace": _workspace_text(workspace), "include_audit": include_audit, "limit": max(1, min(500, int(limit)))},
            "distributed.runtime",
        )

    async def runtime_interaction(self, workspace: str | Path, *, limit: int = 100) -> CoreDelegationResult:
        return await self._get(
            "/v1/runtime/terminals",
            {"workspace": _workspace_text(workspace), "limit": max(1, min(300, int(limit)))},
            "runtime.interaction",
        )

    async def runtime_jobs(
        self,
        workspace: str | Path,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> CoreDelegationResult:
        params: dict[str, Any] = {"workspace": _workspace_text(workspace), "limit": max(1, min(300, int(limit)))}
        if status:
            params["status"] = status
        return await self._get("/v1/runtime/jobs", params, "runtime.jobs")

    async def launch_runtime_job(
        self,
        workspace: str | Path,
        *,
        command: str | list[str],
        cwd: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        terminal_id: str | None = None,
        title: str = "",
        timeout_seconds: int = 120,
        approval: bool = False,
        dry_run: bool = False,
        wait: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "command": command,
            "cwd": cwd,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "terminal_id": terminal_id,
            "title": title,
            "timeout_seconds": max(1, min(3600, int(timeout_seconds))),
            "approval": approval,
            "dry_run": dry_run,
            "wait": wait,
            "source_client": WEBSITE_CLIENT_ID,
            "metadata": metadata or {},
        }
        return await self._post("/v1/runtime/jobs", payload, "runtime.job.mutation")

    async def runtime_job(self, workspace: str | Path, job_id: str) -> CoreDelegationResult:
        return await self._get(
            f"/v1/runtime/jobs/{job_id}",
            {"workspace": _workspace_text(workspace)},
            "runtime.job",
        )

    async def cancel_runtime_job(self, workspace: str | Path, job_id: str, *, reason: str = "") -> CoreDelegationResult:
        payload = {"workspace": _workspace_text(workspace), "reason": reason}
        return await self._post(f"/v1/runtime/jobs/{job_id}/cancel", payload, "runtime.job.mutation")

    async def retry_runtime_job(
        self,
        workspace: str | Path,
        job_id: str,
        *,
        approval: bool | None = None,
        wait: bool = True,
        timeout_seconds: int | None = None,
        reason: str = "",
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "approval": approval,
            "wait": wait,
            "timeout_seconds": timeout_seconds,
            "reason": reason,
        }
        return await self._post(f"/v1/runtime/jobs/{job_id}/retry", payload, "runtime.job.mutation")

    async def runtime_streams(
        self,
        workspace: str | Path,
        *,
        job_id: str | None = None,
        workflow_id: str | None = None,
        since: int = 0,
        limit: int = 100,
    ) -> CoreDelegationResult:
        params: dict[str, Any] = {
            "workspace": _workspace_text(workspace),
            "since": max(0, int(since)),
            "limit": max(1, min(500, int(limit))),
            "as_sse": False,
        }
        if job_id:
            params["job_id"] = job_id
        if workflow_id:
            params["workflow_id"] = workflow_id
        return await self._get("/v1/runtime/streams", params, "runtime.streams")

    async def runtime_processes(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/runtime/processes",
            {"workspace": _workspace_text(workspace)},
            "runtime.processes",
        )

    async def runtime_sessions(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/runtime/sessions",
            {"workspace": _workspace_text(workspace)},
            "runtime.sessions",
        )

    async def create_runtime_session(
        self,
        workspace: str | Path,
        *,
        workflow_id: str = "",
        title: str = "",
        owner_client_id: str = WEBSITE_CLIENT_ID,
        participants: list[dict[str, Any]] | None = None,
        spectators: list[dict[str, Any]] | None = None,
        approval_delegates: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "workflow_id": workflow_id,
            "title": title,
            "owner_client_id": owner_client_id,
            "participants": participants or [],
            "spectators": spectators or [],
            "approval_delegates": approval_delegates or [],
            "metadata": metadata or {},
        }
        return await self._post("/v1/runtime/sessions", payload, "runtime.session.mutation")

    async def sync_runtime_session(self, workspace: str | Path, session_id: str, **kwargs) -> CoreDelegationResult:
        payload = {"workspace": _workspace_text(workspace), **kwargs}
        return await self._post(f"/v1/runtime/sessions/{session_id}/sync", payload, "runtime.session.mutation")

    async def runtime_voice(self, workspace: str | Path) -> CoreDelegationResult:
        return await self._get(
            "/v1/runtime/voice",
            {"workspace": _workspace_text(workspace)},
            "runtime.voice",
        )

    async def route_voice_command(
        self,
        workspace: str | Path,
        *,
        transcript: str,
        workflow_id: str = "",
        client_id: str = WEBSITE_CLIENT_ID,
        dry_run: bool = True,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "transcript": transcript,
            "workflow_id": workflow_id,
            "client_id": client_id,
            "dry_run": dry_run,
        }
        return await self._post("/v1/runtime/voice/command", payload, "runtime.voice.command")

    async def runtime_replay(
        self,
        workspace: str | Path,
        *,
        workflow_id: str | None = None,
        job_id: str | None = None,
        limit: int = 200,
    ) -> CoreDelegationResult:
        params: dict[str, Any] = {"workspace": _workspace_text(workspace), "limit": max(1, min(500, int(limit)))}
        if workflow_id:
            params["workflow_id"] = workflow_id
        if job_id:
            params["job_id"] = job_id
        return await self._get("/v1/runtime/replay", params, "runtime.replay")

    async def collaboration_dashboard(
        self,
        workspace: str | Path,
        *,
        user_id: str | None = None,
        role: str | None = None,
        limit: int = 100,
    ) -> CoreDelegationResult:
        return await self._get(
            "/v1/collaboration",
            {
                "workspace": _workspace_text(workspace),
                "user_id": user_id,
                "role": role,
                "limit": max(1, min(500, int(limit))),
            },
            "collaboration.dashboard",
        )

    async def create_collaboration_workflow(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/collaboration/workflows",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.workflow",
        )

    async def register_collaboration_member(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/collaboration/members",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.member",
        )

    async def register_collaboration_repository(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/collaboration/repositories",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.repository",
        )

    async def collaboration_workflow_action(
        self,
        workspace: str | Path,
        workflow_id: str,
        payload: dict[str, Any],
    ) -> CoreDelegationResult:
        return await self._post(
            f"/v1/collaboration/workflows/{workflow_id}/action",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.workflow",
        )

    async def create_collaboration_approval(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/collaboration/approvals",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.approval",
        )

    async def decide_collaboration_approval(
        self,
        workspace: str | Path,
        approval_id: str,
        payload: dict[str, Any],
    ) -> CoreDelegationResult:
        return await self._post(
            f"/v1/collaboration/approvals/{approval_id}/decision",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.approval",
        )

    async def assign_collaboration_roadmap_item(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/collaboration/roadmap/items",
            {"workspace": _workspace_text(workspace), **payload},
            "collaboration.roadmap",
        )

    async def governance_dashboard(self, workspace: str | Path, *, include_audit: bool = True, limit: int = 100) -> CoreDelegationResult:
        return await self._get(
            "/v1/governance",
            {"workspace": _workspace_text(workspace), "include_audit": include_audit, "limit": max(1, min(500, int(limit)))},
            "governance.dashboard",
        )

    async def evaluate_governance_policy(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/governance/evaluate",
            {"workspace": _workspace_text(workspace), **payload},
            "governance.evaluation",
        )

    async def export_governance_compliance(self, workspace: str | Path, payload: dict[str, Any]) -> CoreDelegationResult:
        return await self._post(
            "/v1/governance/compliance/export",
            {"workspace": _workspace_text(workspace), **payload},
            "governance.compliance_export",
        )

    async def route_model(
        self,
        workspace: str | Path,
        *,
        task_type: str = "chat",
        workflow_type: str | None = None,
        difficulty: str | None = None,
        route_profile: str | None = None,
        required_capabilities: list[str] | None = None,
        privacy_sensitive: bool = False,
        provider_id: str | None = None,
        model: str | None = None,
        allow_cloud: bool = False,
        cloud_approved: bool = False,
        context_files: list[str] | None = None,
        local_failure_reason: str | None = None,
    ) -> CoreDelegationResult:
        payload = {
            "workspace": _workspace_text(workspace),
            "task_type": task_type,
            "workflow_type": workflow_type,
            "difficulty": difficulty,
            "route_profile": route_profile,
            "required_capabilities": required_capabilities or [],
            "privacy_sensitive": privacy_sensitive,
            "provider_id": provider_id,
            "model": model,
            "allow_cloud": allow_cloud,
            "cloud_approved": cloud_approved,
            "context_files": context_files or [],
            "local_failure_reason": local_failure_reason,
        }
        return await self._post("/v1/models/route", payload, "model.route")

    async def runtime_status(self, workspace: str | Path) -> dict[str, Any]:
        health = await self.health_check(workspace)
        compatibility = await self.check_compatibility(workspace)
        distributed = await self.distributed_runtime(workspace, include_audit=False, limit=1)
        connected = bool(health.delegated and health.ok)
        compatibility_data = compatibility.data if compatibility.delegated and isinstance(compatibility.data, dict) else {}
        distributed_data = distributed.data if distributed.delegated and isinstance(distributed.data, dict) else {}
        distributed_observability = distributed_data.get("observability", {}) if isinstance(distributed_data.get("observability"), dict) else {}
        return {
            "core_url": self.base_url,
            "core_connected": connected,
            "core_status": "connected" if connected else "disconnected",
            "release_compatibility": compatibility_data,
            "release_compatible": bool(compatibility_data.get("compatible", False)) if compatibility_data else False,
            "release_status": str(compatibility_data.get("status") or "unknown"),
            "delegated_workflows_enabled": self.delegated_workflows_enabled,
            "delegated_workflows": list(DELEGATED_WORKFLOWS),
            "fallback_mode_active": self._fallback_mode_active or health.should_fallback or compatibility.should_fallback,
            "last_core_error": self._last_core_error or health.error or compatibility.error,
            "last_mode_by_workflow": dict(self._last_mode_by_workflow),
            "distributed_runtime": {
                "connected": bool(distributed.delegated),
                "node_count": int((distributed_observability.get("nodes") or {}).get("total", 0)) if isinstance(distributed_observability.get("nodes"), dict) else 0,
                "active_workloads": int((distributed_observability.get("workloads") or {}).get("active", 0)) if isinstance(distributed_observability.get("workloads"), dict) else 0,
                "queued_workloads": int((distributed_observability.get("workloads") or {}).get("queued", 0)) if isinstance(distributed_observability.get("workloads"), dict) else 0,
                "fallback": distributed.should_fallback,
                "error": distributed.error,
            },
        }

    def record_fallback(self, workflow: str, reason: str) -> None:
        self._fallback_mode_active = True
        self._last_core_error = reason
        self._last_mode_by_workflow[workflow] = "fallback"
        logger.info("Aegis Core delegation fallback for %s: %s", workflow, reason)

    def record_local_only(self, workflow: str, reason: str) -> None:
        self._last_mode_by_workflow[workflow] = "local"
        logger.info("Aegis Core delegation skipped for %s: %s", workflow, reason)

    async def _get(
        self,
        path: str,
        params: dict[str, Any],
        expected_kind: str,
        *,
        workflow: str | None = None,
    ) -> CoreDelegationResult:
        if not self.delegated_workflows_enabled:
            return self._disabled(expected_kind)
        result = await self._bridge.get(path, params=params, expected_kind=expected_kind)
        return self._wrap_bridge_result(result, expected_kind, workflow=workflow or expected_kind)

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        expected_kind: str,
        *,
        workflow: str | None = None,
    ) -> CoreDelegationResult:
        if not self.delegated_workflows_enabled:
            return self._disabled(expected_kind)
        result = await self._bridge.post(path, payload=payload, expected_kind=expected_kind)
        return self._wrap_bridge_result(result, expected_kind, workflow=workflow or expected_kind)

    def _wrap_bridge_result(
        self,
        result: CoreBridgeResult,
        expected_kind: str,
        *,
        workflow: str,
    ) -> CoreDelegationResult:
        delegated = (
            result.reachable
            and result.status_code is not None
            and 200 <= result.status_code < 300
            and result.kind == expected_kind
            and result.data is not None
        )
        error = result.error
        if not error and isinstance(result.envelope, dict) and not result.ok:
            error = core_envelope_error(result.envelope)

        if delegated:
            self._fallback_mode_active = False
            self._last_mode_by_workflow[workflow] = "core"
            if result.ok:
                self._last_core_error = ""
            logger.info("Aegis Core delegated %s via %s", workflow, expected_kind)
        else:
            self._last_core_error = error or "Aegis Core did not return a usable contract response."
            self._last_mode_by_workflow[workflow] = "core_error"
            logger.warning("Aegis Core delegation failed for %s: %s", workflow, self._last_core_error)

        return CoreDelegationResult(
            delegated=delegated,
            ok=result.ok,
            reachable=result.reachable,
            status_code=result.status_code,
            kind=result.kind,
            data=result.data,
            envelope=result.envelope,
            error=error,
        )

    def _disabled(self, kind: str) -> CoreDelegationResult:
        message = "Aegis Core delegated workflows are disabled."
        self._last_core_error = message
        self._fallback_mode_active = True
        self._last_mode_by_workflow[kind] = "fallback"
        return CoreDelegationResult(
            delegated=False,
            ok=False,
            reachable=False,
            status_code=None,
            kind=kind,
            data=None,
            envelope=None,
            error=message,
        )


def checkpoint_summary_from_core(value: dict[str, Any]) -> CheckpointSummary:
    raw_files = value.get("files") if isinstance(value.get("files"), list) else []
    files = [
        CheckpointFileInfo(path=str(item.get("path") or ""), state=str(item.get("state") or "missing"))
        for item in raw_files
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    return CheckpointSummary(
        id=str(value.get("id") or ""),
        created_at=str(value.get("created_at") or ""),
        file_count=int(value.get("file_count") or len(files)),
        present_count=int(value.get("present_count") or sum(1 for item in files if item.state == "present")),
        missing_count=int(value.get("missing_count") or sum(1 for item in files if item.state == "missing")),
        files=files,
    )


def command_run_from_core_validation(value: dict[str, Any], workspace: str | Path) -> CommandRun | None:
    validation = value.get("validation") if isinstance(value.get("validation"), dict) else {}
    command = validation.get("command")
    if command in (None, "", []):
        return None
    command_text = " ".join(str(part) for part in command) if isinstance(command, list) else str(command)
    blocked = bool(validation.get("blocked", False))
    timed_out = bool(validation.get("timed_out", False))
    start_failed = bool(validation.get("start_failed", False))
    exit_code = validation.get("returncode")
    exit_code = int(exit_code) if isinstance(exit_code, int) else None
    stderr = str(validation.get("stderr") or "")
    stdout = str(validation.get("stdout") or "")
    ok = bool(validation.get("ok", False))
    reason = _validation_reason(ok=ok, blocked=blocked, timed_out=timed_out, start_failed=start_failed, stderr=stderr)
    return CommandRun(
        command=command_text,
        cwd=_workspace_text(workspace),
        allowed=not blocked,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        reason=reason,
        category="permission" if blocked else "timeout" if timed_out else "startup" if start_failed else "validation",
        summary=_validation_summary(ok=ok, blocked=blocked, timed_out=timed_out, start_failed=start_failed, exit_code=exit_code),
    )


def core_event(kind: str, title: str, *, status: str = "ok", detail: str = "", payload: dict[str, Any] | None = None) -> ToolEvent:
    return ToolEvent(
        kind=kind,
        title=title,
        status=status,  # type: ignore[arg-type]
        detail=detail,
        payload=payload or {},
        created_at=utc_now(),
    )


def _workspace_text(workspace: str | Path) -> str:
    return str(Path(workspace).resolve())


def _change_payload(change: FileChange) -> dict[str, Any]:
    payload = change.model_dump(mode="json")
    if "content" in payload and payload["content"] is None:
        payload.pop("content")
    return payload


def _command_payload(command: str | list[str] | None) -> list[str] | None:
    if command is None:
        return None
    if isinstance(command, list):
        return [str(part) for part in command if str(part).strip()]
    text = command.strip()
    if not text:
        return None
    try:
        return shlex.split(text, posix=(os.name != "nt"))
    except ValueError:
        return text.split()


def _validation_summary(
    *,
    ok: bool,
    blocked: bool,
    timed_out: bool,
    start_failed: bool,
    exit_code: int | None,
) -> str:
    if ok:
        return "Validation passed."
    if blocked:
        return "Validation command was blocked by Aegis Core safety rules."
    if timed_out:
        return "Validation command timed out."
    if start_failed:
        return "Validation command could not start."
    if exit_code is not None:
        return f"Validation command exited with {exit_code}."
    return "Validation did not pass."


def _validation_reason(
    *,
    ok: bool,
    blocked: bool,
    timed_out: bool,
    start_failed: bool,
    stderr: str,
) -> str:
    if ok:
        return "Command finished."
    if stderr:
        return stderr
    if blocked:
        return "Command blocked by Aegis Core safety rules."
    if timed_out:
        return "Command timed out."
    if start_failed:
        return "Command could not start."
    return "Command finished with a validation failure."
