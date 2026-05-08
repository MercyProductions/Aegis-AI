from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import ChatMessage, FixMemoryEntry, ProjectMemoryEntry, WorkspaceFile
from .settings import Settings
from .task_planner import TaskPlan


CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ContextBudgetProfile:
    intent: str
    route_role: str
    strategy: str
    max_context_tokens: int
    max_context_files: int
    max_file_chars: int
    max_history_turns: int
    max_fix_memory_items: int
    max_project_memory_items: int
    reserve_response_tokens: int
    notes: list[str] = field(default_factory=list)

    @property
    def max_context_chars(self) -> int:
        return max(0, self.max_context_tokens * CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ContextBudgetItem:
    kind: str
    ref: str
    estimated_tokens: int
    included: bool
    reason: str

    def to_event_payload(self) -> dict:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "estimated_tokens": self.estimated_tokens,
            "included": self.included,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ContextBudgetResult:
    profile: ContextBudgetProfile
    privacy_mode: str = "local-first"
    context_files: list[WorkspaceFile] = field(default_factory=list)
    memory_hits: list[FixMemoryEntry] = field(default_factory=list)
    project_memory_hits: list[ProjectMemoryEntry] = field(default_factory=list)
    estimated_context_tokens: int = 0
    estimated_file_tokens: int = 0
    workspace_file_count: int = 0
    omitted_file_count: int = 0
    omitted_memory_count: int = 0
    omitted_project_memory_count: int = 0
    items: list[ContextBudgetItem] = field(default_factory=list)

    @property
    def max_context_chars(self) -> int:
        return max(0, self.estimated_file_tokens * CHARS_PER_TOKEN)

    @property
    def max_file_chars(self) -> int:
        return self.profile.max_file_chars

    @property
    def reserve_response_tokens(self) -> int:
        return self.profile.reserve_response_tokens

    def to_event_payload(self) -> dict:
        return {
            "intent": self.profile.intent,
            "route_role": self.profile.route_role,
            "strategy": self.profile.strategy,
            "privacy_mode": self.privacy_mode,
            "max_context_tokens": self.profile.max_context_tokens,
            "estimated_context_tokens": self.estimated_context_tokens,
            "estimated_file_tokens": self.estimated_file_tokens,
            "reserve_response_tokens": self.profile.reserve_response_tokens,
            "max_context_files": self.profile.max_context_files,
            "selected_file_count": len(self.context_files),
            "workspace_file_count": self.workspace_file_count,
            "selected_memory_count": len(self.memory_hits),
            "selected_project_memory_count": len(self.project_memory_hits),
            "omitted_file_count": self.omitted_file_count,
            "omitted_memory_count": self.omitted_memory_count,
            "omitted_project_memory_count": self.omitted_project_memory_count,
            "max_file_chars": self.profile.max_file_chars,
            "max_history_turns": self.profile.max_history_turns,
            "notes": self.profile.notes,
            "items": [item.to_event_payload() for item in self.items[:40]],
        }


class ContextBudgetManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def profile_for(self, task_plan: TaskPlan, provider_context_window: int | None = None) -> ContextBudgetProfile:
        route_role = task_plan.routing.task_role if task_plan.routing else "chat"
        profile = self._base_profile(task_plan.intent, route_role)
        profile = self._scale_profile(profile, task_plan)
        if provider_context_window and provider_context_window > 0:
            model_context_budget = max(1600, int(provider_context_window * 0.62))
            capped_tokens = min(profile.max_context_tokens, model_context_budget)
            if capped_tokens != profile.max_context_tokens:
                profile = ContextBudgetProfile(
                    intent=profile.intent,
                    route_role=profile.route_role,
                    strategy=profile.strategy,
                    max_context_tokens=capped_tokens,
                    max_context_files=profile.max_context_files,
                    max_file_chars=min(profile.max_file_chars, capped_tokens * CHARS_PER_TOKEN),
                    max_history_turns=profile.max_history_turns,
                    max_fix_memory_items=profile.max_fix_memory_items,
                    max_project_memory_items=profile.max_project_memory_items,
                    reserve_response_tokens=profile.reserve_response_tokens,
                    notes=[
                        *profile.notes,
                        f"Capped to {capped_tokens} context tokens for a {provider_context_window}-token model window.",
                    ],
                )
        return profile

    def build_budget(
        self,
        *,
        task_plan: TaskPlan,
        workspace_files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        memory_hits: list[FixMemoryEntry],
        project_memory_hits: list[ProjectMemoryEntry],
        history: list[ChatMessage],
        provider_context_window: int | None = None,
    ) -> ContextBudgetResult:
        profile = self.profile_for(task_plan, provider_context_window)
        selected_files: list[WorkspaceFile] = []
        selected_memory: list[FixMemoryEntry] = []
        selected_project_memory: list[ProjectMemoryEntry] = []
        items: list[ContextBudgetItem] = []
        used_tokens = 0
        file_tokens = 0

        def include(kind: str, ref: str, estimate: int, limit_reason: str) -> bool:
            nonlocal used_tokens
            if used_tokens + estimate > profile.max_context_tokens:
                items.append(ContextBudgetItem(kind, ref, estimate, False, limit_reason))
                return False
            used_tokens += estimate
            items.append(ContextBudgetItem(kind, ref, estimate, True, "within route budget"))
            return True

        history_turns = history[-profile.max_history_turns :]
        for index, message in enumerate(history_turns, start=1):
            include(
                "history",
                f"{message.role}:{index}",
                self._estimate_text_tokens(message.content),
                "history exceeded route budget",
            )

        for item in memory_hits[: profile.max_fix_memory_items]:
            estimate = self._estimate_text_tokens(f"{item.error_signature}\n{item.fix_summary}\n{item.evidence}")
            if include("fix_memory", item.id, estimate, "fix memory exceeded route budget"):
                selected_memory.append(item)

        for item in project_memory_hits[: profile.max_project_memory_items]:
            estimate = self._estimate_text_tokens(f"{item.category}\n{item.title}\n{item.detail}")
            if include("project_memory", item.id, estimate, "project memory exceeded route budget"):
                selected_project_memory.append(item)

        for item in context_files[: profile.max_context_files]:
            estimate = self._estimate_file_tokens(item, profile)
            if include("file", item.path, estimate, "file context exceeded route budget"):
                selected_files.append(item)
                file_tokens += estimate

        return ContextBudgetResult(
            profile=profile,
            privacy_mode=task_plan.routing.privacy_mode if task_plan.routing else "local-first",
            context_files=selected_files,
            memory_hits=selected_memory,
            project_memory_hits=selected_project_memory,
            estimated_context_tokens=used_tokens,
            estimated_file_tokens=file_tokens,
            workspace_file_count=len(workspace_files),
            omitted_file_count=max(0, len(context_files) - len(selected_files)),
            omitted_memory_count=max(0, len(memory_hits) - len(selected_memory)),
            omitted_project_memory_count=max(0, len(project_memory_hits) - len(selected_project_memory)),
            items=items,
        )

    def _base_profile(self, intent: str, route_role: str) -> ContextBudgetProfile:
        profiles: dict[str, ContextBudgetProfile] = {
            "implementation": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="focused source files, project metadata, and recent implementation memory",
                max_context_tokens=14_000,
                max_context_files=16,
                max_file_chars=4200,
                max_history_turns=6,
                max_fix_memory_items=4,
                max_project_memory_items=5,
                reserve_response_tokens=3500,
            ),
            "debug_and_repair": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="failure surface, nearby dependencies, and prior repair memory",
                max_context_tokens=16_000,
                max_context_files=18,
                max_file_chars=5000,
                max_history_turns=6,
                max_fix_memory_items=5,
                max_project_memory_items=5,
                reserve_response_tokens=3500,
            ),
            "review_and_assess": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="broad scan of high-risk files with concise snippets",
                max_context_tokens=16_000,
                max_context_files=22,
                max_file_chars=3200,
                max_history_turns=5,
                max_fix_memory_items=3,
                max_project_memory_items=6,
                reserve_response_tokens=4000,
            ),
            "architecture_planning": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="architecture documents, manifests, module boundaries, and durable project notes",
                max_context_tokens=12_000,
                max_context_files=20,
                max_file_chars=2800,
                max_history_turns=6,
                max_fix_memory_items=2,
                max_project_memory_items=8,
                reserve_response_tokens=4500,
            ),
            "research_and_synthesize": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="project facts first, external-source requirements second",
                max_context_tokens=8_000,
                max_context_files=8,
                max_file_chars=3200,
                max_history_turns=5,
                max_fix_memory_items=2,
                max_project_memory_items=4,
                reserve_response_tokens=3500,
            ),
            "conversation": ContextBudgetProfile(
                intent=intent,
                route_role=route_role,
                strategy="minimal context with recent conversation and pinned project facts",
                max_context_tokens=5_000,
                max_context_files=6,
                max_file_chars=2200,
                max_history_turns=8,
                max_fix_memory_items=2,
                max_project_memory_items=3,
                reserve_response_tokens=2500,
            ),
        }
        profile = profiles.get(intent, profiles["conversation"])
        return self._cap_to_settings(profile)

    def _scale_profile(self, profile: ContextBudgetProfile, task_plan: TaskPlan) -> ContextBudgetProfile:
        complexity = getattr(task_plan, "complexity", "focused")
        if complexity not in {"large", "epic"}:
            return profile

        if complexity == "epic":
            scaled = ContextBudgetProfile(
                intent=profile.intent,
                route_role=profile.route_role,
                strategy=f"{profile.strategy}; epic-task decomposition with broader source and memory coverage",
                max_context_tokens=max(profile.max_context_tokens, 30_000),
                max_context_files=max(profile.max_context_files, 36),
                max_file_chars=max(profile.max_file_chars, 8200),
                max_history_turns=max(profile.max_history_turns, 10),
                max_fix_memory_items=max(profile.max_fix_memory_items, 8),
                max_project_memory_items=max(profile.max_project_memory_items, 12),
                reserve_response_tokens=max(profile.reserve_response_tokens, 6000),
                notes=[
                    *profile.notes,
                    "Expanded for epic-size coding work so the agent can keep roadmap, architecture, validation, and more files in view.",
                ],
            )
        else:
            scaled = ContextBudgetProfile(
                intent=profile.intent,
                route_role=profile.route_role,
                strategy=f"{profile.strategy}; large-task slice planning with extra project context",
                max_context_tokens=max(profile.max_context_tokens, 22_000),
                max_context_files=max(profile.max_context_files, 26),
                max_file_chars=max(profile.max_file_chars, 6200),
                max_history_turns=max(profile.max_history_turns, 8),
                max_fix_memory_items=max(profile.max_fix_memory_items, 6),
                max_project_memory_items=max(profile.max_project_memory_items, 9),
                reserve_response_tokens=max(profile.reserve_response_tokens, 4800),
                notes=[
                    *profile.notes,
                    "Expanded for large coding work so the agent can carry more files, memory, and validation context.",
                ],
            )
        return self._cap_to_settings(scaled)

    def _cap_to_settings(self, profile: ContextBudgetProfile) -> ContextBudgetProfile:
        settings_cap = max(1200, self.settings.max_context_chars // CHARS_PER_TOKEN)
        if profile.max_context_tokens <= settings_cap:
            return profile
        return ContextBudgetProfile(
            intent=profile.intent,
            route_role=profile.route_role,
            strategy=profile.strategy,
            max_context_tokens=settings_cap,
            max_context_files=profile.max_context_files,
            max_file_chars=min(profile.max_file_chars, self.settings.max_context_chars),
            max_history_turns=profile.max_history_turns,
            max_fix_memory_items=profile.max_fix_memory_items,
            max_project_memory_items=profile.max_project_memory_items,
            reserve_response_tokens=profile.reserve_response_tokens,
            notes=[*profile.notes, f"Capped to the configured {self.settings.max_context_chars}-character context limit."],
        )

    def _estimate_file_tokens(self, item: WorkspaceFile, profile: ContextBudgetProfile) -> int:
        return max(1, min(item.size, profile.max_file_chars) // CHARS_PER_TOKEN)

    def _estimate_text_tokens(self, text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)
