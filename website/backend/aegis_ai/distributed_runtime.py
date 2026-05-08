from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import (
    DistributedRuntimeSnapshot,
    ExecutionQueueCreateRequest,
    ExecutionQueueItem,
    HybridRouteCandidate,
    HybridRouteDecision,
    HybridRouteRequest,
    ModelRegistryResponse,
    RemoteWorkspaceSyncManifest,
    RuntimeObservabilitySnapshot,
    WorkerAuditEvent,
    WorkerCapabilitySet,
    WorkerRegistrationRequest,
    WorkerRuntimeInfo,
)
from .settings import Settings
from .storage import EventStore, utc_now


LOCAL_WORKER_ID = "local-runtime"


class DistributedRuntimeManager:
    """Local-first worker, queue, routing, sync, and observability policy."""

    SDK_COMMANDS: dict[str, tuple[str, ...]] = {
        "python": ("python", "py"),
        "node": ("node",),
        "typescript": ("tsc",),
        "rust": ("cargo", "rustc"),
        "go": ("go",),
        "dotnet": ("dotnet",),
        "cpp": ("cmake", "ctest", "msbuild"),
        "java": ("java", "javac", "mvn", "gradle"),
    }
    BUILD_TOOLS = ("npm", "npx", "pnpm", "yarn", "bun", "pytest", "ruff", "mypy", "vite", "cmake", "ctest", "cargo", "go", "dotnet", "mvn", "gradle")
    JOB_KINDS = ("task", "validation", "build", "indexing", "repair", "benchmark", "telemetry", "sync")

    def __init__(self, settings: Settings):
        self.settings = settings

    def local_worker(self, project_root: Path) -> WorkerRuntimeInfo:
        capabilities = self.local_capabilities()
        now = utc_now()
        return WorkerRuntimeInfo(
            worker_id=LOCAL_WORKER_ID,
            name=f"Local runtime ({platform.node() or 'desktop'})",
            kind="local",
            endpoint=str(project_root.resolve()),
            status="available",
            trust_state="trusted",
            trust_scope="local",
            registered_at=now,
            last_heartbeat_at=now,
            capabilities=capabilities,
            public_key_fingerprint="local",
            permission_scopes=["read", "task", "validation", "build", "indexing", "repair", "benchmark", "telemetry", "sync"],
            isolation_level="process",
            metadata={
                "platform": platform.platform(),
                "python": platform.python_version(),
                "local_first": True,
            },
        )

    def local_capabilities(self) -> WorkerCapabilitySet:
        installed_sdks: list[str] = []
        for language, commands in self.SDK_COMMANDS.items():
            if any(shutil.which(command) for command in commands):
                installed_sdks.append(language)

        build_tools = [tool for tool in self.BUILD_TOOLS if shutil.which(tool)]
        active_model = self.settings.aegis_model_name.strip()
        models = [active_model] if active_model else []
        gpu_available = shutil.which("nvidia-smi") is not None
        return WorkerCapabilitySet(
            installed_sdks=sorted(set(installed_sdks)),
            build_tools=sorted(set(build_tools)),
            supported_languages=sorted(set(installed_sdks)),
            available_models=models,
            gpu_available=gpu_available,
            ram_gb=self._ram_gb_hint(),
            cpu_cores=os.cpu_count() or 1,
            validation_support=bool(build_tools),
            sandbox_profiles=["restricted", "safe", "standard", "permissive"],
            supported_job_kinds=list(self.JOB_KINDS),
            supports_remote_sync=True,
            max_parallel_jobs=1,
        )

    def register_worker(self, request: WorkerRegistrationRequest) -> WorkerRuntimeInfo:
        worker_id = request.worker_id.strip() or f"worker-{uuid4().hex[:12]}"
        name = request.name.strip() or worker_id
        public_key = request.public_key.strip()
        signature_ok = request.kind == "local" or self.verify_registration_signature(
            worker_id=worker_id,
            name=name,
            trust_scope=request.trust_scope,
            public_key=public_key,
            signature=request.registration_signature,
        )
        trust_state = "trusted" if signature_ok else "untrusted"
        return WorkerRuntimeInfo(
            worker_id=worker_id,
            name=name,
            kind=request.kind,
            endpoint=request.endpoint.strip(),
            status="available" if trust_state == "trusted" else "untrusted",
            trust_state=trust_state,
            trust_scope=request.trust_scope.strip() or "local",
            registered_at=utc_now(),
            last_heartbeat_at=utc_now(),
            capabilities=request.capabilities,
            public_key_fingerprint=self.public_key_fingerprint(public_key),
            permission_scopes=sorted(set(request.permission_scopes or ["read"])),
            isolation_level=request.isolation_level,
            metadata={
                **request.metadata,
                "signature_verified": signature_ok,
                "encrypted_transport_required": request.kind in {"lan", "remote"},
            },
        )

    def registration_signature(self, *, worker_id: str, name: str, trust_scope: str, public_key: str) -> str:
        raw = f"{worker_id.strip()}|{name.strip()}|{trust_scope.strip()}|{public_key.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_registration_signature(self, *, worker_id: str, name: str, trust_scope: str, public_key: str, signature: str) -> bool:
        if not public_key.strip() or not signature.strip():
            return False
        return self.registration_signature(
            worker_id=worker_id,
            name=name,
            trust_scope=trust_scope,
            public_key=public_key,
        ) == signature.strip().lower()

    def public_key_fingerprint(self, public_key: str) -> str:
        if not public_key.strip():
            return ""
        return hashlib.sha256(public_key.encode("utf-8")).hexdigest()[:24]

    def create_queue_item(self, request: ExecutionQueueCreateRequest, workspace_root: Path) -> ExecutionQueueItem:
        now = utc_now()
        title = request.title.strip() or f"{request.kind.title()} job"
        return ExecutionQueueItem(
            id=f"job-{uuid4().hex}",
            task_id=request.task_id.strip(),
            workspace_root=str(workspace_root.resolve()),
            kind=request.kind,
            title=title,
            user_goal=request.user_goal.strip() or title,
            status="queued",
            priority=request.priority,
            created_at=now,
            updated_at=now,
            max_attempts=request.max_attempts,
            depends_on=sorted(set(request.depends_on)),
            required_capabilities=sorted(set(request.required_capabilities)),
            permission_scope=request.permission_scope.strip() or "read",
            sandbox_profile=request.sandbox_profile.strip() or "safe",
            payload=request.payload,
        )

    def select_runnable_jobs(
        self,
        jobs: list[ExecutionQueueItem],
        *,
        limit: int = 1,
    ) -> list[ExecutionQueueItem]:
        by_id = {job.id: job for job in jobs}

        def dependencies_succeeded(job: ExecutionQueueItem) -> bool:
            for dependency_id in job.depends_on:
                dependency = by_id.get(dependency_id)
                if dependency is None or dependency.status != "succeeded":
                    return False
            return True

        candidates = [
            job
            for job in jobs
            if job.status in {"queued", "retrying"} and job.attempts < job.max_attempts and dependencies_succeeded(job)
        ]
        return sorted(candidates, key=lambda item: (-item.priority, item.created_at))[:limit]

    def worker_can_run(self, worker: WorkerRuntimeInfo, job: ExecutionQueueItem, *, allow_remote: bool = False) -> bool:
        if worker.trust_state != "trusted" or worker.status in {"offline", "disabled", "untrusted", "revoked"}:
            return False
        if worker.kind in {"lan", "remote"} and not allow_remote:
            return False
        if worker.current_jobs >= worker.capabilities.max_parallel_jobs:
            return False
        if job.kind not in {str(item) for item in worker.capabilities.supported_job_kinds}:
            return False
        if job.kind == "validation" and not worker.capabilities.validation_support:
            return False
        if not self._scope_allowed(worker, job.permission_scope):
            return False
        capability_set = self._worker_capability_set(worker)
        return all(capability.lower() in capability_set for capability in job.required_capabilities)

    def select_worker(
        self,
        workers: list[WorkerRuntimeInfo],
        job: ExecutionQueueItem,
        *,
        requested_worker_id: str = "",
        allow_remote: bool = False,
    ) -> WorkerRuntimeInfo | None:
        if requested_worker_id:
            worker = next((item for item in workers if item.worker_id == requested_worker_id), None)
            return worker if worker and self.worker_can_run(worker, job, allow_remote=allow_remote) else None
        eligible = [worker for worker in workers if self.worker_can_run(worker, job, allow_remote=allow_remote)]
        eligible.sort(key=lambda item: (item.kind != "local", item.current_jobs, item.failed_jobs, item.worker_id))
        return eligible[0] if eligible else None

    def sync_manifest(self, *, workspace_root: Path, sections: list[str], encrypted: bool, payload: dict[str, object]) -> RemoteWorkspaceSyncManifest:
        included = sorted(set(sections or ["task_history", "checkpoints", "project_memory", "architecture_maps", "validation_profiles", "settings"]))
        canonical = json.dumps({"workspace_root": str(workspace_root.resolve()), "sections": included, "payload": payload}, sort_keys=True, ensure_ascii=True)
        return RemoteWorkspaceSyncManifest(
            id=f"sync-{uuid4().hex}",
            workspace_root=str(workspace_root.resolve()),
            created_at=utc_now(),
            encrypted=encrypted,
            included_sections=included,
            manifest_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            payload=payload,
        )

    def route_models(
        self,
        request: HybridRouteRequest,
        *,
        workers: list[WorkerRuntimeInfo],
        registry: ModelRegistryResponse,
    ) -> HybridRouteDecision:
        candidates: list[HybridRouteCandidate] = []
        warnings: list[str] = []
        required = {item.lower() for item in request.required_capabilities}

        for worker in workers:
            if worker.trust_state != "trusted":
                continue
            for model in worker.capabilities.available_models:
                location = "remote" if worker.kind in {"lan", "remote"} else "local"
                if request.privacy == "local_only" and location != "local":
                    continue
                candidates.append(
                    HybridRouteCandidate(
                        worker_id=worker.worker_id,
                        model=model,
                        location=location,
                        privacy_mode="local-only" if location == "local" else "remote-worker",
                        estimated_latency_ms=250 if location == "local" else 900,
                        estimated_cost_usd=0.0,
                        reasoning_fit=self._reasoning_fit(model, request.reasoning_difficulty),
                        reason=f"{worker.name} advertises {model}.",
                    )
                )

        for provider in registry.providers:
            if not provider.enabled or (not provider.local and not provider.configured):
                continue
            provider_caps = {item.lower() for item in provider.capabilities}
            if required and not required.issubset(provider_caps):
                continue
            location = "local" if provider.local else "cloud"
            if request.privacy == "local_only" and location != "local":
                continue
            if request.workspace_sensitivity == "high" and location == "cloud" and request.privacy != "cloud_allowed":
                continue
            cost = (provider.input_cost_per_million or 0.0) + (provider.output_cost_per_million or 0.0)
            candidates.append(
                HybridRouteCandidate(
                    provider_id=provider.id,
                    model=provider.model_name or registry.active_model,
                    location=location,
                    privacy_mode="local-first" if provider.local else "cloud-allowed",
                    estimated_latency_ms=350 if provider.local else 1200,
                    estimated_cost_usd=round(cost * max(1, request.context_tokens) / 1_000_000, 6),
                    reasoning_fit=self._reasoning_fit(provider.model_name or provider.label, request.reasoning_difficulty),
                    reason=f"{provider.label} is {'local' if provider.local else 'configured cloud'} provider.",
                )
            )

        if not candidates:
            warnings.append("No eligible model route matched the privacy and capability constraints.")
            return HybridRouteDecision(
                selected=None,
                candidates=[],
                fallback_order=[],
                privacy_mode=request.privacy,
                summary="No route selected.",
                warnings=warnings,
            )

        selected = sorted(candidates, key=lambda item: self._route_score(item, request), reverse=True)[0]
        candidates = [item.model_copy(update={"selected": item == selected}) for item in candidates]
        fallback_order = [item.provider_id or item.worker_id for item in sorted(candidates, key=lambda item: self._route_score(item, request), reverse=True)]
        return HybridRouteDecision(
            selected=selected.model_copy(update={"selected": True}),
            candidates=candidates,
            fallback_order=fallback_order,
            privacy_mode=selected.privacy_mode,
            summary=f"Selected {selected.model or selected.provider_id or selected.worker_id} for {request.task_role}.",
            warnings=warnings,
        )

    def observability(
        self,
        *,
        workers: list[WorkerRuntimeInfo],
        jobs: list[ExecutionQueueItem],
        audit_events: list[WorkerAuditEvent],
    ) -> RuntimeObservabilitySnapshot:
        status_counts = self._job_status_counts(jobs)
        terminal = [job for job in jobs if job.status in {"succeeded", "failed"}]
        validation_jobs = [job for job in terminal if job.kind in {"validation", "build"}]
        validation_success_rate = (
            len([job for job in validation_jobs if job.status == "succeeded"]) / len(validation_jobs)
            if validation_jobs
            else 0.0
        )
        return RuntimeObservabilitySnapshot(
            generated_at=utc_now(),
            workers_total=len(workers),
            workers_available=len([worker for worker in workers if worker.status == "available"]),
            workers_busy=len([worker for worker in workers if worker.status == "busy"]),
            workers_offline=len([worker for worker in workers if worker.status == "offline"]),
            workers_untrusted=len([worker for worker in workers if worker.trust_state != "trusted"]),
            queued_jobs=status_counts.get("queued", 0) + status_counts.get("retrying", 0),
            running_jobs=status_counts.get("running", 0) + status_counts.get("assigned", 0),
            failed_jobs=status_counts.get("failed", 0) + status_counts.get("blocked", 0),
            succeeded_jobs=status_counts.get("succeeded", 0),
            task_throughput={kind: len([job for job in jobs if job.kind == kind and job.status == "succeeded"]) for kind in self.JOB_KINDS},
            token_usage={},
            model_latency_ms={worker.worker_id: worker.average_latency_ms for worker in workers if worker.average_latency_ms},
            validation_success_rate=round(validation_success_rate, 3),
            repair_loop_statistics={
                "repair_jobs": len([job for job in jobs if job.kind == "repair"]),
                "audit_events": len(audit_events),
            },
            queue_latency_ms=self._queue_latency_ms(jobs),
        )

    def snapshot(
        self,
        *,
        workers: list[WorkerRuntimeInfo],
        jobs: list[ExecutionQueueItem],
        audit_events: list[WorkerAuditEvent],
        sync_manifests: list[RemoteWorkspaceSyncManifest],
        routing: HybridRouteDecision | None = None,
    ) -> DistributedRuntimeSnapshot:
        remote = any(worker.kind in {"lan", "remote"} and worker.status != "revoked" for worker in workers)
        sandbox = any(worker.kind == "sandbox" for worker in workers)
        execution_mode = "hybrid" if remote else "sandbox" if sandbox else "local"
        security_summary = [
            "Local-first execution remains available without network connectivity.",
            "Remote/LAN workers require trusted registration before dispatch.",
            "Command-backed jobs require explicit command permission at dispatch time.",
            "All worker registration, queue, dispatch, sync, and trust changes are audit logged.",
        ]
        return DistributedRuntimeSnapshot(
            generated_at=utc_now(),
            execution_mode=execution_mode,
            workers=workers,
            queue=jobs,
            observability=self.observability(workers=workers, jobs=jobs, audit_events=audit_events),
            audit_events=audit_events,
            routing=routing,
            sync_manifests=sync_manifests,
            security_summary=security_summary,
        )

    def audit_event(self, *, worker_id: str = "", job_id: str = "", event_type: str, status: str = "ok", detail: str = "", metadata: dict[str, object] | None = None) -> WorkerAuditEvent:
        return WorkerAuditEvent(
            id=f"audit-{uuid4().hex}",
            created_at=utc_now(),
            worker_id=worker_id,
            job_id=job_id,
            event_type=event_type,
            status=status,
            detail=detail,
            metadata=dict(metadata or {}),
        )

    def ensure_local_worker(self, store: EventStore, project_root: Path) -> WorkerRuntimeInfo:
        workers = store.runtime_workers(include_revoked=True)
        existing = next((worker for worker in workers if worker.worker_id == LOCAL_WORKER_ID), None)
        local = self.local_worker(project_root)
        if existing:
            local = local.model_copy(
                update={
                    "registered_at": existing.registered_at or local.registered_at,
                    "total_jobs": existing.total_jobs,
                    "failed_jobs": existing.failed_jobs,
                    "average_latency_ms": existing.average_latency_ms,
                }
            )
        store.upsert_runtime_worker(local)
        return local

    def _scope_allowed(self, worker: WorkerRuntimeInfo, permission_scope: str) -> bool:
        scope = (permission_scope or "read").strip().lower()
        worker_scopes = {item.lower() for item in worker.permission_scopes}
        return "admin" in worker_scopes or scope in worker_scopes or (scope == "read" and worker_scopes)

    def _worker_capability_set(self, worker: WorkerRuntimeInfo) -> set[str]:
        capabilities = worker.capabilities
        values = [
            *capabilities.installed_sdks,
            *capabilities.build_tools,
            *capabilities.supported_languages,
            *capabilities.available_models,
            *[str(item) for item in capabilities.supported_job_kinds],
        ]
        return {item.lower() for item in values}

    def _reasoning_fit(self, model: str, difficulty: str) -> float:
        text = model.lower()
        base = 0.55
        if any(marker in text for marker in ("reason", "gpt-5", "opus", "sonnet", "qwen", "coder")):
            base += 0.2
        if difficulty in {"high", "xhigh"}:
            base += 0.1 if any(marker in text for marker in ("reason", "gpt-5", "opus", "sonnet")) else -0.05
        if difficulty == "low":
            base += 0.05
        return max(0.0, min(1.0, base))

    def _route_score(self, candidate: HybridRouteCandidate, request: HybridRouteRequest) -> float:
        score = candidate.reasoning_fit * 100
        if request.privacy in {"local_only", "local_first"} and candidate.location == "local":
            score += 28
        if request.workspace_sensitivity == "high" and candidate.location == "cloud":
            score -= 35
        if request.latency_priority == "high":
            score -= candidate.estimated_latency_ms / 100
        if request.cost_priority == "high":
            score -= candidate.estimated_cost_usd * 100
        if candidate.location == "cloud" and request.privacy == "cloud_allowed":
            score += 8
        return score

    def _job_status_counts(self, jobs: list[ExecutionQueueItem]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
        return counts

    def _queue_latency_ms(self, jobs: list[ExecutionQueueItem]) -> float:
        latencies: list[float] = []
        for job in jobs:
            if job.status not in {"succeeded", "failed", "blocked"}:
                continue
            try:
                created = datetime.fromisoformat(job.created_at)
                updated = datetime.fromisoformat(job.updated_at or job.created_at)
            except ValueError:
                continue
            latencies.append(max(0.0, (updated - created).total_seconds() * 1000))
        if not latencies:
            return 0.0
        return round(sum(latencies) / len(latencies), 2)

    def _ram_gb_hint(self) -> float:
        if os.name != "nt":
            return 0.0
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return round(status.ullTotalPhys / (1024**3), 1)
        except Exception:
            return 0.0
