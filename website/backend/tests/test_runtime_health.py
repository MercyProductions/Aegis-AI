from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.core_bridge import CoreBridgeResult
from aegis_ai.llm import LocalModelStatus
from aegis_ai.schemas import ModelRegistryProvider, ModelRegistryResponse, ModelRegistryRole
from aegis_ai.settings import Settings


class FakeAgent:
    async def model_status(self) -> LocalModelStatus:
        return LocalModelStatus(ready=True, message="test model ready")


class FakeWorkspaceManager:
    def __init__(self, root: Path):
        self.root = root

    def resolve_workspace(self, workspace_root: str | None) -> Path:
        path = self.root / (workspace_root or "workspace")
        path.mkdir(parents=True, exist_ok=True)
        return path


class FakeRegistry:
    def snapshot(self) -> ModelRegistryResponse:
        return ModelRegistryResponse(
            active_provider_id="local:test",
            active_model="test-model",
            router_enabled=True,
            fallback_supported=True,
            providers=[
                ModelRegistryProvider(
                    id="local:test",
                    label="Local Test",
                    api="test",
                    endpoint="http://127.0.0.1:9999",
                    model_name="test-model",
                    enabled=True,
                    configured=True,
                )
            ],
            roles=[
                ModelRegistryRole(
                    id="chat",
                    label="Chat",
                    description="General chat",
                    primary_model="test-model",
                )
            ],
        )


def _core_envelope(kind: str, data: dict) -> dict:
    return {
        "ok": True,
        "api_version": "v1",
        "contract_version": "2026.05.09",
        "kind": kind,
        "data": data,
    }


class ConnectedCoreBridge:
    async def low_risk_runtime_status(self, workspace: Path):
        return {
            "health": CoreBridgeResult(True, True, 200, "health", {"ok": True}, _core_envelope("health", {"ok": True})),
            "models": CoreBridgeResult(
                True,
                True,
                200,
                "models",
                {"reachable": True, "selected_model": "test-model", "installed_models": ["test-model"]},
                _core_envelope("models", {"reachable": True, "selected_model": "test-model", "installed_models": ["test-model"]}),
            ),
            "settings": CoreBridgeResult(True, True, 200, "settings", {}, _core_envelope("settings", {})),
            "diagnostics": CoreBridgeResult(True, True, 200, "diagnostics.summary", {}, _core_envelope("diagnostics.summary", {})),
        }


class OfflineCoreBridge:
    async def low_risk_runtime_status(self, workspace: Path):
        return {
            "health": CoreBridgeResult(False, False, None, "", None, error="connection refused"),
            "models": CoreBridgeResult(False, False, None, "", None, error="connection refused"),
            "settings": CoreBridgeResult(False, False, None, "", None, error="connection refused"),
            "diagnostics": CoreBridgeResult(False, False, None, "", None, error="connection refused"),
        }


class RuntimeHealthTests(unittest.TestCase):
    def test_runtime_health_snapshot_includes_readiness_and_registry_diagnostics(self) -> None:
        settings = Settings(
            _env_file=None,
            DEFAULT_WORKSPACE="workspace",
            AEGIS_MODEL_API="test",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:9999",
            AEGIS_MODEL_NAME="test-model",
            AEGIS_DATABASE_PATH="data/test.sqlite3",
            AEGIS_ROUTER_EXECUTION_ENABLED=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch.object(main, "settings", settings),
                patch.object(main, "PROJECT_ROOT", project_root),
                patch.object(main, "agent", FakeAgent()),
                patch.object(main, "workspace_manager", FakeWorkspaceManager(project_root)),
                patch.object(main, "model_registry", FakeRegistry()),
                patch.object(main, "core_bridge", ConnectedCoreBridge()),
                patch.object(main, "has_env_file", lambda: True),
            ):
                health = asyncio.run(main.runtime_health_snapshot())

        self.assertTrue(health.ok)
        self.assertTrue(health.ready)
        self.assertEqual(health.status, "ready")
        self.assertEqual(health.model_api, "test")
        self.assertTrue(health.model_ready)
        self.assertTrue(health.router_execution_enabled)
        self.assertTrue(health.router_enabled)
        self.assertEqual(health.provider_count, 1)
        self.assertEqual(health.configured_provider_count, 1)
        self.assertEqual(health.enabled_provider_count, 1)
        self.assertEqual(health.role_count, 1)
        self.assertEqual(health.recommendations, [])
        self.assertTrue(health.core_runtime_reachable)
        self.assertEqual(health.core_runtime_status, "connected")

    def test_runtime_health_degrades_when_core_is_offline_but_backend_is_usable(self) -> None:
        settings = Settings(
            _env_file=None,
            DEFAULT_WORKSPACE="workspace",
            AEGIS_MODEL_API="test",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:9999",
            AEGIS_MODEL_NAME="test-model",
            AEGIS_DATABASE_PATH="data/test.sqlite3",
            AEGIS_ROUTER_EXECUTION_ENABLED=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch.object(main, "settings", settings),
                patch.object(main, "PROJECT_ROOT", project_root),
                patch.object(main, "agent", FakeAgent()),
                patch.object(main, "workspace_manager", FakeWorkspaceManager(project_root)),
                patch.object(main, "model_registry", FakeRegistry()),
                patch.object(main, "core_bridge", OfflineCoreBridge()),
                patch.object(main, "has_env_file", lambda: True),
            ):
                health = asyncio.run(main.runtime_health_snapshot())

        self.assertTrue(health.ok)
        self.assertTrue(health.ready)
        self.assertEqual(health.status, "degraded")
        self.assertFalse(health.core_runtime_reachable)
        self.assertEqual(health.core_runtime_status, "unavailable")
        self.assertTrue(any("local fallback mode" in item for item in health.recommendations))


if __name__ == "__main__":
    unittest.main()
