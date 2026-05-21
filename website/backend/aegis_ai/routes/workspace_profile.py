from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Query

from ..schemas import WorkspaceProfileResponse
from ..workspace_cache import WorkspaceStatusSnapshot


WorkspaceStatusSnapshotFactory = Callable[[Path], WorkspaceStatusSnapshot]
ProjectIntelligenceProbe = Callable[[Path], object]


def build_workspace_profile(
    root: Path,
    *,
    workspace_status_snapshot: WorkspaceStatusSnapshotFactory,
    project_intelligence_snapshot: ProjectIntelligenceProbe,
) -> WorkspaceProfileResponse:
    snapshot = workspace_status_snapshot(root)
    manifest = snapshot.manifest
    dependency_profile = snapshot.dependency_profile
    instruction_status = snapshot.instruction_status
    validation_plan = snapshot.validation_plan
    readiness = snapshot.readiness
    recommendations: list[str] = []
    if manifest is None:
        recommendations.append("No .aegis/project.json manifest was found for this workspace.")
    else:
        if manifest.schema_version != "aegis.project.v1":
            recommendations.append("The project manifest schema is unknown; Aegis will treat it as advisory metadata.")
        if not manifest.validation_command:
            recommendations.append("The project manifest does not define a validation command.")
        if not manifest.install_command:
            recommendations.append("The project manifest does not define an install command.")
    if not dependency_profile.config_files:
        recommendations.append("No dependency or build manifest was detected, so validation planning will rely on file scanning and user guidance.")
    if not dependency_profile.validation_commands and (manifest is None or not manifest.validation_command):
        recommendations.append("No validation command was inferred for this workspace.")
    if instruction_status.open_items:
        recommendations.append(
            f"Instruction checkpoint has {instruction_status.open_items} open tracked item(s); autopilot should continue from the saved recommendation."
        )
    elif instruction_status.total_items:
        recommendations.append("Instruction checkpoint shows all tracked project items are currently complete.")
    if validation_plan.steps:
        recommendations.append(
            f"Validation plan has {len(validation_plan.steps)} step(s); use it as the repair loop source of truth before adding new scope."
        )
        last_run = validation_plan.last_run if isinstance(validation_plan.last_run, dict) else {}
        if str(last_run.get("status") or "").lower() in {"failed", "blocked", "needs_attention"}:
            failed_step = str(last_run.get("failed_step") or "").strip()
            failed_hint = f" step {failed_step}" if failed_step else ""
            command = str(last_run.get("command") or validation_plan.validation_command or "").strip()
            command_hint = f" ({command})" if command else ""
            recommendations.append(f"Repair validation plan{failed_hint}{command_hint} before continuing autopilot expansion.")
    elif validation_plan.validation_command:
        recommendations.append("Validation plan has a command but no expanded steps; refresh project memory before long autopilot runs.")
    if readiness.next_action:
        recommendations.append(f"Readiness next action: {readiness.next_action}")
    try:
        project_intelligence_snapshot(root)
    except Exception:
        recommendations.append("Project Intelligence indexing is not ready for this workspace yet.")

    return WorkspaceProfileResponse(
        workspace_root=str(root),
        manifest=manifest,
        has_manifest=manifest is not None,
        dependency_profile=dependency_profile,
        instruction_status=instruction_status,
        has_instruction_status=bool(instruction_status.schema_version or instruction_status.files),
        validation_plan=validation_plan,
        has_validation_plan=bool(validation_plan.schema_version or validation_plan.validation_command or validation_plan.steps),
        readiness=readiness,
        recommendations=recommendations,
    )


def register_workspace_profile_routes(
    app: FastAPI,
    *,
    workspace_profile: Callable[[str | None], Awaitable[WorkspaceProfileResponse]],
) -> None:
    @app.get("/api/workspace/profile", response_model=WorkspaceProfileResponse)
    async def workspace_profile_route(workspace_root: str | None = Query(default=None)) -> WorkspaceProfileResponse:
        return await workspace_profile(workspace_root)
