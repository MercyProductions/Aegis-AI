from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.services.core_client import CoreDelegationResult
from aegis_ai.services.core_delegation import (
    apply_response_from_core,
    checkpoint_list_response_from_core,
    core_delegation_data,
    core_delegation_error,
    restore_response_from_core,
    validate_response_from_core,
)
from aegis_ai.schemas import WorkspaceFile


def _core_result(kind: str, data: object, *, ok: bool = True, status_code: int = 200) -> CoreDelegationResult:
    return CoreDelegationResult(
        delegated=True,
        ok=ok,
        reachable=True,
        status_code=status_code,
        kind=kind,
        data=data,
        envelope={"ok": ok, "api_version": "v1", "kind": kind, "data": data},
    )


def _offline(kind: str) -> CoreDelegationResult:
    return CoreDelegationResult(
        delegated=False,
        ok=False,
        reachable=False,
        status_code=None,
        kind=kind,
        error="Core offline",
    )


def test_core_delegation_data_requires_object_payload() -> None:
    assert core_delegation_data(_core_result("demo", {"ok": True}), "demo") == {"ok": True}

    with pytest.raises(HTTPException) as exc:
        core_delegation_data(_core_result("demo", ["not", "an", "object"]), "demo")

    assert exc.value.status_code == 502
    assert "did not include an object payload" in exc.value.detail


def test_core_delegation_error_preserves_client_status_codes() -> None:
    error = core_delegation_error(
        CoreDelegationResult(
            delegated=False,
            ok=False,
            reachable=True,
            status_code=409,
            kind="changes.apply",
            error="conflict",
        ),
        "changes.apply",
    )

    assert error.status_code == 409
    assert error.detail == "conflict"

    server_error = core_delegation_error(_offline("changes.apply"), "changes.apply")
    assert server_error.status_code == 502
    assert server_error.detail == "Core offline"


def test_apply_and_restore_responses_from_core_include_workspace_scan() -> None:
    root = Path("C:/workspace/project")
    workspace_files = [WorkspaceFile(path="app.py", kind="text", size=12)]

    apply_response = apply_response_from_core(
        root,
        _core_result(
            "changes.apply",
            {
                "applied": ["update: app.py", ""],
                "warnings": ["check formatting", ""],
                "checkpoint": {"id": "checkpoint-from-object"},
            },
        ),
        workspace_files=workspace_files,
    )

    assert apply_response.applied == ["update: app.py"]
    assert apply_response.warnings == ["check formatting"]
    assert apply_response.checkpoint == "checkpoint-from-object"
    assert apply_response.workspace_files == workspace_files

    restore_response = restore_response_from_core(
        root,
        _core_result(
            "checkpoints.restore",
            {
                "restored": ["restore: app.py", ""],
                "warnings": ["kept new file"],
            },
        ),
        workspace_files=workspace_files,
    )

    assert restore_response.restored == ["restore: app.py"]
    assert restore_response.warnings == ["kept new file"]
    assert restore_response.workspace_files == workspace_files


def test_checkpoint_list_response_from_core_maps_summaries() -> None:
    response = checkpoint_list_response_from_core(
        Path("C:/workspace/project"),
        _core_result(
            "checkpoints.list",
            {
                "checkpoints": [
                    {
                        "id": "checkpoint-a",
                        "created_at": "2026-05-21T00:00:00Z",
                        "files": [{"path": "app.py", "state": "present"}],
                    },
                    "ignored",
                ]
            },
        ),
    )

    assert len(response.checkpoints) == 1
    assert response.checkpoints[0].id == "checkpoint-a"
    assert response.checkpoints[0].file_count == 1


def test_validate_response_from_core_queues_repair_for_failed_validation(tmp_path: Path) -> None:
    repair_calls: list[dict[str, str]] = []
    fallbacks: list[tuple[str, str]] = []

    async def create_repair_workflow(root: Path, **kwargs: str) -> CoreDelegationResult:
        repair_calls.append(kwargs)
        return _core_result(
            "workflow.created",
            {"workflow": {"id": "repair-workflow"}},
        )

    response = asyncio.run(
        validate_response_from_core(
            tmp_path,
            _core_result(
                "validation.run",
                {
                    "id": "validation-a",
                    "job_id": "job-a",
                    "task_id": "task-a",
                    "source_client": "website-backend",
                    "validation": {
                        "ok": False,
                        "command": ["python", "-m", "pytest"],
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "failed",
                    },
                    "warnings": [],
                },
                ok=False,
            ),
            validation_profile=None,
            create_repair_workflow=create_repair_workflow,
            record_fallback=lambda workflow, result: fallbacks.append((workflow, result.error)),
        )
    )

    assert response.task_id == "task-a"
    assert response.validation is not None
    assert response.validation.exit_code == 1
    assert "Aegis Core queued repair workflow repair-workflow." in response.warnings
    assert any(event.kind == "repair" for event in response.events)
    assert repair_calls == [
        {
            "validation_id": "validation-a",
            "validation_summary": "Validation command exited with 1.",
            "task_id": "task-a",
        }
    ]
    assert fallbacks == []


def test_validate_response_from_core_records_repair_fallback(tmp_path: Path) -> None:
    fallbacks: list[tuple[str, str]] = []

    async def create_repair_workflow(root: Path, **kwargs: str) -> CoreDelegationResult:
        return _offline("workflow.created")

    response = asyncio.run(
        validate_response_from_core(
            tmp_path,
            _core_result(
                "validation.run",
                {
                    "id": "validation-a",
                    "validation": {
                        "ok": False,
                        "command": "pytest",
                        "returncode": 1,
                        "stderr": "failed",
                    },
                },
                ok=False,
            ),
            validation_profile=None,
            create_repair_workflow=create_repair_workflow,
            record_fallback=lambda workflow, result: fallbacks.append((workflow, result.error)),
        )
    )

    assert "Aegis Core validation ran, but repair workflow creation is unavailable." in response.warnings
    assert fallbacks == [("repair_project.workflow", "Core offline")]
