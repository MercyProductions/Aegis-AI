from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.core_bridge import CoreBridgeResult
from aegis_ai.schemas import AppConfig
from aegis_ai.settings import Settings


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        aegis_assistant_name="Existing Bot",
        aegis_assistant_mission="Existing mission",
        default_mode="review",
        default_workspace="old-workspace",
        aegis_model_api="ollama",
        aegis_model_endpoint="http://127.0.0.1:11434/",
        aegis_model_name="existing-model",
        aegis_database_path="data/test.sqlite3",
        aegis_command_allowlist="python,node,npm",
        aegis_command_timeout_seconds=321,
        aegis_auto_run_validation=True,
        aegis_shared_workspace_mode=True,
        aegis_feedback_capture_excerpts=False,
        aegis_feedback_redaction_enabled=False,
        aegis_feedback_max_excerpt_chars=777,
        aegis_feedback_hash_content=False,
    )


def _app_config(settings: Settings, workspace: str) -> AppConfig:
    return AppConfig(
        assistant_name=settings.aegis_assistant_name,
        assistant_mission=settings.aegis_assistant_mission,
        default_mode="review",
        default_workspace=workspace,
        engine="Aegis Core / existing-model",
        engine_ready=True,
        engine_message="ready",
        model_name=settings.aegis_model_name,
        model_endpoint=settings.aegis_model_endpoint,
        model_api=settings.aegis_model_api,
        model_ready=True,
        model_message="ready",
        database_path=settings.aegis_database_path,
        command_allowlist=settings.aegis_command_allowlist,
        command_timeout_seconds=settings.aegis_command_timeout_seconds,
        auto_run_validation=settings.aegis_auto_run_validation,
        shared_workspace_mode=settings.aegis_shared_workspace_mode,
        feedback_capture_excerpts=settings.aegis_feedback_capture_excerpts,
        feedback_redaction_enabled=settings.aegis_feedback_redaction_enabled,
        feedback_max_excerpt_chars=settings.aegis_feedback_max_excerpt_chars,
        feedback_hash_content=settings.aegis_feedback_hash_content,
        env_exists=True,
    )


class FakeCoreBridge:
    def __init__(self, *, fail_update: bool = False) -> None:
        self.updates: list[dict] = []
        self.fail_update = fail_update

    async def settings_status(self, workspace: Path) -> CoreBridgeResult:
        return CoreBridgeResult(
            True,
            True,
            200,
            "settings",
            {"default_model": "existing-model", "ollama_url": "http://127.0.0.1:11434"},
            {
                "ok": True,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": "settings",
                "data": {"default_model": "existing-model", "ollama_url": "http://127.0.0.1:11434"},
            },
        )

    async def update_settings(self, workspace: Path, settings: dict) -> CoreBridgeResult:
        if self.fail_update:
            raise RuntimeError("Core sync unavailable")
        self.updates.append({"workspace": str(workspace), "settings": settings})
        return CoreBridgeResult(
            True,
            True,
            200,
            "settings.updated",
            settings,
            {
                "ok": True,
                "api_version": "v1",
                "contract_version": "2026.05.09",
                "kind": "settings.updated",
                "data": settings,
            },
        )


