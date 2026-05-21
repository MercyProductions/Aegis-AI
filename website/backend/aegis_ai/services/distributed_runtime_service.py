from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from ..schemas import (
    DistributedRuntimeSnapshot,
    ExecutionDispatchRequest,
    ExecutionDispatchResponse,
    ExecutionQueueActionRequest,
    ExecutionQueueCreateRequest,
    ExecutionQueueItem,
    HybridRouteDecision,
    HybridRouteRequest,
    RemoteWorkspaceSyncManifest,
    RemoteWorkspaceSyncRequest,
    RuntimeObservabilitySnapshot,
    WorkerActionRequest,
    WorkerAuditEvent,
    WorkerCapabilitySet,
    WorkerHeartbeatRequest,
    WorkerRegistrationRequest,
    WorkerRuntimeInfo,
)
from ..storage import utc_now


class DistributedRuntimeService:
    def __init__(
        self,
        *,
        settings_factory: Callable[[], Any],
        agent_factory: Callable[[], Any],
        workspace_manager_factory: Callable[[], Any],
        distributed_runtime_factory: Callable[[], Any],
        model_registry_factory: Callable[[], Any],
        model_benchmarks_factory: Callable[[], Any],
        workspace_resolver: Callable[[str | None], Path],
        runtime_payload_dumper: Callable[[Any], Any],
        project_intelligence_builder: Callable[[Path], Any],
        task_transition_or_event: Callable[..., None],
    ) -> None:
        self._settings_factory = settings_factory
        self._agent_factory = agent_factory
        self._workspace_manager_factory = workspace_manager_factory
        self._distributed_runtime_factory = distributed_runtime_factory
        self._model_registry_factory = model_registry_factory
        self._model_benchmarks_factory = model_benchmarks_factory
        self._workspace_resolver = workspace_resolver
        self._runtime_payload_dumper = runtime_payload_dumper
        self._project_intelligence_builder = project_intelligence_builder
        self._task_transition_or_event = task_transition_or_event

    @property
    def settings(self) -> Any:
        return self._settings_factory()

    @property
    def agent(self) -> Any:
        return self._agent_factory()

    @property
    def workspace_manager(self) -> Any:
        return self._workspace_manager_factory()

    @property
    def distributed_runtime(self) -> Any:
        return self._distributed_runtime_factory()

    @property
    def model_registry(self) -> Any:
        return self._model_registry_factory()

    @property
    def model_benchmarks(self) -> Any:
        return self._model_benchmarks_factory()

    def workers(self, root: Path) -> list[WorkerRuntimeInfo]:
        self.distributed_runtime.ensure_local_worker(self.agent.store, root)
        return self.agent.store.runtime_workers()

    def jobs(
        self,
        root: Path,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ExecutionQueueItem]:
        return self.agent.store.execution_jobs(project_root=root, status=status, limit=limit)

    def audit_events(
        self,
        *,
        worker_id: str = "",
        job_id: str = "",
        limit: int = 100,
    ) -> list[WorkerAuditEvent]:
        return self.agent.store.worker_audit_events(worker_id=worker_id, job_id=job_id, limit=limit)

    def record_audit(self, event: WorkerAuditEvent) -> WorkerAuditEvent:
        return self.agent.store.record_worker_audit_event(event)

    def snapshot(
        self,
        root: Path,
        routing: HybridRouteDecision | None = None,
    ) -> DistributedRuntimeSnapshot:
        workers = self.workers(root)
        jobs = self.jobs(root, limit=200)
        audit_events = self.audit_events(limit=120)
        sync_manifests = self.agent.store.workspace_sync_manifests(project_root=root, limit=20)
        return self.distributed_runtime.snapshot(
            workers=workers,
            jobs=jobs,
            audit_events=audit_events,
            sync_manifests=sync_manifests,
            routing=routing,
        )

    def snapshot_from_core(self, root: Path, result: Any) -> DistributedRuntimeSnapshot | None:
        if not result.delegated or not isinstance(result.data, dict):
            return None
        data = result.data
        workers = [self.core_node_to_worker(item) for item in data.get("nodes", []) if isinstance(item, dict)]
        jobs = [self.core_workload_to_queue_item(root, item) for item in data.get("workloads", []) if isinstance(item, dict)]
        audit_events = [
            self.core_audit_to_worker_event(item)
            for item in data.get("audit_events", [])
            if isinstance(item, dict)
        ]
        observability = self.core_observability_to_runtime(
            data.get("observability") if isinstance(data.get("observability"), dict) else {},
            data.get("generated_at", ""),
        )
        return DistributedRuntimeSnapshot(
            generated_at=str(data.get("generated_at") or utc_now()),
            execution_mode="local",
            workers=workers,
            queue=jobs,
            observability=observability,
            audit_events=audit_events,
            routing=None,
            sync_manifests=[],
            security_summary=[
                "Sourced from Aegis Core distributed runtime.",
                "Local Core remains the authority for approvals, audit, checkpoints, and fallback.",
            ],
        )

    def core_node_to_worker(self, node: dict[str, Any]) -> WorkerRuntimeInfo:
        node_type = str(node.get("node_type") or "trusted_remote")
        capabilities = set(str(item) for item in node.get("capabilities", []) if item)
        gpu = node.get("gpu") if isinstance(node.get("gpu"), dict) else {}
        cpu = node.get("cpu") if isinstance(node.get("cpu"), dict) else {}
        worker_kind = "local" if node_type == "local" else "sandbox" if node_type in {"isolated_worker", "validation", "indexing"} else "remote"
        status_map = {
            "online": "available",
            "idle": "available",
            "busy": "busy",
            "offline": "offline",
            "degraded": "offline",
            "untrusted": "untrusted",
            "revoked": "revoked",
        }
        trust_level = str(node.get("trust_level") or "untrusted")
        return WorkerRuntimeInfo(
            worker_id=str(node.get("node_id") or "node"),
            name=str(node.get("name") or node.get("node_id") or "Runtime Node"),
            kind=worker_kind,
            endpoint=str(node.get("endpoint") or ""),
            status=status_map.get(str(node.get("status") or "offline"), "offline"),
            trust_state="trusted" if trust_level in {"local", "trusted"} else "revoked" if trust_level == "revoked" else "untrusted",
            trust_scope=str(node.get("trust_scope") or trust_level),
            registered_at=str(node.get("registered_at") or ""),
            last_heartbeat_at=str(node.get("last_heartbeat_at") or ""),
            capabilities=WorkerCapabilitySet(
                installed_sdks=[],
                build_tools=[],
                supported_languages=[],
                available_models=[str(item) for item in node.get("installed_models", [])],
                gpu_available=bool(gpu.get("available") or "gpu" in capabilities),
                ram_gb=float(node.get("ram_gb") or 0.0),
                cpu_cores=int(cpu.get("logical_cores") or cpu.get("cores") or 0),
                validation_support="validation_execution" in capabilities,
                sandbox_profiles=[str((node.get("isolation") or {}).get("workspace_mount") or "native")],
                supported_job_kinds=self.core_supported_job_kinds(capabilities),
                supports_remote_sync=node_type != "local",
                max_parallel_jobs=max(1, int(node.get("max_parallel_workloads") or 1)),
            ),
            current_jobs=max(0, int(node.get("current_workload_count") or 0)),
            permission_scopes=[str(item) for item in node.get("permission_scopes", [])],
            isolation_level="process" if node_type == "local" else "container" if node_type == "isolated_worker" else "remote",
            metadata={
                "source": "aegis-core",
                "installed_plugins": node.get("installed_plugins", []),
                "warnings": node.get("warnings", []),
                "transport": node.get("transport", {}),
            },
        )

    def core_supported_job_kinds(self, capabilities: set[str]) -> list[str]:
        kinds: list[str] = []
        if "validation_execution" in capabilities:
            kinds.extend(["validation", "build"])
        if "indexing" in capabilities or "workspace_scan" in capabilities:
            kinds.append("indexing")
        if "repair" in capabilities:
            kinds.append("repair")
        if "benchmark" in capabilities:
            kinds.append("benchmark")
        if "workflow_execution" in capabilities or "model_inference" in capabilities or "plugin_execution" in capabilities:
            kinds.append("task")
        return sorted(set(kinds)) or ["task"]

    def core_workload_to_queue_item(self, root: Path, workload: dict[str, Any]) -> ExecutionQueueItem:
        kind_map = {
            "validation": "validation",
            "build": "build",
            "indexing": "indexing",
            "repair": "repair",
            "benchmark": "benchmark",
        }
        status_map = {
            "queued": "queued",
            "assigned": "assigned",
            "dispatching": "running",
            "running": "running",
            "completed": "succeeded",
            "failed": "failed",
            "cancelled": "canceled",
            "waiting_approval": "blocked",
        }
        workload_id = str(workload.get("workload_id") or uuid4())
        return ExecutionQueueItem(
            id=workload_id,
            task_id=str(workload.get("workflow_type") or ""),
            workspace_root=str(workload.get("workspace") or root),
            kind=kind_map.get(str(workload.get("workload_type") or ""), "task"),
            title=str(workload.get("title") or workload_id),
            user_goal=str(workload.get("scheduling_reason") or ""),
            status=status_map.get(str(workload.get("status") or "queued"), "queued"),
            priority=int(workload.get("priority") or 0),
            created_at=str(workload.get("created_at") or utc_now()),
            updated_at=str(workload.get("updated_at") or ""),
            assigned_worker_id=str(workload.get("assigned_node_id") or ""),
            attempts=int(workload.get("attempts") or 0),
            max_attempts=max(1, int(workload.get("max_attempts") or 1)),
            required_capabilities=[str(item) for item in workload.get("required_capabilities", [])],
            permission_scope=", ".join(str(item) for item in workload.get("permission_scopes", [])) or "read",
            sandbox_profile="remote" if workload.get("allow_remote") else "safe",
            payload=workload.get("payload") if isinstance(workload.get("payload"), dict) else {},
            error_summary="; ".join(str(item) for item in workload.get("errors", [])),
            result_summary=str((workload.get("result") or {}).get("message") or ""),
        )

    def core_audit_to_worker_event(self, event: dict[str, Any]) -> WorkerAuditEvent:
        return WorkerAuditEvent(
            id=str(event.get("event_id") or uuid4()),
            created_at=str(event.get("created_at") or utc_now()),
            worker_id=str(event.get("node_id") or ""),
            job_id=str(event.get("workload_id") or ""),
            event_type=str(event.get("event_type") or "runtime.event"),
            status="warning" if event.get("severity") == "warning" else "error" if event.get("severity") == "error" else "ok",
            detail=str((event.get("details") or {}).get("reason") or event.get("event_type") or ""),
            metadata=event.get("details") if isinstance(event.get("details"), dict) else {},
        )

    def core_observability_to_runtime(self, observability: dict[str, Any], generated_at: str) -> RuntimeObservabilitySnapshot:
        nodes = observability.get("nodes") if isinstance(observability.get("nodes"), dict) else {}
        workloads = observability.get("workloads") if isinstance(observability.get("workloads"), dict) else {}
        latency = observability.get("latency") if isinstance(observability.get("latency"), dict) else {}
        by_status = nodes.get("by_status") if isinstance(nodes.get("by_status"), dict) else {}
        by_trust = nodes.get("by_trust") if isinstance(nodes.get("by_trust"), dict) else {}
        return RuntimeObservabilitySnapshot(
            generated_at=str(generated_at or utc_now()),
            workers_total=int(nodes.get("total") or 0),
            workers_available=int(nodes.get("online") or 0),
            workers_busy=int(by_status.get("busy") or 0),
            workers_offline=int(by_status.get("offline") or 0),
            workers_untrusted=int(by_trust.get("untrusted") or 0),
            queued_jobs=int(workloads.get("queued") or 0),
            running_jobs=int(workloads.get("active") or 0),
            failed_jobs=int(workloads.get("failed") or 0),
            succeeded_jobs=int(workloads.get("completed") or 0),
            task_throughput=workloads.get("by_type") if isinstance(workloads.get("by_type"), dict) else {},
            queue_latency_ms=float(latency.get("average_duration_ms") or 0.0),
        )

    def remote_sync_payload(self, root: Path, sections: list[str]) -> dict[str, Any]:
        wanted = set(sections or ["task_history", "checkpoints", "project_memory", "architecture_maps", "validation_profiles", "settings"])
        payload: dict[str, Any] = {}
        if "task_history" in wanted:
            payload["task_history"] = self._runtime_payload_dumper(
                self.agent.store.list_tasks(project_root=root, limit=100, include_subtasks=True)
            )
        if "checkpoints" in wanted:
            payload["checkpoints"] = self._runtime_payload_dumper(self.workspace_manager.list_checkpoints(root, limit=50))
        if "project_memory" in wanted:
            payload["project_memory"] = self._runtime_payload_dumper(self.agent.store.project_memory(project_root=root, limit=200))
        if "architecture_maps" in wanted:
            intelligence = self.agent.store.project_intelligence(project_root=root)
            payload["architecture_maps"] = self._runtime_payload_dumper(intelligence.architecture if intelligence else {})
            payload["project_profile"] = self._runtime_payload_dumper(intelligence.profile if intelligence else {})
        if "validation_profiles" in wanted:
            payload["validation_profiles"] = self._runtime_payload_dumper(self.agent.validation.profile_snapshot(root))
        if "settings" in wanted:
            settings = self.settings
            payload["settings"] = {
                "model_api": settings.aegis_model_api,
                "model_endpoint": settings.aegis_model_endpoint,
                "model_name": settings.aegis_model_name,
                "approval_tier": settings.approval_tier,
                "sandbox_profile": settings.sandbox_profile,
                "router_execution_enabled": settings.aegis_router_execution_enabled,
                "shared_workspace_mode": settings.aegis_shared_workspace_mode,
            }
        return payload

    def save_remote_sync_manifest(self, root: Path, request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
        payload = self.remote_sync_payload(root, request.sections)
        manifest = self.distributed_runtime.sync_manifest(
            workspace_root=root,
            sections=request.sections,
            encrypted=request.encrypted,
            payload=payload,
        )
        saved = self.agent.store.save_workspace_sync_manifest(manifest)
        self.record_audit(
            self.distributed_runtime.audit_event(
                event_type="sync.manifest.created",
                detail=f"Workspace sync manifest {saved.id} captured {len(saved.included_sections)} section(s).",
                metadata={"workspace_root": str(root), "encrypted": saved.encrypted, "manifest_hash": saved.manifest_hash},
            )
        )
        return saved

    def run_command_job(self, job: ExecutionQueueItem, root: Path, *, allow_commands: bool) -> tuple[str, str, dict[str, Any]]:
        command = str(job.payload.get("command") or "").strip()
        if not allow_commands:
            return "blocked", "Command execution was not allowed for this dispatch.", {"allow_commands": False}

        if command:
            result = self.agent.commands.run(command, root, sandbox_profile=job.sandbox_profile)
            payload = {
                "command": result.command,
                "cwd": result.cwd,
                "allowed": result.allowed,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "reason": result.reason,
            }
            if job.task_id:
                self.agent.store.record_event(
                    job.task_id,
                    kind="command",
                    title="Distributed command executed",
                    status="ok" if result.ok else "error" if result.allowed else "warning",
                    detail=result.reason,
                    payload=payload,
                )
            if result.ok:
                return "succeeded", f"Command `{command}` exited with 0.", payload
            if not result.allowed:
                return "blocked", result.reason, payload
            return "failed", f"Command `{command}` exited with {result.exit_code}.", payload

        validation = self.agent._run_validation(root, lambda *_args, **_kwargs: None, manual=True)
        if validation is None:
            return "blocked", "No validation command was available for this workspace.", {}
        payload = validation.model_dump(mode="json")
        if validation.exit_code == 0:
            return "succeeded", f"Validation command `{validation.command}` exited with 0.", payload
        if not validation.allowed:
            return "blocked", validation.summary or validation.reason, payload
        return "failed", f"Validation command `{validation.command}` exited with {validation.exit_code}.", payload

    def queue_repair_after_validation_failure(
        self,
        job: ExecutionQueueItem,
        root: Path,
        summary: str,
    ) -> ExecutionQueueItem:
        repair = self.distributed_runtime.create_queue_item(
            ExecutionQueueCreateRequest(
                workspace_root=str(root),
                task_id=job.task_id,
                kind="repair",
                title=f"Repair after {job.title or job.kind}",
                user_goal=f"Repair validation failure from {job.id}.",
                priority=max(0, job.priority - 1),
                max_attempts=1,
                permission_scope="repair",
                sandbox_profile=job.sandbox_profile,
                payload={"source_validation_job_id": job.id, "failure_summary": summary},
            ),
            root,
        )
        created = self.agent.store.create_execution_job(repair)
        self.record_audit(
            self.distributed_runtime.audit_event(
                job_id=created.id,
                event_type="queue.repair.created",
                detail=f"Repair job was queued after validation failure in {job.id}.",
                metadata={"source_job_id": job.id, "task_id": job.task_id},
            )
        )
        if job.task_id:
            self.agent.store.record_event(
                job.task_id,
                kind="repair",
                title="Repair queued",
                status="warning",
                detail=summary,
                payload={"source_job_id": job.id, "repair_job_id": created.id},
            )
        return created

    def execute_job(
        self,
        job: ExecutionQueueItem,
        worker: WorkerRuntimeInfo,
        *,
        allow_commands: bool,
    ) -> tuple[ExecutionQueueItem, list[WorkerAuditEvent]]:
        started_at = time.monotonic()
        events: list[WorkerAuditEvent] = []
        root = self._workspace_resolver(job.workspace_root)
        assigned = self.agent.store.update_execution_job(
            job.id,
            status="running",
            assigned_worker_id=worker.worker_id,
            attempts=job.attempts + 1,
        )
        self.agent.store.heartbeat_runtime_worker(worker.worker_id, status="busy", current_jobs=worker.current_jobs + 1)
        start_event = self.record_audit(
            self.distributed_runtime.audit_event(
                worker_id=worker.worker_id,
                job_id=job.id,
                event_type="job.started",
                detail=f"{worker.name} started {assigned.kind} job {assigned.id}.",
                metadata={"kind": assigned.kind, "workspace_root": str(root), "sandbox_profile": assigned.sandbox_profile},
            )
        )
        events.append(start_event)
        self._task_transition_or_event(
            assigned.task_id,
            "running",
            title="Distributed job started",
            detail=f"{worker.name} started {assigned.kind} job {assigned.id}.",
            payload={"job_id": assigned.id, "worker_id": worker.worker_id, "kind": assigned.kind},
        )
        if assigned.kind == "validation":
            self._task_transition_or_event(
                assigned.task_id,
                "validating",
                title="Distributed validation started",
                detail=f"{worker.name} started validation job {assigned.id}.",
                payload={"job_id": assigned.id, "worker_id": worker.worker_id},
            )

        status = "succeeded"
        summary = f"{assigned.kind.title()} job completed."
        payload: dict[str, Any] = {}
        try:
            if assigned.kind in {"validation", "build"}:
                status, summary, payload = self.run_command_job(assigned, root, allow_commands=allow_commands)
                if assigned.kind == "validation" and status == "failed" and assigned.task_id:
                    self._task_transition_or_event(
                        assigned.task_id,
                        "repairing",
                        title="Validation failed",
                        detail=summary,
                        error_summary=summary,
                        payload={"job_id": assigned.id, "validation": payload},
                    )
                    self.queue_repair_after_validation_failure(assigned, root, summary)
            elif assigned.kind == "indexing":
                intelligence = self._project_intelligence_builder(root)
                summary = f"Project Intelligence indexed {len(intelligence.file_importance)} important file(s)."
                payload = {
                    "last_indexed_at": intelligence.profile.last_indexed_at,
                    "important_files": [item.path for item in intelligence.file_importance[:12]],
                }
            elif assigned.kind == "telemetry":
                snapshot = self.agent.store.refresh_telemetry_snapshot(project_root=root)
                summary = "Telemetry snapshot refreshed."
                payload = {
                    "model_attempt_count": snapshot.route_quality.overview.model_attempt_count,
                    "feedback_count": snapshot.feedback.summary.feedback_count,
                    "reliability_score": snapshot.route_quality.overview.reliability_score,
                }
            elif assigned.kind == "benchmark":
                snapshot = self.model_benchmarks.snapshot()
                summary = "Benchmark state inspected without starting a model benchmark run."
                best_model_name = snapshot.provider_scores[0].model_name if snapshot.provider_scores else ""
                payload = {"best_model_name": best_model_name, "provider_count": len(snapshot.provider_scores)}
            elif assigned.kind == "sync":
                manifest = self.save_remote_sync_manifest(
                    root,
                    RemoteWorkspaceSyncRequest(workspace_root=str(root), sections=[], encrypted=True),
                )
                summary = f"Workspace sync manifest {manifest.id} was created."
                payload = manifest.model_dump(mode="json")
            elif assigned.kind == "repair":
                status = "blocked"
                summary = "Repair jobs are recorded and require the task runtime to make code changes with normal approval and checkpoint rules."
                payload = {"source_validation_job_id": assigned.payload.get("source_validation_job_id", "")}
            else:
                summary = "Task job recorded by distributed runtime; no file changes were applied by the queue worker."
                payload = {"local_first": True, "file_changes_applied": False}
        except Exception as exc:
            status = "failed"
            summary = f"{type(exc).__name__}: {exc}"
            payload = {"exception": type(exc).__name__}

        final = self.agent.store.update_execution_job(
            assigned.id,
            status=status,
            error_summary=summary if status in {"failed", "blocked"} else "",
            result_summary=summary if status == "succeeded" else "",
        )
        self.agent.store.complete_execution_job_for_worker(
            worker.worker_id,
            failed=status != "succeeded",
            latency_ms=(time.monotonic() - started_at) * 1000,
        )
        finish_event = self.record_audit(
            self.distributed_runtime.audit_event(
                worker_id=worker.worker_id,
                job_id=assigned.id,
                event_type="job.finished",
                status="ok" if status == "succeeded" else "error" if status == "failed" else "warning",
                detail=summary,
                metadata={"status": status, "payload": payload},
            )
        )
        events.append(finish_event)
        if final.task_id and not (final.kind == "validation" and status == "failed"):
            next_task_status = "completed" if status == "succeeded" else "failed" if status == "failed" else "blocked"
            self._task_transition_or_event(
                final.task_id,
                next_task_status,
                title="Distributed job finished",
                detail=summary,
                error_summary=summary if next_task_status in {"failed", "blocked"} else "",
                final_summary=summary if next_task_status == "completed" else "",
                payload={"job_id": final.id, "worker_id": worker.worker_id, "status": status, "result": payload},
            )
        return final, events

    async def list_runtime_workers(self, workspace_root: str | None = None) -> list[WorkerRuntimeInfo]:
        root = self._workspace_resolver(workspace_root)
        return self.workers(root)

    async def register_runtime_worker(self, request: WorkerRegistrationRequest) -> WorkerRuntimeInfo:
        worker = self.distributed_runtime.register_worker(request)
        self.agent.store.upsert_runtime_worker(worker)
        self.record_audit(
            self.distributed_runtime.audit_event(
                worker_id=worker.worker_id,
                event_type="worker.registered",
                status="ok" if worker.trust_state == "trusted" else "warning",
                detail=f"Worker {worker.name} registered as {worker.trust_state}.",
                metadata={
                    "kind": worker.kind,
                    "trust_scope": worker.trust_scope,
                    "permission_scopes": worker.permission_scopes,
                    "encrypted_transport_required": worker.metadata.get("encrypted_transport_required", False),
                },
            )
        )
        return worker

    async def heartbeat_runtime_worker(self, worker_id: str, request: WorkerHeartbeatRequest) -> WorkerRuntimeInfo:
        capabilities_json = json.dumps(request.capabilities.model_dump(mode="json"), ensure_ascii=True) if request.capabilities else None
        try:
            worker = self.agent.store.heartbeat_runtime_worker(
                worker_id,
                status=request.status,
                current_jobs=request.current_jobs,
                capabilities_json=capabilities_json,
                metadata=request.metadata,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="worker not found") from exc
        self.record_audit(
            self.distributed_runtime.audit_event(
                worker_id=worker.worker_id,
                event_type="worker.heartbeat",
                detail=f"Worker {worker.name} reported {worker.status}.",
                metadata={"current_jobs": worker.current_jobs},
            )
        )
        return worker

    async def revoke_runtime_worker(self, worker_id: str, request: WorkerActionRequest | None = None) -> WorkerRuntimeInfo:
        try:
            current = self.agent.store.runtime_worker(worker_id)
            if current.kind == "local":
                raise HTTPException(status_code=400, detail="the local runtime worker cannot be revoked")
            worker = self.agent.store.revoke_runtime_worker(worker_id, reason=(request.reason if request else ""))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="worker not found") from exc
        self.record_audit(
            self.distributed_runtime.audit_event(
                worker_id=worker.worker_id,
                event_type="worker.revoked",
                status="warning",
                detail=f"Worker {worker.name} trust was revoked.",
                metadata={"reason": request.reason if request else ""},
            )
        )
        return worker

    async def list_execution_queue(
        self,
        workspace_root: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ExecutionQueueItem]:
        root = self._workspace_resolver(workspace_root)
        self.workers(root)
        return self.jobs(root, status=status, limit=limit)

    async def create_execution_queue_item(self, request: ExecutionQueueCreateRequest) -> ExecutionQueueItem:
        root = self._workspace_resolver(request.workspace_root)
        self.workers(root)
        item = self.distributed_runtime.create_queue_item(request, root)
        created = self.agent.store.create_execution_job(item)
        self.record_audit(
            self.distributed_runtime.audit_event(
                job_id=created.id,
                event_type="queue.created",
                detail=f"{created.kind.title()} job {created.id} queued.",
                metadata={"workspace_root": str(root), "task_id": created.task_id, "permission_scope": created.permission_scope},
            )
        )
        return created

    async def read_execution_queue_item(self, job_id: str) -> ExecutionQueueItem:
        try:
            return self.agent.store.execution_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="execution job not found") from exc

    async def cancel_execution_queue_item(
        self,
        job_id: str,
        request: ExecutionQueueActionRequest | None = None,
    ) -> ExecutionQueueItem:
        try:
            job = self.agent.store.cancel_execution_job(job_id, reason=(request.reason if request else ""))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="execution job not found") from exc
        self.record_audit(
            self.distributed_runtime.audit_event(
                job_id=job.id,
                event_type="queue.canceled",
                status="warning",
                detail=request.reason if request and request.reason else "Execution job was canceled.",
                metadata={"task_id": job.task_id},
            )
        )
        if job.task_id:
            self._task_transition_or_event(
                job.task_id,
                "canceled",
                title="Distributed job canceled",
                detail=job.error_summary or "Execution job was canceled.",
            )
        return job

    async def retry_execution_queue_item(
        self,
        job_id: str,
        request: ExecutionQueueActionRequest | None = None,
    ) -> ExecutionQueueItem:
        try:
            job = self.agent.store.retry_execution_job(job_id, reason=(request.reason if request else ""))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="execution job not found") from exc
        self.record_audit(
            self.distributed_runtime.audit_event(
                job_id=job.id,
                event_type="queue.retry",
                detail=request.reason if request and request.reason else "Execution job was queued for retry.",
                metadata={"task_id": job.task_id, "attempts": job.attempts},
            )
        )
        if job.task_id:
            self._task_transition_or_event(
                job.task_id,
                "queued",
                title="Distributed job retry queued",
                detail=job.error_summary or "Execution job was queued for retry.",
            )
        return job

    async def dispatch_execution_queue(self, request: ExecutionDispatchRequest) -> ExecutionDispatchResponse:
        root = self._workspace_resolver(request.workspace_root)
        workers = self.workers(root)
        jobs = self.jobs(root, limit=300)
        runnable = self.distributed_runtime.select_runnable_jobs(jobs, limit=request.limit)
        events: list[WorkerAuditEvent] = []
        dispatched: list[ExecutionQueueItem] = []
        warnings: list[str] = []
        if not runnable:
            warnings.append("No queued execution jobs are runnable yet.")

        for job in runnable:
            worker = self.distributed_runtime.select_worker(
                workers,
                job,
                requested_worker_id=request.worker_id,
                allow_remote=request.allow_remote,
            )
            if worker is None:
                warnings.append(f"No eligible worker is available for job {job.id}.")
                continue
            if worker.kind in {"lan", "remote"}:
                assigned = self.agent.store.update_execution_job(
                    job.id,
                    status="assigned",
                    assigned_worker_id=worker.worker_id,
                    attempts=job.attempts + 1,
                )
                self.agent.store.heartbeat_runtime_worker(worker.worker_id, status="busy", current_jobs=worker.current_jobs + 1)
                event = self.record_audit(
                    self.distributed_runtime.audit_event(
                        worker_id=worker.worker_id,
                        job_id=job.id,
                        event_type="job.assigned.remote",
                        detail=f"Job {job.id} was assigned to remote worker {worker.name}.",
                        metadata={"allow_remote": request.allow_remote, "endpoint": worker.endpoint},
                    )
                )
                events.append(event)
                dispatched.append(assigned)
                if assigned.task_id:
                    self._task_transition_or_event(
                        assigned.task_id,
                        "running",
                        title="Remote worker assigned",
                        detail=f"Job {assigned.id} was assigned to {worker.name}.",
                        payload={"worker_id": worker.worker_id, "job_id": assigned.id},
                    )
                continue
            result, job_events = self.execute_job(job, worker, allow_commands=request.allow_commands)
            events.extend(job_events)
            dispatched.append(result)
            workers = self.workers(root)

        return ExecutionDispatchResponse(jobs=dispatched, workers=self.workers(root), events=events, warnings=warnings)

    async def route_distributed_model(self, request: HybridRouteRequest) -> HybridRouteDecision:
        root = self._workspace_resolver(request.workspace_root)
        decision = self.distributed_runtime.route_models(
            request,
            workers=self.workers(root),
            registry=self.model_registry.snapshot(),
        )
        self.record_audit(
            self.distributed_runtime.audit_event(
                event_type="model.route.selected",
                status="ok" if decision.selected else "warning",
                detail=decision.summary,
                metadata={"fallback_order": decision.fallback_order, "privacy_mode": decision.privacy_mode},
            )
        )
        return decision

    async def distributed_runtime_audit(
        self,
        worker_id: str = "",
        job_id: str = "",
        limit: int = 100,
    ) -> list[WorkerAuditEvent]:
        return self.audit_events(worker_id=worker_id, job_id=job_id, limit=limit)

    async def list_remote_sync_manifests(
        self,
        workspace_root: str | None = None,
        limit: int = 20,
    ) -> list[RemoteWorkspaceSyncManifest]:
        root = self._workspace_resolver(workspace_root)
        return self.agent.store.workspace_sync_manifests(project_root=root, limit=limit)

    async def create_remote_sync_manifest(self, request: RemoteWorkspaceSyncRequest) -> RemoteWorkspaceSyncManifest:
        root = self._workspace_resolver(request.workspace_root)
        return self.save_remote_sync_manifest(root, request)
