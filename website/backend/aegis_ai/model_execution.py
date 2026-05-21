from __future__ import annotations

from dataclasses import dataclass, field

from .routing import RouteCandidate
from .schemas import (
    ModelAttemptInfo,
    ModelBenchmarkProviderScore,
    ModelRegistryProvider,
    ModelRegistryRole,
    ModelRouteHealthInfo,
)
from .task_planner import TaskPlan
from .providers.base import api_family, is_local_endpoint, normalize_capability, provider_label


GENERIC_CAPABILITIES = {"chat", "structured_json"}


@dataclass(frozen=True)
class ModelExecutionPlan:
    attempts: list[ModelAttemptInfo] = field(default_factory=list)

    @property
    def primary(self) -> ModelAttemptInfo | None:
        return self.attempts[0] if self.attempts else None

    def to_event_payload(self) -> dict:
        return {
            "attempt_count": len(self.attempts),
            "primary": self.primary.model_dump() if self.primary else None,
            "attempts": [attempt.model_dump() for attempt in self.attempts],
        }


class ModelExecutionPlanner:
    def build_plan(
        self,
        task_plan: TaskPlan,
        *,
        providers: list[ModelRegistryProvider] | None = None,
        roles: list[ModelRegistryRole] | None = None,
        benchmark_scores: list[ModelBenchmarkProviderScore] | None = None,
        route_health: list[ModelRouteHealthInfo] | None = None,
    ) -> ModelExecutionPlan:
        provider_records = providers or []
        role_policies = {
            role.id.strip().lower(): role
            for role in (roles or [])
            if role.id.strip()
        }
        benchmark_by_provider = {
            score.provider_id: score
            for score in (benchmark_scores or [])
            if score.provider_id
        }
        route_health_by_provider = self._route_health_lookup(route_health or [])
        routing = task_plan.routing
        route_profile = task_plan.route_profile if isinstance(task_plan.route_profile, dict) else {}
        if routing is None:
            return ModelExecutionPlan(
                attempts=[
                    ModelAttemptInfo(
                        attempt=1,
                        role="fallback",
                        provider_id="deterministic:fallback",
                        provider_label="Deterministic Fallback",
                        provider_api="internal",
                        privacy_mode="local-only",
                        status="planned",
                        reason="No routing decision was available.",
                        retryable=False,
                        metadata={
                            "candidate_id": "fallback:fallback",
                            "candidate_source": "no-routing-decision",
                        },
                    )
                ]
            )

        attempts: list[ModelAttemptInfo] = []
        seen: set[tuple[str, str]] = set()
        for candidate in routing.candidates:
            provider = self._resolve_provider(
                candidate,
                provider_records,
                routing.privacy_mode,
                benchmark_by_provider,
                role_policies,
                route_health_by_provider,
                route_profile,
            )
            provider_key = provider.id if provider else candidate.provider_hint
            key = (candidate.role, provider_key)
            if key in seen:
                continue
            seen.add(key)
            required_capabilities = self._normalize_capabilities(candidate.required_capabilities)
            provider_id = provider.id if provider else self._provider_id(candidate.provider_hint)
            provider_label = provider.label if provider else candidate.provider_hint
            provider_api = provider.api if provider else self._provider_api(candidate.provider_hint)
            endpoint = provider.endpoint if provider else ""
            model = provider.model_name if provider else self._model_hint(candidate.provider_hint)
            attempts.append(
                ModelAttemptInfo(
                    attempt=len(attempts) + 1,
                    role=candidate.role,
                    provider_id=provider_id,
                    provider_label=provider_label,
                    provider_api=provider_api,
                    model=model,
                    endpoint=endpoint,
                    privacy_mode=candidate.privacy_mode,
                    status="planned",
                    reason=(
                        candidate.reason
                        if provider
                        else candidate.reason + " No configured registry provider matched this lane yet."
                    ),
                    retryable=provider is not None and provider.configured,
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "candidate_source": "planner",
                        "candidate_provider_hint": candidate.provider_hint,
                        "required_capabilities": sorted(required_capabilities),
                        "provider_capabilities": self._provider_capabilities(provider),
                        "provider_roles": self._provider_roles(provider),
                        "capability_match": provider is not None and not self._missing_required_capabilities(
                            provider,
                            required_capabilities - GENERIC_CAPABILITIES,
                        ),
                        "confidence": candidate.confidence,
                        "registry_resolved": provider is not None,
                        "cost_tier": provider.cost_tier if provider else "unknown",
                        "context_window": provider.context_window if provider else None,
                        "rate_limit_rpm": provider.rate_limit_rpm if provider else None,
                        "input_cost_per_million": provider.input_cost_per_million if provider else None,
                        "output_cost_per_million": provider.output_cost_per_million if provider else None,
                        **self._role_policy_metadata(candidate.role, role_policies),
                        **self._benchmark_metadata(provider, candidate.role, benchmark_by_provider),
                        **self._route_health_metadata(provider, candidate.role, route_health_by_provider),
                        **self._route_profile_metadata(route_profile),
                    },
                )
            )

        for role in routing.fallback_roles:
            fallback_provider = self._resolve_role_provider(
                role,
                provider_records,
                routing.privacy_mode,
                benchmark_scores=benchmark_by_provider,
                role_policies=role_policies,
                route_health=route_health_by_provider,
                route_profile=route_profile,
            )
            provider_key = fallback_provider.id if fallback_provider else "fallback"
            key = (role, provider_key)
            if key in seen:
                continue
            seen.add(key)
            candidate_id = self._fallback_candidate_id(role)
            attempts.append(
                ModelAttemptInfo(
                    attempt=len(attempts) + 1,
                    role=role,
                    provider_id=fallback_provider.id if fallback_provider else f"{role}:fallback",
                    provider_label=fallback_provider.label if fallback_provider else f"{role} fallback",
                    provider_api=fallback_provider.api if fallback_provider else "router",
                    model=fallback_provider.model_name if fallback_provider else "",
                    endpoint=fallback_provider.endpoint if fallback_provider else "",
                    privacy_mode=routing.privacy_mode,
                    status="planned",
                    reason=(
                        f"Fallback role for {routing.task_role}."
                        if fallback_provider
                        else f"Fallback role for {routing.task_role}; no configured provider matched yet."
                    ),
                    retryable=role != "fallback" and fallback_provider is not None and fallback_provider.configured,
                    metadata={
                        "candidate_id": candidate_id,
                        "candidate_source": "fallback-role",
                        "registry_resolved": fallback_provider is not None,
                        "cost_tier": fallback_provider.cost_tier if fallback_provider else "unknown",
                        "context_window": fallback_provider.context_window if fallback_provider else None,
                        "rate_limit_rpm": fallback_provider.rate_limit_rpm if fallback_provider else None,
                        "input_cost_per_million": fallback_provider.input_cost_per_million if fallback_provider else None,
                        "output_cost_per_million": fallback_provider.output_cost_per_million if fallback_provider else None,
                        **self._role_policy_metadata(role, role_policies),
                        **self._benchmark_metadata(fallback_provider, role, benchmark_by_provider),
                        **self._route_health_metadata(fallback_provider, role, route_health_by_provider),
                        **self._route_profile_metadata(route_profile),
                    },
                )
            )

        return ModelExecutionPlan(attempts=attempts)

    def apply_selected_provider(
        self,
        plan: ModelExecutionPlan,
        *,
        selected_provider_id: str = "",
        selected_provider_label: str = "",
        selected_provider_api: str = "",
        selected_provider_endpoint: str = "",
        selected_provider_model: str = "",
        providers: list[ModelRegistryProvider] | None = None,
    ) -> ModelExecutionPlan:
        provider_id = selected_provider_id.strip()
        api = selected_provider_api.strip().lower()
        endpoint = selected_provider_endpoint.strip().rstrip("/")
        model = selected_provider_model.strip()
        if not any((provider_id, api, endpoint, model)):
            return plan

        provider_records = providers or []
        provider = self._resolve_selected_provider(
            provider_id=provider_id,
            api=api,
            endpoint=endpoint,
            model=model,
            providers=provider_records,
        )
        if provider is not None:
            provider_id = provider.id
            api = provider.api.strip().lower() or api
            endpoint = provider.endpoint.strip().rstrip("/") or endpoint
            model = model or provider.model_name.strip()
            selected_provider_label = selected_provider_label.strip() or provider.label
        else:
            api = self._selected_provider_api(provider_id, api)

        if not model:
            return plan

        label = selected_provider_label.strip() or (provider.label if provider is not None else provider_label(api, endpoint))
        endpoint_is_local = provider.local if provider is not None else is_local_endpoint(endpoint)
        selected_attempt = ModelAttemptInfo(
            attempt=1,
            role=plan.primary.role if plan.primary else "chat",
            provider_id=provider_id or f"{api or 'local'}:selected",
            provider_label=label,
            provider_api=api or "openai-compatible",
            model=model,
            endpoint=endpoint,
            privacy_mode="local-only" if endpoint_is_local else (plan.primary.privacy_mode if plan.primary else "cloud-allowed"),
            status="planned",
            reason="Selected in the Aegis provider stack for this chat turn.",
            retryable=provider.configured if provider is not None else True,
            metadata={
                "candidate_id": "ui:selected-provider",
                "candidate_source": "selected-provider",
                "selected_provider_override": True,
                "selected_provider_id": selected_provider_id.strip(),
                "selected_provider_label": selected_provider_label.strip(),
                "selected_provider_api": selected_provider_api.strip(),
                "selected_provider_endpoint": selected_provider_endpoint.strip(),
                "selected_provider_model": selected_provider_model.strip(),
                "registry_resolved": provider is not None,
                "provider_capabilities": self._provider_capabilities(provider),
                "provider_roles": self._provider_roles(provider),
                "cost_tier": provider.cost_tier if provider else "low" if endpoint_is_local else "unknown",
                "context_window": provider.context_window if provider else None,
                "rate_limit_rpm": provider.rate_limit_rpm if provider else None,
                "input_cost_per_million": provider.input_cost_per_million if provider else None,
                "output_cost_per_million": provider.output_cost_per_million if provider else None,
            },
        )
        selected_key = self._attempt_identity(selected_attempt)
        attempts = [
            selected_attempt,
            *[
                attempt
                for attempt in plan.attempts
                if self._attempt_identity(attempt) != selected_key
            ],
        ]
        return ModelExecutionPlan(
            attempts=[
                attempt.model_copy(update={"attempt": index})
                for index, attempt in enumerate(attempts, start=1)
            ]
        )

    def _resolve_selected_provider(
        self,
        *,
        provider_id: str,
        api: str,
        endpoint: str,
        model: str,
        providers: list[ModelRegistryProvider],
    ) -> ModelRegistryProvider | None:
        enabled = [provider for provider in providers if provider.enabled]
        provider_id_lower = provider_id.strip().lower()
        api_lower = api.strip().lower()
        endpoint_lower = endpoint.strip().rstrip("/").lower()
        model_lower = model.strip().lower()

        if provider_id_lower:
            for provider in enabled:
                if provider.id.strip().lower() == provider_id_lower:
                    return provider

        for provider in enabled:
            provider_api = provider.api.strip().lower()
            provider_endpoint = provider.endpoint.strip().rstrip("/").lower()
            provider_matches_model = self._provider_matches_model(provider, model_lower) if model_lower else True
            if not provider_matches_model:
                continue
            if api_lower and provider_api == api_lower:
                if not endpoint_lower or provider_endpoint == endpoint_lower:
                    return provider
            if provider_id_lower == "ollama" and provider_api == "ollama":
                return provider
            if provider_id_lower == "local_openai_compatible" and api_family(provider_api) == "openai" and provider.local:
                if not endpoint_lower or provider_endpoint == endpoint_lower:
                    return provider

        for provider in enabled:
            provider_api = provider.api.strip().lower()
            if provider_id_lower == "ollama" and provider_api == "ollama" and provider.configured:
                return provider
            if provider_id_lower == "local_openai_compatible" and api_family(provider_api) == "openai" and provider.local and provider.configured:
                return provider
        return None

    def _selected_provider_api(self, provider_id: str, api: str) -> str:
        if api:
            return api
        lowered = provider_id.strip().lower()
        if lowered == "ollama":
            return "ollama"
        if lowered in {"local_openai_compatible", "local-openai-compatible"}:
            return "openai-compatible"
        if lowered.startswith("ollama:"):
            return "ollama"
        if ":" in lowered:
            return lowered.split(":", 1)[0] or "openai-compatible"
        return "openai-compatible"

    def _attempt_identity(self, attempt: ModelAttemptInfo) -> tuple[str, str, str]:
        return (
            attempt.provider_id.strip().lower(),
            attempt.provider_api.strip().lower(),
            attempt.model.strip().lower(),
        )

    def _resolve_provider(
        self,
        candidate: RouteCandidate,
        providers: list[ModelRegistryProvider],
        privacy_mode: str,
        benchmark_scores: dict[str, ModelBenchmarkProviderScore],
        role_policies: dict[str, ModelRegistryRole],
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
        route_profile: dict | None = None,
    ) -> ModelRegistryProvider | None:
        eligible = self._eligible_providers(providers, privacy_mode)
        role_provider = self._resolve_role_provider(
            candidate.role,
            providers,
            privacy_mode,
            candidate.required_capabilities,
            benchmark_scores=benchmark_scores,
            role_policies=role_policies,
            route_health=route_health,
            route_profile=route_profile,
        )
        if role_provider is not None:
            return role_provider

        exact_id = self._provider_id(candidate.provider_hint)
        for provider in eligible:
            if provider.id.lower() == exact_id or provider.label.lower() == candidate.provider_hint.lower():
                return provider
        return None

    def _resolve_role_provider(
        self,
        role: str,
        providers: list[ModelRegistryProvider],
        privacy_mode: str,
        required_capabilities: list[str] | None = None,
        benchmark_scores: dict[str, ModelBenchmarkProviderScore] | None = None,
        role_policies: dict[str, ModelRegistryRole] | None = None,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo] | None = None,
        route_profile: dict | None = None,
    ) -> ModelRegistryProvider | None:
        eligible = self._eligible_providers(providers, privacy_mode)
        role_lower = role.strip().lower()
        policy = (role_policies or {}).get(role_lower)
        required = self._normalize_capabilities(required_capabilities or [])
        if policy is not None:
            required |= self._normalize_capabilities(policy.required_capabilities)
        benchmark_scores = benchmark_scores or {}
        route_health = route_health or {}

        configured_matches: list[ModelRegistryProvider] = []
        planned_matches: list[ModelRegistryProvider] = []
        meaningful_required = required - GENERIC_CAPABILITIES
        for provider in eligible:
            roles = self._normalize_capabilities(provider.roles)
            capabilities = self._normalize_capabilities(provider.capabilities)
            role_matches = role_lower in roles or role_lower in capabilities
            missing_required = self._missing_required_capabilities(provider, meaningful_required)
            if missing_required:
                continue
            capability_matches = bool(meaningful_required)
            if not role_matches and not capability_matches:
                continue
            if provider.configured:
                configured_matches.append(provider)
            else:
                planned_matches.append(provider)

        if configured_matches:
            preferred = self._preferred_role_provider(
                role_lower,
                configured_matches,
                role_policies or {},
                route_health,
                meaningful_required,
            )
            if preferred is not None:
                return preferred
            return sorted(
                configured_matches,
                key=lambda provider: self._provider_score(provider, role_lower, required, privacy_mode, benchmark_scores, route_health, route_profile),
                reverse=True,
            )[0]
        if planned_matches:
            preferred = self._preferred_role_provider(
                role_lower,
                planned_matches,
                role_policies or {},
                route_health,
                meaningful_required,
            )
            if preferred is not None:
                return preferred
            return sorted(
                planned_matches,
                key=lambda provider: self._provider_score(provider, role_lower, required, privacy_mode, benchmark_scores, route_health, route_profile),
                reverse=True,
            )[0]
        return None

    def _preferred_role_provider(
        self,
        role: str,
        providers: list[ModelRegistryProvider],
        role_policies: dict[str, ModelRegistryRole],
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
        required_capabilities: set[str],
    ) -> ModelRegistryProvider | None:
        policy = role_policies.get(role)
        if policy is None:
            return None
        primary = policy.primary_model.strip().lower()
        if primary:
            for provider in providers:
                if (
                    self._provider_matches_model(provider, primary)
                    and not self._provider_in_cooldown(provider, role, route_health)
                    and not self._missing_required_capabilities(provider, required_capabilities)
                ):
                    return provider
        for model_name in policy.fallback_models:
            wanted = model_name.strip().lower()
            if not wanted:
                continue
            for provider in providers:
                if (
                    self._provider_matches_model(provider, wanted)
                    and not self._provider_in_cooldown(provider, role, route_health)
                    and not self._missing_required_capabilities(provider, required_capabilities)
                ):
                    return provider
        return None

    def _provider_matches_model(self, provider: ModelRegistryProvider, wanted: str) -> bool:
        if not wanted:
            return False
        names = [provider.model_name, *provider.model_aliases, provider.id, provider.label]
        for name in names:
            normalized = name.strip().lower()
            if normalized and (normalized == wanted or wanted in normalized):
                return True
        return False

    def _eligible_providers(self, providers: list[ModelRegistryProvider], privacy_mode: str) -> list[ModelRegistryProvider]:
        eligible = [provider for provider in providers if provider.enabled]
        if privacy_mode == "local-only":
            eligible = [provider for provider in eligible if provider.local]
        return eligible

    def _provider_score(
        self,
        provider: ModelRegistryProvider,
        role: str,
        required: set[str],
        privacy_mode: str,
        benchmark_scores: dict[str, ModelBenchmarkProviderScore] | None = None,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo] | None = None,
        route_profile: dict | None = None,
    ) -> float:
        model = provider.model_name.lower()
        provider_id = provider.id.lower()
        label = provider.label.lower()
        text = f"{provider_id} {label} {model}"
        roles = self._normalize_capabilities(provider.roles)
        capabilities = self._normalize_capabilities(provider.capabilities)

        score = 1000 if provider.configured else 0
        if role in roles:
            score += 320
        if role in capabilities:
            score += 220
        meaningful_required = required - GENERIC_CAPABILITIES
        missing_required = self._missing_required_capabilities(provider, meaningful_required)
        if missing_required:
            score -= 10000 + (1000 * len(missing_required))
        score += 160 * len(meaningful_required & (capabilities | roles))
        if provider.context_window:
            score += min(provider.context_window // 10_000, 80)

        if privacy_mode == "local-first" and provider.local:
            score += 260
        elif privacy_mode == "cloud-allowed" and not provider.local:
            score += 140

        if role in {"code", "debug", "refactor"}:
            score += self._keyword_score(
                text,
                {
                    "codex": 760,
                    "qwen3-coder:30b": 740,
                    "qwen3-coder-30b": 740,
                    "qwen2.5-coder:32b": 720,
                    "qwen2.5-coder-32b": 720,
                    "qwen2.5-coder:14b": 600,
                    "qwen2.5-coder-14b": 600,
                    "qwen2.5-coder:7b": 480,
                    "qwen2.5-coder-7b": 480,
                    "qwen2.5-coder:3b": 360,
                    "starcoder": 330,
                    "granite-code": 320,
                    "devstral": 310,
                    "deepseek-coder-v2": 308,
                    "codellama": 305,
                    "codegemma": 300,
                    "deepseek": 260,
                    "claude": 240,
                    "gpt-5": 220,
                },
            )
        elif role in {"review", "judge"}:
            score += self._keyword_score(
                text,
                {
                    "claude": 620,
                    "gpt-5.5": 600,
                    "gpt-5.4": 540,
                    "phi4": 500,
                    "qwen3": 460,
                    "deepseek-r1": 420,
                    "qwen2.5-coder": 360,
                },
            )
        elif role in {"reasoning", "architecture", "security"}:
            score += self._keyword_score(
                text,
                {
                    "gpt-5.5": 720,
                    "claude-opus": 700,
                    "claude-sonnet": 640,
                    "qwen3:30b": 650,
                    "qwen3-30b": 650,
                    "qwq:32b": 640,
                    "qwq-32b": 640,
                    "qwen3:14b": 620,
                    "qwen3-14b": 620,
                    "deepseek-r1:14b": 600,
                    "deepseek-r1-14b": 600,
                    "qwen3:8b": 520,
                    "deepseek-r1:8b": 500,
                    "gpt-oss": 480,
                    "gemma3:27b": 470,
                    "gemma3-27b": 470,
                    "phi4": 460,
                    "qwen3:4b": 380,
                },
            )
        elif role == "research":
            score += self._keyword_score(
                text,
                {
                    "sonar-pro": 760,
                    "sonar": 620,
                    "perplexity": 560,
                    "openrouter": 360,
                    "gpt-5": 260,
                },
            )
        elif role in {"image", "creative"}:
            score += self._keyword_score(text, {"gpt-image": 760, "openrouter": 380})
        elif role == "vision":
            score += self._keyword_score(
                text,
                {
                    "llama3.2-vision:90b": 840,
                    "llama3.2-vision-90b": 840,
                    "llava:34b": 720,
                    "llava-34b": 720,
                    "llama3.2-vision:11b": 640,
                    "llama3.2-vision-11b": 640,
                    "llava:13b": 580,
                    "llava-13b": 580,
                    "gemma3:27b": 540,
                    "gemma3-27b": 540,
                    "gemini": 500,
                    "claude": 460,
                    "gpt-5": 430,
                },
            )
        elif role in {"audio", "voice", "realtime"}:
            score += self._keyword_score(text, {"realtime": 760, "audio": 520})
        else:
            score += self._keyword_score(
                text,
                {
                    "llama3.2:3b": 760,
                    "llama3.2-3b": 760,
                    "llama3-2-3b": 900,
                    "llama3.1:8b": 710,
                    "llama3.1-8b": 710,
                    "llama3-1-8b": 760,
                    "qwen2.5:14b": 650,
                    "qwen2.5-14b": 650,
                    "gemma3:12b": 620,
                    "gemma3-12b": 620,
                    "mistral:7b": 610,
                    "mistral-7b": 610,
                    "gpt-5.4-mini": 580,
                    "qwen2.5:7b": 540,
                    "llama3.2:1b": 480,
                    "qwen2.5:32b": 420,
                    "qwen2.5-32b": 420,
                    "gemma3:27b": 360,
                    "gemma3-27b": 360,
                    "llama3.3": 340,
                    "gemma3": 330,
                    "qwen2.5-coder": -180,
                    "vision": -260,
                    "llava": -320,
                    "70b": -380,
                    "72b": -380,
                    "90b": -420,
                },
            )

        if "embeddings" in capabilities and role not in {"embeddings", "rag"}:
            score -= 5000
        score += self._benchmark_score(provider, role, benchmark_scores or {})
        score -= self._route_health_penalty(provider, role, route_health or {})
        score += self._route_profile_score(provider, route_profile or {})
        return score

    def _route_profile_score(self, provider: ModelRegistryProvider, route_profile: dict) -> float:
        if not route_profile:
            return 0.0

        values = [
            provider.id,
            provider.label,
            provider.model_name,
            provider.notes,
            *provider.model_aliases,
            *provider.roles,
            *provider.capabilities,
        ]
        text = " ".join(value for value in values if value).lower()
        keywords = route_profile.get("stack_keywords")
        if not isinstance(keywords, list):
            keywords = []
        cleaned_keywords = [str(item).strip().lower() for item in keywords if str(item).strip()]
        if not cleaned_keywords:
            return 0.0

        score = 0.0
        for keyword in cleaned_keywords:
            if keyword in text:
                score += 42.0

        category = str(route_profile.get("category") or "").strip().lower()
        category_weights = {
            "desktop": {"desktop": 90.0, "tauri": 90.0, "electron": 90.0, "rust": 45.0, "cpp": 45.0},
            "mobile": {"mobile": 90.0, "expo": 90.0, "react-native": 90.0, "android": 45.0, "ios": 45.0},
            "api": {"api": 90.0, "backend": 70.0, "server": 60.0, "fastapi": 45.0, "express": 45.0},
            "web": {"web": 70.0, "frontend": 70.0, "react": 45.0, "nextjs": 45.0, "vite": 45.0},
            "data": {"data": 90.0, "python": 45.0, "pandas": 45.0, "analytics": 45.0},
            "systems": {"systems": 90.0, "cli": 70.0, "rust": 45.0, "go": 45.0, "cpp": 45.0},
            "database": {"database": 100.0, "sql": 80.0, "migration": 70.0, "schema": 70.0, "postgres": 50.0},
            "native": {"native": 100.0, "cpp": 80.0, "cmake": 70.0, "win32": 70.0, "dll": 60.0, "exe": 60.0},
            "driver": {"kernel": 100.0, "driver": 100.0, "firmware": 80.0, "security": 70.0, "cpp": 50.0},
            "reverse-engineering": {"reverse": 100.0, "binary": 90.0, "security": 70.0, "analysis": 60.0, "pe": 50.0},
        }
        for keyword, weight in category_weights.get(category, {}).items():
            if keyword in text:
                score += weight
        return score

    def _route_profile_metadata(self, route_profile: dict) -> dict:
        if not route_profile:
            return {}

        def string_list(key: str, limit: int = 12) -> list[str]:
            values = route_profile.get(key)
            if not isinstance(values, list):
                return []
            return [str(item).strip() for item in values if str(item).strip()][:limit]

        return {
            "route_profile_id": str(route_profile.get("id") or "").strip(),
            "route_profile_label": str(route_profile.get("label") or "").strip(),
            "route_profile_category": str(route_profile.get("category") or "").strip(),
            "route_profile_reason": str(route_profile.get("reason") or "").strip(),
            "route_profile_preferred_roles": string_list("preferred_roles", 8),
            "route_profile_stack_keywords": string_list("stack_keywords", 16),
            "route_profile_focus_paths": string_list("focus_paths", 16),
        }

    def _normalize_capabilities(self, values: list[str] | tuple[str, ...] | set[str]) -> set[str]:
        return {
            normalize_capability(str(item))
            for item in values
            if str(item).strip()
        }

    def _missing_required_capabilities(
        self,
        provider: ModelRegistryProvider | None,
        required: set[str],
    ) -> set[str]:
        if provider is None or not required:
            return set()
        available = self._normalize_capabilities(provider.capabilities) | self._normalize_capabilities(provider.roles)
        return {capability for capability in required if capability not in available}

    def _provider_capabilities(self, provider: ModelRegistryProvider | None) -> list[str]:
        if provider is None:
            return []
        return sorted(self._normalize_capabilities(provider.capabilities))

    def _provider_roles(self, provider: ModelRegistryProvider | None) -> list[str]:
        if provider is None:
            return []
        return sorted(self._normalize_capabilities(provider.roles))

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

    def _route_health_signal(
        self,
        provider: ModelRegistryProvider | None,
        role: str,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> ModelRouteHealthInfo | None:
        if provider is None:
            return None
        provider_id = provider.id.strip().lower()
        model = provider.model_name.strip().lower()
        role = role.strip().lower()
        for key in (
            (provider_id, model, role),
            (provider_id, "", role),
            (provider_id, model, ""),
            (provider_id, "", ""),
        ):
            signal = route_health.get(key)
            if signal is not None:
                return signal
        return None

    def _route_health_penalty(
        self,
        provider: ModelRegistryProvider,
        role: str,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> float:
        signal = self._route_health_signal(provider, role, route_health)
        if signal is None:
            return 0.0
        return max(0.0, float(signal.penalty or 0.0))

    def _provider_in_cooldown(
        self,
        provider: ModelRegistryProvider,
        role: str,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> bool:
        signal = self._route_health_signal(provider, role, route_health)
        return bool(signal and signal.cooldown)

    def _route_health_metadata(
        self,
        provider: ModelRegistryProvider | None,
        role: str,
        route_health: dict[tuple[str, str, str], ModelRouteHealthInfo],
    ) -> dict:
        signal = self._route_health_signal(provider, role, route_health)
        if signal is None:
            return {}
        return {
            "route_health_attempts": signal.attempts,
            "route_health_terminal_attempts": signal.terminal_attempts,
            "route_health_success_rate": signal.success_rate,
            "route_health_failure_rate": signal.failure_rate,
            "route_health_average_latency_ms": signal.average_latency_ms,
            "route_health_penalty": signal.penalty,
            "route_health_cooldown": signal.cooldown,
            "route_health_latest_error": signal.latest_error,
            "route_health_recommendation": signal.recommendation,
        }

    def _benchmark_score(
        self,
        provider: ModelRegistryProvider,
        role: str,
        benchmark_scores: dict[str, ModelBenchmarkProviderScore],
    ) -> float:
        benchmark = benchmark_scores.get(provider.id)
        if benchmark is None:
            return 0.0

        suite_score = self._benchmark_suite_score(benchmark, role)
        score = benchmark.overall_score * 300.0
        if suite_score is not None:
            score += suite_score * 1400.0
        if benchmark.avg_latency_ms is not None and benchmark.avg_latency_ms > 0:
            score += max(0.0, min(180.0, (45000.0 - benchmark.avg_latency_ms) / 250.0))
        return score

    def _benchmark_suite_score(self, benchmark: ModelBenchmarkProviderScore, role: str) -> float | None:
        suite = self._benchmark_suite_for_role(role)
        if suite == "code":
            return benchmark.code_score
        if suite == "reasoning":
            return benchmark.reasoning_score
        return benchmark.chat_score

    def _benchmark_suite_for_role(self, role: str) -> str:
        role = role.strip().lower()
        if role in {"code", "debug", "refactor", "review", "security"}:
            return "code"
        if role in {"reasoning", "architecture", "judge"}:
            return "reasoning"
        return "chat"

    def _benchmark_metadata(
        self,
        provider: ModelRegistryProvider | None,
        role: str,
        benchmark_scores: dict[str, ModelBenchmarkProviderScore],
    ) -> dict:
        if provider is None:
            return {}
        benchmark = benchmark_scores.get(provider.id)
        if benchmark is None:
            return {}
        suite_id = self._benchmark_suite_for_role(role)
        suite_score = self._benchmark_suite_score(benchmark, role)
        return {
            "benchmark_suite": suite_id,
            "benchmark_suite_score": suite_score,
            "benchmark_overall_score": benchmark.overall_score,
            "benchmark_avg_latency_ms": benchmark.avg_latency_ms,
            "benchmark_run_count": benchmark.run_count,
            "benchmark_latest_at": benchmark.latest_at,
            "benchmark_recommendation": benchmark.recommendation,
        }

    def _role_policy_metadata(self, role: str, role_policies: dict[str, ModelRegistryRole]) -> dict:
        policy = role_policies.get(role.strip().lower())
        if policy is None:
            return {}
        return {
            "registry_role_primary_model": policy.primary_model,
            "registry_role_fallback_models": policy.fallback_models,
            "registry_role_privacy_mode": policy.privacy_mode,
            "registry_role_status": policy.status,
        }

    def _keyword_score(self, text: str, weights: dict[str, int]) -> int:
        score = 0
        for keyword, weight in weights.items():
            if keyword in text:
                score += weight
        return score

    def _provider_id(self, provider_hint: str) -> str:
        compact = provider_hint.strip().lower().replace(" ", "-")
        return compact or "provider:unknown"

    def _provider_api(self, provider_hint: str) -> str:
        lowered = provider_hint.lower()
        if lowered.startswith("ollama:"):
            return "ollama"
        if "claude" in lowered or "anthropic" in lowered:
            return "anthropic"
        if "perplexity" in lowered:
            return "perplexity"
        if "openrouter" in lowered:
            return "openrouter"
        if "openai" in lowered:
            return "openai"
        if ":" in provider_hint:
            return provider_hint.split(":", 1)[0].strip() or "router"
        return "router"

    def _model_hint(self, provider_hint: str) -> str:
        if ":" not in provider_hint:
            return ""
        return provider_hint.split(":", 1)[1].strip()

    def _fallback_candidate_id(self, role: str) -> str:
        compact = role.strip().lower().replace(" ", "-") or "fallback"
        return f"fallback:{compact}"
