from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis_core import autopilot, governance_runtime
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.server import create_app


@pytest.fixture
def workspace_fixture() -> Path:
    root = Path.cwd() / ".test-workspaces" / f"governance-{uuid.uuid4().hex[:10]}"
    root.mkdir(parents=True)
    try:
        (root / "README.md").write_text("# Governance Fixture\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def app():\n    return 'ok'\n", encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def assert_kind(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind


def test_governance_dashboard_and_contract_routes(workspace_fixture: Path) -> None:
    client = TestClient(create_app())
    dashboard = client.get("/v1/governance", params={"workspace": str(workspace_fixture)})
    assert dashboard.status_code == 200
    assert_kind(dashboard.json(), "governance.dashboard")
    data = dashboard.json()["data"]
    assert data["compliance"]["local_first"] is True
    assert data["runtime_trust_levels"]
    assert any(policy["policy_id"] == "gov.command.dangerous_tokens" for policy in data["policies"])

    policies = client.get("/v1/governance/policies", params={"workspace": str(workspace_fixture)})
    assert policies.status_code == 200
    assert_kind(policies.json(), "governance.policies")


def test_dangerous_command_is_blocked_and_audited(workspace_fixture: Path) -> None:
    result = governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="command",
        context={"command": ["powershell", "-Command", "rm", "-Recurse", "."]},
        actor_id="maintainer-1",
        actor_role="maintainer",
    )
    assert result["status"] == "blocked"
    assert result["allowed"] is False
    assert any(item["policy_id"] == "gov.command.dangerous_tokens" for item in result["restrictions"])

    audit = governance_runtime.audit_events(workspace_fixture)
    assert any(event["event_type"] == "governance.policy.evaluated" and event["status"] == "blocked" for event in audit["events"])


def test_plugin_runtime_and_remote_node_policy_require_approval(workspace_fixture: Path) -> None:
    plugin_result = governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="plugin_enable",
        context={"permission_scopes": ["filesystem_read", "filesystem_write", "network_access"], "trusted": False},
        actor_role="maintainer",
    )
    assert plugin_result["status"] == "needs_approval"
    assert any(item["policy_id"] == "gov.plugin.high_risk_permissions" for item in plugin_result["approval_requirements"])

    runtime_result = governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="runtime_workload",
        context={
            "allow_remote": True,
            "node_trust_level": "untrusted",
            "workload_type": "build",
            "permission_scopes": ["validation_execution"],
        },
        actor_role="maintainer",
    )
    assert runtime_result["status"] == "blocked"
    assert any(item["policy_id"] == "gov.runtime.remote_trust" for item in runtime_result["restrictions"])


def test_production_deployment_requires_signoff_and_validation(workspace_fixture: Path) -> None:
    blocked = governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="deployment",
        workflow_type="deploy_production",
        target="production",
        context={"target_environment": "production", "validation_passed": False, "production_confirmed": False},
        actor_role="maintainer",
    )
    assert blocked["status"] == "needs_approval"

    allowed = governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="deployment",
        workflow_type="deploy_production",
        target="production",
        context={"target_environment": "production", "validation_passed": True, "production_confirmed": True},
        actor_role="deployment_approver",
        approval=True,
    )
    assert allowed["status"] == "allowed"


def test_compliance_export_contains_policy_and_audit_sources(workspace_fixture: Path) -> None:
    governance_runtime.evaluate_policy(
        workspace_fixture,
        action_type="memory_export",
        context={"operation": "memory_export", "category": "private_memory", "sensitive": True},
        actor_role="owner",
    )
    exported = governance_runtime.compliance_export(workspace_fixture, export_type="audit", limit=100)
    assert Path(exported["path"]).is_file()
    bundle = exported["export"]
    assert bundle["reports"]["policy_violations"]
    assert "governance" in bundle["audit_sources"]
    assert "plugin_permissions" in bundle["reports"]


def test_autopilot_pauses_on_policy_violation(workspace_fixture: Path) -> None:
    run = autopilot.start_autopilot(
        workspace_fixture,
        "Run a supervised build command",
        mode="semi_autonomous",
        workflow_type="generate_feature",
        target_files=["src/app.py"],
    )["run"]
    updated = autopilot.autopilot_action(
        workspace_fixture,
        run["id"],
        "launch_terminal",
        payload={"command": ["powershell", "-Command", "rm", "-Recurse", "."]},
    )["run"]
    assert updated["status"] == "waiting_approval"
    assert updated["governance"]["blocked"] is True
    assert any(item["stage_key"] == "policy_governance" for item in updated["pending_approvals"])


def test_governance_contracts_are_registered() -> None:
    required = {
        "governance.dashboard",
        "governance.policies",
        "governance.policy",
        "governance.evaluation",
        "governance.audit",
        "governance.compliance_export",
    }
    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)
