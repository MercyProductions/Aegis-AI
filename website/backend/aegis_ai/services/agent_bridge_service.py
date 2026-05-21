from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import subprocess
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from ..chat_streaming import sse_event
from ..providers.accounts.agent_bridge import AgentBridgeExecutionError
from ..schemas import (
    AgentBridgeExecuteRequest,
    AgentBridgeExecuteResponse,
    AgentBridgeJobInfo,
    AgentBridgeJobResponse,
    AgentBridgePreflightResponse,
    AgentRequest,
    CheckpointSummary,
)

_AGENT_BRIDGE_JOB_LIMIT = 50
_AGENT_BRIDGE_JOB_MAX_JSON_BYTES = 1_000_000
_AGENT_BRIDGE_JOB_OUTPUT_CHARS = 12_000
_AGENT_BRIDGE_PREFLIGHT_SCHEMA = "aegis.agent_bridge.preflight.v1"
_AGENT_BRIDGE_JOB_TERMINAL_STATUSES = {
    "completed",
    "failed",
    "timed_out",
    "not_configured",
    "unsupported",
    "canceled",
}
_active_agent_bridge_tasks: dict[str, asyncio.Task[None]] = {}
_active_agent_bridge_processes: dict[str, asyncio.subprocess.Process] = {}
_agent_bridge_cancel_events: dict[str, asyncio.Event] = {}


