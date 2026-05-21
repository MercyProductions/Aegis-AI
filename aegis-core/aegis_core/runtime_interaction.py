from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from .diagnostics import scrub
from .memory import ProjectMemory, utc_now
from .validation import is_safe_validation_command


STATE_FILE = "runtime-interaction.json"
MAX_JOBS = 200
MAX_EVENTS = 4000
MAX_SESSIONS = 50
MAX_OUTPUT_CHARS = 16000
MAX_CHUNK_CHARS = 4000
RUNNING_STATES = {"queued", "running", "cancel_requested"}

_STATE_LOCK = threading.RLock()
_ACTIVE_PROCESSES: dict[str, subprocess.Popen[str]] = {}


class RuntimeInteractionError(RuntimeError):
    """Raised when runtime interaction state or safety validation fails."""


class RuntimeJobNotFoundError(KeyError):
    """Raised when a runtime job id is not known for a workspace."""


def runtime_dashboard(workspace: str | Path, *, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    jobs = _sorted_jobs(state.get("jobs", []))[: max(1, min(300, int(limit)))]
    events = _sorted_events(state.get("events", []))[: max(1, min(500, int(limit)))]
    active_jobs = [job for job in jobs if job.get("status") in RUNNING_STATES]
    terminals = _terminal_summaries(jobs)
    sessions = _sorted_sessions(state.get("sessions", []))
    return {
        "schema_version": 1,
        "workspace": str(root),
        "generated_at": utc_now(),
        "terminals": terminals,
        "jobs": jobs,
        "active_jobs": active_jobs,
        "recent_events": events,
        "processes": runtime_processes(root)["processes"],
        "sessions": sessions,
        "voice": voice_status(root),
        "observability": _observability(root, state),
        "safety_controls": _safety_controls(),
        "replay_available": True,
        "stream_endpoint": "/v1/runtime/streams",
    }


def compact_summary(workspace: str | Path) -> dict[str, Any]:
    try:
        dashboard = runtime_dashboard(workspace, limit=25)
    except RuntimeInteractionError as exc:
        return {
            "status": "error",
            "job_count": 0,
            "active_jobs": 0,
            "terminal_count": 0,
            "session_count": 0,
            "error": scrub(str(exc)),
        }
    observability = dashboard.get("observability", {}) if isinstance(dashboard.get("observability"), dict) else {}
    return {
        "status": "ready",
        "job_count": int(observability.get("job_count") or 0),
        "active_jobs": int(observability.get("active_jobs") or 0),
        "failed_jobs": int(observability.get("failed_jobs") or 0),
        "terminal_count": int(observability.get("terminal_count") or 0),
        "session_count": int(observability.get("session_count") or 0),
        "active_processes": int(observability.get("active_processes") or 0),
        "latest_event": (dashboard.get("recent_events") or [{}])[0].get("event_type") if dashboard.get("recent_events") else "",
        "stream_endpoint": dashboard.get("stream_endpoint", "/v1/runtime/streams"),
    }


def list_jobs(workspace: str | Path, *, status: str | None = None, limit: int = 100) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    jobs = _sorted_jobs(state.get("jobs", []))
    if status:
        jobs = [job for job in jobs if str(job.get("status") or "") == status]
    return {"workspace": str(root), "jobs": jobs[: max(1, min(300, int(limit)))], "observability": _observability(root, state)}


def get_job(workspace: str | Path, job_id: str) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    job = _find_job(state, job_id)
    events = [
        event
        for event in _sorted_events(state.get("events", []))
        if event.get("job_id") == job.get("job_id")
    ]
    return {"workspace": str(root), "job": job, "events": events[:500], "process": _process_snapshot(job["job_id"])}


def launch_terminal_job(
    workspace: str | Path,
    command: str | list[str],
    *,
    cwd: str | None = None,
    workflow_id: str | None = None,
    task_id: str | None = None,
    terminal_id: str | None = None,
    title: str = "",
    timeout_seconds: int = 120,
    approval: bool = False,
    dry_run: bool = False,
    wait: bool = True,
    source_client: str = "unknown",
    restart_of: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_command = _normalize_command(command)
    clean_cwd = _normalize_cwd(root, cwd)
    timeout = max(1, min(3600, int(timeout_seconds or 120)))
    safety = _command_safety(clean_command, approval=approval)
    now = utc_now()
    job_id = f"rt-job-{uuid.uuid4().hex[:12]}"
    terminal = _safe_id(terminal_id, prefix="terminal")
    job = {
        "job_id": job_id,
        "terminal_id": terminal,
        "workflow_id": scrub(workflow_id or ""),
        "task_id": scrub(task_id or ""),
        "title": scrub(title or " ".join(clean_command[:3])),
        "command": clean_command,
        "command_text": scrub(" ".join(clean_command)),
        "cwd": str(clean_cwd),
        "workspace": str(root),
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "timeout_seconds": timeout,
        "exit_code": None,
        "timed_out": False,
        "approval_required": bool(safety.get("approval_required")),
        "approved": bool(approval),
        "dry_run": bool(dry_run),
        "source_client": scrub(source_client or "unknown"),
        "restart_of": scrub(restart_of or ""),
        "stdout_tail": "",
        "stderr_tail": "",
        "output_event_count": 0,
        "safety": safety,
        "metadata": _safe_metadata(metadata or {}),
    }
    if not safety.get("allowed", False):
        job["status"] = "blocked"
        job["finished_at"] = now
        job["updated_at"] = now
    if dry_run and safety.get("allowed", False):
        job["status"] = "dry_run"
        job["finished_at"] = now
        job["updated_at"] = now

    _mutate_state(root, lambda state: _record_job(state, job))
    _append_event(root, "runtime.job.created", job_id=job_id, terminal_id=terminal, workflow_id=workflow_id, message=job["title"])

    if job["status"] == "blocked":
        _append_event(
            root,
            "runtime.command.blocked",
            job_id=job_id,
            terminal_id=terminal,
            workflow_id=workflow_id,
            message=safety.get("reason", "Command blocked by runtime safety policy."),
            severity="warning",
        )
        return _job_mutation(root, job_id, "blocked")

    if dry_run:
        _append_event(root, "runtime.job.dry_run", job_id=job_id, terminal_id=terminal, workflow_id=workflow_id, message="Dry run recorded; command was not executed.")
        return _job_mutation(root, job_id, "dry_run")

    if wait:
        _execute_job(root, job_id)
    else:
        thread = threading.Thread(target=_execute_job, args=(root, job_id), name=f"aegis-runtime-{job_id}", daemon=True)
        thread.start()
    return _job_mutation(root, job_id, "started")


def cancel_job(workspace: str | Path, job_id: str, *, reason: str = "") -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_lookup_id(job_id)
    with _STATE_LOCK:
        state = _load_state(root)
        job = _find_job(state, clean_id)
        if job.get("status") not in RUNNING_STATES:
            return _job_mutation(root, clean_id, "not_running")
        job["status"] = "cancel_requested"
        job["updated_at"] = utc_now()
        _save_state(root, state)
        process = _ACTIVE_PROCESSES.get(clean_id)
        if process and process.poll() is None:
            process.terminate()
    _append_event(root, "runtime.job.cancel_requested", job_id=clean_id, terminal_id=job.get("terminal_id"), workflow_id=job.get("workflow_id"), message=reason or "Cancellation requested.", severity="warning")
    return _job_mutation(root, clean_id, "cancel_requested")


def retry_job(
    workspace: str | Path,
    job_id: str,
    *,
    approval: bool | None = None,
    wait: bool = True,
    timeout_seconds: int | None = None,
    reason: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    old = get_job(root, job_id)["job"]
    return launch_terminal_job(
        root,
        old.get("command") or [],
        cwd=old.get("cwd"),
        workflow_id=old.get("workflow_id"),
        task_id=old.get("task_id"),
        terminal_id=old.get("terminal_id"),
        title=f"Retry: {old.get('title') or old.get('job_id')}",
        timeout_seconds=timeout_seconds or int(old.get("timeout_seconds") or 120),
        approval=bool(old.get("approved")) if approval is None else bool(approval),
        wait=wait,
        source_client=old.get("source_client") or "unknown",
        restart_of=old.get("job_id"),
        metadata={"retry_reason": scrub(reason), "previous_status": old.get("status")},
    )


def runtime_processes(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    processes: list[dict[str, Any]] = []
    with _STATE_LOCK:
        for job_id, process in list(_ACTIVE_PROCESSES.items()):
            status = process.poll()
            processes.append(
                {
                    "job_id": job_id,
                    "pid": process.pid,
                    "running": status is None,
                    "returncode": status,
                }
            )
            if status is not None:
                _ACTIVE_PROCESSES.pop(job_id, None)
    return {"workspace": str(root), "processes": processes, "active_count": len([item for item in processes if item["running"]])}


def list_stream_events(
    workspace: str | Path,
    *,
    job_id: str | None = None,
    workflow_id: str | None = None,
    since: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    events = _filtered_events(root, job_id=job_id, workflow_id=workflow_id, since=since, limit=limit)
    return {"workspace": str(root), "events": events, "next_since": since + len(events)}


def stream_events(
    workspace: str | Path,
    *,
    job_id: str | None = None,
    workflow_id: str | None = None,
    since: int = 0,
    limit: int = 100,
    follow: bool = False,
    max_seconds: int = 30,
) -> Iterable[str]:
    root = _workspace_root(workspace)
    started = time.time()
    emitted = 0
    seen: set[str] = set()
    cursor = max(0, int(since or 0))
    while True:
        events = _filtered_events(root, job_id=job_id, workflow_id=workflow_id, since=cursor, limit=limit)
        for event in events:
            event_id = str(event.get("event_id") or "")
            if event_id in seen:
                continue
            seen.add(event_id)
            emitted += 1
            yield _sse(str(event.get("event_type") or "runtime_event"), event)
            if emitted >= max(1, min(500, int(limit))):
                return
        cursor += len(events)
        if not follow:
            return
        if time.time() - started >= max(1, min(120, int(max_seconds))):
            yield _sse("runtime.heartbeat", {"timestamp": utc_now(), "message": "stream timeout"})
            return
        time.sleep(0.5)


def create_session(
    workspace: str | Path,
    *,
    workflow_id: str = "",
    title: str = "",
    owner_client_id: str = "unknown",
    participants: list[dict[str, Any]] | None = None,
    spectators: list[dict[str, Any]] | None = None,
    approval_delegates: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    session_id = f"session-{uuid.uuid4().hex[:12]}"
    now = utc_now()
    session = {
        "session_id": session_id,
        "workflow_id": scrub(workflow_id),
        "title": scrub(title or "Shared workflow session"),
        "owner_client_id": scrub(owner_client_id or "unknown"),
        "participants": _safe_people(participants or []),
        "spectators": _safe_people(spectators or []),
        "approval_delegates": [scrub(item) for item in (approval_delegates or []) if str(item).strip()][:20],
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "last_sync_at": now,
        "metadata": _safe_metadata(metadata or {}),
    }
    _mutate_state(root, lambda state: _record_session(state, session))
    _append_event(root, "runtime.session.created", workflow_id=workflow_id, message=session["title"], payload={"session_id": session_id})
    return {"workspace": str(root), "session": session, "dashboard": sessions_dashboard(root)}


def sync_session(
    workspace: str | Path,
    session_id: str,
    *,
    participants: list[dict[str, Any]] | None = None,
    spectators: list[dict[str, Any]] | None = None,
    approval_delegates: list[str] | None = None,
    status: str | None = None,
    message: str = "",
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean_id = _safe_lookup_id(session_id)
    def update(state: dict[str, Any]) -> None:
        session = _find_session(state, clean_id)
        if participants is not None:
            session["participants"] = _safe_people(participants)
        if spectators is not None:
            session["spectators"] = _safe_people(spectators)
        if approval_delegates is not None:
            session["approval_delegates"] = [scrub(item) for item in approval_delegates if str(item).strip()][:20]
        if status:
            session["status"] = _normalize_session_status(status)
        session["last_sync_at"] = utc_now()
        session["updated_at"] = session["last_sync_at"]
    _mutate_state(root, update)
    session = _find_session(_load_state(root), clean_id)
    _append_event(root, "runtime.session.synced", workflow_id=session.get("workflow_id"), message=message or "Session synchronized.", payload={"session_id": clean_id})
    return {"workspace": str(root), "session": session, "dashboard": sessions_dashboard(root)}


def sessions_dashboard(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    sessions = _sorted_sessions(state.get("sessions", []))
    return {
        "workspace": str(root),
        "sessions": sessions,
        "active_sessions": [item for item in sessions if item.get("status") == "active"],
        "recent_events": [
            event for event in _sorted_events(state.get("events", [])) if str(event.get("event_type", "")).startswith("runtime.session")
        ][:50],
    }


def voice_status(workspace: str | Path) -> dict[str, Any]:
    root = _workspace_root(workspace)
    return {
        "workspace": str(root),
        "push_to_talk": {"enabled": True, "hotkey": "client-defined", "local_first": True},
        "speech_to_text": {"provider": "none", "configured": False, "optional": True, "local_provider_supported": True},
        "text_to_speech": {"provider": "none", "configured": False, "optional": True, "local_provider_supported": True},
        "voice_commands": [
            "summarize_workflow",
            "pause_workflow",
            "resume_workflow",
            "cancel_workflow",
            "run_validation",
            "explain_failure",
        ],
        "privacy": {
            "audio_stored_by_core": False,
            "transcripts_are_commands": True,
            "cloud_requires_explicit_provider_approval": True,
        },
        "status": "contract_ready",
        "warnings": ["No speech provider is configured; clients should submit transcripts from local push-to-talk capture."],
    }


def route_voice_command(
    workspace: str | Path,
    transcript: str,
    *,
    workflow_id: str = "",
    client_id: str = "unknown",
    dry_run: bool = True,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    clean = scrub(transcript).strip()[:2000]
    intent = _voice_intent(clean)
    command = {
        "id": f"voice-{uuid.uuid4().hex[:12]}",
        "transcript": clean,
        "intent": intent,
        "workflow_id": scrub(workflow_id),
        "client_id": scrub(client_id or "unknown"),
        "dry_run": bool(dry_run),
        "created_at": utc_now(),
        "requires_approval": intent in {"cancel_workflow", "run_validation"},
        "routed_to": "workflow_runtime" if workflow_id else "runtime_command_router",
    }
    _append_event(root, "runtime.voice.command", workflow_id=workflow_id, message=f"Voice command routed: {intent}", payload=command)
    return {"workspace": str(root), "command": command, "voice": voice_status(root)}


def execution_replay(
    workspace: str | Path,
    *,
    workflow_id: str | None = None,
    job_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    root = _workspace_root(workspace)
    state = _load_state(root)
    events = _sorted_events(state.get("events", []))
    if workflow_id:
        events = [event for event in events if event.get("workflow_id") == workflow_id]
    if job_id:
        events = [event for event in events if event.get("job_id") == job_id]
    workflow_events = _workflow_events(root, workflow_id=workflow_id)
    return {
        "workspace": str(root),
        "workflow_id": scrub(workflow_id or ""),
        "job_id": scrub(job_id or ""),
        "timeline": workflow_events[: max(1, min(500, int(limit)))],
        "terminal_output": events[: max(1, min(500, int(limit)))],
        "repair_chain": [event for event in workflow_events if "repair" in str(event.get("event") or event.get("event_type") or "")],
        "approval_history": [event for event in workflow_events + events if "approval" in str(event).lower()],
        "sessions": sessions_dashboard(root)["sessions"],
    }


def _execute_job(root: Path, job_id: str) -> None:
    state = _load_state(root)
    try:
        job = _find_job(state, job_id)
    except RuntimeJobNotFoundError:
        return
    if job.get("status") != "queued":
        return
    _update_job(root, job_id, status="running", started_at=utc_now(), updated_at=utc_now())
    _append_event(root, "runtime.job.started", job_id=job_id, terminal_id=job.get("terminal_id"), workflow_id=job.get("workflow_id"), message="Process started.")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [str(item) for item in job.get("command", [])],
            cwd=str(job.get("cwd") or root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            bufsize=1,
        )
        with _STATE_LOCK:
            _ACTIVE_PROCESSES[job_id] = process
        readers = [
            threading.Thread(target=_read_stream, args=(root, job, process.stdout, "stdout"), daemon=True),
            threading.Thread(target=_read_stream, args=(root, job, process.stderr, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        timed_out = False
        try:
            returncode = process.wait(timeout=int(job.get("timeout_seconds") or 120))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=2)
        final_status = "timed_out" if timed_out else "completed" if returncode == 0 else "failed"
        if _job_status(root, job_id) == "cancel_requested":
            final_status = "cancelled"
        _update_job(
            root,
            job_id,
            status=final_status,
            finished_at=utc_now(),
            updated_at=utc_now(),
            exit_code=returncode,
            timed_out=timed_out,
        )
        _append_event(
            root,
            f"runtime.job.{final_status}",
            job_id=job_id,
            terminal_id=job.get("terminal_id"),
            workflow_id=job.get("workflow_id"),
            message=f"Process {final_status} with exit code {returncode}.",
            severity="ok" if final_status == "completed" else "warning",
        )
    except FileNotFoundError as exc:
        _update_job(root, job_id, status="failed", finished_at=utc_now(), updated_at=utc_now(), exit_code=None)
        _append_event(root, "runtime.job.failed", job_id=job_id, terminal_id=job.get("terminal_id"), workflow_id=job.get("workflow_id"), message=f"Executable not found: {scrub(str(exc.filename or 'unknown'))}", severity="error")
    except OSError as exc:
        _update_job(root, job_id, status="failed", finished_at=utc_now(), updated_at=utc_now(), exit_code=None)
        _append_event(root, "runtime.job.failed", job_id=job_id, terminal_id=job.get("terminal_id"), workflow_id=job.get("workflow_id"), message=f"Process failed to start: {scrub(str(exc))}", severity="error")
    finally:
        with _STATE_LOCK:
            _ACTIVE_PROCESSES.pop(job_id, None)
        try:
            if process and process.poll() is None:
                process.kill()
        except OSError:
            pass


def _read_stream(root: Path, job: dict[str, Any], stream: Any, stream_name: str) -> None:
    if stream is None:
        return
    try:
        for chunk in iter(stream.readline, ""):
            if chunk == "":
                break
            _append_event(
                root,
                f"runtime.terminal.{stream_name}",
                job_id=job.get("job_id"),
                terminal_id=job.get("terminal_id"),
                workflow_id=job.get("workflow_id"),
                stream=stream_name,
                chunk=chunk,
                message=chunk,
            )
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _workspace_root(workspace: str | Path) -> Path:
    root = Path(workspace).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise RuntimeInteractionError(f"workspace does not exist or is not a directory: {scrub(str(root))}")
    return root


def _memory(root: Path) -> ProjectMemory:
    memory = ProjectMemory(root)
    memory.ensure()
    return memory


def _state_path(root: Path) -> Path:
    return _memory(root).root / STATE_FILE


def _default_state(root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workspace": str(root),
        "jobs": [],
        "events": [],
        "sessions": [],
        "voice_commands": [],
        "updated_at": utc_now(),
    }


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.exists():
        return _default_state(root)
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RuntimeInteractionError(f"Could not read runtime interaction state: {scrub(str(exc))}") from exc
    if not isinstance(data, dict):
        return _default_state(root)
    default = _default_state(root)
    for key, value in default.items():
        data.setdefault(key, value)
    return data


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = _state_path(root)
    state["updated_at"] = utc_now()
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        import json

        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        for attempt in range(5):
            try:
                tmp.replace(path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except OSError as exc:
        raise RuntimeInteractionError(f"Could not write runtime interaction state: {scrub(str(exc))}") from exc
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _mutate_state(root: Path, mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    with _STATE_LOCK:
        state = _load_state(root)
        mutator(state)
        state["jobs"] = _sorted_jobs(state.get("jobs", []))[:MAX_JOBS]
        state["events"] = _sorted_events(state.get("events", []))[:MAX_EVENTS]
        state["sessions"] = _sorted_sessions(state.get("sessions", []))[:MAX_SESSIONS]
        _save_state(root, state)
        return state


def _record_job(state: dict[str, Any], job: dict[str, Any]) -> None:
    jobs = [item for item in state.get("jobs", []) if item.get("job_id") != job.get("job_id")]
    jobs.append(job)
    state["jobs"] = jobs


def _record_session(state: dict[str, Any], session: dict[str, Any]) -> None:
    sessions = [item for item in state.get("sessions", []) if item.get("session_id") != session.get("session_id")]
    sessions.append(session)
    state["sessions"] = sessions


def _append_event(
    root: Path,
    event_type: str,
    *,
    job_id: str | None = None,
    terminal_id: str | None = None,
    workflow_id: str | None = None,
    stream: str = "",
    chunk: str = "",
    message: str = "",
    payload: dict[str, Any] | None = None,
    severity: str = "info",
) -> dict[str, Any]:
    clean_chunk = scrub(str(chunk or ""))[:MAX_CHUNK_CHARS]
    entry = {
        "event_id": f"rt-event-{uuid.uuid4().hex[:12]}",
        "event_type": scrub(event_type),
        "workspace": str(root),
        "job_id": scrub(job_id or ""),
        "terminal_id": scrub(terminal_id or ""),
        "workflow_id": scrub(workflow_id or ""),
        "stream": scrub(stream),
        "chunk": clean_chunk,
        "message": scrub(message or clean_chunk)[:MAX_CHUNK_CHARS],
        "payload": _safe_metadata(payload or {}),
        "severity": severity if severity in {"info", "ok", "warning", "error"} else "info",
        "created_at": utc_now(),
    }
    def add(state: dict[str, Any]) -> None:
        state.setdefault("events", []).append(entry)
        if job_id and clean_chunk:
            for job in state.get("jobs", []):
                if job.get("job_id") != job_id:
                    continue
                key = "stderr_tail" if stream == "stderr" else "stdout_tail"
                job[key] = (str(job.get(key) or "") + clean_chunk)[-MAX_OUTPUT_CHARS:]
                job["output_event_count"] = int(job.get("output_event_count") or 0) + 1
                job["updated_at"] = utc_now()
                break
    _mutate_state(root, add)
    return entry


def _update_job(root: Path, job_id: str, **updates: Any) -> None:
    clean_id = _safe_lookup_id(job_id)
    def update(state: dict[str, Any]) -> None:
        job = _find_job(state, clean_id)
        for key, value in updates.items():
            job[key] = value
    _mutate_state(root, update)


def _find_job(state: dict[str, Any], job_id: str) -> dict[str, Any]:
    clean_id = _safe_lookup_id(job_id)
    for job in state.get("jobs", []):
        if job.get("job_id") == clean_id:
            return job
    raise RuntimeJobNotFoundError(clean_id)


def _find_session(state: dict[str, Any], session_id: str) -> dict[str, Any]:
    clean_id = _safe_lookup_id(session_id)
    for session in state.get("sessions", []):
        if session.get("session_id") == clean_id:
            return session
    raise RuntimeInteractionError(f"runtime session not found: {scrub(clean_id)}")


def _job_status(root: Path, job_id: str) -> str:
    try:
        return str(_find_job(_load_state(root), job_id).get("status") or "")
    except RuntimeJobNotFoundError:
        return ""


def _job_mutation(root: Path, job_id: str, action: str) -> dict[str, Any]:
    state = _load_state(root)
    return {
        "workspace": str(root),
        "action": action,
        "job": _find_job(state, job_id),
        "dashboard": runtime_dashboard(root, limit=100),
    }


def _normalize_command(command: str | list[str]) -> list[str]:
    if isinstance(command, str):
        parts = shlex.split(command, posix=os.name != "nt")
    else:
        parts = [str(item) for item in command]
    parts = [scrub(item).strip() for item in parts if str(item).strip()]
    if not parts:
        raise RuntimeInteractionError("runtime command is required")
    if len(parts) > 80:
        raise RuntimeInteractionError("runtime command is too long")
    return parts


def _normalize_cwd(root: Path, cwd: str | None) -> Path:
    target = root if not cwd else (root / cwd if not Path(cwd).is_absolute() else Path(cwd)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeInteractionError("runtime command cwd must stay inside the workspace") from exc
    if not target.exists() or not target.is_dir():
        raise RuntimeInteractionError(f"runtime command cwd is not a directory: {scrub(str(target))}")
    return target


def _command_safety(command: list[str], *, approval: bool) -> dict[str, Any]:
    command_text = " ".join(command)
    lower = command_text.lower()
    dangerous_patterns = [
        "remove-item",
        "rm -rf",
        " rmdir ",
        " del ",
        " format ",
        "shutdown",
        "restart-computer",
        "invoke-expression",
        "iex ",
        "set-executionpolicy",
        "bcdedit",
        "diskpart",
        "mkfs",
        "chmod -r",
        "chown -r",
        "curl ",
        "wget ",
    ]
    blocked = [pattern.strip() for pattern in dangerous_patterns if pattern in f" {lower} "]
    validation_safe = is_safe_validation_command(command)
    approval_required = not validation_safe
    allowed = not blocked and (validation_safe or approval)
    reason = ""
    if blocked:
        reason = f"Command contains blocked dangerous token(s): {', '.join(blocked[:4])}."
    elif approval_required and not approval:
        reason = "Command requires explicit approval because it is outside the safe validation allow-list."
    else:
        reason = "Command approved by runtime safety policy."
    return {
        "allowed": allowed,
        "approval_required": approval_required,
        "approved": bool(approval),
        "validation_safe": validation_safe,
        "blocked_tokens": blocked,
        "reason": reason,
        "shell": False,
        "workspace_restricted": True,
        "timeout_enforced": True,
        "isolated_execution": "subprocess_no_shell",
    }


def _terminal_summaries(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terminals: dict[str, dict[str, Any]] = {}
    for job in jobs:
        terminal_id = str(job.get("terminal_id") or "terminal-default")
        item = terminals.setdefault(
            terminal_id,
            {
                "terminal_id": terminal_id,
                "title": terminal_id.replace("-", " ").title(),
                "status": "idle",
                "job_count": 0,
                "active_job_ids": [],
                "latest_job_id": "",
                "latest_output": "",
                "updated_at": "",
            },
        )
        item["job_count"] += 1
        item["latest_job_id"] = item["latest_job_id"] or str(job.get("job_id") or "")
        item["latest_output"] = item["latest_output"] or str(job.get("stderr_tail") or job.get("stdout_tail") or "")[-500:]
        item["updated_at"] = max(str(item.get("updated_at") or ""), str(job.get("updated_at") or ""))
        if job.get("status") in RUNNING_STATES:
            item["status"] = "running"
            item["active_job_ids"].append(job.get("job_id"))
        elif item["status"] == "idle" and job.get("status") in {"failed", "timed_out", "blocked"}:
            item["status"] = "attention"
    return sorted(terminals.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def _observability(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    jobs = state.get("jobs", [])
    events = state.get("events", [])
    completed = len([job for job in jobs if job.get("status") == "completed"])
    failed = len([job for job in jobs if job.get("status") in {"failed", "timed_out", "blocked"}])
    durations: list[float] = []
    for job in jobs:
        start = _parse_time(job.get("started_at"))
        end = _parse_time(job.get("finished_at"))
        if start and end:
            durations.append(max(0.0, end - start))
    return {
        "job_count": len(jobs),
        "active_jobs": len([job for job in jobs if job.get("status") in RUNNING_STATES]),
        "completed_jobs": completed,
        "failed_jobs": failed,
        "terminal_count": len(_terminal_summaries(jobs)),
        "event_count": len(events),
        "session_count": len(state.get("sessions", [])),
        "active_processes": runtime_processes(root).get("active_count", 0),
        "average_duration_ms": int((sum(durations) / len(durations)) * 1000) if durations else 0,
    }


def _safety_controls() -> dict[str, Any]:
    return {
        "shell_execution": "disabled",
        "cwd": "must stay inside workspace",
        "approval": "required for commands outside the safe validation allow-list",
        "blocked_commands": ["Remove-Item", "rm -rf", "format", "shutdown", "Invoke-Expression", "diskpart"],
        "logging": "stdout, stderr, status, exit code, timeout, and approval metadata are persisted",
        "timeouts": "required for every launched process",
        "termination": "running jobs can be cancelled through /v1/runtime/jobs/{job_id}/cancel",
    }


def _filtered_events(root: Path, *, job_id: str | None, workflow_id: str | None, since: int, limit: int) -> list[dict[str, Any]]:
    state = _load_state(root)
    events = list(reversed(_sorted_events(state.get("events", []))))
    if job_id:
        clean_job_id = _safe_lookup_id(job_id)
        events = [event for event in events if event.get("job_id") == clean_job_id]
    if workflow_id:
        clean_workflow = scrub(workflow_id)
        events = [event for event in events if event.get("workflow_id") == clean_workflow]
    start = max(0, int(since or 0))
    return events[start : start + max(1, min(500, int(limit or 100)))]


def _workflow_events(root: Path, *, workflow_id: str | None) -> list[dict[str, Any]]:
    path = ProjectMemory(root).root / "workflow-events.json"
    if not path.is_file():
        return []
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    events = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    if workflow_id:
        events = [event for event in events if event.get("workflow_id") == workflow_id]
    return sorted(events, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _process_snapshot(job_id: str) -> dict[str, Any]:
    with _STATE_LOCK:
        process = _ACTIVE_PROCESSES.get(job_id)
        if not process:
            return {"job_id": job_id, "running": False}
        status = process.poll()
        return {"job_id": job_id, "pid": process.pid, "running": status is None, "returncode": status}


def _safe_metadata(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        clean_key = scrub(str(key))[:120]
        if any(token in clean_key.lower() for token in {"token", "secret", "password", "credential", "api_key"}):
            result[clean_key] = "[redacted]"
        elif isinstance(value, dict):
            result[clean_key] = _safe_metadata(value)
        elif isinstance(value, list):
            result[clean_key] = [scrub(str(item))[:500] for item in value[:100]]
        else:
            result[clean_key] = scrub(str(value))[:1000] if isinstance(value, str) else value
    return result


def _safe_people(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    people = []
    for item in items[:50]:
        if not isinstance(item, dict):
            continue
        people.append(
            {
                "client_id": scrub(str(item.get("client_id") or item.get("id") or "unknown"))[:120],
                "name": scrub(str(item.get("name") or ""))[:160],
                "role": scrub(str(item.get("role") or "participant"))[:80],
                "can_approve": bool(item.get("can_approve", False)),
                "last_seen": scrub(str(item.get("last_seen") or utc_now())),
            }
        )
    return people


def _voice_intent(transcript: str) -> str:
    lower = transcript.lower()
    if "pause" in lower:
        return "pause_workflow"
    if "resume" in lower:
        return "resume_workflow"
    if "cancel" in lower or "stop" in lower:
        return "cancel_workflow"
    if "validate" in lower or "test" in lower or "build" in lower:
        return "run_validation"
    if "summary" in lower or "summarize" in lower:
        return "summarize_workflow"
    if "failure" in lower or "error" in lower:
        return "explain_failure"
    return "route_command"


def _normalize_session_status(status: str) -> str:
    clean = scrub(status).lower().strip().replace(" ", "_")
    return clean if clean in {"active", "paused", "closed"} else "active"


def _safe_id(value: str | None, *, prefix: str) -> str:
    text = _safe_lookup_id(value or "")
    return text or f"{prefix}-{uuid.uuid4().hex[:8]}"


def _safe_lookup_id(value: str) -> str:
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text).strip("-._")
    return clean[:120]


def _sorted_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([job for job in jobs if isinstance(job, dict)], key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)


def _sorted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([event for event in events if isinstance(event, dict)], key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _sorted_sessions(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted([session for session in sessions if isinstance(session, dict)], key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)


def _parse_time(value: Any) -> float | None:
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _sse(event: str, data: dict[str, Any]) -> str:
    import json

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"
