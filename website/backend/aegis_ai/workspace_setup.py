from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .schemas import WorkspaceProjectManifest, WorkspaceSetupRequest


def workspace_setup_project_name(root: Path, requested: str = "") -> str:
    name = requested.strip() or root.name.strip() or "workspace"
    name = re.sub(r"[^A-Za-z0-9_. -]+", "", name).strip(" ._-")
    return name[:80] or "workspace"


def workspace_setup_title(project_name: str, requested: str = "") -> str:
    title = requested.strip()
    if title:
        return title[:120]
    words = [word for word in re.split(r"[-_\s]+", project_name) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words)[:120] or "Workspace"


def workspace_setup_stack_value(values: list[str], *, limit: int = 3) -> str:
    return " + ".join(item for item in values[:limit] if item)


def workspace_setup_preset_id(project_type: str) -> str:
    text = project_type.strip().lower() or "detected-workspace"
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or "detected-workspace"


def workspace_setup_manifest(
    root: Path,
    request: WorkspaceSetupRequest,
    *,
    dependency_profile: Any,
    install_command: str,
    validation_command: str,
) -> WorkspaceProjectManifest:
    project_name = workspace_setup_project_name(root, request.project_name)
    project_type = str(getattr(dependency_profile, "project_type", "") or "").strip()
    preset_label = project_type or "Detected workspace"
    language = workspace_setup_stack_value(list(getattr(dependency_profile, "languages", []) or []))
    framework = workspace_setup_stack_value(list(getattr(dependency_profile, "frameworks", []) or []))
    package_manager = workspace_setup_stack_value(list(getattr(dependency_profile, "package_managers", []) or []), limit=2)
    tags = ["workspace-setup"]
    for item in [project_type, language, framework, package_manager]:
        if item:
            tags.extend(part.strip().lower() for part in item.split("+") if part.strip())

    return WorkspaceProjectManifest(
        schema="aegis.project.v1",
        project_name=project_name,
        title=workspace_setup_title(project_name, request.title),
        preset_id=workspace_setup_preset_id(project_type),
        preset_label=preset_label,
        framework=framework,
        language=language,
        package_manager=package_manager,
        install_command=install_command,
        validation_command=validation_command,
        original_prompt="Workspace setup generated from detected project files.",
        tags=list(dict.fromkeys(tags))[:24],
        generated_by="Aegis Workspace Setup",
        mission_contract={
            "setup_source": "workspace_profile",
            "validation_command": validation_command,
            "install_command": install_command,
        },
        agent_handoff={
            "next_action": "Run validation and continue from the workspace readiness panel.",
        },
    )


def merge_missing_manifest_fields(
    existing: WorkspaceProjectManifest,
    generated: WorkspaceProjectManifest,
) -> tuple[WorkspaceProjectManifest, bool]:
    payload = existing.model_dump(mode="json", by_alias=True)
    changed = False
    for key, value in generated.model_dump(mode="json", by_alias=True).items():
        if key in {"mission_contract", "agent_handoff", "tags"}:
            continue
        if value and not payload.get(key):
            payload[key] = value
            changed = True
    if generated.tags:
        tags = [str(item).strip() for item in payload.get("tags", []) if str(item).strip()]
        for tag in generated.tags:
            if tag not in tags:
                tags.append(tag)
                changed = True
        payload["tags"] = tags[:24]
    return WorkspaceProjectManifest(**payload), changed
