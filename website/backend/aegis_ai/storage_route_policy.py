from __future__ import annotations

from typing import Any

from .schemas import (
    FeedbackAttributionRollup,
    ModelAttemptTelemetryEntry,
    RoutePolicyProviderProposal,
    RoutePolicyRoleProposal,
    RouteQualityProviderRollup,
    RouteQualityResponse,
    RouteQualityRoleRollup,
)
from .storage_helpers import rate


def route_policy_provider_proposals(
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
        score = route_policy_provider_score(provider, feedback)
        terminal_attempts = provider.successes + provider.failures
        action = route_policy_provider_action(provider, feedback, terminal_attempts, min_attempts)
        reasons = route_policy_provider_reasons(provider, feedback, terminal_attempts)
        risks = route_policy_provider_risks(provider, feedback, terminal_attempts, min_attempts)
        proposals.append(
            RoutePolicyProviderProposal(
                provider_id=provider.provider_id,
                provider_label=provider.provider_label,
                provider_api=provider.provider_api,
                model=provider.model,
                observed_rank=observed_rank,
                action=action,
                risk_level=route_policy_risk_level(risks),
                confidence=route_policy_confidence(terminal_attempts, feedback.feedback_count if feedback else 0, min_attempts),
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

def route_policy_role_proposals(
    route_quality: RouteQualityResponse,
    model_attempts: list[ModelAttemptTelemetryEntry],
    provider_proposals: list[RoutePolicyProviderProposal],
    min_attempts: int,
) -> list[RoutePolicyRoleProposal]:
    provider_scores = {
        route_policy_provider_key_from_parts(
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
        provider_key = route_policy_provider_key_from_parts(
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
        observed_primary = route_policy_observed_primary(provider_groups)
        provider_scores_for_role = {
            key: route_policy_role_provider_score(key, group, provider_scores)
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
        action = route_policy_role_action(role, observed_primary, proposed_primary, score_delta, min_attempts)
        reasons = route_policy_role_reasons(role, observed_primary, proposed_primary, score_delta)
        risks = route_policy_role_risks(role, provider_groups, min_attempts)
        proposals.append(
            RoutePolicyRoleProposal(
                role=role.role,
                action=action,
                observed_primary_provider=observed_primary,
                proposed_primary_provider=proposed_primary,
                confidence=route_policy_confidence(role.successes + role.failures, 0, min_attempts),
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

def route_policy_provider_score(
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

def route_policy_provider_action(
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

def route_policy_provider_reasons(
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

def route_policy_provider_risks(
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

def route_policy_role_provider_score(
    provider_key: str,
    group: dict[str, Any],
    provider_scores: dict[str, float],
) -> float:
    attempts = int(group["attempts"])
    successes = int(group["successes"])
    failures = int(group["failures"])
    fallback_rate = rate(int(group["fallbacks"]), attempts)
    role_success_rate = rate(successes, successes + failures)
    base_score = provider_scores.get(provider_key, 45.0)
    if successes + failures == 0:
        return round(min(base_score, 35.0), 2)
    return round((base_score * 0.45) + (role_success_rate * 100.0 * 0.45) - (fallback_rate * 10.0), 2)

def route_policy_observed_primary(provider_groups: dict[str, dict[str, Any]]) -> str:
    if not provider_groups:
        return ""
    return max(provider_groups.items(), key=lambda item: int(item[1]["attempts"]))[0]

def route_policy_role_action(
    role: RouteQualityRoleRollup,
    observed_primary: str,
    proposed_primary: str,
    score_delta: float,
    min_attempts: int,
) -> str:
    terminal_attempts = role.successes + role.failures
    fallback_rate = rate(role.fallback_attempts, role.attempts)
    if terminal_attempts < min_attempts:
        return "keep"
    if proposed_primary and observed_primary and proposed_primary != observed_primary and score_delta >= 8.0:
        return "switch_primary"
    if role.success_rate < 0.70:
        return "strengthen_fallback"
    if fallback_rate >= 0.30:
        return "rebalance"
    return "keep"

def route_policy_role_reasons(
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

def route_policy_role_risks(
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
    if rate(role.fallback_attempts, role.attempts) >= 0.30:
        risks.append("Role has elevated fallback traffic.")
    return risks

def route_policy_warnings(
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

def route_policy_recommendations(
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

def route_policy_confidence(terminal_attempts: int, feedback_count: int, min_attempts: int) -> float:
    attempt_weight = min(0.65, terminal_attempts / max(min_attempts * 6, 1))
    feedback_weight = min(0.20, feedback_count / 50)
    return round(min(0.95, 0.15 + attempt_weight + feedback_weight), 2)

def route_policy_risk_level(risks: list[str]) -> str:
    if any("below" in risk.lower() or "negative" in risk.lower() for risk in risks):
        return "high"
    if risks:
        return "medium"
    return "low"

def route_policy_provider_key_from_parts(
    provider_id: str,
    provider_label: str,
    provider_api: str,
    model: str,
) -> str:
    return provider_id or provider_label or provider_api or model or "unknown"
