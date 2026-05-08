from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import (
    DistributedRuntimeSnapshot,
    GlobalCommandRequest,
    GlobalCommandResponse,
    GlobalCommandRoute,
    MediaAssetLibraryResponse,
    OperatingEnvironmentSnapshot,
    ProjectIntelligenceSnapshot,
    ProjectMemoryEntry,
    TaskSummary,
    ToolEvent,
    UnifiedContextRecord,
    UnifiedContextRelationship,
    UnifiedContextSearchRequest,
    UnifiedContextSearchResponse,
    UnifiedContextSearchResult,
    UnifiedContextSnapshot,
    UnifiedContextSourceSummary,
    WorkspaceOperationsSnapshot,
)


UNIFIED_CONTEXT_API_VERSION = "2026.05.07"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact(text: str, limit: int = 260) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 1)].rstrip()}..."


def _terms(text: str) -> list[str]:
    return [item for item in re.findall(r"[a-zA-Z0-9_./:-]+", text.lower()) if len(item) > 1]


class UnifiedContextEngine:
    """Converges Aegis subsystems into one local-first context graph."""

    def snapshot(
        self,
        *,
        workspace_root: Path,
        tasks: list[TaskSummary],
        task_events: dict[str, list[ToolEvent]],
        project_intelligence: ProjectIntelligenceSnapshot | None,
        project_memory: list[ProjectMemoryEntry],
        fix_memory: list[Any],
        creative_library: MediaAssetLibraryResponse | None,
        workspace_operations: WorkspaceOperationsSnapshot | None,
        operating_environment: OperatingEnvironmentSnapshot | None,
        distributed_runtime: DistributedRuntimeSnapshot | None,
    ) -> UnifiedContextSnapshot:
        records: dict[str, UnifiedContextRecord] = {}
        relationships: list[UnifiedContextRelationship] = []

        def add(record: UnifiedContextRecord) -> UnifiedContextRecord:
            existing = records.get(record.id)
            if existing is None or record.importance >= existing.importance:
                records[record.id] = record
            return records[record.id]

        def relate(source_id: str, target_id: str, kind: str, summary: str, *, strength: float = 0.5, evidence: list[str] | None = None) -> None:
            if source_id == target_id:
                return
            relationships.append(
                UnifiedContextRelationship(
                    source_id=source_id,
                    target_id=target_id,
                    kind=kind,
                    strength=strength,
                    summary=summary,
                    evidence=evidence or [],
                )
            )

        root = str(workspace_root)
        project_name = workspace_root.name or "Workspace"
        project_record = add(
            UnifiedContextRecord(
                id="project:active",
                kind="project",
                title=project_name,
                summary=f"Active local workspace at {root}.",
                source="workspace",
                reference=root,
                workspace_root=root,
                status="active",
                importance=0.96,
                tags=["workspace", "project", "local-first"],
            )
        )

        if project_intelligence is not None:
            profile = project_intelligence.profile
            summary_bits = [
                f"stack: {', '.join(profile.stack[:5])}" if profile.stack else "",
                f"frameworks: {', '.join(profile.frameworks[:5])}" if profile.frameworks else "",
                f"entry files: {', '.join(profile.main_entry_files[:4])}" if profile.main_entry_files else "",
            ]
            add(
                UnifiedContextRecord(
                    id="project:intelligence",
                    kind="project",
                    title=profile.project_name or project_name,
                    summary=_compact("; ".join(bit for bit in summary_bits if bit) or "Project Intelligence profile is available."),
                    source="project_intelligence",
                    reference=root,
                    workspace_root=root,
                    updated_at=project_intelligence.indexing.last_indexed_at,
                    status=project_intelligence.indexing.status,
                    importance=0.92,
                    tags=["project-intelligence", *profile.stack[:6], *profile.frameworks[:6]],
                )
            )
            relate(project_record.id, "project:intelligence", "describes", "Project Intelligence describes the active workspace.", strength=0.92)

            for module in project_intelligence.architecture.major_modules[:40]:
                record_id = f"architecture:{module.path or module.name}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="architecture",
                        title=module.name or module.path,
                        summary=module.summary,
                        source="project_intelligence",
                        reference=module.path,
                        workspace_root=root,
                        importance=0.74,
                        tags=["architecture", module.kind],
                        related_files=[module.path] if module.path else [],
                    )
                )
                relate(project_record.id, record_id, "contains_module", "Workspace architecture contains this module.", strength=0.76)

            for file in project_intelligence.file_importance[:80]:
                record_id = f"file:{file.path}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="file",
                        title=file.path,
                        summary=_compact("; ".join(file.reasons) or "Important project file."),
                        source="project_intelligence",
                        reference=file.path,
                        workspace_root=root,
                        importance=min(1.0, max(0.0, file.score / 100.0 if file.score > 1 else file.score)),
                        tags=["file", "important"],
                        related_files=[file.path],
                        metadata={"importance": file.model_dump(mode="json")},
                    )
                )
                relate(project_record.id, record_id, "contains_file", "Project Intelligence marked this file as important.", strength=0.7)

            for command in project_intelligence.validation_commands[:20]:
                record_id = f"validation:{command}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="runtime",
                        title=command,
                        summary="Validation command discovered for this workspace.",
                        source="project_intelligence",
                        reference=command,
                        workspace_root=root,
                        importance=0.65,
                        tags=["validation", "command"],
                    )
                )
                relate(project_record.id, record_id, "validates_with", "Workspace validation can use this command.", strength=0.68)

        for task in tasks[:100]:
            record_id = f"task:{task.id}"
            task_record = add(
                UnifiedContextRecord(
                    id=record_id,
                    kind="task",
                    title=task.title or task.user_goal or task.message,
                    summary=_compact(task.final_summary or task.error_summary or task.user_goal or task.message),
                    source="task_engine",
                    reference=task.id,
                    workspace_root=task.workspace_root or root,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    status=task.status,
                    importance=0.84 if task.status not in {"completed", "failed", "canceled"} else 0.68,
                    tags=["task", task.mode, task.status, task.assigned_agent_role],
                    related_files=task.related_files,
                    related_tasks=[task.id],
                    metadata={"checkpoints": task.checkpoints, "validation_commands": task.validation_commands},
                )
            )
            relate(project_record.id, record_id, "has_task", "Task belongs to the active workspace.", strength=0.84)
            for path in task.related_files[:20]:
                file_id = f"file:{path}"
                add(
                    UnifiedContextRecord(
                        id=file_id,
                        kind="file",
                        title=path,
                        summary="File referenced by a task.",
                        source="task_engine",
                        reference=path,
                        workspace_root=root,
                        importance=0.55,
                        tags=["file", "task-related"],
                        related_files=[path],
                        related_tasks=[task.id],
                    )
                )
                relate(record_id, file_id, "touches_file", "Task references this file.", strength=0.78)

            for event in task_events.get(task.id, [])[:12]:
                event_id = f"timeline:{task.id}:{event.created_at}:{event.kind}:{event.title}"
                add(
                    UnifiedContextRecord(
                        id=event_id,
                        kind="timeline_event",
                        title=event.title,
                        summary=_compact(event.detail),
                        source="task_timeline",
                        reference=task.id,
                        workspace_root=root,
                        created_at=event.created_at,
                        status=event.status,
                        importance=0.52 if event.status == "ok" else 0.72,
                        tags=["timeline", event.kind, event.status],
                        related_tasks=[task.id],
                        metadata=event.payload,
                    )
                )
                relate(task_record.id, event_id, "has_event", "Task timeline contains this event.", strength=0.66)

        for memory in project_memory[:80]:
            record_id = f"memory:{memory.id}"
            add(
                UnifiedContextRecord(
                    id=record_id,
                    kind="memory",
                    title=memory.title,
                    summary=_compact(memory.detail),
                    source=memory.source or "project_memory",
                    reference=memory.id,
                    workspace_root=root,
                    created_at=memory.created_at,
                    updated_at=memory.updated_at,
                    status=memory.category,
                    importance=min(1.0, max(0.2, memory.confidence)),
                    tags=["memory", memory.category, memory.source],
                )
            )
            relate(project_record.id, record_id, "remembers", "Memory is associated with this workspace.", strength=0.7)

        for item in fix_memory[:60]:
            record_id = f"fix_memory:{getattr(item, 'id', '')}"
            add(
                UnifiedContextRecord(
                    id=record_id,
                    kind="fix_memory",
                    title=getattr(item, "error_signature", "Fix memory"),
                    summary=_compact(getattr(item, "fix_summary", "")),
                    source="fix_memory",
                    reference=getattr(item, "id", ""),
                    workspace_root=root,
                    created_at=getattr(item, "created_at", ""),
                    status=getattr(item, "category", ""),
                    importance=min(1.0, max(0.3, float(getattr(item, "confidence", 0.5) or 0.5))),
                    tags=["repair", "fix-memory", getattr(item, "category", "")],
                )
            )
            relate(project_record.id, record_id, "learned_fix", "A previous repair/fix is remembered for this workspace.", strength=0.62)

        if creative_library is not None:
            for job in creative_library.jobs[:60]:
                job_id = f"media_job:{job.id}"
                add(
                    UnifiedContextRecord(
                        id=job_id,
                        kind="media_job",
                        title=f"{job.studio.title()} {job.kind}",
                        summary=_compact(job.prompt),
                        source="creative_studio",
                        reference=job.id,
                        workspace_root=root,
                        created_at=job.created_at,
                        updated_at=job.updated_at,
                        status=str(job.status),
                        importance=0.62,
                        tags=["creative", job.studio, job.kind, job.operation],
                        related_assets=[asset.id or asset.path for asset in job.assets],
                    )
                )
                relate(project_record.id, job_id, "has_media_job", "Creative job belongs to the workspace media library.", strength=0.56)
                if any(tag in str(job.kind) for tag in ["ui_mockup", "product_mockup", "logo", "icon"]):
                    relate(job_id, project_record.id, "can_feed_project", "Generated visual assets can inform coding or product tasks.", strength=0.72)
                for asset in job.assets[:20]:
                    asset_ref = asset.id or asset.path
                    asset_id = f"media_asset:{asset_ref}"
                    add(
                        UnifiedContextRecord(
                            id=asset_id,
                            kind="media_asset",
                            title=asset.role or Path(asset.path).name,
                            summary=f"{asset.kind} asset in {asset.format} format.",
                            source="creative_studio",
                            reference=asset.path,
                            workspace_root=root,
                            status=asset.format,
                            importance=0.58,
                            tags=["asset", asset.kind, asset.format, asset.role],
                            related_assets=[asset_ref],
                            metadata=asset.metadata,
                        )
                    )
                    relate(job_id, asset_id, "produced_asset", "Creative job produced this asset.", strength=0.86)

        if workspace_operations is not None:
            health_id = "workspace:health"
            add(
                UnifiedContextRecord(
                    id=health_id,
                    kind="automation",
                    title="Workspace Health",
                    summary=workspace_operations.health.status,
                    source="workspace_intelligence",
                    reference=root,
                    workspace_root=root,
                    created_at=workspace_operations.generated_at,
                    status=workspace_operations.health.status,
                    importance=0.82,
                    tags=["workspace-health", workspace_operations.health.status],
                    metadata={"score": workspace_operations.health.score, "top_risks": workspace_operations.health.top_risks},
                )
            )
            relate(project_record.id, health_id, "has_health", "Workspace Intelligence summarizes project health.", strength=0.76)

            for recommendation in workspace_operations.recommendations[:80]:
                record_id = f"recommendation:{recommendation.id}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="recommendation",
                        title=recommendation.title,
                        summary=_compact(recommendation.detail or recommendation.rationale),
                        source="workspace_intelligence",
                        reference=recommendation.id,
                        workspace_root=root,
                        created_at=recommendation.created_at,
                        updated_at=recommendation.updated_at,
                        status=recommendation.status,
                        importance={"critical": 0.92, "high": 0.82, "medium": 0.68, "low": 0.52}.get(recommendation.severity, 0.42),
                        tags=["recommendation", recommendation.severity, recommendation.category],
                        related_files=recommendation.related_files,
                        related_tasks=recommendation.related_tasks,
                    )
                )
                relate(project_record.id, record_id, "has_recommendation", "Workspace Intelligence generated this recommendation.", strength=0.68)
                for path in recommendation.related_files[:12]:
                    relate(record_id, f"file:{path}", "concerns_file", "Recommendation references this file.", strength=0.74)

            for event in workspace_operations.recent_events[:60]:
                record_id = f"workspace_event:{event.id}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="timeline_event",
                        title=event.title,
                        summary=_compact(event.detail),
                        source="workspace_watcher",
                        reference=event.path or event.id,
                        workspace_root=root,
                        created_at=event.created_at,
                        status=event.severity,
                        importance={"critical": 0.86, "high": 0.78, "medium": 0.64}.get(event.severity, 0.42),
                        tags=["workspace-event", event.kind, event.severity],
                        related_files=event.related_files or ([event.path] if event.path else []),
                    )
                )
                relate(project_record.id, record_id, "has_workspace_event", "Workspace watcher recorded this event.", strength=0.52)

        if operating_environment is not None:
            for capability in operating_environment.capabilities:
                record_id = f"operating:{capability.id}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="desktop" if capability.category in {"desktop", "vision"} else "system",
                        title=capability.name,
                        summary=_compact(capability.summary),
                        source="operating_environment",
                        reference=capability.id,
                        workspace_root=root,
                        status=capability.status,
                        importance=0.56 if capability.status == "ready" else 0.44,
                        tags=["operating-environment", capability.category, capability.permission_scope, capability.status],
                        metadata={"approval_required": capability.approval_required, "adapters": capability.adapter_ids},
                    )
                )
                relate(project_record.id, record_id, "available_capability", "Operating Environment registers this capability.", strength=0.48)

            for signal in operating_environment.system_signals:
                add(
                    UnifiedContextRecord(
                        id=f"system_signal:{signal.id}",
                        kind="system",
                        title=signal.label,
                        summary=_compact(signal.detail),
                        source="operating_environment",
                        reference=signal.id,
                        workspace_root=root,
                        updated_at=signal.updated_at,
                        status=signal.status,
                        importance=0.4,
                        tags=["system-signal", signal.category, signal.status],
                        metadata={"value": signal.value},
                    )
                )

        if distributed_runtime is not None:
            for item in distributed_runtime.queue[:80]:
                record_id = f"runtime_job:{item.id}"
                add(
                    UnifiedContextRecord(
                        id=record_id,
                        kind="runtime",
                        title=item.title,
                        summary=_compact(item.result_summary or item.error_summary or item.kind),
                        source="distributed_runtime",
                        reference=item.id,
                        workspace_root=root,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                        status=item.status,
                        importance=0.58 if item.status in {"queued", "running", "assigned"} else 0.44,
                        tags=["runtime-job", item.kind, item.status],
                        related_tasks=[item.task_id] if item.task_id else [],
                    )
                )
                if item.task_id:
                    relate(f"task:{item.task_id}", record_id, "executes_as_job", "Task is connected to a runtime queue job.", strength=0.8)

        record_list = sorted(records.values(), key=lambda item: (item.importance, item.updated_at or item.created_at), reverse=True)
        relationship_list = self._dedupe_relationships(relationships)
        timeline = sorted(
            [item for item in record_list if item.created_at and item.kind in {"task", "timeline_event", "media_job", "recommendation", "runtime"}],
            key=lambda item: item.created_at,
            reverse=True,
        )[:80]

        return UnifiedContextSnapshot(
            workspace_root=root,
            generated_at=utc_now(),
            api_version=UNIFIED_CONTEXT_API_VERSION,
            records=record_list[:500],
            relationships=relationship_list[:700],
            source_summaries=self._source_summaries(record_list),
            timeline=timeline,
            cross_module_insights=self._insights(record_list, relationship_list),
            command_entrypoints=["chat", "command_palette", "desktop_overlay", "voice", "mobile", "api"],
            recommended_focus=self._recommended_focus(record_list),
            warnings=[],
        )

    def search(self, snapshot: UnifiedContextSnapshot, request: UnifiedContextSearchRequest) -> UnifiedContextSearchResponse:
        query_terms = _terms(request.query)
        allowed_scopes = {scope.strip().lower() for scope in request.scopes if scope.strip()}
        scoped_records = [
            record
            for record in snapshot.records
            if not allowed_scopes or record.kind.lower() in allowed_scopes or record.source.lower() in allowed_scopes
        ]

        relationship_map: dict[str, list[UnifiedContextRelationship]] = defaultdict(list)
        if request.include_relationships:
            for relationship in snapshot.relationships:
                relationship_map[relationship.source_id].append(relationship)
                relationship_map[relationship.target_id].append(relationship)

        scored: list[UnifiedContextSearchResult] = []
        for record in scoped_records:
            score, matched_fields = self._score_record(record, query_terms)
            if not query_terms:
                score = record.importance
                matched_fields = ["importance"]
            if score <= 0:
                continue
            scored.append(
                UnifiedContextSearchResult(
                    record=record,
                    score=round(score, 4),
                    matched_fields=matched_fields,
                    relationships=relationship_map.get(record.id, [])[:8],
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        scope_summary = Counter(record.kind for record in scoped_records)
        return UnifiedContextSearchResponse(
            query=request.query,
            workspace_root=snapshot.workspace_root,
            generated_at=utc_now(),
            results=scored[: request.limit],
            scope_summary=dict(scope_summary),
            suggestions=self._search_suggestions(snapshot, request.query),
        )

    def preview_command(
        self,
        *,
        workspace_root: Path,
        request: GlobalCommandRequest,
        snapshot: UnifiedContextSnapshot,
    ) -> GlobalCommandResponse:
        route = self.route_command(request.command)
        context_request = UnifiedContextSearchRequest(
            workspace_root=str(workspace_root),
            query=request.command,
            limit=6,
            include_relationships=True,
        )
        context = self.search(snapshot, context_request)
        return GlobalCommandResponse(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            command=request.command,
            entrypoint=request.entrypoint,
            route=route,
            plan=self._route_plan(route),
            context_results=context.results,
            warnings=[] if request.dry_run else ["Global command execution is routed through existing task/tool endpoints."],
        )

    def route_command(self, command: str) -> GlobalCommandRoute:
        text = command.lower()
        def has(*words: str) -> bool:
            return any(word in text for word in words)

        codingish = has("code", "file", "bug", "debug", "test", "refactor", "build", "implement", "fix", "project")
        creativeish = has("image", "logo", "mockup", "icon", "video", "music", "beat", "voice", "asset", "storyboard")
        if codingish:
            return GlobalCommandRoute(
                intent="coding",
                target_system="task_engine",
                task_kind="coding",
                confidence=0.9 if creativeish else 0.88,
                creates_task=True,
                approval_required=True,
                rollback_supported=True,
                validation_required=True,
                endpoint="/api/tasks",
                reason=(
                    "The command asks for project or code work and can use related creative assets as context."
                    if creativeish
                    else "The command asks for project or code work."
                ),
                safety_notes=["File edits go through approvals, checkpoints, validation, repair, and rollback."],
            )
        if creativeish:
            paid_risk = has("paid", "cloud", "clone", "copyright", "style of", "upscale", "4k", "long video")
            return GlobalCommandRoute(
                intent="creative_generation",
                target_system="creative_studio",
                task_kind="media_generation",
                confidence=0.86,
                creates_task=True,
                approval_required=paid_risk,
                rollback_supported=True,
                validation_required=False,
                endpoint="/api/creative-studio/jobs",
                reason="The command asks for generated or edited media.",
                safety_notes=["Generated media is stored in the local asset library.", "Paid, GPU-heavy, copyright-sensitive, and voice-cloning jobs require approval."],
            )
        if has("research", "search web", "sources", "citation", "cite", "compare sources", "timeline reconstruction"):
            return GlobalCommandRoute(
                intent="research",
                target_system="research_engine",
                task_kind="research",
                confidence=0.84,
                creates_task=True,
                approval_required=True,
                rollback_supported=False,
                validation_required=True,
                endpoint="/api/tasks",
                reason="The command needs source retrieval, summarization, or citation tracking.",
                safety_notes=["Live web access is policy-gated and should preserve citations."],
            )
        if has("automate", "workflow", "schedule", "trigger", "zap", "n8n", "node-red"):
            return GlobalCommandRoute(
                intent="automation",
                target_system="automation_studio",
                task_kind="workflow",
                confidence=0.82,
                creates_task=True,
                approval_required=True,
                rollback_supported=True,
                validation_required=True,
                endpoint="/api/tasks",
                reason="The command describes a reusable workflow or automation chain.",
                safety_notes=["Automation must stay task-tracked and cannot silently run commands or write files."],
            )
        if has("desktop", "window", "screen", "screenshot", "ocr", "clipboard", "click", "type", "launch app", "open app"):
            return GlobalCommandRoute(
                intent="desktop_action",
                target_system="operating_environment",
                task_kind="desktop",
                confidence=0.86,
                creates_task=True,
                approval_required=True,
                rollback_supported=False,
                validation_required=False,
                endpoint="/api/operating-environment/actions/preview",
                reason="The command targets the operating system or screen.",
                safety_notes=["Desktop control and screen capture are preview-only until trusted adapters are installed."],
            )
        if has("cpu", "gpu", "storage", "disk", "driver", "thermal", "process", "system"):
            process_risk = has("process", "driver", "network", "trace", "debugger")
            return GlobalCommandRoute(
                intent="system_analysis",
                target_system="operating_environment",
                task_kind="system_analysis",
                confidence=0.78,
                creates_task=process_risk,
                approval_required=process_risk,
                rollback_supported=False,
                validation_required=False,
                endpoint="/api/operating-environment",
                reason="The command asks for system intelligence or diagnostics.",
                safety_notes=["Current system signals are read-only; deeper process/network diagnostics require approval."],
            )
        if has("remember", "preference", "my style", "always", "never", "memory"):
            return GlobalCommandRoute(
                intent="memory_update",
                target_system="memory",
                task_kind="memory",
                confidence=0.74,
                creates_task=False,
                approval_required=False,
                rollback_supported=True,
                validation_required=False,
                endpoint="/api/memory",
                reason="The command asks Aegis to remember a preference or fact.",
                safety_notes=["Memory should remain local, visible, and editable."],
            )
        return GlobalCommandRoute(
            intent="conversation",
            target_system="chat",
            task_kind="conversation",
            confidence=0.58,
            creates_task=False,
            approval_required=False,
            rollback_supported=False,
            validation_required=False,
            endpoint="/api/chat",
            reason="No clear project, media, research, automation, desktop, or system action was detected.",
            safety_notes=["Normal questions can remain lightweight chat."],
        )

    def _score_record(self, record: UnifiedContextRecord, query_terms: list[str]) -> tuple[float, list[str]]:
        if not query_terms:
            return record.importance, ["importance"]

        fields = {
            "title": record.title,
            "summary": record.summary,
            "source": record.source,
            "reference": record.reference,
            "status": record.status,
            "tags": " ".join(record.tags),
            "files": " ".join(record.related_files),
            "tasks": " ".join(record.related_tasks),
            "assets": " ".join(record.related_assets),
        }
        score = record.importance * 0.25
        matched: list[str] = []
        for field, value in fields.items():
            text = value.lower()
            hits = sum(1 for term in query_terms if term in text)
            if hits:
                matched.append(field)
                weight = 1.0 if field == "title" else 0.65 if field in {"summary", "tags"} else 0.35
                score += hits * weight
        return score, matched

    def _source_summaries(self, records: list[UnifiedContextRecord]) -> list[UnifiedContextSourceSummary]:
        counts = Counter(record.source for record in records)
        summaries = {
            "workspace": "Active workspace identity and root.",
            "project_intelligence": "Architecture, important files, validation, and project profile.",
            "task_engine": "Tasks, project work, approvals, and outcomes.",
            "task_timeline": "Task events, validation, repair, and approvals.",
            "project_memory": "User and project memories.",
            "fix_memory": "Known failures and repair knowledge.",
            "creative_studio": "Generated media jobs, assets, prompts, and exports.",
            "workspace_intelligence": "Health, recommendations, scheduled jobs, and watcher events.",
            "workspace_watcher": "Recent workspace change events.",
            "operating_environment": "Desktop, screen, system, and adapter capability state.",
            "distributed_runtime": "Execution queue and worker-linked jobs.",
        }
        return [
            UnifiedContextSourceSummary(
                source=source,
                records=count,
                ready=count > 0,
                summary=summaries.get(source, "Unified context source."),
            )
            for source, count in sorted(counts.items())
        ]

    def _dedupe_relationships(self, relationships: list[UnifiedContextRelationship]) -> list[UnifiedContextRelationship]:
        seen: set[tuple[str, str, str]] = set()
        result: list[UnifiedContextRelationship] = []
        for relationship in relationships:
            key = (relationship.source_id, relationship.target_id, relationship.kind)
            if key in seen:
                continue
            seen.add(key)
            result.append(relationship)
        result.sort(key=lambda item: item.strength, reverse=True)
        return result

    def _insights(self, records: list[UnifiedContextRecord], relationships: list[UnifiedContextRelationship]) -> list[str]:
        kinds = Counter(record.kind for record in records)
        sources = Counter(record.source for record in records)
        insights = [
            f"Unified context is linking {len(records)} record(s) across {len(sources)} source(s).",
            f"Task continuity includes {kinds.get('task', 0)} task record(s) and {kinds.get('timeline_event', 0)} timeline event(s).",
        ]
        if kinds.get("media_asset", 0):
            insights.append("Creative assets are visible to coding, project, and workflow planning.")
        if kinds.get("recommendation", 0):
            insights.append("Workspace recommendations can be converted into tracked task work.")
        if any(rel.kind == "can_feed_project" for rel in relationships):
            insights.append("Some generated media can feed project implementation or product workflows.")
        if kinds.get("desktop", 0):
            insights.append("Desktop and screen capabilities are represented with safety state instead of silent execution.")
        return insights

    def _recommended_focus(self, records: list[UnifiedContextRecord]) -> list[str]:
        focus: list[str] = []
        if any(record.kind == "recommendation" and record.importance >= 0.8 for record in records):
            focus.append("Review high-severity workspace recommendations before starting more work.")
        if any(record.kind == "task" and record.status not in {"completed", "failed", "canceled"} for record in records):
            focus.append("Continue active tasks before creating parallel work.")
        if not any(record.kind == "memory" for record in records):
            focus.append("Save useful project decisions so future context can improve.")
        if any(record.id == "operating:desktop_control" and record.status == "blocked" for record in records):
            focus.append("Keep desktop actions preview-only until a trusted adapter is approved.")
        return focus or ["Use unified search or the global command preview to route the next request."]

    def _search_suggestions(self, snapshot: UnifiedContextSnapshot, query: str) -> list[str]:
        if query.strip():
            return ["Search related tasks", "Search generated assets", "Search project memory"]
        kinds = Counter(record.kind for record in snapshot.records)
        suggestions = ["active tasks", "important files", "workspace recommendations"]
        if kinds.get("media_asset"):
            suggestions.append("generated assets")
        if kinds.get("memory"):
            suggestions.append("project decisions")
        return suggestions

    def _route_plan(self, route: GlobalCommandRoute) -> list[str]:
        plan = ["Classify the request through the global command router.", "Select relevant unified context records."]
        if route.creates_task:
            plan.append("Create or continue a tracked task before execution.")
        if route.approval_required:
            plan.append("Request explicit approval before risky or paid action.")
        if route.rollback_supported:
            plan.append("Create or link rollback/checkpoint artifacts before modifications.")
        if route.validation_required:
            plan.append("Attach validation or verification requirements to the task.")
        plan.append("Record outcome, telemetry, and useful memory back into unified context.")
        return plan
