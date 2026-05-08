from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import (
    AdaptiveBenchmarkReport,
    AdaptiveInsight,
    AdaptiveIntelligenceSnapshot,
    AdaptivePolicyProfileUpdateRequest,
    AdaptiveQualityScore,
    AdaptiveReplayRequest,
    AdaptiveRouteRecommendation,
    ContextBudgetTelemetryEntry,
    EvaluationReplayResult,
    FeedbackTelemetryEntry,
    IntelligencePolicyProfile,
    ModelAttemptTelemetryEntry,
    RouteQualityResponse,
    TaskOutcomeRecord,
    TaskSummary,
    ToolEvent,
)


ADAPTIVE_BENCHMARK_SUITES: tuple[tuple[str, str], ...] = (
    ("project_scaffolding", "Project Scaffolding"),
    ("debugging", "Debugging"),
    ("repair_quality", "Repair Quality"),
    ("reasoning", "Reasoning"),
    ("code_review", "Code Review"),
    ("architecture_planning", "Architecture Planning"),
    ("validation_success", "Validation Success"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdaptiveIntelligenceEngine:
    """Turns telemetry into reviewable, reversible routing and quality guidance."""

    def default_profiles(self) -> list[IntelligencePolicyProfile]:
        now = utc_now()
        profiles = [
            IntelligencePolicyProfile(
                id="local_privacy_first",
                name="Local Privacy-First",
                description="Prefer local models and local workers unless the user explicitly opts into cloud or remote execution.",
                privacy_mode="local-first",
                routing_strategy="privacy",
                cost_priority=0.7,
                latency_priority=0.5,
                reasoning_bias=0.45,
                allow_cloud=False,
                allow_remote_workers=False,
                active=True,
                score_weights={"success": 0.42, "privacy": 0.28, "latency": 0.12, "cost": 0.10, "feedback": 0.08},
            ),
            IntelligencePolicyProfile(
                id="balanced_hybrid",
                name="Balanced Hybrid",
                description="Balance local-first behavior with cloud or remote fallback when telemetry shows a clear quality gain.",
                privacy_mode="hybrid",
                routing_strategy="balanced",
                cost_priority=0.5,
                latency_priority=0.5,
                reasoning_bias=0.55,
                allow_cloud=True,
                allow_remote_workers=True,
                score_weights={"success": 0.45, "feedback": 0.18, "latency": 0.15, "cost": 0.12, "privacy": 0.10},
            ),
            IntelligencePolicyProfile(
                id="maximum_reasoning",
                name="Maximum Reasoning",
                description="Bias toward the most reliable reasoning route for complex design, repair, and review tasks.",
                privacy_mode="hybrid",
                routing_strategy="quality",
                cost_priority=0.18,
                latency_priority=0.22,
                reasoning_bias=0.95,
                allow_cloud=True,
                allow_remote_workers=True,
                score_weights={"success": 0.58, "feedback": 0.18, "latency": 0.06, "cost": 0.04, "privacy": 0.14},
            ),
            IntelligencePolicyProfile(
                id="fast_iterative",
                name="Fast Iterative",
                description="Favor low-latency routes for quick edits, questions, and tight local feedback loops.",
                privacy_mode="local-first",
                routing_strategy="fast",
                cost_priority=0.55,
                latency_priority=0.9,
                reasoning_bias=0.35,
                allow_cloud=True,
                allow_remote_workers=False,
                score_weights={"success": 0.33, "latency": 0.33, "feedback": 0.14, "cost": 0.12, "privacy": 0.08},
            ),
            IntelligencePolicyProfile(
                id="low_cost",
                name="Low-Cost",
                description="Prioritize inexpensive routes and avoid costly fallbacks unless reliability is suffering.",
                privacy_mode="local-first",
                routing_strategy="cost",
                cost_priority=0.95,
                latency_priority=0.45,
                reasoning_bias=0.35,
                allow_cloud=False,
                allow_remote_workers=False,
                score_weights={"success": 0.35, "cost": 0.35, "latency": 0.12, "feedback": 0.10, "privacy": 0.08},
            ),
            IntelligencePolicyProfile(
                id="autonomous_engineering",
                name="Autonomous Engineering",
                description="Use broader reasoning and remote validation while still requiring approvals for risky changes.",
                privacy_mode="hybrid",
                routing_strategy="autonomous",
                cost_priority=0.35,
                latency_priority=0.4,
                reasoning_bias=0.85,
                allow_cloud=True,
                allow_remote_workers=True,
                review_required=True,
                score_weights={"success": 0.52, "feedback": 0.18, "validation": 0.14, "latency": 0.08, "cost": 0.08},
            ),
            IntelligencePolicyProfile(
                id="safe_review_only",
                name="Safe Review-Only",
                description="Prefer analysis, review, and validation routes; file-changing work stays approval-gated.",
                privacy_mode="local-first",
                routing_strategy="review",
                cost_priority=0.55,
                latency_priority=0.35,
                reasoning_bias=0.75,
                allow_cloud=False,
                allow_remote_workers=False,
                review_required=True,
                score_weights={"success": 0.40, "feedback": 0.22, "privacy": 0.20, "validation": 0.12, "cost": 0.06},
            ),
        ]
        return [
            profile.model_copy(update={"created_at": profile.created_at or now, "updated_at": profile.updated_at or now})
            for profile in profiles
        ]

    def ensure_profiles(self, store: Any) -> list[IntelligencePolicyProfile]:
        profiles = store.adaptive_policy_profiles()
        if profiles:
            return profiles
        return store.ensure_adaptive_policy_profiles(self.default_profiles())

    def snapshot(
        self,
        store: Any,
        *,
        project_root: Path,
        limit: int = 200,
        refresh_outcomes: bool = True,
    ) -> AdaptiveIntelligenceSnapshot:
        profiles = self.ensure_profiles(store)
        active_profile = self._active_profile(profiles)
        outcomes = (
            self.refresh_outcomes(store, project_root=project_root, limit=limit)
            if refresh_outcomes
            else store.adaptive_task_outcomes(project_root=project_root, limit=limit)
        )
        route_quality = store.route_quality(project_root=project_root, limit=min(max(limit, 1), 500))
        feedback_events = store.recent_feedback(project_root=project_root, limit=min(max(limit, 1), 500))
        context_budgets = store.recent_context_budgets(project_root=project_root, limit=min(max(limit, 1), 500))
        fix_history = store.fix_history(project_root=project_root, limit=100)

        quality_scores = self.quality_scores(route_quality, outcomes, feedback_events, context_budgets)
        route_recommendations = self.route_recommendations(route_quality, active_profile)
        repair_insights = self.repair_insights(outcomes, fix_history)
        context_insights = self.context_insights(outcomes, context_budgets)
        feedback_insights = self.feedback_insights(feedback_events)

        recommendations = self._snapshot_recommendations(
            quality_scores,
            route_recommendations,
            repair_insights,
            context_insights,
            feedback_insights,
        )
        warnings = [
            "Adaptive Intelligence only writes telemetry, profile selections, benchmarks, and replay reports; it does not rewrite runtime logic."
        ]
        if active_profile.auto_apply_policy:
            warnings.append("The active profile allows policy auto-application, but runtime policy writes still require explicit API calls.")

        return AdaptiveIntelligenceSnapshot(
            workspace_root=str(project_root.resolve()),
            generated_at=utc_now(),
            active_profile=active_profile,
            profiles=profiles,
            outcomes=outcomes,
            quality_scores=quality_scores,
            route_recommendations=route_recommendations,
            repair_insights=repair_insights,
            context_insights=context_insights,
            feedback_insights=feedback_insights,
            benchmark_reports=store.adaptive_benchmark_reports(project_root=project_root, limit=20),
            replay_results=store.adaptive_replay_results(project_root=project_root, limit=20),
            policy_checkpoints=store.adaptive_policy_checkpoints(limit=20),
            recommendations=recommendations,
            warnings=warnings,
        )

    def refresh_outcomes(self, store: Any, *, project_root: Path, limit: int = 200) -> list[TaskOutcomeRecord]:
        tasks = store.list_tasks(project_root=project_root, limit=max(1, min(1000, limit)), include_subtasks=True)
        attempts_by_task = self._group_model_attempts(store.recent_model_attempts(project_root=project_root, limit=4000))
        context_by_task = self._latest_context_by_task(store.recent_context_budgets(project_root=project_root, limit=2000))
        feedback_by_task = self._group_feedback(store.recent_feedback(project_root=project_root, limit=2000))
        outcomes: list[TaskOutcomeRecord] = []
        for task in tasks:
            events = store.task_events(task.id)
            artifacts = store.task_artifacts(task.id)
            attempts = attempts_by_task.get(task.id, [])
            context = context_by_task.get(task.id)
            feedback = feedback_by_task.get(task.id, [])
            outcome = self._outcome_from_signals(task, events, artifacts.repair_attempts, feedback)
            record = TaskOutcomeRecord(
                id=f"outcome-{task.id}",
                task_id=task.id,
                project_id=task.project_id,
                workspace_root=str(project_root.resolve()),
                title=task.title,
                status=task.status,
                outcome=outcome,
                success=outcome == "success",
                repair_count=len(artifacts.repair_attempts),
                validation_runs=self._validation_runs(events),
                validation_passes=self._validation_passes(events),
                validation_failures=self._validation_failures(events),
                retry_count=self._event_count(events, "retry"),
                approval_count=sum(1 for item in feedback if item.action == "accepted") + self._approval_count(events, True),
                rejection_count=sum(1 for item in feedback if item.action == "rejected") + self._approval_count(events, False),
                rollback_count=sum(1 for item in feedback if item.action == "rolled_back") + self._event_count(events, "rollback"),
                completion_time_seconds=self._completion_seconds(task.created_at, task.completed_at or task.finished_at),
                input_tokens=sum(int(attempt.attempt.input_tokens or 0) for attempt in attempts),
                output_tokens=sum(int(attempt.attempt.output_tokens or 0) for attempt in attempts),
                estimated_cost_usd=sum(float(attempt.attempt.estimated_cost_usd or 0.0) for attempt in attempts),
                model_used=self._winning_model(attempts),
                provider_id=self._winning_provider(attempts),
                route_role=self._winning_role(attempts, context),
                routing_path=self._routing_path(attempts),
                context_files=self._context_files(context),
                memory_refs=self._memory_refs(context),
                checkpoints=task.checkpoints,
                error_summary=task.error_summary,
                final_summary=task.final_summary,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at or task.finished_at,
                metadata={
                    "feedback_count": len(feedback),
                    "repair_outcomes": [item.outcome for item in artifacts.repair_attempts],
                    "validation_commands": artifacts.validation_commands,
                },
            )
            validation_runs = record.validation_runs
            record.validation_pass_rate = self._rate(record.validation_passes, validation_runs)
            store.upsert_task_outcome(record)
            outcomes.append(record)
        return sorted(outcomes, key=lambda item: item.created_at, reverse=True)

    def quality_scores(
        self,
        route_quality: RouteQualityResponse,
        outcomes: list[TaskOutcomeRecord],
        feedback_events: list[FeedbackTelemetryEntry],
        context_budgets: list[ContextBudgetTelemetryEntry],
    ) -> list[AdaptiveQualityScore]:
        completed = [item for item in outcomes if item.outcome in {"success", "failed", "rolled_back"}]
        success_rate = self._rate(sum(1 for item in completed if item.success), len(completed))
        repair_tasks = [item for item in completed if item.repair_count > 0 or item.validation_failures > 0]
        repaired_success = sum(1 for item in repair_tasks if item.success)
        validation_runs = sum(item.validation_runs for item in outcomes)
        validation_passes = sum(item.validation_passes for item in outcomes)
        negative_feedback = sum(1 for item in feedback_events if item.sentiment in {"disliked", "rejected"} or item.action in {"rejected", "rolled_back"})
        positive_feedback = sum(1 for item in feedback_events if item.sentiment in {"liked", "accepted", "copied"} or item.action in {"accepted", "applied", "copied"})
        context_score = self._context_quality_score(context_budgets, outcomes)
        return [
            AdaptiveQualityScore(
                dimension="task_completion",
                label="Task Completion",
                score=success_rate,
                confidence=self._confidence(len(completed)),
                sample_size=len(completed),
                trend=self._outcome_trend(completed),
                reasons=[f"{sum(1 for item in completed if item.success)} of {len(completed)} terminal task(s) succeeded."],
                recommendations=self._completion_recommendations(success_rate, completed),
            ),
            AdaptiveQualityScore(
                dimension="model_effectiveness",
                label="Model Effectiveness",
                score=max(0.0, min(1.0, route_quality.overview.success_rate)),
                confidence=self._confidence(route_quality.overview.model_attempt_count),
                sample_size=route_quality.overview.model_attempt_count,
                trend="stable",
                reasons=[f"{route_quality.overview.succeeded_attempts} succeeded attempt(s), {route_quality.overview.failed_attempts} failed."],
                recommendations=route_quality.recommendations[:3],
            ),
            AdaptiveQualityScore(
                dimension="repair_effectiveness",
                label="Repair Effectiveness",
                score=self._rate(repaired_success, len(repair_tasks)),
                confidence=self._confidence(len(repair_tasks)),
                sample_size=len(repair_tasks),
                trend="stable",
                reasons=[f"{repaired_success} of {len(repair_tasks)} task(s) with repair pressure completed successfully."],
                recommendations=self._repair_recommendations(repair_tasks),
            ),
            AdaptiveQualityScore(
                dimension="validation_reliability",
                label="Validation Reliability",
                score=self._rate(validation_passes, validation_runs),
                confidence=self._confidence(validation_runs),
                sample_size=validation_runs,
                trend="stable",
                reasons=[f"{validation_passes} of {validation_runs} validation run(s) passed."],
                recommendations=self._validation_recommendations(outcomes),
            ),
            AdaptiveQualityScore(
                dimension="context_quality",
                label="Context Quality",
                score=context_score,
                confidence=self._confidence(len(context_budgets)),
                sample_size=len(context_budgets),
                trend="stable",
                reasons=[f"{len(context_budgets)} context budget sample(s) analyzed."],
                recommendations=self._context_recommendations(context_budgets, context_score),
            ),
            AdaptiveQualityScore(
                dimension="feedback_quality",
                label="User Feedback Signal",
                score=self._rate(positive_feedback, positive_feedback + negative_feedback),
                confidence=self._confidence(positive_feedback + negative_feedback),
                sample_size=positive_feedback + negative_feedback,
                trend="stable",
                reasons=[f"{positive_feedback} positive and {negative_feedback} negative feedback event(s)."],
                recommendations=self._feedback_recommendations(positive_feedback, negative_feedback),
            ),
        ]

    def route_recommendations(
        self,
        route_quality: RouteQualityResponse,
        active_profile: IntelligencePolicyProfile,
    ) -> list[AdaptiveRouteRecommendation]:
        recommendations: list[AdaptiveRouteRecommendation] = []
        weights = active_profile.score_weights or {}
        success_weight = weights.get("success", 0.45)
        latency_weight = weights.get("latency", 0.15)
        cost_weight = weights.get("cost", 0.12)
        feedback_weight = weights.get("feedback", 0.18)
        privacy_weight = weights.get("privacy", 0.10)
        feedback_by_provider = {
            rollup.key: rollup
            for rollup in route_quality.feedback_rollups
            if rollup.dimension == "provider"
        }
        max_cost = max((provider.estimated_cost_usd for provider in route_quality.providers), default=0.0) or 1.0
        max_latency = max((provider.average_latency_ms or 0.0 for provider in route_quality.providers), default=0.0) or 1.0
        for provider in route_quality.providers:
            feedback = feedback_by_provider.get(provider.provider_id)
            feedback_score = feedback.positive_rate if feedback else 0.5
            latency_score = 1.0 - min(1.0, float(provider.average_latency_ms or 0.0) / max_latency)
            cost_score = 1.0 - min(1.0, provider.estimated_cost_usd / max_cost)
            privacy_score = 1.0 if provider.provider_api in {"ollama", "local", "llama.cpp"} else 0.45
            if active_profile.allow_cloud:
                privacy_score = max(privacy_score, 0.7)
            score = (
                provider.success_rate * success_weight
                + latency_score * latency_weight
                + cost_score * cost_weight
                + feedback_score * feedback_weight
                + privacy_score * privacy_weight
            )
            score = max(0.0, min(1.0, score))
            action = "prefer" if score >= 0.72 and provider.attempts >= 3 else "deprioritize" if score < 0.42 and provider.attempts >= 3 else "monitor"
            reasons = [
                f"{provider.success_rate:.0%} observed success across {provider.attempts} attempt(s).",
                f"{active_profile.name} weights success, feedback, latency, cost, and privacy for this route.",
            ]
            risks = []
            if provider.fallback_rate > 0.35:
                risks.append("High fallback rate suggests this route needs a stronger backup.")
            if provider.provider_api not in {"ollama", "local", "llama.cpp"} and not active_profile.allow_cloud:
                risks.append("Active profile does not allow cloud routing by default.")
            recommendations.append(
                AdaptiveRouteRecommendation(
                    provider_id=provider.provider_id,
                    provider_label=provider.provider_label,
                    model=provider.model,
                    role="default",
                    profile_id=active_profile.id,
                    action=action,
                    score=score,
                    confidence=self._confidence(provider.attempts),
                    reasons=reasons,
                    risks=risks,
                    metadata={"provider_api": provider.provider_api, "fallback_rate": provider.fallback_rate},
                )
            )
        return sorted(recommendations, key=lambda item: (item.score, item.confidence), reverse=True)[:12]

    def repair_insights(self, outcomes: list[TaskOutcomeRecord], fix_history: list[Any]) -> list[AdaptiveInsight]:
        insights: list[AdaptiveInsight] = []
        failure_counter = Counter(self._failure_signature(item) for item in outcomes if not item.success and item.error_summary)
        recurring = [(key, count) for key, count in failure_counter.items() if key and count >= 2]
        for key, count in recurring[:5]:
            related = [item.task_id for item in outcomes if self._failure_signature(item) == key][:5]
            insights.append(
                AdaptiveInsight(
                    id=f"repair-recurring-{self._stable_id(key)}",
                    category="repair",
                    key=key,
                    title="Recurring Repair Failure",
                    detail=f"This failure pattern appeared in {count} task outcome(s).",
                    severity="medium" if count < 4 else "high",
                    score=min(1.0, count / 6),
                    evidence=[key],
                    recommendations=["Prefer the previously successful repair strategy before starting a new loop."],
                    related_tasks=related,
                )
            )
        for fix in fix_history[:5]:
            signature = getattr(fix, "error_signature", "")
            summary = getattr(fix, "fix_summary", "")
            if not signature and not summary:
                continue
            insights.append(
                AdaptiveInsight(
                    id=f"repair-memory-{self._stable_id(signature or summary)}",
                    category="repair_memory",
                    key=signature or summary[:80],
                    title="Successful Repair Memory",
                    detail=summary or signature,
                    severity="info",
                    score=float(getattr(fix, "confidence", 0.6) or 0.6),
                    evidence=[signature] if signature else [],
                    recommendations=["Use this memory when a matching validation error appears again."],
                )
            )
        if not insights:
            insights.append(
                AdaptiveInsight(
                    id="repair-no-patterns",
                    category="repair",
                    key="no-patterns",
                    title="No Recurring Repair Pattern",
                    detail="Recent repair telemetry has not accumulated a repeated failure signature yet.",
                    severity="info",
                    score=0.5,
                )
            )
        return insights

    def context_insights(
        self,
        outcomes: list[TaskOutcomeRecord],
        context_budgets: list[ContextBudgetTelemetryEntry],
    ) -> list[AdaptiveInsight]:
        file_hits: Counter[str] = Counter()
        wasted_refs: Counter[str] = Counter()
        outcome_by_task = {item.task_id: item for item in outcomes}
        for outcome in outcomes:
            if outcome.success:
                file_hits.update(outcome.context_files)
        for budget in context_budgets:
            outcome = outcome_by_task.get(budget.task_id)
            if outcome and not outcome.success:
                wasted_refs.update(self._context_files(budget))
        insights: list[AdaptiveInsight] = []
        for path, count in file_hits.most_common(6):
            insights.append(
                AdaptiveInsight(
                    id=f"context-useful-{self._stable_id(path)}",
                    category="context",
                    key=path,
                    title="Useful Context File",
                    detail=f"{path} appeared in {count} successful task context(s).",
                    severity="info",
                    score=min(1.0, count / 5),
                    evidence=[path],
                    related_files=[path],
                    recommendations=["Keep this file eligible for context when the task touches nearby code."],
                )
            )
        for path, count in wasted_refs.most_common(4):
            if file_hits[path] >= count:
                continue
            insights.append(
                AdaptiveInsight(
                    id=f"context-waste-{self._stable_id(path)}",
                    category="context",
                    key=path,
                    title="Low-Yield Context Candidate",
                    detail=f"{path} appeared mostly in unsuccessful task context.",
                    severity="low",
                    score=min(1.0, count / 5),
                    evidence=[path],
                    related_files=[path],
                    recommendations=["Require stronger relevance before including this file in large-context prompts."],
                )
            )
        pressure = [budget for budget in context_budgets if budget.max_context_tokens and budget.estimated_context_tokens / budget.max_context_tokens > 0.85]
        if pressure:
            insights.append(
                AdaptiveInsight(
                    id="context-pressure",
                    category="context",
                    key="budget-pressure",
                    title="Context Budget Pressure",
                    detail=f"{len(pressure)} recent context budget(s) used more than 85% of the available window.",
                    severity="medium",
                    score=min(1.0, len(pressure) / max(1, len(context_budgets))),
                    recommendations=["Prefer architecture notes and highly scored files over broad file dumps for large tasks."],
                )
            )
        return insights or [
            AdaptiveInsight(
                id="context-no-patterns",
                category="context",
                key="no-patterns",
                title="Context Learning Pending",
                detail="Aegis needs more completed task outcomes before ranking high-yield context confidently.",
                severity="info",
                score=0.4,
            )
        ]

    def feedback_insights(self, feedback_events: list[FeedbackTelemetryEntry]) -> list[AdaptiveInsight]:
        grouped: dict[str, list[FeedbackTelemetryEntry]] = defaultdict(list)
        for event in feedback_events:
            key = event.route_role or event.model_label or event.target or "assistant_response"
            grouped[key].append(event)
        insights: list[AdaptiveInsight] = []
        for key, events in sorted(grouped.items(), key=lambda pair: len(pair[1]), reverse=True)[:8]:
            positives = sum(1 for item in events if item.sentiment in {"liked", "accepted", "copied"} or item.action in {"accepted", "applied", "copied"})
            negatives = sum(1 for item in events if item.sentiment in {"disliked", "rejected"} or item.action in {"rejected", "rolled_back"})
            if positives + negatives == 0:
                continue
            positive_rate = self._rate(positives, positives + negatives)
            insights.append(
                AdaptiveInsight(
                    id=f"feedback-{self._stable_id(key)}",
                    category="feedback",
                    key=key,
                    title="Feedback Pattern",
                    detail=f"{key} has {positive_rate:.0%} positive feedback over {positives + negatives} signal(s).",
                    severity="info" if positive_rate >= 0.65 else "medium",
                    score=positive_rate,
                    evidence=[f"{positives} positive", f"{negatives} negative"],
                    recommendations=["Use this feedback signal when ranking routes for similar tasks."],
                )
            )
        return insights or [
            AdaptiveInsight(
                id="feedback-no-patterns",
                category="feedback",
                key="no-feedback",
                title="Feedback Learning Pending",
                detail="No strong user feedback pattern is available yet.",
                severity="info",
                score=0.5,
            )
        ]

    def activate_profile(self, store: Any, *, profile_id: str, reason: str = "") -> IntelligencePolicyProfile:
        self.ensure_profiles(store)
        store.create_adaptive_policy_checkpoint(reason or f"Before activating {profile_id}.")
        return store.set_active_adaptive_policy_profile(profile_id)

    def upsert_profile(
        self,
        store: Any,
        request: AdaptivePolicyProfileUpdateRequest,
    ) -> IntelligencePolicyProfile:
        self.ensure_profiles(store)
        store.create_adaptive_policy_checkpoint(request.reason or f"Before updating {request.profile.name}.")
        saved = store.upsert_adaptive_policy_profile(
            request.profile.model_copy(update={"updated_at": utc_now()})
        )
        if request.activate:
            return store.set_active_adaptive_policy_profile(saved.id)
        return saved

    def rollback_policy(self, store: Any, *, checkpoint_id: str, reason: str = "") -> list[IntelligencePolicyProfile]:
        return store.rollback_adaptive_policy_checkpoint(checkpoint_id, reason=reason)

    def run_benchmarks(
        self,
        store: Any,
        *,
        project_root: Path,
        suite_ids: list[str] | None = None,
        baseline_score: float | None = None,
    ) -> list[AdaptiveBenchmarkReport]:
        outcomes = store.adaptive_task_outcomes(project_root=project_root, limit=250)
        if not outcomes:
            outcomes = self.refresh_outcomes(store, project_root=project_root, limit=250)
        route_quality = store.route_quality(project_root=project_root, limit=250)
        selected = set(suite_ids or [])
        suites = [suite for suite in ADAPTIVE_BENCHMARK_SUITES if not selected or suite[0] in selected]
        reports: list[AdaptiveBenchmarkReport] = []
        for suite_id, suite_label in suites:
            candidate = self._suite_score(suite_id, outcomes, route_quality)
            baseline = baseline_score if baseline_score is not None else self._previous_benchmark_score(store, project_root, suite_id, candidate)
            regression = candidate + 0.04 < baseline
            status = "regressed" if regression else "passed" if outcomes or route_quality.overview.model_attempt_count else "insufficient"
            report = AdaptiveBenchmarkReport(
                id=f"bench-{suite_id}-{self._stable_id(str(project_root.resolve()))[:10]}-{uuid4().hex[:8]}",
                workspace_root=str(project_root.resolve()),
                created_at=utc_now(),
                suite_id=suite_id,
                suite_label=suite_label,
                status=status,
                baseline_score=baseline,
                candidate_score=candidate,
                regression_detected=regression,
                reproducibility_key=self._benchmark_repro_key(suite_id, outcomes, route_quality),
                metrics=self._suite_metrics(suite_id, outcomes, route_quality),
                recommendations=self._benchmark_recommendations(suite_id, candidate, baseline, regression),
                warnings=[] if not regression else ["Regression detected against the saved or requested baseline."],
            )
            store.save_adaptive_benchmark_report(report)
            reports.append(report)
        return reports

    def replay(
        self,
        store: Any,
        *,
        project_root: Path,
        request: AdaptiveReplayRequest,
    ) -> list[EvaluationReplayResult]:
        outcomes = store.adaptive_task_outcomes(project_root=project_root, limit=250)
        if not outcomes:
            outcomes = self.refresh_outcomes(store, project_root=project_root, limit=250)
        wanted = set(request.task_ids or [])
        selected = [item for item in outcomes if not wanted or item.task_id in wanted][: max(1, min(100, request.limit))]
        active_profile = self._active_profile(self.ensure_profiles(store))
        route_quality = store.route_quality(project_root=project_root, limit=250)
        top_routes = self.route_recommendations(route_quality, active_profile)[:3]
        replay_route = [item.provider_id for item in top_routes if item.provider_id]
        results: list[EvaluationReplayResult] = []
        for outcome in selected:
            previous = self._outcome_score(outcome)
            route_bonus = (top_routes[0].score - 0.5) * 0.12 if top_routes else 0.0
            repair_penalty = min(0.12, outcome.repair_count * 0.025)
            replay_score = max(0.0, min(1.0, previous + route_bonus - repair_penalty))
            status = "improved" if replay_score > previous + 0.03 else "regressed" if replay_score + 0.03 < previous else "matched"
            regression = status == "regressed"
            result = EvaluationReplayResult(
                id=f"replay-{outcome.task_id}-{self._stable_id(active_profile.id)[:8]}",
                workspace_root=str(project_root.resolve()),
                created_at=utc_now(),
                source_task_id=outcome.task_id,
                status=status,
                previous_score=previous,
                replay_score=replay_score,
                regression_detected=regression,
                previous_route=outcome.routing_path,
                replay_route=replay_route,
                differences=self._replay_differences(outcome, replay_route, previous, replay_score),
                recommendations=self._replay_recommendations(status),
                metadata={"active_profile_id": active_profile.id},
            )
            store.save_adaptive_replay_result(result)
            results.append(result)
        return results

    def _active_profile(self, profiles: list[IntelligencePolicyProfile]) -> IntelligencePolicyProfile:
        for profile in profiles:
            if profile.active:
                return profile
        if profiles:
            return profiles[0].model_copy(update={"active": True})
        return self.default_profiles()[0]

    def _group_model_attempts(self, attempts: list[ModelAttemptTelemetryEntry]) -> dict[str, list[ModelAttemptTelemetryEntry]]:
        grouped: dict[str, list[ModelAttemptTelemetryEntry]] = defaultdict(list)
        for attempt in attempts:
            grouped[attempt.task_id].append(attempt)
        return dict(grouped)

    def _latest_context_by_task(self, budgets: list[ContextBudgetTelemetryEntry]) -> dict[str, ContextBudgetTelemetryEntry]:
        latest: dict[str, ContextBudgetTelemetryEntry] = {}
        for budget in budgets:
            if budget.task_id not in latest or budget.created_at > latest[budget.task_id].created_at:
                latest[budget.task_id] = budget
        return latest

    def _group_feedback(self, feedback_events: list[FeedbackTelemetryEntry]) -> dict[str, list[FeedbackTelemetryEntry]]:
        grouped: dict[str, list[FeedbackTelemetryEntry]] = defaultdict(list)
        for event in feedback_events:
            if event.task_id:
                grouped[event.task_id].append(event)
        return dict(grouped)

    def _outcome_from_signals(
        self,
        task: TaskSummary,
        events: list[ToolEvent],
        repairs: list[Any],
        feedback: list[FeedbackTelemetryEntry],
    ) -> str:
        if any(item.action == "rolled_back" for item in feedback) or self._event_count(events, "rollback"):
            return "rolled_back"
        if task.status == "completed":
            if self._validation_failures(events) and not self._validation_passes(events) and repairs:
                return "failed"
            return "success"
        if task.status in {"failed", "canceled", "blocked"}:
            return task.status
        return "unknown"

    def _validation_runs(self, events: list[ToolEvent]) -> int:
        return sum(1 for event in events if event.kind == "command" or event.kind.startswith("validation"))

    def _validation_passes(self, events: list[ToolEvent]) -> int:
        return sum(1 for event in events if self._event_exit_code(event) == 0 or (event.kind.startswith("validation") and event.status == "ok"))

    def _validation_failures(self, events: list[ToolEvent]) -> int:
        return sum(1 for event in events if self._event_exit_code(event) not in {None, 0} or (event.kind.startswith("validation") and event.status == "error"))

    def _event_exit_code(self, event: ToolEvent) -> int | None:
        value = event.payload.get("exit_code") if isinstance(event.payload, dict) else None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _event_count(self, events: list[ToolEvent], needle: str) -> int:
        lowered = needle.lower()
        return sum(1 for event in events if lowered in f"{event.kind} {event.title} {event.detail}".lower())

    def _approval_count(self, events: list[ToolEvent], approved: bool) -> int:
        return sum(1 for event in events if event.kind == "approval" and bool(event.payload.get("approved")) is approved)

    def _completion_seconds(self, started: str, finished: str | None) -> float | None:
        if not started or not finished:
            return None
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            finish_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            return max(0.0, (finish_dt - start_dt).total_seconds())
        except ValueError:
            return None

    def _winning_attempt(self, attempts: list[ModelAttemptTelemetryEntry]) -> ModelAttemptTelemetryEntry | None:
        for attempt in reversed(attempts):
            if attempt.attempt.status in {"succeeded", "success", "completed"}:
                return attempt
        return attempts[-1] if attempts else None

    def _winning_model(self, attempts: list[ModelAttemptTelemetryEntry]) -> str:
        attempt = self._winning_attempt(attempts)
        return attempt.attempt.model if attempt else ""

    def _winning_provider(self, attempts: list[ModelAttemptTelemetryEntry]) -> str:
        attempt = self._winning_attempt(attempts)
        return attempt.attempt.provider_id if attempt else ""

    def _winning_role(
        self,
        attempts: list[ModelAttemptTelemetryEntry],
        context: ContextBudgetTelemetryEntry | None,
    ) -> str:
        attempt = self._winning_attempt(attempts)
        if attempt and attempt.attempt.role:
            return attempt.attempt.role
        return context.route_role if context else ""

    def _routing_path(self, attempts: list[ModelAttemptTelemetryEntry]) -> list[str]:
        path: list[str] = []
        for entry in attempts:
            value = entry.attempt.provider_id or entry.attempt.provider_label or entry.attempt.model
            if value and value not in path:
                path.append(value)
        return path

    def _context_files(self, context: ContextBudgetTelemetryEntry | None) -> list[str]:
        if context is None:
            return []
        refs: list[str] = []
        for item in context.payload.items:
            if item.included and item.kind in {"file", "workspace_file", "source"} and item.ref:
                refs.append(item.ref)
        return refs

    def _memory_refs(self, context: ContextBudgetTelemetryEntry | None) -> list[str]:
        if context is None:
            return []
        refs: list[str] = []
        for item in context.payload.items:
            if item.included and "memory" in item.kind and item.ref:
                refs.append(item.ref)
        return refs

    def _rate(self, numerator: int | float, denominator: int | float) -> float:
        if denominator <= 0:
            return 0.0
        return max(0.0, min(1.0, float(numerator) / float(denominator)))

    def _confidence(self, sample_size: int) -> float:
        return max(0.05, min(1.0, sample_size / 20))

    def _outcome_trend(self, outcomes: list[TaskOutcomeRecord]) -> str:
        if len(outcomes) < 6:
            return "unknown"
        latest = outcomes[: max(3, len(outcomes) // 2)]
        older = outcomes[max(3, len(outcomes) // 2) :]
        latest_rate = self._rate(sum(1 for item in latest if item.success), len(latest))
        older_rate = self._rate(sum(1 for item in older if item.success), len(older))
        if latest_rate > older_rate + 0.12:
            return "improving"
        if latest_rate + 0.12 < older_rate:
            return "declining"
        return "stable"

    def _context_quality_score(
        self,
        context_budgets: list[ContextBudgetTelemetryEntry],
        outcomes: list[TaskOutcomeRecord],
    ) -> float:
        if not context_budgets:
            return 0.0
        pressure_penalties = []
        for budget in context_budgets:
            utilization = budget.estimated_context_tokens / budget.max_context_tokens if budget.max_context_tokens else 0.0
            pressure_penalties.append(max(0.0, min(1.0, utilization)))
        average_pressure = sum(pressure_penalties) / len(pressure_penalties)
        successful_with_context = [item for item in outcomes if item.success and item.context_files]
        context_success_bonus = self._rate(len(successful_with_context), max(1, sum(1 for item in outcomes if item.context_files)))
        return max(0.0, min(1.0, (1.0 - average_pressure * 0.35) * 0.55 + context_success_bonus * 0.45))

    def _failure_signature(self, outcome: TaskOutcomeRecord) -> str:
        text = (outcome.error_summary or "").strip().lower()
        return " ".join(text.split())[:120]

    def _stable_id(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _outcome_score(self, outcome: TaskOutcomeRecord) -> float:
        base = 0.72 if outcome.success else 0.28
        base += min(0.12, outcome.validation_pass_rate * 0.12)
        base -= min(0.18, outcome.repair_count * 0.04)
        base -= min(0.18, outcome.rollback_count * 0.12)
        return max(0.0, min(1.0, base))

    def _suite_score(
        self,
        suite_id: str,
        outcomes: list[TaskOutcomeRecord],
        route_quality: RouteQualityResponse,
    ) -> float:
        completed = [item for item in outcomes if item.outcome in {"success", "failed", "rolled_back"}]
        completion = self._rate(sum(1 for item in completed if item.success), len(completed))
        validation = self._rate(sum(item.validation_passes for item in outcomes), sum(item.validation_runs for item in outcomes))
        repair_tasks = [item for item in completed if item.repair_count or item.validation_failures]
        repair = self._rate(sum(1 for item in repair_tasks if item.success), len(repair_tasks))
        route = route_quality.overview.success_rate
        context = 0.55
        weights = {
            "project_scaffolding": (completion, validation, route),
            "debugging": (repair, completion, validation),
            "repair_quality": (repair, validation, completion),
            "reasoning": (route, completion, validation),
            "code_review": (completion, route, validation),
            "architecture_planning": (completion, route, context or 0.55),
            "validation_success": (validation, completion, repair),
        }.get(suite_id, (completion, validation, route))
        return max(0.0, min(1.0, sum(weights) / len(weights)))

    def _suite_metrics(
        self,
        suite_id: str,
        outcomes: list[TaskOutcomeRecord],
        route_quality: RouteQualityResponse,
    ) -> dict[str, float]:
        terminal = [item for item in outcomes if item.outcome in {"success", "failed", "rolled_back"}]
        validation_runs = sum(item.validation_runs for item in outcomes)
        return {
            "task_success_rate": self._rate(sum(1 for item in terminal if item.success), len(terminal)),
            "validation_pass_rate": self._rate(sum(item.validation_passes for item in outcomes), validation_runs),
            "repair_pressure_rate": self._rate(sum(1 for item in outcomes if item.repair_count > 0), len(outcomes)),
            "route_success_rate": route_quality.overview.success_rate,
            "sample_size": float(len(outcomes)),
        }

    def _previous_benchmark_score(
        self,
        store: Any,
        project_root: Path,
        suite_id: str,
        fallback: float,
    ) -> float:
        reports = [item for item in store.adaptive_benchmark_reports(project_root=project_root, limit=50) if item.suite_id == suite_id]
        if not reports:
            return fallback
        return reports[0].candidate_score

    def _benchmark_repro_key(
        self,
        suite_id: str,
        outcomes: list[TaskOutcomeRecord],
        route_quality: RouteQualityResponse,
    ) -> str:
        payload = "|".join(
            [
                suite_id,
                str(len(outcomes)),
                str(sum(1 for item in outcomes if item.success)),
                str(route_quality.overview.model_attempt_count),
                f"{route_quality.overview.success_rate:.4f}",
            ]
        )
        return self._stable_id(payload)

    def _benchmark_recommendations(self, suite_id: str, candidate: float, baseline: float, regression: bool) -> list[str]:
        if regression:
            return [f"Review {suite_id} replay results before promoting new routing or context policy changes."]
        if candidate < 0.55:
            return [f"{suite_id} quality is weak; collect more successful examples before relying on adaptation."]
        return [f"{suite_id} is stable enough to use as a regression guard."]

    def _replay_differences(
        self,
        outcome: TaskOutcomeRecord,
        replay_route: list[str],
        previous: float,
        replay: float,
    ) -> list[str]:
        differences: list[str] = []
        if replay_route and replay_route != outcome.routing_path:
            differences.append("Route ranking changed for this task profile.")
        if abs(replay - previous) >= 0.03:
            differences.append(f"Replay score changed from {previous:.2f} to {replay:.2f}.")
        if outcome.repair_count:
            differences.append("Historical repair pressure was included in the replay penalty.")
        return differences

    def _replay_recommendations(self, status: str) -> list[str]:
        if status == "regressed":
            return ["Do not promote the current adaptive route without reviewing the replay diff."]
        if status == "improved":
            return ["The active profile appears better for this historical task; keep monitoring real outcomes."]
        return ["Replay matched historical behavior; no policy change is suggested from this task alone."]

    def _completion_recommendations(self, success_rate: float, outcomes: list[TaskOutcomeRecord]) -> list[str]:
        if not outcomes:
            return ["Complete a few tracked tasks before adaptive completion scoring becomes meaningful."]
        if success_rate < 0.65:
            return ["Prefer safer routing and stricter validation until completion rate recovers."]
        return ["Completion rate is healthy; route changes can be evaluated with replay before promotion."]

    def _repair_recommendations(self, repair_tasks: list[TaskOutcomeRecord]) -> list[str]:
        if not repair_tasks:
            return ["No repair-heavy tasks were found in the recent outcome window."]
        failed = [item for item in repair_tasks if not item.success]
        if failed:
            return ["Stop repeated repair loops sooner and surface the recurring failure signature."]
        return ["Successful repair patterns are available for future validation failures."]

    def _validation_recommendations(self, outcomes: list[TaskOutcomeRecord]) -> list[str]:
        failures = sum(item.validation_failures for item in outcomes)
        if failures:
            return ["Attach validation failures to replay reports so repair strategy changes can be checked."]
        return ["Validation has not reported failures in the recent adaptive window."]

    def _context_recommendations(
        self,
        context_budgets: list[ContextBudgetTelemetryEntry],
        context_score: float,
    ) -> list[str]:
        if not context_budgets:
            return ["Record context budgets before optimizing file selection."]
        if context_score < 0.55:
            return ["Prefer Project Intelligence summaries and high-importance files to reduce context waste."]
        return ["Context selection is stable; keep tracking which files appear in successful tasks."]

    def _feedback_recommendations(self, positive: int, negative: int) -> list[str]:
        if positive + negative == 0:
            return ["Ask for lightweight feedback on accepted changes to improve routing attribution."]
        if negative > positive:
            return ["Review rejected and rolled-back outputs before changing route preferences."]
        return ["Positive feedback can be used as a secondary route-quality signal."]

    def _snapshot_recommendations(
        self,
        quality_scores: list[AdaptiveQualityScore],
        route_recommendations: list[AdaptiveRouteRecommendation],
        repair_insights: list[AdaptiveInsight],
        context_insights: list[AdaptiveInsight],
        feedback_insights: list[AdaptiveInsight],
    ) -> list[str]:
        recommendations: list[str] = []
        weak_scores = [item for item in quality_scores if item.score < 0.55 and item.sample_size > 0]
        if weak_scores:
            recommendations.append(f"Review {weak_scores[0].label}; it is the weakest current adaptive signal.")
        if route_recommendations:
            recommendations.append(f"Top route candidate: {route_recommendations[0].provider_label or route_recommendations[0].provider_id}.")
        high_repair = [item for item in repair_insights if item.severity in {"medium", "high"}]
        if high_repair:
            recommendations.append("Use recurring repair insights before starting a new repair loop.")
        pressure = [item for item in context_insights if item.key == "budget-pressure"]
        if pressure:
            recommendations.append("Context budget pressure is high; prefer ranked project notes over broad source dumps.")
        negative_feedback = [item for item in feedback_insights if item.severity == "medium"]
        if negative_feedback:
            recommendations.append("Feedback shows at least one weak route or target; inspect before promotion.")
        return recommendations or ["Adaptive signals are stable; continue collecting task outcomes and feedback."]
