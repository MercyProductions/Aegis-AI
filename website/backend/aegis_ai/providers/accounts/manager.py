from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import subprocess
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...diagnostic_redaction import redact_inline
from ...settings import Settings
from ...storage_schema import ensure_provider_account_schema
from ...providers.base import is_local_endpoint
from .cli_bridge import CliBridgeAdapter
from .models import (
    ProviderAccountLinkResponse,
    ProviderAccountManifest,
    ProviderAccountsResponse,
    ProviderAccountStatus,
    ProviderApiKeyLinkRequest,
    ProviderCliBridgeInfo,
    ProviderCliLoginResponse,
    ProviderLinkedAccount,
    ProviderRouteSafety,
    ProviderSessionInfo,
    ProviderSourceDropInfo,
    ProviderSourceRefreshAction,
    ProviderSourceRefreshJobInfo,
    ProviderSourceRefreshJobResponse,
    ProviderSourceRefreshJobsResponse,
    ProviderSourceRefreshRequest,
    ProviderSourceRefreshResponse,
    ProviderSourceRootInfo,
    ProviderSourceRootOpenResponse,
)
from .vault import CredentialVault, CredentialVaultError, credential_ref, safe_error


class ProviderAccountError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


SOURCE_REFRESH_COMMAND_ALLOWLIST = {
    "cargo",
    "cargo.exe",
    "node",
    "node.exe",
    "npm",
    "npm.cmd",
    "npm.exe",
    "npx",
    "npx.cmd",
    "npx.exe",
    "pnpm",
    "pnpm.cmd",
    "pnpm.exe",
    "python",
    "python.exe",
    "py",
    "py.exe",
    "yarn",
    "yarn.cmd",
    "yarn.exe",
}
MAX_SOURCE_REFRESH_JOBS_JSON_BYTES = 1_000_000
MAX_SOURCE_REFRESH_OUTPUT_CHARS = 8_000
SOURCE_REFRESH_TERMINAL_STATUSES = {
    "completed",
    "failed",
    "timed_out",
    "not_configured",
    "unsupported",
    "interrupted",
    "canceled",
}


