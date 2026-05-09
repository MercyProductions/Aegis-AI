from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.core_bridge import (
    AegisCoreBridge,
    core_envelope_error,
    core_dashboard_to_website_runtime_status,
    core_task_to_website_task_summary,
    core_validation_to_website_validation,
    normalize_core_base_url,
)


def test_normalize_core_base_url_accepts_common_local_inputs() -> None:
    assert normalize_core_base_url("127.0.0.1:8788") == "http://127.0.0.1:8788"
    assert normalize_core_base_url("http://127.0.0.1:8788/v1/health") == "http://127.0.0.1:8788"
    assert normalize_core_base_url("https://core.local:8788/v1/tasks") == "https://core.local:8788"
    assert normalize_core_base_url("not a url") == "http://127.0.0.1:8788"
    assert normalize_core_base_url("http://user:secret@127.0.0.1:8788") == "http://127.0.0.1:8788"


def test_core_bridge_reads_shared_runtime_status(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        kind_by_path = {
            "/v1/health": "health",
            "/v1/models": "models",
            "/v1/settings": "settings",
            "/v1/memory": "memory.summary",
            "/v1/diagnostics": "diagnostics.summary",
            "/v1/ecosystem/dashboard": "ecosystem.dashboard",
        }
        kind = kind_by_path[request.url.path]
        return httpx.Response(
            200,
            json={
                "ok": True,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": kind,
                "workspace": str(workspace.resolve()),
                "data": {"path": request.url.path},
            },
        )

    bridge = AegisCoreBridge("127.0.0.1:8788/v1/health", transport=httpx.MockTransport(handler))
    status = asyncio.run(bridge.shared_runtime_status(workspace))

    assert status["ok"] is True
    assert status["reachable"] is True
    assert status["core_url"] == "http://127.0.0.1:8788"
    assert status["contract_version"] == "2026.05.09"
    assert status["contract_versions"]["health"] == "2026.05.09"
    assert status["ownership"]["shared_runtime"] == "aegis-core"
    assert status["health"]["kind"] == "health"
    assert status["models"]["kind"] == "models"
    assert status["settings"]["kind"] == "settings"
    assert status["memory"]["kind"] == "memory.summary"
    assert status["diagnostics"]["kind"] == "diagnostics.summary"
    assert status["dashboard"]["kind"] == "ecosystem.dashboard"
    assert status["errors"] == []


def test_core_bridge_degrades_when_core_is_unavailable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": f"missing {request.url.path}"})

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    status = asyncio.run(bridge.shared_runtime_status(workspace))

    assert status["ok"] is False
    assert status["reachable"] is True
    assert status["health"] is None
    assert len(status["errors"]) == 6


def test_core_bridge_rejects_unexpected_contract_kind(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": "settings",
                "workspace": str(workspace.resolve()),
                "data": {},
            },
        )

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    result = asyncio.run(bridge.model_status(workspace))

    assert result.reachable is True
    assert result.ok is False
    assert "kind mismatch" in result.error


def test_core_bridge_marks_malformed_json_response_reachable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not Aegis Core JSON</html>")

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    result = asyncio.run(bridge.health_status(workspace))

    assert result.reachable is True
    assert result.ok is False
    assert result.status_code == 200
    assert "not valid JSON" in result.error


def test_low_risk_runtime_status_validates_all_expected_contracts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        kind_by_path = {
            "/v1/health": "health",
            "/v1/models": "models",
            "/v1/settings": "settings",
            "/v1/diagnostics": "diagnostics.summary",
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": kind_by_path[request.url.path],
                "workspace": str(workspace.resolve()),
                "data": {},
            },
        )

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    results = asyncio.run(bridge.low_risk_runtime_status(workspace))

    assert set(results) == {"health", "models", "settings", "diagnostics"}
    assert all(result.ok for result in results.values())
    assert set(seen_paths) == {"/v1/health", "/v1/models", "/v1/settings", "/v1/diagnostics"}


