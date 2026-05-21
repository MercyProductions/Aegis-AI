from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .schemas import (
    AegisContinuitySnapshot,
    AmbientPresenceState,
    CognitiveAwarenessState,
    ContinuationHandoff,
    DigitalTwinWorkspaceModel,
    ForecastSignal,
    HardwareAccelerationProfile,
    MemoryDistillationSnapshot,
    OperatingMemoryTimeline,
    OperatingTimelineEntry,
    PersistentWorkspaceState,
    PlatformSdkCapability,
    ResearchLabEvaluation,
    SelfDiagnosticSignal,
    SimulationForecastSnapshot,
    SkillPackInfo,
    TimelineSearchRequest,
    TimelineSearchResponse,
    UnifiedContextRecord,
    UnifiedContextSnapshot,
    UniversalDataSource,
)


CONTINUITY_API_VERSION = "2026.05.07"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact(text: str, limit: int = 280) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 1)].rstrip()}..."


def _terms(text: str) -> list[str]:
    return [item for item in re.findall(r"[a-zA-Z0-9_./:-]+", text.lower()) if len(item) > 1]


class AegisContinuityEngine:
    """Derives ambient presence, timeline, forecasts, and continuity state from unified context."""

    def snapshot(self, *, workspace_root: Path, context: UnifiedContextSnapshot) -> AegisContinuitySnapshot:
        timeline = self.timeline(workspace_root=workspace_root, context=context)
        diagnostics = self._self_diagnostics(context)
        forecasts = self._forecasts(context)
        cognitive = self._cognitive(context, diagnostics)
        presence = self._presence(context, forecasts, cognitive)
        workspace_state = self._workspace_state(workspace_root, context)
        digital_twin = self._digital_twin(workspace_root, context)
        memory_distillation = self._memory_distillation(context)
        hardware = self._hardware_profile(context)
        continuation = self._continuation_handoff(
            workspace_root=workspace_root,
            context=context,
            forecasts=forecasts,
            diagnostics=diagnostics,
        )

        return AegisContinuitySnapshot(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            api_version=CONTINUITY_API_VERSION,
            presence=presence,
            timeline=timeline,
            forecasts=forecasts,
            cognitive=cognitive,
            hardware=hardware,
            workspace_state=workspace_state,
            self_diagnostics=diagnostics,
            skill_packs=self._skill_packs(),
            universal_data_sources=self._universal_data_sources(context),
            platform_sdk=self._platform_sdk(),
            digital_twin=digital_twin,
            research_lab=self._research_lab(context),
            memory_distillation=memory_distillation,
            continuation=continuation,
            recommendations=self._recommendations(presence, forecasts, diagnostics, memory_distillation),
            warnings=[],
        )

    def timeline(self, *, workspace_root: Path, context: UnifiedContextSnapshot) -> OperatingMemoryTimeline:
        entries = [self._timeline_entry(record) for record in context.timeline[:140]]
        if not entries:
            entries = [
                self._timeline_entry(record)
                for record in context.records
                if record.created_at or record.updated_at
            ][:80]
        source_counts = Counter(entry.source for entry in entries)
        return OperatingMemoryTimeline(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            entries=entries,
            source_counts=dict(source_counts),
            reconstruction_notes=[
                "Timeline is reconstructed from persisted tasks, task events, workspace events, media jobs, recommendations, and runtime jobs.",
                "Replay is descriptive today; executable replay must route back through task, approval, checkpoint, validation, and provider safety contracts.",
            ],
            replay_supported=True,
            search_supported=True,
        )

    def search_timeline(self, snapshot: AegisContinuitySnapshot, request: TimelineSearchRequest) -> TimelineSearchResponse:
        query_terms = _terms(request.query)
        kinds = {kind.lower() for kind in request.kinds}
        results: list[tuple[float, OperatingTimelineEntry]] = []
        for entry in snapshot.timeline.entries:
            if kinds and entry.kind.lower() not in kinds:
                continue
            haystack = " ".join(
                [
                    entry.kind,
                    entry.title,
                    entry.summary,
                    entry.source,
                    entry.reference,
                    entry.status,
                    " ".join(entry.related_files),
                    " ".join(entry.related_tasks),
                    " ".join(entry.related_assets),
                ]
            ).lower()
            score = entry.importance * 0.2
            if query_terms:
                hits = sum(1 for term in query_terms if term in haystack)
                if hits <= 0:
                    continue
                score += hits
            results.append((score, entry))
        results.sort(key=lambda item: item[0], reverse=True)
        return TimelineSearchResponse(
            query=request.query,
            workspace_root=snapshot.workspace_root,
            generated_at=utc_now(),
            results=[entry for _score, entry in results[: request.limit]],
            suggestions=["validation failures", "generated media", "approval events", "recent tasks"],
        )

    def _timeline_entry(self, record: UnifiedContextRecord) -> OperatingTimelineEntry:
        return OperatingTimelineEntry(
            id=f"timeline:{record.id}",
            kind=record.kind,
            title=record.title,
            summary=record.summary,
            source=record.source,
            reference=record.reference,
            occurred_at=record.created_at or record.updated_at,
            status=record.status,
            importance=record.importance,
            related_records=[record.id],
            related_files=record.related_files,
            related_tasks=record.related_tasks,
            related_assets=record.related_assets,
            replay_hint=self._replay_hint(record),
            metadata=record.metadata,
        )

    def _presence(self, context: UnifiedContextSnapshot, forecasts: SimulationForecastSnapshot, cognitive: CognitiveAwarenessState) -> AmbientPresenceState:
        active_tasks = [record for record in context.records if record.kind == "task" and record.status not in {"completed", "failed", "canceled"}]
        recommendations = [record for record in context.records if record.kind == "recommendation" and record.status != "dismissed"]
        high_risk = [signal for signal in forecasts.signals if signal.severity in {"high", "critical"}]
        workload = "overloaded" if len(active_tasks) >= 6 or cognitive.load_level == "overload_risk" else "heavy" if len(active_tasks) >= 3 else "steady" if active_tasks else "light"
        status = "attention" if high_risk else "busy" if workload in {"heavy", "overloaded"} else "focused" if active_tasks else "calm"
        intensity = "paused" if cognitive.load_level == "overload_risk" else "reduced" if workload == "heavy" else "quiet"
        focus = active_tasks[0].title if active_tasks else "Workspace continuity"

        suggestions = []
        if active_tasks:
            suggestions.append("Continue the current active task before opening another work stream.")
        if recommendations:
            suggestions.append("Review the highest-severity workspace recommendation when you have a stopping point.")
        if high_risk:
            suggestions.append("Run a dry-run simulation before taking risky architecture or dependency work.")
        if not suggestions:
            suggestions.append("Use global command preview to route the next request through the right subsystem.")

        return AmbientPresenceState(
            status=status,
            active_focus=focus,
            workload_level=workload,
            suggestion_intensity=intensity,
            notification_style="urgent_only" if workload == "overloaded" else "subtle",
            continuity_summary=f"{len(context.records)} context record(s), {len(context.relationships)} relationship(s), {len(active_tasks)} active task(s).",
            proactive_suggestions=suggestions[:4],
            active_signals=[
                f"{len(active_tasks)} active task(s)",
                f"{len(recommendations)} active recommendation(s)",
                f"{len(high_risk)} high-risk forecast(s)",
            ],
            session_handoff=context.recommended_focus[:4],
        )

    def _forecasts(self, context: UnifiedContextSnapshot) -> SimulationForecastSnapshot:
        records = context.records
        task_failures = [record for record in records if record.kind == "task" and record.status in {"failed", "canceled"}]
        validation_events = [record for record in records if "validation" in record.tags or "validation" in record.title.lower()]
        recommendations = [record for record in records if record.kind == "recommendation"]
        high_recommendations = [record for record in recommendations if "high" in record.tags or "critical" in record.tags]
        runtime_failures = [record for record in records if record.kind == "runtime" and record.status in {"failed", "blocked"}]
        important_files = [record for record in records if record.kind == "file" and record.importance >= 0.75]
        memory_records = [record for record in records if record.kind in {"memory", "fix_memory"}]
        signals: list[ForecastSignal] = []

        if high_recommendations or len(important_files) >= 12:
            signals.append(
                ForecastSignal(
                    id="architecture-risk",
                    kind="architecture_risk",
                    severity="high" if high_recommendations else "medium",
                    score=min(1.0, 0.35 + 0.08 * len(high_recommendations) + 0.02 * len(important_files)),
                    title="Architecture Change Risk",
                    summary="Important files or high-severity recommendations suggest architecture-sensitive work should be simulated first.",
                    evidence=[record.title for record in high_recommendations[:4]] + [record.title for record in important_files[:4]],
                    projected_impact="Higher chance of broad edits, validation failures, or inconsistent module boundaries.",
                    recommended_action="Use dry-run planning and approval gates before large refactors.",
                    confidence=0.72,
                )
            )

        if validation_events or task_failures:
            signals.append(
                ForecastSignal(
                    id="validation-failure",
                    kind="validation_failure",
                    severity="medium" if len(task_failures) < 3 else "high",
                    score=min(1.0, 0.25 + 0.1 * len(task_failures) + 0.03 * len(validation_events)),
                    title="Validation Failure Prediction",
                    summary="Recent failures or validation-related events increase the chance that the next code task will need repair.",
                    evidence=[record.title for record in (task_failures + validation_events)[:6]],
                    projected_impact="Possible repair loop or extra verification cycle.",
                    recommended_action="Attach known validation commands and fix-memory context before edits.",
                    confidence=0.7,
                )
            )

        if runtime_failures:
            signals.append(
                ForecastSignal(
                    id="runtime-stability",
                    kind="runtime_stability",
                    severity="medium",
                    score=min(1.0, 0.3 + 0.1 * len(runtime_failures)),
                    title="Runtime Stability Watch",
                    summary="Blocked or failed runtime jobs may slow automation, validation, or distributed execution.",
                    evidence=[record.title for record in runtime_failures[:5]],
                    projected_impact="Queue throughput or validation latency may degrade.",
                    recommended_action="Resolve blocked queue jobs before dispatching more work.",
                    confidence=0.66,
                )
            )

        if len(memory_records) >= 80:
            signals.append(
                ForecastSignal(
                    id="memory-bloat",
                    kind="memory_bloat",
                    severity="medium",
                    score=min(1.0, len(memory_records) / 150),
                    title="Memory Compression Needed",
                    summary="Memory volume is growing enough to benefit from distillation.",
                    evidence=[f"{len(memory_records)} memory/fix-memory record(s)"],
                    projected_impact="Context ranking can become noisy if old low-value records are never distilled.",
                    recommended_action="Distill recurring decisions and archive low-importance memory.",
                    confidence=0.74,
                )
            )

        if not signals:
            signals.append(
                ForecastSignal(
                    id="baseline",
                    kind="technical_debt",
                    severity="info",
                    score=0.18,
                    title="Baseline Risk",
                    summary="No strong instability pattern is visible in the current unified context.",
                    evidence=["No high-severity forecast signal crossed the threshold."],
                    projected_impact="Normal validation and review should be enough for focused work.",
                    recommended_action="Keep using task tracking and validation for project changes.",
                    confidence=0.58,
                )
            )

        risk_score = max((signal.score for signal in signals), default=0.0)
        return SimulationForecastSnapshot(
            generated_at=utc_now(),
            risk_score=risk_score,
            signals=signals,
            dry_run_modes=["architecture", "dependency", "validation", "migration", "workflow"],
            assumptions=[
                "Forecasting is heuristic and based on persisted local context.",
                "Forecasts are advisory; risky execution still requires approvals and existing safety workflows.",
            ],
        )

    def _cognitive(self, context: UnifiedContextSnapshot, diagnostics: list[SelfDiagnosticSignal]) -> CognitiveAwarenessState:
        active_tasks = [record for record in context.records if record.kind == "task" and record.status not in {"completed", "failed", "canceled"}]
        failures = [record for record in context.records if record.status in {"failed", "error", "critical"} or "error" in record.tags]
        repair_records = [record for record in context.records if "repair" in record.tags or "repair" in record.title.lower()]
        degraded = [item for item in diagnostics if item.status in {"degraded", "critical"}]
        patterns: list[str] = []
        if len(active_tasks) >= 5:
            patterns.append("many_active_workstreams")
        if len(failures) >= 4:
            patterns.append("repeated_failures")
        if len(repair_records) >= 3:
            patterns.append("repair_loop_risk")
        if degraded:
            patterns.append("runtime_health_watch")

        load = "overload_risk" if len(patterns) >= 3 or len(active_tasks) >= 7 else "high" if len(active_tasks) >= 4 or len(failures) >= 4 else "steady" if active_tasks else "low"
        return CognitiveAwarenessState(
            load_level=load,
            detected_patterns=patterns,
            pacing="pause_and_summarize" if load == "overload_risk" else "focus_mode" if load == "high" else "normal",
            verbosity="concise" if load in {"high", "overload_risk"} else "balanced",
            notification_intensity="urgent_only" if load in {"high", "overload_risk"} else "quiet",
            workflow_aggressiveness="conservative" if load in {"high", "overload_risk"} else "normal",
            recommendation_style="short, specific, and interruption-light" if load in {"high", "overload_risk"} else "calm, specific, and low-noise",
            safeguards=[
                "Do not infer or simulate emotions.",
                "Adapt pacing from observable workflow signals only.",
                "Prefer summaries and next-best action when repeated failures are detected.",
            ],
        )

    def _hardware_profile(self, context: UnifiedContextSnapshot) -> HardwareAccelerationProfile:
        cpu_logical = os.cpu_count() or 0
        system_records = [record for record in context.records if record.kind == "system"]
        accelerators = ["CPU"]
        gpu_available = any("gpu" in (record.title + " " + record.summary + " ".join(record.tags)).lower() for record in system_records)
        npu_available = any("npu" in (record.title + " " + record.summary + " ".join(record.tags)).lower() for record in system_records)
        if gpu_available:
            accelerators.append("GPU")
        if npu_available:
            accelerators.append("NPU")
        return HardwareAccelerationProfile(
            status="partial",
            cpu_logical=cpu_logical,
            gpu_available=gpu_available,
            npu_available=npu_available,
            accelerators=accelerators,
            local_model_optimizations=["quantized local model routing", "context budget trimming", "batch validation queues"],
            routing_notes=[
                "CPU-only local routing remains the safe baseline.",
                "GPU/NPU detection is adapter-backed and should not be assumed from OS signals alone.",
                "Distributed inference should remain opt-in and privacy-scoped.",
            ],
            power_profile="unknown",
            warnings=[] if gpu_available or npu_available else ["No GPU/NPU adapter is currently reporting acceleration capability."],
        )

    def _workspace_state(self, workspace_root: Path, context: UnifiedContextSnapshot) -> PersistentWorkspaceState:
        active_tasks = [record for record in context.records if record.kind == "task" and record.status not in {"completed", "failed", "canceled"}]
        memory = [record for record in context.records if record.kind in {"memory", "fix_memory"}]
        assets = [record for record in context.records if record.kind == "media_asset"]
        checkpoints = sum(len(record.metadata.get("checkpoints", []) or []) for record in context.records if record.kind == "task")
        sections = [
            "tasks",
            "task timeline",
            "project intelligence",
            "workspace intelligence",
            "project memory",
            "creative media library",
            "operating environment state",
            "distributed queue state",
        ]
        readiness = "ready" if memory or active_tasks or assets else "partial"
        return PersistentWorkspaceState(
            workspace_root=str(workspace_root),
            restore_readiness=readiness,
            persisted_sections=sections,
            active_task_count=len(active_tasks),
            active_workflow_count=len([record for record in context.records if record.kind in {"workflow", "automation"} and record.status not in {"completed", "dismissed"}]),
            memory_record_count=len(memory),
            media_asset_count=len(assets),
            checkpoint_references=checkpoints,
            recovery_notes=[
                "Workspace state is reconstructed from persisted SQLite records and local media files.",
                "Executable recovery still routes through task, checkpoint, validation, and rollback flows.",
            ],
        )

    def _self_diagnostics(self, context: UnifiedContextSnapshot) -> list[SelfDiagnosticSignal]:
        records = context.records
        failed_tasks = [record for record in records if record.kind == "task" and record.status == "failed"]
        repair_records = [record for record in records if "repair" in record.tags or "repair" in record.title.lower()]
        validation_records = [record for record in records if "validation" in record.tags or "validation" in record.title.lower()]
        blocked_runtime = [record for record in records if record.kind == "runtime" and record.status in {"blocked", "failed"}]
        memory_records = [record for record in records if record.kind in {"memory", "fix_memory"}]
        desktop_blocked = [record for record in records if record.id == "operating:desktop_control" and record.status == "blocked"]
        diagnostics = [
            SelfDiagnosticSignal(
                id="routing-health",
                category="routing",
                status="healthy",
                title="Routing Health",
                summary="Global command routing is deterministic and preview-first.",
                evidence=["No autonomous route mutation is performed by the convergence layer."],
                recommendation="Keep command previews visible before executing cross-module work.",
            ),
            SelfDiagnosticSignal(
                id="validation-stability",
                category="validation",
                status="watch" if failed_tasks or len(validation_records) >= 5 else "healthy",
                title="Validation Stability",
                summary=f"{len(failed_tasks)} failed task(s), {len(validation_records)} validation-related record(s).",
                evidence=[record.title for record in (failed_tasks + validation_records)[:6]],
                recommendation="Attach validation commands and fix memory to risky coding tasks.",
            ),
            SelfDiagnosticSignal(
                id="repair-loop-health",
                category="repair",
                status="watch" if len(repair_records) >= 3 else "healthy",
                title="Repair Loop Health",
                summary=f"{len(repair_records)} repair-related record(s) detected.",
                evidence=[record.title for record in repair_records[:6]],
                recommendation="Pause and summarize after repeated repair failures.",
            ),
            SelfDiagnosticSignal(
                id="runtime-queue-health",
                category="runtime",
                status="watch" if blocked_runtime else "healthy",
                title="Runtime Queue Health",
                summary=f"{len(blocked_runtime)} blocked or failed runtime job(s).",
                evidence=[record.title for record in blocked_runtime[:6]],
                recommendation="Clear blocked runtime jobs before adding background work.",
            ),
            SelfDiagnosticSignal(
                id="memory-health",
                category="memory",
                status="watch" if len(memory_records) >= 80 else "healthy",
                title="Memory Health",
                summary=f"{len(memory_records)} memory/fix-memory record(s) are available.",
                evidence=[],
                recommendation="Distill recurring memory if context starts getting noisy.",
            ),
            SelfDiagnosticSignal(
                id="desktop-safety",
                category="safety",
                status="watch" if desktop_blocked else "healthy",
                title="Desktop Safety",
                summary="Desktop control remains blocked unless a trusted adapter is approved.",
                evidence=[record.title for record in desktop_blocked],
                recommendation="Keep OS actions preview-only until a scoped adapter exists.",
            ),
        ]
        return diagnostics

    def _skill_packs(self) -> list[SkillPackInfo]:
        packs = [
            ("unreal_engine", "Unreal Engine Pack", "game-dev", ["workflows", "validators", "agents", "memory templates"]),
            ("reverse_engineering", "Reverse Engineering Pack", "security", ["analysis workflows", "sandbox policies", "UI panels"]),
            ("nursing_study", "Nursing Study Pack", "learning", ["quizzes", "flashcards", "mock exams", "voice teaching"]),
            ("nextjs", "Next.js Pack", "web", ["scaffold templates", "validators", "routing hints"]),
            ("security_analysis", "Security Analysis Pack", "security", ["validators", "workflows", "audit rules"]),
            ("crypto_analysis", "Crypto Analysis Pack", "research", ["research workflows", "risk notes", "data connectors"]),
            ("blender_workflow", "Blender Workflow Pack", "creative", ["asset workflows", "render validators", "UI panel"]),
        ]
        return [
            SkillPackInfo(
                id=pack_id,
                name=name,
                category=category,
                status="planned",
                trust_level="metadata",
                capabilities=capabilities,
                included_assets=["workflows", "prompts", "agents", "validation rules"],
                permission_scopes=["workspace_read", "task_create"],
                lifecycle=["validate", "install", "enable", "disable"],
                notes=["Skill packs are metadata until installed through the trusted ecosystem/plugin path."],
            )
            for pack_id, name, category, capabilities in packs
        ]

    def _universal_data_sources(self, context: UnifiedContextSnapshot) -> list[UniversalDataSource]:
        counts = Counter(record.source for record in context.records)
        sources = [
            ("files", "Files", "workspace", "project_intelligence", "workspace"),
            ("tasks", "Tasks And Timelines", "runtime", "task_engine", "task"),
            ("media", "Generated Media", "creative", "creative_studio", "creative"),
            ("memory", "Memory Graph", "memory", "project_memory", "memory"),
            ("automation", "Automation History", "workflow", "workspace_intelligence", "workflow"),
            ("desktop", "Desktop And System State", "desktop", "operating_environment", "desktop_control"),
            ("distributed", "Distributed Runtime", "runtime", "distributed_runtime", "worker"),
            ("research", "Research Sessions", "research", "research_engine", "network_research"),
            ("external_apps", "Local Apps And Cloud Connectors", "connector", "", "connector"),
        ]
        return [
            UniversalDataSource(
                id=source_id,
                name=name,
                category=category,
                status="partial" if source_key else "planned",
                records_indexed=counts.get(source_key, 0) if source_key else 0,
                semantic_index_ready=False,
                permission_scope=permission,
                connectors=[source_key] if source_key else [],
                notes=["Indexed through Unified Context." if source_key else "Requires an approved connector adapter."],
            )
            for source_id, name, category, source_key, permission in sources
        ]

    def _platform_sdk(self) -> list[PlatformSdkCapability]:
        return [
            PlatformSdkCapability(id="agents", name="Custom Agents", status="partial", signing_supported=False, lifecycle_hooks=["validate", "enable", "disable"], docs=["docs/PRODUCTIZATION_AND_HARDENING.md"]),
            PlatformSdkCapability(id="plugins", name="Plugins And UI Panels", status="partial", signing_supported=True, lifecycle_hooks=["install", "validate", "enable", "disable", "uninstall"], docs=["docs/PRODUCTIZATION_AND_HARDENING.md"]),
            PlatformSdkCapability(id="workflows", name="Workflow Extensions", status="partial", signing_supported=True, lifecycle_hooks=["validate", "run", "pause", "cancel"], docs=["docs/ECOSYSTEM_AND_SHARED_INTELLIGENCE.md"]),
            PlatformSdkCapability(id="skill_packs", name="Skill Packs", status="planned", signing_supported=True, lifecycle_hooks=["validate", "install", "enable", "disable"], docs=["docs/PRESENCE_AND_CONTINUITY.md"]),
            PlatformSdkCapability(id="automation_nodes", name="Automation Nodes", status="planned", signing_supported=True, lifecycle_hooks=["validate", "run", "rollback"], docs=["docs/PRESENCE_AND_CONTINUITY.md"]),
        ]

    def _digital_twin(self, workspace_root: Path, context: UnifiedContextSnapshot) -> DigitalTwinWorkspaceModel:
        counts = Counter(record.kind for record in context.records)
        source_count = len({record.source for record in context.records})
        confidence = min(0.95, 0.25 + 0.03 * source_count + 0.001 * len(context.records) + 0.001 * len(context.relationships))
        architecture_files = counts.get("architecture", 0) + counts.get("file", 0)
        return DigitalTwinWorkspaceModel(
            workspace_root=str(workspace_root),
            confidence=round(confidence, 3),
            modeled_entities=dict(counts),
            architecture_summary=f"{architecture_files} architecture/file entity(s) modeled.",
            workflow_summary=f"{counts.get('task', 0)} task(s), {counts.get('runtime', 0)} runtime job(s), {counts.get('recommendation', 0)} recommendation(s).",
            dependency_summary="Dependency model is derived from Project Intelligence and Workspace Intelligence when available.",
            preference_summary=f"{counts.get('memory', 0)} explicit memory record(s) are available for personalization.",
            recovery_uses=["resume active tasks", "reconstruct recent timeline", "restore context after restart"],
            predictive_uses=["validation risk", "architecture risk", "workflow bottleneck", "memory distillation"],
        )

    def _research_lab(self, context: UnifiedContextSnapshot) -> list[ResearchLabEvaluation]:
        return [
            ResearchLabEvaluation(id="routing_eval", name="Routing Evaluation", category="routing", status="partial", metric="route agreement and task outcome", last_result="preview-only routing available", next_run_hint="compare global command route with completed task outcomes"),
            ResearchLabEvaluation(id="repair_eval", name="Repair Evaluation", category="repair", status="partial", metric="repair success after validation failure", last_result=f"{len([r for r in context.records if 'repair' in r.tags])} repair record(s) indexed", next_run_hint="replay validation failures through repair summaries"),
            ResearchLabEvaluation(id="prompt_eval", name="Prompt Evaluation", category="prompt", status="planned", metric="accepted output and validation success", last_result="not yet scheduled", next_run_hint="run controlled prompt variants against golden workflow tasks"),
            ResearchLabEvaluation(id="latency_eval", name="Latency Analysis", category="performance", status="partial", metric="runtime queue and model latency", last_result="runtime records indexed through unified context", next_run_hint="sample queue completion times"),
            ResearchLabEvaluation(id="context_efficiency", name="Context Efficiency Analysis", category="context", status="partial", metric="useful record ratio", last_result=f"{len(context.records)} context record(s), {len(context.relationships)} relationship(s)", next_run_hint="measure which records appear in successful tasks"),
        ]

    def _memory_distillation(self, context: UnifiedContextSnapshot) -> MemoryDistillationSnapshot:
        memory_records = [record for record in context.records if record.kind in {"memory", "fix_memory"}]
        themes = Counter(tag for record in memory_records for tag in record.tags if tag and tag not in {"memory", "fix-memory", "repair"})
        low_importance = [record.title for record in memory_records if record.importance < 0.45]
        return MemoryDistillationSnapshot(
            generated_at=utc_now(),
            raw_memory_records=len(memory_records),
            distilled_themes=[f"{theme}: {count}" for theme, count in themes.most_common(8)],
            archive_candidates=low_importance[:12],
            compression_ratio_estimate=round(min(0.85, max(0.0, len(low_importance) / max(len(memory_records), 1))), 3),
            pruning_recommendations=(
                ["Distill repeated repair notes into one higher-confidence memory.", "Archive low-importance stale records after user review."]
                if len(memory_records) >= 40
                else ["Memory volume is still manageable; keep explicit user review before pruning."]
            ),
            continuity_preserved=True,
        )

    def _continuation_handoff(
        self,
        *,
        workspace_root: Path,
        context: UnifiedContextSnapshot,
        forecasts: SimulationForecastSnapshot,
        diagnostics: list[SelfDiagnosticSignal],
    ) -> ContinuationHandoff:
        active_tasks = [
            record
            for record in context.records
            if record.kind == "task" and record.status not in {"completed", "failed", "canceled", "dismissed"}
        ]
        failed_tasks = [record for record in context.records if record.kind == "task" and record.status == "failed"]
        recommendations = [
            record
            for record in context.records
            if record.kind == "recommendation" and record.status not in {"dismissed", "completed"}
        ]
        candidates = active_tasks or failed_tasks or recommendations
        memory_records = [record for record in context.records if record.kind in {"memory", "fix_memory"}]

        if not candidates:
            return self._baseline_continuation_handoff(workspace_root, context, memory_records)

        selected = sorted(candidates, key=self._continuation_record_score, reverse=True)[0]
        related_tasks = selected.related_tasks or ([selected.reference] if selected.kind == "task" and selected.reference else [])
        context_records = [
            record.id
            for record in context.records
            if record.id == selected.id or any(task_id in record.related_tasks for task_id in related_tasks)
        ][:16]
        validation_commands = self._validation_commands_for_continuation(selected, context_records, context)
        memory_refs = [record.reference or record.id for record in memory_records[:8]]
        blockers = self._continuation_blockers(selected, diagnostics)
        risk_level = self._continuation_risk_level(selected, forecasts, diagnostics)
        next_action = self._continuation_next_action(selected, validation_commands)
        active_goal = selected.title or selected.summary or "Workspace continuation"

        return ContinuationHandoff(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            active_goal=active_goal,
            next_action=next_action,
            source_kind=selected.kind,
            source_title=selected.title,
            source_record_id=selected.id,
            confidence=self._continuation_confidence(selected, context_records, memory_refs),
            risk_level=risk_level,
            blockers=blockers,
            related_tasks=related_tasks[:8],
            related_files=selected.related_files[:12],
            validation_commands=validation_commands[:8],
            memory_refs=memory_refs,
            context_record_ids=context_records,
            resume_prompt=self._resume_prompt(active_goal, next_action, selected, validation_commands),
            rationale=self._continuation_rationale(selected, memory_refs, context_records),
            warnings=self._continuation_warnings(risk_level, blockers),
        )

    def _baseline_continuation_handoff(
        self,
        workspace_root: Path,
        context: UnifiedContextSnapshot,
        memory_records: list[UnifiedContextRecord],
    ) -> ContinuationHandoff:
        focus = context.recommended_focus[0] if context.recommended_focus else "Review workspace state and choose the next tracked task."
        memory_refs = [record.reference or record.id for record in memory_records[:8]]
        return ContinuationHandoff(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            active_goal="Workspace continuity",
            next_action=focus,
            source_kind="workspace",
            source_title="Workspace continuity",
            source_record_id="project:active",
            confidence=0.45 if memory_refs else 0.32,
            risk_level="low",
            memory_refs=memory_refs,
            context_record_ids=["project:active"],
            resume_prompt=f"Continue from persisted workspace state. Next action: {focus}",
            rationale="No active or failed task was found, so the handoff falls back to recommended focus and project memory.",
        )

    def _continuation_record_score(self, record: UnifiedContextRecord) -> tuple[float, str]:
        status_order = {
            "needs_approval": 1.0,
            "blocked": 0.95,
            "failed": 0.9,
            "running": 0.82,
            "repairing": 0.78,
            "validating": 0.76,
            "planning": 0.72,
            "queued": 0.64,
        }
        return (status_order.get(record.status, 0.55) + record.importance, record.updated_at or record.created_at)

    def _validation_commands_for_continuation(
        self,
        selected: UnifiedContextRecord,
        context_record_ids: list[str],
        context: UnifiedContextSnapshot,
    ) -> list[str]:
        commands: list[str] = []
        for record in [selected, *[item for item in context.records if item.id in set(context_record_ids)]]:
            raw = record.metadata.get("validation_commands") if isinstance(record.metadata, dict) else None
            if isinstance(raw, list):
                commands.extend(str(item) for item in raw if str(item).strip())
            if record.kind == "runtime" and "validation" in record.tags and record.reference:
                commands.append(record.reference)
        seen: set[str] = set()
        result: list[str] = []
        for command in commands:
            normalized = command.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    def _continuation_blockers(
        self,
        selected: UnifiedContextRecord,
        diagnostics: list[SelfDiagnosticSignal],
    ) -> list[str]:
        blockers: list[str] = []
        if selected.status in {"needs_approval", "blocked", "failed"}:
            blockers.append(f"{selected.title} is {selected.status.replace('_', ' ')}.")
        blockers.extend(
            diagnostic.title
            for diagnostic in diagnostics
            if diagnostic.status in {"degraded", "critical"}
        )
        return blockers[:6]

    def _continuation_risk_level(
        self,
        selected: UnifiedContextRecord,
        forecasts: SimulationForecastSnapshot,
        diagnostics: list[SelfDiagnosticSignal],
    ) -> str:
        if any(item.status == "critical" for item in diagnostics) or forecasts.risk_score >= 0.85:
            return "critical"
        if selected.status in {"blocked", "failed"} or forecasts.risk_score >= 0.65:
            return "high"
        if selected.status == "needs_approval" or any(item.status == "watch" for item in diagnostics):
            return "medium"
        return "low"

    def _continuation_next_action(self, selected: UnifiedContextRecord, validation_commands: list[str]) -> str:
        if selected.status == "needs_approval":
            return "Review the pending approval, then resume the task through the task API."
        if selected.status in {"blocked", "failed"}:
            return "Inspect the task timeline and artifacts, repair the blocker, then retry with validation."
        if selected.kind == "recommendation":
            return "Convert this workspace recommendation into a tracked task if it is still relevant."
        if validation_commands:
            return f"Continue the active task and validate with `{validation_commands[0]}` before closing it."
        return "Continue the active task, update artifacts, and record the next validation step."

    def _continuation_confidence(
        self,
        selected: UnifiedContextRecord,
        context_record_ids: list[str],
        memory_refs: list[str],
    ) -> float:
        score = 0.42 + min(0.28, selected.importance * 0.2) + min(0.18, len(context_record_ids) * 0.015) + min(0.12, len(memory_refs) * 0.015)
        return round(min(0.95, score), 3)

    def _resume_prompt(
        self,
        active_goal: str,
        next_action: str,
        selected: UnifiedContextRecord,
        validation_commands: list[str],
    ) -> str:
        files = f" Related files: {', '.join(selected.related_files[:5])}." if selected.related_files else ""
        validation = f" Validation: {validation_commands[0]}." if validation_commands else ""
        return _compact(f"Continue the persisted objective: {active_goal}. {next_action}{files}{validation}", 520)

    def _continuation_rationale(
        self,
        selected: UnifiedContextRecord,
        memory_refs: list[str],
        context_record_ids: list[str],
    ) -> str:
        return (
            f"Selected `{selected.id}` because it is the strongest persisted continuation candidate "
            f"with status `{selected.status or 'unknown'}`, {len(context_record_ids)} related context record(s), "
            f"and {len(memory_refs)} memory reference(s)."
        )

    def _continuation_warnings(self, risk_level: str, blockers: list[str]) -> list[str]:
        warnings: list[str] = []
        if risk_level in {"high", "critical"}:
            warnings.append("Use approval, checkpoint, and validation gates before mutating files.")
        if blockers:
            warnings.append("Resolve blockers before dispatching background or autonomous work.")
        return warnings

    def _recommendations(
        self,
        presence: AmbientPresenceState,
        forecasts: SimulationForecastSnapshot,
        diagnostics: list[SelfDiagnosticSignal],
        memory: MemoryDistillationSnapshot,
    ) -> list[str]:
        recommendations = [
            "Keep advanced intelligence inside the Runtime convergence surface instead of adding more dashboards.",
            "Route executable work through global command preview and the owning task/tool endpoint.",
        ]
        if presence.workload_level in {"heavy", "overloaded"}:
            recommendations.append("Reduce notification intensity and finish active work before adding more tasks.")
        if forecasts.risk_score >= 0.65:
            recommendations.append("Run a dry-run simulation before architecture, dependency, or migration work.")
        if any(item.status in {"watch", "degraded", "critical"} for item in diagnostics):
            recommendations.append("Review self-diagnostics before enabling more background automation.")
        if memory.raw_memory_records >= 40:
            recommendations.append("Distill memory themes to keep context useful and low-noise.")
        return recommendations

    def _replay_hint(self, record: UnifiedContextRecord) -> str:
        if record.kind == "task":
            return "Open the task, inspect timeline/artifacts, then retry or continue through the task API."
        if record.kind == "media_job":
            return "Open the Creative Studio job and regenerate/export through media job endpoints."
        if record.kind == "recommendation":
            return "Open the Workspace Intelligence recommendation and convert it into a tracked task if still relevant."
        if record.kind == "runtime":
            return "Inspect runtime queue/audit state before retrying or canceling."
        if record.kind == "timeline_event":
            return "Use the parent task or workspace event source for reconstruction."
        return "Use unified context search to find related tasks, files, assets, and memory before action."
