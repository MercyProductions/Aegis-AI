from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aegis_core.contracts import validate_contract_envelope
from aegis_core.diagnostics import redact_inline
from aegis_core.server import create_app


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "security-project"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Security Project\n", encoding="utf-8")
    return workspace


def test_security_status_contract_exposes_trust_controls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CORE_LOCAL_TOKEN", raising=False)
    monkeypatch.delenv("AEGIS_CORE_REQUIRE_TOKEN", raising=False)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get("/v1/security/status", params={"workspace": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == "security.status"
    data = payload["data"]
    assert data["local_api"]["loopback_host_guard"] is True
    assert data["workspace_access"]["path_traversal_rejected"] is True
    assert data["credentials"]["plaintext_storage_allowed"] is False
    assert data["updates"]["checksum_required"] is True
    assert data["audit"]["enabled"] is True


def test_core_local_api_token_blocks_unauthorized_requests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_CORE_LOCAL_TOKEN", "local-test-token")
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    blocked = client.get("/v1/security/status", params={"workspace": str(workspace)})
    allowed = client.get(
        "/v1/security/status",
        params={"workspace": str(workspace)},
        headers={"Authorization": "Bearer local-test-token"},
    )

    assert blocked.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["data"]["local_api"]["token_enforced"] is True


def test_core_rejects_untrusted_browser_origin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CORE_LOCAL_TOKEN", raising=False)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.get(
        "/v1/security/status",
        params={"workspace": str(workspace)},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


def test_core_rejects_oversized_requests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CORE_LOCAL_TOKEN", raising=False)
    monkeypatch.setenv("AEGIS_CORE_MAX_REQUEST_BYTES", "1024")
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "README.md", "content": "x" * 5000}],
        },
    )

    assert response.status_code == 413


def test_unsafe_workspace_paths_are_audited(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CORE_LOCAL_TOKEN", raising=False)
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/changes/propose",
        json={
            "workspace": str(workspace),
            "changes": [{"action": "update", "path": "../outside.txt", "content": "OPENAI_API_KEY=sk-secret"}],
        },
    )

    assert response.status_code == 400
    audit_path = workspace / ".aegis" / "security-audit.jsonl"
    audit = audit_path.read_text(encoding="utf-8")
    assert "workspace.unsafe_path" in audit
    assert "sk-secret" not in audit


def test_secret_redaction_masks_provider_keys() -> None:
    text = redact_inline("Authorization: Bearer sk-abc12345678901234567890 api_key=secret-value")

    assert "sk-abc" not in text
    assert "secret-value" not in text
    assert "[redacted]" in text


def test_privacy_mode_blocks_cloud_routing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AEGIS_CORE_LOCAL_TOKEN", raising=False)
    monkeypatch.setenv("AEGIS_CLOUD_DISABLED", "true")
    workspace = make_workspace(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/v1/models/route",
        json={
            "workspace": str(workspace),
            "task_type": "hard_debugging",
            "route_profile": "best_reasoning",
            "allow_cloud": True,
            "cloud_approved": True,
            "provider_id": "openai",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["local_only"] is True
    assert data["selected"]["provider_id"] in {"ollama", "lm_studio"}
    assert any("disabled" in warning.lower() for warning in data["warnings"])