class ConfigUpdateTests(unittest.TestCase):
    def test_config_post_accepts_partial_update_and_preserves_existing_values(self) -> None:
        settings = _settings()
        captured: dict[str, str] = {}

        async def fake_config_snapshot() -> AppConfig:
            return _app_config(settings, captured.get("DEFAULT_WORKSPACE", settings.default_workspace))

        fake_core = FakeCoreBridge()
        with (
            patch.object(main, "settings", settings),
            patch.object(main, "update_env", lambda values: captured.update(values)),
            patch.object(main, "refresh_runtime", lambda: None),
            patch.object(main, "config_snapshot", fake_config_snapshot),
            patch.object(main, "core_bridge", fake_core),
            TestClient(main.app) as client,
        ):
            response = client.post("/api/config", json={"default_workspace": "new-workspace"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["default_workspace"], "new-workspace")
        self.assertEqual(captured["DEFAULT_WORKSPACE"], "new-workspace")
        self.assertEqual(captured["AEGIS_ASSISTANT_NAME"], "Existing Bot")
        self.assertEqual(captured["AEGIS_ASSISTANT_MISSION"], "Existing mission")
        self.assertEqual(captured["DEFAULT_MODE"], "review")
        self.assertEqual(captured["AEGIS_MODEL_API"], "ollama")
        self.assertEqual(captured["AEGIS_MODEL_NAME"], "existing-model")
        self.assertEqual(captured["AEGIS_COMMAND_TIMEOUT_SECONDS"], "321")
        self.assertEqual(captured["AEGIS_AUTO_RUN_VALIDATION"], "true")
        self.assertEqual(captured["AEGIS_SHARED_WORKSPACE_MODE"], "true")
        self.assertEqual(captured["AEGIS_FEEDBACK_CAPTURE_EXCERPTS"], "false")
        self.assertEqual(captured["AEGIS_FEEDBACK_REDACTION_ENABLED"], "false")
        self.assertEqual(captured["AEGIS_FEEDBACK_MAX_EXCERPT_CHARS"], "777")
        self.assertEqual(captured["AEGIS_FEEDBACK_HASH_CONTENT"], "false")
        self.assertEqual(fake_core.updates[0]["settings"]["default_model"], "existing-model")

    def test_config_post_preserves_website_save_when_core_sync_raises(self) -> None:
        settings = _settings()
        captured: dict[str, str] = {}

        async def fake_config_snapshot() -> AppConfig:
            return _app_config(settings, captured.get("DEFAULT_WORKSPACE", settings.default_workspace))

        with (
            patch.object(main, "settings", settings),
            patch.object(main, "update_env", lambda values: captured.update(values)),
            patch.object(main, "refresh_runtime", lambda: None),
            patch.object(main, "config_snapshot", fake_config_snapshot),
            patch.object(main, "core_bridge", FakeCoreBridge(fail_update=True)),
            TestClient(main.app) as client,
        ):
            response = client.post("/api/config", json={"default_workspace": "fallback-workspace"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["default_workspace"], "fallback-workspace")
        self.assertEqual(captured["DEFAULT_WORKSPACE"], "fallback-workspace")

    def test_config_post_full_update_still_normalizes_strings(self) -> None:
        settings = _settings()
        captured: dict[str, str] = {}

        async def fake_config_snapshot() -> AppConfig:
            return _app_config(settings, captured.get("DEFAULT_WORKSPACE", settings.default_workspace))

        fake_core = FakeCoreBridge()
        with (
            patch.object(main, "settings", settings),
            patch.object(main, "update_env", lambda values: captured.update(values)),
            patch.object(main, "refresh_runtime", lambda: None),
            patch.object(main, "config_snapshot", fake_config_snapshot),
            patch.object(main, "core_bridge", fake_core),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/config",
                json={
                    "assistant_name": " Updated Bot ",
                    "assistant_mission": "First line\n\nSecond line",
                    "default_mode": "develop",
                    "default_workspace": "workspace-two",
                    "model_api": "OLLAMA",
                    "model_endpoint": "http://127.0.0.1:11434/",
                    "model_name": "new-model",
                    "command_allowlist": "python,node",
                    "command_timeout_seconds": 45,
                    "auto_run_validation": False,
                    "shared_workspace_mode": False,
                    "feedback_capture_excerpts": True,
                    "feedback_redaction_enabled": True,
                    "feedback_max_excerpt_chars": 123,
                    "feedback_hash_content": True,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(captured["AEGIS_ASSISTANT_NAME"], "Updated Bot")
        self.assertEqual(captured["AEGIS_ASSISTANT_MISSION"], "First line Second line")
        self.assertEqual(captured["DEFAULT_MODE"], "develop")
        self.assertEqual(captured["DEFAULT_WORKSPACE"], "workspace-two")
        self.assertEqual(captured["AEGIS_MODEL_API"], "ollama")
        self.assertEqual(captured["AEGIS_MODEL_ENDPOINT"], "http://127.0.0.1:11434")
        self.assertEqual(captured["AEGIS_MODEL_NAME"], "new-model")
        self.assertEqual(captured["AEGIS_COMMAND_ALLOWLIST"], "python,node")
        self.assertEqual(captured["AEGIS_COMMAND_TIMEOUT_SECONDS"], "45")
        self.assertEqual(captured["AEGIS_AUTO_RUN_VALIDATION"], "false")
        self.assertEqual(captured["AEGIS_SHARED_WORKSPACE_MODE"], "false")
        self.assertEqual(captured["AEGIS_FEEDBACK_CAPTURE_EXCERPTS"], "true")
        self.assertEqual(captured["AEGIS_FEEDBACK_REDACTION_ENABLED"], "true")
        self.assertEqual(captured["AEGIS_FEEDBACK_MAX_EXCERPT_CHARS"], "123")
        self.assertEqual(captured["AEGIS_FEEDBACK_HASH_CONTENT"], "true")

    def test_feedback_redaction_handles_provider_oauth_aliases(self) -> None:
        text = "\n".join(
            [
                "access_token=feedback-access-secret",
                "refresh_token: feedback-refresh-secret",
                'client_secret="feedback-client-secret"',
                "private_key=feedback-private-secret",
                "callback=https://provider.test/callback?access_token=feedback-query-secret&x-api-key=feedback-query-key",
            ]
        )

        redacted, count = main._redact_feedback_text(text)

        self.assertGreaterEqual(count, 6)
        self.assertNotIn("feedback-access-secret", redacted)
        self.assertNotIn("feedback-refresh-secret", redacted)
        self.assertNotIn("feedback-client-secret", redacted)
        self.assertNotIn("feedback-private-secret", redacted)
        self.assertNotIn("feedback-query-secret", redacted)
        self.assertNotIn("feedback-query-key", redacted)
        self.assertIn("access_token=[REDACTED_SECRET]", redacted)
        self.assertIn("refresh_token: [REDACTED_SECRET]", redacted)
        self.assertIn('client_secret="[REDACTED_SECRET]"', redacted)
        self.assertIn("private_key=[REDACTED_SECRET]", redacted)
        self.assertIn("access_token=[REDACTED]", redacted)
        self.assertIn("x-api-key=[REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
