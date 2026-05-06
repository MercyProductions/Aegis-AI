from __future__ import annotations

import re

from dataclasses import dataclass, field

from .schemas import ModeName
from .settings import Settings


@dataclass(frozen=True)
class RouteCandidate:
    role: str
    provider_hint: str
    required_capabilities: list[str]
    privacy_mode: str
    reason: str
    confidence: float
    candidate_id: str = ""


@dataclass(frozen=True)
class RoutingDecision:
    task_role: str
    privacy_mode: str
    candidates: list[RouteCandidate] = field(default_factory=list)
    fallback_roles: list[str] = field(default_factory=list)
    requires_tools: bool = False
    requires_workspace: bool = False
    summary: str = ""
    confidence: float = 0.5

    def to_event_payload(self) -> dict:
        return {
            "task_role": self.task_role,
            "privacy_mode": self.privacy_mode,
            "fallback_roles": self.fallback_roles,
            "requires_tools": self.requires_tools,
            "requires_workspace": self.requires_workspace,
            "summary": self.summary,
            "confidence": self.confidence,
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "role": candidate.role,
                    "provider_hint": candidate.provider_hint,
                    "required_capabilities": candidate.required_capabilities,
                    "privacy_mode": candidate.privacy_mode,
                    "reason": candidate.reason,
                    "confidence": candidate.confidence,
                }
                for candidate in self.candidates
            ],
        }

    def to_prompt_context(self) -> str:
        candidates = "\n".join(
            f"- {candidate.candidate_id or candidate.role}: {candidate.provider_hint} ({candidate.privacy_mode}, "
            f"{', '.join(candidate.required_capabilities) or 'no special capability'}): {candidate.reason}"
            for candidate in self.candidates
        )
        return "\n".join(
            [
                f"Task role: {self.task_role}",
                f"Privacy mode: {self.privacy_mode}",
                f"Requires workspace tools: {'yes' if self.requires_workspace else 'no'}",
                f"Requires execution tools: {'yes' if self.requires_tools else 'no'}",
                f"Fallback roles: {', '.join(self.fallback_roles) or '(none)'}",
                "Candidate routes:",
                candidates or "- local fallback: use deterministic response path",
            ]
        )


class ModelRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def recommend(self, message: str, mode: ModeName, *, has_workspace_context: bool) -> RoutingDecision:
        lowered = message.lower()
        task_role = self._classify_role(lowered, mode)
        privacy_mode = self._privacy_mode(lowered, has_workspace_context)
        requires_tools = self._requires_tools(lowered, mode)
        requires_workspace = has_workspace_context or task_role in {"code", "review", "debug", "refactor"}
        candidates = self._candidates(task_role, privacy_mode)
        fallback_roles = self._fallback_roles(task_role, privacy_mode)
        summary = (
            f"Route as {task_role} with {privacy_mode} privacy; "
            f"{len(candidates)} candidate lane(s), fallback: {', '.join(fallback_roles) or 'none'}."
        )
        return RoutingDecision(
            task_role=task_role,
            privacy_mode=privacy_mode,
            candidates=candidates,
            fallback_roles=fallback_roles,
            requires_tools=requires_tools,
            requires_workspace=requires_workspace,
            summary=summary,
            confidence=0.82 if candidates else 0.58,
        )

    def _classify_role(self, lowered: str, mode: ModeName) -> str:
        if "workspace readiness continuation context" in lowered or "autopilot continuation context" in lowered:
            if any(term in lowered for term in ("needs_repair", "repair", "failed", "failure", "error", "debug")):
                return "debug"
            return "code"
        if any(term in lowered for term in ("security", "permission", "sandbox", "auth", "secret")):
            return "security"
        if any(term in lowered for term in ("visual studio", "vcxproj", ".sln", " solution file", "msbuild")):
            return "code"
        if any(term in lowered for term in ("bug", "error", "traceback", "failing", "fix", "debug")):
            return "debug"
        if any(term in lowered for term in ("reverse engineer", "reverse-engineer", "reverse engineering", "disassemble", "decompile", "binary analysis")):
            return "review"
        if any(term in lowered for term in ("review", "audit", "risk", "regression")) or mode == "review":
            return "review"
        if any(term in lowered for term in ("plan", "architecture", "roadmap", "design", "todo")):
            return "architecture"
        if self._looks_like_code_work(lowered):
            return "code"
        if self._looks_like_external_research(lowered):
            return "research"
        if any(term in lowered for term in ("screenshot", "photo", "picture", "vision", "analyze image")) or (
            "visual" in lowered and "visual studio" not in lowered
        ):
            return "vision"
        if any(term in lowered for term in ("image", "video", "audio", "music", "creative", "thumbnail")):
            return "creative"
        if any(term in lowered for term in self._code_terms()):
            return "code"
        return "chat"

    def _looks_like_code_work(self, lowered: str) -> bool:
        action_terms = (
            "create",
            "build",
            "implement",
            "complete",
            "finish",
            "develop",
            "add",
            "edit",
            "refactor",
            "scaffold",
            "generate",
            "write",
            "set up",
            "setup",
            "refine",
            "improve",
            "optimize",
            "repair",
            "debug",
            "fix",
            "work on",
            "clean up",
            "cleanup",
            "polish",
            "modernize",
            "enhance",
            "continue",
        )
        code_context = any(term in lowered for term in self._code_terms()) or bool(
            re.search(r"\bsource\s+(?:code|file|files|tree|layout|root|folder|map)\b", lowered)
        )
        if "mission continuity anchor" in lowered and "original user mission" in lowered and code_context:
            return True
        return any(term in lowered for term in action_terms) and code_context

    def _looks_like_external_research(self, lowered: str) -> bool:
        if any(
            term in lowered
            for term in (
                "search",
                "research",
                "latest",
                "citation",
                "citations",
                "cite",
                "sources",
                "web search",
                "search web",
                "search the web",
                "look up",
            )
        ):
            return True
        if re.search(r"\bsource\b", lowered) and not re.search(
            r"\bsource\s+(?:code|file|files|tree|layout|root|folder|map)\b",
            lowered,
        ):
            return True
        return False

    def _privacy_mode(self, lowered: str, has_workspace_context: bool) -> str:
        if any(term in lowered for term in ("local only", "private", "secret", ".env", "credential", "no cloud")):
            return "local-only"
        latest_source_context = bool(
            re.search(r"\blatest\s+source\s+(?:code|file|files|tree|layout|root|folder|map)\b", lowered)
        )
        if any(term in lowered for term in ("web", "research", "external api", "cloud")) or (
            "latest" in lowered and not latest_source_context
        ):
            return "cloud-allowed"
        return "local-first" if has_workspace_context else "hybrid"

    def _requires_tools(self, lowered: str, mode: ModeName) -> bool:
        return any(
            term in lowered
            for term in (
                "read file",
                "write file",
                "edit",
                "patch",
                "run command",
                "install",
                "search project",
                "validate",
            )
        )

    def _code_terms(self) -> tuple[str, ...]:
        return (
            "code",
            "implement",
            "build",
            "create",
            "refactor",
            "edit",
            "file",
            "script",
            "function",
            "component",
            "api",
            "bug",
            "compile",
            "test",
            "workspace",
            "project",
            "repo",
            "repository",
            "path",
            "folder",
            "database",
            "sql",
            "migration",
            "schema",
            "kernel",
            "driver",
            "firmware",
            "dll",
            "exe",
            "binary",
            "native",
            "disassemble",
            "decompile",
            "reverse engineer",
            "reverse-engineer",
            "reverse engineering",
        )

    def _candidates(self, task_role: str, privacy_mode: str) -> list[RouteCandidate]:
        local_candidate = RouteCandidate(
            role=task_role,
            provider_hint=self._active_provider_hint(),
            required_capabilities=self._capabilities_for(task_role),
            privacy_mode="local-first" if privacy_mode != "cloud-allowed" else "hybrid",
            reason="Use the configured primary model before escalating.",
            confidence=0.74,
            candidate_id=self._candidate_id("primary", task_role),
        )
        judge_candidate = RouteCandidate(
            role="judge",
            provider_hint="local judge or strongest configured reasoning model",
            required_capabilities=["chat", "structured_json"],
            privacy_mode="local-first",
            reason="Score risky plans, large edits, and multi-provider answers.",
            confidence=0.62,
            candidate_id=self._candidate_id("judge", "judge"),
        )
        if privacy_mode == "local-only":
            return [local_candidate, judge_candidate]

        cloud_hint = {
            "research": "Perplexity, OpenAI, or OpenRouter research lane",
            "architecture": "OpenAI or Claude reasoning lane",
            "code": "OpenAI, Claude, or local coder lane",
            "review": "Claude, OpenAI, or judge lane",
            "debug": "OpenAI, Claude, or local coder lane",
            "creative": "OpenAI or OpenRouter creative lane",
            "vision": "local vision model, OpenAI, Claude, or Gemini vision lane",
            "security": "local-first security reviewer plus cloud reasoning only with consent",
            "chat": "fast configured chat lane",
        }.get(task_role, "configured specialist lane")
        specialist = RouteCandidate(
            role=task_role,
            provider_hint=cloud_hint,
            required_capabilities=self._capabilities_for(task_role),
            privacy_mode=privacy_mode,
            reason="Escalate when the local model lacks capability, quality, or freshness.",
            confidence=0.78,
            candidate_id=self._candidate_id("specialist", task_role),
        )
        return [local_candidate, specialist, judge_candidate]

    def _fallback_roles(self, task_role: str, privacy_mode: str) -> list[str]:
        if privacy_mode == "local-only":
            return [task_role, "judge", "fallback"]
        if task_role == "research":
            return ["research", "reasoning", "chat", "fallback"]
        if task_role in {"code", "debug", "review"}:
            return [task_role, "reasoning", "judge", "fallback"]
        if task_role == "creative":
            return ["creative", "reasoning", "fallback"]
        if task_role == "vision":
            return ["vision", "reasoning", "chat", "fallback"]
        return [task_role, "chat", "fallback"]

    def _capabilities_for(self, task_role: str) -> list[str]:
        capabilities = {
            "architecture": ["chat", "reasoning", "structured_json"],
            "chat": ["chat"],
            "code": ["chat", "code", "structured_json"],
            "debug": ["chat", "code", "structured_json"],
            "review": ["chat", "code", "judge"],
            "research": ["chat", "research", "search"],
            "creative": ["chat", "creative"],
            "vision": ["chat", "vision"],
            "security": ["chat", "code", "judge"],
        }
        return capabilities.get(task_role, ["chat"])

    def _active_provider_hint(self) -> str:
        api = self.settings.aegis_model_api.strip() or "ollama"
        model = self.settings.aegis_model_name.strip() or "unconfigured"
        return f"{api}:{model}"

    def _candidate_id(self, lane: str, role: str) -> str:
        lane_slug = self._slug(lane) or "candidate"
        role_slug = self._slug(role) or "route"
        return f"{lane_slug}:{role_slug}"

    def _slug(self, value: str) -> str:
        cleaned = []
        previous_dash = False
        for char in value.strip().lower():
            if char.isalnum():
                cleaned.append(char)
                previous_dash = False
            elif not previous_dash:
                cleaned.append("-")
                previous_dash = True
        return "".join(cleaned).strip("-")