class AgentBridgeService:
    def __init__(
        self,
        *,
        settings_factory: Callable[[], Any],
        workspace_manager_factory: Callable[[], Any],
        workspace_operations_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        provider_accounts_factory: Callable[[], Any],
        agent_bridge_runner_factory: Callable[[], Any],
        workspace_resolver: Callable[[str | None], Path],
        checkpoint_creator: Callable[[Path, str], Awaitable[CheckpointSummary]],
        runtime_payload_dumper: Callable[[Any], Any],
        jobs_path: Path,
        jobs_lock: threading.RLock,
    ) -> None:
        self._settings_factory = settings_factory
        self._workspace_manager_factory = workspace_manager_factory
        self._workspace_operations_factory = workspace_operations_factory
        self._agent_factory = agent_factory
        self._provider_accounts_factory = provider_accounts_factory
        self._agent_bridge_runner_factory = agent_bridge_runner_factory
        self._workspace_resolver = workspace_resolver
        self._checkpoint_creator = checkpoint_creator
        self._runtime_payload_dumper = runtime_payload_dumper
        self._jobs_path = jobs_path
        self._jobs_lock = jobs_lock

    @property
    def settings(self) -> Any:
        return self._settings_factory()

    @property
    def workspace_manager(self) -> Any:
        return self._workspace_manager_factory()

    @property
    def workspace_operations(self) -> Any:
        return self._workspace_operations_factory()

    @property
    def agent(self) -> Any:
        return self._agent_factory()

    @property
    def provider_accounts(self) -> Any:
        return self._provider_accounts_factory()

    @property
    def agent_bridge_runner(self) -> Any:
        return self._agent_bridge_runner_factory()

    def provider_manifest(self, provider_id: str) -> Any:
        manifest = next((item for item in self.provider_accounts.manifests() if item.id == provider_id.strip()), None)
        if manifest is None:
            raise HTTPException(status_code=404, detail="provider account manifest not found")
        return manifest

    def normalize_request(self, request: AgentBridgeExecuteRequest) -> tuple[Path, AgentBridgeExecuteRequest]:
        root = self._workspace_resolver(request.workspace_root)
        normalized_context_paths = self.agent_bridge_runner.normalize_context_paths(request.context_paths)
        normalized_request = request.model_copy(
            update={"workspace_root": str(root), "context_paths": normalized_context_paths}
        )
        return root, normalized_request

    def workspace_state(self, root: Path, *, max_files: int = 5000) -> dict[str, dict[str, Any]]:
        try:
            files = self.workspace_manager.scan(root, max_files=max_files)
            states = self.workspace_operations.file_states(root, files)
        except OSError:
            return {}
        return {
            state.path: {
                "size": state.size,
                "kind": state.kind,
                "fingerprint": state.fingerprint,
            }
            for state in states
        }

    def workspace_changes(
        self,
        before: dict[str, dict[str, Any]],
        after: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        before_paths = set(before)
        after_paths = set(after)
        created = sorted(after_paths - before_paths)
        deleted = sorted(before_paths - after_paths)
        updated = sorted(
            path
            for path in before_paths & after_paths
            if before[path].get("fingerprint") != after[path].get("fingerprint")
            or before[path].get("size") != after[path].get("size")
        )
        return {
            "created": created[:100],
            "updated": updated[:100],
            "deleted": deleted[:100],
            "created_count": len(created),
            "updated_count": len(updated),
            "deleted_count": len(deleted),
            "changed_total": len(created) + len(updated) + len(deleted),
            "truncated": len(created) > 100 or len(updated) > 100 or len(deleted) > 100,
        }

    def augment_response(
        self,
        response: AgentBridgeExecuteResponse,
        *,
        checkpoint: CheckpointSummary | None,
        before_state: dict[str, dict[str, Any]],
        after_state: dict[str, dict[str, Any]],
    ) -> AgentBridgeExecuteResponse:
        if checkpoint is not None:
            response.checkpoint = checkpoint.id
            response.metadata["checkpoint"] = checkpoint.id
            response.metadata["checkpoint_file_count"] = checkpoint.file_count

        changes = self.workspace_changes(before_state, after_state)
        changed_files = [*changes["created"], *changes["updated"], *changes["deleted"]]
        response.metadata["workspace_changes"] = changes
        response.metadata["changed_files"] = changed_files[:100]
        return response

    def response_payload(self, response: AgentBridgeExecuteResponse) -> dict[str, Any]:
        return self._runtime_payload_dumper(response)

    def job_terminal(self, status: str) -> bool:
        return str(status).lower() in _AGENT_BRIDGE_JOB_TERMINAL_STATUSES

    def trim_output(self, value: str) -> str:
        text = value or ""
        if len(text) <= _AGENT_BRIDGE_JOB_OUTPUT_CHARS:
            return text
        return text[-_AGENT_BRIDGE_JOB_OUTPUT_CHARS:]

    def request_payload(self, request: AgentBridgeExecuteRequest) -> dict[str, Any]:
        return request.model_dump(mode="json")

    def preflight_signature(
        self,
        request: AgentBridgeExecuteRequest,
        preflight: AgentBridgePreflightResponse,
    ) -> str:
        route_metadata = {
            key: preflight.metadata.get(key)
            for key in ("execution_provider", "local_api", "endpoint", "context_path_count")
            if key in preflight.metadata
        }
        payload = {
            "schema": _AGENT_BRIDGE_PREFLIGHT_SCHEMA,
            "request": {
                "provider_id": request.provider_id.strip(),
                "message_hash": hashlib.sha256(request.message.strip().encode("utf-8")).hexdigest(),
                "workspace_root": request.workspace_root or "",
                "mode": request.mode or "build",
                "model": request.model.strip(),
                "allow_edits": request.allow_edits,
                "context_paths": list(request.context_paths),
                "timeout_seconds": request.timeout_seconds,
            },
            "route": {
                "provider_id": preflight.provider_id,
                "provider_label": preflight.provider_label,
                "status": preflight.status,
                "route_type": preflight.route_type,
                "command": preflight.command,
                "cwd": preflight.cwd,
                "timeout_seconds": preflight.timeout_seconds,
                "model": preflight.model,
                "allow_edits": preflight.allow_edits,
                "metadata": route_metadata,
            },
        }
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def preflight_response(
        self,
        request: AgentBridgeExecuteRequest,
        manifest: Any,
        root: Path,
    ) -> AgentBridgePreflightResponse:
        settings = self.settings
        warnings: list[str] = []
        if request.allow_edits:
            warnings.append("This run can modify files and will create a rollback checkpoint before execution.")

        if manifest.kind == "local":
            local_api = "ollama" if manifest.id == "ollama" else settings.aegis_model_api.strip() or "openai-compatible"
            response = AgentBridgePreflightResponse(
                ok=True,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="ready",
                route_type="local",
                command="Aegis local model route",
                cwd=str(root),
                timeout_seconds=max(5, min(request.timeout_seconds, 900)),
                model=request.model or settings.aegis_model_name,
                allow_edits=request.allow_edits,
                message=f"{manifest.label} will run through the local Aegis model adapter.",
                warnings=warnings,
                metadata={
                    "execution_provider": "aegis_local",
                    "local_api": local_api,
                    "endpoint": settings.aegis_model_endpoint,
                    "mode": request.mode or "build",
                    "context_paths": request.context_paths,
                    "context_path_count": len(request.context_paths),
                },
            )
            response.preflight_signature = self.preflight_signature(request, response)
            return response

        try:
            prepared = self.agent_bridge_runner.prepare_command(manifest, request, root)
        except AgentBridgeExecutionError as exc:
            return AgentBridgePreflightResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="unsupported",
                route_type="none",
                cwd=str(root),
                timeout_seconds=max(5, min(request.timeout_seconds, 900)),
                model=request.model,
                allow_edits=request.allow_edits,
                message=str(exc),
                warnings=warnings,
            )

        if prepared is None:
            return AgentBridgePreflightResponse(
                ok=False,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="not_configured",
                route_type="none",
                cwd=str(root),
                timeout_seconds=max(5, min(request.timeout_seconds, 900)),
                model=request.model,
                allow_edits=request.allow_edits,
                message=f"{manifest.label} does not have a runnable CLI or source-drop command yet.",
                warnings=[*warnings, "No runnable CLI or source-drop command was found for this provider."],
            )

        response = AgentBridgePreflightResponse(
            ok=True,
            provider_id=manifest.id,
            provider_label=manifest.label,
            status="ready",
            route_type="cli",
            command=prepared.display_command,
            cwd=str(prepared.cwd),
            timeout_seconds=prepared.timeout,
            model=request.model,
            allow_edits=request.allow_edits,
            message=f"{manifest.label} bridge is ready to queue.",
            warnings=warnings,
            metadata={**prepared.metadata},
        )
        response.preflight_signature = self.preflight_signature(request, response)
        return response

    def require_preflight(
        self,
        request: AgentBridgeExecuteRequest,
        manifest: Any,
        root: Path,
    ) -> AgentBridgePreflightResponse:
        signature = request.preflight_signature.strip()
        if not signature:
            raise HTTPException(status_code=428, detail="Run Preflight before queueing a provider bridge job.")

        preflight = self.preflight_response(request, manifest, root)
        if not preflight.ok:
            raise HTTPException(status_code=409, detail=preflight.message or "Provider bridge preflight is not ready.")
        if preflight.preflight_signature != signature:
            raise HTTPException(status_code=409, detail="Provider bridge preflight changed. Run Preflight again before queueing.")
        return preflight

    def load_jobs(self) -> list[AgentBridgeJobInfo]:
        with self._jobs_lock:
            if not self._jobs_path.exists():
                return []
            try:
                if self._jobs_path.stat().st_size > _AGENT_BRIDGE_JOB_MAX_JSON_BYTES:
                    return []
                payload = json.loads(self._jobs_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
            jobs: list[AgentBridgeJobInfo] = []
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                try:
                    jobs.append(AgentBridgeJobInfo.model_validate(item))
                except Exception:
                    continue
            return jobs

    def save_jobs(self, jobs: list[AgentBridgeJobInfo]) -> None:
        with self._jobs_lock:
            self._jobs_path.parent.mkdir(parents=True, exist_ok=True)
            trimmed = sorted(jobs, key=lambda job: job.created_at, reverse=True)[:_AGENT_BRIDGE_JOB_LIMIT]
            self._jobs_path.write_text(
                json.dumps([job.model_dump(mode="json") for job in trimmed], ensure_ascii=True, indent=2),
                encoding="utf-8",
            )

    def upsert_job(self, job: AgentBridgeJobInfo) -> None:
        with self._jobs_lock:
            jobs = [item for item in self.load_jobs() if item.id != job.id]
            jobs.append(job)
            self.save_jobs(jobs)

    def jobs(self, limit: int = 25) -> list[AgentBridgeJobInfo]:
        jobs = sorted(self.load_jobs(), key=lambda job: job.created_at, reverse=True)
        return jobs[: max(1, min(limit, 100))]

    def job_or_404(self, job_id: str) -> AgentBridgeJobInfo:
        wanted = job_id.strip()
        for job in self.load_jobs():
            if job.id == wanted:
                return job
        raise HTTPException(status_code=404, detail="Agent bridge job was not found.")

    def new_job(self, request: AgentBridgeExecuteRequest, *, retry_of: str = "") -> AgentBridgeJobInfo:
        root, normalized_request = self.normalize_request(request)
        manifest = self.provider_manifest(request.provider_id)

        now = datetime.now(timezone.utc).isoformat()
        metadata: dict[str, Any] = {}
        if retry_of:
            metadata["retry_of"] = retry_of
        job = AgentBridgeJobInfo(
            id=f"agent-bridge-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            provider_id=manifest.id,
            provider_label=manifest.label,
            mode=request.mode,
            model=request.model,
            workspace_root=str(root),
            allow_edits=request.allow_edits,
            status="queued",
            cwd=str(root),
            message=f"{manifest.label} bridge queued.",
            created_at=now,
            updated_at=now,
            request=self.request_payload(normalized_request),
            metadata=metadata,
        )
        self.upsert_job(job)
        return job

    def job_from_response(
        self,
        job: AgentBridgeJobInfo,
        response: AgentBridgeExecuteResponse,
        *,
        message: str = "",
    ) -> AgentBridgeJobInfo:
        job.provider_id = response.provider_id
        job.provider_label = response.provider_label
        job.status = response.status
        job.command = response.command
        job.cwd = response.cwd
        job.pid = None
        job.exit_code = response.exit_code
        job.stdout = self.trim_output(response.stdout)
        job.stderr = self.trim_output(response.stderr)
        job.reply = self.trim_output(response.reply)
        job.duration_ms = response.duration_ms
        job.warnings = response.warnings
        job.checkpoint = response.checkpoint
        job.finished_at = response.completed_at
        job.updated_at = response.completed_at
        job.message = message or f"{response.provider_label} bridge {response.status}."
        job.metadata = {**job.metadata, **response.metadata}
        return job

    async def preflight_agent_bridge(self, request: AgentBridgeExecuteRequest) -> AgentBridgePreflightResponse:
        root, request = self.normalize_request(request)
        manifest = self.provider_manifest(request.provider_id)
        return self.preflight_response(request, manifest, root)

    async def execute_agent_bridge(self, request: AgentBridgeExecuteRequest) -> AgentBridgeExecuteResponse:
        root, request = self.normalize_request(request)
        manifest = self.provider_manifest(request.provider_id)
        settings = self.settings

        if manifest.kind == "local":
            local_api = "ollama" if manifest.id == "ollama" else settings.aegis_model_api.strip() or "openai-compatible"
            response = await self.agent.run(
                AgentRequest(
                    message=request.message,
                    workspace_root=str(root),
                    mode=request.mode,
                    selected_provider_id=manifest.id,
                    selected_provider_label=manifest.label,
                    selected_provider_api=local_api,
                    selected_provider_endpoint=settings.aegis_model_endpoint,
                    selected_provider_model=request.model or settings.aegis_model_name,
                    apply_changes=request.allow_edits,
                    run_validation=False,
                    context_paths=request.context_paths,
                )
            )
            now = datetime.now(timezone.utc).isoformat()
            return AgentBridgeExecuteResponse(
                ok=True,
                provider_id=manifest.id,
                provider_label=manifest.label,
                status="completed",
                command="Aegis local model route",
                cwd=str(root),
                exit_code=0,
                stdout=response.reply,
                reply=response.reply,
                started_at=now,
                completed_at=now,
                duration_ms=0,
                checkpoint=response.checkpoint,
                metadata={
                    "execution_provider": "aegis_local",
                    "task_id": response.task_id,
                    "mode": request.mode or "build",
                    "context_paths": request.context_paths,
                    "context_path_count": len(request.context_paths),
                },
            )

        try:
            before_state = self.workspace_state(root)
            checkpoint = await self._checkpoint_creator(root, manifest.label) if request.allow_edits else None
            response = await asyncio.to_thread(self.agent_bridge_runner.execute, manifest, request, root)
            after_state = self.workspace_state(root)
            return self.augment_response(
                response,
                checkpoint=checkpoint,
                before_state=before_state,
                after_state=after_state,
            )
        except AgentBridgeExecutionError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"checkpoint could not be created: {exc}") from exc

    async def start_job(self, request: AgentBridgeExecuteRequest, *, retry_of: str = "") -> AgentBridgeJobResponse:
        if not retry_of or request.preflight_signature:
            root, request = self.normalize_request(request)
            manifest = self.provider_manifest(request.provider_id)
            self.require_preflight(request, manifest, root)

        job = self.new_job(request, retry_of=retry_of)
        normalized_request = AgentBridgeExecuteRequest.model_validate(job.request)
        cancel_event = asyncio.Event()
        _agent_bridge_cancel_events[job.id] = cancel_event
        task = asyncio.create_task(self.run_job(job.id, normalized_request, cancel_event))
        _active_agent_bridge_tasks[job.id] = task
        task.add_done_callback(lambda finished_task, job_id=job.id: self.handle_job_done(job_id, finished_task))
        return AgentBridgeJobResponse(job=job)

    async def run_job(
        self,
        job_id: str,
        request: AgentBridgeExecuteRequest,
        cancel_event: asyncio.Event,
    ) -> None:
        job = self.job_or_404(job_id)
        root = self._workspace_resolver(request.workspace_root)
        try:
            manifest = self.provider_manifest(request.provider_id)
        except HTTPException:
            job.status = "not_configured"
            job.message = "Provider account manifest was not found."
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.updated_at = job.finished_at
            self.upsert_job(job)
            return

        before_state: dict[str, dict[str, Any]] = {}
        checkpoint: CheckpointSummary | None = None
        process: asyncio.subprocess.Process | None = None
        prepared: Any | None = None
        started_counter = time.perf_counter()
        try:
            before_state = self.workspace_state(root)
            if manifest.kind == "local":
                job.status = "running"
                job.started_at = datetime.now(timezone.utc).isoformat()
                job.updated_at = job.started_at
                job.command = "Aegis local model route"
                job.message = f"{manifest.label} local route is running."
                self.upsert_job(job)
                response = await self.execute_agent_bridge(request)
                job = self.job_from_response(job, response)
                self.upsert_job(job)
                return

            if request.allow_edits:
                job.status = "checkpoint"
                job.message = f"Creating rollback checkpoint before {manifest.label} can edit files."
                job.updated_at = datetime.now(timezone.utc).isoformat()
                self.upsert_job(job)
                checkpoint = await self._checkpoint_creator(root, manifest.label)
                job.checkpoint = checkpoint.id

            prepared = self.agent_bridge_runner.prepare_command(manifest, request, root)
            if prepared is None:
                now = datetime.now(timezone.utc).isoformat()
                response = AgentBridgeExecuteResponse(
                    ok=False,
                    provider_id=manifest.id,
                    provider_label=manifest.label,
                    status="not_configured",
                    command="",
                    cwd=str(root),
                    started_at=now,
                    completed_at=now,
                    duration_ms=0,
                    warnings=["No runnable CLI or source-drop command was found for this provider."],
                )
                response = self.augment_response(
                    response,
                    checkpoint=checkpoint,
                    before_state=before_state,
                    after_state=self.workspace_state(root),
                )
                job = self.job_from_response(
                    job,
                    response,
                    message=f"{manifest.label} does not have a runnable bridge command yet.",
                )
                self.upsert_job(job)
                return

            job.status = "running"
            job.command = prepared.display_command
            job.cwd = str(prepared.cwd)
            job.started_at = prepared.started_at
            job.updated_at = job.started_at
            job.message = f"{manifest.label} bridge is running."
            self.upsert_job(job)

            try:
                process = await asyncio.create_subprocess_exec(
                    *prepared.command,
                    cwd=str(prepared.cwd),
                    env=prepared.env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except FileNotFoundError:
                response = self.agent_bridge_runner.response_from_process_result(
                    manifest,
                    prepared,
                    stdout="",
                    stderr="CLI command was not found.",
                    exit_code=None,
                    status="not_configured",
                )
                job = self.job_from_response(job, response)
                self.upsert_job(job)
                return
            except PermissionError:
                response = self.agent_bridge_runner.response_from_process_result(
                    manifest,
                    prepared,
                    stdout="",
                    stderr="CLI command could not be executed because permission was denied.",
                    exit_code=None,
                    status="failed",
                )
                job = self.job_from_response(job, response)
                self.upsert_job(job)
                return

            _active_agent_bridge_processes[job_id] = process
            job.pid = process.pid
            job.updated_at = datetime.now(timezone.utc).isoformat()
            self.upsert_job(job)

            queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
            reader_tasks = [
                asyncio.create_task(self.read_stream(process.stdout, "stdout", queue)),
                asyncio.create_task(self.read_stream(process.stderr, "stderr", queue)),
            ]
            stdout_parts: list[str] = []
            stderr_parts: list[str] = []
            warnings: list[str] = []
            closed_streams = 0
            timed_out = False
            canceled = False
            deadline = time.perf_counter() + prepared.timeout

            while closed_streams < 2:
                if cancel_event.is_set():
                    canceled = True
                    await self.terminate_process(process)
                    break
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    warnings.append(f"{manifest.label} timed out after {prepared.timeout} seconds.")
                    await self.terminate_process(process)
                    break
                try:
                    stream_name, text = await asyncio.wait_for(queue.get(), timeout=min(0.25, remaining))
                except asyncio.TimeoutError:
                    continue
                if text is None:
                    closed_streams += 1
                    continue
                safe_text = self.agent_bridge_runner.redact_output(text)
                if stream_name == "stderr":
                    stderr_parts.append(safe_text)
                else:
                    stdout_parts.append(safe_text)
                job.stdout = self.trim_output("".join(stdout_parts))
                job.stderr = self.trim_output("".join(stderr_parts))
                job.duration_ms = int((time.perf_counter() - started_counter) * 1000)
                job.updated_at = datetime.now(timezone.utc).isoformat()
                self.upsert_job(job)

            if reader_tasks:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.gather(*reader_tasks, return_exceptions=True), timeout=5)
            while not queue.empty():
                stream_name, text = queue.get_nowait()
                if text is None:
                    continue
                safe_text = self.agent_bridge_runner.redact_output(text)
                if stream_name == "stderr":
                    stderr_parts.append(safe_text)
                else:
                    stdout_parts.append(safe_text)

            if cancel_event.is_set():
                canceled = True
            if timed_out:
                exit_code = process.returncode
                status = "timed_out"
            elif canceled:
                exit_code = process.returncode
                status = "canceled"
                warnings.append(f"{manifest.label} bridge was canceled.")
            else:
                exit_code = await process.wait()
                status = "completed" if exit_code == 0 else "failed"

            response = self.agent_bridge_runner.response_from_process_result(
                manifest,
                prepared,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=exit_code,
                status=status,
                warnings=warnings,
            )
            response = self.augment_response(
                response,
                checkpoint=checkpoint,
                before_state=before_state,
                after_state=self.workspace_state(root),
            )
            job = self.job_from_response(job, response)
            self.upsert_job(job)
        except AgentBridgeExecutionError as exc:
            job.status = "unsupported"
            job.message = str(exc)
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.updated_at = job.finished_at
            self.upsert_job(job)
        except Exception as exc:
            job.status = "failed"
            job.message = f"Agent bridge job failed: {exc}"
            job.stderr = str(exc)
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.updated_at = job.finished_at
            self.upsert_job(job)
        finally:
            _active_agent_bridge_processes.pop(job_id, None)
            _agent_bridge_cancel_events.pop(job_id, None)

    def handle_job_done(self, job_id: str, task: asyncio.Task[None]) -> None:
        _active_agent_bridge_tasks.pop(job_id, None)
        if task.cancelled():
            job = self.job_or_404(job_id)
            job.status = "canceled"
            job.message = "Agent bridge job was canceled."
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.updated_at = job.finished_at
            self.upsert_job(job)
            return
        try:
            task.result()
        except Exception as exc:
            job = self.job_or_404(job_id)
            job.status = "failed"
            job.message = f"Agent bridge job failed: {exc}"
            job.stderr = str(exc)
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.updated_at = job.finished_at
            self.upsert_job(job)

    async def cancel_job(self, job_id: str) -> AgentBridgeJobResponse:
        job = self.job_or_404(job_id)
        if self.job_terminal(job.status):
            return AgentBridgeJobResponse(job=job)

        event = _agent_bridge_cancel_events.get(job.id)
        if event is not None:
            event.set()

        process = _active_agent_bridge_processes.get(job.id)
        if process is not None and process.returncode is None:
            await self.terminate_process(process)

        task = _active_agent_bridge_tasks.get(job.id)
        if process is None and task is not None and not task.done():
            task.cancel()

        now = datetime.now(timezone.utc).isoformat()
        job.status = "running" if process is not None and process.returncode is None else "canceled"
        job.message = f"Cancel requested for {job.provider_label or job.provider_id} bridge."
        job.updated_at = now
        if job.status == "canceled":
            job.finished_at = now
        job.metadata = {**job.metadata, "cancel_requested": True}
        self.upsert_job(job)
        return AgentBridgeJobResponse(job=job)

    async def retry_job(self, job_id: str) -> AgentBridgeJobResponse:
        job = self.job_or_404(job_id)
        if not self.job_terminal(job.status):
            raise HTTPException(status_code=409, detail="Agent bridge job is still active.")
        request = AgentBridgeExecuteRequest.model_validate(job.request)
        return await self.start_job(request, retry_of=job.id)

    async def terminate_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            pass
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5)

    async def read_stream(
        self,
        reader: asyncio.StreamReader | None,
        stream_name: str,
        queue: asyncio.Queue[tuple[str, str | None]],
    ) -> None:
        if reader is None:
            await queue.put((stream_name, None))
            return

        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            await queue.put((stream_name, chunk.decode("utf-8", errors="replace")))
        await queue.put((stream_name, None))

    async def stream_events(
        self,
        request: AgentBridgeExecuteRequest,
        root: Path,
        manifest: Any,
    ) -> AsyncIterator[str]:
        stream_request = request.model_copy(update={"workspace_root": str(root)})
        stream_job = self.new_job(stream_request)
        checkpoint: CheckpointSummary | None = None
        before_state: dict[str, dict[str, Any]] = {}
        process: asyncio.subprocess.Process | None = None
        reader_tasks: list[asyncio.Task[None]] = []

        def record_stream_status(status: str, message: str, **updates: Any) -> None:
            stream_job.status = status
            stream_job.message = message
            stream_job.updated_at = datetime.now(timezone.utc).isoformat()
            for key, value in updates.items():
                setattr(stream_job, key, value)
            self.upsert_job(stream_job)

        def record_stream_response(response: AgentBridgeExecuteResponse, message: str = "") -> None:
            nonlocal stream_job
            stream_job = self.job_from_response(stream_job, response, message=message)
            self.upsert_job(stream_job)

        yield sse_event(
            "meta",
            {
                "type": "meta",
                "schema_version": "aegis.agent_bridge.stream.v1",
                "job_id": stream_job.id,
                "stream_mode": "provider-cli-delta-final",
                "workspace_root": str(root),
                "mode": request.mode or "auto",
                "provider_id": manifest.id,
                "provider_label": manifest.label,
                "model": request.model,
            },
        )

        try:
            before_state = self.workspace_state(root)
            if request.allow_edits:
                record_stream_status(
                    "checkpoint",
                    f"Creating rollback checkpoint before {manifest.label} can edit files.",
                )
                yield sse_event(
                    "status",
                    {
                        "type": "status",
                        "stage": "checkpoint",
                        "message": f"Creating rollback checkpoint before {manifest.label} can edit files.",
                    },
                )
                checkpoint = await self._checkpoint_creator(root, manifest.label)
                stream_job.checkpoint = checkpoint.id
                record_stream_status("checkpoint", f"Checkpoint ready: {checkpoint.id}", checkpoint=checkpoint.id)
                yield sse_event(
                    "status",
                    {
                        "type": "status",
                        "stage": "checkpoint_ready",
                        "message": f"Checkpoint ready: {checkpoint.id}",
                        "checkpoint": checkpoint.id,
                    },
                )

            prepared = self.agent_bridge_runner.prepare_command(manifest, request, root)
            if prepared is None:
                now = datetime.now(timezone.utc).isoformat()
                response = AgentBridgeExecuteResponse(
                    ok=False,
                    provider_id=manifest.id,
                    provider_label=manifest.label,
                    status="not_configured",
                    command="",
                    cwd=str(root),
                    started_at=now,
                    completed_at=now,
                    duration_ms=0,
                    warnings=["No runnable CLI or source-drop command was found for this provider."],
                )
                response = self.augment_response(
                    response,
                    checkpoint=checkpoint,
                    before_state=before_state,
                    after_state=self.workspace_state(root),
                )
                record_stream_response(response, message=f"{manifest.label} does not have a runnable bridge command yet.")
                yield sse_event(
                    "status",
                    {
                        "type": "status",
                        "stage": "not_configured",
                        "message": f"{manifest.label} does not have a runnable bridge command yet.",
                    },
                )
                yield sse_event(
                    "final",
                    {
                        "type": "final",
                        "provider_id": manifest.id,
                        "provider_label": manifest.label,
                        "bridge_response": self.response_payload(response),
                    },
                )
                yield sse_event("done", {"type": "done"})
                return

            record_stream_status(
                "running",
                f"{manifest.label} bridge is launching.",
                command=prepared.display_command,
                cwd=str(prepared.cwd),
                started_at=prepared.started_at,
            )
            yield sse_event(
                "status",
                {
                    "type": "status",
                    "stage": "launching",
                    "message": f"Launching {manifest.label} bridge.",
                    "command": prepared.display_command,
                },
            )

            try:
                process = await asyncio.create_subprocess_exec(
                    *prepared.command,
                    cwd=str(prepared.cwd),
                    env=prepared.env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except FileNotFoundError:
                response = self.agent_bridge_runner.response_from_process_result(
                    manifest,
                    prepared,
                    stdout="",
                    stderr="CLI command was not found.",
                    exit_code=None,
                    status="not_configured",
                )
                response = self.augment_response(
                    response,
                    checkpoint=checkpoint,
                    before_state=before_state,
                    after_state=self.workspace_state(root),
                )
                record_stream_response(response)
                yield sse_event("final", {"type": "final", "bridge_response": self.response_payload(response)})
                yield sse_event("done", {"type": "done"})
                return
            except PermissionError:
                response = self.agent_bridge_runner.response_from_process_result(
                    manifest,
                    prepared,
                    stdout="",
                    stderr="CLI command could not be executed because permission was denied.",
                    exit_code=None,
                    status="failed",
                )
                response = self.augment_response(
                    response,
                    checkpoint=checkpoint,
                    before_state=before_state,
                    after_state=self.workspace_state(root),
                )
                record_stream_response(response)
                yield sse_event("final", {"type": "final", "bridge_response": self.response_payload(response)})
                yield sse_event("done", {"type": "done"})
                return

            _active_agent_bridge_processes[stream_job.id] = process
            stream_job.pid = process.pid
            stream_job.message = f"{manifest.label} bridge is running."
            stream_job.updated_at = datetime.now(timezone.utc).isoformat()
            self.upsert_job(stream_job)

            queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
            reader_tasks = [
                asyncio.create_task(self.read_stream(process.stdout, "stdout", queue)),
                asyncio.create_task(self.read_stream(process.stderr, "stderr", queue)),
            ]
            stdout_parts: list[str] = []
            stderr_parts: list[str] = []
            warnings: list[str] = []
            closed_streams = 0
            timed_out = False
            deadline = time.perf_counter() + prepared.timeout

            while closed_streams < 2:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    warnings.append(f"{manifest.label} timed out after {prepared.timeout} seconds.")
                    yield sse_event(
                        "status",
                        {
                            "type": "status",
                            "stage": "timed_out",
                            "message": f"{manifest.label} timed out; stopping the bridge process.",
                        },
                    )
                    await self.terminate_process(process)
                    break
                try:
                    stream_name, text = await asyncio.wait_for(queue.get(), timeout=min(0.25, remaining))
                except asyncio.TimeoutError:
                    continue
                if text is None:
                    closed_streams += 1
                    continue
                if stream_name == "stderr":
                    stderr_parts.append(text)
                else:
                    stdout_parts.append(text)
                safe_text = self.agent_bridge_runner.redact_output(text)
                if stream_name == "stderr":
                    stream_job.stderr = self.trim_output(f"{stream_job.stderr}{safe_text}")
                else:
                    stream_job.stdout = self.trim_output(f"{stream_job.stdout}{safe_text}")
                stream_job.duration_ms = int((time.perf_counter() - prepared.start_counter) * 1000)
                stream_job.updated_at = datetime.now(timezone.utc).isoformat()
                self.upsert_job(stream_job)
                if safe_text:
                    yield sse_event(
                        "delta",
                        {
                            "type": "delta",
                            "delta": safe_text,
                            "source": "agent_bridge_cli",
                            "stream": stream_name,
                            "provider_id": manifest.id,
                            "provider_label": manifest.label,
                            "stream_mode": "provider-cli-delta-final",
                        },
                    )

            if reader_tasks:
                try:
                    await asyncio.wait_for(asyncio.gather(*reader_tasks, return_exceptions=True), timeout=5)
                except asyncio.TimeoutError:
                    for task in reader_tasks:
                        task.cancel()
            while not queue.empty():
                stream_name, text = queue.get_nowait()
                if text is None:
                    continue
                if stream_name == "stderr":
                    stderr_parts.append(text)
                else:
                    stdout_parts.append(text)
                safe_text = self.agent_bridge_runner.redact_output(text)
                if stream_name == "stderr":
                    stream_job.stderr = self.trim_output(f"{stream_job.stderr}{safe_text}")
                else:
                    stream_job.stdout = self.trim_output(f"{stream_job.stdout}{safe_text}")
                stream_job.duration_ms = int((time.perf_counter() - prepared.start_counter) * 1000)
                stream_job.updated_at = datetime.now(timezone.utc).isoformat()
                self.upsert_job(stream_job)
                if safe_text:
                    yield sse_event(
                        "delta",
                        {
                            "type": "delta",
                            "delta": safe_text,
                            "source": "agent_bridge_cli",
                            "stream": stream_name,
                            "provider_id": manifest.id,
                            "provider_label": manifest.label,
                        },
                    )

            if timed_out:
                exit_code = process.returncode
                status = "timed_out"
            elif self.job_or_404(stream_job.id).metadata.get("cancel_requested"):
                exit_code = process.returncode
                status = "canceled"
                warnings.append(f"{manifest.label} bridge was canceled.")
            else:
                exit_code = await process.wait()
                status = "completed" if exit_code == 0 else "failed"

            response = self.agent_bridge_runner.response_from_process_result(
                manifest,
                prepared,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=exit_code,
                status=status,
                warnings=warnings,
            )
            response = self.augment_response(
                response,
                checkpoint=checkpoint,
                before_state=before_state,
                after_state=self.workspace_state(root),
            )
            record_stream_response(response)
            yield sse_event(
                "status",
                {
                    "type": "status",
                    "stage": response.status,
                    "message": f"{manifest.label} bridge {response.status}.",
                },
            )
            yield sse_event(
                "final",
                {
                    "type": "final",
                    "provider_id": manifest.id,
                    "provider_label": manifest.label,
                    "bridge_response": self.response_payload(response),
                },
            )
            yield sse_event("done", {"type": "done"})
        except asyncio.CancelledError:
            if process is not None:
                await self.terminate_process(process)
            now = datetime.now(timezone.utc).isoformat()
            stream_job.status = "canceled"
            stream_job.message = f"{manifest.label} bridge stream was canceled."
            stream_job.finished_at = now
            stream_job.updated_at = now
            stream_job.metadata = {**stream_job.metadata, "cancel_requested": True}
            self.upsert_job(stream_job)
            raise
        except AgentBridgeExecutionError as exc:
            now = datetime.now(timezone.utc).isoformat()
            stream_job.status = "unsupported"
            stream_job.message = str(exc)
            stream_job.finished_at = now
            stream_job.updated_at = now
            self.upsert_job(stream_job)
            yield sse_event("error", {"type": "error", "message": str(exc), "detail": str(exc)})
            yield sse_event("done", {"type": "done"})
        except Exception as exc:
            now = datetime.now(timezone.utc).isoformat()
            stream_job.status = "failed"
            stream_job.message = f"{manifest.label} bridge failed before returning a final response."
            stream_job.stderr = str(exc)
            stream_job.finished_at = now
            stream_job.updated_at = now
            self.upsert_job(stream_job)
            yield sse_event(
                "error",
                {
                    "type": "error",
                    "message": f"{manifest.label} bridge failed before returning a final response.",
                    "detail": str(exc),
                },
            )
            yield sse_event("done", {"type": "done"})
        finally:
            _active_agent_bridge_processes.pop(stream_job.id, None)
            for task in reader_tasks:
                if not task.done():
                    task.cancel()

    async def stream_agent_bridge(self, request: AgentBridgeExecuteRequest) -> StreamingResponse:
        root = self._workspace_resolver(request.workspace_root)
        manifest = self.provider_manifest(request.provider_id)
        if manifest.kind == "local":
            raise HTTPException(status_code=400, detail="Local model execution is handled by the main Aegis chat route.")
        return StreamingResponse(
            self.stream_events(request, root, manifest),
            media_type="text/event-stream",
        )