class ProviderAccountManager:
    def __init__(
        self,
        project_root: Path,
        settings: Settings,
        *,
        vault: CredentialVault | None = None,
        cli_bridge: CliBridgeAdapter | None = None,
    ):
        self.project_root = project_root
        self.settings = settings
        self.db_path = self._resolve_db_path(settings.aegis_database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_refresh_jobs_path = self.db_path.parent / "provider_source_refresh_jobs.json"
        self._source_refresh_lock = threading.RLock()
        self._active_source_refresh_tasks: dict[str, asyncio.Task[None]] = {}
        self._active_source_refresh_processes: dict[str, subprocess.Popen[str]] = {}
        self._source_refresh_cancel_events: dict[str, threading.Event] = {}
        self.vault = vault or CredentialVault()
        self.cli_bridge = cli_bridge or CliBridgeAdapter(project_root=project_root)
        self.manifest_dir = Path(__file__).resolve().parent / "manifests"
        self._init_db()

    def snapshot(self) -> ProviderAccountsResponse:
        manifests = self.manifests()
        accounts = self.accounts()
        local_accounts = [account for account in (self._local_runtime_account(manifest) for manifest in manifests) if account is not None]
        display_accounts = self._merge_display_accounts(accounts, local_accounts)
        sessions = [*self.sessions(), *[self._local_runtime_session(account) for account in local_accounts]]
        cli_bridges = self.cli_bridges()
        account_by_provider = self._preferred_accounts_by_provider(display_accounts)
        bridge_by_provider = {bridge.provider_id: bridge for bridge in cli_bridges}

        providers = [
            self._provider_status(
                manifest,
                account=account_by_provider.get(manifest.id),
                cli_bridge=bridge_by_provider.get(manifest.id),
            )
            for manifest in manifests
        ]
        return ProviderAccountsResponse(
            generated_at=utc_now(),
            credential_store_available=self.vault.available,
            providers=providers,
            accounts=display_accounts,
            sessions=sessions,
            cli_bridges=cli_bridges,
            source_roots=self._source_root_infos(manifests, cli_bridges),
            source_drops=self._source_drop_infos(manifests, cli_bridges),
            source_refresh_jobs=self.source_refresh_jobs(limit=8),
            security_notes=[
                "Aegis stores provider secrets only in the OS credential manager or installed keyring backend.",
                "Existing provider CLI sessions are reused by delegation only; token files are never imported or read.",
                "OAuth and device-code flows require Aegis-owned provider app registrations before they are enabled.",
            ],
        )

    def manifests(self) -> list[ProviderAccountManifest]:
        items: list[ProviderAccountManifest] = []
        for path in sorted(self.manifest_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items.append(ProviderAccountManifest.model_validate(payload))
            except Exception:
                continue
        return items

    def accounts(self) -> list[ProviderLinkedAccount]:
        with self._session() as conn:
            rows = conn.execute(
                """
                select account_id, provider_id, provider_label, auth_mode, status, account_label,
                       subject_hash, credential_ref, credential_hint, session_ref, scopes_json,
                       quota_status, expires_at, created_at, updated_at, last_validated_at,
                       last_error, metadata_json
                from provider_accounts
                order by provider_label collate nocase, provider_id
                """
            ).fetchall()
        return [self._account_from_row(row) for row in rows]

    def sessions(self) -> list[ProviderSessionInfo]:
        with self._session() as conn:
            rows = conn.execute(
                """
                select session_id, account_id, provider_id, auth_mode, status, credential_ref,
                       refresh_supported, expires_at, created_at, updated_at, last_refresh_at,
                       last_refresh_error, metadata_json
                from provider_sessions
                order by updated_at desc
                """
            ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def cli_bridges(self) -> list[ProviderCliBridgeInfo]:
        with self._session() as conn:
            rows = conn.execute(
                """
                select provider_id, cli_name, binary_path, version, status, auth_status,
                       probe_command, supported_delegation_modes_json, last_probe_at,
                       last_error, metadata_json
                from provider_cli_bridges
                order by cli_name collate nocase, provider_id
                """
            ).fetchall()
        return [self._cli_bridge_from_row(row) for row in rows]

    def link_api_key(self, provider_id: str, request: ProviderApiKeyLinkRequest) -> ProviderAccountLinkResponse:
        manifest = self._manifest_or_404(provider_id)
        if "api_key" not in manifest.auth_modes:
            raise ProviderAccountError(f"{manifest.label} does not declare API-key linking.", status_code=400)
        if not self.vault.available:
            raise ProviderAccountError("No OS credential store is available for provider API keys.", status_code=503)

        now = utc_now()
        ref = credential_ref(manifest.id, "api_key")
        try:
            self.vault.write_secret(ref, request.api_key)
        except CredentialVaultError as exc:
            raise ProviderAccountError(str(exc), status_code=503) from exc

        account_id = f"{manifest.id}:api_key"
        session_id = f"{account_id}:session"
        hint = self._credential_hint(request.api_key)
        label = request.account_label.strip() or f"{manifest.label} API key {hint}".strip()
        scopes = self._clean_list(request.scopes)
        metadata = {
            "secret_storage": "os_credential_store",
            "auth_boundary": "api_key",
            "raw_secret_persisted_in_sqlite": False,
        }
        with self._session() as conn:
            conn.execute(
                """
                insert into provider_accounts (
                    account_id, provider_id, provider_label, auth_mode, status, account_label,
                    subject_hash, credential_ref, credential_hint, session_ref, scopes_json,
                    quota_status, expires_at, created_at, updated_at, last_validated_at,
                    last_error, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(account_id) do update set
                    provider_label = excluded.provider_label,
                    status = excluded.status,
                    account_label = excluded.account_label,
                    subject_hash = excluded.subject_hash,
                    credential_ref = excluded.credential_ref,
                    credential_hint = excluded.credential_hint,
                    session_ref = excluded.session_ref,
                    scopes_json = excluded.scopes_json,
                    quota_status = excluded.quota_status,
                    updated_at = excluded.updated_at,
                    last_validated_at = excluded.last_validated_at,
                    last_error = excluded.last_error,
                    metadata_json = excluded.metadata_json
                """,
                (
                    account_id,
                    manifest.id,
                    manifest.label,
                    "api_key",
                    "linked",
                    label,
                    self._subject_hash(manifest.id, label, hint),
                    ref,
                    hint,
                    session_id,
                    json.dumps(scopes, ensure_ascii=True),
                    "unknown",
                    "",
                    now,
                    now,
                    now,
                    "",
                    json.dumps(metadata, ensure_ascii=True),
                ),
            )
            conn.execute(
                """
                insert into provider_sessions (
                    session_id, account_id, provider_id, auth_mode, status, credential_ref,
                    refresh_supported, expires_at, created_at, updated_at, last_refresh_at,
                    last_refresh_error, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(session_id) do update set
                    status = excluded.status,
                    credential_ref = excluded.credential_ref,
                    updated_at = excluded.updated_at,
                    last_refresh_error = excluded.last_refresh_error,
                    metadata_json = excluded.metadata_json
                """,
                (
                    session_id,
                    account_id,
                    manifest.id,
                    "api_key",
                    "linked",
                    ref,
                    0,
                    "",
                    now,
                    now,
                    "",
                    "",
                    json.dumps({"refresh": "not_applicable_for_api_key"}, ensure_ascii=True),
                ),
            )

        account = next(item for item in self.accounts() if item.account_id == account_id)
        return ProviderAccountLinkResponse(account=account, snapshot=self.snapshot())

    def unlink_provider(self, provider_id: str) -> ProviderAccountsResponse:
        provider = provider_id.strip()
        if not provider:
            raise ProviderAccountError("Provider id is required.", status_code=400)

        refs: list[str] = []
        with self._session() as conn:
            rows = conn.execute("select credential_ref from provider_accounts where provider_id = ?", (provider,)).fetchall()
            refs = [str(row["credential_ref"] or "") for row in rows if str(row["credential_ref"] or "").strip()]
            conn.execute("delete from provider_sessions where provider_id = ?", (provider,))
            conn.execute("delete from provider_accounts where provider_id = ?", (provider,))

        for ref in refs:
            try:
                self.vault.delete_secret(ref)
            except CredentialVaultError:
                continue
        return self.snapshot()

    def execution_environment(self, manifest: ProviderAccountManifest) -> dict[str, str]:
        """Return provider API-key env only for a linked account at execution time."""
        cli_account = self._linked_cli_account(manifest.id)
        if cli_account is not None:
            return {}

        account = self._linked_api_key_account(manifest.id)
        if account is None:
            return {}

        env_name = self._api_key_env_name(manifest)
        if not env_name:
            return {}

        try:
            secret = self.vault.read_secret(account.credential_ref)
        except CredentialVaultError:
            return {}
        if not secret:
            return {}
        return {env_name: secret}

    def link_cli_session(self, provider_id: str) -> ProviderAccountLinkResponse:
        manifest = self._manifest_or_404(provider_id)
        if manifest.cli_bridge is None or "cli_bridge" not in manifest.auth_modes:
            raise ProviderAccountError(f"{manifest.label} does not declare CLI-session linking.", status_code=400)

        info = self.cli_bridge.probe(manifest)
        if info is None or not info.binary_path:
            raise ProviderAccountError("No runnable CLI or source-drop command was found for this provider.", status_code=404)

        link_status = self._cli_link_status(info)
        if link_status in {"not_configured", "error"}:
            message = info.last_error or f"{manifest.label} CLI is not ready for reuse."
            raise ProviderAccountError(message, status_code=400)

        now = utc_now()
        account_id = f"{manifest.id}:cli_bridge"
        session_id = f"{account_id}:session"
        metadata = {
            "secret_storage": "provider_cli_only",
            "auth_boundary": "official_cli_session",
            "raw_secret_persisted_in_sqlite": False,
            "token_files_read": False,
            "delegation_policy": "delegate_only_no_token_import",
            "cli_binary_path": info.binary_path,
            "cli_version": info.version,
            "cli_status": info.status,
            "cli_auth_status": info.auth_status,
            "probe_command": info.probe_command,
            "last_probe_at": info.last_probe_at,
            **{
                key: value
                for key, value in info.metadata.items()
                if key
                in {
                    "detected_from",
                    "cwd",
                    "source_candidate",
                    "source_root",
                    "login_command",
                    "delegation_policy",
                }
            },
        }
        with self._session() as conn:
            self._store_cli_bridge(conn, info)
            conn.execute(
                """
                insert into provider_accounts (
                    account_id, provider_id, provider_label, auth_mode, status, account_label,
                    subject_hash, credential_ref, credential_hint, session_ref, scopes_json,
                    quota_status, expires_at, created_at, updated_at, last_validated_at,
                    last_error, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(account_id) do update set
                    provider_label = excluded.provider_label,
                    status = excluded.status,
                    account_label = excluded.account_label,
                    subject_hash = excluded.subject_hash,
                    credential_ref = excluded.credential_ref,
                    credential_hint = excluded.credential_hint,
                    session_ref = excluded.session_ref,
                    scopes_json = excluded.scopes_json,
                    quota_status = excluded.quota_status,
                    updated_at = excluded.updated_at,
                    last_validated_at = excluded.last_validated_at,
                    last_error = excluded.last_error,
                    metadata_json = excluded.metadata_json
                """,
                (
                    account_id,
                    manifest.id,
                    manifest.label,
                    "cli_bridge",
                    link_status,
                    f"{manifest.label} CLI session",
                    self._subject_hash(manifest.id, info.binary_path, info.version, "cli_bridge"),
                    "",
                    "official CLI session",
                    session_id,
                    json.dumps(info.supported_delegation_modes, ensure_ascii=True),
                    "provider_managed",
                    "",
                    now,
                    now,
                    now,
                    safe_error(RuntimeError(info.last_error)) if info.last_error else "",
                    json.dumps(metadata, ensure_ascii=True),
                ),
            )
            conn.execute(
                """
                insert into provider_sessions (
                    session_id, account_id, provider_id, auth_mode, status, credential_ref,
                    refresh_supported, expires_at, created_at, updated_at, last_refresh_at,
                    last_refresh_error, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(session_id) do update set
                    status = excluded.status,
                    credential_ref = excluded.credential_ref,
                    updated_at = excluded.updated_at,
                    last_refresh_error = excluded.last_refresh_error,
                    metadata_json = excluded.metadata_json
                """,
                (
                    session_id,
                    account_id,
                    manifest.id,
                    "cli_bridge",
                    link_status,
                    "",
                    0,
                    "",
                    now,
                    now,
                    "",
                    "",
                    json.dumps(
                        {
                            "refresh": "managed_by_provider_cli",
                            "login_command": str(info.metadata.get("login_command") or ""),
                            "probe_command": info.probe_command,
                            "token_files_read": False,
                        },
                        ensure_ascii=True,
                    ),
                ),
            )

        account = next(item for item in self.accounts() if item.account_id == account_id)
        return ProviderAccountLinkResponse(account=account, snapshot=self.snapshot())

    def start_cli_login(self, provider_id: str) -> ProviderCliLoginResponse:
        manifest = self._manifest_or_404(provider_id)
        bridge = manifest.cli_bridge
        if bridge is None:
            return ProviderCliLoginResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="unsupported",
                message=f"{manifest.label} does not declare a CLI login flow.",
                snapshot=self.snapshot(),
            )

        targets = self.cli_bridge.targets_for(manifest)
        if not targets:
            return ProviderCliLoginResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="not_configured",
                message="No runnable CLI or source-drop command was found for this provider.",
                snapshot=self.snapshot(),
            )

        target = targets[0]
        login_args = target.login_args if target.login_args is not None else bridge.login_args
        if not login_args:
            return ProviderCliLoginResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="unsupported",
                message=f"{manifest.label} does not expose an official CLI login command.",
                snapshot=self.snapshot(),
            )

        command = [*target.command, *login_args]
        display = self.cli_bridge._format_command(target, login_args)
        env = os.environ.copy()
        if target.env:
            env.update(target.env)

        try:
            process = subprocess.Popen(
                command,
                cwd=target.cwd or None,
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
        except FileNotFoundError as exc:
            return ProviderCliLoginResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="not_configured",
                command=display,
                cwd=target.cwd,
                message="CLI command was not found.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )
        except (OSError, PermissionError) as exc:
            return ProviderCliLoginResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="failed",
                command=display,
                cwd=target.cwd,
                message="CLI login could not be launched.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )

        return ProviderCliLoginResponse(
            ok=True,
            provider_id=manifest.id,
            provider_label=manifest.label,
            status="launched",
            command=display,
            cwd=target.cwd,
            pid=process.pid,
            message="Official CLI login opened. Finish the provider login there, then probe CLIs again.",
            snapshot=self.snapshot(),
        )

    def open_source_root(self, path: str = "") -> ProviderSourceRootOpenResponse:
        roots = self._source_root_infos(self.manifests(), self.cli_bridges())
        if not roots:
            return ProviderSourceRootOpenResponse(
                ok=False,
                message="No provider source root is configured.",
                snapshot=self.snapshot(),
            )

        root_by_path = {self._normalized_path(root.path): root for root in roots}
        requested = path.strip()
        selected = root_by_path.get(self._normalized_path(requested)) if requested else next((root for root in roots if root.exists), roots[0])
        if selected is None:
            return ProviderSourceRootOpenResponse(
                ok=False,
                path=requested,
                message="Requested path is not an Aegis provider source root.",
                snapshot=self.snapshot(),
            )

        target = Path(selected.path)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ProviderSourceRootOpenResponse(
                ok=False,
                path=str(target),
                message="Provider source root could not be created.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )

        try:
            if os.name == "nt":
                process = subprocess.Popen(["explorer.exe", str(target)])
            else:
                opener = shutil.which("xdg-open") or shutil.which("open")
                if opener is None:
                    return ProviderSourceRootOpenResponse(
                        ok=False,
                        path=str(target),
                        message="No desktop folder opener is available.",
                        snapshot=self.snapshot(),
                    )
                process = subprocess.Popen([opener, str(target)])
        except (OSError, PermissionError) as exc:
            return ProviderSourceRootOpenResponse(
                ok=False,
                path=str(target),
                message="Provider source root could not be opened.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )

        return ProviderSourceRootOpenResponse(
            ok=True,
            path=str(target),
            pid=process.pid,
            message="Provider source root opened.",
            snapshot=self.snapshot(),
        )

    def refresh_source_drop(self, request: ProviderSourceRefreshRequest) -> ProviderSourceRefreshResponse:
        manifest = self._manifest_or_404(request.provider_id)
        if manifest.cli_bridge is None:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="unsupported",
                message=f"{manifest.label} does not declare a CLI source bridge.",
                snapshot=self.snapshot(),
            )

        action = self._resolve_source_refresh_action(
            manifest,
            action_id=request.action_id,
            source_root=request.source_root,
            source_candidate=request.source_candidate,
        )
        if action is None:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=request.action_id,
                status="unsupported",
                message=f"{manifest.label} does not expose a matching source refresh action.",
                snapshot=self.snapshot(),
            )

        if not action.available:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="not_configured",
                command=action.command,
                cwd=action.cwd,
                message=action.detail or "Source refresh action is not available for this source drop.",
                snapshot=self.snapshot(),
            )

        command_parts = action.command_parts
        if not command_parts or not self._source_refresh_command_allowed(command_parts[0]):
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="unsupported",
                command=action.command,
                cwd=action.cwd,
                message="Source refresh command is not allowlisted.",
                snapshot=self.snapshot(),
            )

        if request.dry_run:
            return ProviderSourceRefreshResponse(
                ok=True,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="planned",
                command=action.command,
                cwd=action.cwd,
                message="Source refresh action is ready to run.",
                snapshot=self.snapshot(),
            )

        started = time.perf_counter()
        timeout = max(1, min(int(action.timeout_seconds or 120), 900))
        env = os.environ.copy()
        try:
            completed = subprocess.run(
                command_parts,
                cwd=action.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
        except FileNotFoundError as exc:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="not_configured",
                command=action.command,
                cwd=action.cwd,
                duration_ms=int((time.perf_counter() - started) * 1000),
                message="Source refresh command was not found.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )
        except subprocess.TimeoutExpired as exc:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="timed_out",
                command=action.command,
                cwd=action.cwd,
                duration_ms=int((time.perf_counter() - started) * 1000),
                stdout=self.cli_bridge._redact(exc.stdout or ""),
                stderr=self.cli_bridge._redact(exc.stderr or ""),
                message=f"Source refresh timed out after {timeout} seconds.",
                snapshot=self.snapshot(),
            )
        except (OSError, PermissionError) as exc:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="failed",
                command=action.command,
                cwd=action.cwd,
                duration_ms=int((time.perf_counter() - started) * 1000),
                message="Source refresh could not be launched.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        if completed.returncode == 0:
            info = self.cli_bridge.probe(manifest)
            if info is not None:
                with self._session() as conn:
                    self._store_cli_bridge(conn, info)

        return ProviderSourceRefreshResponse(
            ok=completed.returncode == 0,
            provider_id=manifest.id,
            provider_label=manifest.label,
            action_id=action.id,
            action_label=action.label,
            status="completed" if completed.returncode == 0 else "failed",
            command=action.command,
            cwd=action.cwd,
            exit_code=completed.returncode,
            stdout=self.cli_bridge._redact(completed.stdout or ""),
            stderr=self.cli_bridge._redact(completed.stderr or ""),
            duration_ms=duration_ms,
            message=(
                f"{action.label or 'Source refresh'} completed and {manifest.label} was reprobed."
                if completed.returncode == 0
                else f"{action.label or 'Source refresh'} failed with exit code {completed.returncode}."
            ),
            snapshot=self.snapshot(),
        )

    def source_refresh_jobs(self, limit: int = 25) -> list[ProviderSourceRefreshJobInfo]:
        jobs = sorted(self._load_source_refresh_jobs(), key=lambda job: job.created_at, reverse=True)
        return jobs[: max(1, min(limit, 100))]

    def source_refresh_job(self, job_id: str) -> ProviderSourceRefreshJobInfo:
        wanted = job_id.strip()
        for job in self._load_source_refresh_jobs():
            if job.id == wanted:
                return job
        raise ProviderAccountError("Provider source refresh job was not found.", status_code=404)

    def start_source_refresh_job(self, request: ProviderSourceRefreshRequest) -> ProviderSourceRefreshJobResponse:
        planned = self.refresh_source_drop(request.model_copy(update={"dry_run": True}))
        if not planned.ok:
            raise ProviderAccountError(planned.message or "Provider source refresh action is not available.", status_code=400)

        now = utc_now()
        job = ProviderSourceRefreshJobInfo(
            id=f"source-refresh-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            provider_id=planned.provider_id,
            provider_label=planned.provider_label,
            action_id=planned.action_id,
            action_label=planned.action_label,
            source_root=request.source_root,
            source_candidate=request.source_candidate,
            status="queued",
            command=planned.command,
            cwd=planned.cwd,
            message=f"{planned.action_label or 'Source refresh'} queued.",
            created_at=now,
            updated_at=now,
            metadata={"dry_run": False},
        )
        self._upsert_source_refresh_job(job)
        task = asyncio.create_task(self._run_source_refresh_job(job.id, request.model_copy(update={"dry_run": False})))
        self._active_source_refresh_tasks[job.id] = task
        task.add_done_callback(lambda finished_task, job_id=job.id: self._handle_source_refresh_task_done(job_id, finished_task))
        return ProviderSourceRefreshJobResponse(job=job, snapshot=self.snapshot())

    def cancel_source_refresh_job(self, job_id: str) -> ProviderSourceRefreshJobResponse:
        job = self.source_refresh_job(job_id)
        if self._source_refresh_job_terminal(job.status):
            return ProviderSourceRefreshJobResponse(job=job, snapshot=self.snapshot())

        cancel_event = self._source_refresh_cancel_events.get(job.id)
        if cancel_event is not None:
            cancel_event.set()

        process = self._active_source_refresh_processes.get(job.id)
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

        task = self._active_source_refresh_tasks.get(job.id)
        if process is None and task is not None and not task.done():
            task.cancel()

        job.status = "running" if process is not None and process.poll() is None else "canceled"
        job.message = f"Cancel requested for {job.action_label or 'source refresh'}."
        job.updated_at = utc_now()
        if job.status == "canceled":
            job.finished_at = job.updated_at
        job.metadata = {**job.metadata, "cancel_requested": True}
        self._upsert_source_refresh_job(job)
        return ProviderSourceRefreshJobResponse(job=job, snapshot=self.snapshot())

    def retry_source_refresh_job(self, job_id: str) -> ProviderSourceRefreshJobResponse:
        job = self.source_refresh_job(job_id)
        if not self._source_refresh_job_terminal(job.status):
            raise ProviderAccountError("Provider source refresh job is still active.", status_code=409)
        response = self.start_source_refresh_job(
            ProviderSourceRefreshRequest(
                provider_id=job.provider_id,
                action_id=job.action_id,
                source_root=job.source_root,
                source_candidate=job.source_candidate,
            )
        )
        response.job.metadata = {**response.job.metadata, "retry_of": job.id}
        self._upsert_source_refresh_job(response.job)
        return ProviderSourceRefreshJobResponse(job=response.job, snapshot=self.snapshot())

    def source_refresh_job_response(self, job_id: str) -> ProviderSourceRefreshJobResponse:
        return ProviderSourceRefreshJobResponse(job=self.source_refresh_job(job_id), snapshot=self.snapshot())

    def source_refresh_jobs_response(self, limit: int = 25) -> ProviderSourceRefreshJobsResponse:
        return ProviderSourceRefreshJobsResponse(jobs=self.source_refresh_jobs(limit=limit), snapshot=self.snapshot())

    async def _run_source_refresh_job(self, job_id: str, request: ProviderSourceRefreshRequest) -> None:
        cancel_event = threading.Event()
        self._source_refresh_cancel_events[job_id] = cancel_event
        try:
            response = await asyncio.to_thread(self._refresh_source_drop_for_job, job_id, request, cancel_event)
            job = self.source_refresh_job(job_id)
            job.status = response.status
            job.command = response.command
            job.cwd = response.cwd
            job.pid = None
            job.exit_code = response.exit_code
            job.stdout = self._trim_source_refresh_output(response.stdout)
            job.stderr = self._trim_source_refresh_output(response.stderr)
            job.duration_ms = response.duration_ms
            job.message = response.message
            job.warnings = response.warnings
            job.finished_at = utc_now()
            job.updated_at = job.finished_at
            self._upsert_source_refresh_job(job)
        except Exception as exc:
            job = self.source_refresh_job(job_id)
            job.status = "failed"
            job.message = "Provider source refresh job failed."
            job.stderr = safe_error(exc)
            job.finished_at = utc_now()
            job.updated_at = job.finished_at
            self._upsert_source_refresh_job(job)
        finally:
            self._source_refresh_cancel_events.pop(job_id, None)
            self._active_source_refresh_processes.pop(job_id, None)

    def _handle_source_refresh_task_done(self, job_id: str, task: asyncio.Task[None]) -> None:
        self._active_source_refresh_tasks.pop(job_id, None)
        if task.cancelled():
            job = self.source_refresh_job(job_id)
            job.status = "canceled"
            job.message = "Provider source refresh job was canceled."
            job.finished_at = utc_now()
            job.updated_at = job.finished_at
            job.metadata = {**job.metadata, "cancel_requested": True}
            self._upsert_source_refresh_job(job)
            return
        try:
            task.result()
        except Exception as exc:
            job = self.source_refresh_job(job_id)
            job.status = "failed"
            job.message = "Provider source refresh job failed."
            job.stderr = safe_error(exc)
            job.finished_at = utc_now()
            job.updated_at = job.finished_at
            self._upsert_source_refresh_job(job)

    def _refresh_source_drop_for_job(
        self,
        job_id: str,
        request: ProviderSourceRefreshRequest,
        cancel_event: threading.Event,
    ) -> ProviderSourceRefreshResponse:
        planned = self.refresh_source_drop(request.model_copy(update={"dry_run": True}))
        if not planned.ok:
            return planned

        manifest = self._manifest_or_404(request.provider_id)
        action = self._resolve_source_refresh_action(
            manifest,
            action_id=request.action_id,
            source_root=request.source_root,
            source_candidate=request.source_candidate,
        )
        if action is None:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=request.action_id,
                status="unsupported",
                message=f"{manifest.label} does not expose a matching source refresh action.",
                snapshot=self.snapshot(),
            )

        command_parts = action.command_parts
        started = time.perf_counter()
        timeout = max(1, min(int(action.timeout_seconds or 120), 900))
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        output_lock = threading.Lock()
        last_publish_at = 0.0

        def publish_output(force: bool = False) -> None:
            nonlocal last_publish_at
            now = time.perf_counter()
            if not force and now - last_publish_at < 0.5:
                return
            last_publish_at = now
            with output_lock:
                stdout = self._trim_source_refresh_output("".join(stdout_chunks))
                stderr = self._trim_source_refresh_output("".join(stderr_chunks))
            try:
                current = self.source_refresh_job(job_id)
            except ProviderAccountError:
                return
            current.stdout = stdout
            current.stderr = stderr
            current.duration_ms = int((time.perf_counter() - started) * 1000)
            current.updated_at = utc_now()
            self._upsert_source_refresh_job(current)

        def read_stream(stream: Any, chunks: list[str]) -> None:
            if stream is None:
                return
            try:
                for line in stream:
                    with output_lock:
                        chunks.append(self.cli_bridge._redact(str(line)))
                    publish_output()
            finally:
                try:
                    stream.close()
                except OSError:
                    pass

        job = self.source_refresh_job(job_id)
        job.status = "running"
        job.started_at = utc_now()
        job.updated_at = job.started_at
        job.message = f"{job.action_label or 'Source refresh'} is running."
        self._upsert_source_refresh_job(job)

        try:
            process = subprocess.Popen(
                command_parts,
                cwd=action.cwd,
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError as exc:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="not_configured",
                command=action.command,
                cwd=action.cwd,
                duration_ms=int((time.perf_counter() - started) * 1000),
                message="Source refresh command was not found.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )
        except (OSError, PermissionError) as exc:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="failed",
                command=action.command,
                cwd=action.cwd,
                duration_ms=int((time.perf_counter() - started) * 1000),
                message="Source refresh could not be launched.",
                warnings=[safe_error(exc)],
                snapshot=self.snapshot(),
            )

        self._active_source_refresh_processes[job_id] = process
        job = self.source_refresh_job(job_id)
        job.pid = process.pid
        job.updated_at = utc_now()
        self._upsert_source_refresh_job(job)

        stdout_reader = threading.Thread(target=read_stream, args=(process.stdout, stdout_chunks), daemon=True)
        stderr_reader = threading.Thread(target=read_stream, args=(process.stderr, stderr_chunks), daemon=True)
        stdout_reader.start()
        stderr_reader.start()

        timed_out = False
        canceled = False
        deadline = started + timeout
        while process.poll() is None:
            if cancel_event.is_set():
                canceled = True
                self._terminate_source_refresh_process(process)
                break
            if time.perf_counter() >= deadline:
                timed_out = True
                self._terminate_source_refresh_process(process)
                break
            time.sleep(0.1)

        if cancel_event.is_set():
            canceled = True
        stdout_reader.join(timeout=2)
        stderr_reader.join(timeout=2)
        publish_output(force=True)
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = self._trim_source_refresh_output("".join(stdout_chunks))
        stderr = self._trim_source_refresh_output("".join(stderr_chunks))

        self._active_source_refresh_processes.pop(job_id, None)
        exit_code = process.returncode
        if timed_out:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="timed_out",
                command=action.command,
                cwd=action.cwd,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                message=f"Source refresh timed out after {timeout} seconds.",
                snapshot=self.snapshot(),
            )
        if canceled:
            return ProviderSourceRefreshResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                action_id=action.id,
                action_label=action.label,
                status="canceled",
                command=action.command,
                cwd=action.cwd,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                message=f"{action.label or 'Source refresh'} was canceled.",
                snapshot=self.snapshot(),
            )

        if exit_code == 0:
            info = self.cli_bridge.probe(manifest)
            if info is not None:
                with self._session() as conn:
                    self._store_cli_bridge(conn, info)

        return ProviderSourceRefreshResponse(
            ok=exit_code == 0,
            provider_id=manifest.id,
            provider_label=manifest.label,
            action_id=action.id,
            action_label=action.label,
            status="completed" if exit_code == 0 else "failed",
            command=action.command,
            cwd=action.cwd,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            message=(
                f"{action.label or 'Source refresh'} completed and {manifest.label} was reprobed."
                if exit_code == 0
                else f"{action.label or 'Source refresh'} failed with exit code {exit_code}."
            ),
            snapshot=self.snapshot(),
        )

    def _terminate_source_refresh_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def _source_refresh_job_terminal(self, status: str) -> bool:
        return str(status).lower() in SOURCE_REFRESH_TERMINAL_STATUSES

    def _trim_source_refresh_output(self, text: str) -> str:
        if len(text) <= MAX_SOURCE_REFRESH_OUTPUT_CHARS:
            return text
        return text[-MAX_SOURCE_REFRESH_OUTPUT_CHARS:]

    def probe_cli_bridges(self, provider_id: str = "") -> ProviderAccountsResponse:
        wanted = provider_id.strip()
        manifests = [item for item in self.manifests() if item.cli_bridge is not None]
        if wanted:
            manifests = [item for item in manifests if item.id == wanted]
            if not manifests:
                self._manifest_or_404(wanted)

        with self._session() as conn:
            for manifest in manifests:
                info = self.cli_bridge.probe(manifest)
                if info is None:
                    continue
                self._store_cli_bridge(conn, info)
        return self.snapshot()

    def _preferred_accounts_by_provider(self, accounts: list[ProviderLinkedAccount]) -> dict[str, ProviderLinkedAccount]:
        selected: dict[str, ProviderLinkedAccount] = {}
        for account in accounts:
            current = selected.get(account.provider_id)
            if current is None or self._account_priority(account) > self._account_priority(current):
                selected[account.provider_id] = account
        return selected

    def _merge_display_accounts(
        self,
        persisted: list[ProviderLinkedAccount],
        local_accounts: list[ProviderLinkedAccount],
    ) -> list[ProviderLinkedAccount]:
        by_id = {account.account_id: account for account in persisted}
        for account in local_accounts:
            by_id.setdefault(account.account_id, account)
        return sorted(by_id.values(), key=lambda item: (item.provider_label.lower(), item.account_id))

    def _account_priority(self, account: ProviderLinkedAccount) -> tuple[int, int, str]:
        status_priority = {
            "linked": 40,
            "limited": 30,
            "unknown": 20,
            "expired": 10,
            "offline": 5,
            "error": 1,
            "not_configured": 0,
        }.get(str(account.status).lower(), 0)
        auth_priority = {
            "cli_bridge": 30,
            "api_key": 20,
            "oauth_browser": 15,
            "device_code": 15,
            "env_profile": 10,
            "none": 0,
        }.get(str(account.auth_mode).lower(), 0)
        return (status_priority, auth_priority, account.updated_at)

    def _store_cli_bridge(self, conn: sqlite3.Connection, info: ProviderCliBridgeInfo) -> None:
        conn.execute(
            """
            insert into provider_cli_bridges (
                provider_id, cli_name, binary_path, version, status, auth_status,
                probe_command, supported_delegation_modes_json, last_probe_at,
                last_error, metadata_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(provider_id) do update set
                cli_name = excluded.cli_name,
                binary_path = excluded.binary_path,
                version = excluded.version,
                status = excluded.status,
                auth_status = excluded.auth_status,
                probe_command = excluded.probe_command,
                supported_delegation_modes_json = excluded.supported_delegation_modes_json,
                last_probe_at = excluded.last_probe_at,
                last_error = excluded.last_error,
                metadata_json = excluded.metadata_json
            """,
            (
                info.provider_id,
                info.cli_name,
                info.binary_path,
                info.version,
                info.status,
                info.auth_status,
                info.probe_command,
                json.dumps(info.supported_delegation_modes, ensure_ascii=True),
                info.last_probe_at,
                safe_error(RuntimeError(info.last_error)) if info.last_error else "",
                json.dumps(info.metadata, ensure_ascii=True),
            ),
        )

    def _cli_link_status(self, info: ProviderCliBridgeInfo) -> str:
        auth_status = str(info.auth_status or "unknown").lower()
        bridge_status = str(info.status or "unknown").lower()
        if auth_status == "linked" or bridge_status == "linked":
            return "linked"
        if auth_status in {"not_configured", "error"}:
            return auth_status
        if bridge_status in {"not_configured", "error"}:
            return bridge_status
        return "limited"

    def _linked_api_key_account(self, provider_id: str) -> ProviderLinkedAccount | None:
        for account in self.accounts():
            if account.provider_id == provider_id and account.auth_mode == "api_key" and account.status == "linked":
                return account
        return None

    def _linked_cli_account(self, provider_id: str) -> ProviderLinkedAccount | None:
        for account in self.accounts():
            if account.provider_id == provider_id and account.auth_mode == "cli_bridge" and account.status in {"linked", "limited"}:
                return account
        return None

    def _local_runtime_account(self, manifest: ProviderAccountManifest) -> ProviderLinkedAccount | None:
        if manifest.kind != "local" or "none" not in manifest.auth_modes:
            return None

        active = self._local_manifest_matches_settings(manifest)
        model_name = self.settings.aegis_model_name.strip()
        api = self.settings.aegis_model_api.strip().lower() or "ollama"
        endpoint = self.settings.aegis_model_endpoint.strip()
        label = (
            f"{manifest.label} / {model_name or 'active model'}"
            if active
            else f"{manifest.label} (no credentials required)"
        )
        now = utc_now()
        return ProviderLinkedAccount(
            account_id=f"{manifest.id}:local_runtime",
            provider_id=manifest.id,
            provider_label=manifest.label,
            auth_mode="none",
            status="linked" if active else "unknown",
            account_label=label,
            subject_hash=self._subject_hash(manifest.id, api, endpoint, model_name, "local_runtime"),
            credential_ref="",
            credential_hint="no credentials required",
            session_ref=f"{manifest.id}:local_runtime:session",
            scopes=["chat", "code", "streaming"],
            quota_status=manifest.quota_status or "local runtime",
            expires_at="",
            created_at=now,
            updated_at=now,
            last_validated_at=now if active else "",
            last_error="",
            metadata={
                "auth_boundary": "local_runtime",
                "active": active,
                "model_api": api,
                "model_endpoint": endpoint,
                "model_name": model_name,
                "raw_secret_persisted_in_sqlite": False,
            },
        )

    def _local_runtime_session(self, account: ProviderLinkedAccount) -> ProviderSessionInfo:
        return ProviderSessionInfo(
            session_id=account.session_ref,
            account_id=account.account_id,
            provider_id=account.provider_id,
            auth_mode="none",
            status=account.status,
            credential_ref="",
            refresh_supported=False,
            expires_at="",
            created_at=account.created_at,
            updated_at=account.updated_at,
            last_refresh_at="",
            last_refresh_error="",
            metadata={
                "refresh": "not_applicable_for_local_runtime",
                "active": bool(account.metadata.get("active")),
                "model_api": account.metadata.get("model_api", ""),
                "model_endpoint": account.metadata.get("model_endpoint", ""),
                "model_name": account.metadata.get("model_name", ""),
            },
        )

    def _local_manifest_matches_settings(self, manifest: ProviderAccountManifest) -> bool:
        api = self.settings.aegis_model_api.strip().lower() or "ollama"
        endpoint = self.settings.aegis_model_endpoint.strip()
        if manifest.id == "ollama":
            return api == "ollama"
        if manifest.id == "local_openai_compatible":
            return api in {"lmstudio", "openai-compatible", "openai"} and is_local_endpoint(endpoint)
        return False

    def _api_key_env_name(self, manifest: ProviderAccountManifest) -> str:
        for env_name in manifest.credential_env_vars:
            if "API_KEY" in env_name.upper():
                return env_name
        return manifest.credential_env_vars[0] if manifest.credential_env_vars else ""

    def _provider_status(
        self,
        manifest: ProviderAccountManifest,
        *,
        account: ProviderLinkedAccount | None,
        cli_bridge: ProviderCliBridgeInfo | None,
    ) -> ProviderAccountStatus:
        status = "not_configured"
        if account is not None:
            status = account.status
        elif manifest.kind == "local" and "none" in manifest.auth_modes:
            status = "linked"
        elif cli_bridge is not None and cli_bridge.status not in {"not_configured", "error"}:
            status = cli_bridge.status

        setup_actions: list[str] = []
        if account is None and "api_key" in manifest.auth_modes:
            setup_actions.append("Link an API key through the Aegis credential vault.")
        if account is None and cli_bridge is not None and cli_bridge.binary_path and cli_bridge.status not in {"not_configured", "error"}:
            setup_actions.append("Reuse the detected official CLI session for subscription-style provider delegation.")
        if account is not None and account.auth_mode == "cli_bridge" and account.status == "limited":
            setup_actions.append("CLI auth status is not exposed by this provider; execution will verify the session at run time.")
        if manifest.cli_bridge is not None and (cli_bridge is None or not cli_bridge.binary_path):
            setup_actions.append(f"Install {manifest.cli_bridge.cli_name or manifest.label} CLI and sign in with its official login command.")
        if "oauth_browser" in manifest.auth_modes:
            setup_actions.append("Configure an Aegis-owned OAuth app registration before browser login is enabled.")
        if "env_profile" in manifest.auth_modes:
            setup_actions.append("Use official cloud profile or environment authentication for enterprise routing.")

        limit_summary = self._limit_summary(manifest, account, cli_bridge)
        readiness = self._execution_readiness(
            manifest,
            account=account,
            cli_bridge=cli_bridge,
            connection_status=status,
        )
        routing_weight = self._routing_weight(
            manifest,
            connection_status=status,
            execution_ready=readiness["execution_ready"],
            readiness=str(readiness["readiness"]),
        )
        fallback_eligible = status in {"linked", "limited", "unknown"} or manifest.kind == "local"
        route_safety = self._route_safety(
            manifest,
            account=account,
            cli_bridge=cli_bridge,
            connection_status=status,
            execution_ready=bool(readiness["execution_ready"]),
            readiness_detail=str(readiness["readiness_detail"]),
            fallback_eligible=fallback_eligible,
            limit_summary=limit_summary,
        )
        return ProviderAccountStatus(
            manifest=manifest,
            account=self._redacted_account_snapshot(account),
            cli_bridge=self._redacted_cli_bridge_snapshot(cli_bridge),
            connection_status=status,
            primary_auth_mode=account.auth_mode if account is not None else manifest.default_auth_mode,
            fallback_eligible=fallback_eligible,
            setup_actions=setup_actions,
            execution_ready=bool(readiness["execution_ready"]),
            readiness=str(readiness["readiness"]),
            readiness_label=str(readiness["readiness_label"]),
            readiness_detail=str(readiness["readiness_detail"]),
            routing_weight=routing_weight,
            quota_status=limit_summary,
            model_limit_summary=limit_summary,
            route_safety=route_safety,
        )

    def _route_safety(
        self,
        manifest: ProviderAccountManifest,
        *,
        account: ProviderLinkedAccount | None,
        cli_bridge: ProviderCliBridgeInfo | None,
        connection_status: str,
        execution_ready: bool,
        readiness_detail: str,
        fallback_eligible: bool,
        limit_summary: str,
    ) -> ProviderRouteSafety:
        kind = str(manifest.kind or "cloud").lower()
        declared_auth_modes = [str(item or "").lower() for item in manifest.auth_modes]
        default_auth_mode = str(manifest.default_auth_mode or "").lower()
        auth_mode = (
            str(account.auth_mode or "").lower()
            if account is not None
            else default_auth_mode
            if default_auth_mode in declared_auth_modes
            else declared_auth_modes[0]
            if declared_auth_modes
            else ""
        )
        user_action = "" if execution_ready else readiness_detail
        fallback_policy = (
            "Eligible for policy-approved fallback routing."
            if fallback_eligible
            else "Not eligible for automatic fallback until the route is executable."
        )

        if kind == "local":
            return ProviderRouteSafety(
                route_type="local_endpoint",
                privacy_boundary="local",
                secret_policy="No provider credential is required; Aegis does not attach API-key environment variables.",
                secret_storage="none",
                cloud_context_requires_consent=False,
                sends_workspace_context=False,
                cost_boundary="Local compute; provider API billing is not expected for this route.",
                quota_boundary=limit_summary,
                latency_boundary="Bound to local endpoint health, model size, and workstation capacity.",
                fallback_policy=fallback_policy,
                user_action_required=user_action,
            )

        if auth_mode == "cli_bridge" or (
            account is None and cli_bridge is not None and cli_bridge.binary_path and connection_status in {"linked", "limited", "unknown"}
        ):
            return ProviderRouteSafety(
                route_type="cli_bridge",
                privacy_boundary="provider_cli",
                secret_policy="Aegis delegates to the official provider CLI and does not import provider token files.",
                secret_storage="provider_cli_only",
                cloud_context_requires_consent=True,
                sends_workspace_context=True,
                cost_boundary="Usage, subscription, and billing are controlled by the signed-in provider CLI account.",
                quota_boundary=limit_summary,
                latency_boundary="Bound to provider CLI startup, auth checks, network, and selected model load.",
                fallback_policy=fallback_policy,
                user_action_required=user_action,
            )

        if auth_mode == "api_key" or "api_key" in manifest.auth_modes:
            enterprise_route = kind == "enterprise"
            return ProviderRouteSafety(
                route_type="api_key",
                privacy_boundary="enterprise_cloud" if enterprise_route else "cloud",
                secret_policy=(
                    "API keys are read from the OS credential store only at execution time; SQLite stores only "
                    "the credential reference and redacted hint."
                ),
                secret_storage="os_credential_store",
                cloud_context_requires_consent=True,
                sends_workspace_context=True,
                cost_boundary="Usage and billing limits stay with the linked provider account or project.",
                quota_boundary=limit_summary,
                latency_boundary="Bound to provider endpoint, network, model load, and rate limits.",
                fallback_policy=fallback_policy,
                user_action_required=user_action,
            )

        if auth_mode == "env_profile" or "env_profile" in manifest.auth_modes:
            return ProviderRouteSafety(
                route_type="environment_profile",
                privacy_boundary="enterprise_cloud",
                secret_policy="Aegis uses official cloud profile or environment authentication without copying provider credentials into SQLite.",
                secret_storage="environment_profile",
                cloud_context_requires_consent=True,
                sends_workspace_context=True,
                cost_boundary="Usage and billing limits stay with the configured cloud project, subscription, or account.",
                quota_boundary=limit_summary,
                latency_boundary="Bound to cloud profile, provider region, network, model load, and rate limits.",
                fallback_policy=fallback_policy,
                user_action_required=user_action,
            )

        if "oauth_browser" in manifest.auth_modes or "device_code" in manifest.auth_modes:
            return ProviderRouteSafety(
                route_type="oauth_pending",
                privacy_boundary="cloud",
                secret_policy="OAuth and device-code routes stay disabled until Aegis-owned provider app registrations are configured.",
                secret_storage="oauth_pending",
                cloud_context_requires_consent=True,
                sends_workspace_context=True,
                cost_boundary="Usage and billing limits will stay with the authorized provider account.",
                quota_boundary=limit_summary,
                latency_boundary="Bound to provider OAuth, network, model load, and rate limits after setup.",
                fallback_policy=fallback_policy,
                user_action_required=user_action,
            )

        return ProviderRouteSafety(
            route_type="unsupported",
            privacy_boundary="unknown",
            secret_policy="No executable provider credential route is configured.",
            secret_storage="none",
            cloud_context_requires_consent=True,
            sends_workspace_context=False,
            cost_boundary="Unknown until an executable provider route is configured.",
            quota_boundary=limit_summary,
            latency_boundary="Unknown until an executable provider route is configured.",
            fallback_policy=fallback_policy,
            user_action_required=user_action,
        )

    def _execution_readiness(
        self,
        manifest: ProviderAccountManifest,
        *,
        account: ProviderLinkedAccount | None,
        cli_bridge: ProviderCliBridgeInfo | None,
        connection_status: str,
    ) -> dict[str, Any]:
        status = str(connection_status or "not_configured").lower()
        if manifest.kind == "local":
            if status == "linked":
                return {
                    "execution_ready": True,
                    "readiness": "local_ready",
                    "readiness_label": "Local Ready",
                    "readiness_detail": f"{manifest.label} routes through the active local runtime.",
                }
            return {
                "execution_ready": False,
                "readiness": "local_not_active",
                "readiness_label": "Not Active",
                "readiness_detail": f"Select and save a {manifest.label} model before routing work through it.",
            }

        if account is not None:
            auth_mode = str(account.auth_mode or "").lower()
            account_status = str(account.status or status).lower()
            if account_status == "linked":
                return {
                    "execution_ready": True,
                    "readiness": "account_ready",
                    "readiness_label": "Ready",
                    "readiness_detail": (
                        "API-key routing is available through the Aegis credential vault."
                        if auth_mode == "api_key"
                        else "Official CLI delegation is linked for subscription-style usage."
                        if auth_mode == "cli_bridge"
                        else f"{manifest.label} account is linked for execution."
                    ),
                }
            if account_status == "limited" and auth_mode == "cli_bridge":
                return {
                    "execution_ready": True,
                    "readiness": "runtime_verified",
                    "readiness_label": "Runtime Verified",
                    "readiness_detail": "Official CLI delegation can run; auth and quota are verified by the provider CLI at execution time.",
                }
            return {
                "execution_ready": False,
                "readiness": account_status or "account_not_ready",
                "readiness_label": self._status_label(account_status or "account_not_ready"),
                "readiness_detail": self._redacted_provider_error(
                    account.last_error,
                    fallback=f"{manifest.label} account is present but not ready for execution.",
                ),
            }

        if cli_bridge is not None and cli_bridge.binary_path:
            auth_status = str(cli_bridge.auth_status or "unknown").lower()
            bridge_status = str(cli_bridge.status or "unknown").lower()
            if auth_status == "linked" or bridge_status == "linked":
                return {
                    "execution_ready": True,
                    "readiness": "cli_ready",
                    "readiness_label": "CLI Ready",
                    "readiness_detail": "Official CLI is signed in and can be delegated without importing provider tokens.",
                }
            if auth_status in {"unknown", "limited"} and bridge_status not in {"error", "not_configured"}:
                return {
                    "execution_ready": True,
                    "readiness": "runtime_verified",
                    "readiness_label": "Runtime Verified",
                    "readiness_detail": "Official CLI is runnable; auth and quota will be verified by the provider CLI at execution time.",
                }
            if auth_status == "not_configured":
                return {
                    "execution_ready": False,
                    "readiness": "login_required",
                    "readiness_label": "Login Required",
                    "readiness_detail": f"Run the official {manifest.label} login flow before delegating work.",
                }
            return {
                "execution_ready": False,
                "readiness": "cli_error" if bridge_status == "error" else "cli_not_ready",
                "readiness_label": "CLI Issue" if bridge_status == "error" else "CLI Not Ready",
                "readiness_detail": self._redacted_provider_error(
                    cli_bridge.last_error,
                    fallback=f"{manifest.label} CLI is detected but not ready for execution.",
                ),
            }

        if "api_key" in manifest.auth_modes:
            return {
                "execution_ready": False,
                "readiness": "api_key_required",
                "readiness_label": "Key Required",
                "readiness_detail": "Link an API key or reuse an official CLI session before routing work through this provider.",
            }
        if manifest.cli_bridge is not None:
            return {
                "execution_ready": False,
                "readiness": "cli_required",
                "readiness_label": "CLI Required",
                "readiness_detail": f"Install {manifest.cli_bridge.cli_name or manifest.label} and sign in with the official login command.",
            }
        return {
            "execution_ready": False,
            "readiness": "unsupported",
            "readiness_label": "Unsupported",
            "readiness_detail": f"{manifest.label} does not expose an executable account route yet.",
        }

    def _redacted_provider_error(self, value: str, *, fallback: str) -> str:
        detail = str(value or "").strip()
        if not detail:
            return fallback
        return safe_error(RuntimeError(redact_inline(detail)))

    def _redacted_account_snapshot(self, account: ProviderLinkedAccount | None) -> ProviderLinkedAccount | None:
        if account is None or not account.last_error:
            return account
        return account.model_copy(update={"last_error": self._redacted_provider_error(account.last_error, fallback="")})

    def _redacted_cli_bridge_snapshot(self, cli_bridge: ProviderCliBridgeInfo | None) -> ProviderCliBridgeInfo | None:
        if cli_bridge is None or not cli_bridge.last_error:
            return cli_bridge
        return cli_bridge.model_copy(update={"last_error": self._redacted_provider_error(cli_bridge.last_error, fallback="")})

    def _routing_weight(
        self,
        manifest: ProviderAccountManifest,
        *,
        connection_status: str,
        execution_ready: bool,
        readiness: str,
    ) -> float:
        capabilities = {item.strip().lower() for item in manifest.capabilities}
        status = str(connection_status or "not_configured").lower()
        score = 0.0
        if execution_ready:
            score += 5.0
        else:
            score -= 5.0
        if status == "linked":
            score += 2.0
        elif status == "limited" or readiness == "runtime_verified":
            score += 1.0
        elif status in {"error", "expired", "offline"}:
            score -= 4.0
        elif status == "not_configured":
            score -= 2.0
        if manifest.kind == "local" or "local" in capabilities:
            score += 1.5
        if "code" in capabilities:
            score += 0.75
        if "agent_delegation" in capabilities:
            score += 0.5
        if "long_context" in capabilities or "large_context" in capabilities:
            score += 0.25
        return round(score, 2)

    def _status_label(self, value: str) -> str:
        return " ".join(part.capitalize() for part in str(value or "unknown").replace("-", "_").split("_") if part) or "Unknown"

    def _limit_summary(
        self,
        manifest: ProviderAccountManifest,
        account: ProviderLinkedAccount | None,
        cli_bridge: ProviderCliBridgeInfo | None,
    ) -> str:
        if account is not None and account.quota_status and account.quota_status != "unknown":
            return account.quota_status
        if account is not None and account.auth_mode == "cli_bridge":
            if account.status == "limited":
                return "Delegation uses the official CLI session; auth and quota details are verified by the provider CLI at run time."
            return "Limits are controlled by the signed-in CLI account and surfaced through observed provider responses."
        if cli_bridge is not None and cli_bridge.auth_status == "linked":
            return "Limits are controlled by the signed-in CLI account and surfaced through observed provider responses."
        if manifest.quota_status and manifest.quota_status != "unknown":
            return manifest.quota_status
        return "Unknown until Aegis observes provider responses or the provider exposes quota metadata."

    def _source_root_infos(
        self,
        manifests: list[ProviderAccountManifest],
        cli_bridges: list[ProviderCliBridgeInfo],
    ) -> list[ProviderSourceRootInfo]:
        bridge_by_provider = {bridge.provider_id: bridge for bridge in cli_bridges}
        root_map: dict[str, dict[str, Any]] = {}
        for manifest in manifests:
            if manifest.cli_bridge is None:
                continue
            for root in self.cli_bridge.source_roots_for(manifest):
                key = self._normalized_path(str(root))
                item = root_map.setdefault(
                    key,
                    {
                        "path": str(root),
                        "exists": root.exists(),
                        "provider_ids": [],
                        "provider_labels": [],
                    },
                )
                item["exists"] = bool(item["exists"] or root.exists())
                if manifest.id not in item["provider_ids"]:
                    item["provider_ids"].append(manifest.id)
                if manifest.label not in item["provider_labels"]:
                    item["provider_labels"].append(manifest.label)

        infos: list[ProviderSourceRootInfo] = []
        for payload in sorted(root_map.values(), key=lambda value: str(value.get("path", "")).lower()):
            path = Path(str(payload["path"]))
            provider_ids = [str(item) for item in payload.get("provider_ids", [])]
            probe_times = [
                bridge_by_provider[provider_id].last_probe_at
                for provider_id in provider_ids
                if provider_id in bridge_by_provider and bridge_by_provider[provider_id].last_probe_at
            ]
            missing_probe_count = sum(
                1
                for provider_id in provider_ids
                if provider_id not in bridge_by_provider or not bridge_by_provider[provider_id].last_probe_at
            )
            last_probe_at = self._latest_iso(probe_times)
            exists = path.exists()
            modified_at = self._source_path_modified_at(path)
            payload["child_count"] = self._source_root_child_count(path)
            payload["modified_at"] = modified_at
            payload["last_probe_at"] = last_probe_at
            payload.update(
                self._source_freshness(
                    exists=exists,
                    modified_at=modified_at,
                    last_probe_at=last_probe_at,
                    missing_probe_count=missing_probe_count,
                    subject="source root",
                )
            )
            infos.append(ProviderSourceRootInfo.model_validate(payload))
        return infos

    def _source_drop_infos(
        self,
        manifests: list[ProviderAccountManifest],
        cli_bridges: list[ProviderCliBridgeInfo],
    ) -> list[ProviderSourceDropInfo]:
        bridge_by_provider = {bridge.provider_id: bridge for bridge in cli_bridges}
        drops: list[ProviderSourceDropInfo] = []
        for manifest in manifests:
            if manifest.cli_bridge is None:
                continue
            for target in self.cli_bridge.targets_for(manifest):
                metadata = target.metadata or {}
                source_root = str(metadata.get("source_root") or "")
                if target.source not in {"source_drop", "package_glob"} and not source_root:
                    continue
                bridge = bridge_by_provider.get(manifest.id)
                bridge_matches = bridge is not None and (
                    bridge.binary_path == target.display
                    or str((bridge.metadata or {}).get("source_candidate") or "") == str(metadata.get("source_candidate") or "")
                    or (
                        source_root
                        and self._normalized_path(str((bridge.metadata or {}).get("source_root") or "")) == self._normalized_path(source_root)
                    )
                )
                path = target.cwd or target.command[0] if target.command else target.display
                last_probe_at = bridge.last_probe_at if bridge_matches and bridge is not None else ""
                drop_path = Path(str(path))
                modified_at = self._source_path_modified_at(drop_path)
                freshness = self._source_freshness(
                    exists=drop_path.exists(),
                    modified_at=modified_at,
                    last_probe_at=last_probe_at,
                    missing_probe_count=0,
                    subject=f"{manifest.label} source drop",
                )
                drops.append(
                    ProviderSourceDropInfo(
                        provider_id=manifest.id,
                        provider_label=manifest.label,
                        cli_name=manifest.cli_bridge.cli_name or manifest.label,
                        source_root=source_root,
                        detected_from=target.source,
                        source_candidate=str(metadata.get("source_candidate") or ""),
                        path=str(path),
                        cwd=target.cwd,
                        display=target.display,
                        command=self.cli_bridge._format_command_parts(target.command),
                        version=bridge.version if bridge_matches and bridge is not None else "",
                        status=bridge.status if bridge_matches and bridge is not None else "detected",
                        auth_status=bridge.auth_status if bridge_matches and bridge is not None else "unknown",
                        last_probe_at=last_probe_at,
                        modified_at=modified_at,
                        updated_after_probe=bool(freshness["updated_after_probe"]),
                        freshness=str(freshness["freshness"]),
                        freshness_label=str(freshness["freshness_label"]),
                        freshness_detail=str(freshness["freshness_detail"]),
                        refresh_actions=self._source_refresh_actions_for_drop(
                            manifest,
                            source_root=source_root,
                            source_candidate=str(metadata.get("source_candidate") or ""),
                            drop_path=drop_path,
                        ),
                        last_error=bridge.last_error if bridge_matches and bridge is not None else "",
                        metadata={key: value for key, value in metadata.items() if key not in {"source_root"}},
                    )
                )
        return sorted(drops, key=lambda item: (item.provider_label.lower(), item.detected_from, item.display.lower()))

    def _resolve_source_refresh_action(
        self,
        manifest: ProviderAccountManifest,
        *,
        action_id: str = "",
        source_root: str = "",
        source_candidate: str = "",
    ) -> ProviderSourceRefreshAction | None:
        selected_id = action_id.strip()
        targets = self.cli_bridge.targets_for(manifest)
        for target in targets:
            metadata = target.metadata or {}
            target_source_root = str(metadata.get("source_root") or "")
            target_candidate = str(metadata.get("source_candidate") or "")
            if source_root and self._normalized_path(target_source_root) != self._normalized_path(source_root):
                continue
            if source_candidate and target_candidate != source_candidate:
                continue
            path = Path(str(target.cwd or target.command[0] if target.command else target.display))
            actions = self._source_refresh_actions_for_drop(
                manifest,
                source_root=target_source_root,
                source_candidate=target_candidate,
                drop_path=path,
            )
            if selected_id:
                match = next((action for action in actions if action.id == selected_id), None)
                if match is not None:
                    return match
                continue
            available = next((action for action in actions if action.available), None)
            if available is not None:
                return available
            if actions:
                return actions[0]
        return None

    def _source_refresh_actions_for_drop(
        self,
        manifest: ProviderAccountManifest,
        *,
        source_root: str = "",
        source_candidate: str = "",
        drop_path: Path | None = None,
    ) -> list[ProviderSourceRefreshAction]:
        actions: list[ProviderSourceRefreshAction] = []
        for payload in self._source_refresh_payloads(manifest):
            action = self._source_refresh_action_from_payload(
                manifest,
                payload,
                source_root=source_root,
                source_candidate=source_candidate,
                drop_path=drop_path,
            )
            if action is not None:
                actions.append(action)
        return actions

    def _source_refresh_payloads(self, manifest: ProviderAccountManifest) -> list[dict[str, Any]]:
        metadata = manifest.metadata if isinstance(manifest.metadata, dict) else {}
        source_bridge = metadata.get("source_bridge") if isinstance(metadata.get("source_bridge"), dict) else {}
        payloads = source_bridge.get("refresh_commands") if isinstance(source_bridge.get("refresh_commands"), list) else []
        return [item for item in payloads if isinstance(item, dict)]

    def _source_refresh_action_from_payload(
        self,
        manifest: ProviderAccountManifest,
        payload: dict[str, Any],
        *,
        source_root: str = "",
        source_candidate: str = "",
        drop_path: Path | None = None,
    ) -> ProviderSourceRefreshAction | None:
        action_id = str(payload.get("id") or "").strip()
        command = self._clean_list(payload.get("command") if isinstance(payload.get("command"), list) else [])
        if not action_id or not command:
            return None

        roots = self.cli_bridge.source_roots_for(manifest)
        cwd = self._resolve_source_refresh_cwd(str(payload.get("cwd") or "."), roots=roots, source_root=source_root)
        label = str(payload.get("label") or action_id.replace("_", " ").replace("-", " ").title())
        timeout_seconds = int(payload.get("timeout_seconds") or 120)
        detail = "Ready to refresh this source drop."
        available = cwd is not None
        if cwd is None:
            detail = "Refresh folder is not present under a declared provider source root."
        elif drop_path is not None and drop_path.exists() and not self._paths_overlap(cwd, drop_path):
            return None
        elif not self._source_refresh_command_allowed(command[0]):
            available = False
            detail = "Refresh command is not allowlisted."
        command_parts = [shutil.which(command[0]) or command[0], *command[1:]]

        return ProviderSourceRefreshAction(
            id=action_id,
            label=label,
            cwd=str(cwd) if cwd is not None else "",
            command=self.cli_bridge._format_command_parts(command),
            command_parts=command_parts,
            available=available,
            detail=detail,
            timeout_seconds=max(1, min(timeout_seconds, 900)),
        )

    def _resolve_source_refresh_cwd(self, value: str, *, roots: list[Path], source_root: str = "") -> Path | None:
        expanded = Path(os.path.expandvars(value)).expanduser()
        candidates: list[Path] = []
        selected_root = Path(source_root) if source_root else None
        if expanded.is_absolute():
            candidates.append(expanded)
        elif selected_root is not None:
            candidates.append(selected_root / expanded)
        else:
            candidates.extend(root / expanded for root in roots)

        declared_roots = [root.resolve() if root.exists() else root.absolute() for root in roots]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate.absolute()
            if not resolved.is_dir():
                continue
            if any(self._path_is_within(resolved, root) for root in declared_roots):
                return resolved
        return None

    def _source_refresh_command_allowed(self, executable: str) -> bool:
        name = Path(str(executable or "")).name.lower()
        return name in SOURCE_REFRESH_COMMAND_ALLOWLIST

    def _load_source_refresh_jobs(self) -> list[ProviderSourceRefreshJobInfo]:
        with self._source_refresh_lock:
            path = self.source_refresh_jobs_path
            if not path.exists():
                return []
            try:
                if path.stat().st_size > MAX_SOURCE_REFRESH_JOBS_JSON_BYTES:
                    return []
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
            items = payload if isinstance(payload, list) else []
            jobs: list[ProviderSourceRefreshJobInfo] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    jobs.append(ProviderSourceRefreshJobInfo.model_validate(item))
                except Exception:
                    continue
            return jobs

    def _save_source_refresh_jobs(self, jobs: list[ProviderSourceRefreshJobInfo]) -> None:
        with self._source_refresh_lock:
            self.source_refresh_jobs_path.parent.mkdir(parents=True, exist_ok=True)
            trimmed = sorted(jobs, key=lambda job: job.created_at, reverse=True)[:50]
            self.source_refresh_jobs_path.write_text(
                json.dumps([job.model_dump() for job in trimmed], ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

    def _upsert_source_refresh_job(self, job: ProviderSourceRefreshJobInfo) -> None:
        with self._source_refresh_lock:
            jobs = [item for item in self._load_source_refresh_jobs() if item.id != job.id]
            jobs.append(job)
            self._save_source_refresh_jobs(jobs)

    def _paths_overlap(self, left: Path, right: Path) -> bool:
        return self._path_is_within(left, right) or self._path_is_within(right, left)

    def _path_is_within(self, child: Path, parent: Path) -> bool:
        try:
            child.resolve().relative_to(parent.resolve())
            return True
        except (OSError, ValueError):
            try:
                child.absolute().relative_to(parent.absolute())
                return True
            except ValueError:
                return False

    def _source_root_child_count(self, path: Path) -> int:
        if not path.exists() or not path.is_dir():
            return 0
        try:
            return sum(1 for _ in path.iterdir())
        except OSError:
            return 0

    def _source_path_modified_at(self, path: Path) -> str:
        timestamp = self._source_path_mtime(path)
        if timestamp is None:
            return ""
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    def _source_path_mtime(self, path: Path) -> float | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        latest = stat.st_mtime
        if path.is_dir():
            try:
                for index, child in enumerate(path.iterdir()):
                    if index >= 128:
                        break
                    try:
                        latest = max(latest, child.stat().st_mtime)
                    except OSError:
                        continue
            except OSError:
                pass
        return latest

    def _source_freshness(
        self,
        *,
        exists: bool,
        modified_at: str,
        last_probe_at: str,
        missing_probe_count: int = 0,
        subject: str = "source drop",
    ) -> dict[str, Any]:
        if not exists:
            return {
                "updated_after_probe": False,
                "freshness": "missing",
                "freshness_label": "Missing",
                "freshness_detail": f"The {subject} path is not present on disk.",
            }
        if missing_probe_count > 0:
            plural = "bridge" if missing_probe_count == 1 else "bridges"
            return {
                "updated_after_probe": False,
                "freshness": "needs_probe",
                "freshness_label": "Probe Needed",
                "freshness_detail": f"{missing_probe_count} provider {plural} in this source root need a CLI probe.",
            }
        modified = self._parse_iso_datetime(modified_at)
        probed = self._parse_iso_datetime(last_probe_at)
        if probed is None:
            return {
                "updated_after_probe": False,
                "freshness": "needs_probe",
                "freshness_label": "Probe Needed",
                "freshness_detail": f"Probe CLIs after adding or replacing this {subject}.",
            }
        if modified is not None and modified > probed + timedelta(seconds=1):
            return {
                "updated_after_probe": True,
                "freshness": "changed",
                "freshness_label": "Update Detected",
                "freshness_detail": f"This {subject} changed after the last CLI probe. Rescan to refresh the detected bridge.",
            }
        return {
            "updated_after_probe": False,
            "freshness": "current",
            "freshness_label": "Current",
            "freshness_detail": f"This {subject} has not changed since the last CLI probe.",
        }

    def _latest_iso(self, values: list[str]) -> str:
        latest: datetime | None = None
        for value in values:
            parsed = self._parse_iso_datetime(value)
            if parsed is not None and (latest is None or parsed > latest):
                latest = parsed
        return latest.isoformat() if latest is not None else ""

    def _parse_iso_datetime(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _normalized_path(self, value: str) -> str:
        if not value:
            return ""
        try:
            return str(Path(value).resolve()).lower()
        except OSError:
            return str(Path(value).absolute()).lower()

    def _manifest_or_404(self, provider_id: str) -> ProviderAccountManifest:
        provider = provider_id.strip()
        for manifest in self.manifests():
            if manifest.id == provider:
                return manifest
        raise ProviderAccountError("provider account manifest not found", status_code=404)

    def _account_from_row(self, row: sqlite3.Row) -> ProviderLinkedAccount:
        payload = dict(row)
        payload["scopes"] = self._json_list(payload.pop("scopes_json"))
        payload["metadata"] = self._json_payload(payload.pop("metadata_json"))
        if payload.get("last_error"):
            payload["last_error"] = self._redacted_provider_error(str(payload["last_error"]), fallback="")
        return ProviderLinkedAccount.model_validate(payload)

    def _session_from_row(self, row: sqlite3.Row) -> ProviderSessionInfo:
        payload = dict(row)
        payload["refresh_supported"] = bool(payload.get("refresh_supported"))
        payload["metadata"] = self._json_payload(payload.pop("metadata_json"))
        if payload.get("last_refresh_error"):
            payload["last_refresh_error"] = self._redacted_provider_error(str(payload["last_refresh_error"]), fallback="")
        return ProviderSessionInfo.model_validate(payload)

    def _cli_bridge_from_row(self, row: sqlite3.Row) -> ProviderCliBridgeInfo:
        payload = dict(row)
        payload["supported_delegation_modes"] = self._json_list(payload.pop("supported_delegation_modes_json"))
        payload["metadata"] = self._json_payload(payload.pop("metadata_json"))
        if payload.get("last_error"):
            payload["last_error"] = self._redacted_provider_error(str(payload["last_error"]), fallback="")
        return ProviderCliBridgeInfo.model_validate(payload)

    def _json_list(self, value: str) -> list[str]:
        try:
            payload = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return self._clean_list(payload if isinstance(payload, list) else [])

    def _json_payload(self, value: str) -> dict[str, Any]:
        try:
            payload = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _clean_list(self, values: list[Any]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _credential_hint(self, value: str) -> str:
        key = value.strip()
        if len(key) <= 4:
            return "ending " + ("*" * len(key))
        return "ending " + key[-4:]

    def _subject_hash(self, *parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]

    def _resolve_db_path(self, configured: str) -> Path:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _session(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._session() as conn:
            ensure_provider_account_schema(conn)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
