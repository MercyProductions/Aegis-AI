from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.schemas import ValidateResponse
from aegis_ai.services.core_client import CoreDelegationResult


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "delegation-workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("print('old')\n", encoding="utf-8")
    return workspace


def _core_result(kind: str, data: dict, *, ok: bool = True) -> CoreDelegationResult:
    return CoreDelegationResult(
        delegated=True,
        ok=ok,
        reachable=True,
        status_code=200,
        kind=kind,
        data=data,
        envelope={"ok": ok, "api_version": "v1", "kind": kind, "data": data},
    )


def _offline(kind: str) -> CoreDelegationResult:
    return CoreDelegationResult(
        delegated=False,
        ok=False,
        reachable=False,
        status_code=None,
        kind=kind,
        data=None,
        envelope=None,
        error="Core offline",
    )


class DelegatingCoreClient:
    delegated_workflows_enabled = True

    def __init__(self) -> None:
        self.fallbacks: list[tuple[str, str]] = []
        self.memory_records: list[dict] = [
            {
                "id": "mem-core",
                "category": "project_memory",
                "title": "Core memory note",
                "content": "Prefer pytest for validation.",
                "scope": "project",
                "created_at": "2026-05-11T00:00:00Z",
                "updated_at": "2026-05-11T00:00:00Z",
                "pinned": True,
                "tags": ["validation"],
                "related_files": ["app.py"],
                "confidence": 0.91,
                "metadata": {"legacy_category": "insight"},
                "privacy": {"local_only": True, "sensitive": False, "excluded_from_cloud": True},
            }
        ]
        self.memory_controls = {
            "local_only": True,
            "cloud_memory_sharing": False,
            "sensitive_memory_exclusions": True,
            "allowed_scopes": ["user", "workspace", "project", "workflow"],
            "categories": {
                "project_memory": {
                    "enabled": True,
                    "retention_days": None,
                    "include_in_orchestration": True,
                    "encrypted": False,
                    "encrypted_storage_active": False,
                },
                "repair_history": {
                    "enabled": False,
                    "retention_days": 180,
                    "include_in_orchestration": False,
                    "encrypted": False,
                    "encrypted_storage_active": False,
                },
            },
            "transparency": {
                "inspectable": True,
                "editable": True,
                "exportable": True,
                "deletable": True,
                "category_controls": True,
            },
        }

    async def apply_changes(self, workspace: Path, changes, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "changes.apply",
            {
                "applied": ["update: app.py"],
                "warnings": [],
                "checkpoint_id": "checkpoint-core",
                "job_id": "job-apply",
                "task_id": "task-apply",
            },
        )

    async def create_checkpoint(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "checkpoints.create",
            {
                "id": "checkpoint-manual",
                "created_at": "2026-05-11T00:00:00Z",
                "file_count": 1,
                "present_count": 1,
                "missing_count": 0,
                "files": [{"path": "app.py", "state": "present"}],
            },
        )

    async def list_checkpoints(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _core_result(
            "checkpoints.list",
            {
                "checkpoints": [
                    {
                        "id": "checkpoint-core",
                        "created_at": "2026-05-11T00:00:00Z",
                        "file_count": 1,
                        "present_count": 1,
                        "missing_count": 0,
                        "files": [{"path": "app.py", "state": "present"}],
                    }
                ]
            },
        )

    async def restore_checkpoint(self, workspace: Path, checkpoint_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "checkpoints.restore",
            {
                "restored": ["restore: app.py"],
                "warnings": [],
                "checkpoint_id": checkpoint_id,
                "pre_restore_checkpoint_id": "checkpoint-before-restore",
            },
        )

    async def run_validation(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "validation.run",
            {
                "id": "validation-core",
                "job_id": "job-validation",
                "task_id": "task-validation",
                "source_client": "website-backend",
                "validation": {
                    "ok": False,
                    "command": ["python", "-m", "pytest"],
                    "returncode": 1,
                    "stdout": "captured stdout",
                    "stderr": "captured stderr",
                },
                "warnings": [],
            },
            ok=False,
        )

    async def create_repair_workflow(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "workflow.created",
            {"workflow": {"id": "workflow-repair", "workflow_type": "repair_project", "status": "queued"}},
        )

    async def release_manifest(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "release.manifest",
            {
                "schema_version": "2026.05.12",
                "components": {"website": {"version": "0.1.0"}, "aegis-core": {"version": "0.1.0"}},
                "compatibility": {"minimum_core_version": "0.1.0"},
            },
        )

    async def check_compatibility(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "release.compatibility",
            {
                "compatible": True,
                "client_type": "website",
                "client_version": "0.1.0",
                "status": "compatible",
                "required_schema_version": "2026.05.12",
                "blockers": [],
                "warnings": [],
                "recommendations": [],
            },
        )

    async def agent_runtime(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "agent.runtime",
            {
                "agents": [
                    {
                        "id": "planner_agent",
                        "role": "planner",
                        "status": "active",
                        "preferred_model_profile": {"route_profile": "best_reasoning"},
                    }
                ],
                "safety_controls": {"max_file_modifications": 25},
            },
        )

    async def list_workflows(self, workspace: Path, *, include_completed: bool = False, limit: int = 30) -> CoreDelegationResult:
        workflow = {
            "id": "workflow-core",
            "workflow_type": "generate_feature",
            "status": "running",
            "active_task_id": "task-plan",
            "tasks": [
                {
                    "id": "task-plan",
                    "title": "Plan implementation",
                    "status": "waiting_input",
                    "agent_id": "planner_agent",
                    "execution_mode": "planning",
                    "approval_required": True,
                    "target_files": ["app.py"],
                }
            ],
        }
        return _core_result("workflows.list", {"workflows": [workflow], "active_workflows": [workflow]})

    async def workflow_dashboard(self, workspace: Path, workflow_id: str) -> CoreDelegationResult:
        return _core_result(
            "workflow.dashboard",
            {
                "workflow": {
                    "id": workflow_id,
                    "workflow_type": "generate_feature",
                    "status": "running",
                    "active_task_id": "task-plan",
                    "tasks": [
                        {
                            "id": "task-plan",
                            "title": "Plan implementation",
                            "status": "waiting_input",
                            "agent_id": "planner_agent",
                            "execution_mode": "planning",
                            "approval_required": True,
                            "target_files": ["app.py"],
                        }
                    ],
                },
                "timeline": [{"kind": "workflow.created", "title": "Created workflow", "status": "ok"}],
            },
        )

    async def workflow_agent_coordination(self, workspace: Path, workflow_id: str) -> CoreDelegationResult:
        return _core_result(
            "agent.coordination",
            {
                "workflow_id": workflow_id,
                "agents": [
                    {
                        "id": "planner_agent",
                        "role": "planner",
                        "status": "waiting_input",
                        "task_ownership": [{"task_id": "task-plan", "title": "Plan implementation", "status": "waiting_input"}],
                    }
                ],
                "execution_timeline": [{"kind": "workflow.created", "title": "Created workflow", "status": "ok"}],
                "safety": {"warnings": []},
            },
        )

    async def step_workflow(self, workspace: Path, workflow_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "workflow.step",
            {
                "workflow": {"id": workflow_id, "status": "queued"},
                "event": {"kind": "workflow.advance", "title": "Advanced", "status": "ok"},
                "timeline": [],
            },
        )

    async def delegate_agent_task(self, workspace: Path, workflow_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "agent.delegation",
            {
                "workflow": {"id": workflow_id, "status": "queued"},
                "event": {"kind": "workflow.delegate_task", "title": "Delegated", "status": "ok"},
            },
        )

    async def quality_gates(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _core_result(
            "quality.gates",
            {
                "latest": {
                    "id": "quality-core",
                    "status": "passed",
                    "apply_allowed": True,
                    "scorecard": {"confidence_score": 91, "risk_score": 12, "validation_score": 88},
                    "gates": [{"id": "syntax_check", "status": "passed", "label": "Syntax check"}],
                    "blockers": [],
                    "warnings": [],
                },
                "recent_runs": [],
                "reports": [],
                "benchmark_history": [],
                "benchmark_suites": [{"id": "coding_task_quality", "label": "Coding Task Quality"}],
                "statistics": {"run_count": 1, "blocked_count": 0},
            },
        )

    async def evaluate_quality_gates(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "quality.gates.evaluate",
            {
                "id": "quality-core",
                "status": "passed",
                "apply_allowed": True,
                "scorecard": {"confidence_score": 91, "risk_score": 12, "validation_score": 88},
                "gates": [{"id": "syntax_check", "status": "passed", "label": "Syntax check"}],
                "blockers": [],
                "warnings": [],
                "changed_files": ["app.py"],
            },
        )

    async def workflow_quality(self, workspace: Path, workflow_id: str) -> CoreDelegationResult:
        return _core_result(
            "workflow.quality",
            {"workflow_id": workflow_id, "latest": {"id": "quality-core", "status": "passed"}, "runs": [], "reports": []},
        )

    async def benchmarks(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _core_result(
            "quality.benchmarks",
            {
                "suites": [{"id": "coding_task_quality", "label": "Coding Task Quality"}],
                "history": [],
                "latest": None,
                "statistics": {"run_count": 0},
            },
        )

    async def run_benchmark(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "quality.benchmark.run",
            {
                "id": "benchmark-core",
                "status": "passed",
                "score": 0.91,
                "results": [{"suite_id": "coding_task_quality", "score": 0.91}],
            },
        )

    async def evaluation_reports(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "quality.evaluation_reports",
            {"reports": [{"id": "evaluation-core", "status": "passed"}], "latest": {"id": "evaluation-core"}},
        )

    async def create_evaluation_report(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "quality.evaluation_report",
            {"id": "evaluation-core", "status": "passed", "rollback_instructions": ["Restore checkpoint checkpoint-core."]},
        )

    async def model_registry(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "model.registry",
            {
                "active_profile": "best_coding",
                "selected_model": {"provider_id": "ollama", "model_id": "qwen3-coder:30b"},
                "routing_profiles": [
                    {
                        "id": "best_coding",
                        "label": "Best Coding",
                        "description": "Prefer strong coding models.",
                        "privacy_mode": "local-first",
                        "priority": ["ollama", "openai"],
                    }
                ],
                "providers": [
                    {
                        "id": "ollama",
                        "label": "Ollama",
                        "api": "ollama",
                        "endpoint": "http://127.0.0.1:11434",
                        "default_model": "qwen3-coder:30b",
                        "local": True,
                        "enabled": True,
                        "configured": True,
                        "capabilities": ["chat", "code"],
                        "roles": ["chat", "code"],
                        "context_window": 32768,
                        "availability_status": "available",
                        "auth_methods": ["none"],
                        "provider_reachable": True,
                        "privacy_level": "local",
                    }
                ],
                "provider_status": [
                    {
                        "provider_id": "ollama",
                        "linked": "linked",
                        "key_present": False,
                        "auth_method_available": True,
                        "provider_reachable": True,
                        "availability_status": "available",
                    }
                ],
                "models": [
                    {
                        "provider_id": "ollama",
                        "model_id": "qwen3-coder:30b",
                        "display_name": "qwen3-coder:30b",
                        "availability_status": "available",
                    }
                ],
            },
        )

    async def distributed_runtime(self, workspace: Path, *, include_audit: bool = True, limit: int = 100) -> CoreDelegationResult:
        return _core_result(
            "distributed.runtime",
            {
                "schema_version": 1,
                "workspace": str(workspace.resolve()),
                "generated_at": "2026-05-11T00:00:00Z",
                "local_authority": {"node_id": "local"},
                "nodes": [
                    {
                        "node_id": "local",
                        "name": "Local Aegis Core",
                        "node_type": "local",
                        "endpoint": "local://aegis-core",
                        "status": "online",
                        "trust_level": "local",
                        "trust_scope": "full_local_authority",
                        "registered_at": "2026-05-11T00:00:00Z",
                        "last_heartbeat_at": "2026-05-11T00:00:00Z",
                        "capabilities": ["workflow_execution", "validation_execution", "indexing"],
                        "cpu": {"logical_cores": 8},
                        "gpu": {"available": False},
                        "supported_workflow_types": ["all"],
                        "installed_models": [],
                        "installed_plugins": [],
                        "permission_scopes": ["workspace_scan", "validation_execution"],
                        "current_workload_count": 0,
                        "max_parallel_workloads": 2,
                        "isolation": {"workspace_mount": "native"},
                    }
                ],
                "workloads": [
                    {
                        "workload_id": "workload-core",
                        "workspace": str(workspace.resolve()),
                        "workload_type": "validation",
                        "title": "Validate from Core",
                        "status": "queued",
                        "priority": 50,
                        "created_at": "2026-05-11T00:00:00Z",
                        "required_capabilities": ["validation_execution"],
                        "permission_scopes": ["validation_execution"],
                        "errors": [],
                        "payload": {},
                    }
                ],
                "observability": {
                    "nodes": {"total": 1, "online": 1, "by_status": {"online": 1}, "by_trust": {"local": 1}},
                    "workloads": {"queued": 1, "active": 0, "completed": 0, "failed": 0, "by_type": {"validation": 1}},
                    "latency": {"average_duration_ms": 0},
                },
                "audit_events": [
                    {
                        "event_id": "runtime-event-core",
                        "event_type": "runtime.workload.created",
                        "created_at": "2026-05-11T00:00:00Z",
                        "severity": "info",
                        "node_id": "local",
                        "workload_id": "workload-core",
                        "details": {"reason": "queued"},
                    }
                ],
            },
        )

    async def runtime_interaction(self, workspace: Path, *, limit: int = 100) -> CoreDelegationResult:
        return _core_result(
            "runtime.interaction",
            {
                "workspace": str(workspace.resolve()),
                "terminals": [{"terminal_id": "terminal-core", "status": "running", "job_count": 1}],
                "jobs": [{"job_id": "rt-job-core", "terminal_id": "terminal-core", "status": "completed", "stdout_tail": "ok"}],
                "active_jobs": [],
                "recent_events": [{"event_id": "rt-event-core", "event_type": "runtime.job.completed", "message": "done"}],
                "processes": [],
                "sessions": [],
                "voice": {"status": "contract_ready"},
                "observability": {"job_count": 1, "active_jobs": 0, "terminal_count": 1},
                "safety_controls": {"shell_execution": "disabled"},
                "stream_endpoint": "/v1/runtime/streams",
            },
        )

    async def runtime_jobs(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.jobs",
            {
                "workspace": str(workspace.resolve()),
                "jobs": [{"job_id": "rt-job-core", "terminal_id": "terminal-core", "status": "completed"}],
                "observability": {"job_count": 1},
            },
        )

    async def launch_runtime_job(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.job.mutation",
            {
                "workspace": str(workspace.resolve()),
                "action": "started",
                "job": {
                    "job_id": "rt-job-created",
                    "terminal_id": kwargs.get("terminal_id") or "terminal-core",
                    "status": "completed",
                    "command": kwargs.get("command") or [],
                    "stdout_tail": "created",
                },
                "dashboard": {},
            },
        )

    async def runtime_job(self, workspace: Path, job_id: str) -> CoreDelegationResult:
        return _core_result(
            "runtime.job",
            {
                "workspace": str(workspace.resolve()),
                "job": {"job_id": job_id, "status": "completed"},
                "events": [{"event_id": "rt-event-core", "event_type": "runtime.job.completed"}],
                "process": {"running": False},
            },
        )

    async def cancel_runtime_job(self, workspace: Path, job_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.job.mutation",
            {"workspace": str(workspace.resolve()), "action": "cancel_requested", "job": {"job_id": job_id, "status": "cancel_requested"}, "dashboard": {}},
        )

    async def retry_runtime_job(self, workspace: Path, job_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.job.mutation",
            {"workspace": str(workspace.resolve()), "action": "started", "job": {"job_id": "rt-job-retry", "restart_of": job_id, "status": "completed"}, "dashboard": {}},
        )

    async def runtime_streams(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.streams",
            {"workspace": str(workspace.resolve()), "events": [{"event_id": "rt-event-core", "chunk": "ok"}], "next_since": 1},
        )

    async def runtime_sessions(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "runtime.sessions",
            {"workspace": str(workspace.resolve()), "sessions": [], "active_sessions": [], "recent_events": []},
        )

    async def create_runtime_session(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.session.mutation",
            {"workspace": str(workspace.resolve()), "session": {"session_id": "session-core", "status": "active"}, "dashboard": {}},
        )

    async def sync_runtime_session(self, workspace: Path, session_id: str, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.session.mutation",
            {"workspace": str(workspace.resolve()), "session": {"session_id": session_id, "status": kwargs.get("status") or "active"}, "dashboard": {}},
        )

    async def runtime_voice(self, workspace: Path) -> CoreDelegationResult:
        return _core_result("runtime.voice", {"workspace": str(workspace.resolve()), "status": "contract_ready", "voice_commands": ["pause_workflow"]})

    async def route_voice_command(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.voice.command",
            {"workspace": str(workspace.resolve()), "command": {"intent": "pause_workflow", "transcript": kwargs.get("transcript")}, "voice": {"status": "contract_ready"}},
        )

    async def runtime_replay(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "runtime.replay",
            {"workspace": str(workspace.resolve()), "timeline": [], "terminal_output": [{"event_id": "rt-event-core"}], "repair_chain": [], "approval_history": [], "sessions": []},
        )

    async def onboarding_status(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "onboarding.status",
            {
                "schema_version": 1,
                "workspace": str(workspace.resolve()),
                "generated_at": "2026-05-11T00:00:00Z",
                "completed": False,
                "current_step": "local_models",
                "steps": [
                    {"id": "welcome", "label": "Welcome", "required": True, "status": "complete"},
                    {"id": "local_models", "label": "Local Models", "required": True, "status": "complete"},
                ],
                "diagnostics": {
                    "summary": {"status": "pass", "pass_count": 2, "warning_count": 0, "failure_count": 0},
                    "checks": [{"id": "core_running", "label": "Core Running", "status": "pass", "detail": "ok"}],
                },
                "privacy": {"mode": "local-first", "local_only": True},
                "recommended_defaults": {"auto_apply": False, "checkpoint_before_apply": True},
                "first_workflow": {"completed_steps": [], "steps": []},
                "recovery": [],
                "settings": {"preferences": {}, "config": {}},
            },
        )

    async def update_onboarding(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        data = (await self.onboarding_status(workspace)).data
        assert isinstance(data, dict)
        data["current_step"] = kwargs.get("current_step") or "workspace"
        return _core_result("onboarding.updated", data)

    async def run_first_workflow(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "onboarding.first_workflow",
            {
                "workspace": str(workspace.resolve()),
                "action": kwargs.get("action") or "scan_project",
                "dry_run": kwargs.get("dry_run", True),
                "completed": kwargs.get("action") or "scan_project",
                "result": {"file_count": 1, "summary": "scan complete"},
                "next_actions": ["Run generate roadmap"],
            },
        )

    async def export_settings(self, workspace: Path) -> CoreDelegationResult:
        return _core_result(
            "settings.export",
            {
                "schema_version": 1,
                "workspace": str(workspace.resolve()),
                "settings": {"default_model": "qwen3-coder:30b"},
                "privacy": {"local_only": True},
                "provider_config_metadata": [],
                "ui_preferences": {},
                "runtime_urls": {"ollama_url": "http://127.0.0.1:11434"},
                "workspace_preferences": {"workspace": str(workspace.resolve())},
                "notes": ["no secrets"],
            },
        )

    async def import_settings(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "settings.import",
            {
                "workspace": str(workspace.resolve()),
                "dry_run": kwargs.get("dry_run", True),
                "imported_keys": ["default_model"],
                "ignored_keys": ["api_key"],
                "ui_preference_keys": ["theme"],
                "settings_preview": {"default_model": "qwen3-coder:30b"},
                "warnings": [],
            },
        )

    async def personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        category = kwargs.get("category")
        records = [record for record in self.memory_records if not category or record.get("category") == category]
        return _core_result(
            "personal.memory",
            {
                "workspace": str(workspace.resolve()),
                "records": records,
                "warnings": [],
                "observability": {"records": {"total": len(records)}},
                "controls": self.memory_controls,
                "categories": [
                    {
                        "id": "project_memory",
                        "label": "Project Memory",
                        "record_count": len(records),
                        **self.memory_controls["categories"]["project_memory"],
                    },
                    {
                        "id": "repair_history",
                        "label": "Repair History",
                        "record_count": 0,
                        **self.memory_controls["categories"]["repair_history"],
                    },
                ],
                "privacy": {
                    "local_only": True,
                    "cloud_memory_sharing": False,
                    "sensitive_memory_exclusions": True,
                    "per_project_isolation": True,
                    "inspectable": True,
                    "editable": True,
                    "exportable": True,
                    "deletable": True,
                    "encrypted_storage_requested_categories": [],
                    "encrypted_storage_active_categories": [],
                    "encrypted_storage_available": False,
                },
                "audit_events": [{"event_type": "memory.created", "status": "ok"}],
            },
        )

    async def create_personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        record = {
            "id": "mem-created",
            "category": kwargs.get("category") or "project_memory",
            "title": kwargs.get("title") or "Untitled",
            "content": kwargs.get("content") or "",
            "scope": kwargs.get("scope") or "project",
            "created_at": "2026-05-11T00:00:01Z",
            "updated_at": "2026-05-11T00:00:01Z",
            "pinned": bool(kwargs.get("pinned", False)),
            "tags": kwargs.get("tags") or [],
            "related_files": kwargs.get("related_files") or [],
            "confidence": kwargs.get("confidence", 0.8),
            "metadata": kwargs.get("metadata") or {},
        }
        self.memory_records.append(record)
        return _core_result("personal.memory.record", {"workspace": str(workspace.resolve()), "record": record, "warnings": []})

    async def update_personal_memory(self, workspace: Path, memory_id: str, **kwargs) -> CoreDelegationResult:
        record = next((item for item in self.memory_records if item.get("id") == memory_id), None)
        if record is None:
            return CoreDelegationResult(
                delegated=False,
                ok=False,
                reachable=True,
                status_code=400,
                kind="personal.memory.record",
                data=None,
                envelope=None,
                error="memory record not found",
            )
        for key in ("category", "title", "content", "scope", "tags", "related_files", "pinned", "confidence", "metadata"):
            if kwargs.get(key) is not None:
                record[key] = kwargs[key]
        record["updated_at"] = "2026-05-11T00:00:02Z"
        return _core_result("personal.memory.record", {"workspace": str(workspace.resolve()), "record": record, "warnings": []})

    async def delete_personal_memory(self, workspace: Path, memory_id: str, **kwargs) -> CoreDelegationResult:
        before = len(self.memory_records)
        self.memory_records = [item for item in self.memory_records if item.get("id") != memory_id]
        return _core_result(
            "personal.memory.deleted",
            {
                "workspace": str(workspace.resolve()),
                "memory_id": memory_id,
                "deleted": len(self.memory_records) != before,
                "hard_delete": bool(kwargs.get("hard_delete", True)),
            },
        )

    async def export_personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        redact_sensitive = bool(kwargs.get("redact_sensitive", True))
        records = []
        for record in self.memory_records:
            exported = dict(record)
            if redact_sensitive and exported.get("privacy", {}).get("sensitive"):
                exported["content"] = "[redacted sensitive memory]"
            records.append(exported)
        return _core_result(
            "personal.memory.export",
            {
                "workspace": str(workspace.resolve()),
                "record_count": len(records),
                "export": {
                    "schema_version": 1,
                    "workspace": str(workspace.resolve()),
                    "local_first": True,
                    "redacted_sensitive": redact_sensitive,
                    "records": records,
                    "controls": self.memory_controls,
                    "privacy": {
                        "local_only": True,
                        "cloud_memory_sharing": False,
                        "sensitive_memory_exclusions": True,
                        "per_project_isolation": True,
                        "inspectable": True,
                        "editable": True,
                        "exportable": True,
                        "deletable": True,
                    },
                },
            },
        )

    async def update_personal_memory_controls(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        if kwargs.get("local_only") is not None:
            self.memory_controls["local_only"] = bool(kwargs["local_only"])
        category = kwargs.get("category")
        if category:
            control = self.memory_controls["categories"].setdefault(str(category), {})
            for key in ("enabled", "retention_days", "include_in_orchestration", "encrypted"):
                if kwargs.get(key) is not None:
                    control[key] = kwargs[key]
        return _core_result(
            "personal.memory.controls",
            {
                "workspace": str(workspace.resolve()),
                "controls": self.memory_controls,
                "categories": [
                    {"id": key, "label": key.replace("_", " ").title(), "record_count": 0, **value}
                    for key, value in self.memory_controls["categories"].items()
                ],
                "privacy": {
                    "local_only": bool(self.memory_controls["local_only"]),
                    "cloud_memory_sharing": False,
                    "sensitive_memory_exclusions": True,
                    "per_project_isolation": True,
                    "inspectable": True,
                    "editable": True,
                    "exportable": True,
                    "deletable": True,
                    "encrypted_storage_requested_categories": [],
                    "encrypted_storage_active_categories": [],
                    "encrypted_storage_available": False,
                },
            },
        )

    async def collaboration_dashboard(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "collaboration.dashboard",
            {
                "workspace": str(workspace.resolve()),
                "viewer": {"user_id": kwargs.get("user_id") or "local-owner", "role": kwargs.get("role") or "owner"},
                "shared_workflows": [{"workflow_id": "collab-wf-core", "status": "waiting_approval"}],
                "active_workflows": [{"workflow_id": "collab-wf-core", "status": "waiting_approval"}],
                "approval_queue": [{"approval_id": "approval-core", "required_roles": ["owner"], "status": "pending"}],
                "roadmap_board": {"lanes": {"planned": []}, "milestones": {"alpha": 1}, "blocked": []},
                "repositories": [{"repository_id": "repo-main", "runtime_nodes": ["local"]}],
                "observability": {"pending_approval_count": 1, "active_workflow_count": 1, "repository_count": 1},
                "audit_events": [{"event_type": "collaboration.workflow.created"}],
            },
        )

    async def register_collaboration_member(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result("collaboration.member", {"member": {"user_id": payload.get("user_id"), "role": payload.get("role", "reviewer")}})

    async def register_collaboration_repository(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result("collaboration.repository", {"repository": {"repository_id": payload.get("repository_id", "repo-main")}})

    async def create_collaboration_workflow(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result("collaboration.workflow", {"workflow": {"workflow_id": "collab-wf-core", "status": "waiting_approval"}})

    async def collaboration_workflow_action(self, workspace: Path, workflow_id: str, payload: dict) -> CoreDelegationResult:
        status = {"pause": "paused", "resume": "active", "cancel": "cancelled"}.get(str(payload.get("action") or ""), "active")
        return _core_result("collaboration.workflow", {"workflow": {"workflow_id": workflow_id, "status": status}})

    async def create_collaboration_approval(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result("collaboration.approval", {"approval": {"approval_id": "approval-core", "status": "pending"}})

    async def decide_collaboration_approval(self, workspace: Path, approval_id: str, payload: dict) -> CoreDelegationResult:
        decision = str(payload.get("decision") or "approve")
        status = "approved" if decision == "approve" else "rejected"
        return _core_result("collaboration.approval", {"approval": {"approval_id": approval_id, "status": status}})

    async def assign_collaboration_roadmap_item(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result("collaboration.roadmap", {"roadmap_item": {"item_id": "roadmap-core", "title": payload.get("title")}})

    async def governance_dashboard(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _core_result(
            "governance.dashboard",
            {
                "workspace": str(workspace.resolve()),
                "ui_summary": {"status": "review", "policy_violations": 1},
                "compliance": {"enabled_policy_count": 10, "recent_violation_count": 1},
                "policy_violations": [{"event_id": "gov-event-core", "status": "needs_approval"}],
                "runtime_trust_levels": [{"id": "trusted"}],
            },
        )

    async def evaluate_governance_policy(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result(
            "governance.evaluation",
            {
                "evaluation_id": "policy-eval-core",
                "status": "needs_approval",
                "allowed": False,
                "approval_requirements": [{"policy_id": "gov.plugin.high_risk_permissions"}],
            },
            ok=False,
        )

    async def export_governance_compliance(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _core_result(
            "governance.compliance_export",
            {"path": str(workspace / ".aegis" / "governance-export-audit.json"), "export": {"export_id": "governance-export-core"}},
        )

    async def runtime_status(self, workspace: Path) -> dict:
        return {
            "core_connected": True,
            "delegated_workflows_enabled": True,
            "fallback_mode_active": False,
            "last_core_error": "",
        }

    def record_fallback(self, workflow: str, reason: str) -> None:
        self.fallbacks.append((workflow, reason))

    def record_local_only(self, workflow: str, reason: str) -> None:
        pass


class OfflineCoreClient(DelegatingCoreClient):
    async def apply_changes(self, workspace: Path, changes, **kwargs) -> CoreDelegationResult:
        return _offline("changes.apply")

    async def list_checkpoints(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _offline("checkpoints.list")

    async def restore_checkpoint(self, workspace: Path, checkpoint_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("checkpoints.restore")

    async def run_validation(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("validation.run")

    async def model_registry(self, workspace: Path) -> CoreDelegationResult:
        return _offline("model.registry")

    async def distributed_runtime(self, workspace: Path, *, include_audit: bool = True, limit: int = 100) -> CoreDelegationResult:
        return _offline("distributed.runtime")

    async def runtime_interaction(self, workspace: Path, *, limit: int = 100) -> CoreDelegationResult:
        return _offline("runtime.interaction")

    async def runtime_jobs(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.jobs")

    async def launch_runtime_job(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.job.mutation")

    async def runtime_job(self, workspace: Path, job_id: str) -> CoreDelegationResult:
        return _offline("runtime.job")

    async def cancel_runtime_job(self, workspace: Path, job_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.job.mutation")

    async def retry_runtime_job(self, workspace: Path, job_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.job.mutation")

    async def runtime_streams(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.streams")

    async def runtime_sessions(self, workspace: Path) -> CoreDelegationResult:
        return _offline("runtime.sessions")

    async def create_runtime_session(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.session.mutation")

    async def sync_runtime_session(self, workspace: Path, session_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.session.mutation")

    async def runtime_voice(self, workspace: Path) -> CoreDelegationResult:
        return _offline("runtime.voice")

    async def route_voice_command(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.voice.command")

    async def runtime_replay(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("runtime.replay")

    async def release_manifest(self, workspace: Path) -> CoreDelegationResult:
        return _offline("release.manifest")

    async def check_compatibility(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("release.compatibility")

    async def agent_runtime(self, workspace: Path) -> CoreDelegationResult:
        return _offline("agent.runtime")

    async def list_workflows(self, workspace: Path, *, include_completed: bool = False, limit: int = 30) -> CoreDelegationResult:
        return _offline("workflows.list")

    async def workflow_dashboard(self, workspace: Path, workflow_id: str) -> CoreDelegationResult:
        return _offline("workflow.dashboard")

    async def workflow_agent_coordination(self, workspace: Path, workflow_id: str) -> CoreDelegationResult:
        return _offline("agent.coordination")

    async def quality_gates(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _offline("quality.gates")

    async def evaluate_quality_gates(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("quality.gates.evaluate")

    async def benchmarks(self, workspace: Path, *, limit: int = 50) -> CoreDelegationResult:
        return _offline("quality.benchmarks")

    async def onboarding_status(self, workspace: Path) -> CoreDelegationResult:
        return _offline("onboarding.status")

    async def update_onboarding(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("onboarding.updated")

    async def run_first_workflow(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("onboarding.first_workflow")

    async def export_settings(self, workspace: Path) -> CoreDelegationResult:
        return _offline("settings.export")

    async def import_settings(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("settings.import")

    async def personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory")

    async def create_personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory.record")

    async def update_personal_memory(self, workspace: Path, memory_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory.record")

    async def delete_personal_memory(self, workspace: Path, memory_id: str, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory.deleted")

    async def export_personal_memory(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory.export")

    async def update_personal_memory_controls(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("personal.memory.controls")

    async def collaboration_dashboard(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("collaboration.dashboard")

    async def register_collaboration_member(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.member")

    async def register_collaboration_repository(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.repository")

    async def create_collaboration_workflow(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.workflow")

    async def collaboration_workflow_action(self, workspace: Path, workflow_id: str, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.workflow")

    async def create_collaboration_approval(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.approval")

    async def decide_collaboration_approval(self, workspace: Path, approval_id: str, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.approval")

    async def assign_collaboration_roadmap_item(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("collaboration.roadmap")

    async def governance_dashboard(self, workspace: Path, **kwargs) -> CoreDelegationResult:
        return _offline("governance.dashboard")

    async def evaluate_governance_policy(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("governance.evaluation")

    async def export_governance_compliance(self, workspace: Path, payload: dict) -> CoreDelegationResult:
        return _offline("governance.compliance_export")


class RejectingCoreClient(DelegatingCoreClient):
    async def apply_changes(self, workspace: Path, changes, **kwargs) -> CoreDelegationResult:
        return CoreDelegationResult(
            delegated=False,
            ok=False,
            reachable=True,
            status_code=400,
            kind="",
            data=None,
            envelope=None,
            error="path is blocked by Core safety rules",
        )


def test_apply_route_delegates_to_core_and_preserves_response_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).post(
            "/api/apply",
            json={
                "workspace_root": str(workspace),
                "changes": [{"action": "update", "path": "app.py", "content": "print('new')\n"}],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] == ["update: app.py"]
    assert payload["checkpoint"] == "checkpoint-core"
    assert payload["workspace_root"] == str(workspace.resolve())
    assert "workspace_files" in payload


def test_apply_route_falls_back_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        response = TestClient(main.app).post(
            "/api/apply",
            json={
                "workspace_root": str(workspace),
                "changes": [{"action": "update", "path": "app.py", "content": "print('fallback')\n"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["applied"] == ["update: app.py"]
    assert response.json()["checkpoint"]
    assert (workspace / "app.py").read_text(encoding="utf-8") == "print('fallback')\n"
    assert fake_core.fallbacks[0][0] == "changes.apply"


def test_apply_route_does_not_fallback_when_core_rejects_a_safety_error(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", RejectingCoreClient()):
        response = TestClient(main.app).post(
            "/api/apply",
            json={
                "workspace_root": str(workspace),
                "changes": [{"action": "create", "path": ".env", "content": "SECRET=value\n"}],
            },
        )

    assert response.status_code == 400
    assert "Core safety" in response.json()["detail"]
    assert not (workspace / ".env").exists()


def test_checkpoint_routes_delegate_to_core(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        created = client.post("/api/checkpoints", json={"workspace_root": str(workspace), "paths": ["app.py"]})
        listed = client.get("/api/checkpoints", params={"workspace_root": str(workspace)})
        restored = client.post(
            "/api/restore-checkpoint",
            json={"workspace_root": str(workspace), "checkpoint": "checkpoint-core"},
        )

    assert created.status_code == 200
    assert created.json()["id"] == "checkpoint-manual"
    assert listed.status_code == 200
    assert listed.json()["checkpoints"][0]["id"] == "checkpoint-core"
    assert restored.status_code == 200
    assert restored.json()["restored"] == ["restore: app.py"]


def test_validation_route_delegates_to_core_and_creates_repair_workflow(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).post("/api/validate", json={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-validation"
    assert payload["validation"]["command"] == "python -m pytest"
    assert payload["validation"]["exit_code"] == 1
    assert "workflow-repair" in " ".join(payload["warnings"])
    assert any(event["kind"] == "repair" for event in payload["events"])


def test_validation_route_falls_back_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()

    async def fake_validate(workspace_root: str | None) -> ValidateResponse:
        return ValidateResponse(task_id="local-validation", workspace_root=str(workspace), warnings=["local fallback"])

    with (
        patch.object(main, "core_runtime_client", fake_core),
        patch.object(main.agent, "validate_workspace", fake_validate),
    ):
        response = TestClient(main.app).post("/api/validate", json={"workspace_root": str(workspace)})

    assert response.status_code == 200
    assert response.json()["task_id"] == "local-validation"
    assert response.json()["warnings"] == ["local fallback"]
    assert fake_core.fallbacks[0][0] == "validation.run"


def test_runtime_delegation_status_endpoint_reports_core_mode(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).get("/api/runtime/delegation", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    assert response.json()["core_connected"] is True
    assert response.json()["delegated_workflows_enabled"] is True
    assert response.json()["fallback_mode_active"] is False


def test_distributed_runtime_route_delegates_to_core_snapshot(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).get("/api/distributed-runtime", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["workers"][0]["worker_id"] == "local"
    assert payload["workers"][0]["metadata"]["source"] == "aegis-core"
    assert payload["queue"][0]["id"] == "workload-core"
    assert payload["observability"]["workers_total"] == 1
    assert "Aegis Core distributed runtime" in payload["security_summary"][0]


def test_distributed_runtime_route_falls_back_when_core_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        response = TestClient(main.app).get("/api/distributed-runtime", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    assert response.json()["workers"]
    assert fake_core.fallbacks[0][0] == "distributed.runtime"


def test_runtime_interaction_routes_delegate_to_core(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/runtime-interaction", params={"workspace_root": str(workspace)})
        jobs = client.get("/api/runtime-interaction/jobs", params={"workspace_root": str(workspace)})
        launched = client.post(
            "/api/runtime-interaction/jobs",
            json={"workspace_root": str(workspace), "command": ["python", "-m", "pytest"], "approval": True},
        )
        lookup = client.get("/api/runtime-interaction/jobs/rt-job-created", params={"workspace_root": str(workspace)})
        streams = client.get("/api/runtime-interaction/streams", params={"workspace_root": str(workspace)})
        session = client.post("/api/runtime-interaction/sessions", json={"workspace_root": str(workspace), "title": "Pair review"})
        voice = client.post(
            "/api/runtime-interaction/voice/command",
            json={"workspace_root": str(workspace), "transcript": "pause workflow"},
        )
        replay = client.get("/api/runtime-interaction/replay", params={"workspace_root": str(workspace)})

    assert dashboard.status_code == 200
    assert dashboard.json()["delegated"] is True
    assert dashboard.json()["jobs"][0]["job_id"] == "rt-job-core"
    assert jobs.status_code == 200
    assert jobs.json()["jobs"][0]["job_id"] == "rt-job-core"
    assert launched.status_code == 200
    assert launched.json()["job"]["job_id"] == "rt-job-created"
    assert lookup.status_code == 200
    assert lookup.json()["job"]["job_id"] == "rt-job-created"
    assert streams.status_code == 200
    assert streams.json()["events"][0]["chunk"] == "ok"
    assert session.status_code == 200
    assert session.json()["session"]["session_id"] == "session-core"
    assert voice.status_code == 200
    assert voice.json()["command"]["intent"] == "pause_workflow"
    assert replay.status_code == 200
    assert replay.json()["terminal_output"]


def test_runtime_interaction_status_degrades_when_core_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        client = TestClient(main.app)
        dashboard = client.get("/api/runtime-interaction", params={"workspace_root": str(workspace)})
        launch = client.post(
            "/api/runtime-interaction/jobs",
            json={"workspace_root": str(workspace), "command": ["python", "-m", "pytest"], "approval": True},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["delegated"] is False
    assert dashboard.json()["fallback_mode_active"] is True
    assert launch.status_code == 503
    assert any(workflow == "runtime.interaction" for workflow, _ in fake_core.fallbacks)


def test_agent_supervision_route_delegates_to_core_and_preserves_gateway_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).get("/api/agent-supervision", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["core_connected"] is True
    assert payload["active_workflow"]["id"] == "workflow-core"
    assert payload["coordination"]["agents"][0]["id"] == "planner_agent"
    assert payload["task_counts"]["approval_requests"] == 1
    assert payload["events_url"].startswith("/api/agent-supervision/workflows/workflow-core/events")


def test_agent_supervision_workflow_controls_delegate_to_core(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        step = client.post(
            "/api/agent-supervision/workflows/workflow-core/step",
            json={"workspace_root": str(workspace), "action": "advance", "task_id": "task-plan", "approval": True},
        )
        delegated = client.post(
            "/api/agent-supervision/workflows/workflow-core/agents/delegate",
            json={"workspace_root": str(workspace), "task_id": "task-plan", "agent_id": "coder_agent", "approval": True},
        )

    assert step.status_code == 200
    assert step.json()["ok"] is True
    assert step.json()["delegated"] is True
    assert delegated.status_code == 200
    assert delegated.json()["ok"] is True
    assert delegated.json()["delegated"] is True


def test_agent_supervision_route_degrades_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", OfflineCoreClient()):
        response = TestClient(main.app).get("/api/agent-supervision", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["core_connected"] is False
    assert payload["fallback_mode_active"] is True
    assert payload["active_workflow"] is None
    assert "Core offline" in payload["last_core_error"]


def test_collaboration_routes_delegate_to_core_and_preserve_gateway_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/collaboration", params={"workspace_root": str(workspace), "user_id": "owner-1"})
        member = client.post(
            "/api/collaboration/members",
            json={"workspace_root": str(workspace), "user_id": "reviewer-1", "role": "reviewer"},
        )
        repository = client.post(
            "/api/collaboration/repositories",
            json={"workspace_root": str(workspace), "repository_id": "repo-main", "path": "."},
        )
        workflow = client.post(
            "/api/collaboration/workflows",
            json={"workspace_root": str(workspace), "objective": "Ship a reviewed change"},
        )
        action = client.post(
            "/api/collaboration/workflows/collab-wf-core/action",
            json={"workspace_root": str(workspace), "action": "pause", "actor_id": "owner-1", "actor_role": "owner"},
        )
        approval = client.post(
            "/api/collaboration/approvals",
            json={"workspace_root": str(workspace), "target_type": "workflow", "target_id": "collab-wf-core"},
        )
        decision = client.post(
            "/api/collaboration/approvals/approval-core/decision",
            json={"workspace_root": str(workspace), "decision": "approve", "user_id": "owner-1", "role": "owner"},
        )
        roadmap = client.post(
            "/api/collaboration/roadmap/items",
            json={"workspace_root": str(workspace), "title": "Alpha signoff", "workflow_id": "collab-wf-core"},
    )

    assert dashboard.status_code == 200
    assert dashboard.json()["runtime"] == "core"
    assert dashboard.json()["data"]["approval_queue"][0]["approval_id"] == "approval-core"
    assert member.status_code == 200
    assert member.json()["data"]["member"]["role"] == "reviewer"
    assert repository.status_code == 200
    assert repository.json()["data"]["repository"]["repository_id"] == "repo-main"
    assert workflow.status_code == 200
    assert workflow.json()["data"]["workflow"]["workflow_id"] == "collab-wf-core"
    assert action.status_code == 200
    assert action.json()["data"]["workflow"]["status"] == "paused"
    assert approval.status_code == 200
    assert approval.json()["data"]["approval"]["status"] == "pending"
    assert decision.status_code == 200
    assert decision.json()["data"]["approval"]["status"] == "approved"
    assert roadmap.status_code == 200
    assert roadmap.json()["data"]["roadmap_item"]["title"] == "Alpha signoff"


def test_collaboration_mutations_fail_closed_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", OfflineCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/collaboration", params={"workspace_root": str(workspace)})
        workflow = client.post(
            "/api/collaboration/workflows",
            json={"workspace_root": str(workspace), "objective": "Needs Core"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["runtime"] == "website_fallback"
    assert dashboard.json()["fallback"] is True
    assert workflow.status_code == 503


def test_governance_routes_delegate_to_core_and_preserve_gateway_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/governance", params={"workspace_root": str(workspace)})
        evaluation = client.post(
            "/api/governance/evaluate",
            json={"workspace_root": str(workspace), "action_type": "plugin_enable", "context": {"permission_scopes": ["filesystem_write"]}},
        )
        exported = client.post(
            "/api/governance/compliance/export",
            json={"workspace_root": str(workspace), "export_type": "audit"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["runtime"] == "core"
    assert dashboard.json()["data"]["ui_summary"]["status"] == "review"
    assert evaluation.status_code == 200
    assert evaluation.json()["data"]["status"] == "needs_approval"
    assert exported.status_code == 200
    assert exported.json()["data"]["export"]["export_id"] == "governance-export-core"


def test_governance_mutations_fail_closed_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", OfflineCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/governance", params={"workspace_root": str(workspace)})
        evaluation = client.post(
            "/api/governance/evaluate",
            json={"workspace_root": str(workspace), "action_type": "provider_call"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["runtime"] == "website_fallback"
    assert dashboard.json()["fallback"] is True
    assert evaluation.status_code == 503


def test_quality_gate_routes_delegate_to_core_and_preserve_gateway_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        dashboard = client.get("/api/quality-gates", params={"workspace_root": str(workspace)})
        evaluated = client.post(
            "/api/quality-gates/evaluate",
            json={
                "workspace_root": str(workspace),
                "changes": [{"action": "update", "path": "app.py", "content": "print('new')\n"}],
            },
        )
        workflow_quality = client.get(
            "/api/quality-gates/workflows/workflow-core",
            params={"workspace_root": str(workspace)},
        )
        benchmarks = client.get("/api/benchmarks", params={"workspace_root": str(workspace)})
        benchmark_run = client.post(
            "/api/benchmarks/run",
            json={"workspace_root": str(workspace), "suite_ids": ["coding_task_quality"]},
        )
        reports = client.get("/api/evaluation-reports", params={"workspace_root": str(workspace)})
        created_report = client.post(
            "/api/evaluation-reports",
            json={"workspace_root": str(workspace), "quality_run_id": "quality-core"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["latest"]["id"] == "quality-core"
    assert evaluated.status_code == 200
    assert evaluated.json()["apply_allowed"] is True
    assert workflow_quality.status_code == 200
    assert workflow_quality.json()["workflow_id"] == "workflow-core"
    assert benchmarks.status_code == 200
    assert benchmarks.json()["suites"][0]["id"] == "coding_task_quality"
    assert benchmark_run.status_code == 200
    assert benchmark_run.json()["id"] == "benchmark-core"
    assert reports.status_code == 200
    assert reports.json()["latest"]["id"] == "evaluation-core"
    assert created_report.status_code == 200
    assert created_report.json()["rollback_instructions"]


def test_quality_gate_route_degrades_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        response = TestClient(main.app).get("/api/quality-gates", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["fallback_mode_active"] is True
    assert payload["latest"] is None
    assert fake_core.fallbacks[0][0] == "quality.gates"


def test_onboarding_routes_delegate_to_core_and_preserve_gateway_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        status = client.get("/api/onboarding/status", params={"workspace_root": str(workspace)})
        updated = client.post(
            "/api/onboarding",
            json={"workspace_root": str(workspace), "completed_steps": ["welcome"], "current_step": "workspace"},
        )
        first = client.post(
            "/api/onboarding/first-workflow",
            json={"workspace_root": str(workspace), "action": "scan_project", "dry_run": True},
        )
        exported = client.get("/api/settings/export", params={"workspace_root": str(workspace)})
        imported = client.post(
            "/api/settings/import",
            json={
                "workspace_root": str(workspace),
                "dry_run": True,
                "settings": {"default_model": "qwen3-coder:30b", "api_key": "sk-secret"},
            },
        )

    assert status.status_code == 200
    assert status.json()["delegated"] is True
    assert status.json()["current_step"] == "local_models"
    assert updated.status_code == 200
    assert updated.json()["current_step"] == "workspace"
    assert first.status_code == 200
    assert first.json()["action"] == "scan_project"
    assert exported.status_code == 200
    assert exported.json()["settings"]["default_model"] == "qwen3-coder:30b"
    assert imported.status_code == 200
    assert imported.json()["ignored_keys"] == ["api_key"]


def test_onboarding_status_degrades_to_website_diagnostics_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        response = TestClient(main.app).get("/api/onboarding/status", params={"workspace_root": str(workspace)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["delegated"] is False
    assert payload["fallback_mode_active"] is True
    assert any(check["id"] == "website_backend" for check in payload["diagnostics"]["checks"])
    assert fake_core.fallbacks[0][0] == "onboarding.status"


def test_memory_routes_delegate_to_core_and_preserve_legacy_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = DelegatingCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        client = TestClient(main.app)
        listed = client.get("/api/memory", params={"workspace_root": str(workspace), "category": "insight"})
        created = client.post(
            "/api/memory",
            params={"workspace_root": str(workspace)},
            json={
                "title": "Use local validation",
                "content": "Run pytest before applying changes.",
                "category": "preference",
                "tags": ["validation"],
                "related_files": ["app.py"],
                "pinned": True,
            },
        )
        updated = client.put(
            "/api/memory/mem-created",
            params={"workspace_root": str(workspace)},
            json={"title": "Use pytest validation", "content": "Run pytest before apply."},
        )
        deleted = client.delete("/api/memory/mem-created", params={"workspace_root": str(workspace)})
        governance = client.get("/api/memory/governance", params={"workspace_root": str(workspace)})
        exported = client.post(
            "/api/memory/export",
            params={"workspace_root": str(workspace)},
            json={"categories": ["insight"], "redact_sensitive": True},
        )
        controls = client.post(
            "/api/memory/controls",
            params={"workspace_root": str(workspace)},
            json={"category": "fix", "enabled": False, "retention_days": 90},
        )

    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["runtime"] == "aegis-core"
    assert listed_payload["notes"][0]["id"] == "mem-core"
    assert listed_payload["notes"][0]["category"] == "insight"
    assert listed_payload["governance"]["mode"] == "local_only"
    assert listed_payload["governance"]["cloud_context_requires_consent"] is True
    assert listed_payload["governance"]["sensitive_export_default"] == "redacted"

    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["id"] == "mem-created"
    assert created_payload["category"] == "preference"
    assert created_payload["related_files"] == ["app.py"]

    assert updated.status_code == 200
    assert updated.json()["title"] == "Use pytest validation"
    assert updated.json()["category"] == "preference"

    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == "mem-created"
    assert deleted.json()["runtime"] == "aegis-core"
    assert governance.status_code == 200
    assert governance.json()["governance"]["disabled_categories"] == ["repair_history"]
    assert governance.json()["governance"]["audit_available"] is True
    assert exported.status_code == 200
    assert exported.json()["record_count"] == 1
    assert exported.json()["governance"]["storage_boundary"] == "aegis-core-project-memory"
    assert controls.status_code == 200
    assert controls.json()["governance"]["retention_by_category"]["repair_history"] == 90


def test_memory_routes_fallback_when_core_is_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        client = TestClient(main.app)
        created = client.post(
            "/api/memory",
            params={"workspace_root": str(workspace)},
            json={"title": "Fallback memory", "content": "Stored locally with api_key=legacy-secret-value.", "category": "insight"},
        )
        note_id = created.json()["id"]
        listed = client.get("/api/memory", params={"workspace_root": str(workspace), "category": "insight"})
        governance = client.get("/api/memory/governance", params={"workspace_root": str(workspace)})
        exported = client.post(
            "/api/memory/export",
            params={"workspace_root": str(workspace)},
            json={"redact_sensitive": True},
        )
        updated = client.put(
            f"/api/memory/{note_id}",
            params={"workspace_root": str(workspace)},
            json={"content": "Updated locally.", "pinned": True},
        )
        deleted = client.delete(f"/api/memory/{note_id}", params={"workspace_root": str(workspace)})

    assert created.status_code == 200
    assert created.json()["title"] == "Fallback memory"
    assert listed.status_code == 200
    assert listed.json()["runtime"] == "website-backend"
    assert listed.json()["notes"][0]["id"] == note_id
    assert listed.json()["governance"]["storage_boundary"] == "website-backend-local-memory-files"
    assert governance.status_code == 200
    assert governance.json()["governance"]["cloud_context_requires_consent"] is True
    assert governance.json()["governance"]["controls"]["transparency"]["category_controls"] is False
    assert exported.status_code == 200
    serialized_export = str(exported.json())
    assert "legacy-secret-value" not in serialized_export
    assert "[REDACTED_SECRET]" in serialized_export
    assert updated.status_code == 200
    assert updated.json()["content"] == "Updated locally."
    assert deleted.status_code == 200
    assert deleted.json()["runtime"] == "website-backend"
    assert any(workflow.startswith("personal.memory") for workflow, _ in fake_core.fallbacks)


def test_model_registry_route_merges_core_registry_without_breaking_shape(tmp_path: Path) -> None:
    _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        response = TestClient(main.app).get("/api/model-registry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_provider_id"] == "ollama"
    assert payload["active_model"] == "qwen3-coder:30b"
    assert payload["router_enabled"] is True
    assert any(provider["id"] == "ollama" and provider["health"] == "available" for provider in payload["providers"])
    assert any(preset["id"] == "best_coding" for preset in payload["presets"])
    assert "Aegis Core model registry connected" in payload["message"]


def test_model_registry_route_falls_back_when_core_is_offline(tmp_path: Path) -> None:
    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        response = TestClient(main.app).get("/api/model-registry")

    assert response.status_code == 200
    assert response.json()["providers"]
    assert fake_core.fallbacks[0][0] == "model.registry"


def test_release_routes_delegate_and_degrade_without_breaking_shape(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with patch.object(main, "core_runtime_client", DelegatingCoreClient()):
        client = TestClient(main.app)
        manifest = client.get("/api/release/manifest", params={"workspace_root": str(workspace)})
        compatibility = client.get("/api/release/compatibility", params={"workspace_root": str(workspace)})

    assert manifest.status_code == 200
    assert manifest.json()["delegated"] is True
    assert manifest.json()["manifest"]["schema_version"] == "2026.05.12"
    assert compatibility.status_code == 200
    assert compatibility.json()["delegated"] is True
    assert compatibility.json()["compatible"] is True

    fake_core = OfflineCoreClient()
    with patch.object(main, "core_runtime_client", fake_core):
        offline = TestClient(main.app).get("/api/release/compatibility", params={"workspace_root": str(workspace)})

    assert offline.status_code == 200
    assert offline.json()["delegated"] is False
    assert offline.json()["fallback_mode_active"] is True
    assert fake_core.fallbacks[0][0] == "release.compatibility"
