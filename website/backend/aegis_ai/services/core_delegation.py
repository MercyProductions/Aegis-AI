from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..core_bridge import CoreBridgeResult
from ..schemas import ApplyResponse, CheckpointListResponse, RestoreCheckpointResponse, ValidateResponse
from .core_client import (
    AegisCoreClient,
    CoreDelegationResult,
    checkpoint_summary_from_core,
    command_run_from_core_validation,
    core_event,
)


RepairWorkflowCreator = Callable[..., Awaitable[CoreDelegationResult]]
FallbackRecorder = Callable[[str, CoreDelegationResult], None]


def core_result_data(result: CoreBridgeResult | None) -> dict[str, Any]:
    return result.data if result is not None and isinstance(result.data, dict) else {}


def core_contract_version(result: CoreBridgeResult | None) -> str:
    envelope = result.envelope if result is not None else None
    return str(envelope.get("contract_version") or "") if isinstance(envelope, dict) else ""


def core_route_status(result: CoreBridgeResult | None) -> str:
    if result is not None and result.ok:
        return "connected"
    if result is not None and result.reachable:
        return "degraded"
    return "unavailable"


def core_route_message(result: CoreBridgeResult | None, route_group: str) -> str:
    if result is not None and result.ok:
        return f"Aegis Core {route_group} adapter is connected."
    if result is not None and result.error:
        return f"Aegis Core {route_group} adapter is unavailable; Website /api is using local fallback behavior. {result.error}"
    return f"Aegis Core {route_group} adapter is unavailable; Website /api is using local fallback behavior."


def core_delegation_data(result: CoreDelegationResult, workflow: str) -> dict[str, Any]:
    if isinstance(result.data, dict):
        return result.data
    raise HTTPException(
        status_code=502,
        detail=f"Aegis Core {workflow} response did not include an object payload.",
    )


def core_delegation_error(result: CoreDelegationResult, workflow: str) -> HTTPException:
    status_code = result.status_code if result.status_code and 400 <= result.status_code < 500 else 502
    detail = result.error or f"Aegis Core rejected {workflow}."
    return HTTPException(status_code=status_code, detail=detail)


def record_core_fallback(core_client: AegisCoreClient, workflow: str, result: CoreDelegationResult) -> None:
    reason = result.error or "Aegis Core is unavailable for this workflow."
    core_client.record_fallback(workflow, reason)


def apply_response_from_core(
    root: Path,
    result: CoreDelegationResult,
    *,
    workspace_files: Sequence[Any],
) -> ApplyResponse:
    data = core_delegation_data(result, "changes.apply")
    warnings = [str(item) for item in data.get("warnings", []) if str(item).strip()]
    checkpoint = data.get("checkpoint_id")
    if not checkpoint and isinstance(data.get("checkpoint"), dict):
        checkpoint = data["checkpoint"].get("id")
    return ApplyResponse(
        applied=[str(item) for item in data.get("applied", []) if str(item).strip()],
        warnings=warnings,
        checkpoint=str(checkpoint) if checkpoint else None,
        workspace_root=str(root),
        workspace_files=list(workspace_files),
    )


def checkpoint_list_response_from_core(root: Path, result: CoreDelegationResult) -> CheckpointListResponse:
    data = core_delegation_data(result, "checkpoints.list")
    checkpoints = [
        checkpoint_summary_from_core(item)
        for item in data.get("checkpoints", [])
        if isinstance(item, dict)
    ]
    return CheckpointListResponse(workspace_root=str(root), checkpoints=checkpoints)


def restore_response_from_core(
    root: Path,
    result: CoreDelegationResult,
    *,
    workspace_files: Sequence[Any],
) -> RestoreCheckpointResponse:
    data = core_delegation_data(result, "checkpoints.restore")
    return RestoreCheckpointResponse(
        restored=[str(item) for item in data.get("restored", []) if str(item).strip()],
        warnings=[str(item) for item in data.get("warnings", []) if str(item).strip()],
        workspace_root=str(root),
        workspace_files=list(workspace_files),
    )


def validation_warnings_from_core(data: dict[str, Any], validation_present: bool) -> list[str]:
    warnings = [str(item) for item in data.get("warnings", []) if str(item).strip()]
    if not validation_present:
        warnings.append("No validation command was detected for this workspace.")
    return warnings


def validation_failed(validation: Any) -> bool:
    return bool(
        validation is not None
        and (
            not validation.allowed
            or validation.timed_out
            or validation.exit_code is None
            or validation.exit_code != 0
        )
    )


async def validate_response_from_core(
    root: Path,
    result: CoreDelegationResult,
    *,
    validation_profile: Any,
    create_repair_workflow: RepairWorkflowCreator,
    record_fallback: FallbackRecorder,
) -> ValidateResponse:
    data = core_delegation_data(result, "validation.run")
    validation = command_run_from_core_validation(data, root)
    task_id = str(data.get("task_id") or data.get("job_id") or data.get("id") or "")
    events = [
        core_event(
            "core",
            "Validation delegated to Aegis Core",
            detail="Website preserved the /api/validate response shape while Core executed and stored the validation run.",
            payload={
                "validation_id": data.get("id"),
                "job_id": data.get("job_id"),
                "task_id": task_id,
                "source_client": data.get("source_client"),
            },
        )
    ]
    warnings = validation_warnings_from_core(data, validation is not None)

    if validation is not None:
        events.append(
            core_event(
                "command",
                "Validation command executed",
                status="ok" if not validation_failed(validation) else "error",
                detail=validation.summary or validation.reason,
                payload=validation.model_dump(mode="json"),
            )
        )

    if validation_failed(validation):
        repair_result = await create_repair_workflow(
            root,
            validation_id=str(data.get("id") or ""),
            validation_summary=validation.summary or validation.reason,
            task_id=task_id,
        )
        if repair_result.delegated:
            repair_data = core_delegation_data(repair_result, "repair_project.workflow")
            workflow = repair_data.get("workflow") if isinstance(repair_data.get("workflow"), dict) else {}
            workflow_id = str(workflow.get("id") or "")
            if workflow_id:
                warnings.append(f"Aegis Core queued repair workflow {workflow_id}.")
                events.append(
                    core_event(
                        "repair",
                        "Core repair workflow queued",
                        status="warning",
                        detail=workflow_id,
                        payload={"workflow_id": workflow_id, "validation_id": data.get("id")},
                    )
                )
        elif repair_result.should_fallback:
            record_fallback("repair_project.workflow", repair_result)
            warnings.append("Aegis Core validation ran, but repair workflow creation is unavailable.")
        else:
            warnings.append(repair_result.error or "Aegis Core rejected repair workflow creation.")

    return ValidateResponse(
        task_id=task_id or "core-validation",
        workspace_root=str(root),
        events=events,
        validation=validation,
        validation_profile=validation_profile,
        warnings=warnings,
    )
