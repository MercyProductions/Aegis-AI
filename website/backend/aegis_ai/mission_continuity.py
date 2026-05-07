from __future__ import annotations

from typing import Any
import re

from .agent_runtime import MissionAnchor


MISSION_ANCHOR_PREFIX = "Aegis mission anchor:"


def mission_anchor_from_history(history: list[Any]) -> MissionAnchor | None:
    for item in reversed(history):
        role = str(getattr(item, "role", "") or "").strip().lower()
        content = str(getattr(item, "content", "") or "")
        if role != "system" or not content.strip().startswith(MISSION_ANCHOR_PREFIX):
            continue
        anchor = parse_mission_anchor(content)
        if anchor is not None:
            return anchor
    return None


def parse_mission_anchor(content: str) -> MissionAnchor | None:
    values: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("-") or ":" not in line:
            continue
        key, value = line[1:].split(":", 1)
        normalized_key = key.strip().lower()
        values[normalized_key] = value.strip()

    anchor = MissionAnchor(
        original_user_mission=values.get("original user mission", ""),
        active_workspace_root=values.get("active workspace root", ""),
        continuity_rule=values.get("continuity rule", ""),
    )
    if anchor.original_user_mission or anchor.active_workspace_root:
        return anchor
    return None


def request_is_broad_mission_followup(cleaned_message: str, *, has_explicit_workspace: bool = False) -> bool:
    cleaned = cleaned_message.strip().lower()
    if not cleaned:
        return False
    if has_explicit_workspace:
        return False
    if len(cleaned.split()) > 14:
        return False

    followup_patterns = (
        r"^(continue|keep going|carry on|go ahead|move forward|next|next step|next pass)$",
        r"^(continue|keep going|carry on|go ahead) (with|working|building|fixing|repairing).*$",
        r"^(yes|yeah|yep|yup|sure|confirmed|confirm|ok|okay|please do|do it|go for it|proceed)$",
        r"^(yes|yeah|yep|yup|sure|ok|okay)\b.*\b(go ahead|continue|do it|build it|finish it|complete it|make it|proceed)\b.*$",
        r"^(build|fix|repair|validate|finish|complete|run|test|compile|verify)( it| this| the project| the app| the build)?$",
        r"^(build|fix|repair|validate|finish|complete|run|test|compile|verify)\b.*\b(source|code|files?|project|app|build)\b.*$",
        r"^(use|keep|follow)\b.*\b(latest|current|existing|source|workspace|project)\b.*\b(build|compile|validate|continue|finish|complete)\b.*$",
        r"^(autopilot|wrap up|finish up|do the next pass|continue your suggestions).*$",
        r"^if (there'?s|there is) an error.*$",
        r"^you didn'?t build it.*$",
    )
    if any(re.search(pattern, cleaned) for pattern in followup_patterns):
        return True

    continuation_terms = ("continue", "fix it", "build it", "repair it", "validate it", "finish it", "yes")
    return cleaned in continuation_terms


def mission_anchor_context(anchor: MissionAnchor | None) -> str:
    if anchor is None:
        return ""
    lines = ["Mission continuity anchor:"]
    if anchor.original_user_mission:
        lines.append(f"- Original user mission: {anchor.original_user_mission}")
    if anchor.active_workspace_root:
        lines.append(f"- Active workspace root: {anchor.active_workspace_root}")
    if anchor.continuity_rule:
        lines.append(f"- Continuity rule: {anchor.continuity_rule}")
    lines.append("- Vague follow-ups must preserve that target path, stack, artifact type, and validation intent.")
    return "\n".join(lines)


def mission_aware_message(message: str, anchor: MissionAnchor | None, *, is_broad_followup: bool) -> str:
    if anchor is None or not is_broad_followup:
        return message
    context = mission_anchor_context(anchor)
    if not context:
        return message
    return (
        f"{message}\n\n"
        f"{context}\n"
        "- Treat this user text as a continuation of the original mission, not a new project request."
    )
