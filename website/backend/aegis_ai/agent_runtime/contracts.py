from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import FileChange


@dataclass
class AgentDraft:
    reply: str
    plan: list[str] = field(default_factory=list)
    changes: list[FileChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    proposed_commands: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class MissionAnchor:
    original_user_mission: str = ""
    active_workspace_root: str = ""
    continuity_rule: str = ""
