from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ...schemas import AgentBridgeExecuteRequest, AgentBridgeExecuteResponse
from .cli_bridge import BridgeProbeTarget, CliBridgeAdapter, SECRET_OUTPUT_RE
from .models import ProviderAccountManifest


class AgentBridgeExecutionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PreparedAgentBridgeCommand:
    command: list[str]
    display_command: str
    cwd: Path
    env: dict[str, str]
    metadata: dict[str, Any]
    timeout: int
    started_at: str
    start_counter: float


class AgentBridgeRunner:
    def __init__(
        self,
        cli_bridge: CliBridgeAdapter,
        execution_env_provider: Callable[[ProviderAccountManifest], dict[str, str]] | None = None,
    ):
        self.cli_bridge = cli_bridge
        self.execution_env_provider = execution_env_provider

    def execute(
        self,
        manifest: ProviderAccountManifest,
        request: AgentBridgeExecuteRequest,
        workspace_root: Path,
    ) -> AgentBridgeExecuteResponse:
        started = utc_now()
        start = time.perf_counter()
        warnings: list[str] = []

        if manifest.kind == "local":
            raise AgentBridgeExecutionError(
                "Local model execution is handled by the main Aegis chat route.",
                status_code=400,
            )
        if manifest.cli_bridge is None:
            raise AgentBridgeExecutionError(f"{manifest.label} does not expose a CLI bridge.", status_code=400)

        prepared = self.prepare_command(manifest, request, workspace_root)
        if prepared is None:
            return AgentBridgeExecuteResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="not_configured",
                command="",
                cwd=str(workspace_root),
                started_at=started,
                completed_at=utc_now(),
                duration_ms=self._duration_ms(start),
                warnings=["No runnable CLI or source-drop command was found for this provider."],
            )

        try:
            completed = subprocess.run(
                prepared.command,
                cwd=str(prepared.cwd),
                env=prepared.env,
                capture_output=True,
                text=True,
                timeout=prepared.timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
            stdout = self._redact(completed.stdout)
            stderr = self._redact(completed.stderr)
            exit_code = completed.returncode
            status = "completed" if exit_code == 0 else "failed"
            reply = stdout.strip() or stderr.strip()
        except subprocess.TimeoutExpired as exc:
            stdout = self._redact(exc.stdout if isinstance(exc.stdout, str) else "")
            stderr = self._redact(exc.stderr if isinstance(exc.stderr, str) else "")
            exit_code = None
            status = "timed_out"
            reply = stderr or stdout or f"{manifest.label} timed out after {prepared.timeout} seconds."
            warnings.append(f"{manifest.label} timed out after {prepared.timeout} seconds.")
        except FileNotFoundError:
            stdout = ""
            stderr = "CLI command was not found."
            exit_code = None
            status = "not_configured"
            reply = stderr
        except PermissionError:
            stdout = ""
            stderr = "CLI command could not be executed because permission was denied."
            exit_code = None
            status = "failed"
            reply = stderr

        if status == "failed" and self._looks_like_auth_error(f"{stdout}\n{stderr}"):
            status = "not_configured"
            warnings.append(f"{manifest.label} needs an official login or API key before it can run.")

        completed_at = utc_now()
        return AgentBridgeExecuteResponse(
            ok=status == "completed",
            provider_id=manifest.id,
            provider_label=manifest.label,
            status=status,
            command=prepared.display_command,
            cwd=str(prepared.cwd),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            reply=reply[:24_000],
            started_at=prepared.started_at,
            completed_at=completed_at,
            duration_ms=self._duration_ms(prepared.start_counter),
            warnings=warnings,
            metadata=prepared.metadata,
        )

    def prepare_command(
        self,
        manifest: ProviderAccountManifest,
        request: AgentBridgeExecuteRequest,
        workspace_root: Path,
    ) -> PreparedAgentBridgeCommand | None:
        if manifest.kind == "local":
            raise AgentBridgeExecutionError(
                "Local model execution is handled by the main Aegis chat route.",
                status_code=400,
            )
        if manifest.cli_bridge is None:
            raise AgentBridgeExecutionError(f"{manifest.label} does not expose a CLI bridge.", status_code=400)

        target = self._select_target(manifest)
        if target is None:
            return None

        command, cwd, metadata = self._build_command(manifest, target, request, workspace_root)
        env = os.environ.copy()
        if target.env:
            env.update(target.env)
        if self.execution_env_provider is not None:
            env.update(self.execution_env_provider(manifest))
        return PreparedAgentBridgeCommand(
            command=command,
            display_command=self._display_command(command),
            cwd=cwd,
            env=env,
            metadata=metadata,
            timeout=max(5, min(request.timeout_seconds, 900)),
            started_at=utc_now(),
            start_counter=time.perf_counter(),
        )

    def response_from_process_result(
        self,
        manifest: ProviderAccountManifest,
        prepared: PreparedAgentBridgeCommand,
        *,
        stdout: str,
        stderr: str,
        exit_code: int | None,
        status: str,
        warnings: list[str] | None = None,
    ) -> AgentBridgeExecuteResponse:
        redacted_stdout = self._redact(stdout)
        redacted_stderr = self._redact(stderr)
        next_warnings = [*(warnings or [])]
        next_status = status
        if next_status == "failed" and self._looks_like_auth_error(f"{redacted_stdout}\n{redacted_stderr}"):
            next_status = "not_configured"
            next_warnings.append(f"{manifest.label} needs an official login or API key before it can run.")

        reply = (redacted_stdout.strip() or redacted_stderr.strip())[:24_000]
        return AgentBridgeExecuteResponse(
            ok=next_status == "completed",
            provider_id=manifest.id,
            provider_label=manifest.label,
            status=next_status,
            command=prepared.display_command,
            cwd=str(prepared.cwd),
            exit_code=exit_code,
            stdout=redacted_stdout,
            stderr=redacted_stderr,
            reply=reply,
            started_at=prepared.started_at,
            completed_at=utc_now(),
            duration_ms=self._duration_ms(prepared.start_counter),
            warnings=next_warnings,
            metadata={**prepared.metadata},
        )

    def redact_output(self, value: str) -> str:
        return SECRET_OUTPUT_RE.sub("[redacted]", value or "")[:24_000]

    def _select_target(self, manifest: ProviderAccountManifest) -> BridgeProbeTarget | None:
        targets = self.cli_bridge.targets_for(manifest)
        return targets[0] if targets else None

    def _build_command(
        self,
        manifest: ProviderAccountManifest,
        target: BridgeProbeTarget,
        request: AgentBridgeExecuteRequest,
        workspace_root: Path,
    ) -> tuple[list[str], Path, dict[str, Any]]:
        context_paths = self.normalize_context_paths(request.context_paths)
        prompt = self._execution_prompt(manifest, request, workspace_root, context_paths=context_paths)
        model = request.model.strip()
        allow_edits = request.allow_edits
        provider_id = manifest.id
        command_base = self._execution_command_base(target)
        metadata = {
            "allow_edits": allow_edits,
            "mode": request.mode or "build",
            "context_paths": context_paths,
            "context_path_count": len(context_paths),
        }

        if provider_id == "openai":
            command = [
                *command_base,
                "exec",
                "-c",
                'approval_policy="never"',
                "--skip-git-repo-check",
                "-C",
                str(workspace_root),
                "--sandbox",
                "workspace-write" if allow_edits else "read-only",
            ]
            if model:
                command.extend(["--model", model])
            command.append(prompt)
            return command, workspace_root, {**metadata, "execution_provider": "codex"}

        if provider_id == "anthropic":
            command = [
                *command_base,
                "--print",
                "--output-format",
                "text",
                "--permission-mode",
                "acceptEdits" if allow_edits else "plan",
                "--add-dir",
                str(workspace_root),
            ]
            if model:
                command.extend(["--model", model])
            command.append(prompt)
            return command, workspace_root, {**metadata, "execution_provider": "claude"}

        if provider_id == "google_gemini":
            command = [
                *command_base,
                "--prompt",
                prompt,
                "--output-format",
                "text",
                "--skip-trust",
                "--approval-mode",
                "auto_edit" if allow_edits else "plan",
            ]
            if model:
                command.extend(["--model", model])
            return command, workspace_root, {**metadata, "execution_provider": "gemini"}

        raise AgentBridgeExecutionError(f"{manifest.label} execution is not supported yet.", status_code=400)

    def _execution_command_base(self, target: BridgeProbeTarget) -> list[str]:
        if target.source == "source_drop" and target.cwd:
            cwd = Path(target.cwd)
            command = [*target.command]
            resolved: list[str] = []
            for index, part in enumerate(command):
                if index > 0 and self._looks_like_relative_file(part):
                    candidate = (cwd / part).resolve()
                    resolved.append(str(candidate) if candidate.exists() else part)
                else:
                    resolved.append(part)
            return resolved
        return [*target.command]

    def _looks_like_relative_file(self, value: str) -> bool:
        if not value or value.startswith("-"):
            return False
        path = Path(value)
        return not path.is_absolute() and ("/" in value or "\\" in value or "." in path.name)

    def normalize_context_paths(self, paths: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_path in paths:
            candidate = str(raw_path).strip().strip("`'\"").replace("\\", "/")
            candidate = re.sub(r"^@+", "", candidate)
            candidate = re.sub(r"^\./+", "", candidate)
            candidate = candidate.lstrip("/")
            if not candidate or re.match(r"^[A-Za-z]:/", candidate):
                continue
            parts = [part for part in candidate.split("/") if part]
            if not parts or any(part in {"", ".", ".."} for part in parts):
                continue
            safe_path = "/".join(parts)
            if safe_path in seen:
                continue
            seen.add(safe_path)
            normalized.append(safe_path)
            if len(normalized) >= 50:
                break
        return normalized

    def _execution_prompt(
        self,
        manifest: ProviderAccountManifest,
        request: AgentBridgeExecuteRequest,
        workspace_root: Path,
        *,
        context_paths: list[str],
    ) -> str:
        mode = request.mode or "build"
        context = "\n".join(f"- {path}" for path in context_paths)
        safety = (
            "You may modify files inside this workspace when needed."
            if request.allow_edits
            else "Do not modify files. Plan, inspect, or explain only."
        )
        context_block = f"\nPinned context files:\n{context}" if context else ""
        return (
            f"Run as the {manifest.label} bridge for Aegis Agent Studio.\n"
            f"Mode: {mode}\n"
            f"Workspace: {workspace_root}\n"
            f"{safety}{context_block}\n\n"
            f"User request:\n{request.message.strip()}"
        )

    def _display_command(self, command: list[str]) -> str:
        safe: list[str] = []
        redact_next = False
        redacted_prompt = False
        for part in command:
            if redact_next:
                safe.append("[prompt omitted]")
                redact_next = False
                redacted_prompt = True
                continue
            safe.append(part)
            if part in {"--prompt", "-p"}:
                redact_next = True
        if safe and not redacted_prompt:
            safe[-1] = "[prompt omitted]"
        return " ".join(self._quote(part) for part in safe)

    def _quote(self, value: str) -> str:
        if any(char.isspace() for char in value) and not (value.startswith('"') and value.endswith('"')):
            return f'"{value}"'
        return value

    def _looks_like_auth_error(self, value: str) -> bool:
        text = value.lower()
        return any(
            marker in text
            for marker in (
                "not logged",
                "not authenticated",
                "login required",
                "sign in",
                "auth method",
                "api key",
                "api_key",
                "subscription",
            )
        )

    def _redact(self, value: str) -> str:
        return SECRET_OUTPUT_RE.sub("[redacted]", value or "").strip()[:24_000]

    def _duration_ms(self, start: float) -> int:
        return max(0, int((time.perf_counter() - start) * 1000))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