def test_core_bridge_surfaces_ok_false_error_detail(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": False,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": "models",
                "workspace": str(workspace.resolve()),
                "data": {"error": "model inventory unavailable"},
            },
        )

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    result = asyncio.run(bridge.model_status(workspace))

    assert result.reachable is True
    assert result.ok is False
    assert result.error == "model inventory unavailable"


def test_core_bridge_redacts_secret_like_core_error_detail(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = "AIzaSyVerySecretProviderKey"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": False,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": "models",
                "workspace": str(workspace.resolve()),
                "data": {"error": f"Provider failed at https://example.test/v1?key={secret}&alt=json"},
            },
        )

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    result = asyncio.run(bridge.model_status(workspace))

    assert result.reachable is True
    assert result.ok is False
    assert secret not in result.error
    assert "key=[redacted]" in result.error
    assert "Provider failed" in result.error


def test_core_bridge_redacts_secret_like_http_error_urls(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = "secret-token-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    bridge = AegisCoreBridge("http://127.0.0.1:8788", transport=httpx.MockTransport(handler))
    result = asyncio.run(bridge.get(f"/v1/models?token={secret}", expected_kind="models"))

    assert result.reachable is True
    assert result.ok is False
    assert secret not in result.error
    assert "token=[redacted]" in result.error


def test_core_envelope_error_redacts_secret_like_deprecations() -> None:
    secret = "sk-live-should-not-leak"
    error = core_envelope_error(
        {
            "ok": False,
            "api_version": "v1",
            "kind": "models",
            "deprecations": [f"Bearer {secret} should never be visible"],
            "data": {},
        }
    )

    assert secret not in error
    assert "Bearer [redacted]" in error


def test_core_envelope_error_redacts_full_authorization_header() -> None:
    secret = "basic-secret-token"
    error = core_envelope_error(
        {
            "ok": False,
            "api_version": "v1",
            "kind": "models",
            "data": {"error": f"Provider rejected Authorization: Basic {secret}"},
        }
    )

    assert secret not in error
    assert "Authorization: [redacted]" in error
    assert "Provider rejected" in error


def test_core_envelope_error_redacts_json_secret_fields() -> None:
    secret = "json-secret-token"
    error = core_envelope_error(
        {
            "ok": False,
            "api_version": "v1",
            "kind": "models",
            "data": {"error": f'Provider HTTP 401: {{"api_key":"{secret}","message":"invalid"}}'},
        }
    )

    assert secret not in error
    assert '"api_key":"[redacted]"' in error
    assert "invalid" in error


def test_core_runtime_endpoint_delegates_to_core_bridge(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class FakeCoreBridge:
        async def shared_runtime_status(self, workspace_path: Path):
            return {
                "ok": True,
                "reachable": True,
                "workspace": str(workspace_path),
                "core_url": "http://127.0.0.1:8788",
                "api_version": "v1",
                "health": {"kind": "health"},
                "errors": [],
            }

    with patch.object(main, "core_bridge", FakeCoreBridge()):
        response = TestClient(main.app).get("/api/core-runtime", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["health"]["kind"] == "health"
    assert response.json()["workspace"] == str(workspace.resolve())


def test_core_bridge_adapters_tolerate_missing_optional_fields() -> None:
    task = core_task_to_website_task_summary({"id": "task-1"})
    validation = core_validation_to_website_validation({"commands": [{"command": ["python", "-m", "pytest"]}]})
    dashboard = core_dashboard_to_website_runtime_status(
        {
            "ok": True,
            "api_version": "v1",
            "contract_version": "2026.05.09",
            "kind": "ecosystem.dashboard",
            "data": {
                "clients": [{"client_id": "desktop"}],
                "active_tasks": [{"id": "task-1"}],
                "validation": {"commands": [{"command": ["python", "-m", "pytest"]}]},
            },
        }
    )

    assert task["title"] == "Untitled task"
    assert task["status"] == "planned"
    assert validation["commands"][0]["command"] == "python -m pytest"
    assert dashboard["client_count"] == 1
    assert dashboard["active_tasks"][0]["id"] == "task-1"
    assert dashboard["contract_version"] == "2026.05.09"
