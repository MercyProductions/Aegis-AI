from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
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


if __name__ == "__main__":
    unittest.main()
