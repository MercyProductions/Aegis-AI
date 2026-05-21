from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.providers.accounts.cli_bridge import CliBridgeAdapter
from aegis_ai.providers.accounts.agent_bridge import AgentBridgeRunner
from aegis_ai.providers.accounts.manager import ProviderAccountManager
from aegis_ai.providers.accounts.models import (
    ProviderAccountManifest,
    ProviderApiKeyLinkRequest,
    ProviderCliBridgeManifest,
    ProviderLinkedAccount,
    ProviderSourceRefreshRequest,
)
from aegis_ai.schemas import AgentBridgeExecuteRequest
from aegis_ai.settings import Settings
from aegis_ai.storage_schema import ensure_provider_account_schema


class MemoryVault:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.available = True

    def write_secret(self, ref: str, secret: str) -> None:
        self.values[ref] = secret

    def read_secret(self, ref: str) -> str | None:
        return self.values.get(ref)

    def delete_secret(self, ref: str) -> bool:
        return self.values.pop(ref, None) is not None


class ProviderAccountTests(unittest.TestCase):
    def test_provider_account_schema_is_idempotent_and_extends_attempt_telemetry(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            create table model_attempt_telemetry (
                id text primary key,
                task_id text not null,
                created_at text not null,
                workspace_root text not null,
                attempt_number integer not null,
                role text not null,
                provider_id text not null,
                provider_label text not null,
                provider_api text not null,
                model text not null,
                endpoint text not null,
                privacy_mode text not null,
                status text not null,
                retryable integer not null,
                input_tokens integer,
                output_tokens integer,
                estimated_cost_usd real,
                latency_ms integer,
                reason text not null,
                error text not null,
                metadata_json text not null
            )
            """
        )

        ensure_provider_account_schema(conn)
        ensure_provider_account_schema(conn)

        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type = 'table'")}
        columns = {row["name"] for row in conn.execute("pragma table_info(model_attempt_telemetry)")}
        self.assertIn("provider_accounts", tables)
        self.assertIn("provider_sessions", tables)
        self.assertIn("provider_cli_bridges", tables)
        self.assertIn("routing_runs", tables)
        self.assertIn("provider_account_id", columns)
        self.assertIn("routing_run_id", columns)
        self.assertIn("limit_class", columns)

    def test_api_key_link_stores_only_credential_reference_in_sqlite(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = MemoryVault()
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=vault)

            response = manager.link_api_key(
                "openai",
                ProviderApiKeyLinkRequest(api_key="sk-test-secret-value", account_label="Work API"),
            )

            self.assertEqual(response.account.provider_id, "openai")
            self.assertEqual(response.account.status, "linked")
            self.assertIn(response.account.credential_ref, vault.values)
            conn = sqlite3.connect(Path(temp_dir) / "data" / "aegis.db")
            try:
                rows = conn.execute("select * from provider_accounts").fetchall()
            finally:
                conn.close()
            serialized_rows = repr(rows)
            self.assertNotIn("sk-test-secret-value", serialized_rows)
            self.assertIn("ending alue", response.account.credential_hint)
            openai_status = next(provider for provider in response.snapshot.providers if provider.manifest.id == "openai")
            self.assertEqual(openai_status.route_safety.route_type, "api_key")
            self.assertEqual(openai_status.route_safety.secret_storage, "os_credential_store")
            self.assertTrue(openai_status.route_safety.cloud_context_requires_consent)
            self.assertTrue(openai_status.route_safety.sends_workspace_context)
            self.assertTrue(openai_status.route_safety.diagnostics_safe)
            self.assertNotIn("sk-test-secret-value", response.snapshot.model_dump_json())
            self.assertIn("os_credential_store", response.snapshot.model_dump_json())

    def test_execution_environment_reads_linked_key_only_at_runtime(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = MemoryVault()
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=vault)
            manager.link_api_key(
                "openai",
                ProviderApiKeyLinkRequest(api_key="sk-runtime-secret-value", account_label="Runtime API"),
            )
            manifest = next(item for item in manager.manifests() if item.id == "openai")

            env = manager.execution_environment(manifest)

            self.assertEqual(env, {"OPENAI_API_KEY": "sk-runtime-secret-value"})

    def test_local_runtime_accounts_surface_active_model_without_secrets(self) -> None:
        settings = Settings(
            _env_file=None,
            aegis_database_path="data/aegis.db",
            AEGIS_MODEL_API="ollama",
            AEGIS_MODEL_ENDPOINT="http://127.0.0.1:11434",
            AEGIS_MODEL_NAME="qwen2.5-coder:7b",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())

            snapshot = manager.snapshot()

            ollama = next(provider for provider in snapshot.providers if provider.manifest.id == "ollama")
            self.assertIsNotNone(ollama.account)
            assert ollama.account is not None
            self.assertEqual(ollama.connection_status, "linked")
            self.assertEqual(ollama.account.auth_mode, "none")
            self.assertEqual(ollama.account.credential_ref, "")
            self.assertEqual(ollama.account.credential_hint, "no credentials required")
            self.assertTrue(ollama.account.metadata["active"])
            self.assertEqual(ollama.account.metadata["model_name"], "qwen2.5-coder:7b")
            self.assertTrue(ollama.execution_ready)
            self.assertEqual(ollama.readiness, "local_ready")
            self.assertIn("local runtime", ollama.readiness_detail.lower())
            self.assertGreater(ollama.routing_weight, 0)
            self.assertEqual(ollama.route_safety.route_type, "local_endpoint")
            self.assertEqual(ollama.route_safety.secret_storage, "none")
            self.assertFalse(ollama.route_safety.cloud_context_requires_consent)
            self.assertFalse(ollama.route_safety.sends_workspace_context)
            self.assertIn(ollama.account.account_id, {account.account_id for account in snapshot.accounts})

    def test_route_safety_redacts_secret_like_readiness_errors(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manifest = ProviderAccountManifest(
                id="fake",
                label="Fake Cloud",
                kind="cloud",
                auth_modes=["api_key"],
                default_auth_mode="api_key",
                credential_env_vars=["FAKE_API_KEY"],
            )
            account = ProviderLinkedAccount(
                account_id="fake:api_key",
                provider_id="fake",
                provider_label="Fake Cloud",
                auth_mode="api_key",
                status="error",
                last_error="request failed api_key=sk-phase30-secret-value Authorization: Bearer eyJphase30.secret",
            )

            status = manager._provider_status(manifest, account=account, cli_bridge=None)
            serialized_status = status.model_dump_json()

            self.assertFalse(status.execution_ready)
            self.assertEqual(status.route_safety.secret_storage, "os_credential_store")
            self.assertTrue(status.route_safety.cloud_context_requires_consent)
            self.assertTrue(status.route_safety.diagnostics_safe)
            self.assertIn("[redacted]", status.readiness_detail)
            self.assertNotIn("sk-phase30-secret-value", serialized_status)
            self.assertNotIn("eyJphase30.secret", serialized_status)

    def test_cli_bridge_probe_classifies_logged_in_status_without_token_import(self) -> None:
        manifest = ProviderAccountManifest(
            id="fake",
            label="Fake CLI",
            auth_modes=["cli_bridge"],
            default_auth_mode="cli_bridge",
            cli_bridge=ProviderCliBridgeManifest(
                cli_name="Python",
                candidate_binaries=[sys.executable],
                version_args=["--version"],
                status_args=["-c", "print('Logged in using test account')"],
                delegation_modes=["exec"],
            ),
        )

        info = CliBridgeAdapter(timeout_seconds=4).probe(manifest)

        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.provider_id, "fake")
        self.assertEqual(info.auth_status, "linked")
        self.assertEqual(info.status, "linked")
        self.assertEqual(info.metadata["delegation_policy"], "delegate_only_no_token_import")

    def test_agent_bridge_prepares_normalized_pinned_context_metadata(self) -> None:
        manifest = ProviderAccountManifest(
            id="openai",
            label="OpenAI",
            auth_modes=["cli_bridge"],
            default_auth_mode="cli_bridge",
            cli_bridge=ProviderCliBridgeManifest(
                cli_name="Python",
                candidate_binaries=[sys.executable],
                version_args=["--version"],
                delegation_modes=["exec"],
            ),
        )
        request = AgentBridgeExecuteRequest(
            provider_id="openai",
            message="summarize the pinned files",
            workspace_root=".",
            mode="review",
            context_paths=[
                "@src/App.tsx",
                "./backend/aegis_ai/main.py",
                "../outside.txt",
                "C:/outside.txt",
                "src/App.tsx",
            ],
        )

        prepared = AgentBridgeRunner(CliBridgeAdapter(timeout_seconds=4)).prepare_command(
            manifest,
            request,
            Path.cwd(),
        )

        self.assertIsNotNone(prepared)
        assert prepared is not None
        self.assertEqual(prepared.metadata["mode"], "review")
        self.assertEqual(prepared.metadata["context_paths"], ["src/App.tsx", "backend/aegis_ai/main.py"])
        self.assertEqual(prepared.metadata["context_path_count"], 2)
        self.assertIn('approval_policy="never"', prepared.command)
        self.assertNotIn("--ask-for-approval", prepared.command)
        self.assertIn("[prompt omitted]", prepared.display_command)

    def test_agent_bridge_preflight_signature_requires_matching_reviewed_request(self) -> None:
        from fastapi import HTTPException

        from aegis_ai import main as app_main

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = ProviderAccountManifest(
                id="openai",
                label="OpenAI",
                auth_modes=["cli_bridge"],
                default_auth_mode="cli_bridge",
                cli_bridge=ProviderCliBridgeManifest(
                    cli_name="Python",
                    candidate_binaries=[sys.executable],
                    version_args=["--version"],
                    delegation_modes=["exec"],
                ),
            )
            request = AgentBridgeExecuteRequest(
                provider_id="openai",
                message="please inspect this run",
                workspace_root=str(root),
                mode="review",
                model="gpt-5.5",
                allow_edits=False,
                context_paths=["src/App.tsx"],
                timeout_seconds=240,
            )

            preflight = app_main._agent_bridge_preflight_response(request, manifest, root)
            self.assertTrue(preflight.ok)
            self.assertEqual(preflight.status, "ready")
            self.assertTrue(preflight.preflight_signature)

            approved = request.model_copy(update={"preflight_signature": preflight.preflight_signature})
            confirmed = app_main._require_agent_bridge_preflight(approved, manifest, root)
            self.assertEqual(confirmed.preflight_signature, preflight.preflight_signature)

            stale = approved.model_copy(update={"mode": "build"})
            with self.assertRaises(HTTPException) as raised:
                app_main._require_agent_bridge_preflight(stale, manifest, root)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn("Preflight again", str(raised.exception.detail))

            with self.assertRaises(HTTPException) as missing:
                app_main._require_agent_bridge_preflight(request, manifest, root)
            self.assertEqual(missing.exception.status_code, 428)

    def test_cli_bridge_probe_can_use_source_drop_command_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = ProviderAccountManifest(
                id="source",
                label="Source CLI",
                auth_modes=["cli_bridge"],
                default_auth_mode="cli_bridge",
                cli_bridge=ProviderCliBridgeManifest(
                    cli_name="Source",
                    candidate_binaries=["definitely-not-installed-aegis-test-cli"],
                    version_args=["--version"],
                    delegation_modes=["prompt"],
                ),
                metadata={
                    "source_bridge": {
                        "prefer_source": True,
                        "root_candidates": [temp_dir],
                        "command_candidates": [
                            {
                                "label": "Python source shim",
                                "cwd": ".",
                                "command": [sys.executable],
                                "version_args": ["-c", "print('source cli 1.0')"],
                            }
                        ],
                    }
                },
            )

            info = CliBridgeAdapter(timeout_seconds=4).probe(manifest)

        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.version, "source cli 1.0")
        self.assertEqual(info.metadata["detected_from"], "source_drop")
        self.assertIn("Python source shim", info.binary_path)

    def test_source_drop_freshness_marks_folder_changed_after_probe(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "AI"
            source_dir = source_root / "fake"
            source_dir.mkdir(parents=True)
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["cli_bridge"],
                        "default_auth_mode": "cli_bridge",
                        "cli_bridge": {
                            "cli_name": "Fake",
                            "candidate_binaries": ["definitely-not-installed-aegis-test-cli"],
                            "version_args": ["--version"],
                            "delegation_modes": ["prompt"],
                        },
                        "metadata": {
                            "source_bridge": {
                                "prefer_source": True,
                                "root_candidates": [str(source_root)],
                                "command_candidates": [
                                    {
                                        "label": "Fake source shim",
                                        "cwd": "fake",
                                        "command": [sys.executable],
                                        "version_args": ["-c", "print('fake cli 1.0')"],
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manager.manifest_dir = manifest_dir

            snapshot = manager.probe_cli_bridges()
            drop = snapshot.source_drops[0]
            root = next(item for item in snapshot.source_roots if Path(item.path) == source_root)
            self.assertEqual(drop.freshness, "current")
            self.assertEqual(root.freshness, "current")

            future = time.time() + 5
            os.utime(source_dir, (future, future))

            refreshed = manager.snapshot()
            drop = refreshed.source_drops[0]
            root = next(item for item in refreshed.source_roots if Path(item.path) == source_root)
            self.assertEqual(drop.freshness, "changed")
            self.assertTrue(drop.updated_after_probe)
            self.assertEqual(drop.freshness_label, "Update Detected")
            self.assertEqual(root.freshness, "changed")
            self.assertTrue(root.updated_after_probe)

    def test_source_refresh_action_runs_manifest_command_and_reprobes(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "AI"
            source_dir = source_root / "fake"
            source_dir.mkdir(parents=True)
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["cli_bridge"],
                        "default_auth_mode": "cli_bridge",
                        "cli_bridge": {
                            "cli_name": "Fake",
                            "candidate_binaries": ["definitely-not-installed-aegis-test-cli"],
                            "version_args": ["--version"],
                            "delegation_modes": ["prompt"],
                        },
                        "metadata": {
                            "source_bridge": {
                                "prefer_source": True,
                                "root_candidates": [str(source_root)],
                                "command_candidates": [
                                    {
                                        "label": "Fake source shim",
                                        "cwd": "fake",
                                        "command": [sys.executable],
                                        "version_args": ["-c", "print('fake cli 1.0')"],
                                    }
                                ],
                                "refresh_commands": [
                                    {
                                        "id": "write-build-marker",
                                        "label": "Write build marker",
                                        "cwd": "fake",
                                        "command": [
                                            sys.executable,
                                            "-c",
                                            "from pathlib import Path; Path('built.txt').write_text('ok', encoding='utf-8')",
                                        ],
                                        "timeout_seconds": 20,
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manager.manifest_dir = manifest_dir

            initial = manager.snapshot()
            drop = initial.source_drops[0]
            self.assertEqual(drop.refresh_actions[0].id, "write-build-marker")
            self.assertTrue(drop.refresh_actions[0].available)

            response = manager.refresh_source_drop(
                ProviderSourceRefreshRequest(
                    provider_id="fake",
                    action_id="write-build-marker",
                    source_root=str(source_root),
                    source_candidate="fake",
                )
            )

            self.assertTrue(response.ok)
            self.assertEqual(response.status, "completed")
            self.assertTrue((source_dir / "built.txt").exists())
            self.assertIsNotNone(response.snapshot)
            assert response.snapshot is not None
            refreshed_drop = response.snapshot.source_drops[0]
            self.assertEqual(refreshed_drop.version, "fake cli 1.0")
            self.assertEqual(refreshed_drop.freshness, "current")

    def test_source_refresh_job_runs_in_background_and_persists_result(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "AI"
            source_dir = source_root / "fake"
            source_dir.mkdir(parents=True)
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["cli_bridge"],
                        "default_auth_mode": "cli_bridge",
                        "cli_bridge": {
                            "cli_name": "Fake",
                            "candidate_binaries": ["definitely-not-installed-aegis-test-cli"],
                            "version_args": ["--version"],
                            "delegation_modes": ["prompt"],
                        },
                        "metadata": {
                            "source_bridge": {
                                "prefer_source": True,
                                "root_candidates": [str(source_root)],
                                "command_candidates": [
                                    {
                                        "label": "Fake source shim",
                                        "cwd": "fake",
                                        "command": [sys.executable],
                                        "version_args": ["-c", "print('fake cli 1.0')"],
                                    }
                                ],
                                "refresh_commands": [
                                    {
                                        "id": "write-job-marker",
                                        "label": "Write job marker",
                                        "cwd": "fake",
                                        "command": [
                                            sys.executable,
                                            "-c",
                                            "from pathlib import Path; Path('job-built.txt').write_text('ok', encoding='utf-8')",
                                        ],
                                        "timeout_seconds": 20,
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manager.manifest_dir = manifest_dir

            async def run_job() -> None:
                response = manager.start_source_refresh_job(
                    ProviderSourceRefreshRequest(
                        provider_id="fake",
                        action_id="write-job-marker",
                        source_root=str(source_root),
                        source_candidate="fake",
                    )
                )
                self.assertEqual(response.job.status, "queued")
                for _ in range(80):
                    job = manager.source_refresh_job(response.job.id)
                    if job.status in {"completed", "failed", "timed_out"}:
                        break
                    await asyncio.sleep(0.05)
                job = manager.source_refresh_job(response.job.id)
                self.assertEqual(job.status, "completed")
                self.assertEqual(job.exit_code, 0)
                self.assertTrue((source_dir / "job-built.txt").exists())
                self.assertEqual(manager.source_refresh_jobs()[0].id, job.id)

            asyncio.run(run_job())

    def test_source_refresh_job_streams_output_and_can_cancel(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "AI"
            source_dir = source_root / "fake"
            source_dir.mkdir(parents=True)
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["cli_bridge"],
                        "default_auth_mode": "cli_bridge",
                        "cli_bridge": {
                            "cli_name": "Fake",
                            "candidate_binaries": ["definitely-not-installed-aegis-test-cli"],
                            "version_args": ["--version"],
                            "delegation_modes": ["prompt"],
                        },
                        "metadata": {
                            "source_bridge": {
                                "prefer_source": True,
                                "root_candidates": [str(source_root)],
                                "command_candidates": [
                                    {
                                        "label": "Fake source shim",
                                        "cwd": "fake",
                                        "command": [sys.executable],
                                        "version_args": ["-c", "print('fake cli 1.0')"],
                                    }
                                ],
                                "refresh_commands": [
                                    {
                                        "id": "slow-build",
                                        "label": "Slow build",
                                        "cwd": "fake",
                                        "command": [
                                            sys.executable,
                                            "-c",
                                            "import time; print('live-start', flush=True); time.sleep(10); print('live-end', flush=True)",
                                        ],
                                        "timeout_seconds": 30,
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manager.manifest_dir = manifest_dir

            async def run_job() -> None:
                response = manager.start_source_refresh_job(
                    ProviderSourceRefreshRequest(
                        provider_id="fake",
                        action_id="slow-build",
                        source_root=str(source_root),
                        source_candidate="fake",
                    )
                )
                for _ in range(80):
                    job = manager.source_refresh_job(response.job.id)
                    if "live-start" in job.stdout:
                        break
                    await asyncio.sleep(0.05)
                job = manager.source_refresh_job(response.job.id)
                self.assertIn("live-start", job.stdout)
                self.assertIn(job.status, {"running", "completed"})

                cancel_response = manager.cancel_source_refresh_job(job.id)
                self.assertIn(cancel_response.job.status, {"running", "canceled"})
                for _ in range(80):
                    job = manager.source_refresh_job(response.job.id)
                    if job.status == "canceled":
                        break
                    await asyncio.sleep(0.05)
                job = manager.source_refresh_job(response.job.id)
                self.assertEqual(job.status, "canceled")
                self.assertIn("cancel", job.message.lower())

            asyncio.run(run_job())

    def test_source_refresh_job_retry_starts_new_job_from_terminal_job(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "AI"
            source_dir = source_root / "fake"
            source_dir.mkdir(parents=True)
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["cli_bridge"],
                        "default_auth_mode": "cli_bridge",
                        "cli_bridge": {
                            "cli_name": "Fake",
                            "candidate_binaries": ["definitely-not-installed-aegis-test-cli"],
                            "version_args": ["--version"],
                            "delegation_modes": ["prompt"],
                        },
                        "metadata": {
                            "source_bridge": {
                                "prefer_source": True,
                                "root_candidates": [str(source_root)],
                                "command_candidates": [
                                    {
                                        "label": "Fake source shim",
                                        "cwd": "fake",
                                        "command": [sys.executable],
                                        "version_args": ["-c", "print('fake cli 1.0')"],
                                    }
                                ],
                                "refresh_commands": [
                                    {
                                        "id": "failing-build",
                                        "label": "Failing build",
                                        "cwd": "fake",
                                        "command": [
                                            sys.executable,
                                            "-c",
                                            "import sys; print('retry-start', flush=True); sys.exit(7)",
                                        ],
                                        "timeout_seconds": 20,
                                    }
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=MemoryVault())
            manager.manifest_dir = manifest_dir

            async def run_job() -> None:
                response = manager.start_source_refresh_job(
                    ProviderSourceRefreshRequest(
                        provider_id="fake",
                        action_id="failing-build",
                        source_root=str(source_root),
                        source_candidate="fake",
                    )
                )
                for _ in range(80):
                    job = manager.source_refresh_job(response.job.id)
                    if job.status == "failed":
                        break
                    await asyncio.sleep(0.05)
                job = manager.source_refresh_job(response.job.id)
                self.assertEqual(job.status, "failed")
                self.assertEqual(job.exit_code, 7)
                self.assertIn("retry-start", job.stdout)

                retry_response = manager.retry_source_refresh_job(job.id)
                self.assertNotEqual(retry_response.job.id, job.id)
                self.assertEqual(retry_response.job.metadata.get("retry_of"), job.id)
                for _ in range(80):
                    retry_job = manager.source_refresh_job(retry_response.job.id)
                    if retry_job.status == "failed":
                        break
                    await asyncio.sleep(0.05)
                retry_job = manager.source_refresh_job(retry_response.job.id)
                self.assertEqual(retry_job.status, "failed")

            asyncio.run(run_job())

    def test_cli_session_link_records_no_secret_and_suppresses_api_env_for_cli(self) -> None:
        settings = Settings(_env_file=None, aegis_database_path="data/aegis.db")
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_dir = Path(temp_dir) / "manifests"
            manifest_dir.mkdir()
            manifest_dir.joinpath("fake.json").write_text(
                json.dumps(
                    {
                        "id": "fake",
                        "label": "Fake CLI",
                        "auth_modes": ["api_key", "cli_bridge"],
                        "default_auth_mode": "api_key",
                        "credential_env_vars": ["FAKE_API_KEY"],
                        "cli_bridge": {
                            "cli_name": "Python",
                            "candidate_binaries": [sys.executable],
                            "version_args": ["--version"],
                            "status_args": ["-c", "print('Logged in using test account')"],
                            "login_args": ["-c", "print('login')"],
                            "delegation_modes": ["exec"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            vault = MemoryVault()
            manager = ProviderAccountManager(Path(temp_dir), settings, vault=vault)
            manager.manifest_dir = manifest_dir

            manager.link_api_key("fake", ProviderApiKeyLinkRequest(api_key="fake-secret-value", account_label="API"))
            response = manager.link_cli_session("fake")
            manifest = manager.manifests()[0]

            self.assertEqual(response.account.provider_id, "fake")
            self.assertEqual(response.account.auth_mode, "cli_bridge")
            self.assertEqual(response.account.status, "linked")
            self.assertEqual(response.account.credential_ref, "")
            self.assertEqual(response.account.credential_hint, "official CLI session")
            self.assertEqual(manager.execution_environment(manifest), {})
            fake_status = next(provider for provider in response.snapshot.providers if provider.manifest.id == "fake")
            self.assertTrue(fake_status.execution_ready)
            self.assertEqual(fake_status.readiness, "account_ready")
            self.assertEqual(fake_status.quota_status, "provider_managed")
            self.assertEqual(fake_status.route_safety.route_type, "cli_bridge")
            self.assertEqual(fake_status.route_safety.secret_storage, "provider_cli_only")
            self.assertIn("does not import provider token files", fake_status.route_safety.secret_policy)

            conn = sqlite3.connect(Path(temp_dir) / "data" / "aegis.db")
            try:
                rows = conn.execute("select * from provider_accounts").fetchall()
                session_rows = conn.execute("select * from provider_sessions").fetchall()
            finally:
                conn.close()
            serialized_rows = repr(rows) + repr(session_rows)
            self.assertNotIn("fake-secret-value", serialized_rows)
            self.assertIn("token_files_read", serialized_rows)
            self.assertIn("official CLI session", serialized_rows)

    def test_agent_bridge_display_command_redacts_prompt_but_preserves_model(self) -> None:
        runner = AgentBridgeRunner(CliBridgeAdapter(timeout_seconds=4))

        display = runner._display_command(
            [
                "node",
                "bundle.js",
                "--prompt",
                "secret user prompt",
                "--output-format",
                "text",
                "--model",
                "gemini-3.5-flash",
            ]
        )

        self.assertIn("[prompt omitted]", display)
        self.assertIn("gemini-3.5-flash", display)
        self.assertNotIn("secret user prompt", display)

    def test_agent_bridge_stream_redaction_preserves_chunk_spacing(self) -> None:
        runner = AgentBridgeRunner(CliBridgeAdapter(timeout_seconds=4))

        redacted = runner.redact_output(" first line\napi_key=sk-test-secret-value\n")

        self.assertTrue(redacted.startswith(" first line\n"))
        self.assertTrue(redacted.endswith("\n"))
        self.assertIn("[redacted]", redacted)
        self.assertNotIn("sk-test-secret-value", redacted)


if __name__ == "__main__":
    unittest.main()
