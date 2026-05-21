from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core import collaboration_runtime
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"collaboration-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "README.md").write_text("# Collaboration Fixture\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def app():\n    return 'ok'\n", encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_collaboration_roles_and_member_registration(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    roles = client.get("/v1/collaboration/roles")
    assert roles.status_code == 200
    assert_kind(roles.json(), "collaboration.roles")
    role_ids = {item["id"] for item in roles.json()["data"]["roles"]}
    assert {"owner", "maintainer", "reviewer", "observer", "deployment_approver", "validation_reviewer"}.issubset(role_ids)

    registered = client.post(
        "/v1/collaboration/members",
        json={
            "workspace": str(workspace_fixture),
            "user_id": "reviewer-1",
            "display_name": "Reviewer One",
            "role": "reviewer",
            "client_id": "pytest",
        },
    )
    assert registered.status_code == 200
    assert_kind(registered.json(), "collaboration.member")
    assert registered.json()["data"]["member"]["role"] == "reviewer"

    dashboard = client.get("/v1/collaboration", params={"workspace": str(workspace_fixture), "user_id": "reviewer-1"})
    assert dashboard.status_code == 200
    assert_kind(dashboard.json(), "collaboration.dashboard")
    assert dashboard.json()["data"]["observability"]["member_count"] >= 2


def test_shared_workflow_approval_chain_requires_role_signoff(workspace_fixture: Path) -> None:
    created = collaboration_runtime.create_shared_workflow(
        workspace_fixture,
        objective="Implement feature behind collaborative review",
        workflow_type="generate_feature",
        owner_id="owner-1",
        owner_role="owner",
        participants=[{"user_id": "reviewer-1", "role": "reviewer"}],
        approval_chain=[
            {"stage": "validation_signoff", "approval_type": "validation", "required_roles": ["reviewer"]},
            {"stage": "owner_gate", "approval_type": "workflow", "required_roles": ["owner"]},
        ],
    )
    workflow = created["workflow"]
    approvals = created["approvals"]

    assert workflow["status"] == "waiting_approval"
    assert len(approvals) == 2

    first = collaboration_runtime.decide_approval(
        workspace_fixture,
        approvals[0]["approval_id"],
        decision="approve",
        user_id="reviewer-1",
        role="reviewer",
        comment="Validation evidence looks sufficient.",
    )
    assert first["approval"]["status"] == "approved"
    assert first["target_workflow"]["status"] == "waiting_approval"

    second = collaboration_runtime.decide_approval(
        workspace_fixture,
        approvals[1]["approval_id"],
        decision="approve",
        user_id="owner-1",
        role="owner",
        comment="Owner approves implementation.",
    )
    assert second["approval"]["status"] == "approved"
    assert second["target_workflow"]["status"] == "active"

    audit = collaboration_runtime.collaboration_audit(workspace_fixture)
    assert any(event["event_type"] == "collaboration.workflow.created" for event in audit["events"])
    assert any(event["event_type"] == "collaboration.approval.approve" for event in audit["events"])


def test_observer_cannot_authorize_rollback(workspace_fixture: Path) -> None:
    created = collaboration_runtime.create_shared_workflow(
        workspace_fixture,
        objective="Coordinate a rollback rehearsal",
        workflow_type="generate_feature",
        owner_id="owner-1",
        owner_role="owner",
    )
    workflow_id = created["workflow"]["workflow_id"]
    action = collaboration_runtime.workflow_action(
        workspace_fixture,
        workflow_id,
        action="request_rollback",
        actor_id="owner-1",
        actor_role="owner",
        reason="Exercise rollback governance.",
    )
    approval_id = action["approval"]["approval_id"]

    with pytest.raises(collaboration_runtime.CollaborationRuntimeError):
        collaboration_runtime.decide_approval(
            workspace_fixture,
            approval_id,
            decision="approve",
            user_id="observer-1",
            role="observer",
        )

    approved = collaboration_runtime.decide_approval(
        workspace_fixture,
        approval_id,
        decision="approve",
        user_id="owner-1",
        role="owner",
    )
    assert approved["approval"]["status"] == "approved"
    assert approved["target_workflow"]["status"] == "active"


def test_collaborative_roadmap_repository_and_autopilot_context(workspace_fixture: Path) -> None:
    repo = collaboration_runtime.register_repository(
        workspace_fixture,
        repository_id="repo-main",
        path=".",
        name="Main Repo",
        owner_id="owner-1",
        runtime_nodes=["local", "validation-node"],
        validation_infrastructure=["pytest"],
    )["repository"]
    assert repo["repository_id"] == "repo-main"

    workflow = collaboration_runtime.create_shared_workflow(
        workspace_fixture,
        objective="Run deployment validation",
        workflow_type="deploy_staging",
        owner_id="owner-1",
        owner_role="owner",
        repository_id="repo-main",
    )["workflow"]
    item = collaboration_runtime.assign_roadmap_item(
        workspace_fixture,
        title="Validate staging deployment",
        workflow_id=workflow["workflow_id"],
        milestone="alpha",
        owner_id="owner-1",
        assigned_to="maintainer-1",
        approval_required=True,
    )["roadmap_item"]

    assert item["approval_required"] is True
    dashboard = collaboration_runtime.collaboration_dashboard(workspace_fixture)
    assert dashboard["observability"]["repository_count"] >= 1
    assert dashboard["roadmap_board"]["milestones"]["alpha"] == 1
    context = collaboration_runtime.autopilot_context(
        workspace_fixture,
        {"collaboration_workflow_id": workflow["workflow_id"]},
    )
    assert context["enabled"] is True
    assert context["requires_approval"] is True
    assert "deployment_approver" in context["required_roles"] or "owner" in context["required_roles"]


def test_collaboration_contracts_are_registered() -> None:
    required = {
        "collaboration.dashboard",
        "collaboration.roles",
        "collaboration.member",
        "collaboration.repository",
        "collaboration.workflow",
        "collaboration.approval",
        "collaboration.roadmap",
        "collaboration.audit",
    }
    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
