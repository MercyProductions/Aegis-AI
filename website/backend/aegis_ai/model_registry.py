from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import (
    ModelBenchmarkProviderScore,
    ModelAdapterHealthInfo,
    ModelAttemptTelemetryEntry,
    ModelRegistryCheckpointDiffResponse,
    ModelRegistryCheckpointEntityDiff,
    ModelRegistryCheckpointInfo,
    ModelRegistryCheckpointListResponse,
    ModelRegistryCheckpointSettingDiff,
    ModelRegistryAuditIssue,
    ModelRegistryAuditResponse,
    ModelRegistryRouteCoverage,
    ModelRegistrySetupAction,
    ModelRegistryBenchmarkPreviewResponse,
    ModelRegistryBenchmarkRoleDiff,
    ModelRegistryProvider,
    ModelRegistryProviderUpsertRequest,
    ModelRegistryResponse,
    ModelRegistryRole,
    ModelRouteHealthInfo,
    ModelRoutingPreset,
    ModelTokenizerDiagnosticInfo,
    RoutePolicyDiffResponse,
    RoutePolicyProviderProposal,
    RoutePolicyRoleProposal,
)
from .settings import Settings
from .providers.base import api_family, is_local_endpoint, provider_label, secret_env_name, secret_value


REGISTRY_VERSION = 4


