from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.core_bridge import CoreBridgeResult
from aegis_ai.llm import LocalModelClient
from aegis_ai.llm import LocalModelInventory, LocalModelRecord
from aegis_ai.model_registry import ModelRegistryManager
from aegis_ai.providers.base import provider_capability_flags
from aegis_ai.schemas import ModelRegistryProviderUpsertRequest
from aegis_ai.settings import Settings


class ModelInventoryTests(unittest.TestCase):
    def test_unsupported_model_api_returns_configured_model_record(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="custom-runtime",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:9999",
            AEGIS_MODEL_NAME="custom-model",
        )
        client = LocalModelClient(settings)

        inventory = asyncio.run(client.inventory())

        self.assertEqual(inventory.active_api, "custom-runtime")
        self.assertEqual(inventory.active_model, "custom-model")
        self.assertEqual(len(inventory.models), 1)
        self.assertTrue(inventory.models[0].configured)
        self.assertFalse(inventory.models[0].ready)
        self.assertIn("unsupported", inventory.models[0].message.lower())

    def test_cloud_openai_provider_requires_env_key(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="openai",
            AEGIS_MODEL_ENDPOINT="https://api.openai.com/v1",
            AEGIS_MODEL_NAME="configured-cloud-model",
        )
        client = LocalModelClient(settings)

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            status = asyncio.run(client.status())

        self.assertFalse(status.ready)
        self.assertIn("OPENAI_API_KEY", status.message)

    def test_cloud_openai_inventory_uses_env_key_without_model_listing(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="openai",
            AEGIS_MODEL_ENDPOINT="https://api.openai.com/v1",
            AEGIS_MODEL_NAME="configured-cloud-model",
        )
        client = LocalModelClient(settings)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            inventory = asyncio.run(client.inventory())

        self.assertEqual(inventory.active_api, "openai")
        self.assertEqual(len(inventory.models), 1)
        self.assertEqual(inventory.models[0].name, "configured-cloud-model")
        self.assertFalse(inventory.models[0].local)
        self.assertTrue(inventory.models[0].ready)

    def test_inventory_infers_creative_and_realtime_capabilities(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="openai",
            AEGIS_MODEL_ENDPOINT="https://api.openai.com/v1",
            AEGIS_MODEL_NAME="gpt-image-1-realtime",
        )
        client = LocalModelClient(settings)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            inventory = asyncio.run(client.inventory())

        capabilities = inventory.models[0].capabilities or {}
        self.assertTrue(capabilities["image"])
        self.assertTrue(capabilities["realtime"])
        self.assertTrue(capabilities["tools"])

    def test_capability_inference_marks_coder_models_for_code_routes(self) -> None:
        capabilities = provider_capability_flags(
            "ollama",
            "http://127.0.0.1:11434",
            "qwen2.5-coder:7b",
            ["chat", "structured_json"],
        )

        self.assertTrue(capabilities["code"])
        self.assertTrue(capabilities["debug"])
        self.assertTrue(capabilities["refactor"])

    def test_anthropic_provider_uses_anthropic_env_key(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="anthropic",
            AEGIS_MODEL_ENDPOINT="https://api.anthropic.com",
            AEGIS_MODEL_NAME="configured-claude-model",
        )
        client = LocalModelClient(settings)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            status = asyncio.run(client.status())

        self.assertTrue(status.ready)
        self.assertIn("Anthropic", status.message)

    def test_model_registry_includes_active_provider_and_core_roles(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = ModelRegistryManager(Path(temp_dir), settings).snapshot()

        self.assertEqual(registry.active_provider_id, "ollama:active")
        self.assertTrue(registry.fallback_supported)
        self.assertGreaterEqual(len(registry.providers), 3)
        self.assertIn("chat", {role.id for role in registry.roles})
        self.assertIn("code", {role.id for role in registry.roles})
        self.assertIn("balanced", {preset.id for preset in registry.presets})

    def test_model_registry_can_upsert_and_delete_provider(self) -> None:
        settings = Settings(
            _env_file=None,
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelRegistryManager(Path(temp_dir), settings)
            registry = manager.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="image:local",
                    label="Local Image Lab",
                    api="mock",
                    endpoint="http://127.0.0.1:9998",
                    local=True,
                    enabled=True,
                    configured=False,
                    capabilities=["image", "image", "gif"],
                    roles=["image", "creative_judge"],
                    health="planned",
                    notes="Test provider.",
                )
            )
            provider_ids = {provider.id for provider in registry.providers}
            self.assertIn("image:local", provider_ids)
            image_provider = next(provider for provider in registry.providers if provider.id == "image:local")
            self.assertEqual(image_provider.capabilities, ["image", "gif"])

            registry = manager.delete_provider("image:local")

        self.assertNotIn("image:local", {provider.id for provider in registry.providers})

    def test_models_endpoint_overlays_core_inventory_without_replacing_website_shape(self) -> None:
        settings = Settings(
            _env_file=None,
            DEFAULT_WORKSPACE="workspace",
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )

        class FakeAgent:
            async def model_inventory(self) -> LocalModelInventory:
                return LocalModelInventory(
                    active_model="qwen2.5-coder:7b",
                    active_api="ollama",
                    active_endpoint="http://127.0.0.1:11434",
                    message="Website inventory ready.",
                    models=[
                        LocalModelRecord(
                            id="ollama:qwen2.5-coder:7b",
                            name="qwen2.5-coder:7b",
                            provider="Ollama",
                            api="ollama",
                            endpoint="http://127.0.0.1:11434",
                            local=True,
                            configured=True,
                            available=True,
                            ready=True,
                            message="Configured model ready.",
                        )
                    ],
                )

        class FakeWorkspaceManager:
            def __init__(self, root: Path):
                self.root = root

            def resolve_workspace(self, workspace_root: str | None) -> Path:
                path = self.root / (workspace_root or "workspace")
                path.mkdir(parents=True, exist_ok=True)
                return path

        class FakeCoreBridge:
            async def model_status(self, workspace: Path) -> CoreBridgeResult:
                data = {
                    "reachable": True,
                    "installed_models": ["qwen2.5-coder:7b", "qwen3-coder:30b"],
                    "selected_model": "qwen3-coder:30b",
                }
                return CoreBridgeResult(
                    True,
                    True,
                    200,
                    "models",
                    data,
                    {
                        "ok": True,
                        "api_version": "v1",
                        "contract_version": "2026.05.09",
                        "kind": "models",
                        "data": data,
                    },
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with (
                patch.object(main, "settings", settings),
                patch.object(main, "PROJECT_ROOT", project_root),
                patch.object(main, "agent", FakeAgent()),
                patch.object(main, "workspace_manager", FakeWorkspaceManager(project_root)),
                patch.object(main, "model_registry", ModelRegistryManager(project_root, settings)),
                patch.object(main, "core_bridge", FakeCoreBridge()),
                TestClient(main.app) as client,
            ):
                response = client.get("/api/models")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["active_model"], "qwen2.5-coder:7b")
        self.assertEqual(payload["core_runtime_status"], "connected")
        model_ids = {item["id"] for item in payload["models"]}
        self.assertIn("ollama:qwen2.5-coder:7b", model_ids)
        self.assertIn("aegis-core:qwen3-coder:30b", model_ids)


if __name__ == "__main__":
    unittest.main()
