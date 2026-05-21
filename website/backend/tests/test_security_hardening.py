from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main


def test_security_status_endpoint_reports_website_and_core_trust(monkeypatch) -> None:
    async def fake_security_status(workspace):
        return main.CoreDelegationResult(
            delegated=True,
            ok=True,
            reachable=True,
            status_code=200,
            kind="security.status",
            data={"local_api": {"token_enforced": True}, "privacy": {"mode": "local-first"}},
            envelope=None,
        )

    monkeypatch.setattr(main.core_runtime_client, "security_status", fake_security_status)
    client = TestClient(main.app)

    response = client.get("/api/security/status")

    assert response.status_code == 200
    data = response.json()
    assert data["website"]["localhost_origin_guard"] is True
    assert data["website"]["max_request_bytes"] > 0
    assert data["workspace"]["path_traversal_rejected"] is True
    assert data["credentials"]["responses_mask_keys"] is True
    assert data["core"]["local_api"]["token_enforced"] is True


def test_website_rejects_untrusted_browser_origin() -> None:
    client = TestClient(main.app)

    response = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