class ModelRegistryManager:
    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root
        self.settings = settings
        self.registry_path = project_root / "data" / "model_registry.json"
        self.checkpoint_dir = project_root / "data" / "model_registry_checkpoints"

    def snapshot(self) -> ModelRegistryResponse:
        payload = self._refresh_provider_availability(self._load_or_create())
        return ModelRegistryResponse(
            version=int(payload.get("version", 1) or 1),
            active_provider_id=str(payload.get("active_provider_id", self._active_provider_id()) or ""),
            active_model=self.settings.aegis_model_name,
            router_enabled=bool(payload.get("router_enabled", False)),
            fallback_supported=bool(payload.get("fallback_supported", True)),
            message=str(
                payload.get(
                    "message",
                    "Registry foundation is ready. Routing policies are visible; live router execution comes next.",
                )
                or ""
            ),
            providers=[
                ModelRegistryProvider.model_validate(provider)
                for provider in payload.get("providers", [])
                if isinstance(provider, dict)
            ],
            roles=[
                ModelRegistryRole.model_validate(role)
                for role in payload.get("roles", [])
                if isinstance(role, dict)
            ],
            presets=[
                ModelRoutingPreset.model_validate(preset)
                for preset in payload.get("presets", [])
                if isinstance(preset, dict)
            ],
        )

    def upsert_provider(self, request: ModelRegistryProviderUpsertRequest) -> ModelRegistryResponse:
        provider = self._normalize_provider(request.model_dump(), None)
        provider["id"] = str(provider.get("id", "")).strip()
        if not provider["id"]:
            raise ValueError("Provider id is required.")

        payload = self._load_or_create()
        providers = [item for item in payload.get("providers", []) if isinstance(item, dict)]
        replaced = False
        for index, existing in enumerate(providers):
            if str(existing.get("id", "")).strip() == provider["id"]:
                providers[index] = provider
                replaced = True
                break
        if not replaced:
            providers.append(provider)

        payload["providers"] = providers
        payload["message"] = f"Provider registry saved: {provider['label']}."
        action = "updated" if replaced else "added"
        self._save(payload, backup_reason=f"Before provider {action}: {provider['id']}")
        return self.snapshot()

    def delete_provider(self, provider_id: str) -> ModelRegistryResponse:
        provider_id = provider_id.strip()
        if not provider_id:
            raise ValueError("Provider id is required.")

        payload = self._load_or_create()
        if provider_id == str(payload.get("active_provider_id", self._active_provider_id()) or ""):
            raise ValueError("The active provider cannot be deleted.")

        providers = [item for item in payload.get("providers", []) if isinstance(item, dict)]
        remaining = [item for item in providers if str(item.get("id", "")).strip() != provider_id]
        if len(remaining) == len(providers):
            raise FileNotFoundError(provider_id)

        payload["providers"] = remaining
        payload["message"] = f"Provider registry removed: {provider_id}."
        self._save(payload, backup_reason=f"Before removing provider: {provider_id}")
        return self.snapshot()

    def audit(
        self,
        *,
        model_attempts: list[ModelAttemptTelemetryEntry] | None = None,
        route_health: list[ModelRouteHealthInfo] | None = None,
    ) -> ModelRegistryAuditResponse:
        registry = self.snapshot()
        providers = registry.providers
        roles = registry.roles
        enabled_providers = [provider for provider in providers if provider.enabled]
        configured_providers = [provider for provider in enabled_providers if provider.configured]
        issues: list[ModelRegistryAuditIssue] = []
        route_coverages: list[ModelRegistryRouteCoverage] = []

        for provider in providers:
            if not provider.enabled:
                continue
            if not provider.endpoint.strip():
                issues.append(
                    ModelRegistryAuditIssue(
                        severity="warning",
                        category="provider_endpoint",
                        provider_id=provider.id,
                        message=f"{provider.label or provider.id} is enabled without an endpoint.",
                        recommendation="Add a local or cloud endpoint, or disable the provider until it is ready.",
                    )
                )
            if provider.configured and not provider.model_name.strip() and not provider.model_aliases:
                issues.append(
                    ModelRegistryAuditIssue(
                        severity="warning",
                        category="provider_model",
                        provider_id=provider.id,
                        message=f"{provider.label or provider.id} is configured without a model name or aliases.",
                        recommendation="Set the model name that should be used for routing.",
                    )
                )
            if not provider.local:
                if not provider.secret_env.strip():
                    issues.append(
                        ModelRegistryAuditIssue(
                            severity="warning",
                            category="provider_secret",
                            provider_id=provider.id,
                            message=f"{provider.label or provider.id} is a configured cloud provider without a secret environment variable.",
                            recommendation="Set secret_env so API keys stay outside the registry file.",
                        )
                    )
                elif not secret_value(provider.secret_env):
                    issues.append(
                        ModelRegistryAuditIssue(
                            severity="warning",
                            category="provider_secret",
                            provider_id=provider.id,
                            message=f"{provider.label or provider.id} expects {provider.secret_env}, but it is not set.",
                            recommendation=f"Set {provider.secret_env} before routing private or paid calls to this provider.",
                        )
                    )

        for role in roles:
            eligible = [provider for provider in enabled_providers if self._provider_matches_role(provider, role)]
            configured = [provider for provider in eligible if provider.configured]
            candidate_ids = [provider.id for provider in configured[:6]]
            primary_provider = self._provider_for_model(role.primary_model, providers)
            primary_configured = bool(primary_provider and primary_provider.enabled and primary_provider.configured)
            fallback_configured_count = sum(
                1
                for model in role.fallback_models
                for provider in [self._provider_for_model(model, providers)]
                if provider is not None and provider.enabled and provider.configured
            )
            recommendations: list[str] = []
            if not eligible:
                status = "missing"
                recommendations.append("Add or enable a provider with this role or its required capabilities.")
                severity = "error" if role.id.strip().lower() in {"chat", "code", "reasoning"} else "warning"
                issues.append(
                    ModelRegistryAuditIssue(
                        severity=severity,
                        category="route_coverage",
                        role=role.id,
                        message=f"{role.label or role.id} has no enabled provider coverage.",
                        recommendation="Add a provider role/capability mapping before routing this role.",
                    )
                )
            elif not configured:
                status = "partial"
                recommendations.append("Configure at least one eligible provider for this route.")
                issues.append(
                    ModelRegistryAuditIssue(
                        severity="warning",
                        category="route_configuration",
                        role=role.id,
                        message=f"{role.label or role.id} has enabled providers but none are configured.",
                        recommendation="Finish provider setup or point the role to a configured provider.",
                    )
                )
            elif not primary_configured:
                status = "covered"
                recommendations.append("Set the primary model to one of the configured candidates.")
                issues.append(
                    ModelRegistryAuditIssue(
                        severity="warning",
                        category="route_primary",
                        role=role.id,
                        message=f"{role.label or role.id} primary model is not backed by a configured provider.",
                        recommendation="Use benchmark winners or select a configured provider as the primary route.",
                    )
                )
            else:
                status = "ready"
            if fallback_configured_count == 0 and len(configured) > 1:
                recommendations.append("Add configured fallback models so one provider failure does not stop this route.")

            route_coverages.append(
                ModelRegistryRouteCoverage(
                    role=role.id,
                    label=role.label,
                    status=status,
                    primary_model=role.primary_model,
                    primary_provider_id=primary_provider.id if primary_provider is not None else "",
                    primary_configured=primary_configured,
                    required_capabilities=role.required_capabilities,
                    eligible_provider_count=len(eligible),
                    configured_provider_count=len(configured),
                    enabled_provider_count=len(eligible),
                    fallback_configured_count=fallback_configured_count,
                    candidate_provider_ids=candidate_ids,
                    recommendations=recommendations,
                )
            )

        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        ready_routes = sum(1 for route in route_coverages if route.status == "ready")
        route_count = max(1, len(route_coverages))
        readiness_score = max(
            0,
            min(100, round((ready_routes / route_count) * 100) - error_count * 20 - min(warning_count, 25)),
        )
        status = "blocked" if error_count else ("ready" if readiness_score >= 80 and warning_count == 0 else "attention")
        recommendations = [
            "Use configured providers as route primaries before trusting autonomous routing.",
            "Keep at least one local fallback for private workspace tasks.",
        ]
        if error_count:
            recommendations.insert(0, "Fix missing route coverage before enabling fully autonomous routing.")
        elif warning_count:
            recommendations.insert(0, "Resolve provider and route warnings to improve fallback reliability.")
        setup_actions = self._audit_setup_actions(
            providers=providers,
            route_coverages=route_coverages,
            issues=issues,
        )
        adapter_health = self.adapter_health(
            providers=providers,
            model_attempts=model_attempts or [],
            route_health=route_health or [],
        )
        tokenizer_diagnostics = self.tokenizer_diagnostics(
            providers=providers,
            model_attempts=model_attempts or [],
        )

        return ModelRegistryAuditResponse(
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            readiness_score=readiness_score,
            status=status,
            provider_count=len(providers),
            enabled_provider_count=len(enabled_providers),
            configured_provider_count=len(configured_providers),
            disabled_provider_count=len(providers) - len(enabled_providers),
            local_provider_count=sum(1 for provider in providers if provider.local),
            cloud_provider_count=sum(1 for provider in providers if not provider.local),
            role_count=len(roles),
            route_coverages=route_coverages,
            issues=issues,
            setup_actions=setup_actions,
            adapter_health=adapter_health,
            tokenizer_diagnostics=tokenizer_diagnostics,
            warnings=[issue.message for issue in issues if issue.severity in {"error", "warning"}],
            recommendations=recommendations,
        )

    def tokenizer_diagnostics(
        self,
        *,
        providers: list[ModelRegistryProvider] | None = None,
        model_attempts: list[ModelAttemptTelemetryEntry] | None = None,
    ) -> list[ModelTokenizerDiagnosticInfo]:
        provider_list = providers or self.snapshot().providers
        attempts_by_provider: dict[str, list[ModelAttemptTelemetryEntry]] = {}
        for entry in model_attempts or []:
            provider_id = entry.attempt.provider_id.strip()
            if provider_id:
                attempts_by_provider.setdefault(provider_id, []).append(entry)

        diagnostics = [
            self._tokenizer_diagnostic_summary(provider, attempts_by_provider.get(provider.id, []))
            for provider in provider_list
        ]
        status_rank = {
            "missing": 0,
            "mixed": 1,
            "heuristic": 2,
            "unobserved": 3,
            "profiled": 4,
            "exact": 5,
        }
        return sorted(
            diagnostics,
            key=lambda item: (
                status_rank.get(item.status, 1),
                item.recent_attempts,
                item.configured,
                item.enabled,
            ),
            reverse=True,
        )

    def adapter_health(
        self,
        *,
        providers: list[ModelRegistryProvider] | None = None,
        model_attempts: list[ModelAttemptTelemetryEntry] | None = None,
        route_health: list[ModelRouteHealthInfo] | None = None,
    ) -> list[ModelAdapterHealthInfo]:
        provider_list = providers or self.snapshot().providers
        attempts_by_provider: dict[str, list[ModelAttemptTelemetryEntry]] = {}
        for entry in model_attempts or []:
            provider_id = entry.attempt.provider_id.strip()
            if provider_id:
                attempts_by_provider.setdefault(provider_id, []).append(entry)

        health_by_provider: dict[str, list[ModelRouteHealthInfo]] = {}
        for signal in route_health or []:
            provider_id = signal.provider_id.strip()
            if provider_id:
                health_by_provider.setdefault(provider_id, []).append(signal)

        summaries = [
            self._adapter_health_summary(
                provider,
                attempts_by_provider.get(provider.id, []),
                health_by_provider.get(provider.id, []),
            )
            for provider in provider_list
        ]
        status_rank = {
            "missing_secret": 0,
            "unsupported_api": 1,
            "missing_model": 2,
            "disabled": 3,
            "unconfigured": 4,
            "cooldown": 5,
            "degraded": 6,
            "ready": 7,
            "unknown": 8,
        }
        return sorted(summaries, key=lambda item: (status_rank.get(item.status, 99), item.provider_label.lower()))

    def apply_benchmark_winners(
        self,
        provider_scores: list[ModelBenchmarkProviderScore],
        *,
        min_score: float = 0.55,
        route_health: list[ModelRouteHealthInfo] | None = None,
    ) -> ModelRegistryResponse:
        payload = self._load_or_create()
        winners = self._benchmark_winners(provider_scores, min_score=min_score)
        if route_health:
            winners = self._health_adjusted_benchmark_winners(winners, route_health)
        if not winners:
            raise ValueError("No benchmark winners are available yet. Run a benchmark first.")

        providers = [item for item in payload.get("providers", []) if isinstance(item, dict)]
        providers_by_id = {str(provider.get("id", "")).strip(): provider for provider in providers}
        role_traits = {
            "chat": (["chat", "fallback"], ["chat", "structured_json"]),
            "code": (["code", "debug", "review", "refactor", "fallback"], ["chat", "code", "structured_json"]),
            "reasoning": (["reasoning", "architecture", "judge", "fallback"], ["chat", "reasoning", "structured_json"]),
        }

        applied_roles: list[str] = []
        for role_id, scores in winners.items():
            winner = scores[0]
            provider = providers_by_id.get(winner.provider_id)
            if provider is not None:
                roles_to_add, capabilities_to_add = role_traits.get(role_id, ([role_id], ["chat"]))
                provider["roles"] = self._dedupe_strings([*self._clean_list(provider.get("roles", [])), *roles_to_add])
                provider["capabilities"] = self._dedupe_strings(
                    [*self._clean_list(provider.get("capabilities", [])), *capabilities_to_add]
                )
                provider["enabled"] = True
                provider["configured"] = bool(provider.get("configured", True))
                if not str(provider.get("model_name", "")).strip() and winner.model_name:
                    provider["model_name"] = winner.model_name
                aliases = self._clean_list(provider.get("model_aliases", []))
                if winner.model_name and winner.model_name not in aliases:
                    aliases.insert(0, winner.model_name)
                provider["model_aliases"] = aliases
                note = str(provider.get("notes", "") or "").strip()
                health_signal = self._route_health_signal_for_score(winner, role_id, self._route_health_lookup(route_health or []))
                if health_signal is not None and health_signal.penalty > 0:
                    benchmark_note = (
                        f"Benchmark promoted for {role_id} routing at {winner.overall_score:.0%} overall "
                        f"after route-health penalty {health_signal.penalty:.0f}."
                    )
                else:
                    benchmark_note = f"Benchmark promoted for {role_id} routing at {winner.overall_score:.0%} overall."
                provider["notes"] = note if benchmark_note in note else f"{note} {benchmark_note}".strip()
            applied_roles.append(role_id)

        roles = [item for item in payload.get("roles", []) if isinstance(item, dict)]
        roles_by_id = {str(role.get("id", "")).strip(): role for role in roles}
        for role_id, scores in winners.items():
            role = roles_by_id.get(role_id)
            if role is None:
                role = {
                    "id": role_id,
                    "label": role_id.title(),
                    "description": f"Benchmark-ranked {role_id} route.",
                    "required_capabilities": ["chat"],
                    "privacy_mode": "local-first",
                    "cost_tier": "low",
                }
                roles.append(role)
                roles_by_id[role_id] = role
            primary = scores[0].model_name or scores[0].provider_id
            fallback_models = self._dedupe_strings(
                [primary, *self._clean_list(role.get("fallback_models", [])), *[score.model_name for score in scores[1:4] if score.model_name]]
            )
            role["primary_model"] = primary
            role["fallback_models"] = fallback_models
            role["status"] = "active"

        payload["providers"] = providers
        payload["roles"] = roles
        payload["router_enabled"] = True
        payload["fallback_supported"] = True
        if route_health:
            payload["message"] = (
                f"Applied health-aware benchmark winners to {', '.join(applied_roles)} routing role(s)."
            )
        else:
            payload["message"] = f"Applied benchmark winners to {', '.join(applied_roles)} routing role(s)."
        self._save(payload, backup_reason=f"Before applying benchmark winners to {', '.join(applied_roles)}")
        return self.snapshot()

    def apply_policy_diff(
        self,
        diff: RoutePolicyDiffResponse,
        *,
        min_confidence: float = 0.55,
        allow_high_risk: bool = False,
    ) -> ModelRegistryResponse:
        payload = self._load_or_create()
        providers = [item for item in payload.get("providers", []) if isinstance(item, dict)]
        roles = [item for item in payload.get("roles", []) if isinstance(item, dict)]
        roles_by_id = {str(role.get("id", "") or "").strip(): role for role in roles}
        min_confidence = max(0.0, min(1.0, min_confidence))

        applied_provider_ids: list[str] = []
        applied_roles: list[str] = []
        skipped: list[str] = []

        for proposal in diff.provider_proposals:
            if not self._policy_proposal_allowed(proposal, min_confidence=min_confidence, allow_high_risk=allow_high_risk):
                continue
            provider = self._provider_for_policy_proposal(proposal, providers)
            if provider is None:
                skipped.append(proposal.provider_id or proposal.provider_label or proposal.model or "unknown provider")
                continue
            if proposal.action == "promote":
                provider["enabled"] = True
                provider["health"] = "promoted"
                self._append_policy_note(
                    provider,
                    f"Policy promoted after {proposal.attempts} attempt(s), {proposal.success_rate:.0%} success, confidence {proposal.confidence:.0%}.",
                )
                applied_provider_ids.append(str(provider.get("id", "") or proposal.provider_id or proposal.model))
            elif proposal.action == "deprioritize":
                provider["health"] = "deprioritized"
                self._append_policy_note(
                    provider,
                    f"Policy flagged for deprioritization after {proposal.attempts} attempt(s), {proposal.success_rate:.0%} success, confidence {proposal.confidence:.0%}.",
                )
                applied_provider_ids.append(str(provider.get("id", "") or proposal.provider_id or proposal.model))

        for proposal in diff.role_proposals:
            if not self._policy_role_allowed(proposal, min_confidence=min_confidence, allow_high_risk=allow_high_risk):
                continue
            provider = self._provider_for_policy_key(proposal.proposed_primary_provider, providers)
            if provider is None and proposal.candidate_provider_ids:
                provider = self._provider_for_policy_key(proposal.candidate_provider_ids[0], providers)
            if provider is None:
                skipped.append(proposal.role or "unknown role")
                continue

            role_id = proposal.role.strip() or "chat"
            role = roles_by_id.get(role_id)
            if role is None:
                role = {
                    "id": role_id,
                    "label": role_id.title(),
                    "description": f"Telemetry-managed {role_id} route.",
                    "primary_model": "",
                    "fallback_models": [],
                    "required_capabilities": ["chat" if role_id == "fallback" else role_id],
                    "privacy_mode": "local-first",
                    "cost_tier": "unknown",
                    "status": "active",
                }
                roles.append(role)
                roles_by_id[role_id] = role

            primary_model = self._provider_route_model(provider)
            if not primary_model:
                skipped.append(role_id)
                continue

            fallback_models = self._clean_list(role.get("fallback_models", []))
            candidate_models = [
                self._provider_route_model(candidate)
                for key in proposal.candidate_provider_ids
                for candidate in [self._provider_for_policy_key(key, providers)]
                if candidate is not None and self._provider_route_model(candidate)
            ]
            if proposal.action == "switch_primary":
                previous_primary = str(role.get("primary_model", "") or "").strip()
                role["primary_model"] = primary_model
                fallback_models = self._dedupe_strings(
                    [primary_model, previous_primary, *fallback_models, *candidate_models]
                )
            elif proposal.action in {"strengthen_fallback", "rebalance"}:
                if not str(role.get("primary_model", "") or "").strip():
                    role["primary_model"] = primary_model
                fallback_models = self._dedupe_strings(
                    [*fallback_models, primary_model, *candidate_models]
                )
            else:
                continue

            role["fallback_models"] = fallback_models
            role["status"] = "active"
            self._apply_role_traits_to_provider(provider, role_id)
            applied_roles.append(role_id)

        payload["providers"] = providers
        payload["roles"] = roles
        if applied_roles or applied_provider_ids:
            payload["router_enabled"] = True
            payload["fallback_supported"] = True
            parts: list[str] = []
            if applied_roles:
                parts.append(f"{len(self._dedupe_strings(applied_roles))} role update(s)")
            if applied_provider_ids:
                parts.append(f"{len(self._dedupe_strings(applied_provider_ids))} provider policy marker(s)")
            payload["message"] = "Applied safe route policy diff: " + ", ".join(parts) + "."
            self._save(payload, backup_reason="Before applying telemetry route policy diff")
        else:
            payload["message"] = (
                "No safe route policy diff changes were applied."
                if not skipped
                else "No safe route policy diff changes were applied; unresolved proposal(s): " + ", ".join(skipped[:4]) + "."
            )
            self._save(payload)
        return self.snapshot()

    def checkpoints(self, limit: int = 20) -> ModelRegistryCheckpointListResponse:
        limit = max(1, min(100, int(limit or 20)))
        items: list[ModelRegistryCheckpointInfo] = []
        current_registry = self._load_for_preview()
        if self.checkpoint_dir.exists():
            for path in sorted(self.checkpoint_dir.glob("*.json"), reverse=True):
                info = self._checkpoint_info(path, current_registry=current_registry)
                if info is not None:
                    items.append(info)
                if len(items) >= limit:
                    break
        return ModelRegistryCheckpointListResponse(checkpoints=items)

    def create_checkpoint(self, reason: str = "") -> ModelRegistryCheckpointInfo:
        self._load_or_create()
        reason = reason.strip() or "Manual model registry checkpoint."
        checkpoint = self._write_checkpoint(reason)
        if checkpoint is None:
            raise ValueError("Unable to create model registry checkpoint.")
        return checkpoint

    def restore_checkpoint(self, checkpoint_id: str) -> ModelRegistryResponse:
        checkpoint_id, payload = self._load_checkpoint_payload(checkpoint_id)
        registry = self._merge_defaults(payload["registry"])
        registry["message"] = f"Restored model registry checkpoint {checkpoint_id}."
        self._save(registry, backup_reason=f"Before restoring checkpoint: {checkpoint_id}")
        return self.snapshot()

    def checkpoint_diff(self, checkpoint_id: str) -> ModelRegistryCheckpointDiffResponse:
        _checkpoint_id, payload = self._load_checkpoint_payload(checkpoint_id)
        checkpoint_registry = self._merge_defaults(payload["registry"])
        current_registry = self._load_for_preview()
        checkpoint_info = self._checkpoint_info_for_payload(payload, current_registry=current_registry)
        if checkpoint_info is None:
            raise ValueError("Model registry checkpoint is malformed.")

        provider_diffs = self._restore_entity_diffs(
            [item for item in checkpoint_registry.get("providers", []) if isinstance(item, dict)],
            [item for item in current_registry.get("providers", []) if isinstance(item, dict)],
            key_name="id",
            label_keys=("label", "model_name"),
            summary_builder=self._provider_restore_summary,
        )
        role_diffs = self._restore_entity_diffs(
            [item for item in checkpoint_registry.get("roles", []) if isinstance(item, dict)],
            [item for item in current_registry.get("roles", []) if isinstance(item, dict)],
            key_name="id",
            label_keys=("label", "primary_model"),
            summary_builder=self._role_restore_summary,
        )
        setting_diffs: list[ModelRegistryCheckpointSettingDiff] = []
        for key in ("active_provider_id", "router_enabled", "fallback_supported"):
            current_value = self._checkpoint_value_summary(current_registry.get(key))
            checkpoint_value = self._checkpoint_value_summary(checkpoint_registry.get(key))
            if current_value != checkpoint_value:
                setting_diffs.append(
                    ModelRegistryCheckpointSettingDiff(
                        key=key,
                        current_value=current_value,
                        checkpoint_value=checkpoint_value,
                    )
                )

        recommendations = [
            "Review provider, role, and setting diffs before restoring this checkpoint."
        ]
        if checkpoint_info.restore_total_change_count == 0:
            recommendations = ["This checkpoint matches the current model registry; restore is not needed."]
        return ModelRegistryCheckpointDiffResponse(
            checkpoint=checkpoint_info,
            provider_diffs=provider_diffs,
            role_diffs=role_diffs,
            setting_diffs=setting_diffs,
            recommendations=recommendations,
        )

    def preview_benchmark_winners(
        self,
        provider_scores: list[ModelBenchmarkProviderScore],
        *,
        min_score: float = 0.55,
        route_health: list[ModelRouteHealthInfo] | None = None,
    ) -> ModelRegistryBenchmarkPreviewResponse:
        payload = self._load_for_preview()
        winners = self._benchmark_winners(provider_scores, min_score=min_score)
        if route_health:
            winners = self._health_adjusted_benchmark_winners(winners, route_health)
        if not winners:
            return ModelRegistryBenchmarkPreviewResponse(
                applicable=False,
                message="No benchmark winners are available yet. Run a benchmark first.",
                warnings=[],
                recommendations=[
                    "Run a benchmark sweep for chat, code, and reasoning before applying route winners."
                ],
            )

        role_diffs = self._benchmark_role_diffs(payload, winners, route_health or [])
        change_count = sum(1 for diff in role_diffs if diff.action != "keep")
        cooled_down = [diff for diff in role_diffs if diff.health_cooldown]
        warnings = [
            f"{diff.role} would use {diff.winner_model or diff.winner_provider_id}, but that route is still in cooldown."
            for diff in cooled_down
        ]
        recommendations = [
            "Review the proposed primary and fallback model changes, then apply healthy winners when the routing looks right."
        ]
        if change_count == 0:
            recommendations = ["Current registry routing already matches the health-aware benchmark winners."]

        prefix = "Previewed health-aware benchmark winners" if route_health else "Previewed benchmark winners"
        return ModelRegistryBenchmarkPreviewResponse(
            applicable=True,
            message=f"{prefix} for {len(role_diffs)} routing role(s); {change_count} role change(s) would be applied.",
            role_diffs=role_diffs,
            warnings=warnings,
            recommendations=recommendations,
        )

    def _load_or_create(self) -> dict[str, Any]:
        if self.registry_path.exists():
            try:
                payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    merged = self._merge_defaults(payload)
                    if merged != payload:
                        self._save(merged)
                    return merged
            except json.JSONDecodeError:
                pass

        payload = self._default_registry()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    def _load_for_preview(self) -> dict[str, Any]:
        if self.registry_path.exists():
            try:
                payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return self._merge_defaults(payload)
            except json.JSONDecodeError:
                pass
        return self._default_registry()

    def _save(self, payload: dict[str, Any], *, backup_reason: str = "") -> None:
        if backup_reason:
            self._write_checkpoint(backup_reason)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _write_checkpoint(self, reason: str) -> ModelRegistryCheckpointInfo | None:
        if not self.registry_path.exists():
            return None
        try:
            registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(registry, dict):
            return None
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        checkpoint_id = now.strftime("%Y%m%dT%H%M%S%fZ")
        checkpoint = {
            "id": checkpoint_id,
            "created_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "reason": reason,
            "registry": registry,
        }
        (self.checkpoint_dir / f"{checkpoint_id}.json").write_text(
            json.dumps(checkpoint, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return self._checkpoint_info(self.checkpoint_dir / f"{checkpoint_id}.json", current_registry=registry)

    def _load_checkpoint_payload(self, checkpoint_id: str) -> tuple[str, dict[str, Any]]:
        checkpoint_id = checkpoint_id.strip()
        if not checkpoint_id or any(char in checkpoint_id for char in "\\/.:"):
            raise ValueError("Invalid model registry checkpoint id.")
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            raise FileNotFoundError(checkpoint_id)
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("registry"), dict):
            raise ValueError("Model registry checkpoint is malformed.")
        return checkpoint_id, payload

    def _checkpoint_info(
        self,
        path: Path,
        *,
        current_registry: dict[str, Any] | None = None,
    ) -> ModelRegistryCheckpointInfo | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        registry = payload.get("registry")
        if not isinstance(registry, dict):
            return None
        return self._checkpoint_info_for_payload(payload, current_registry=current_registry)

    def _checkpoint_info_for_payload(
        self,
        payload: dict[str, Any],
        *,
        current_registry: dict[str, Any] | None = None,
    ) -> ModelRegistryCheckpointInfo | None:
        registry = payload.get("registry")
        if not isinstance(registry, dict):
            return None
        providers = [item for item in registry.get("providers", []) if isinstance(item, dict)]
        roles = [item for item in registry.get("roles", []) if isinstance(item, dict)]
        current_registry = current_registry if isinstance(current_registry, dict) else self._load_for_preview()
        current_providers = [item for item in current_registry.get("providers", []) if isinstance(item, dict)]
        current_roles = [item for item in current_registry.get("roles", []) if isinstance(item, dict)]
        provider_add, provider_remove, provider_change = self._restore_entity_delta_counts(
            providers,
            current_providers,
            "id",
        )
        role_add, role_remove, role_change = self._restore_entity_delta_counts(
            roles,
            current_roles,
            "id",
        )
        settings_change_count = sum(
            1
            for key in ("active_provider_id", "router_enabled", "fallback_supported")
            if registry.get(key) != current_registry.get(key)
        )
        total_change_count = (
            provider_add
            + provider_remove
            + provider_change
            + role_add
            + role_remove
            + role_change
            + settings_change_count
        )
        return ModelRegistryCheckpointInfo(
            id=str(payload.get("id", "") or ""),
            created_at=str(payload.get("created_at", "") or ""),
            reason=str(payload.get("reason", "") or ""),
            provider_count=len(providers),
            role_count=len(roles),
            router_enabled=bool(registry.get("router_enabled", False)),
            active_provider_id=str(registry.get("active_provider_id", "") or ""),
            message=str(registry.get("message", "") or ""),
            restore_provider_add_count=provider_add,
            restore_provider_remove_count=provider_remove,
            restore_provider_change_count=provider_change,
            restore_role_add_count=role_add,
            restore_role_remove_count=role_remove,
            restore_role_change_count=role_change,
            restore_settings_change_count=settings_change_count,
            restore_total_change_count=total_change_count,
            restore_summary=self._restore_summary(
                provider_add=provider_add,
                provider_remove=provider_remove,
                provider_change=provider_change,
                role_add=role_add,
                role_remove=role_remove,
                role_change=role_change,
                settings_change=settings_change_count,
            ),
        )

    def _restore_entity_diffs(
        self,
        checkpoint_items: list[dict[str, Any]],
        current_items: list[dict[str, Any]],
        *,
        key_name: str,
        label_keys: tuple[str, ...],
        summary_builder: Any,
    ) -> list[ModelRegistryCheckpointEntityDiff]:
        checkpoint_by_id = {
            str(item.get(key_name, "") or "").strip(): item
            for item in checkpoint_items
            if str(item.get(key_name, "") or "").strip()
        }
        current_by_id = {
            str(item.get(key_name, "") or "").strip(): item
            for item in current_items
            if str(item.get(key_name, "") or "").strip()
        }
        diffs: list[ModelRegistryCheckpointEntityDiff] = []
        for item_id in sorted(set(checkpoint_by_id) | set(current_by_id)):
            checkpoint_item = checkpoint_by_id.get(item_id)
            current_item = current_by_id.get(item_id)
            if checkpoint_item is None:
                action = "remove_on_restore"
            elif current_item is None:
                action = "add_on_restore"
            elif self._canonical_json(checkpoint_item) != self._canonical_json(current_item):
                action = "change_on_restore"
            else:
                continue

            label = self._entity_label(checkpoint_item or current_item or {}, label_keys)
            diffs.append(
                ModelRegistryCheckpointEntityDiff(
                    id=item_id,
                    label=label or item_id,
                    action=action,
                    current_summary=summary_builder(current_item) if current_item is not None else "Not present",
                    checkpoint_summary=summary_builder(checkpoint_item) if checkpoint_item is not None else "Not present",
                )
            )
        return diffs

    def _entity_label(self, item: dict[str, Any], label_keys: tuple[str, ...]) -> str:
        for key in label_keys:
            text = str(item.get(key, "") or "").strip()
            if text:
                return text
        return str(item.get("id", "") or "").strip()

    def _provider_restore_summary(self, item: dict[str, Any] | None) -> str:
        if item is None:
            return "Not present"
        label = str(item.get("label", "") or item.get("id", "") or "").strip()
        model = str(item.get("model_name", "") or "").strip()
        api = str(item.get("api", "") or "").strip()
        enabled = "enabled" if bool(item.get("enabled", False)) else "disabled"
        configured = "configured" if bool(item.get("configured", False)) else "not configured"
        roles = ", ".join(self._clean_list(item.get("roles", []))) or "no roles"
        return f"{label} / {model or 'no model'} / {api or 'unknown api'} / {enabled}, {configured} / roles: {roles}"

    def _role_restore_summary(self, item: dict[str, Any] | None) -> str:
        if item is None:
            return "Not present"
        label = str(item.get("label", "") or item.get("id", "") or "").strip()
        primary = str(item.get("primary_model", "") or "").strip()
        status = str(item.get("status", "") or "unknown").strip()
        fallbacks = ", ".join(self._clean_list(item.get("fallback_models", []))) or "no fallbacks"
        privacy = str(item.get("privacy_mode", "") or "unknown").strip()
        return f"{label} / primary: {primary or 'none'} / {status} / {privacy} / fallbacks: {fallbacks}"

    def _checkpoint_value_summary(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return ""
        return str(value)

    def _restore_entity_delta_counts(
        self,
        checkpoint_items: list[dict[str, Any]],
        current_items: list[dict[str, Any]],
        key_name: str,
    ) -> tuple[int, int, int]:
        checkpoint_by_id = {
            str(item.get(key_name, "") or "").strip(): item
            for item in checkpoint_items
            if str(item.get(key_name, "") or "").strip()
        }
        current_by_id = {
            str(item.get(key_name, "") or "").strip(): item
            for item in current_items
            if str(item.get(key_name, "") or "").strip()
        }
        checkpoint_ids = set(checkpoint_by_id)
        current_ids = set(current_by_id)
        add_count = len(checkpoint_ids - current_ids)
        remove_count = len(current_ids - checkpoint_ids)
        change_count = 0
        for item_id in checkpoint_ids & current_ids:
            if self._canonical_json(checkpoint_by_id[item_id]) != self._canonical_json(current_by_id[item_id]):
                change_count += 1
        return add_count, remove_count, change_count

    def _canonical_json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _restore_summary(
        self,
        *,
        provider_add: int,
        provider_remove: int,
        provider_change: int,
        role_add: int,
        role_remove: int,
        role_change: int,
        settings_change: int,
    ) -> str:
        total = provider_add + provider_remove + provider_change + role_add + role_remove + role_change + settings_change
        if total <= 0:
            return "Matches current registry."
        parts: list[str] = []
        if provider_add or provider_remove or provider_change:
            parts.append(
                f"providers +{provider_add}/-{provider_remove}/~{provider_change}"
            )
        if role_add or role_remove or role_change:
            parts.append(
                f"roles +{role_add}/-{role_remove}/~{role_change}"
            )
        if settings_change:
            parts.append(f"settings ~{settings_change}")
        return "Restore would change " + ", ".join(parts) + "."

    def _clean_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            values = value.split(",")
        elif isinstance(value, list):
            values = value
        else:
            return []
        cleaned: list[str] = []
        for item in values:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _provider_matches_role(self, provider: ModelRegistryProvider, role: ModelRegistryRole) -> bool:
        provider_roles = {item.strip().lower() for item in provider.roles if item.strip()}
        provider_capabilities = {item.strip().lower() for item in provider.capabilities if item.strip()}
        role_id = role.id.strip().lower()
        required = {item.strip().lower() for item in role.required_capabilities if item.strip()}
        if role_id and role_id in provider_roles:
            return True
        if required and required.issubset(provider_capabilities):
            return True
        if role_id and role_id in provider_capabilities:
            return True
        if role_id == "fallback" and "chat" in provider_capabilities:
            return True
        return False

    def _provider_for_model(
        self,
        model_name: str,
        providers: list[ModelRegistryProvider],
    ) -> ModelRegistryProvider | None:
        model_key = model_name.strip().lower()
        if not model_key:
            return None
        for provider in providers:
            names = [provider.model_name, *provider.model_aliases, provider.id]
            if any(item.strip().lower() == model_key for item in names if item.strip()):
                return provider
        return None

    def _policy_proposal_allowed(
        self,
        proposal: RoutePolicyProviderProposal,
        *,
        min_confidence: float,
        allow_high_risk: bool,
    ) -> bool:
        if proposal.action not in {"promote", "deprioritize"}:
            return False
        if proposal.confidence < min_confidence:
            return False
        if proposal.risk_level == "high" and not allow_high_risk:
            return False
        return True

    def _policy_role_allowed(
        self,
        proposal: RoutePolicyRoleProposal,
        *,
        min_confidence: float,
        allow_high_risk: bool,
    ) -> bool:
        if proposal.action not in {"switch_primary", "strengthen_fallback", "rebalance"}:
            return False
        if proposal.confidence < min_confidence:
            return False
        if proposal.risks and not allow_high_risk:
            severe_markers = ("only one provider", "insufficient", "below")
            if any(any(marker in risk.lower() for marker in severe_markers) for risk in proposal.risks):
                return False
        return True

    def _provider_for_policy_proposal(
        self,
        proposal: RoutePolicyProviderProposal,
        providers: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for key in (proposal.provider_id, proposal.model, proposal.provider_label, proposal.provider_api):
            provider = self._provider_for_policy_key(key, providers)
            if provider is not None:
                return provider
        return None

    def _provider_for_policy_key(self, key: str, providers: list[dict[str, Any]]) -> dict[str, Any] | None:
        key_normalized = str(key or "").strip().lower()
        if not key_normalized:
            return None
        exact_matches: list[dict[str, Any]] = []
        for provider in providers:
            candidates = [
                str(provider.get("id", "") or ""),
                str(provider.get("label", "") or ""),
                str(provider.get("model_name", "") or ""),
                *self._clean_list(provider.get("model_aliases", [])),
            ]
            if any(candidate.strip().lower() == key_normalized for candidate in candidates if candidate.strip()):
                exact_matches.append(provider)
        if len(exact_matches) == 1:
            return exact_matches[0]

        api_matches = [
            provider
            for provider in providers
            if str(provider.get("api", "") or "").strip().lower() == key_normalized
        ]
        return api_matches[0] if len(api_matches) == 1 else None

    def _provider_route_model(self, provider: dict[str, Any]) -> str:
        model_name = str(provider.get("model_name", "") or "").strip()
        if model_name:
            return model_name
        aliases = self._clean_list(provider.get("model_aliases", []))
        if aliases:
            return aliases[0]
        return str(provider.get("id", "") or "").strip()

    def _apply_role_traits_to_provider(self, provider: dict[str, Any], role_id: str) -> None:
        role_id = role_id.strip().lower()
        role_traits = {
            "chat": (["chat", "fallback"], ["chat", "structured_json"]),
            "code": (["code", "debug", "review", "refactor", "fallback"], ["chat", "code", "structured_json"]),
            "reasoning": (["reasoning", "architecture", "judge", "fallback"], ["chat", "reasoning", "structured_json"]),
            "research": (["research", "search", "fallback"], ["chat", "research", "search"]),
            "judge": (["judge", "fallback"], ["chat", "judge"]),
        }
        roles_to_add, capabilities_to_add = role_traits.get(role_id, ([role_id], ["chat"]))
        provider["roles"] = self._dedupe_strings([*self._clean_list(provider.get("roles", [])), *roles_to_add])
        provider["capabilities"] = self._dedupe_strings(
            [*self._clean_list(provider.get("capabilities", [])), *capabilities_to_add]
        )
        provider["enabled"] = True
        provider["configured"] = bool(provider.get("configured", True))
        provider["health"] = str(provider.get("health", "") or "policy-applied")
        self._append_policy_note(provider, f"Telemetry policy applied for {role_id} routing.")

    def _append_policy_note(self, provider: dict[str, Any], note: str) -> None:
        current = str(provider.get("notes", "") or "").strip()
        if note and note not in current:
            provider["notes"] = f"{current} {note}".strip()

    def _adapter_health_summary(
        self,
        provider: ModelRegistryProvider,
        attempts: list[ModelAttemptTelemetryEntry],
        route_health: list[ModelRouteHealthInfo],
    ) -> ModelAdapterHealthInfo:
        preflight = self._provider_preflight_issue(provider)
        recent_attempts = len(attempts)
        recent_successes = sum(1 for entry in attempts if entry.attempt.status == "succeeded")
        recent_failures = sum(1 for entry in attempts if entry.attempt.status == "failed")
        recent_skips = sum(1 for entry in attempts if entry.attempt.status == "skipped")
        preflight_skips = sum(
            1 for entry in attempts if entry.attempt.status == "skipped" and bool(entry.attempt.metadata.get("preflight"))
        )
        cooldown = any(signal.cooldown for signal in route_health)
        latest_signal = max(route_health, key=lambda item: item.latest_at or "", default=None)
        latest_attempt = max(attempts, key=lambda item: item.created_at or "", default=None)
        latest_error = ""
        latest_at = ""
        if latest_signal is not None and latest_signal.latest_error:
            latest_error = latest_signal.latest_error
            latest_at = latest_signal.latest_at
        elif latest_attempt is not None and latest_attempt.attempt.error:
            latest_error = latest_attempt.attempt.error
            latest_at = latest_attempt.created_at

        secret_env = provider.secret_env.strip() or secret_env_name(provider.api, provider.endpoint)
        if preflight is not None and not (preflight["code"] == "unconfigured" and cooldown):
            status = preflight["code"]
            message = preflight["message"]
            recommendation = self._adapter_health_recommendation(status, provider, latest_error)
            secret_env = preflight.get("secret_env", secret_env)
        elif cooldown:
            status = "cooldown"
            message = f"{provider.label or provider.id} is temporarily cooled down by recent route failures."
            recommendation = "Use a fallback provider until recent failures are resolved or enough successful attempts recover the route."
        elif recent_failures > recent_successes and recent_failures >= 2:
            status = "degraded"
            message = f"{provider.label or provider.id} has more recent failures than successes."
            recommendation = latest_error or "Inspect provider logs, endpoint availability, model name, rate limits, and credentials."
        else:
            status = "ready"
            message = f"{provider.label or provider.id} is configured for routed execution."
            recommendation = "Keep monitoring route telemetry and benchmark results."

        model = provider.model_name.strip() or (provider.model_aliases[0].strip() if provider.model_aliases else "")
        return ModelAdapterHealthInfo(
            provider_id=provider.id,
            provider_label=provider.label or provider.id,
            api=provider.api,
            endpoint=provider.endpoint,
            model=model,
            local=provider.local,
            enabled=provider.enabled,
            configured=provider.configured,
            status=status,
            error_code=status if status not in {"ready", "cooldown", "degraded"} else "",
            message=message,
            secret_env=secret_env,
            secret_present=bool(secret_env and secret_value(secret_env)),
            capabilities=provider.capabilities,
            roles=provider.roles,
            recent_attempts=recent_attempts,
            recent_successes=recent_successes,
            recent_failures=recent_failures,
            recent_skips=recent_skips,
            preflight_skips=preflight_skips,
            cooldown=cooldown,
            latest_error=latest_error,
            latest_at=latest_at,
            recommendation=recommendation,
        )

    def _provider_preflight_issue(self, provider: ModelRegistryProvider) -> dict[str, str] | None:
        label = provider.label or provider.id
        if not provider.enabled:
            return {"code": "disabled", "message": f"{label} is disabled in the provider registry."}
        if not provider.model_name.strip() and not any(alias.strip() for alias in provider.model_aliases):
            return {"code": "missing_model", "message": f"{label} does not have a model name or alias configured."}
        if api_family(provider.api) == "unsupported":
            return {"code": "unsupported_api", "message": f"{label} uses unsupported provider API '{provider.api}'."}
        if not provider.local:
            env_name = provider.secret_env.strip() or secret_env_name(provider.api, provider.endpoint)
            if env_name and not secret_value(env_name):
                return {
                    "code": "missing_secret",
                    "message": f"{label} requires {env_name} before it can execute.",
                    "secret_env": env_name,
                }
        if not provider.configured:
            return {"code": "unconfigured", "message": f"{label} is enabled but not fully configured."}
        return None

    def _adapter_health_recommendation(
        self,
        status: str,
        provider: ModelRegistryProvider,
        latest_error: str,
    ) -> str:
        if status == "disabled":
            return "Enable this provider only when it should be eligible for routing."
        if status == "unconfigured":
            return "Set endpoint, model name, capabilities, and route roles before using this provider."
        if status == "missing_model":
            return "Set a concrete model name or alias for this provider."
        if status == "unsupported_api":
            return "Switch the provider API to a supported adapter family or add a new adapter."
        if status == "missing_secret":
            env_name = provider.secret_env.strip() or secret_env_name(provider.api, provider.endpoint)
            return f"Set {env_name} in the backend environment before routing to this provider."
        return latest_error or "Inspect provider settings and recent model-attempt telemetry."

    def _tokenizer_diagnostic_summary(
        self,
        provider: ModelRegistryProvider,
        attempts: list[ModelAttemptTelemetryEntry],
    ) -> ModelTokenizerDiagnosticInfo:
        estimator_sources: set[str] = set()
        exact_attempts = 0
        profiled_attempts = 0
        heuristic_attempts = 0
        missing_attempts = 0
        context_utilizations: list[float] = []
        context_window = provider.context_window
        input_token_errors: list[float] = []
        output_token_errors: list[float] = []
        calibrated_attempts = 0
        reported_token_sources: set[str] = set()

        for entry in attempts:
            metadata = entry.attempt.metadata if isinstance(entry.attempt.metadata, dict) else {}
            source = self._token_estimator_label(metadata)
            if source:
                estimator_sources.add(source)
            category = self._token_estimator_category(source)
            if category == "exact":
                exact_attempts += 1
            elif category == "profiled":
                profiled_attempts += 1
            elif category == "heuristic":
                heuristic_attempts += 1
            else:
                missing_attempts += 1

            if context_window is None:
                window = self._optional_int(metadata.get("context_window"))
                if window is not None:
                    context_window = window
            utilization = self._optional_float(metadata.get("context_window_utilization"))
            if utilization is not None:
                context_utilizations.append(utilization)

            calibration = self._token_calibration_errors(entry)
            if calibration["calibrated"]:
                calibrated_attempts += 1
            if calibration["reported_source"]:
                reported_token_sources.add(str(calibration["reported_source"]))
            if calibration["input_error"] is not None:
                input_token_errors.append(float(calibration["input_error"]))
            if calibration["output_error"] is not None:
                output_token_errors.append(float(calibration["output_error"]))

        recent_attempts = len(attempts)
        if recent_attempts == 0:
            status = "unobserved"
        elif missing_attempts == recent_attempts:
            status = "missing"
        elif exact_attempts > 0 and (profiled_attempts + heuristic_attempts + missing_attempts) == 0:
            status = "exact"
        elif profiled_attempts > 0 and heuristic_attempts == 0 and missing_attempts == 0:
            status = "profiled"
        elif heuristic_attempts > 0 and exact_attempts == 0 and profiled_attempts == 0 and missing_attempts == 0:
            status = "heuristic"
        else:
            status = "mixed"

        primary_source = sorted(estimator_sources)[0] if estimator_sources else ""
        average_input_error = self._average_float(input_token_errors)
        average_output_error = self._average_float(output_token_errors)
        worst_input_error = max(input_token_errors) if input_token_errors else None
        worst_output_error = max(output_token_errors) if output_token_errors else None
        calibration_status = self._token_calibration_status(
            calibrated_attempts=calibrated_attempts,
            average_input_error=average_input_error,
            average_output_error=average_output_error,
            worst_input_error=worst_input_error,
            worst_output_error=worst_output_error,
        )
        return ModelTokenizerDiagnosticInfo(
            provider_id=provider.id,
            provider_label=provider.label or provider.id,
            api=provider.api,
            model=provider.model_name.strip() or (provider.model_aliases[0].strip() if provider.model_aliases else ""),
            local=provider.local,
            enabled=provider.enabled,
            configured=provider.configured,
            context_window=context_window,
            status=status,
            recent_attempts=recent_attempts,
            exact_attempts=exact_attempts,
            profiled_attempts=profiled_attempts,
            heuristic_attempts=heuristic_attempts,
            missing_attempts=missing_attempts,
            estimator_sources=sorted(estimator_sources),
            primary_estimator_source=primary_source,
            average_context_utilization=(
                sum(context_utilizations) / len(context_utilizations) if context_utilizations else None
            ),
            calibrated_attempts=calibrated_attempts,
            average_input_token_error=average_input_error,
            worst_input_token_error=worst_input_error,
            average_output_token_error=average_output_error,
            worst_output_token_error=worst_output_error,
            reported_token_sources=sorted(reported_token_sources),
            calibration_status=calibration_status,
            calibration_recommendation=self._token_calibration_recommendation(
                status=calibration_status,
                provider=provider,
                calibrated_attempts=calibrated_attempts,
                average_input_error=average_input_error,
                average_output_error=average_output_error,
                reported_sources=sorted(reported_token_sources),
            ),
            recommendation=self._tokenizer_diagnostic_recommendation(
                status=status,
                provider=provider,
                context_window=context_window,
                primary_source=primary_source,
                recent_attempts=recent_attempts,
            ),
        )

    def _token_estimator_category(self, source: str) -> str:
        lowered = source.strip().lower()
        if not lowered:
            return "missing"
        if "exact" in lowered or "tokenizer" in lowered or "tiktoken" in lowered:
            return "exact"
        if "provider_profile" in lowered or "profile" in lowered:
            return "profiled"
        if "heuristic" in lowered or "char" in lowered or "approx" in lowered:
            return "heuristic"
        return "profiled"

    def _token_estimator_label(self, metadata: dict[str, Any]) -> str:
        if not isinstance(metadata, dict):
            return ""
        family = str(metadata.get("token_estimator_family") or "").strip()
        source = str(metadata.get("token_estimate_source") or "").strip()
        if family and source:
            return f"{family}:{source}"
        return family or source

    def _optional_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _optional_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _first_optional_int(self, metadata: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        if not isinstance(metadata, dict):
            return None
        for key in keys:
            value = self._optional_int(metadata.get(key))
            if value is not None:
                return value
        return None

    def _average_float(self, values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    def _relative_token_error(self, estimated: int | None, reported: int | None) -> float | None:
        if estimated is None or reported is None:
            return None
        if estimated < 0 or reported < 0:
            return None
        return abs(estimated - reported) / max(reported, 1)

    def _token_calibration_errors(self, entry: ModelAttemptTelemetryEntry) -> dict[str, Any]:
        metadata = entry.attempt.metadata if isinstance(entry.attempt.metadata, dict) else {}
        estimated_input = self._first_optional_int(
            metadata,
            (
                "estimated_input_tokens",
                "planned_input_tokens",
                "input_token_estimate",
                "estimated_prompt_tokens",
            ),
        )
        estimated_output = self._first_optional_int(
            metadata,
            (
                "estimated_output_tokens",
                "reserved_response_tokens",
                "planned_output_tokens",
                "output_token_estimate",
                "estimated_completion_tokens",
            ),
        )
        if estimated_input is None:
            estimated_input = self._optional_int(entry.attempt.input_tokens)
        if estimated_output is None:
            estimated_output = self._optional_int(entry.attempt.output_tokens)

        reported_input = self._first_optional_int(
            metadata,
            (
                "reported_input_tokens",
                "actual_input_tokens",
                "provider_input_tokens",
                "prompt_tokens",
            ),
        )
        reported_output = self._first_optional_int(
            metadata,
            (
                "reported_output_tokens",
                "actual_output_tokens",
                "provider_output_tokens",
                "completion_tokens",
            ),
        )
        input_error = self._relative_token_error(estimated_input, reported_input)
        output_error = self._relative_token_error(estimated_output, reported_output)
        return {
            "calibrated": input_error is not None or output_error is not None,
            "input_error": input_error,
            "output_error": output_error,
            "reported_source": str(metadata.get("reported_token_source") or "").strip(),
        }

    def _token_calibration_status(
        self,
        *,
        calibrated_attempts: int,
        average_input_error: float | None,
        average_output_error: float | None,
        worst_input_error: float | None,
        worst_output_error: float | None,
    ) -> str:
        if calibrated_attempts <= 0:
            return "insufficient"
        average_error = max(average_input_error or 0.0, average_output_error or 0.0)
        worst_error = max(worst_input_error or 0.0, worst_output_error or 0.0)
        if average_error <= 0.12 and worst_error <= 0.25:
            return "stable"
        if average_error <= 0.25 and worst_error <= 0.45:
            return "watch"
        return "drift"

    def _token_calibration_recommendation(
        self,
        *,
        status: str,
        provider: ModelRegistryProvider,
        calibrated_attempts: int,
        average_input_error: float | None,
        average_output_error: float | None,
        reported_sources: list[str],
    ) -> str:
        label = provider.label or provider.id
        if status == "insufficient":
            return f"Capture provider-reported token usage for {label} to compare planned estimates against actual requests."
        source = ", ".join(reported_sources[:2]) if reported_sources else "provider usage metadata"
        input_text = f"{average_input_error:.0%}" if average_input_error is not None else "n/a"
        output_text = f"{average_output_error:.0%}" if average_output_error is not None else "n/a"
        if status == "stable":
            return f"{label} token estimates are calibrated from {calibrated_attempts} attempt(s) via {source}; avg error in/out {input_text}/{output_text}."
        if status == "watch":
            return f"{label} has moderate token-estimator drift; keep sampling {source} before changing the route profile."
        return f"{label} token estimates are drifting from reported usage; adjust tokenizer profile or overhead before trusting tight context budgets."

    def _tokenizer_diagnostic_recommendation(
        self,
        *,
        status: str,
        provider: ModelRegistryProvider,
        context_window: int | None,
        primary_source: str,
        recent_attempts: int,
    ) -> str:
        label = provider.label or provider.id
        if status == "unobserved":
            return f"Run a routed task through {label} to collect tokenizer and context-window telemetry."
        if status == "missing":
            return f"Add estimator metadata for {label} so routing can predict prompt size and cost before execution."
        if status == "heuristic":
            return f"Replace character-count heuristics for {label} with a provider profile or exact tokenizer adapter."
        if status == "mixed":
            return f"Normalize tokenizer metadata for {label}; recent attempts used inconsistent estimator sources."
        if status == "exact":
            return f"{label} is using exact tokenizer telemetry across {recent_attempts} recent attempt(s)."
        if context_window is None:
            return f"Set a context window for {label} so budget-pressure warnings can be route-aware."
        return f"{label} is using {primary_source or 'profiled'} token estimates; exact tokenizer adapters can further improve cost and context planning."

    def _audit_setup_actions(
        self,
        *,
        providers: list[ModelRegistryProvider],
        route_coverages: list[ModelRegistryRouteCoverage],
        issues: list[ModelRegistryAuditIssue],
    ) -> list[ModelRegistrySetupAction]:
        actions: list[ModelRegistrySetupAction] = []
        missing_secret_providers: dict[str, list[ModelRegistryProvider]] = {}
        for provider in providers:
            if provider.local or not provider.enabled or not provider.secret_env.strip():
                continue
            if secret_value(provider.secret_env):
                continue
            missing_secret_providers.setdefault(provider.secret_env.strip(), []).append(provider)

        for env_var, env_providers in sorted(missing_secret_providers.items()):
            provider_labels = [provider.label or provider.id for provider in env_providers[:4]]
            roles = {
                role.strip().lower()
                for provider in env_providers
                for role in provider.roles
                if role.strip()
            }
            priority = "high" if roles & {"chat", "code", "reasoning", "research"} else "medium"
            actions.append(
                ModelRegistrySetupAction(
                    id=f"secret:{env_var}",
                    kind="secret",
                    priority=priority,
                    title=f"Set {env_var}",
                    detail=(
                        f"{len(env_providers)} provider(s) need this key: "
                        + ", ".join(provider_labels)
                        + ("." if len(env_providers) <= 4 else ", ...")
                    ),
                    recommendation="Set the key as a user environment variable, then restart the backend.",
                    env_var=env_var,
                    provider_ids=[provider.id for provider in env_providers],
                    command=(
                        f"[Environment]::SetEnvironmentVariable('{env_var}', 'PASTE_KEY_HERE', 'User')"
                    ),
                )
            )

        for route in route_coverages:
            if route.status == "ready":
                continue
            role = route.role.strip().lower()
            if route.status == "missing":
                priority = "critical" if role in {"chat", "code", "reasoning"} else "medium"
                title = f"Add {route.label or route.role} route coverage"
                detail = "No enabled provider currently advertises this role or its required capabilities."
                recommendation = "Stage a matching provider blueprint or add the role/capability to an existing provider."
            elif route.status == "partial":
                priority = "high" if role in {"chat", "code", "reasoning", "research"} else "medium"
                title = f"Configure {route.label or route.role} provider"
                detail = (
                    f"{route.eligible_provider_count} provider(s) can cover this route, "
                    "but none are configured."
                )
                recommendation = "Finish the provider's model/API-key setup or choose a configured local fallback."
            else:
                priority = "medium"
                title = f"Select {route.label or route.role} primary"
                detail = "This route has configured candidates, but its primary model is not backed by one."
                recommendation = "Apply benchmark winners or set the primary model to a configured candidate."
            actions.append(
                ModelRegistrySetupAction(
                    id=f"route:{route.role}",
                    kind="route",
                    priority=priority,
                    title=title,
                    detail=detail,
                    recommendation=recommendation,
                    role=route.role,
                    provider_ids=route.candidate_provider_ids,
                )
            )

        if any(route.role in {"chat", "code", "reasoning"} and route.status == "ready" for route in route_coverages):
            actions.append(
                ModelRegistrySetupAction(
                    id="benchmark:healthy-winners",
                    kind="benchmark",
                    priority="low",
                    title="Refresh benchmark winners",
                    detail="Local core routes have configured providers; benchmark scores keep primaries and fallbacks honest.",
                    recommendation="Run a quick benchmark after adding or removing local models.",
                )
            )

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        severity_by_category = {
            (issue.category, issue.provider_id, issue.role)
            for issue in issues
            if issue.severity == "error"
        }
        actions.sort(
            key=lambda action: (
                priority_order.get(action.priority, 2),
                0 if (action.kind, action.provider_ids[0] if action.provider_ids else "", action.role) in severity_by_category else 1,
                action.kind,
                action.title,
            )
        )
        return actions[:12]

    def _benchmark_winners(
        self,
        provider_scores: list[ModelBenchmarkProviderScore],
        *,
        min_score: float,
    ) -> dict[str, list[ModelBenchmarkProviderScore]]:
        suite_fields = {
            "chat": "chat_score",
            "code": "code_score",
            "reasoning": "reasoning_score",
        }
        winners: dict[str, list[ModelBenchmarkProviderScore]] = {}
        for role_id, field_name in suite_fields.items():
            eligible = [
                score
                for score in provider_scores
                if score.enabled
                and score.configured
                and score.model_name.strip()
                and getattr(score, field_name) is not None
                and float(getattr(score, field_name) or 0.0) >= min_score
            ]
            eligible.sort(
                key=lambda score: (
                    float(getattr(score, field_name) or 0.0),
                    score.overall_score,
                    -(score.avg_latency_ms or 999999),
                    score.run_count,
                ),
                reverse=True,
            )
            if eligible:
                winners[role_id] = eligible
        return winners

    def _benchmark_role_diffs(
        self,
        payload: dict[str, Any],
        winners: dict[str, list[ModelBenchmarkProviderScore]],
        route_health: list[ModelRouteHealthInfo],
    ) -> list[ModelRegistryBenchmarkRoleDiff]:
        roles = [item for item in payload.get("roles", []) if isinstance(item, dict)]
        roles_by_id = {str(role.get("id", "")).strip(): role for role in roles}
        health_lookup = self._route_health_lookup(route_health)
        suite_fields = {
            "chat": "chat_score",
            "code": "code_score",
            "reasoning": "reasoning_score",
        }

        diffs: list[ModelRegistryBenchmarkRoleDiff] = []
        for role_id, scores in winners.items():
            if not scores:
                continue
            winner = scores[0]
            role = roles_by_id.get(role_id)
            current_primary = str(role.get("primary_model", "") or "").strip() if role else ""
            current_fallbacks = self._clean_list(role.get("fallback_models", []) if role else [])
            proposed_primary = winner.model_name or winner.provider_id
            proposed_fallbacks = self._dedupe_strings(
                [
                    proposed_primary,
                    *current_fallbacks,
                    *[score.model_name for score in scores[1:4] if score.model_name],
                ]
            )
            if role is None:
                action = "add_role"
            elif current_primary != proposed_primary:
                action = "switch_primary"
            elif current_fallbacks != proposed_fallbacks:
                action = "update_fallbacks"
            else:
                action = "keep"

            field_name = suite_fields.get(role_id, "overall_score")
            winner_score = float(getattr(winner, field_name) or winner.overall_score or 0.0)
            health_signal = self._route_health_signal_for_score(winner, role_id, health_lookup)
            reasons = [
                f"{winner.provider_label or winner.provider_id} ranked highest for {role_id} at {winner_score:.0%}.",
            ]
            if action == "add_role":
                reasons.append("The registry does not have this benchmarked role yet.")
            elif action == "switch_primary":
                reasons.append(
                    f"Primary model would change from {current_primary or 'none'} to {proposed_primary or 'none'}."
                )
            elif action == "update_fallbacks":
                reasons.append("Fallback ordering would be refreshed from the benchmark ranking.")
            else:
                reasons.append("Current routing already matches the selected benchmark winner.")
            if route_health:
                reasons.append("Route-health penalties and cooldowns were applied before ranking.")
            if health_signal is not None and health_signal.penalty > 0:
                reasons.append(f"Selected route has a health penalty of {health_signal.penalty:.0f}.")
            if health_signal is not None and health_signal.cooldown:
                reasons.append("Selected route is currently marked for cooldown.")

            diffs.append(
                ModelRegistryBenchmarkRoleDiff(
                    role=role_id,
                    action=action,
                    current_primary_model=current_primary,
                    proposed_primary_model=proposed_primary,
                    current_fallback_models=current_fallbacks,
                    proposed_fallback_models=proposed_fallbacks,
                    winner_provider_id=winner.provider_id,
                    winner_provider_label=winner.provider_label,
                    winner_model=winner.model_name,
                    winner_score=winner_score,
                    health_penalty=health_signal.penalty if health_signal is not None else 0.0,
                    health_cooldown=health_signal.cooldown if health_signal is not None else False,
                    health_recommendation=health_signal.recommendation if health_signal is not None else "",
                    reasons=reasons,
                )
            )
        return diffs

    def _health_adjusted_benchmark_winners(
        self,
        winners: dict[str, list[ModelBenchmarkProviderScore]],
        route_health: list[ModelRouteHealthInfo],
    ) -> dict[str, list[ModelBenchmarkProviderScore]]:
        health_lookup = self._route_health_lookup(route_health)
        suite_fields = {
            "chat": "chat_score",
            "code": "code_score",
            "reasoning": "reasoning_score",
        }
        adjusted: dict[str, list[ModelBenchmarkProviderScore]] = {}
        for role_id, scores in winners.items():
            field_name = suite_fields.get(role_id, "overall_score")
            non_cooldown = [
                score
                for score in scores
                if not self._route_health_cooldown(score, role_id, health_lookup)
            ]
            ranked = non_cooldown or scores
            ranked = sorted(
                ranked,
                key=lambda score: self._health_adjusted_score_key(score, role_id, field_name, health_lookup),
                reverse=True,
            )
            if ranked:
                adjusted[role_id] = ranked
        return adjusted

    def _route_health_lookup(
        self,
        route_health: list[ModelRouteHealthInfo],
    ) -> dict[tuple[str, str, str], ModelRouteHealthInfo]:
        lookup: dict[tuple[str, str, str], ModelRouteHealthInfo] = {}
        for signal in route_health:
            provider_id = signal.provider_id.strip().lower()
            model = signal.model.strip().lower()
            role = signal.role.strip().lower()
            if provider_id:
                lookup[(provider_id, model, role)] = signal
        return lookup

    def _route_health_signal_for_score(
        self,
        score: ModelBenchmarkProviderScore,
        role_id: str,
        health_lookup: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> ModelRouteHealthInfo | None:
        provider_id = score.provider_id.strip().lower()
        model = score.model_name.strip().lower()
        role = role_id.strip().lower()
        for key in (
            (provider_id, model, role),
            (provider_id, "", role),
            (provider_id, model, ""),
            (provider_id, "", ""),
        ):
            signal = health_lookup.get(key)
            if signal is not None:
                return signal
        return None

    def _route_health_cooldown(
        self,
        score: ModelBenchmarkProviderScore,
        role_id: str,
        health_lookup: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> bool:
        signal = self._route_health_signal_for_score(score, role_id, health_lookup)
        return bool(signal and signal.cooldown)

    def _health_adjusted_score_key(
        self,
        score: ModelBenchmarkProviderScore,
        role_id: str,
        field_name: str,
        health_lookup: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> tuple[float, float, int, int]:
        signal = self._route_health_signal_for_score(score, role_id, health_lookup)
        health_penalty = 0.0
        if signal is not None:
            health_penalty += min(max(signal.penalty, 0.0) / 10000.0, 1.25)
            health_penalty += min(max(signal.failure_rate, 0.0) * 0.25, 0.25)
            if signal.average_latency_ms is not None and signal.average_latency_ms >= 30_000:
                health_penalty += min((signal.average_latency_ms - 30_000) / 120_000.0, 0.25)
            if signal.cooldown:
                health_penalty += 10.0

        suite_score = float(getattr(score, field_name) or 0.0)
        effective_score = suite_score - health_penalty
        return (
            effective_score,
            score.overall_score,
            -(score.avg_latency_ms or 999999),
            score.run_count,
        )

    def _merge_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        defaults = self._default_registry()
        merged = {**defaults, **payload}
        payload_version = self._clean_version(payload.get("version"))
        backfill_missing_defaults = payload_version < REGISTRY_VERSION
        merged["version"] = max(self._clean_version(merged.get("version")), REGISTRY_VERSION)
        merged["providers"] = self._merge_provider_list(
            payload.get("providers"),
            defaults["providers"],
            append_missing_defaults=backfill_missing_defaults,
        )
        merged["roles"] = self._merge_object_list(
            payload.get("roles"),
            defaults["roles"],
            append_missing_defaults=backfill_missing_defaults,
        )
        merged["presets"] = self._merge_object_list(
            payload.get("presets"),
            defaults["presets"],
            append_missing_defaults=backfill_missing_defaults,
        )
        return merged

    def _merge_provider_list(
        self,
        value: Any,
        defaults: list[dict[str, Any]],
        *,
        append_missing_defaults: bool,
    ) -> list[dict[str, Any]]:
        source = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
        if not source:
            source = defaults
            append_missing_defaults = True

        defaults_by_id = {
            str(item.get("id", "")).strip(): item
            for item in defaults
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        providers: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in source:
            provider_id = str(item.get("id", "")).strip()
            provider = self._normalize_provider(item, defaults_by_id.get(provider_id))
            provider_id = str(provider.get("id", "")).strip()
            if not provider_id or provider_id in seen:
                continue
            providers.append(provider)
            seen.add(provider_id)

        if append_missing_defaults:
            for default in defaults:
                provider_id = str(default.get("id", "")).strip()
                if provider_id and provider_id not in seen:
                    providers.append(self._normalize_provider(default, default))
                    seen.add(provider_id)
        return providers

    def _merge_object_list(
        self,
        value: Any,
        defaults: list[dict[str, Any]],
        *,
        append_missing_defaults: bool,
    ) -> list[dict[str, Any]]:
        source = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
        if not source:
            append_missing_defaults = True
        defaults_by_id = {
            str(item.get("id", "")).strip(): item
            for item in defaults
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in source:
            item_id = str(item.get("id", "")).strip()
            if not item_id or item_id in seen:
                continue
            merged.append({**defaults_by_id.get(item_id, {}), **item})
            seen.add(item_id)

        if append_missing_defaults:
            for default in defaults:
                item_id = str(default.get("id", "")).strip()
                if item_id and item_id not in seen:
                    merged.append(default)
                    seen.add(item_id)
        return merged or defaults

    def _normalize_provider(self, raw: dict[str, Any], defaults: dict[str, Any] | None) -> dict[str, Any]:
        provider = {**(defaults or {}), **raw}
        provider_id = str(provider.get("id") or "").strip()
        api = str(provider.get("api") or "openai-compatible").strip()
        endpoint = str(provider.get("endpoint") or "").strip().rstrip("/")
        active_model = self.settings.aegis_model_name.strip()
        active_like = self._is_active_provider(provider_id, api, endpoint)

        model_name = str(
            provider.get("model_name")
            or provider.get("model")
            or provider.get("default_model")
            or ""
        ).strip()
        if not model_name and active_like:
            model_name = active_model

        aliases = self._clean_list(provider.get("model_aliases", []))
        if model_name and model_name not in aliases:
            aliases.insert(0, model_name)

        local = self._clean_bool(provider.get("local"), is_local_endpoint(endpoint))
        configured_default = bool(model_name) if active_like else False
        configured = self._clean_bool(provider.get("configured"), configured_default)

        return {
            "id": provider_id,
            "label": str(provider.get("label") or provider_label(api, endpoint) or provider_id).strip(),
            "api": api,
            "endpoint": endpoint,
            "model_name": model_name,
            "model_aliases": aliases,
            "secret_env": str(provider.get("secret_env") or secret_env_name(api, endpoint)).strip(),
            "local": local,
            "enabled": self._clean_bool(provider.get("enabled"), True),
            "configured": configured,
            "capabilities": self._clean_list(provider.get("capabilities", [])),
            "roles": self._clean_list(provider.get("roles", [])),
            "cost_tier": str(provider.get("cost_tier") or ("low" if local else "unknown")).strip() or "unknown",
            "context_window": self._clean_optional_int(provider.get("context_window")),
            "rate_limit_rpm": self._clean_optional_int(provider.get("rate_limit_rpm")),
            "input_cost_per_million": self._clean_optional_float(provider.get("input_cost_per_million")),
            "output_cost_per_million": self._clean_optional_float(provider.get("output_cost_per_million")),
            "health": str(provider.get("health") or ("configured" if configured else "planned")).strip(),
            "notes": str(provider.get("notes") or "").strip(),
        }

    def _clean_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        if value is None:
            return default
        return bool(value)

    def _clean_version(self, value: Any) -> int:
        try:
            parsed = int(value or 1)
        except (TypeError, ValueError):
            return 1
        return parsed if parsed > 0 else 1

    def _clean_optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _clean_optional_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0.0 else None

    def _is_active_provider(self, provider_id: str, api: str, endpoint: str) -> bool:
        if provider_id == self._active_provider_id():
            return True
        active_endpoint = self.settings.aegis_model_endpoint.strip().rstrip("/")
        return bool(
            api.strip().lower() == self.settings.aegis_model_api.strip().lower()
            and endpoint
            and active_endpoint
            and endpoint == active_endpoint
        )

    def _active_provider_id(self) -> str:
        api = self.settings.aegis_model_api.strip().lower() or "ollama"
        return f"{api}:active"

    def _refresh_provider_availability(self, payload: dict[str, Any]) -> dict[str, Any]:
        providers = [dict(item) for item in payload.get("providers", []) if isinstance(item, dict)]
        if not providers:
            return payload

        changed = False
        ollama_by_endpoint: dict[str, set[str] | None] = {}
        known_ollama_models: dict[tuple[str, str], str] = {}

        for index, provider in enumerate(providers):
            api = str(provider.get("api") or "").strip().lower()
            endpoint = str(provider.get("endpoint") or "").strip().rstrip("/")
            model_name = str(provider.get("model_name") or "").strip()
            secret_env = str(provider.get("secret_env") or secret_env_name(api, endpoint)).strip()

            if api == "ollama" and endpoint and is_local_endpoint(endpoint):
                if endpoint not in ollama_by_endpoint:
                    ollama_by_endpoint[endpoint] = self._installed_ollama_models(endpoint)
                installed = ollama_by_endpoint[endpoint]
                if model_name:
                    traits = self._local_model_traits(model_name)
                    for key, value in (
                        ("roles", traits["roles"]),
                        ("capabilities", traits["capabilities"]),
                        ("context_window", traits["context_window"]),
                        ("notes", provider.get("notes") or traits["notes"]),
                    ):
                        if provider.get(key) != value:
                            provider[key] = value
                            changed = True
                    known_ollama_models[(endpoint, model_name)] = provider.get("id", "")
                    if installed is not None:
                        available = model_name in installed
                        desired_health = "available" if available else "missing-local-model"
                        if provider.get("configured") != available:
                            provider["configured"] = available
                            changed = True
                        if provider.get("health") != desired_health:
                            provider["health"] = desired_health
                            changed = True
                        providers[index] = provider
                continue

            if model_name.lower().startswith(("gpt-image", "gpt-realtime")) and provider.get("enabled") is not False:
                provider["enabled"] = False
                provider["health"] = "adapter-planned"
                changed = True
                providers[index] = provider

            if secret_env and model_name and not provider.get("local"):
                has_secret = bool(secret_value(secret_env))
                desired_health = (
                    str(provider.get("health") or "adapter-planned")
                    if provider.get("enabled") is False
                    else ("configured" if has_secret else f"missing-secret:{secret_env}")
                )
                if provider.get("configured") != has_secret:
                    provider["configured"] = has_secret
                    changed = True
                if provider.get("health") != desired_health:
                    provider["health"] = desired_health
                    changed = True
                providers[index] = provider

        base_ollama_keys = {
            (
                str(provider.get("endpoint") or "").strip().rstrip("/"),
                str(provider.get("model_name") or "").strip(),
            )
            for provider in providers
            if str(provider.get("api") or "").strip().lower() == "ollama"
            and str(provider.get("model_name") or "").strip()
            and not str(provider.get("model_name") or "").strip().endswith(":latest")
        }
        filtered_providers: list[dict[str, Any]] = []
        for provider in providers:
            api = str(provider.get("api") or "").strip().lower()
            endpoint = str(provider.get("endpoint") or "").strip().rstrip("/")
            model_name = str(provider.get("model_name") or "").strip()
            if api == "ollama" and model_name.endswith(":latest"):
                base_name = model_name[: -len(":latest")]
                if (endpoint, base_name) in base_ollama_keys:
                    changed = True
                    continue
            filtered_providers.append(provider)
        providers = filtered_providers

        known_ollama_models = {}
        for provider in providers:
            if str(provider.get("api") or "").strip().lower() != "ollama":
                continue
            endpoint = str(provider.get("endpoint") or "").strip().rstrip("/")
            model_name = str(provider.get("model_name") or "").strip()
            if endpoint and model_name:
                known_ollama_models[(endpoint, model_name)] = provider.get("id", "")

        for endpoint, installed in ollama_by_endpoint.items():
            if installed is None:
                continue
            for model_name in sorted(installed):
                if model_name.endswith(":latest"):
                    base_name = model_name[: -len(":latest")]
                    if (endpoint, base_name) in known_ollama_models:
                        continue
                if (endpoint, model_name) in known_ollama_models:
                    continue
                providers.append(
                    self._ollama_provider(
                        model_name,
                        endpoint=endpoint,
                        configured=True,
                        health="available",
                        notes="Discovered from the local Ollama inventory.",
                    )
                )
                known_ollama_models[(endpoint, model_name)] = model_name
                changed = True

        if not changed:
            return payload
        refreshed = {**payload, "providers": providers}
        self._save(refreshed)
        return refreshed

    def _installed_ollama_models(self, endpoint: str) -> set[str] | None:
        url = f"{endpoint.rstrip('/')}/api/tags"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except (OSError, urllib.error.URLError, TimeoutError):
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        models = payload.get("models", []) if isinstance(payload, dict) else []
        installed: set[str] = set()
        if not isinstance(models, list):
            return installed
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                installed.add(name)
                if name.endswith(":latest"):
                    installed.add(name[: -len(":latest")])
                elif ":" not in name:
                    installed.add(f"{name}:latest")
        return installed

    def _ollama_provider(
        self,
        model_name: str,
        *,
        endpoint: str,
        configured: bool = False,
        health: str = "pullable",
        notes: str = "",
    ) -> dict[str, Any]:
        traits = self._local_model_traits(model_name)
        return {
            "id": f"ollama:{self._model_slug(model_name)}",
            "label": traits["label"],
            "api": "ollama",
            "endpoint": endpoint,
            "model_name": model_name,
            "model_aliases": [model_name],
            "secret_env": "",
            "local": True,
            "enabled": True,
            "configured": configured,
            "capabilities": traits["capabilities"],
            "roles": traits["roles"],
            "cost_tier": "low",
            "context_window": traits["context_window"],
            "rate_limit_rpm": None,
            "input_cost_per_million": None,
            "output_cost_per_million": None,
            "health": health,
            "notes": notes or traits["notes"],
        }

    def _cloud_provider(
        self,
        provider_id: str,
        *,
        label: str,
        api: str,
        endpoint: str,
        model_name: str,
        secret_env: str,
        capabilities: list[str],
        roles: list[str],
        cost_tier: str,
        context_window: int | None = None,
        notes: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        configured = bool(secret_value(secret_env))
        return {
            "id": provider_id,
            "label": label,
            "api": api,
            "endpoint": endpoint.rstrip("/"),
            "model_name": model_name,
            "model_aliases": [model_name] if model_name else [],
            "secret_env": secret_env,
            "local": False,
            "enabled": enabled,
            "configured": configured,
            "capabilities": capabilities,
            "roles": roles,
            "cost_tier": cost_tier,
            "context_window": context_window,
            "rate_limit_rpm": None,
            "input_cost_per_million": None,
            "output_cost_per_million": None,
            "health": "configured" if configured else f"missing-secret:{secret_env}",
            "notes": notes,
        }

    def _model_slug(self, model_name: str) -> str:
        cleaned: list[str] = []
        previous_dash = False
        for char in model_name.strip().lower():
            if char.isalnum():
                cleaned.append(char)
                previous_dash = False
            elif not previous_dash:
                cleaned.append("-")
                previous_dash = True
        return "".join(cleaned).strip("-") or "model"

    def _local_model_traits(self, model_name: str) -> dict[str, Any]:
        lowered = model_name.lower()
        roles = ["chat", "fallback"]
        capabilities = ["chat", "structured_json"]
        notes = "General local chat model."
        context_window: int | None = None

        if "embed" in lowered or "nomic" in lowered or "minilm" in lowered or "bge" in lowered:
            return {
                "label": f"Ollama Local / {model_name}",
                "roles": ["embeddings", "rag"],
                "capabilities": ["embeddings"],
                "context_window": None,
                "notes": "Local embedding model for future RAG and semantic search lanes.",
            }

        if "vision" in lowered or "llava" in lowered:
            roles = ["vision", "chat", "reasoning", "fallback"]
            capabilities = ["chat", "vision", "structured_json", "reasoning"]
            notes = "Local multimodal model for future image-aware chat and visual analysis lanes."

        if any(term in lowered for term in ("coder", "code", "starcoder", "granite", "devstral")):
            roles = ["code", "debug", "review", "refactor", "fallback"]
            capabilities = ["chat", "code", "structured_json"]
            notes = "Local code-specialized model for file edits, debugging, review, and refactors."

        if any(term in lowered for term in ("qwen3", "deepseek-r1", "phi4", "mistral", "gpt-oss")):
            roles = list(dict.fromkeys(["reasoning", "architecture", "judge", *roles]))
            capabilities = list(dict.fromkeys([*capabilities, "reasoning", "judge"]))
            notes = "Local reasoning-oriented model for planning, critique, and harder prompts."

        if any(term in lowered for term in ("llama3.2", "gemma", "qwen2.5")) and "coder" not in lowered:
            roles = list(dict.fromkeys(["chat", "reasoning", *roles]))
            capabilities = list(dict.fromkeys([*capabilities, "reasoning"]))

        if "90b" in lowered or "72b" in lowered or "70b" in lowered:
            context_window = 128000
        elif "35b" in lowered or "34b" in lowered or "32b" in lowered or "30b" in lowered or "27b" in lowered or "24b" in lowered:
            context_window = 32768
        elif "14b" in lowered or "12b" in lowered:
            context_window = 32768
        elif "8b" in lowered or "7b" in lowered:
            context_window = 32768
        elif "4b" in lowered or "3b" in lowered or "2b" in lowered or "1b" in lowered:
            context_window = 8192

        return {
            "label": f"Ollama Local / {model_name}",
            "roles": roles,
            "capabilities": capabilities,
            "context_window": context_window,
            "notes": notes,
        }

    def _default_registry(self) -> dict[str, Any]:
        api = self.settings.aegis_model_api.strip().lower() or "ollama"
        provider_label = "Ollama Local" if api == "ollama" else "OpenAI-Compatible"
        provider_id = self._active_provider_id()
        endpoint = self.settings.aegis_model_endpoint.rstrip("/")
        model = self.settings.aegis_model_name.strip()
        local = is_local_endpoint(endpoint)

        providers = [
            {
                "id": provider_id,
                "label": provider_label,
                "api": api,
                "endpoint": endpoint,
                "model_name": model,
                "model_aliases": [model] if model else [],
                "secret_env": secret_env_name(api, endpoint),
                "local": local,
                "enabled": True,
                "configured": bool(model),
                "capabilities": ["chat", "structured_json", "code"],
                "roles": ["chat", "code", "reasoning", "fallback"],
                "cost_tier": "low" if local else "unknown",
                "context_window": None,
                "rate_limit_rpm": None,
                "input_cost_per_million": None,
                "output_cost_per_million": None,
                "health": "configured" if model else "missing-model",
                "notes": "Created from the active Aegis model settings.",
            }
        ]

        if api == "ollama" and endpoint:
            local_models = [
                "llama3.2:1b",
                "llama3.2:3b",
                "llama3.1:8b",
                "gemma3:1b",
                "phi4-mini",
                "phi4",
                "gpt-oss:20b",
                "qwen3:30b",
                "qwen3-coder:30b",
                "qwq:32b",
                "qwen3:4b",
                "qwen3:8b",
                "qwen3:14b",
                "deepseek-r1:1.5b",
                "deepseek-r1:7b",
                "deepseek-r1:8b",
                "deepseek-r1:14b",
                "gemma3:4b",
                "gemma3:12b",
                "gemma3:27b",
                "mistral:7b",
                "mistral-small:24b",
                "magistral:24b",
                "qwen2.5:7b",
                "qwen2.5:14b",
                "qwen2.5:32b",
                "qwen2.5:72b",
                "qwen2.5-coder:1.5b",
                "qwen2.5-coder:3b",
                "qwen2.5-coder:7b",
                "qwen2.5-coder:14b",
                "qwen2.5-coder:32b",
                "codellama:7b",
                "deepseek-coder-v2:16b",
                "devstral:24b",
                "command-r:35b",
                "mixtral:8x7b",
                "llama3.3:70b",
                "llama3.1:70b",
                "llama3.2-vision:11b",
                "llama3.2-vision:90b",
                "llava:13b",
                "llava:34b",
                "yi:34b",
                "starcoder2:3b",
                "starcoder2:7b",
                "granite-code:3b",
                "granite-code:8b",
                "codegemma:2b",
                "nomic-embed-text",
                "mxbai-embed-large",
                "all-minilm",
                "bge-m3",
                "snowflake-arctic-embed2",
            ]
            providers.extend(
                self._ollama_provider(
                    local_model,
                    endpoint=endpoint,
                    configured=False,
                    health="pullable",
                    notes="Part of the expanded local Ollama model pack.",
                )
                for local_model in local_models
            )

        providers.extend(
            [
                self._cloud_provider(
                    "openai:gpt-5.5",
                    label="OpenAI / gpt-5.5",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-5.5",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "debug", "review", "reasoning", "architecture", "judge"],
                    cost_tier="high",
                    context_window=1_000_000,
                    notes="Flagship OpenAI lane for complex reasoning, coding, and agentic work.",
                ),
                self._cloud_provider(
                    "openai:gpt-5.4",
                    label="OpenAI / gpt-5.4",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-5.4",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "debug", "review", "reasoning", "architecture", "judge"],
                    cost_tier="medium",
                    context_window=1_000_000,
                    notes="Balanced OpenAI lane for coding and professional work.",
                ),
                self._cloud_provider(
                    "openai:gpt-5.4-mini",
                    label="OpenAI / gpt-5.4-mini",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-5.4-mini",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "reasoning", "fallback", "judge"],
                    cost_tier="low",
                    context_window=400_000,
                    notes="Lower-cost OpenAI lane for everyday chat, code, and subagent tasks.",
                ),
                self._cloud_provider(
                    "openai:gpt-5.2-codex",
                    label="OpenAI / GPT-5.2 Codex",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-5.2-codex",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["chat", "reasoning", "tools", "structured_json", "code"],
                    roles=["code", "debug", "review", "refactor", "architecture", "judge"],
                    cost_tier="high",
                    context_window=400_000,
                    notes="Codex-optimized cloud lane for long-horizon coding tasks.",
                ),
                self._cloud_provider(
                    "openai:gpt-image-2",
                    label="OpenAI / GPT Image 2",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-image-2",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["image", "vision", "creative"],
                    roles=["image", "creative", "creative_judge"],
                    cost_tier="variable",
                    notes="Cloud image generation and editing lane.",
                    enabled=False,
                ),
                self._cloud_provider(
                    "openai:gpt-realtime-1.5",
                    label="OpenAI / gpt-realtime-1.5",
                    api="openai",
                    endpoint="https://api.openai.com/v1",
                    model_name="gpt-realtime-1.5",
                    secret_env="OPENAI_API_KEY",
                    capabilities=["audio", "realtime", "chat"],
                    roles=["audio", "voice", "realtime"],
                    cost_tier="variable",
                    notes="Future realtime voice lane; the current backend does not stream realtime yet.",
                    enabled=False,
                ),
                self._cloud_provider(
                    "anthropic:claude-sonnet-4-6",
                    label="Anthropic / Claude Sonnet 4.6",
                    api="anthropic",
                    endpoint="https://api.anthropic.com",
                    model_name="claude-sonnet-4-6",
                    secret_env="ANTHROPIC_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "code", "structured_json"],
                    roles=["chat", "code", "debug", "review", "reasoning", "architecture", "judge"],
                    cost_tier="medium",
                    context_window=200_000,
                    notes="Claude lane for code review, architecture, long context, and careful writing.",
                ),
                self._cloud_provider(
                    "anthropic:claude-opus-4-6",
                    label="Anthropic / Claude Opus 4.6",
                    api="anthropic",
                    endpoint="https://api.anthropic.com",
                    model_name="claude-opus-4-6",
                    secret_env="ANTHROPIC_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "code", "structured_json"],
                    roles=["code", "debug", "review", "reasoning", "architecture", "judge"],
                    cost_tier="high",
                    context_window=200_000,
                    notes="High-end Claude lane for difficult engineering and reasoning tasks.",
                ),
                self._cloud_provider(
                    "openrouter:auto",
                    label="OpenRouter / Auto Router",
                    api="openrouter",
                    endpoint="https://openrouter.ai/api/v1",
                    model_name="openrouter/auto",
                    secret_env="OPENROUTER_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "research", "creative", "reasoning", "fallback", "judge"],
                    cost_tier="variable",
                    notes="Aggregator lane that can route across hundreds of hosted models.",
                ),
                self._cloud_provider(
                    "perplexity:sonar-pro",
                    label="Perplexity / Sonar Pro",
                    api="perplexity",
                    endpoint="https://api.perplexity.ai/v1",
                    model_name="sonar-pro",
                    secret_env="PERPLEXITY_API_KEY",
                    capabilities=["chat", "research", "search", "citations", "freshness", "structured_json"],
                    roles=["research", "fact_check", "citation_judge", "chat"],
                    cost_tier="variable",
                    context_window=128_000,
                    notes="Fresh web-grounded research lane with citations.",
                ),
                self._cloud_provider(
                    "perplexity:sonar",
                    label="Perplexity / Sonar",
                    api="perplexity",
                    endpoint="https://api.perplexity.ai/v1",
                    model_name="sonar",
                    secret_env="PERPLEXITY_API_KEY",
                    capabilities=["chat", "research", "search", "citations", "freshness"],
                    roles=["research", "fact_check", "chat"],
                    cost_tier="low",
                    context_window=128_000,
                    notes="Fast, lower-cost web-grounded research lane.",
                ),
                self._cloud_provider(
                    "xai:grok-4",
                    label="xAI / Grok 4",
                    api="xai",
                    endpoint="https://api.x.ai/v1",
                    model_name="grok-4",
                    secret_env="XAI_API_KEY",
                    capabilities=["chat", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "reasoning", "code", "judge"],
                    cost_tier="variable",
                    notes="OpenAI-compatible xAI lane.",
                ),
                self._cloud_provider(
                    "groq:llama-fast",
                    label="Groq / Fast Llama",
                    api="groq",
                    endpoint="https://api.groq.com/openai",
                    model_name="llama-3.3-70b-versatile",
                    secret_env="GROQ_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "reasoning", "fallback"],
                    cost_tier="low",
                    notes="Very fast OpenAI-compatible hosted inference lane.",
                ),
                self._cloud_provider(
                    "mistral:large",
                    label="Mistral AI / Large",
                    api="mistral",
                    endpoint="https://api.mistral.ai",
                    model_name="mistral-large-latest",
                    secret_env="MISTRAL_API_KEY",
                    capabilities=["chat", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "reasoning", "judge"],
                    cost_tier="medium",
                    notes="Mistral hosted model lane through an OpenAI-compatible adapter.",
                ),
                self._cloud_provider(
                    "deepseek:chat",
                    label="DeepSeek / Chat",
                    api="deepseek",
                    endpoint="https://api.deepseek.com",
                    model_name="deepseek-chat",
                    secret_env="DEEPSEEK_API_KEY",
                    capabilities=["chat", "structured_json", "code"],
                    roles=["chat", "code", "debug", "fallback"],
                    cost_tier="low",
                    notes="DeepSeek hosted coding/chat lane through an OpenAI-compatible adapter.",
                ),
                self._cloud_provider(
                    "deepseek:reasoner",
                    label="DeepSeek / Reasoner",
                    api="deepseek",
                    endpoint="https://api.deepseek.com",
                    model_name="deepseek-reasoner",
                    secret_env="DEEPSEEK_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["reasoning", "architecture", "debug", "judge"],
                    cost_tier="low",
                    notes="DeepSeek hosted reasoning lane.",
                ),
                self._cloud_provider(
                    "together:llama",
                    label="Together AI / Llama",
                    api="together",
                    endpoint="https://api.together.xyz",
                    model_name="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                    secret_env="TOGETHER_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "reasoning", "fallback"],
                    cost_tier="low",
                    notes="Together hosted open model lane.",
                ),
                self._cloud_provider(
                    "cerebras:fast",
                    label="Cerebras / Fast Inference",
                    api="cerebras",
                    endpoint="https://api.cerebras.ai",
                    model_name="llama3.1-8b",
                    secret_env="CEREBRAS_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json"],
                    roles=["chat", "fallback"],
                    cost_tier="low",
                    notes="Fast hosted OpenAI-compatible lane.",
                ),
                self._cloud_provider(
                    "fireworks:llama",
                    label="Fireworks AI / Llama",
                    api="fireworks",
                    endpoint="https://api.fireworks.ai/inference",
                    model_name="accounts/fireworks/models/llama-v3p1-70b-instruct",
                    secret_env="FIREWORKS_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "code", "reasoning", "fallback"],
                    cost_tier="low",
                    notes="Fireworks hosted open model lane.",
                ),
                self._cloud_provider(
                    "google:gemini-2.5-pro",
                    label="Google / Gemini 2.5 Pro",
                    api="google",
                    endpoint="https://generativelanguage.googleapis.com/v1beta/openai",
                    model_name="gemini-2.5-pro",
                    secret_env="GEMINI_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "code", "debug", "review", "reasoning", "architecture", "judge"],
                    cost_tier="medium",
                    context_window=1_000_000,
                    notes="Gemini OpenAI-compatible cloud lane for long context, multimodal, and reasoning work.",
                ),
                self._cloud_provider(
                    "google:gemini-2.5-flash",
                    label="Google / Gemini 2.5 Flash",
                    api="google",
                    endpoint="https://generativelanguage.googleapis.com/v1beta/openai",
                    model_name="gemini-2.5-flash",
                    secret_env="GEMINI_API_KEY",
                    capabilities=["chat", "vision", "reasoning", "tools", "structured_json", "code"],
                    roles=["chat", "reasoning", "fallback", "judge"],
                    cost_tier="low",
                    context_window=1_000_000,
                    notes="Fast Gemini cloud lane for low-latency general tasks.",
                ),
                self._cloud_provider(
                    "huggingface:router-llama",
                    label="Hugging Face Router / Llama",
                    api="huggingface",
                    endpoint="https://router.huggingface.co/v1",
                    model_name="meta-llama/Llama-3.1-70B-Instruct",
                    secret_env="HUGGINGFACE_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "code", "reasoning", "fallback"],
                    cost_tier="variable",
                    notes="Hugging Face Inference Router lane through an OpenAI-compatible API.",
                ),
                self._cloud_provider(
                    "nvidia:nemotron",
                    label="NVIDIA NIM / Nemotron",
                    api="nvidia",
                    endpoint="https://integrate.api.nvidia.com/v1",
                    model_name="nvidia/llama-3.1-nemotron-ultra-253b-v1",
                    secret_env="NVIDIA_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "reasoning", "judge", "fallback"],
                    cost_tier="variable",
                    notes="NVIDIA hosted NIM lane for large hosted reasoning models.",
                ),
                self._cloud_provider(
                    "sambanova:llama-3.3-70b",
                    label="SambaNova / Llama 3.3 70B",
                    api="sambanova",
                    endpoint="https://api.sambanova.ai/v1",
                    model_name="Meta-Llama-3.3-70B-Instruct",
                    secret_env="SAMBANOVA_API_KEY",
                    capabilities=["chat", "reasoning", "structured_json", "code"],
                    roles=["chat", "code", "reasoning", "fallback"],
                    cost_tier="variable",
                    notes="SambaNova hosted OpenAI-compatible lane.",
                ),
                {
                    "id": "local:lmstudio",
                    "label": "LM Studio Local",
                    "api": "lmstudio",
                    "endpoint": "http://127.0.0.1:1234",
                    "model_name": "",
                    "model_aliases": [],
                    "secret_env": "",
                    "local": True,
                    "enabled": True,
                    "configured": False,
                    "capabilities": ["chat", "structured_json", "code", "reasoning"],
                    "roles": ["chat", "code", "reasoning", "fallback"],
                    "cost_tier": "low",
                    "context_window": None,
                    "rate_limit_rpm": None,
                    "input_cost_per_million": None,
                    "output_cost_per_million": None,
                    "health": "waiting-for-local-server",
                    "notes": "OpenAI-compatible local server lane for LM Studio.",
                },
                {
                    "id": "local:vllm",
                    "label": "vLLM Local",
                    "api": "openai-compatible",
                    "endpoint": "http://127.0.0.1:8000",
                    "model_name": "",
                    "model_aliases": [],
                    "secret_env": "",
                    "local": True,
                    "enabled": True,
                    "configured": False,
                    "capabilities": ["chat", "structured_json", "code", "reasoning"],
                    "roles": ["chat", "code", "reasoning", "fallback"],
                    "cost_tier": "low",
                    "context_window": None,
                    "rate_limit_rpm": None,
                    "input_cost_per_million": None,
                    "output_cost_per_million": None,
                    "health": "waiting-for-local-server",
                    "notes": "OpenAI-compatible local server lane for vLLM, llama.cpp servers, and similar runtimes.",
                },
            ]
        )

        roles = [
            {
                "id": "chat",
                "label": "General Chat",
                "description": "Default conversational, productivity, and knowledge tasks.",
                "primary_model": "llama3.2:3b" if api == "ollama" else model,
                "fallback_models": [model] if model else [],
                "required_capabilities": ["chat"],
                "privacy_mode": "local-first",
                "cost_tier": "low",
                "status": "active" if model else "needs-model",
            },
            {
                "id": "code",
                "label": "Coding Agent",
                "description": "Web, mobile, desktop, macOS, Linux, Windows, game, data, and system coding.",
                "primary_model": "qwen2.5-coder:32b" if api == "ollama" else model,
                "fallback_models": ["qwen2.5-coder:14b", "qwen2.5-coder:7b", model] if model else [],
                "required_capabilities": ["chat", "code", "structured_json"],
                "privacy_mode": "local-first",
                "cost_tier": "medium",
                "status": "active" if model else "needs-model",
            },
            {
                "id": "reasoning",
                "label": "Deep Reasoning",
                "description": "Planning, architecture, debugging, evaluation, and hard problem solving.",
                "primary_model": "qwen3:14b" if api == "ollama" else model,
                "fallback_models": ["deepseek-r1:14b", "phi4-mini", model] if model else [],
                "required_capabilities": ["chat", "structured_json"],
                "privacy_mode": "local-first",
                "cost_tier": "medium",
                "status": "active" if model else "needs-model",
            },
            {
                "id": "research",
                "label": "Research",
                "description": "Fresh web research, source tracking, citations, and uncertainty checks.",
                "primary_model": "sonar-pro",
                "fallback_models": ["sonar", model] if model else ["sonar"],
                "required_capabilities": ["research", "search", "citations"],
                "privacy_mode": "cloud-allowed",
                "cost_tier": "variable",
                "status": "active",
            },
            {
                "id": "image",
                "label": "Image Creation",
                "description": "Image generation, thumbnails, icon sets, stickers, brand kits, and revisions.",
                "primary_model": "gpt-image-2",
                "fallback_models": [],
                "required_capabilities": ["image"],
                "privacy_mode": "cloud-allowed",
                "cost_tier": "variable",
                "status": "active",
            },
            {
                "id": "video",
                "label": "Video And Motion",
                "description": "Video generation, video editing, animation, GIFs, storyboards, and export plans.",
                "primary_model": "",
                "fallback_models": [],
                "required_capabilities": ["video", "animation"],
                "privacy_mode": "cloud-allowed",
                "cost_tier": "high",
                "status": "planned",
            },
            {
                "id": "audio",
                "label": "Music And Audio",
                "description": "Beat creation, arrangements, MIDI/stem planning, voice cleanup, and mix guidance.",
                "primary_model": "gpt-realtime-1.5",
                "fallback_models": [],
                "required_capabilities": ["audio", "realtime"],
                "privacy_mode": "cloud-allowed",
                "cost_tier": "variable",
                "status": "active",
            },
            {
                "id": "judge",
                "label": "Judge And Evals",
                "description": "Critique, compare, score, and select outputs across models.",
                "primary_model": "phi4-mini" if api == "ollama" else model,
                "fallback_models": ["qwen3:8b", model] if model else [],
                "required_capabilities": ["chat", "structured_json", "judge"],
                "privacy_mode": "local-first",
                "cost_tier": "low",
                "status": "active" if model else "needs-model",
            },
        ]

        presets = [
            {
                "id": "local_first",
                "label": "Local First",
                "description": "Prefer local/private models and only use planned cloud roles when explicitly enabled.",
                "role_order": ["chat", "code", "reasoning", "judge", "fallback"],
                "privacy_mode": "local-only",
            },
            {
                "id": "balanced",
                "label": "Balanced",
                "description": "Use local chat/code first, then specialist providers for creative and research tasks.",
                "role_order": ["chat", "code", "reasoning", "research", "image", "video", "audio", "judge"],
                "privacy_mode": "hybrid",
            },
            {
                "id": "best_available",
                "label": "Best Available",
                "description": "Route to the strongest configured specialist per task, then judge and synthesize.",
                "role_order": ["reasoning", "code", "research", "image", "video", "audio", "judge"],
                "privacy_mode": "cloud-allowed",
            },
        ]

        return {
            "version": REGISTRY_VERSION,
            "active_provider_id": provider_id,
            "router_enabled": True,
            "fallback_supported": True,
            "message": "Registry foundation is ready. Aegis can route live requests to the best configured model for the prompt.",
            "providers": providers,
            "roles": roles,
            "presets": presets,
        }
