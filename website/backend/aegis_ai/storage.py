from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import (
    ContextBudgetInfo,
    ContextBudgetTelemetryEntry,
    FallbackInspectorCandidate,
    FallbackInspectorResponse,
    FallbackInspectorTask,
    FeedbackAttributionRollup,
    FeedbackRecordRequest,
    FeedbackTelemetryEntry,
    FeedbackTelemetryResponse,
    FeedbackTelemetrySummary,
    FeedbackTrendBucket,
    FixMemoryEntry,
    ModelAdapterHealthInfo,
    ModelAttemptInfo,
    ModelAttemptTelemetryEntry,
    ModelRouteHealthInfo,
    ProjectMemoryEntry,
    RepairAttempt,
    RouteQualityContextRollup,
    RouteQualityContextDrilldown,
    RouteQualityOverview,
    RouteQualityProviderRollup,
    RouteQualityResponse,
    RouteQualityRoleRollup,
    RouteQualityStructuredPreviewRollup,
    RouteQualityTokenCalibrationRollup,
    RouteQualityTokenCalibrationTrendBucket,
    RoutePolicyDiffResponse,
    RoutePolicyProviderProposal,
    RoutePolicyRoleProposal,
    TaskPlanInfo,
    TaskSummary,
    TelemetrySnapshot,
    TelemetrySnapshotPruneInfo,
    ToolEvent,
)
from .settings import Settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventStore:
    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root
        self.db_path = self._resolve_db_path(settings.aegis_database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._import_legacy_db_if_needed()

    def create_task(self, *, mode: str, workspace_root: Path, message: str) -> str:
        task_id = str(uuid4())
        with self._session() as conn:
            conn.execute(
                """
                insert into tasks (id, created_at, mode, workspace_root, message, status)
                values (?, ?, ?, ?, ?, ?)
                """,
                (task_id, utc_now(), mode, str(workspace_root), message, "running"),
            )
        return task_id

    def finish_task(self, task_id: str, status: str) -> None:
        with self._session() as conn:
            conn.execute("update tasks set status = ?, finished_at = ? where id = ?", (status, utc_now(), task_id))

    def record_event(
        self,
        task_id: str,
        *,
        kind: str,
        title: str,
        status: str = "ok",
        detail: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ToolEvent:
        event = ToolEvent(
            kind=kind,
            title=title,
            status=status,
            detail=detail,
            payload=payload or {},
            created_at=utc_now(),
        )
        with self._session() as conn:
            conn.execute(
                """
                insert into events (task_id, created_at, kind, title, status, detail, payload_json)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    event.created_at,
                    event.kind,
                    event.title,
                    event.status,
                    event.detail,
                    json.dumps(event.payload, ensure_ascii=True),
                ),
            )
        return event

    def remember_fix(
        self,
        *,
        project_root: Path,
        error_signature: str,
        fix_summary: str,
        evidence: str,
        confidence: float,
        category: str = "unknown",
    ) -> None:
        with self._session() as conn:
            conn.execute(
                """
                insert into fix_memory (
                    id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    utc_now(),
                    str(project_root),
                    error_signature,
                    fix_summary,
                    evidence,
                    confidence,
                    category,
                ),
            )

    def recent_tasks(self, *, project_root: Path, limit: int = 8) -> list[TaskSummary]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, finished_at, mode, workspace_root, message, status
                from tasks
                where workspace_root in ({placeholders})
                order by created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()
        tasks: list[TaskSummary] = []
        for row in rows:
            payload = dict(row)
            payload["workspace_root"] = str(project_root.resolve())
            tasks.append(TaskSummary.model_validate(payload))
        return tasks

    def fix_history(self, *, project_root: Path, limit: int = 8) -> list[FixMemoryEntry]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category
                from fix_memory
                where project_root in ({placeholders})
                order by created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()
        history: list[FixMemoryEntry] = []
        for row in rows:
            payload = dict(row)
            payload["project_root"] = str(project_root.resolve())
            history.append(FixMemoryEntry.model_validate(payload))
        return history

    def relevant_fix_history(self, *, project_root: Path, query: str, limit: int = 3) -> list[FixMemoryEntry]:
        candidates = self.fix_history(project_root=project_root, limit=40)
        scored = [
            (self._memory_match_score(query, item.error_signature, item.fix_summary, item.category), item)
            for item in candidates
        ]
        ranked = [item for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True) if score > 0]
        return ranked[:limit]

    def remember_project_note(
        self,
        *,
        project_root: Path,
        category: str,
        title: str,
        detail: str,
        source: str,
        confidence: float,
    ) -> None:
        now = utc_now()
        normalized_root = str(project_root.resolve())
        fingerprint = self._fingerprint(category, title, detail)
        with self._session() as conn:
            conn.execute(
                """
                insert into project_memory (
                    id, created_at, updated_at, project_root, category, title, detail, source, confidence, fingerprint
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(project_root, fingerprint) do update set
                    updated_at = excluded.updated_at,
                    category = excluded.category,
                    title = excluded.title,
                    detail = excluded.detail,
                    source = excluded.source,
                    confidence = case
                        when excluded.confidence > project_memory.confidence then excluded.confidence
                        else project_memory.confidence
                    end
                """,
                (
                    str(uuid4()),
                    now,
                    now,
                    normalized_root,
                    category,
                    title,
                    detail,
                    source,
                    confidence,
                    fingerprint,
                ),
            )

    def project_memory(self, *, project_root: Path, limit: int = 8) -> list[ProjectMemoryEntry]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, updated_at, project_root, category, title, detail, source, confidence
                from project_memory
                where project_root in ({placeholders})
                order by updated_at desc, created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()

        notes: list[ProjectMemoryEntry] = []
        seen: set[str] = set()
        for row in rows:
            payload = dict(row)
            dedupe_key = self._fingerprint(payload["category"], payload["title"], payload["detail"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            payload["project_root"] = str(project_root.resolve())
            notes.append(ProjectMemoryEntry.model_validate(payload))
        return notes

    def relevant_project_memory(self, *, project_root: Path, query: str, limit: int = 4) -> list[ProjectMemoryEntry]:
        candidates = self.project_memory(project_root=project_root, limit=40)
        scored = [
            (self._memory_match_score(query, item.category, item.title, item.detail, item.source), item)
            for item in candidates
        ]
        ranked = [item for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True) if score > 0]
        return ranked[:limit]

    def record_repair_attempt(self, task_id: str, attempt: RepairAttempt) -> None:
        with self._session() as conn:
            conn.execute(
                """
                insert into repair_attempts (
                    id, task_id, created_at, attempt_number, category, before_signature,
                    after_signature, outcome, checkpoint, summary
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    task_id,
                    attempt.created_at or utc_now(),
                    attempt.attempt,
                    attempt.category,
                    attempt.before_signature,
                    attempt.after_signature,
                    attempt.outcome,
                    attempt.checkpoint,
                    attempt.summary,
                ),
            )

    def record_context_budget(
        self,
        *,
        task_id: str,
        workspace_root: Path,
        context_budget: ContextBudgetInfo,
    ) -> None:
        payload = context_budget.model_dump()
        with self._session() as conn:
            conn.execute(
                """
                insert into context_budget_telemetry (
                    id, task_id, created_at, workspace_root, intent, route_role, strategy, privacy_mode,
                    max_context_tokens, estimated_context_tokens, estimated_file_tokens, reserve_response_tokens,
                    selected_file_count, omitted_file_count, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    task_id,
                    utc_now(),
                    str(workspace_root.resolve()),
                    context_budget.intent,
                    context_budget.route_role,
                    context_budget.strategy,
                    context_budget.privacy_mode,
                    context_budget.max_context_tokens,
                    context_budget.estimated_context_tokens,
                    context_budget.estimated_file_tokens,
                    context_budget.reserve_response_tokens,
                    context_budget.selected_file_count,
                    context_budget.omitted_file_count,
                    json.dumps(payload, ensure_ascii=True),
                ),
            )

    def record_model_attempts(
        self,
        *,
        task_id: str,
        workspace_root: Path,
        attempts: list[ModelAttemptInfo],
        replace_for_task: bool = False,
    ) -> None:
        now = utc_now()
        with self._session() as conn:
            if replace_for_task:
                conn.execute("delete from model_attempt_telemetry where task_id = ?", (task_id,))
            for attempt in attempts:
                conn.execute(
                    """
                    insert into model_attempt_telemetry (
                        id, task_id, created_at, workspace_root, attempt_number, role, provider_id,
                        provider_label, provider_api, model, endpoint, privacy_mode, status, retryable,
                        input_tokens, output_tokens, estimated_cost_usd, latency_ms, reason, error, metadata_json
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        task_id,
                        now,
                        str(workspace_root.resolve()),
                        attempt.attempt,
                        attempt.role,
                        attempt.provider_id,
                        attempt.provider_label,
                        attempt.provider_api,
                        attempt.model,
                        attempt.endpoint,
                        attempt.privacy_mode,
                        attempt.status,
                        1 if attempt.retryable else 0,
                        attempt.input_tokens,
                        attempt.output_tokens,
                        attempt.estimated_cost_usd,
                        attempt.latency_ms,
                        attempt.reason,
                        attempt.error,
                        json.dumps(attempt.metadata, ensure_ascii=True),
                    ),
                )

    def record_feedback(
        self,
        *,
        project_root: Path,
        request: FeedbackRecordRequest,
    ) -> FeedbackTelemetryEntry:
        event = FeedbackTelemetryEntry(
            id=str(uuid4()),
            created_at=utc_now(),
            workspace_root=str(project_root.resolve()),
            task_id=request.task_id.strip(),
            sentiment=request.sentiment,
            action=request.action,
            target=request.target.strip()[:120] or "assistant_response",
            model_label=request.model_label.strip()[:160],
            route_role=request.route_role.strip()[:80],
            candidate_id=request.candidate_id.strip()[:120],
            content_hash=self._content_hash(request.content),
            context=request.context.strip()[:500],
            metadata=self._feedback_metadata(request),
        )
        with self._session() as conn:
            conn.execute(
                """
                insert into feedback_telemetry (
                    id, created_at, workspace_root, task_id, sentiment, action, target,
                    model_label, route_role, candidate_id, content_hash, context, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.created_at,
                    event.workspace_root,
                    event.task_id,
                    event.sentiment,
                    event.action,
                    event.target,
                    event.model_label,
                    event.route_role,
                    event.candidate_id,
                    event.content_hash,
                    event.context,
                    json.dumps(event.metadata, ensure_ascii=True),
                ),
            )
        return event

    def recent_feedback(
        self,
        *,
        project_root: Path,
        limit: int = 100,
    ) -> list[FeedbackTelemetryEntry]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        bounded_limit = max(1, min(500, limit))
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, workspace_root, task_id, sentiment, action, target,
                       model_label, route_role, candidate_id, content_hash, context, metadata_json
                from feedback_telemetry
                where workspace_root in ({placeholders})
                order by created_at desc
                limit ?
                """,
                (*aliases, bounded_limit),
            ).fetchall()

        events: list[FeedbackTelemetryEntry] = []
        for row in rows:
            payload = dict(row)
            payload["workspace_root"] = str(project_root.resolve())
            payload["metadata"] = self._json_payload(payload.pop("metadata_json"))
            events.append(FeedbackTelemetryEntry.model_validate(payload))
        return events

    def feedback_telemetry(
        self,
        *,
        project_root: Path,
        limit: int = 100,
    ) -> FeedbackTelemetryResponse:
        bounded_limit = max(1, min(500, limit))
        events = self.recent_feedback(project_root=project_root, limit=bounded_limit)
        context_budgets = self.recent_context_budgets(project_root=project_root, limit=bounded_limit)
        model_attempts = self.recent_model_attempts(project_root=project_root, limit=min(bounded_limit * 4, 1000))
        summary = self._feedback_summary(events)
        return FeedbackTelemetryResponse(
            workspace_root=str(project_root.resolve()),
            limit=bounded_limit,
            summary=summary,
            events=events,
            rollups=self._feedback_attribution_rollups(events, model_attempts, context_budgets),
            trends=self._feedback_trends(events),
            recommendations=self._feedback_recommendations(summary, events),
        )

    def recent_context_budgets(
        self,
        *,
        project_root: Path,
        limit: int = 20,
    ) -> list[ContextBudgetTelemetryEntry]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select task_id, created_at, workspace_root, intent, route_role, strategy, privacy_mode,
                       max_context_tokens, estimated_context_tokens, estimated_file_tokens, reserve_response_tokens,
                       selected_file_count, omitted_file_count, payload_json
                from context_budget_telemetry
                where workspace_root in ({placeholders})
                order by created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()

        budgets: list[ContextBudgetTelemetryEntry] = []
        for row in rows:
            payload = dict(row)
            payload["workspace_root"] = str(project_root.resolve())
            payload["payload"] = self._context_budget_payload(payload.pop("payload_json"))
            budgets.append(ContextBudgetTelemetryEntry.model_validate(payload))
        return budgets

    def recent_model_attempts(
        self,
        *,
        project_root: Path,
        limit: int = 50,
    ) -> list[ModelAttemptTelemetryEntry]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select task_id, created_at, workspace_root, attempt_number, role, provider_id,
                       provider_label, provider_api, model, endpoint, privacy_mode, status, retryable,
                       input_tokens, output_tokens, estimated_cost_usd, latency_ms, reason, error, metadata_json
                from model_attempt_telemetry
                where workspace_root in ({placeholders})
                order by created_at desc, attempt_number asc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()

        attempts: list[ModelAttemptTelemetryEntry] = []
        for row in rows:
            payload = dict(row)
            attempt_payload = {
                "attempt": payload.pop("attempt_number"),
                "role": payload.pop("role"),
                "provider_id": payload.pop("provider_id"),
                "provider_label": payload.pop("provider_label"),
                "provider_api": payload.pop("provider_api"),
                "model": payload.pop("model"),
                "endpoint": payload.pop("endpoint"),
                "privacy_mode": payload.pop("privacy_mode"),
                "status": payload.pop("status"),
                "retryable": bool(payload.pop("retryable")),
                "input_tokens": payload.pop("input_tokens"),
                "output_tokens": payload.pop("output_tokens"),
                "estimated_cost_usd": payload.pop("estimated_cost_usd"),
                "latency_ms": payload.pop("latency_ms"),
                "reason": payload.pop("reason"),
                "error": payload.pop("error"),
                "metadata": self._json_payload(payload.pop("metadata_json")),
            }
            payload["workspace_root"] = str(project_root.resolve())
            payload["attempt"] = ModelAttemptInfo.model_validate(attempt_payload)
            attempts.append(ModelAttemptTelemetryEntry.model_validate(payload))
        return attempts

    def route_health_signals(
        self,
        *,
        project_root: Path,
        limit: int = 200,
    ) -> list[ModelRouteHealthInfo]:
        attempts = self.recent_model_attempts(project_root=project_root, limit=max(1, min(1000, limit)))
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for entry in attempts:
            attempt = entry.attempt
            provider_id = attempt.provider_id.strip()
            if not provider_id:
                continue
            model = attempt.model.strip()
            role = attempt.role.strip().lower() or "unknown"
            key = (provider_id, model, role)
            group = groups.setdefault(
                key,
                {
                    "provider_id": provider_id,
                    "provider_label": attempt.provider_label,
                    "model": model,
                    "role": role,
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "fallback_attempts": 0,
                    "latencies": [],
                    "structured_preview_attempts": 0,
                    "structured_preview_retired_attempts": 0,
                    "structured_preview_reset_count": 0,
                    "structured_preview_final_winners": 0,
                    "latest_error": "",
                    "latest_at": "",
                },
            )
            group["attempts"] += 1
            group["latest_at"] = max(str(group["latest_at"]), entry.created_at)
            if not group["provider_label"] and attempt.provider_label:
                group["provider_label"] = attempt.provider_label
            status = self._attempt_status(entry)
            if status == "succeeded":
                group["successes"] += 1
            elif status in {"failed", "canceled"}:
                group["failures"] += 1
                if not group["latest_error"] and attempt.error:
                    group["latest_error"] = attempt.error
            if self._is_fallback_attempt(entry):
                group["fallback_attempts"] += 1
            if attempt.latency_ms is not None and attempt.latency_ms > 0:
                group["latencies"].append(attempt.latency_ms)
            preview = self._structured_preview_metrics(attempt.metadata)
            if preview is not None and preview["emitted"]:
                group["structured_preview_attempts"] += 1
                if preview["retired"]:
                    group["structured_preview_retired_attempts"] += 1
                if preview["final_winner"]:
                    group["structured_preview_final_winners"] += 1
                group["structured_preview_reset_count"] += int(preview["reset_count"])

        signals: list[ModelRouteHealthInfo] = []
        for group in groups.values():
            successes = int(group["successes"])
            failures = int(group["failures"])
            terminal = successes + failures
            success_rate = self._rate(successes, terminal)
            failure_rate = self._rate(failures, terminal)
            average_latency = self._average(group["latencies"])
            structured_preview_attempts = int(group["structured_preview_attempts"])
            structured_preview_retired_attempts = int(group["structured_preview_retired_attempts"])
            structured_preview_reset_count = int(group["structured_preview_reset_count"])
            structured_preview_final_winners = int(group["structured_preview_final_winners"])
            structured_preview_retired_rate = self._rate(
                structured_preview_retired_attempts,
                structured_preview_attempts,
            )
            penalty, cooldown, recommendation = self._route_health_policy(
                terminal_attempts=terminal,
                failures=failures,
                success_rate=success_rate,
                failure_rate=failure_rate,
                average_latency_ms=average_latency,
                structured_preview_attempts=structured_preview_attempts,
                structured_preview_retired_attempts=structured_preview_retired_attempts,
                structured_preview_reset_count=structured_preview_reset_count,
                structured_preview_final_winners=structured_preview_final_winners,
            )
            signals.append(
                ModelRouteHealthInfo(
                    provider_id=str(group["provider_id"]),
                    provider_label=str(group["provider_label"]),
                    model=str(group["model"]),
                    role=str(group["role"]),
                    attempts=int(group["attempts"]),
                    terminal_attempts=terminal,
                    successes=successes,
                    failures=failures,
                    fallback_attempts=int(group["fallback_attempts"]),
                    success_rate=success_rate,
                    failure_rate=failure_rate,
                    average_latency_ms=average_latency,
                    structured_preview_attempts=structured_preview_attempts,
                    structured_preview_retired_attempts=structured_preview_retired_attempts,
                    structured_preview_reset_count=structured_preview_reset_count,
                    structured_preview_final_winners=structured_preview_final_winners,
                    structured_preview_retired_rate=structured_preview_retired_rate,
                    penalty=penalty,
                    cooldown=cooldown,
                    latest_error=str(group["latest_error"]),
                    latest_at=str(group["latest_at"]),
                    recommendation=recommendation,
                )
            )
        return sorted(
            signals,
            key=lambda signal: (signal.cooldown, signal.penalty, signal.failures, signal.attempts),
            reverse=True,
        )

    def route_quality(
        self,
        *,
        project_root: Path,
        limit: int = 200,
    ) -> RouteQualityResponse:
        bounded_limit = max(1, min(500, limit))
        context_budgets = self.recent_context_budgets(project_root=project_root, limit=bounded_limit)
        model_attempts = self.recent_model_attempts(project_root=project_root, limit=min(bounded_limit * 4, 1000))
        feedback_events = self.recent_feedback(project_root=project_root, limit=min(bounded_limit * 2, 1000))

        overview = self._route_quality_overview(context_budgets, model_attempts, feedback_events)
        providers = self._route_quality_provider_rollups(model_attempts)
        token_calibration = self._route_quality_token_calibration_rollups(model_attempts)
        token_calibration_trends = self._route_quality_token_calibration_trends(model_attempts)
        structured_preview = self._route_quality_structured_preview_rollups(model_attempts)
        roles = self._route_quality_role_rollups(model_attempts)
        contexts = self._route_quality_context_rollups(context_budgets)
        context_drilldowns = self._route_quality_context_drilldowns(context_budgets)
        feedback_rollups = self._feedback_attribution_rollups(feedback_events, model_attempts, context_budgets)
        feedback_trends = self._feedback_trends(feedback_events)
        recommendations = self._route_quality_recommendations(
            overview,
            providers,
            contexts,
            token_calibration,
            structured_preview,
        )

        return RouteQualityResponse(
            workspace_root=str(project_root.resolve()),
            limit=bounded_limit,
            overview=overview,
            providers=providers,
            token_calibration=token_calibration,
            token_calibration_trends=token_calibration_trends,
            structured_preview=structured_preview,
            roles=roles,
            contexts=contexts,
            context_drilldowns=context_drilldowns,
            feedback_rollups=feedback_rollups,
            feedback_trends=feedback_trends,
            feedback_events=feedback_events[:40],
            recommendations=recommendations,
        )

    def fallback_inspector(
        self,
        *,
        project_root: Path,
        limit: int = 20,
        adapter_health: list[ModelAdapterHealthInfo] | None = None,
    ) -> FallbackInspectorResponse:
        bounded_limit = max(1, min(100, limit))
        task_rows = self._recent_task_dicts(project_root=project_root, limit=bounded_limit)
        task_ids = [str(row["id"]) for row in task_rows]
        if not task_ids:
            return FallbackInspectorResponse(
                workspace_root=str(project_root.resolve()),
                limit=bounded_limit,
                task_count=0,
                recommendations=[
                    "No task history exists for this workspace yet; run a planned chat turn to seed fallback inspection."
                ],
            )

        planner_payloads = self._planner_payloads_for_tasks(task_ids)
        context_budgets = self._context_budgets_for_tasks(project_root=project_root, task_ids=task_ids)
        model_attempts = self._model_attempts_for_tasks(project_root=project_root, task_ids=task_ids)
        adapter_health_lookup = self._adapter_health_lookup(adapter_health or [])

        tasks: list[FallbackInspectorTask] = []
        for row in task_rows:
            task_id = str(row["id"])
            task_plan = self._task_plan_from_payload(planner_payloads.get(task_id))
            attempts = model_attempts.get(task_id, [])
            context_budget = context_budgets.get(task_id)
            candidates = self._fallback_inspector_candidates(task_plan, attempts, adapter_health_lookup)
            recommendations = self._fallback_inspector_task_recommendations(task_plan, context_budget, attempts, candidates)
            tasks.append(
                FallbackInspectorTask(
                    task_id=task_id,
                    created_at=str(row["created_at"]),
                    finished_at=str(row["finished_at"]) if row["finished_at"] is not None else None,
                    mode=str(row["mode"]),
                    workspace_root=str(project_root.resolve()),
                    message=str(row["message"]),
                    status=str(row["status"]),
                    task_plan=task_plan,
                    context_budget=context_budget,
                    attempts=attempts,
                    candidates=candidates,
                    fallback_roles=task_plan.routing.fallback_roles if task_plan and task_plan.routing else [],
                    summary=self._fallback_inspector_task_summary(task_plan, attempts, candidates),
                    recommendations=recommendations,
                )
            )

        return FallbackInspectorResponse(
            workspace_root=str(project_root.resolve()),
            limit=bounded_limit,
            task_count=len(tasks),
            tasks=tasks,
            recommendations=self._fallback_inspector_recommendations(tasks),
        )

    def telemetry_snapshot(
        self,
        *,
        project_root: Path,
        route_quality_limit: int = 200,
        fallback_limit: int = 20,
        feedback_limit: int = 100,
        stale_after_seconds: int = 900,
    ) -> TelemetrySnapshot | None:
        route_limit, fallback_limit, feedback_limit = self._bounded_snapshot_limits(
            route_quality_limit, fallback_limit, feedback_limit
        )
        snapshot_key = self._telemetry_snapshot_key(route_limit, fallback_limit, feedback_limit)
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            row = conn.execute(
                f"""
                select *
                from telemetry_snapshots
                where workspace_root in ({placeholders})
                  and snapshot_key = ?
                order by updated_at desc
                limit 1
                """,
                (*aliases, snapshot_key),
            ).fetchone()

        return self._telemetry_snapshot_from_row(row, project_root, stale_after_seconds) if row else None

    def refresh_telemetry_snapshot(
        self,
        *,
        project_root: Path,
        route_quality_limit: int = 200,
        fallback_limit: int = 20,
        feedback_limit: int = 100,
        stale_after_seconds: int = 900,
    ) -> TelemetrySnapshot:
        route_limit, fallback_limit, feedback_limit = self._bounded_snapshot_limits(
            route_quality_limit, fallback_limit, feedback_limit
        )
        snapshot_key = self._telemetry_snapshot_key(route_limit, fallback_limit, feedback_limit)
        workspace_root = str(project_root.resolve())
        now = utc_now()
        route_quality = self.route_quality(project_root=project_root, limit=route_limit)
        fallback_inspector = self.fallback_inspector(project_root=project_root, limit=fallback_limit)
        feedback = self.feedback_telemetry(project_root=project_root, limit=feedback_limit)

        with self._session() as conn:
            existing = conn.execute(
                """
                select id, created_at
                from telemetry_snapshots
                where workspace_root = ?
                  and snapshot_key = ?
                """,
                (workspace_root, snapshot_key),
            ).fetchone()
            snapshot_id = str(existing["id"]) if existing else str(uuid4())
            created_at = str(existing["created_at"]) if existing else now
            conn.execute(
                """
                insert into telemetry_snapshots (
                    id, created_at, updated_at, workspace_root, snapshot_key,
                    route_quality_limit, fallback_limit, feedback_limit,
                    stale_after_seconds, route_quality_json, fallback_inspector_json,
                    feedback_json, task_count, model_attempt_count, feedback_count,
                    reliability_score, positive_feedback_rate
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(workspace_root, snapshot_key) do update set
                    updated_at = excluded.updated_at,
                    route_quality_limit = excluded.route_quality_limit,
                    fallback_limit = excluded.fallback_limit,
                    feedback_limit = excluded.feedback_limit,
                    stale_after_seconds = excluded.stale_after_seconds,
                    route_quality_json = excluded.route_quality_json,
                    fallback_inspector_json = excluded.fallback_inspector_json,
                    feedback_json = excluded.feedback_json,
                    task_count = excluded.task_count,
                    model_attempt_count = excluded.model_attempt_count,
                    feedback_count = excluded.feedback_count,
                    reliability_score = excluded.reliability_score,
                    positive_feedback_rate = excluded.positive_feedback_rate
                """,
                (
                    snapshot_id,
                    created_at,
                    now,
                    workspace_root,
                    snapshot_key,
                    route_limit,
                    fallback_limit,
                    feedback_limit,
                    stale_after_seconds,
                    self._model_json(route_quality),
                    self._model_json(fallback_inspector),
                    self._model_json(feedback),
                    route_quality.overview.task_count,
                    route_quality.overview.model_attempt_count,
                    feedback.summary.feedback_count,
                    route_quality.overview.reliability_score,
                    feedback.summary.positive_rate,
                ),
            )

        return TelemetrySnapshot(
            id=snapshot_id,
            workspace_root=workspace_root,
            snapshot_key=snapshot_key,
            created_at=created_at,
            updated_at=now,
            route_quality_limit=route_limit,
            fallback_limit=fallback_limit,
            feedback_limit=feedback_limit,
            stale_after_seconds=stale_after_seconds,
            age_seconds=0,
            is_stale=False,
            route_quality=route_quality,
            fallback_inspector=fallback_inspector,
            feedback=feedback,
        )

    def prune_telemetry_snapshots(
        self,
        *,
        project_root: Path,
        max_snapshots: int = 12,
        retention_days: int = 30,
    ) -> TelemetrySnapshotPruneInfo:
        max_count = max(1, min(250, max_snapshots))
        days = max(1, min(3650, retention_days))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, updated_at
                from telemetry_snapshots
                where workspace_root in ({placeholders})
                order by updated_at desc
                """,
                tuple(aliases),
            ).fetchall()
            delete_ids: list[str] = []
            for index, row in enumerate(rows):
                updated_at = str(row["updated_at"])
                if index >= max_count or self._snapshot_updated_before(updated_at, cutoff):
                    delete_ids.append(str(row["id"]))
            if delete_ids:
                delete_placeholders = ",".join("?" for _ in delete_ids)
                conn.execute(f"delete from telemetry_snapshots where id in ({delete_placeholders})", tuple(delete_ids))
            retained = conn.execute(
                f"""
                select updated_at
                from telemetry_snapshots
                where workspace_root in ({placeholders})
                order by updated_at asc
                """,
                tuple(aliases),
            ).fetchall()

        retained_count = len(retained)
        oldest = str(retained[0]["updated_at"]) if retained else ""
        newest = str(retained[-1]["updated_at"]) if retained else ""
        if delete_ids:
            recommendation = f"Pruned {len(delete_ids)} telemetry snapshot(s); retained {retained_count} recent snapshot(s)."
        elif retained_count >= max_count:
            recommendation = f"Snapshot cache is at the retention cap of {max_count}; future refreshes will prune older windows."
        else:
            recommendation = f"Snapshot cache is within policy with {retained_count} retained snapshot(s)."
        return TelemetrySnapshotPruneInfo(
            retention_max_snapshots=max_count,
            retention_days=days,
            deleted_count=len(delete_ids),
            retained_count=retained_count,
            oldest_retained_at=oldest,
            newest_retained_at=newest,
            recommendation=recommendation,
        )

    def route_policy_diff(
        self,
        *,
        project_root: Path,
        limit: int = 200,
        use_snapshot: bool = True,
        stale_after_seconds: int = 900,
        min_attempts: int = 3,
    ) -> RoutePolicyDiffResponse:
        bounded_limit = max(1, min(500, limit))
        source = "live"
        source_snapshot_id = ""
        source_snapshot_age_seconds = 0
        source_snapshot_stale = False
        snapshot = self.telemetry_snapshot(
            project_root=project_root,
            route_quality_limit=bounded_limit,
            fallback_limit=20,
            feedback_limit=min(500, bounded_limit),
            stale_after_seconds=stale_after_seconds,
        ) if use_snapshot else None
        if snapshot is not None and not snapshot.is_stale:
            route_quality = snapshot.route_quality
            source = "snapshot"
            source_snapshot_id = snapshot.id
            source_snapshot_age_seconds = snapshot.age_seconds
            source_snapshot_stale = snapshot.is_stale
        else:
            route_quality = self.route_quality(project_root=project_root, limit=bounded_limit)
            if snapshot is not None:
                source = "live_with_stale_snapshot"
                source_snapshot_id = snapshot.id
                source_snapshot_age_seconds = snapshot.age_seconds
                source_snapshot_stale = snapshot.is_stale

        model_attempts = self.recent_model_attempts(project_root=project_root, limit=min(bounded_limit * 4, 1000))
        provider_proposals = self._route_policy_provider_proposals(route_quality, max(1, min_attempts))
        role_proposals = self._route_policy_role_proposals(route_quality, model_attempts, provider_proposals, max(1, min_attempts))
        warnings = self._route_policy_warnings(route_quality, source_snapshot_stale, min_attempts)
        return RoutePolicyDiffResponse(
            workspace_root=str(project_root.resolve()),
            generated_at=utc_now(),
            limit=bounded_limit,
            source=source,
            source_snapshot_id=source_snapshot_id,
            source_snapshot_age_seconds=source_snapshot_age_seconds,
            source_snapshot_stale=source_snapshot_stale,
            min_attempts=max(1, min_attempts),
            provider_proposals=provider_proposals,
            role_proposals=role_proposals,
            recommendations=self._route_policy_recommendations(provider_proposals, role_proposals, warnings),
            warnings=warnings,
        )

    def repair_attempts(self, task_id: str) -> list[RepairAttempt]:
        with self._session() as conn:
            rows = conn.execute(
                """
                select attempt_number, category, before_signature, after_signature, outcome, checkpoint, summary, created_at
                from repair_attempts
                where task_id = ?
                order by attempt_number asc, created_at asc
                """,
                (task_id,),
            ).fetchall()
        attempts: list[RepairAttempt] = []
        for row in rows:
            payload = dict(row)
            payload["attempt"] = payload.pop("attempt_number")
            attempts.append(RepairAttempt.model_validate(payload))
        return attempts

    def _bounded_snapshot_limits(
        self,
        route_quality_limit: int,
        fallback_limit: int,
        feedback_limit: int,
    ) -> tuple[int, int, int]:
        return (
            max(1, min(500, route_quality_limit)),
            max(1, min(100, fallback_limit)),
            max(1, min(500, feedback_limit)),
        )

    def _telemetry_snapshot_key(self, route_quality_limit: int, fallback_limit: int, feedback_limit: int) -> str:
        return f"route:{route_quality_limit}|fallback:{fallback_limit}|feedback:{feedback_limit}"

    def _telemetry_snapshot_from_row(
        self,
        row: sqlite3.Row,
        project_root: Path,
        stale_after_seconds: int,
    ) -> TelemetrySnapshot:
        updated_at = str(row["updated_at"])
        age_seconds = self._snapshot_age_seconds(updated_at)
        stale_after = max(60, stale_after_seconds or int(row["stale_after_seconds"] or 900))
        return TelemetrySnapshot(
            id=str(row["id"]),
            workspace_root=str(project_root.resolve()),
            snapshot_key=str(row["snapshot_key"]),
            created_at=str(row["created_at"]),
            updated_at=updated_at,
            route_quality_limit=int(row["route_quality_limit"]),
            fallback_limit=int(row["fallback_limit"]),
            feedback_limit=int(row["feedback_limit"]),
            stale_after_seconds=stale_after,
            age_seconds=age_seconds,
            is_stale=age_seconds > stale_after,
            route_quality=RouteQualityResponse.model_validate(self._json_payload(str(row["route_quality_json"]))),
            fallback_inspector=FallbackInspectorResponse.model_validate(
                self._json_payload(str(row["fallback_inspector_json"]))
            ),
            feedback=FeedbackTelemetryResponse.model_validate(self._json_payload(str(row["feedback_json"]))),
        )

    def _snapshot_age_seconds(self, updated_at: str) -> int:
        parsed = self._parse_snapshot_timestamp(updated_at)
        if parsed is None:
            return 0
        return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))

    def _snapshot_updated_before(self, updated_at: str, cutoff: datetime) -> bool:
        parsed = self._parse_snapshot_timestamp(updated_at)
        if parsed is None:
            return False
        return parsed.astimezone(timezone.utc) < cutoff.astimezone(timezone.utc)

    def _parse_snapshot_timestamp(self, updated_at: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _model_json(self, value: Any) -> str:
        if hasattr(value, "model_dump"):
            return json.dumps(value.model_dump(mode="json"), ensure_ascii=True, sort_keys=True)
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _route_policy_provider_proposals(
        self,
        route_quality: RouteQualityResponse,
        min_attempts: int,
    ) -> list[RoutePolicyProviderProposal]:
        feedback_by_provider = {
            rollup.key: rollup
            for rollup in route_quality.feedback_rollups
            if rollup.dimension == "provider"
        }
        proposals: list[RoutePolicyProviderProposal] = []
        for observed_rank, provider in enumerate(route_quality.providers, start=1):
            provider_key = provider.provider_id or provider.provider_label or provider.provider_api or provider.model or "unknown"
            feedback = feedback_by_provider.get(provider_key)
            score = self._route_policy_provider_score(provider, feedback)
            terminal_attempts = provider.successes + provider.failures
            action = self._route_policy_provider_action(provider, feedback, terminal_attempts, min_attempts)
            reasons = self._route_policy_provider_reasons(provider, feedback, terminal_attempts)
            risks = self._route_policy_provider_risks(provider, feedback, terminal_attempts, min_attempts)
            proposals.append(
                RoutePolicyProviderProposal(
                    provider_id=provider.provider_id,
                    provider_label=provider.provider_label,
                    provider_api=provider.provider_api,
                    model=provider.model,
                    observed_rank=observed_rank,
                    action=action,
                    risk_level=self._route_policy_risk_level(risks),
                    confidence=self._route_policy_confidence(terminal_attempts, feedback.feedback_count if feedback else 0, min_attempts),
                    score=score,
                    attempts=provider.attempts,
                    successes=provider.successes,
                    failures=provider.failures,
                    fallback_rate=provider.fallback_rate,
                    success_rate=provider.success_rate,
                    positive_feedback_rate=feedback.positive_rate if feedback else 0.0,
                    negative_feedback_rate=feedback.negative_rate if feedback else 0.0,
                    average_latency_ms=provider.average_latency_ms,
                    average_context_utilization=provider.average_context_utilization,
                    estimated_cost_usd=provider.estimated_cost_usd,
                    reasons=reasons,
                    risks=risks,
                )
            )

        proposals.sort(key=lambda proposal: (proposal.score, proposal.confidence, -proposal.observed_rank), reverse=True)
        for proposed_rank, proposal in enumerate(proposals, start=1):
            proposal.proposed_rank = proposed_rank
        return proposals

    def _route_policy_role_proposals(
        self,
        route_quality: RouteQualityResponse,
        model_attempts: list[ModelAttemptTelemetryEntry],
        provider_proposals: list[RoutePolicyProviderProposal],
        min_attempts: int,
    ) -> list[RoutePolicyRoleProposal]:
        provider_scores = {
            self._route_policy_provider_key_from_parts(
                proposal.provider_id,
                proposal.provider_label,
                proposal.provider_api,
                proposal.model,
            ): proposal.score
            for proposal in provider_proposals
        }
        role_provider_stats: dict[str, dict[str, dict[str, Any]]] = {}
        for entry in model_attempts:
            attempt = entry.attempt
            role = attempt.role or "unknown"
            provider_key = self._route_policy_provider_key_from_parts(
                attempt.provider_id,
                attempt.provider_label,
                attempt.provider_api,
                attempt.model,
            )
            group = role_provider_stats.setdefault(role, {}).setdefault(
                provider_key,
                {
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "fallbacks": 0,
                    "latencies": [],
                },
            )
            group["attempts"] += 1
            if attempt.status == "succeeded":
                group["successes"] += 1
            if attempt.status == "failed":
                group["failures"] += 1
            if attempt.attempt > 1 or str(attempt.metadata.get("candidate_source") or "").lower() == "fallback":
                group["fallbacks"] += 1
            if attempt.latency_ms is not None:
                group["latencies"].append(attempt.latency_ms)

        proposals: list[RoutePolicyRoleProposal] = []
        for role in route_quality.roles:
            provider_groups = role_provider_stats.get(role.role, {})
            observed_primary = self._route_policy_observed_primary(provider_groups)
            provider_scores_for_role = {
                key: self._route_policy_role_provider_score(key, group, provider_scores)
                for key, group in provider_groups.items()
            }
            proposed_primary = (
                max(provider_scores_for_role.items(), key=lambda item: item[1])[0]
                if provider_scores_for_role
                else observed_primary
            )
            observed_score = provider_scores_for_role.get(observed_primary, 0.0)
            proposed_score = provider_scores_for_role.get(proposed_primary, observed_score)
            score_delta = round(max(0.0, proposed_score - observed_score), 4)
            action = self._route_policy_role_action(role, observed_primary, proposed_primary, score_delta, min_attempts)
            reasons = self._route_policy_role_reasons(role, observed_primary, proposed_primary, score_delta)
            risks = self._route_policy_role_risks(role, provider_groups, min_attempts)
            proposals.append(
                RoutePolicyRoleProposal(
                    role=role.role,
                    action=action,
                    observed_primary_provider=observed_primary,
                    proposed_primary_provider=proposed_primary,
                    confidence=self._route_policy_confidence(role.successes + role.failures, 0, min_attempts),
                    task_count=role.task_count,
                    attempts=role.attempts,
                    success_rate=role.success_rate,
                    fallback_attempts=role.fallback_attempts,
                    score_delta=score_delta,
                    candidate_provider_ids=sorted(provider_groups.keys(), key=lambda key: provider_scores_for_role.get(key, 0.0), reverse=True),
                    reasons=reasons,
                    risks=risks,
                )
            )

        return sorted(
            proposals,
            key=lambda proposal: (
                proposal.action != "keep",
                proposal.score_delta,
                proposal.attempts,
            ),
            reverse=True,
        )

    def _route_policy_provider_score(
        self,
        provider: RouteQualityProviderRollup,
        feedback: FeedbackAttributionRollup | None,
    ) -> float:
        positive_rate = feedback.positive_rate if feedback else 0.0
        negative_rate = feedback.negative_rate if feedback else 0.0
        context_penalty = max(0.0, ((provider.average_context_utilization or 0.0) - 0.72) * 14.0)
        latency_penalty = 0.0
        if provider.average_latency_ms is not None:
            if provider.average_latency_ms > 30000:
                latency_penalty = 8.0
            elif provider.average_latency_ms > 10000:
                latency_penalty = 3.0
        score = (
            provider.success_rate * 100.0
            - provider.fallback_rate * 20.0
            + positive_rate * 8.0
            - negative_rate * 16.0
            - context_penalty
            - latency_penalty
        )
        if provider.successes + provider.failures == 0:
            score = min(score, 35.0)
        return round(max(0.0, min(100.0, score)), 2)

    def _route_policy_provider_action(
        self,
        provider: RouteQualityProviderRollup,
        feedback: FeedbackAttributionRollup | None,
        terminal_attempts: int,
        min_attempts: int,
    ) -> str:
        negative_rate = feedback.negative_rate if feedback else 0.0
        if terminal_attempts < min_attempts:
            return "monitor"
        if provider.success_rate < 0.65 or provider.fallback_rate >= 0.45 or negative_rate >= 0.35:
            return "deprioritize"
        if provider.success_rate >= 0.82 and provider.fallback_rate <= 0.25 and negative_rate < 0.20:
            return "promote"
        return "hold"

    def _route_policy_provider_reasons(
        self,
        provider: RouteQualityProviderRollup,
        feedback: FeedbackAttributionRollup | None,
        terminal_attempts: int,
    ) -> list[str]:
        reasons = [
            f"Observed {terminal_attempts} terminal attempts with {round(provider.success_rate * 100)}% success.",
            f"Fallback share is {round(provider.fallback_rate * 100)}% across {provider.attempts} attempts.",
        ]
        if feedback and feedback.feedback_count:
            reasons.append(
                f"User feedback is {round(feedback.positive_rate * 100)}% positive and {round(feedback.negative_rate * 100)}% negative across {feedback.feedback_count} events."
            )
        if provider.average_latency_ms is not None:
            reasons.append(f"Average latency is {round(provider.average_latency_ms)}ms.")
        if provider.estimated_cost_usd > 0:
            reasons.append(f"Recent estimated spend is ${provider.estimated_cost_usd:.4f}.")
        return reasons

    def _route_policy_provider_risks(
        self,
        provider: RouteQualityProviderRollup,
        feedback: FeedbackAttributionRollup | None,
        terminal_attempts: int,
        min_attempts: int,
    ) -> list[str]:
        risks: list[str] = []
        if terminal_attempts < min_attempts:
            risks.append("Insufficient completed attempts for a confident provider policy change.")
        if provider.success_rate < 0.65 and terminal_attempts >= min_attempts:
            risks.append("Provider success rate is below the promotion floor.")
        if provider.fallback_rate >= 0.35:
            risks.append("Provider is already involved in elevated fallback traffic.")
        if feedback and feedback.negative_rate >= 0.30:
            risks.append("Negative feedback is elevated for this provider.")
        if provider.average_context_utilization is not None and provider.average_context_utilization > 0.80:
            risks.append("Context utilization is high enough to increase truncation risk.")
        return risks

    def _route_policy_role_provider_score(
        self,
        provider_key: str,
        group: dict[str, Any],
        provider_scores: dict[str, float],
    ) -> float:
        attempts = int(group["attempts"])
        successes = int(group["successes"])
        failures = int(group["failures"])
        fallback_rate = self._rate(int(group["fallbacks"]), attempts)
        role_success_rate = self._rate(successes, successes + failures)
        base_score = provider_scores.get(provider_key, 45.0)
        if successes + failures == 0:
            return round(min(base_score, 35.0), 2)
        return round((base_score * 0.45) + (role_success_rate * 100.0 * 0.45) - (fallback_rate * 10.0), 2)

    def _route_policy_observed_primary(self, provider_groups: dict[str, dict[str, Any]]) -> str:
        if not provider_groups:
            return ""
        return max(provider_groups.items(), key=lambda item: int(item[1]["attempts"]))[0]

    def _route_policy_role_action(
        self,
        role: RouteQualityRoleRollup,
        observed_primary: str,
        proposed_primary: str,
        score_delta: float,
        min_attempts: int,
    ) -> str:
        terminal_attempts = role.successes + role.failures
        fallback_rate = self._rate(role.fallback_attempts, role.attempts)
        if terminal_attempts < min_attempts:
            return "keep"
        if proposed_primary and observed_primary and proposed_primary != observed_primary and score_delta >= 8.0:
            return "switch_primary"
        if role.success_rate < 0.70:
            return "strengthen_fallback"
        if fallback_rate >= 0.30:
            return "rebalance"
        return "keep"

    def _route_policy_role_reasons(
        self,
        role: RouteQualityRoleRollup,
        observed_primary: str,
        proposed_primary: str,
        score_delta: float,
    ) -> list[str]:
        reasons = [
            f"Role has {role.attempts} attempts with {round(role.success_rate * 100)}% success.",
            f"Observed {role.fallback_attempts} fallback attempts for this role.",
        ]
        if proposed_primary and observed_primary and proposed_primary != observed_primary:
            reasons.append(
                f"Observed primary {observed_primary} trails proposed primary {proposed_primary} by {score_delta:.1f} score points."
            )
        return reasons

    def _route_policy_role_risks(
        self,
        role: RouteQualityRoleRollup,
        provider_groups: dict[str, dict[str, Any]],
        min_attempts: int,
    ) -> list[str]:
        risks: list[str] = []
        if role.successes + role.failures < min_attempts:
            risks.append("Insufficient terminal attempts for this route role.")
        if len(provider_groups) <= 1:
            risks.append("Only one provider has recent telemetry for this route role.")
        if role.success_rate < 0.70 and role.successes + role.failures >= min_attempts:
            risks.append("Role reliability is below the desired policy floor.")
        if self._rate(role.fallback_attempts, role.attempts) >= 0.30:
            risks.append("Role has elevated fallback traffic.")
        return risks

    def _route_policy_warnings(
        self,
        route_quality: RouteQualityResponse,
        source_snapshot_stale: bool,
        min_attempts: int,
    ) -> list[str]:
        warnings: list[str] = []
        if source_snapshot_stale:
            warnings.append("A stale snapshot existed, so the proposal was generated from live recent-window telemetry.")
        if route_quality.overview.model_attempt_count == 0:
            warnings.append("No model-attempt telemetry is available; policy proposals are not actionable yet.")
        if route_quality.overview.feedback_count == 0:
            warnings.append("No feedback telemetry is available; proposals rely only on execution metrics.")
        low_sample_count = sum(1 for provider in route_quality.providers if provider.successes + provider.failures < min_attempts)
        if low_sample_count:
            warnings.append(f"{low_sample_count} provider(s) have fewer than {min_attempts} terminal attempts.")
        return warnings

    def _route_policy_recommendations(
        self,
        provider_proposals: list[RoutePolicyProviderProposal],
        role_proposals: list[RoutePolicyRoleProposal],
        warnings: list[str],
    ) -> list[str]:
        recommendations: list[str] = []
        promoted = [proposal for proposal in provider_proposals if proposal.action == "promote"]
        deprioritized = [proposal for proposal in provider_proposals if proposal.action == "deprioritize"]
        switches = [proposal for proposal in role_proposals if proposal.action == "switch_primary"]
        if promoted:
            recommendations.append(
                f"Consider promoting {promoted[0].provider_label or promoted[0].provider_id or promoted[0].model} for more primary traffic after review."
            )
        if deprioritized:
            recommendations.append(
                f"Review deprioritizing {deprioritized[0].provider_label or deprioritized[0].provider_id or deprioritized[0].model} because reliability or feedback risk is elevated."
            )
        if switches:
            recommendations.append(
                f"Review {len(switches)} route role primary-provider switch proposal(s) before updating routing presets."
            )
        if not recommendations and not warnings:
            recommendations.append("No route-policy changes are recommended for the current telemetry window.")
        return recommendations

    def _route_policy_confidence(self, terminal_attempts: int, feedback_count: int, min_attempts: int) -> float:
        attempt_weight = min(0.65, terminal_attempts / max(min_attempts * 6, 1))
        feedback_weight = min(0.20, feedback_count / 50)
        return round(min(0.95, 0.15 + attempt_weight + feedback_weight), 2)

    def _route_policy_risk_level(self, risks: list[str]) -> str:
        if any("below" in risk.lower() or "negative" in risk.lower() for risk in risks):
            return "high"
        if risks:
            return "medium"
        return "low"

    def _route_policy_provider_key_from_parts(
        self,
        provider_id: str,
        provider_label: str,
        provider_api: str,
        model: str,
    ) -> str:
        return provider_id or provider_label or provider_api or model or "unknown"

    def _project_root_aliases(self, project_root: Path) -> list[str]:
        resolved = project_root.resolve()
        aliases = {str(resolved)}

        current_workspace = (self.project_root / "workspace").resolve()
        legacy_workspace = (self.project_root / "backend" / "workspace").resolve()

        if resolved == legacy_workspace:
            aliases.add(str(current_workspace))
        elif resolved == current_workspace:
            aliases.add(str(legacy_workspace))
        elif resolved.is_relative_to(current_workspace):
            aliases.add(str((legacy_workspace / resolved.relative_to(current_workspace)).resolve()))
        elif resolved.is_relative_to(legacy_workspace):
            aliases.add(str((current_workspace / resolved.relative_to(legacy_workspace)).resolve()))

        return list(aliases)

    def _recent_task_dicts(self, *, project_root: Path, limit: int) -> list[dict[str, Any]]:
        aliases = self._project_root_aliases(project_root)
        placeholders = ",".join("?" for _ in aliases)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select id, created_at, finished_at, mode, workspace_root, message, status
                from tasks
                where workspace_root in ({placeholders})
                order by created_at desc
                limit ?
                """,
                (*aliases, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _planner_payloads_for_tasks(self, task_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" for _ in task_ids)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select task_id, payload_json
                from events
                where task_id in ({placeholders}) and kind = ? and title = ?
                order by created_at desc, id desc
                """,
                (*task_ids, "planner", "Task plan prepared"),
            ).fetchall()

        payloads: dict[str, dict[str, Any]] = {}
        for row in rows:
            task_id = str(row["task_id"])
            if task_id not in payloads:
                payloads[task_id] = self._json_payload(str(row["payload_json"]))
        return payloads

    def _context_budgets_for_tasks(
        self,
        *,
        project_root: Path,
        task_ids: list[str],
    ) -> dict[str, ContextBudgetTelemetryEntry]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" for _ in task_ids)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select task_id, created_at, workspace_root, intent, route_role, strategy, privacy_mode,
                       max_context_tokens, estimated_context_tokens, estimated_file_tokens, reserve_response_tokens,
                       selected_file_count, omitted_file_count, payload_json
                from context_budget_telemetry
                where task_id in ({placeholders})
                order by created_at desc
                """,
                (*task_ids,),
            ).fetchall()

        budgets: dict[str, ContextBudgetTelemetryEntry] = {}
        for row in rows:
            task_id = str(row["task_id"])
            if task_id in budgets:
                continue
            payload = dict(row)
            payload["workspace_root"] = str(project_root.resolve())
            payload["payload"] = self._context_budget_payload(payload.pop("payload_json"))
            budgets[task_id] = ContextBudgetTelemetryEntry.model_validate(payload)
        return budgets

    def _model_attempts_for_tasks(
        self,
        *,
        project_root: Path,
        task_ids: list[str],
    ) -> dict[str, list[ModelAttemptTelemetryEntry]]:
        if not task_ids:
            return {}
        placeholders = ",".join("?" for _ in task_ids)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                select task_id, created_at, workspace_root, attempt_number, role, provider_id,
                       provider_label, provider_api, model, endpoint, privacy_mode, status, retryable,
                       input_tokens, output_tokens, estimated_cost_usd, latency_ms, reason, error, metadata_json
                from model_attempt_telemetry
                where task_id in ({placeholders})
                order by task_id asc, attempt_number asc, created_at asc
                """,
                (*task_ids,),
            ).fetchall()

        attempts: dict[str, list[ModelAttemptTelemetryEntry]] = {}
        for row in rows:
            entry = self._model_attempt_entry_from_row(row, project_root)
            attempts.setdefault(entry.task_id, []).append(entry)
        return attempts

    def _model_attempt_entry_from_row(
        self,
        row: sqlite3.Row,
        project_root: Path,
    ) -> ModelAttemptTelemetryEntry:
        payload = dict(row)
        attempt_payload = {
            "attempt": payload.pop("attempt_number"),
            "role": payload.pop("role"),
            "provider_id": payload.pop("provider_id"),
            "provider_label": payload.pop("provider_label"),
            "provider_api": payload.pop("provider_api"),
            "model": payload.pop("model"),
            "endpoint": payload.pop("endpoint"),
            "privacy_mode": payload.pop("privacy_mode"),
            "status": payload.pop("status"),
            "retryable": bool(payload.pop("retryable")),
            "input_tokens": payload.pop("input_tokens"),
            "output_tokens": payload.pop("output_tokens"),
            "estimated_cost_usd": payload.pop("estimated_cost_usd"),
            "latency_ms": payload.pop("latency_ms"),
            "reason": payload.pop("reason"),
            "error": payload.pop("error"),
            "metadata": self._json_payload(payload.pop("metadata_json")),
        }
        payload["workspace_root"] = str(project_root.resolve())
        payload["attempt"] = ModelAttemptInfo.model_validate(attempt_payload)
        return ModelAttemptTelemetryEntry.model_validate(payload)

    def _task_plan_from_payload(self, payload: dict[str, Any] | None) -> TaskPlanInfo | None:
        if not payload:
            return None
        try:
            return TaskPlanInfo.model_validate(payload)
        except ValueError:
            return None

    def _fallback_inspector_candidates(
        self,
        task_plan: TaskPlanInfo | None,
        attempts: list[ModelAttemptTelemetryEntry],
        adapter_health_lookup: dict[str, ModelAdapterHealthInfo] | None = None,
    ) -> list[FallbackInspectorCandidate]:
        routing = task_plan.routing if task_plan else None
        if routing is None:
            return []

        health_lookup = adapter_health_lookup or {}
        candidates: list[FallbackInspectorCandidate] = []
        used_attempts: set[int] = set()
        for index, candidate in enumerate(routing.candidates, start=1):
            candidate_id = candidate.candidate_id or self._legacy_candidate_id(index, candidate.role)
            attempt = self._match_candidate_attempt(
                candidate_id=candidate_id,
                candidate_index=index - 1,
                role=candidate.role,
                provider_hint=candidate.provider_hint,
                attempts=attempts,
                used_attempts=used_attempts,
            )
            candidates.append(
                self._fallback_inspector_candidate(
                    index=index,
                    candidate_id=candidate_id,
                    role=candidate.role,
                    provider_hint=candidate.provider_hint,
                    required_capabilities=candidate.required_capabilities,
                    privacy_mode=candidate.privacy_mode,
                    reason=candidate.reason,
                    confidence=candidate.confidence,
                    attempt=attempt,
                    adapter_health=self._candidate_adapter_health(
                        health_lookup,
                        attempt=attempt,
                        provider_hint=candidate.provider_hint,
                    ),
                )
            )

        existing_roles = {candidate.role for candidate in routing.candidates}
        for fallback_role in routing.fallback_roles:
            if fallback_role in existing_roles:
                continue
            index = len(candidates) + 1
            candidate_id = self._fallback_candidate_id(fallback_role)
            attempt = self._match_candidate_attempt(
                candidate_id=candidate_id,
                candidate_index=index - 1,
                role=fallback_role,
                provider_hint=f"{fallback_role} fallback",
                attempts=attempts,
                used_attempts=used_attempts,
            )
            candidates.append(
                self._fallback_inspector_candidate(
                    index=index,
                    candidate_id=candidate_id,
                    role=fallback_role,
                    provider_hint=f"{fallback_role} fallback",
                    required_capabilities=[],
                    privacy_mode=routing.privacy_mode,
                    reason=f"Fallback role for {routing.task_role}.",
                    confidence=0.5,
                    attempt=attempt,
                    adapter_health=self._candidate_adapter_health(
                        health_lookup,
                        attempt=attempt,
                        provider_hint=f"{fallback_role} fallback",
                    ),
                )
            )
        return candidates

    def _match_candidate_attempt(
        self,
        *,
        candidate_id: str,
        candidate_index: int,
        role: str,
        provider_hint: str,
        attempts: list[ModelAttemptTelemetryEntry],
        used_attempts: set[int],
    ) -> ModelAttemptTelemetryEntry | None:
        if candidate_id:
            for entry in attempts:
                attempt = entry.attempt
                if attempt.attempt in used_attempts:
                    continue
                metadata = attempt.metadata if isinstance(attempt.metadata, dict) else {}
                if str(metadata.get("candidate_id") or "") == candidate_id:
                    used_attempts.add(attempt.attempt)
                    return entry

        if candidate_index < len(attempts):
            direct = attempts[candidate_index]
            if direct.attempt.attempt not in used_attempts and direct.attempt.role == role:
                used_attempts.add(direct.attempt.attempt)
                return direct

        provider_tokens = [
            token.strip(" ,:;().").lower()
            for token in provider_hint.replace("/", " ").replace("-", " ").split()
            if len(token.strip(" ,:;().")) > 3
        ]
        for entry in attempts:
            attempt = entry.attempt
            if attempt.attempt in used_attempts or attempt.role != role:
                continue
            provider_text = " ".join(
                [attempt.provider_id, attempt.provider_label, attempt.provider_api, attempt.model]
            ).lower()
            if provider_tokens and any(token in provider_text for token in provider_tokens):
                used_attempts.add(attempt.attempt)
                return entry

        for entry in attempts:
            attempt = entry.attempt
            if attempt.attempt not in used_attempts and attempt.role == role:
                used_attempts.add(attempt.attempt)
                return entry
        return None

    def _fallback_inspector_candidate(
        self,
        *,
        index: int,
        candidate_id: str,
        role: str,
        provider_hint: str,
        required_capabilities: list[str],
        privacy_mode: str,
        reason: str,
        confidence: float,
        attempt: ModelAttemptTelemetryEntry | None,
        adapter_health: ModelAdapterHealthInfo | None = None,
    ) -> FallbackInspectorCandidate:
        adapter_payload = self._fallback_candidate_adapter_payload(adapter_health)
        if attempt is None:
            return FallbackInspectorCandidate(
                index=index,
                candidate_id=candidate_id,
                role=role,
                provider_hint=provider_hint,
                required_capabilities=required_capabilities,
                privacy_mode=privacy_mode,
                reason=reason,
                confidence=confidence,
                **adapter_payload,
            )

        model_attempt = attempt.attempt
        metadata = model_attempt.metadata if isinstance(model_attempt.metadata, dict) else {}
        return FallbackInspectorCandidate(
            index=index,
            candidate_id=candidate_id or str(metadata.get("candidate_id") or ""),
            role=role,
            provider_hint=provider_hint,
            required_capabilities=required_capabilities,
            privacy_mode=privacy_mode,
            reason=reason,
            confidence=confidence,
            status=model_attempt.status,
            matched_attempt_number=model_attempt.attempt,
            provider_id=model_attempt.provider_id,
            provider_label=model_attempt.provider_label,
            provider_api=model_attempt.provider_api,
            model=model_attempt.model,
            registry_resolved=self._optional_bool(metadata.get("registry_resolved")),
            retryable=model_attempt.retryable,
            input_tokens=model_attempt.input_tokens,
            output_tokens=model_attempt.output_tokens,
            estimated_cost_usd=model_attempt.estimated_cost_usd,
            latency_ms=model_attempt.latency_ms,
            token_estimator_source=self._token_estimator_label(metadata),
            context_window=self._optional_int(metadata.get("context_window")),
            context_window_utilization=self._float_value(metadata.get("context_window_utilization"), None),
            error=model_attempt.error,
            **adapter_payload,
        )

    def _adapter_health_lookup(
        self,
        adapter_health: list[ModelAdapterHealthInfo],
    ) -> dict[str, ModelAdapterHealthInfo]:
        lookup: dict[str, ModelAdapterHealthInfo] = {}
        for health in adapter_health:
            for key in (
                health.provider_id,
                health.provider_label,
                health.model,
                f"{health.api}:{health.model}" if health.api and health.model else "",
            ):
                normalized = self._adapter_health_key(key)
                if normalized and normalized not in lookup:
                    lookup[normalized] = health
        return lookup

    def _candidate_adapter_health(
        self,
        lookup: dict[str, ModelAdapterHealthInfo],
        *,
        attempt: ModelAttemptTelemetryEntry | None,
        provider_hint: str,
    ) -> ModelAdapterHealthInfo | None:
        if not lookup:
            return None

        if attempt is not None:
            model_attempt = attempt.attempt
            for key in (
                model_attempt.provider_id,
                model_attempt.provider_label,
                model_attempt.model,
                f"{model_attempt.provider_api}:{model_attempt.model}"
                if model_attempt.provider_api and model_attempt.model
                else "",
            ):
                health = lookup.get(self._adapter_health_key(key))
                if health is not None:
                    return health

        health = lookup.get(self._adapter_health_key(provider_hint))
        if health is not None:
            return health
        hint = provider_hint.strip().lower()
        if not hint:
            return None
        hint_tokens = {
            token.strip(" ,:;()/\\[]{}").lower()
            for token in hint.replace("-", " ").replace("_", " ").split()
            if len(token.strip(" ,:;()/\\[]{}")) > 3
        }
        for key, health in lookup.items():
            if key and key in hint:
                return health
            if hint_tokens and any(token in key for token in hint_tokens):
                return health
        return None

    def _fallback_candidate_adapter_payload(
        self,
        adapter_health: ModelAdapterHealthInfo | None,
    ) -> dict[str, Any]:
        if adapter_health is None:
            return {}
        return {
            "adapter_status": adapter_health.status,
            "adapter_message": adapter_health.message,
            "adapter_recommendation": adapter_health.recommendation,
            "adapter_secret_env": adapter_health.secret_env,
            "adapter_secret_present": adapter_health.secret_present,
            "adapter_cooldown": adapter_health.cooldown,
            "adapter_preflight_skips": adapter_health.preflight_skips,
            "adapter_recent_failures": adapter_health.recent_failures,
            "adapter_latest_error": adapter_health.latest_error,
        }

    def _adapter_health_key(self, value: str) -> str:
        return value.strip().lower()

    def _legacy_candidate_id(self, index: int, role: str) -> str:
        compact = role.strip().lower().replace(" ", "-") or "route"
        return f"legacy:{index}:{compact}"

    def _fallback_candidate_id(self, role: str) -> str:
        compact = role.strip().lower().replace(" ", "-") or "fallback"
        return f"fallback:{compact}"

    def _fallback_inspector_task_summary(
        self,
        task_plan: TaskPlanInfo | None,
        attempts: list[ModelAttemptTelemetryEntry],
        candidates: list[FallbackInspectorCandidate],
    ) -> str:
        if task_plan is None:
            return "No stored planner payload is available for this task."
        terminal = sum(1 for entry in attempts if self._attempt_status(entry) in {"succeeded", "failed", "canceled"})
        fallback_count = sum(1 for entry in attempts if self._is_fallback_attempt(entry))
        unresolved = sum(1 for candidate in candidates if candidate.registry_resolved is False)
        return (
            f"{task_plan.routing.task_role if task_plan.routing else task_plan.intent} route with "
            f"{len(candidates)} candidate(s), {len(attempts)} attempt(s), "
            f"{terminal} terminal result(s), {fallback_count} fallback attempt(s), "
            f"and {unresolved} unresolved registry match(es)."
        )

    def _fallback_inspector_task_recommendations(
        self,
        task_plan: TaskPlanInfo | None,
        context_budget: ContextBudgetTelemetryEntry | None,
        attempts: list[ModelAttemptTelemetryEntry],
        candidates: list[FallbackInspectorCandidate],
    ) -> list[str]:
        recommendations: list[str] = []
        if task_plan is None:
            recommendations.append("Planner payload is missing; only newer tasks can show candidate-level routing detail.")
        if not attempts:
            recommendations.append("No model attempts were recorded for this task; keep the execution planner before draft generation.")
        if attempts and all(self._attempt_status(entry) in {"planned", "running", "skipped"} for entry in attempts):
            recommendations.append("Attempts are planned-only; enable routed execution to compare observed provider behavior.")
        if any(candidate.registry_resolved is False for candidate in candidates):
            recommendations.append("One or more route candidates did not resolve to configured provider records.")
        if any(candidate.adapter_status == "missing_secret" for candidate in candidates):
            recommendations.append("A matched provider is missing its required secret; set the environment variable before routing to it.")
        if any(candidate.adapter_cooldown for candidate in candidates):
            recommendations.append("A matched provider is cooling down from recent failures; keep it deprioritized until health recovers.")
        if any(candidate.adapter_preflight_skips > 0 for candidate in candidates):
            recommendations.append("Provider preflight skipped one or more candidates; inspect adapter health before adding more retries.")
        if any(self._is_fallback_attempt(entry) for entry in attempts):
            recommendations.append("Fallback attempts were present; inspect the primary provider readiness and retry policy.")
        if any(self._attempt_status(entry) in {"failed", "canceled"} and entry.attempt.retryable for entry in attempts):
            recommendations.append("Retryable failures exist; temporarily deprioritize unstable providers in routing policy.")
        if context_budget is not None:
            utilization = self._context_budget_utilization(context_budget)
            if utilization is not None and utilization > 0.72:
                recommendations.append("Context budget utilization is high; add compression before widening fallback chains.")
        if not recommendations:
            recommendations.append("Route candidates and attempts are aligned for this task.")
        return recommendations[:5]

    def _fallback_inspector_recommendations(self, tasks: list[FallbackInspectorTask]) -> list[str]:
        if not tasks:
            return ["No fallback inspection data is available yet."]

        unresolved_count = sum(
            1 for task in tasks for candidate in task.candidates if candidate.registry_resolved is False
        )
        fallback_task_count = sum(
            1 for task in tasks if any(self._is_fallback_attempt(entry) for entry in task.attempts)
        )
        planned_only_count = sum(
            1
            for task in tasks
            if task.attempts and all(self._attempt_status(entry) in {"planned", "running", "skipped"} for entry in task.attempts)
        )
        high_context_count = sum(
            1
            for task in tasks
            if task.context_budget is not None
            and (self._context_budget_utilization(task.context_budget) or 0.0) > 0.72
        )
        missing_secret_count = sum(
            1 for task in tasks for candidate in task.candidates if candidate.adapter_status == "missing_secret"
        )
        cooldown_count = sum(1 for task in tasks for candidate in task.candidates if candidate.adapter_cooldown)

        recommendations: list[str] = []
        if unresolved_count:
            recommendations.append(
                f"{unresolved_count} candidate route(s) did not resolve to configured providers; tighten registry roles and aliases."
            )
        if missing_secret_count:
            recommendations.append(
                f"{missing_secret_count} matched route candidate(s) are blocked by missing provider secrets."
            )
        if cooldown_count:
            recommendations.append(f"{cooldown_count} matched route candidate(s) are in provider cooldown.")
        if fallback_task_count:
            recommendations.append(
                f"{fallback_task_count} recent task(s) used fallback attempts; inspect primary provider health before expanding execution."
            )
        if planned_only_count:
            recommendations.append(
                f"{planned_only_count} recent task(s) are planned-only; live execution telemetry is needed before policy automation."
            )
        if high_context_count:
            recommendations.append(
                f"{high_context_count} recent task(s) exceeded 72% context utilization; prioritize compression and retrieval tuning."
            )
        if not recommendations:
            recommendations.append("Recent route candidates, fallback roles, and attempts are aligned enough for desktop inspector UI work.")
        return recommendations[:6]

    def _route_quality_overview(
        self,
        context_budgets: list[ContextBudgetTelemetryEntry],
        model_attempts: list[ModelAttemptTelemetryEntry],
        feedback_events: list[FeedbackTelemetryEntry],
    ) -> RouteQualityOverview:
        task_ids = {entry.task_id for entry in context_budgets}
        task_ids.update(entry.task_id for entry in model_attempts)
        task_ids.update(entry.task_id for entry in feedback_events if entry.task_id)
        successes = sum(1 for entry in model_attempts if self._attempt_status(entry) == "succeeded")
        failures = sum(1 for entry in model_attempts if self._attempt_status(entry) in {"failed", "canceled"})
        planned = sum(1 for entry in model_attempts if self._attempt_status(entry) in {"planned", "running", "skipped"})
        fallback_attempts = sum(1 for entry in model_attempts if self._is_fallback_attempt(entry))
        retryable_failures = sum(
            1
            for entry in model_attempts
            if self._attempt_status(entry) in {"failed", "canceled"} and entry.attempt.retryable
        )
        cost = sum(self._float_value(entry.attempt.estimated_cost_usd) for entry in model_attempts)
        input_tokens = sum(self._int_value(entry.attempt.input_tokens) for entry in model_attempts)
        output_tokens = sum(self._int_value(entry.attempt.output_tokens) for entry in model_attempts)
        latencies = [entry.attempt.latency_ms for entry in model_attempts if entry.attempt.latency_ms is not None]
        utilizations = [
            self._float_value(entry.attempt.metadata.get("context_window_utilization"), None)
            for entry in model_attempts
            if isinstance(entry.attempt.metadata, dict)
        ]
        utilizations = [value for value in utilizations if value is not None]
        context_utilizations = [
            self._context_budget_utilization(entry)
            for entry in context_budgets
        ]
        context_utilizations = [value for value in context_utilizations if value is not None]
        all_utilizations = utilizations or context_utilizations
        success_rate = self._rate(successes, successes + failures)
        fallback_rate = self._rate(fallback_attempts, len(model_attempts))
        average_context_utilization = self._average(all_utilizations)
        feedback_summary = self._feedback_summary(feedback_events)
        preview_metrics = [
            preview
            for entry in model_attempts
            if (preview := self._structured_preview_metrics(entry.attempt.metadata)) is not None and preview["emitted"]
        ]
        structured_preview_attempts = len(preview_metrics)
        structured_preview_retired_attempts = sum(1 for preview in preview_metrics if preview["retired"])
        structured_preview_reset_count = sum(int(preview["reset_count"]) for preview in preview_metrics)
        structured_preview_final_winners = sum(1 for preview in preview_metrics if preview["final_winner"])

        return RouteQualityOverview(
            task_count=len(task_ids),
            context_budget_count=len(context_budgets),
            model_attempt_count=len(model_attempts),
            succeeded_attempts=successes,
            failed_attempts=failures,
            planned_attempts=planned,
            fallback_attempts=fallback_attempts,
            retryable_failures=retryable_failures,
            success_rate=success_rate,
            fallback_rate=fallback_rate,
            estimated_cost_usd=round(cost, 6),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            average_latency_ms=self._average(latencies),
            average_context_utilization=average_context_utilization,
            average_context_tokens=self._average([entry.estimated_context_tokens for entry in context_budgets]) or 0.0,
            average_selected_files=self._average([entry.selected_file_count for entry in context_budgets]) or 0.0,
            average_omitted_files=self._average([entry.omitted_file_count for entry in context_budgets]) or 0.0,
            reliability_score=self._reliability_score(
                success_rate,
                fallback_rate,
                average_context_utilization,
                feedback_summary.positive_rate,
                feedback_summary.negative_rate,
            ),
            feedback_count=feedback_summary.feedback_count,
            positive_feedback=feedback_summary.positive_count,
            negative_feedback=feedback_summary.negative_count,
            revised_feedback=feedback_summary.revised_count,
            regenerated_feedback=feedback_summary.regenerated_count,
            applied_feedback=feedback_summary.applied_count,
            rolled_back_feedback=feedback_summary.rolled_back_count,
            corrected_feedback=feedback_summary.corrected_count,
            positive_feedback_rate=feedback_summary.positive_rate,
            negative_feedback_rate=feedback_summary.negative_rate,
            structured_preview_attempts=structured_preview_attempts,
            structured_preview_retired_attempts=structured_preview_retired_attempts,
            structured_preview_reset_count=structured_preview_reset_count,
            structured_preview_final_winners=structured_preview_final_winners,
            structured_preview_retired_rate=self._rate(
                structured_preview_retired_attempts,
                structured_preview_attempts,
            ),
        )

    def _route_quality_provider_rollups(
        self,
        model_attempts: list[ModelAttemptTelemetryEntry],
    ) -> list[RouteQualityProviderRollup]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in model_attempts:
            attempt = entry.attempt
            provider_id = attempt.provider_id or attempt.provider_label or attempt.provider_api or "unknown"
            model = attempt.model or "unspecified"
            key = (provider_id, model)
            group = groups.setdefault(
                key,
                {
                    "provider_id": provider_id,
                    "provider_label": attempt.provider_label or provider_id,
                    "provider_api": attempt.provider_api,
                    "model": model,
                    "tasks": set(),
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "planned": 0,
                    "fallback_attempts": 0,
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latencies": [],
                    "utilizations": [],
                    "token_estimator_sources": set(),
                },
            )
            group["tasks"].add(entry.task_id)
            group["attempts"] += 1
            status = self._attempt_status(entry)
            if status == "succeeded":
                group["successes"] += 1
            elif status in {"failed", "canceled"}:
                group["failures"] += 1
            elif status in {"planned", "running", "skipped"}:
                group["planned"] += 1
            if self._is_fallback_attempt(entry):
                group["fallback_attempts"] += 1
            group["cost"] += self._float_value(attempt.estimated_cost_usd)
            group["input_tokens"] += self._int_value(attempt.input_tokens)
            group["output_tokens"] += self._int_value(attempt.output_tokens)
            if attempt.latency_ms is not None:
                group["latencies"].append(attempt.latency_ms)
            utilization = self._float_value(attempt.metadata.get("context_window_utilization"), None)
            if utilization is not None:
                group["utilizations"].append(utilization)
            estimator = self._token_estimator_label(attempt.metadata)
            if estimator:
                group["token_estimator_sources"].add(estimator)

        rollups: list[RouteQualityProviderRollup] = []
        for group in groups.values():
            attempts = int(group["attempts"])
            successes = int(group["successes"])
            failures = int(group["failures"])
            rollups.append(
                RouteQualityProviderRollup(
                    provider_id=str(group["provider_id"]),
                    provider_label=str(group["provider_label"]),
                    provider_api=str(group["provider_api"]),
                    model=str(group["model"]),
                    task_count=len(group["tasks"]),
                    attempts=attempts,
                    successes=successes,
                    failures=failures,
                    planned=int(group["planned"]),
                    fallback_attempts=int(group["fallback_attempts"]),
                    success_rate=self._rate(successes, successes + failures),
                    fallback_rate=self._rate(int(group["fallback_attempts"]), attempts),
                    estimated_cost_usd=round(float(group["cost"]), 6),
                    input_tokens=int(group["input_tokens"]),
                    output_tokens=int(group["output_tokens"]),
                    average_latency_ms=self._average(group["latencies"]),
                    average_context_utilization=self._average(group["utilizations"]),
                    token_estimator_sources=sorted(group["token_estimator_sources"]),
                )
            )
        return sorted(rollups, key=lambda item: (item.attempts, item.success_rate), reverse=True)

    def _route_quality_token_calibration_rollups(
        self,
        model_attempts: list[ModelAttemptTelemetryEntry],
    ) -> list[RouteQualityTokenCalibrationRollup]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in model_attempts:
            attempt = entry.attempt
            provider_id = attempt.provider_id or attempt.provider_label or attempt.provider_api or "unknown"
            model = attempt.model or "unspecified"
            key = (provider_id, model)
            group = groups.setdefault(
                key,
                {
                    "provider_id": provider_id,
                    "provider_label": attempt.provider_label or provider_id,
                    "provider_api": attempt.provider_api,
                    "model": model,
                    "attempts": 0,
                    "calibrated_attempts": 0,
                    "estimated_input_tokens": 0,
                    "reported_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "reported_output_tokens": 0,
                    "input_errors": [],
                    "output_errors": [],
                    "token_estimator_sources": set(),
                    "reported_token_sources": set(),
                },
            )
            group["attempts"] += 1
            metadata = attempt.metadata if isinstance(attempt.metadata, dict) else {}
            estimator = self._token_estimator_label(metadata)
            if estimator:
                group["token_estimator_sources"].add(estimator)
            reported_source = str(metadata.get("reported_token_source") or "").strip()
            if reported_source:
                group["reported_token_sources"].add(reported_source)

            estimated_input = self._token_metadata_int(
                metadata,
                ("estimated_input_tokens", "planned_input_tokens", "input_token_estimate", "estimated_prompt_tokens"),
            )
            estimated_output = self._token_metadata_int(
                metadata,
                (
                    "estimated_output_tokens",
                    "reserved_response_tokens",
                    "planned_output_tokens",
                    "output_token_estimate",
                    "estimated_completion_tokens",
                ),
            )
            if estimated_input is None:
                estimated_input = self._optional_positive_int(attempt.input_tokens)
            if estimated_output is None:
                estimated_output = self._optional_positive_int(attempt.output_tokens)

            reported_input = self._token_metadata_int(
                metadata,
                ("reported_input_tokens", "actual_input_tokens", "provider_input_tokens", "prompt_tokens"),
            )
            reported_output = self._token_metadata_int(
                metadata,
                ("reported_output_tokens", "actual_output_tokens", "provider_output_tokens", "completion_tokens"),
            )
            input_error = self._token_relative_error(estimated_input, reported_input)
            output_error = self._token_relative_error(estimated_output, reported_output)
            if input_error is not None or output_error is not None:
                group["calibrated_attempts"] += 1
            if input_error is not None:
                group["input_errors"].append(input_error)
                group["estimated_input_tokens"] += estimated_input or 0
                group["reported_input_tokens"] += reported_input or 0
            if output_error is not None:
                group["output_errors"].append(output_error)
                group["estimated_output_tokens"] += estimated_output or 0
                group["reported_output_tokens"] += reported_output or 0

        rollups: list[RouteQualityTokenCalibrationRollup] = []
        for group in groups.values():
            average_input_error = self._average(group["input_errors"])
            average_output_error = self._average(group["output_errors"])
            worst_input_error = max(group["input_errors"]) if group["input_errors"] else None
            worst_output_error = max(group["output_errors"]) if group["output_errors"] else None
            status = self._token_calibration_status(
                calibrated_attempts=int(group["calibrated_attempts"]),
                average_input_error=average_input_error,
                average_output_error=average_output_error,
                worst_input_error=worst_input_error,
                worst_output_error=worst_output_error,
            )
            rollups.append(
                RouteQualityTokenCalibrationRollup(
                    provider_id=str(group["provider_id"]),
                    provider_label=str(group["provider_label"]),
                    provider_api=str(group["provider_api"]),
                    model=str(group["model"]),
                    attempts=int(group["attempts"]),
                    calibrated_attempts=int(group["calibrated_attempts"]),
                    calibration_status=status,
                    estimated_input_tokens=int(group["estimated_input_tokens"]),
                    reported_input_tokens=int(group["reported_input_tokens"]),
                    estimated_output_tokens=int(group["estimated_output_tokens"]),
                    reported_output_tokens=int(group["reported_output_tokens"]),
                    average_input_token_error=average_input_error,
                    worst_input_token_error=worst_input_error,
                    average_output_token_error=average_output_error,
                    worst_output_token_error=worst_output_error,
                    token_estimator_sources=sorted(group["token_estimator_sources"]),
                    reported_token_sources=sorted(group["reported_token_sources"]),
                    recommendation=self._token_calibration_recommendation(
                        status=status,
                        provider_label=str(group["provider_label"]),
                        calibrated_attempts=int(group["calibrated_attempts"]),
                        average_input_error=average_input_error,
                        average_output_error=average_output_error,
                        reported_sources=sorted(group["reported_token_sources"]),
                    ),
                )
            )
        status_rank = {"drift": 0, "watch": 1, "insufficient": 2, "stable": 3}
        return sorted(
            rollups,
            key=lambda item: (
                status_rank.get(item.calibration_status, 2),
                -item.calibrated_attempts,
                -item.attempts,
            ),
        )

    def _route_quality_token_calibration_trends(
        self,
        model_attempts: list[ModelAttemptTelemetryEntry],
        max_buckets: int = 18,
    ) -> list[RouteQualityTokenCalibrationTrendBucket]:
        groups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for entry in model_attempts:
            attempt = entry.attempt
            metadata = attempt.metadata if isinstance(attempt.metadata, dict) else {}
            provider_id = attempt.provider_id or attempt.provider_label or attempt.provider_api or "unknown"
            model = attempt.model or "unspecified"
            period_start = self._feedback_period_start(entry.created_at)
            key = (provider_id, model, period_start)
            group = groups.setdefault(
                key,
                {
                    "provider_id": provider_id,
                    "provider_label": attempt.provider_label or provider_id,
                    "provider_api": attempt.provider_api,
                    "model": model,
                    "period_start": period_start,
                    "attempts": 0,
                    "calibrated_attempts": 0,
                    "estimated_input_tokens": 0,
                    "reported_input_tokens": 0,
                    "estimated_output_tokens": 0,
                    "reported_output_tokens": 0,
                    "input_errors": [],
                    "output_errors": [],
                },
            )
            group["attempts"] += 1

            estimated_input = self._token_metadata_int(
                metadata,
                ("estimated_input_tokens", "planned_input_tokens", "input_token_estimate", "estimated_prompt_tokens"),
            )
            estimated_output = self._token_metadata_int(
                metadata,
                (
                    "estimated_output_tokens",
                    "reserved_response_tokens",
                    "planned_output_tokens",
                    "output_token_estimate",
                    "estimated_completion_tokens",
                ),
            )
            if estimated_input is None:
                estimated_input = self._optional_positive_int(attempt.input_tokens)
            if estimated_output is None:
                estimated_output = self._optional_positive_int(attempt.output_tokens)

            reported_input = self._token_metadata_int(
                metadata,
                ("reported_input_tokens", "actual_input_tokens", "provider_input_tokens", "prompt_tokens"),
            )
            reported_output = self._token_metadata_int(
                metadata,
                ("reported_output_tokens", "actual_output_tokens", "provider_output_tokens", "completion_tokens"),
            )
            input_error = self._token_relative_error(estimated_input, reported_input)
            output_error = self._token_relative_error(estimated_output, reported_output)
            if input_error is not None or output_error is not None:
                group["calibrated_attempts"] += 1
            if input_error is not None:
                group["input_errors"].append(input_error)
                group["estimated_input_tokens"] += estimated_input or 0
                group["reported_input_tokens"] += reported_input or 0
            if output_error is not None:
                group["output_errors"].append(output_error)
                group["estimated_output_tokens"] += estimated_output or 0
                group["reported_output_tokens"] += reported_output or 0

        buckets_by_provider: dict[tuple[str, str], list[RouteQualityTokenCalibrationTrendBucket]] = {}
        for group in groups.values():
            average_input_error = self._average(group["input_errors"])
            average_output_error = self._average(group["output_errors"])
            worst_input_error = max(group["input_errors"]) if group["input_errors"] else None
            worst_output_error = max(group["output_errors"]) if group["output_errors"] else None
            status = self._token_calibration_status(
                calibrated_attempts=int(group["calibrated_attempts"]),
                average_input_error=average_input_error,
                average_output_error=average_output_error,
                worst_input_error=worst_input_error,
                worst_output_error=worst_output_error,
            )
            bucket = RouteQualityTokenCalibrationTrendBucket(
                provider_id=str(group["provider_id"]),
                provider_label=str(group["provider_label"]),
                provider_api=str(group["provider_api"]),
                model=str(group["model"]),
                period_start=str(group["period_start"]),
                attempts=int(group["attempts"]),
                calibrated_attempts=int(group["calibrated_attempts"]),
                calibration_status=status,
                estimated_input_tokens=int(group["estimated_input_tokens"]),
                reported_input_tokens=int(group["reported_input_tokens"]),
                estimated_output_tokens=int(group["estimated_output_tokens"]),
                reported_output_tokens=int(group["reported_output_tokens"]),
                average_input_token_error=average_input_error,
                worst_input_token_error=worst_input_error,
                average_output_token_error=average_output_error,
                worst_output_token_error=worst_output_error,
            )
            buckets_by_provider.setdefault((bucket.provider_id, bucket.model), []).append(bucket)

        buckets: list[RouteQualityTokenCalibrationTrendBucket] = []
        for provider_buckets in buckets_by_provider.values():
            provider_buckets.sort(key=lambda bucket: bucket.period_start)
            previous_error: float | None = None
            for bucket in provider_buckets:
                current_error = max(bucket.average_input_token_error or 0.0, bucket.average_output_token_error or 0.0)
                if bucket.calibrated_attempts <= 0:
                    bucket.trend_direction = "insufficient"
                elif previous_error is None:
                    bucket.trend_direction = "baseline"
                else:
                    delta = current_error - previous_error
                    if delta <= -0.03:
                        bucket.trend_direction = "improving"
                    elif delta >= 0.03:
                        bucket.trend_direction = "worsening"
                    else:
                        bucket.trend_direction = "flat"
                bucket.recommendation = self._token_calibration_trend_recommendation(bucket)
                if bucket.calibrated_attempts > 0:
                    previous_error = current_error
                buckets.append(bucket)

        status_rank = {"drift": 0, "watch": 1, "insufficient": 2, "stable": 3}
        return sorted(
            buckets,
            key=lambda item: (
                item.period_start,
                -status_rank.get(item.calibration_status, 2),
                item.calibrated_attempts,
            ),
            reverse=True,
        )[: max(1, max_buckets)]

    def _route_quality_structured_preview_rollups(
        self,
        model_attempts: list[ModelAttemptTelemetryEntry],
    ) -> list[RouteQualityStructuredPreviewRollup]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in model_attempts:
            attempt = entry.attempt
            preview = self._structured_preview_metrics(attempt.metadata)
            if preview is None or not preview["emitted"]:
                continue
            provider_id = attempt.provider_id or attempt.provider_label or attempt.provider_api or "unknown"
            model = attempt.model or "unspecified"
            key = (provider_id, model)
            group = groups.setdefault(
                key,
                {
                    "provider_id": provider_id,
                    "provider_label": attempt.provider_label or provider_id,
                    "provider_api": attempt.provider_api,
                    "model": model,
                    "attempts": 0,
                    "previewed_attempts": 0,
                    "final_winning_attempts": 0,
                    "retired_attempts": 0,
                    "reset_count": 0,
                    "delta_count": 0,
                    "char_count": 0,
                    "retired_reasons": set(),
                },
            )
            group["attempts"] += 1
            group["previewed_attempts"] += 1
            group["delta_count"] += int(preview["delta_count"])
            group["char_count"] += int(preview["char_count"])
            group["reset_count"] += int(preview["reset_count"])
            if preview["final_winner"]:
                group["final_winning_attempts"] += 1
            if preview["retired"]:
                group["retired_attempts"] += 1
            reason = str(preview["retired_reason"] or "").strip()
            if reason:
                group["retired_reasons"].add(reason)

        rollups: list[RouteQualityStructuredPreviewRollup] = []
        for group in groups.values():
            previewed = int(group["previewed_attempts"])
            retired = int(group["retired_attempts"])
            final_winners = int(group["final_winning_attempts"])
            reset_count = int(group["reset_count"])
            preview_success_rate = self._rate(final_winners, previewed)
            retired_rate = self._rate(retired, previewed)
            average_preview_chars = round(int(group["char_count"]) / previewed, 2) if previewed else 0.0
            status = self._structured_preview_status(
                previewed_attempts=previewed,
                final_winning_attempts=final_winners,
                retired_attempts=retired,
                reset_count=reset_count,
            )
            rollups.append(
                RouteQualityStructuredPreviewRollup(
                    provider_id=str(group["provider_id"]),
                    provider_label=str(group["provider_label"]),
                    provider_api=str(group["provider_api"]),
                    model=str(group["model"]),
                    attempts=int(group["attempts"]),
                    previewed_attempts=previewed,
                    final_winning_attempts=final_winners,
                    retired_attempts=retired,
                    reset_count=reset_count,
                    delta_count=int(group["delta_count"]),
                    char_count=int(group["char_count"]),
                    preview_success_rate=preview_success_rate,
                    retired_rate=retired_rate,
                    average_preview_chars=average_preview_chars,
                    preview_status=status,
                    retired_reasons=sorted(group["retired_reasons"]),
                    recommendation=self._structured_preview_recommendation(
                        status=status,
                        provider_label=str(group["provider_label"]),
                        previewed_attempts=previewed,
                        final_winning_attempts=final_winners,
                        retired_attempts=retired,
                        reset_count=reset_count,
                    ),
                )
            )
        status_rank = {"unstable": 0, "watch": 1, "insufficient": 2, "stable": 3}
        return sorted(
            rollups,
            key=lambda item: (
                status_rank.get(item.preview_status, 2),
                -item.reset_count,
                -item.retired_attempts,
                -item.previewed_attempts,
            ),
        )

    def _route_quality_role_rollups(
        self,
        model_attempts: list[ModelAttemptTelemetryEntry],
    ) -> list[RouteQualityRoleRollup]:
        groups: dict[str, dict[str, Any]] = {}
        for entry in model_attempts:
            role = entry.attempt.role or "unknown"
            group = groups.setdefault(
                role,
                {
                    "tasks": set(),
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "planned": 0,
                    "fallback_attempts": 0,
                    "cost": 0.0,
                    "latencies": [],
                },
            )
            group["tasks"].add(entry.task_id)
            group["attempts"] += 1
            status = self._attempt_status(entry)
            if status == "succeeded":
                group["successes"] += 1
            elif status in {"failed", "canceled"}:
                group["failures"] += 1
            elif status in {"planned", "running", "skipped"}:
                group["planned"] += 1
            if self._is_fallback_attempt(entry):
                group["fallback_attempts"] += 1
            group["cost"] += self._float_value(entry.attempt.estimated_cost_usd)
            if entry.attempt.latency_ms is not None:
                group["latencies"].append(entry.attempt.latency_ms)

        rollups: list[RouteQualityRoleRollup] = []
        for role, group in groups.items():
            successes = int(group["successes"])
            failures = int(group["failures"])
            rollups.append(
                RouteQualityRoleRollup(
                    role=role,
                    task_count=len(group["tasks"]),
                    attempts=int(group["attempts"]),
                    successes=successes,
                    failures=failures,
                    planned=int(group["planned"]),
                    fallback_attempts=int(group["fallback_attempts"]),
                    success_rate=self._rate(successes, successes + failures),
                    estimated_cost_usd=round(float(group["cost"]), 6),
                    average_latency_ms=self._average(group["latencies"]),
                )
            )
        return sorted(rollups, key=lambda item: (item.attempts, item.success_rate), reverse=True)

    def _route_quality_context_rollups(
        self,
        context_budgets: list[ContextBudgetTelemetryEntry],
    ) -> list[RouteQualityContextRollup]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for entry in context_budgets:
            route_role = entry.route_role or entry.payload.route_role or "unknown"
            intent = entry.intent or entry.payload.intent or "unknown"
            key = (route_role, intent)
            group = groups.setdefault(
                key,
                {
                    "count": 0,
                    "context_tokens": [],
                    "file_tokens": [],
                    "reserved_tokens": [],
                    "selected_files": [],
                    "omitted_files": [],
                    "utilizations": [],
                },
            )
            group["count"] += 1
            group["context_tokens"].append(entry.estimated_context_tokens)
            group["file_tokens"].append(entry.estimated_file_tokens)
            group["reserved_tokens"].append(entry.reserve_response_tokens)
            group["selected_files"].append(entry.selected_file_count)
            group["omitted_files"].append(entry.omitted_file_count)
            utilization = self._context_budget_utilization(entry)
            if utilization is not None:
                group["utilizations"].append(utilization)

        rollups: list[RouteQualityContextRollup] = []
        for (route_role, intent), group in groups.items():
            rollups.append(
                RouteQualityContextRollup(
                    route_role=route_role,
                    intent=intent,
                    budget_count=int(group["count"]),
                    average_context_tokens=self._average(group["context_tokens"]) or 0.0,
                    average_file_tokens=self._average(group["file_tokens"]) or 0.0,
                    average_reserved_response_tokens=self._average(group["reserved_tokens"]) or 0.0,
                    average_selected_files=self._average(group["selected_files"]) or 0.0,
                    average_omitted_files=self._average(group["omitted_files"]) or 0.0,
                    average_budget_utilization=self._average(group["utilizations"]),
                )
            )
        return sorted(rollups, key=lambda item: item.budget_count, reverse=True)

    def _route_quality_context_drilldowns(
        self,
        context_budgets: list[ContextBudgetTelemetryEntry],
    ) -> list[RouteQualityContextDrilldown]:
        drilldowns = [
            self._route_quality_context_drilldown(entry)
            for entry in sorted(context_budgets, key=lambda item: item.created_at, reverse=True)
        ]
        return sorted(
            drilldowns,
            key=lambda item: (
                item.utilization if item.utilization is not None else -1.0,
                item.omitted_file_count + item.omitted_memory_count + item.omitted_project_memory_count,
                item.estimated_context_tokens,
            ),
            reverse=True,
        )[:12]

    def _route_quality_context_drilldown(
        self,
        entry: ContextBudgetTelemetryEntry,
    ) -> RouteQualityContextDrilldown:
        payload = entry.payload
        selected_items = [item for item in payload.items if item.included]
        omitted_items = [item for item in payload.items if not item.included]
        largest_items = sorted(payload.items, key=lambda item: item.estimated_tokens, reverse=True)
        utilization = self._context_budget_utilization(entry)
        recommendations = self._context_drilldown_recommendations(entry, selected_items, omitted_items, utilization)
        return RouteQualityContextDrilldown(
            task_id=entry.task_id,
            created_at=entry.created_at,
            route_role=entry.route_role or payload.route_role,
            intent=entry.intent or payload.intent,
            strategy=entry.strategy or payload.strategy,
            privacy_mode=entry.privacy_mode or payload.privacy_mode,
            max_context_tokens=entry.max_context_tokens or payload.max_context_tokens,
            estimated_context_tokens=entry.estimated_context_tokens or payload.estimated_context_tokens,
            estimated_file_tokens=entry.estimated_file_tokens or payload.estimated_file_tokens,
            reserve_response_tokens=entry.reserve_response_tokens or payload.reserve_response_tokens,
            utilization=utilization,
            selected_file_count=entry.selected_file_count or payload.selected_file_count,
            omitted_file_count=entry.omitted_file_count or payload.omitted_file_count,
            selected_memory_count=payload.selected_memory_count,
            omitted_memory_count=payload.omitted_memory_count,
            selected_project_memory_count=payload.selected_project_memory_count,
            omitted_project_memory_count=payload.omitted_project_memory_count,
            selected_refs=[self._context_item_label(item) for item in selected_items[:8]],
            omitted_refs=[self._context_item_label(item) for item in omitted_items[:8]],
            largest_refs=[self._context_item_label(item) for item in largest_items[:6]],
            notes=payload.notes[:6],
            recommendations=recommendations,
        )

    def _context_item_label(self, item: Any) -> str:
        ref = str(getattr(item, "ref", "") or "")
        kind = str(getattr(item, "kind", "") or "item")
        tokens = int(getattr(item, "estimated_tokens", 0) or 0)
        reason = str(getattr(item, "reason", "") or "")
        label = f"{kind}: {ref}" if ref else kind
        if tokens > 0:
            label += f" ({tokens} tokens)"
        if reason:
            label += f" - {reason}"
        return label

    def _context_drilldown_recommendations(
        self,
        entry: ContextBudgetTelemetryEntry,
        selected_items: list[Any],
        omitted_items: list[Any],
        utilization: float | None,
    ) -> list[str]:
        recommendations: list[str] = []
        if utilization is not None and utilization >= 0.82:
            recommendations.append("Context utilization is very high; summarize older turns or narrow selected files before widening model fallbacks.")
        elif utilization is not None and utilization >= 0.68:
            recommendations.append("Context utilization is elevated; prefer targeted search and smaller file snippets for this route.")
        omitted_total = (
            (entry.omitted_file_count or entry.payload.omitted_file_count)
            + entry.payload.omitted_memory_count
            + entry.payload.omitted_project_memory_count
        )
        if omitted_total:
            recommendations.append(f"{omitted_total} context item(s) were omitted; inspect omitted refs before assuming the model saw everything.")
        if selected_items:
            largest = max(selected_items, key=lambda item: getattr(item, "estimated_tokens", 0) or 0)
            if (getattr(largest, "estimated_tokens", 0) or 0) >= 1200:
                recommendations.append("A large selected item dominates the budget; split or summarize it for better multi-file reasoning.")
        if not recommendations and not omitted_items:
            recommendations.append("Context selection is comfortably inside budget for this route.")
        return recommendations[:4]

    def _route_quality_recommendations(
        self,
        overview: RouteQualityOverview,
        providers: list[RouteQualityProviderRollup],
        contexts: list[RouteQualityContextRollup],
        token_calibration: list[RouteQualityTokenCalibrationRollup],
        structured_preview: list[RouteQualityStructuredPreviewRollup],
    ) -> list[str]:
        if overview.model_attempt_count == 0 and overview.context_budget_count == 0 and overview.feedback_count == 0:
            return ["No route telemetry exists yet for this workspace; run a planned chat turn to seed rollups."]

        recommendations: list[str] = []
        terminal_attempts = overview.succeeded_attempts + overview.failed_attempts
        if overview.model_attempt_count > 0 and terminal_attempts == 0:
            recommendations.append("Route telemetry is still planned-only; enable live routed execution or wait for completed attempts before treating reliability as observed quality.")
        if overview.failed_attempts > 0 and overview.success_rate < 0.80:
            recommendations.append("Prioritize provider health checks because terminal model attempts are below an 80% success rate.")
        if overview.fallback_rate > 0.25:
            recommendations.append("Review fallback policy and primary-provider readiness because more than 25% of attempts are fallback attempts.")
        if overview.retryable_failures > 0:
            recommendations.append("Retryable provider failures exist; route policy can use them to avoid unstable providers until health recovers.")
        if overview.feedback_count == 0:
            recommendations.append("No user feedback is attached yet; collect accepted/rejected/regenerated/applied outcomes before tuning route policy.")
        elif overview.negative_feedback_rate >= 0.30:
            recommendations.append("User rejection feedback is elevated; review affected task routes before promoting those providers.")
        elif overview.positive_feedback_rate >= 0.70:
            recommendations.append("Positive feedback is strong enough to start comparing provider and role policy changes against observed outcomes.")
        if overview.average_context_utilization is not None and overview.average_context_utilization > 0.72:
            recommendations.append("Context utilization is high; add compression or stricter file selection before increasing model context windows.")
        if any(context.average_omitted_files > context.average_selected_files for context in contexts):
            recommendations.append("Some routes omit more files than they include; semantic retrieval or per-route snippet compression should come next.")
        calibrated = [item for item in token_calibration if item.calibrated_attempts > 0]
        if overview.model_attempt_count > 0 and not calibrated:
            recommendations.append("Provider token calibration has not started yet; capture provider-reported usage before trusting tight token budgets.")
        drifted = next((item for item in token_calibration if item.calibration_status == "drift"), None)
        if drifted is not None:
            recommendations.append(
                f"Token estimates for {drifted.provider_label or drifted.provider_id} are drifting from reported usage; tune estimator profile before widening context."
            )
        watched = next((item for item in token_calibration if item.calibration_status == "watch"), None)
        if drifted is None and watched is not None:
            recommendations.append(
                f"Token estimates for {watched.provider_label or watched.provider_id} need more samples before route-policy automation uses cost and context signals."
            )

        unstable_preview = next((item for item in structured_preview if item.preview_status == "unstable"), None)
        if unstable_preview is not None:
            recommendations.append(
                f"Structured preview resets are elevated for {unstable_preview.provider_label or unstable_preview.provider_id}; route policy should keep a stronger fallback ahead of it for coding/build streams."
            )
        watched_preview = next((item for item in structured_preview if item.preview_status == "watch"), None)
        if unstable_preview is None and watched_preview is not None:
            recommendations.append(
                f"Structured preview reliability for {watched_preview.provider_label or watched_preview.provider_id} needs more samples before promotion."
            )

        weak_provider = next((provider for provider in providers if provider.failures > 0 and provider.success_rate < 0.70), None)
        if weak_provider is not None:
            recommendations.append(
                f"Investigate {weak_provider.provider_label or weak_provider.provider_id}; its recent success rate is below 70%."
            )

        if not recommendations:
            recommendations.append("Route telemetry is healthy enough for the next expansion: richer candidate inspection and streaming contracts.")
        return recommendations[:6]

    def _route_health_policy(
        self,
        *,
        terminal_attempts: int,
        failures: int,
        success_rate: float,
        failure_rate: float,
        average_latency_ms: float | None,
        structured_preview_attempts: int = 0,
        structured_preview_retired_attempts: int = 0,
        structured_preview_reset_count: int = 0,
        structured_preview_final_winners: int = 0,
    ) -> tuple[float, bool, str]:
        penalty = 0.0
        cooldown = False
        reasons: list[str] = []

        if terminal_attempts < 2:
            reasons.append("Insufficient terminal attempts for automatic demotion.")
        elif failures >= 2 and success_rate <= 0.50:
            penalty += 6000.0
            cooldown = True
            reasons.append(
                f"Cooldown active after {failures} failure(s) across {terminal_attempts} recent terminal attempt(s)."
            )
        elif failures >= 2 and failure_rate >= 0.50:
            penalty += 2400.0
            reasons.append(f"Strong demotion after a {failure_rate:.0%} recent failure rate.")
        elif failures >= 1 and failure_rate >= 0.34:
            penalty += 900.0
            reasons.append(f"Light demotion after a {failure_rate:.0%} recent failure rate.")
        else:
            reasons.append("Recent terminal attempts are healthy enough for normal routing.")

        if average_latency_ms is not None and average_latency_ms >= 60_000:
            penalty += 600.0
            reasons.append("Average latency is above 60 seconds.")
        elif average_latency_ms is not None and average_latency_ms >= 30_000:
            penalty += 250.0
            reasons.append("Average latency is above 30 seconds.")

        if structured_preview_attempts >= 2:
            retired_rate = self._rate(structured_preview_retired_attempts, structured_preview_attempts)
            final_winner_rate = self._rate(structured_preview_final_winners, structured_preview_attempts)
            if retired_rate >= 0.75 and structured_preview_reset_count >= 2:
                penalty += 1400.0
                reasons.append(
                    f"Structured preview reliability is poor after {structured_preview_reset_count} reset(s)."
                )
            elif retired_rate >= 0.40 or structured_preview_reset_count >= 2:
                penalty += 700.0
                reasons.append(
                    f"Structured previews were retired for {structured_preview_retired_attempts}/{structured_preview_attempts} attempt(s)."
                )
            elif structured_preview_reset_count > 0:
                penalty += 250.0
                reasons.append("Structured preview reset telemetry is present; keep this route under observation.")
            if final_winner_rate <= 0.25 and structured_preview_attempts >= 3:
                penalty += 500.0
                reasons.append("Few structured previews became the final selected response.")

        return penalty, cooldown, " ".join(reasons)

    def _feedback_summary(self, events: list[FeedbackTelemetryEntry]) -> FeedbackTelemetrySummary:
        positive_sentiments = {"liked", "accepted", "copied"}
        negative_sentiments = {"disliked", "rejected"}
        positive = sum(1 for event in events if event.sentiment in positive_sentiments)
        negative = sum(1 for event in events if event.sentiment in negative_sentiments)
        return FeedbackTelemetrySummary(
            feedback_count=len(events),
            positive_count=positive,
            negative_count=negative,
            copied_count=sum(1 for event in events if event.sentiment == "copied" or event.action == "copied"),
            revised_count=sum(1 for event in events if event.sentiment == "revised"),
            regenerated_count=sum(1 for event in events if event.action == "regenerated"),
            applied_count=sum(1 for event in events if event.action == "applied"),
            rolled_back_count=sum(1 for event in events if event.action == "rolled_back"),
            corrected_count=sum(1 for event in events if event.action == "corrected"),
            positive_rate=self._rate(positive, len(events)),
            negative_rate=self._rate(negative, len(events)),
        )

    def _feedback_trends(
        self,
        events: list[FeedbackTelemetryEntry],
        max_buckets: int = 14,
    ) -> list[FeedbackTrendBucket]:
        if not events:
            return []

        positive_sentiments = {"liked", "accepted", "copied"}
        negative_sentiments = {"disliked", "rejected"}
        groups: dict[str, dict[str, int]] = {}
        for event in events:
            period_start = self._feedback_period_start(event.created_at)
            group = groups.setdefault(
                period_start,
                {
                    "feedback_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "copied_count": 0,
                    "revised_count": 0,
                    "regenerated_count": 0,
                    "applied_count": 0,
                    "rolled_back_count": 0,
                    "corrected_count": 0,
                },
            )
            group["feedback_count"] += 1
            if event.sentiment in positive_sentiments:
                group["positive_count"] += 1
            if event.sentiment in negative_sentiments:
                group["negative_count"] += 1
            if event.sentiment == "copied" or event.action == "copied":
                group["copied_count"] += 1
            if event.sentiment == "revised":
                group["revised_count"] += 1
            if event.action == "regenerated":
                group["regenerated_count"] += 1
            if event.action == "applied":
                group["applied_count"] += 1
            if event.action == "rolled_back":
                group["rolled_back_count"] += 1
            if event.action == "corrected":
                group["corrected_count"] += 1

        buckets: list[FeedbackTrendBucket] = []
        for period_start, group in groups.items():
            feedback_count = int(group["feedback_count"])
            positive_count = int(group["positive_count"])
            negative_count = int(group["negative_count"])
            buckets.append(
                FeedbackTrendBucket(
                    period_start=period_start,
                    feedback_count=feedback_count,
                    positive_count=positive_count,
                    negative_count=negative_count,
                    copied_count=int(group["copied_count"]),
                    revised_count=int(group["revised_count"]),
                    regenerated_count=int(group["regenerated_count"]),
                    applied_count=int(group["applied_count"]),
                    rolled_back_count=int(group["rolled_back_count"]),
                    corrected_count=int(group["corrected_count"]),
                    positive_rate=self._rate(positive_count, feedback_count),
                    negative_rate=self._rate(negative_count, feedback_count),
                )
            )
        return sorted(buckets, key=lambda bucket: bucket.period_start, reverse=True)[:max(1, max_buckets)]

    def _feedback_period_start(self, created_at: str) -> str:
        timestamp = (created_at or "").strip()
        if len(timestamp) >= 10:
            return timestamp[:10]
        return "unknown"

    def _feedback_attribution_rollups(
        self,
        events: list[FeedbackTelemetryEntry],
        model_attempts: list[ModelAttemptTelemetryEntry],
        context_budgets: list[ContextBudgetTelemetryEntry],
    ) -> list[FeedbackAttributionRollup]:
        if not events:
            return []

        contexts_by_task: dict[str, ContextBudgetTelemetryEntry] = {
            entry.task_id: entry for entry in context_budgets if entry.task_id
        }
        attempts_by_task: dict[str, list[ModelAttemptTelemetryEntry]] = {}
        for entry in model_attempts:
            if entry.task_id:
                attempts_by_task.setdefault(entry.task_id, []).append(entry)

        positive_sentiments = {"liked", "accepted", "copied"}
        negative_sentiments = {"disliked", "rejected"}
        groups: dict[tuple[str, str], dict[str, Any]] = {}

        def add_rollup_event(dimension: str, key: str, label: str, event: FeedbackTelemetryEntry) -> None:
            normalized_key = self._feedback_rollup_value(key)
            normalized_label = self._feedback_rollup_value(label or normalized_key)
            group = groups.setdefault(
                (dimension, normalized_key),
                {
                    "dimension": dimension,
                    "key": normalized_key,
                    "label": normalized_label,
                    "tasks": set(),
                    "feedback_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "copied_count": 0,
                    "revised_count": 0,
                    "regenerated_count": 0,
                    "applied_count": 0,
                    "rolled_back_count": 0,
                    "corrected_count": 0,
                    "latest_at": "",
                },
            )
            if event.task_id:
                group["tasks"].add(event.task_id)
            group["feedback_count"] += 1
            if event.sentiment in positive_sentiments:
                group["positive_count"] += 1
            if event.sentiment in negative_sentiments:
                group["negative_count"] += 1
            if event.sentiment == "copied" or event.action == "copied":
                group["copied_count"] += 1
            if event.sentiment == "revised":
                group["revised_count"] += 1
            if event.action == "regenerated":
                group["regenerated_count"] += 1
            if event.action == "applied":
                group["applied_count"] += 1
            if event.action == "rolled_back":
                group["rolled_back_count"] += 1
            if event.action == "corrected":
                group["corrected_count"] += 1
            if event.created_at > group["latest_at"]:
                group["latest_at"] = event.created_at

        for event in events:
            attempts = attempts_by_task.get(event.task_id, [])
            attempt_entry = self._feedback_attempt_for_event(event, attempts)
            attempt = attempt_entry.attempt if attempt_entry is not None else None
            attempt_metadata = attempt.metadata if attempt is not None and isinstance(attempt.metadata, dict) else {}
            context = contexts_by_task.get(event.task_id)

            provider_id = attempt.provider_id if attempt is not None else ""
            provider_label = attempt.provider_label if attempt is not None else ""
            provider_api = attempt.provider_api if attempt is not None else ""
            provider_key = provider_id or provider_label or provider_api or "unknown"
            model = event.model_label or (attempt.model if attempt is not None else "")
            provider_display = provider_label or provider_key
            if model and model not in provider_display:
                provider_display = f"{provider_display} / {model}"

            route_role = (
                event.route_role
                or (context.route_role if context is not None else "")
                or (context.payload.route_role if context is not None else "")
                or (attempt.role if attempt is not None else "")
            )
            task_intent = (
                (context.intent if context is not None else "")
                or (context.payload.intent if context is not None else "")
                or "unknown"
            )
            candidate_id = event.candidate_id or str(attempt_metadata.get("candidate_id") or "")

            add_rollup_event("provider", provider_key, provider_display, event)
            add_rollup_event("model", model or "unknown", model or "unknown", event)
            add_rollup_event("route_role", route_role or "unknown", route_role or "unknown", event)
            add_rollup_event("task_intent", task_intent or "unknown", task_intent or "unknown", event)
            add_rollup_event("candidate", candidate_id or "unknown", candidate_id or "unknown", event)
            add_rollup_event("target", event.target or "assistant_response", event.target or "assistant_response", event)
            add_rollup_event("action", event.action or "manual", event.action or "manual", event)

        rollups: list[FeedbackAttributionRollup] = []
        for group in groups.values():
            feedback_count = int(group["feedback_count"])
            positive_count = int(group["positive_count"])
            negative_count = int(group["negative_count"])
            rollups.append(
                FeedbackAttributionRollup(
                    dimension=str(group["dimension"]),
                    key=str(group["key"]),
                    label=str(group["label"]),
                    feedback_count=feedback_count,
                    task_count=len(group["tasks"]),
                    positive_count=positive_count,
                    negative_count=negative_count,
                    copied_count=int(group["copied_count"]),
                    revised_count=int(group["revised_count"]),
                    regenerated_count=int(group["regenerated_count"]),
                    applied_count=int(group["applied_count"]),
                    rolled_back_count=int(group["rolled_back_count"]),
                    corrected_count=int(group["corrected_count"]),
                    positive_rate=self._rate(positive_count, feedback_count),
                    negative_rate=self._rate(negative_count, feedback_count),
                    latest_at=str(group["latest_at"]),
                )
            )

        priority = {
            "provider": 0,
            "model": 1,
            "route_role": 2,
            "task_intent": 3,
            "candidate": 4,
            "target": 5,
            "action": 6,
        }
        return sorted(
            rollups,
            key=lambda item: (
                priority.get(item.dimension, 99),
                -item.feedback_count,
                -item.negative_count,
                item.label.lower(),
            ),
        )[:80]

    def _feedback_attempt_for_event(
        self,
        event: FeedbackTelemetryEntry,
        attempts: list[ModelAttemptTelemetryEntry],
    ) -> ModelAttemptTelemetryEntry | None:
        if not attempts:
            return None

        candidate_id = event.candidate_id.strip()
        if candidate_id:
            matched = [
                entry
                for entry in attempts
                if str(entry.attempt.metadata.get("candidate_id") or "") == candidate_id
            ]
            if matched:
                return sorted(matched, key=self._feedback_attempt_rank)[0]

        route_role = event.route_role.strip()
        if route_role:
            matched = [entry for entry in attempts if entry.attempt.role == route_role]
            if matched:
                return sorted(matched, key=self._feedback_attempt_rank)[0]

        model_label = event.model_label.strip().lower()
        if model_label:
            matched = [
                entry
                for entry in attempts
                if model_label
                in {
                    entry.attempt.model.strip().lower(),
                    entry.attempt.provider_label.strip().lower(),
                    entry.attempt.provider_id.strip().lower(),
                }
            ]
            if matched:
                return sorted(matched, key=self._feedback_attempt_rank)[0]

        return sorted(attempts, key=self._feedback_attempt_rank)[0]

    def _feedback_attempt_rank(self, entry: ModelAttemptTelemetryEntry) -> tuple[int, int]:
        status_priority = {
            "succeeded": 0,
            "running": 1,
            "planned": 2,
            "fallback": 2,
            "skipped": 3,
            "failed": 4,
            "canceled": 5,
        }
        return (status_priority.get(self._attempt_status(entry), 3), entry.attempt.attempt)

    def _feedback_rollup_value(self, value: Any) -> str:
        text = str(value or "").strip()
        return text[:160] if text else "unknown"

    def _feedback_recommendations(
        self,
        summary: FeedbackTelemetrySummary,
        events: list[FeedbackTelemetryEntry],
    ) -> list[str]:
        if summary.feedback_count == 0:
            return ["No feedback telemetry exists yet; desktop like, reject, copy, apply, and rollback actions will seed route learning."]

        recommendations: list[str] = []
        if summary.negative_rate >= 0.30:
            recommendations.append("Negative feedback is above 30%; inspect recent rejected responses before automating route policy changes.")
        if summary.regenerated_count > summary.positive_count and summary.regenerated_count >= 3:
            recommendations.append("Regeneration is outpacing positive feedback; compare first-attempt models and fallback roles for these tasks.")
        if summary.rolled_back_count > 0:
            recommendations.append("Rollback feedback exists; keep write approvals strict and bias risky routes toward review-first planning.")
        if summary.corrected_count > 0:
            recommendations.append("Manual correction feedback exists; promote corrected patterns into project memory or eval fixtures.")
        models = sorted({event.model_label for event in events if event.model_label})
        if models:
            recommendations.append("Feedback is now model-attributed for: " + ", ".join(models[:4]) + ".")
        if not recommendations:
            recommendations.append("Feedback telemetry is available for route-quality scoring; next step is provider/role-level attribution.")
        return recommendations[:6]

    def _content_hash(self, content: str) -> str:
        normalized = " ".join((content or "").split())
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()

    def _feedback_metadata(self, request: FeedbackRecordRequest) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        metadata["content_length"] = len(request.content or "")
        metadata["has_content"] = bool((request.content or "").strip())
        return {
            str(key)[:80]: value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }

    def _attempt_status(self, entry: ModelAttemptTelemetryEntry) -> str:
        return (entry.attempt.status or "planned").strip().lower()

    def _is_fallback_attempt(self, entry: ModelAttemptTelemetryEntry) -> bool:
        attempt = entry.attempt
        return attempt.attempt > 1 or (attempt.status or "").lower() == "fallback" or (attempt.role or "").lower() == "fallback"

    def _token_estimator_label(self, metadata: dict[str, Any]) -> str:
        if not isinstance(metadata, dict):
            return ""
        family = str(metadata.get("token_estimator_family") or "").strip()
        source = str(metadata.get("token_estimate_source") or "").strip()
        if family and source:
            return f"{family}:{source}"
        return family or source

    def _optional_positive_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    def _token_metadata_int(self, metadata: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        if not isinstance(metadata, dict):
            return None
        for key in keys:
            value = self._optional_positive_int(metadata.get(key))
            if value is not None:
                return value
        return None

    def _token_relative_error(self, estimated: int | None, reported: int | None) -> float | None:
        if estimated is None or reported is None:
            return None
        return round(abs(estimated - reported) / max(reported, 1), 4)

    def _structured_preview_metrics(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None
        keys = {
            "structured_preview_delta_count",
            "structured_preview_char_count",
            "structured_preview_reset_count",
            "structured_preview_emitted",
            "structured_preview_retired",
            "structured_preview_final_winner",
            "structured_preview_retired_reason",
        }
        if not any(key in metadata for key in keys):
            return None
        delta_count = self._int_value(metadata.get("structured_preview_delta_count"))
        char_count = self._int_value(metadata.get("structured_preview_char_count"))
        reset_count = self._int_value(metadata.get("structured_preview_reset_count"))
        emitted = self._optional_bool(metadata.get("structured_preview_emitted"))
        retired = self._optional_bool(metadata.get("structured_preview_retired"))
        final_winner = self._optional_bool(metadata.get("structured_preview_final_winner"))
        return {
            "delta_count": max(0, delta_count),
            "char_count": max(0, char_count),
            "reset_count": max(0, reset_count),
            "emitted": bool(emitted) or delta_count > 0 or char_count > 0,
            "retired": bool(retired) or reset_count > 0,
            "final_winner": bool(final_winner),
            "retired_reason": str(metadata.get("structured_preview_retired_reason") or "").strip(),
        }

    def _structured_preview_status(
        self,
        *,
        previewed_attempts: int,
        final_winning_attempts: int,
        retired_attempts: int,
        reset_count: int,
    ) -> str:
        if previewed_attempts <= 0:
            return "insufficient"
        retired_rate = self._rate(retired_attempts, previewed_attempts)
        final_winner_rate = self._rate(final_winning_attempts, previewed_attempts)
        if previewed_attempts >= 2 and (retired_rate >= 0.50 or reset_count >= 2):
            return "unstable"
        if previewed_attempts < 2:
            return "insufficient"
        if retired_rate > 0.0 or final_winner_rate < 0.67:
            return "watch"
        return "stable"

    def _structured_preview_recommendation(
        self,
        *,
        status: str,
        provider_label: str,
        previewed_attempts: int,
        final_winning_attempts: int,
        retired_attempts: int,
        reset_count: int,
    ) -> str:
        label = provider_label or "provider"
        if status == "unstable":
            return (
                f"{label} retired {retired_attempts}/{previewed_attempts} structured preview attempt(s) "
                f"with {reset_count} reset(s); route policy should prefer a more stable structured-output provider."
            )
        if status == "watch":
            return (
                f"{label} previews are mixed: {final_winning_attempts}/{previewed_attempts} became final output. "
                "Keep collecting samples before promoting this provider for structured workspace streams."
            )
        if status == "stable":
            return f"{label} structured previews are stable enough for normal streamed coding/build routes."
        return f"Collect more structured preview samples for {label} before making route-policy decisions."

    def _token_calibration_status(
        self,
        *,
        calibrated_attempts: int,
        average_input_error: float | None,
        average_output_error: float | None,
        worst_input_error: float | None,
        worst_output_error: float | None,
    ) -> str:
        if calibrated_attempts <= 0:
            return "insufficient"
        average_error = max(average_input_error or 0.0, average_output_error or 0.0)
        worst_error = max(worst_input_error or 0.0, worst_output_error or 0.0)
        if average_error <= 0.12 and worst_error <= 0.25:
            return "stable"
        if average_error <= 0.25 and worst_error <= 0.45:
            return "watch"
        return "drift"

    def _token_calibration_recommendation(
        self,
        *,
        status: str,
        provider_label: str,
        calibrated_attempts: int,
        average_input_error: float | None,
        average_output_error: float | None,
        reported_sources: list[str],
    ) -> str:
        label = provider_label or "provider"
        if status == "insufficient":
            return f"Collect provider-reported token usage for {label} before tuning route context budgets from estimator data."
        source = ", ".join(reported_sources[:2]) if reported_sources else "provider usage metadata"
        input_text = f"{average_input_error:.0%}" if average_input_error is not None else "n/a"
        output_text = f"{average_output_error:.0%}" if average_output_error is not None else "n/a"
        if status == "stable":
            return f"{label} calibration is stable across {calibrated_attempts} attempt(s) via {source}; avg error in/out {input_text}/{output_text}."
        if status == "watch":
            return f"{label} token estimates have moderate drift; continue sampling {source} before changing profile overhead."
        return f"{label} token estimates are drifting from reported usage; adjust tokenizer profile or context overhead before relying on tight budgets."

    def _token_calibration_trend_recommendation(
        self,
        bucket: RouteQualityTokenCalibrationTrendBucket,
    ) -> str:
        label = bucket.provider_label or bucket.provider_id or "provider"
        if bucket.calibrated_attempts <= 0:
            return f"No provider-reported usage landed for {label} during {bucket.period_start}; keep collecting samples."
        if bucket.trend_direction == "improving":
            return f"{label} token estimates improved during {bucket.period_start}; keep the current estimator profile under observation."
        if bucket.trend_direction == "worsening":
            return f"{label} token-estimate error worsened during {bucket.period_start}; review recent prompt/context mix before expanding budgets."
        if bucket.calibration_status == "drift":
            return f"{label} is still drifting during {bucket.period_start}; tune estimator overhead before using tight context limits."
        if bucket.calibration_status == "watch":
            return f"{label} is in watch state for {bucket.period_start}; collect more samples before automated routing changes use token cost signals."
        if bucket.trend_direction == "flat":
            return f"{label} calibration stayed flat during {bucket.period_start}; continue sampling before changing the profile."
        return f"{label} established a calibration baseline during {bucket.period_start}."

    def _context_budget_utilization(self, entry: ContextBudgetTelemetryEntry) -> float | None:
        max_tokens = entry.max_context_tokens or entry.payload.max_context_tokens
        if max_tokens <= 0:
            return None
        requested = (entry.estimated_context_tokens or entry.payload.estimated_context_tokens) + (
            entry.reserve_response_tokens or entry.payload.reserve_response_tokens
        )
        return min(1.0, max(0.0, requested / max_tokens))

    def _reliability_score(
        self,
        success_rate: float,
        fallback_rate: float,
        context_utilization: float | None,
        positive_feedback_rate: float = 0.0,
        negative_feedback_rate: float = 0.0,
    ) -> float:
        pressure_penalty = max(0.0, ((context_utilization or 0.0) - 0.72) * 0.40)
        feedback_adjustment = (positive_feedback_rate * 0.08) - (negative_feedback_rate * 0.16)
        score = success_rate - (fallback_rate * 0.20) - pressure_penalty + feedback_adjustment
        return round(max(0.0, min(1.0, score)) * 100.0, 2)

    def _average(self, values: list[Any]) -> float | None:
        cleaned = [self._float_value(value, None) for value in values]
        cleaned = [value for value in cleaned if value is not None]
        if not cleaned:
            return None
        return round(sum(cleaned) / len(cleaned), 4)

    def _rate(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    def _int_value(self, value: Any, default: int = 0) -> int:
        if value in (None, ""):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        lowered = str(value).strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
        return None

    def _float_value(self, value: Any, default: float | None = 0.0) -> float | None:
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

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

    def _resolve_db_path(self, configured: str) -> Path:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _init_db(self) -> None:
        with self._session() as conn:
            conn.execute(
                """
                create table if not exists tasks (
                    id text primary key,
                    created_at text not null,
                    finished_at text,
                    mode text not null,
                    workspace_root text not null,
                    message text not null,
                    status text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists events (
                    id integer primary key autoincrement,
                    task_id text not null,
                    created_at text not null,
                    kind text not null,
                    title text not null,
                    status text not null,
                    detail text not null,
                    payload_json text not null,
                    foreign key(task_id) references tasks(id)
                )
                """
            )
            conn.execute(
                """
                create table if not exists fix_memory (
                    id text primary key,
                    created_at text not null,
                    project_root text not null,
                    error_signature text not null,
                    fix_summary text not null,
                    evidence text not null,
                    confidence real not null,
                    category text not null default 'unknown'
                )
                """
            )
            conn.execute(
                """
                create table if not exists repair_attempts (
                    id text primary key,
                    task_id text not null,
                    created_at text not null,
                    attempt_number integer not null,
                    category text not null,
                    before_signature text not null,
                    after_signature text not null,
                    outcome text not null,
                    checkpoint text,
                    summary text not null,
                    foreign key(task_id) references tasks(id)
                )
                """
            )
            conn.execute(
                """
                create table if not exists project_memory (
                    id text primary key,
                    created_at text not null,
                    updated_at text not null,
                    project_root text not null,
                    category text not null,
                    title text not null,
                    detail text not null,
                    source text not null,
                    confidence real not null,
                    fingerprint text not null,
                    unique(project_root, fingerprint)
                )
                """
            )
            conn.execute(
                """
                create table if not exists context_budget_telemetry (
                    id text primary key,
                    task_id text not null,
                    created_at text not null,
                    workspace_root text not null,
                    intent text not null,
                    route_role text not null,
                    strategy text not null,
                    privacy_mode text not null,
                    max_context_tokens integer not null,
                    estimated_context_tokens integer not null,
                    estimated_file_tokens integer not null,
                    reserve_response_tokens integer not null,
                    selected_file_count integer not null,
                    omitted_file_count integer not null,
                    payload_json text not null,
                    foreign key(task_id) references tasks(id)
                )
                """
            )
            conn.execute(
                """
                create table if not exists model_attempt_telemetry (
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
                    metadata_json text not null,
                    foreign key(task_id) references tasks(id)
                )
                """
            )
            conn.execute(
                """
                create table if not exists feedback_telemetry (
                    id text primary key,
                    created_at text not null,
                    workspace_root text not null,
                    task_id text not null,
                    sentiment text not null,
                    action text not null,
                    target text not null,
                    model_label text not null,
                    route_role text not null,
                    candidate_id text not null,
                    content_hash text not null,
                    context text not null,
                    metadata_json text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists telemetry_snapshots (
                    id text primary key,
                    created_at text not null,
                    updated_at text not null,
                    workspace_root text not null,
                    snapshot_key text not null,
                    route_quality_limit integer not null,
                    fallback_limit integer not null,
                    feedback_limit integer not null,
                    stale_after_seconds integer not null,
                    route_quality_json text not null,
                    fallback_inspector_json text not null,
                    feedback_json text not null,
                    task_count integer not null,
                    model_attempt_count integer not null,
                    feedback_count integer not null,
                    reliability_score real not null,
                    positive_feedback_rate real not null,
                    unique(workspace_root, snapshot_key)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_context_budget_workspace_created on context_budget_telemetry(workspace_root, created_at)"
            )
            conn.execute(
                "create index if not exists idx_model_attempt_workspace_created on model_attempt_telemetry(workspace_root, created_at)"
            )
            conn.execute(
                "create index if not exists idx_feedback_workspace_created on feedback_telemetry(workspace_root, created_at)"
            )
            conn.execute(
                "create index if not exists idx_feedback_task on feedback_telemetry(task_id)"
            )
            conn.execute(
                "create index if not exists idx_telemetry_snapshots_workspace_updated on telemetry_snapshots(workspace_root, updated_at)"
            )
            self._ensure_fix_memory_category_column(conn)

    def _ensure_fix_memory_category_column(self, conn: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute("pragma table_info(fix_memory)").fetchall()
            if row["name"]
        }
        if "category" not in columns:
            conn.execute("alter table fix_memory add column category text not null default 'unknown'")

    def _import_legacy_db_if_needed(self) -> None:
        legacy_db = (self.project_root / "backend" / "data" / "aegis.sqlite3").resolve()
        if legacy_db == self.db_path or not legacy_db.exists():
            return

        legacy_conn = sqlite3.connect(legacy_db)
        legacy_conn.row_factory = sqlite3.Row
        try:
            with self._session() as conn:
                self._import_legacy_tasks(conn, legacy_conn)
                self._import_legacy_events(conn, legacy_conn)
                self._import_legacy_fix_memory(conn, legacy_conn)
                self._import_legacy_repair_attempts(conn, legacy_conn)
                self._import_legacy_project_memory(conn, legacy_conn)
        finally:
            legacy_conn.close()

    def _import_legacy_tasks(self, conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
        if not self._table_exists(legacy_conn, "tasks"):
            return
        rows = legacy_conn.execute(
            "select id, created_at, finished_at, mode, workspace_root, message, status from tasks"
        ).fetchall()
        for row in rows:
            workspace_root = self._normalize_legacy_workspace_root(str(row["workspace_root"]))
            conn.execute(
                """
                insert or ignore into tasks (id, created_at, finished_at, mode, workspace_root, message, status)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    str(row["created_at"]),
                    str(row["finished_at"]) if row["finished_at"] is not None else None,
                    str(row["mode"]),
                    workspace_root,
                    str(row["message"]),
                    str(row["status"]),
                ),
            )

    def _import_legacy_events(self, conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
        if not self._table_exists(legacy_conn, "events"):
            return
        rows = legacy_conn.execute(
            "select task_id, created_at, kind, title, status, detail, payload_json from events"
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                insert into events (task_id, created_at, kind, title, status, detail, payload_json)
                select ?, ?, ?, ?, ?, ?, ?
                where not exists (
                    select 1 from events
                    where task_id = ? and created_at = ? and kind = ? and title = ? and detail = ?
                )
                """,
                (
                    str(row["task_id"]),
                    str(row["created_at"]),
                    str(row["kind"]),
                    str(row["title"]),
                    str(row["status"]),
                    str(row["detail"]),
                    str(row["payload_json"]),
                    str(row["task_id"]),
                    str(row["created_at"]),
                    str(row["kind"]),
                    str(row["title"]),
                    str(row["detail"]),
                ),
            )

    def _import_legacy_fix_memory(self, conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
        if not self._table_exists(legacy_conn, "fix_memory"):
            return
        columns = self._table_columns(legacy_conn, "fix_memory")
        has_category = "category" in columns
        select_sql = (
            "select id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category from fix_memory"
            if has_category
            else "select id, created_at, project_root, error_signature, fix_summary, evidence, confidence from fix_memory"
        )
        rows = legacy_conn.execute(select_sql).fetchall()
        for row in rows:
            conn.execute(
                """
                insert or ignore into fix_memory (
                    id, created_at, project_root, error_signature, fix_summary, evidence, confidence, category
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    str(row["created_at"]),
                    self._normalize_legacy_workspace_root(str(row["project_root"])),
                    str(row["error_signature"]),
                    str(row["fix_summary"]),
                    str(row["evidence"]),
                    float(row["confidence"]),
                    str(row["category"]) if has_category else "unknown",
                ),
            )

    def _import_legacy_repair_attempts(self, conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
        if not self._table_exists(legacy_conn, "repair_attempts"):
            return
        rows = legacy_conn.execute(
            """
            select id, task_id, created_at, attempt_number, category, before_signature,
                   after_signature, outcome, checkpoint, summary
            from repair_attempts
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                insert or ignore into repair_attempts (
                    id, task_id, created_at, attempt_number, category, before_signature,
                    after_signature, outcome, checkpoint, summary
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    str(row["task_id"]),
                    str(row["created_at"]),
                    int(row["attempt_number"]),
                    str(row["category"]),
                    str(row["before_signature"]),
                    str(row["after_signature"]),
                    str(row["outcome"]),
                    str(row["checkpoint"]) if row["checkpoint"] is not None else None,
                    str(row["summary"]),
                ),
            )

    def _import_legacy_project_memory(self, conn: sqlite3.Connection, legacy_conn: sqlite3.Connection) -> None:
        if not self._table_exists(legacy_conn, "project_memory"):
            return
        columns = self._table_columns(legacy_conn, "project_memory")
        if not {"id", "created_at", "updated_at", "project_root", "category", "title", "detail", "source", "confidence"}.issubset(columns):
            return

        rows = legacy_conn.execute(
            """
            select id, created_at, updated_at, project_root, category, title, detail, source, confidence
            from project_memory
            """
        ).fetchall()
        for row in rows:
            fingerprint = self._fingerprint(str(row["category"]), str(row["title"]), str(row["detail"]))
            conn.execute(
                """
                insert or ignore into project_memory (
                    id, created_at, updated_at, project_root, category, title, detail, source, confidence, fingerprint
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    str(row["created_at"]),
                    str(row["updated_at"]),
                    self._normalize_legacy_workspace_root(str(row["project_root"])),
                    str(row["category"]),
                    str(row["title"]),
                    str(row["detail"]),
                    str(row["source"]),
                    float(row["confidence"]),
                    fingerprint,
                ),
            )

    def _table_exists(self, conn: sqlite3.Connection, name: str) -> bool:
        row = conn.execute("select name from sqlite_master where type = 'table' and name = ?", (name,)).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, name: str) -> set[str]:
        return {
            str(row["name"])
            for row in conn.execute(f"pragma table_info({name})").fetchall()
            if row["name"]
        }

    def _normalize_legacy_workspace_root(self, value: str) -> str:
        try:
            path = Path(value).resolve()
        except OSError:
            return value

        legacy_workspace = (self.project_root / "backend" / "workspace").resolve()
        current_workspace = (self.project_root / "workspace").resolve()

        if path == legacy_workspace:
            return str(current_workspace)
        if path.is_relative_to(legacy_workspace):
            return str((current_workspace / path.relative_to(legacy_workspace)).resolve())
        return str(path)

    def _context_budget_payload(self, value: str) -> ContextBudgetInfo:
        return ContextBudgetInfo.model_validate(self._json_payload(value))

    def _json_payload(self, value: str) -> dict[str, Any]:
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _memory_match_score(self, query: str, *parts: str) -> float:
        query_tokens = self._tokenize(query)
        memory_tokens = self._tokenize("\n".join(parts))
        if not query_tokens or not memory_tokens:
            return 0.0

        overlap = len(query_tokens & memory_tokens)
        if overlap == 0:
            return 0.0

        return overlap / max(len(query_tokens), 1)

    def _fingerprint(self, *parts: str) -> str:
        normalized = "\n".join(part.strip().lower() for part in parts if part.strip())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _tokenize(self, value: str) -> set[str]:
        cleaned = [
            "".join(character for character in chunk.lower() if character.isalnum())
            for chunk in value.split()
        ]
        return {token for token in cleaned if len(token) >= 3}
