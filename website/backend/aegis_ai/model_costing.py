from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .context_budget import ContextBudgetResult
from .model_execution import ModelExecutionPlan
from .model_tokenizer import ModelTokenEstimator
from .schemas import ModelAttemptInfo


@dataclass(frozen=True)
class ModelCostEstimator:
    """Adds planning-time token and cost estimates to model attempts.

    The estimator stays metadata-driven and safe for offline planning. It does
    not call providers; token estimation is delegated to provider-family hooks
    with deterministic fallback when exact local tokenizers are unavailable.
    """

    overhead_tokens: int = 900
    token_estimator: ModelTokenEstimator = field(default_factory=ModelTokenEstimator)

    def estimate_plan(self, plan: ModelExecutionPlan, context_budget: ContextBudgetResult) -> ModelExecutionPlan:
        attempts = [self.estimate_attempt(attempt, context_budget) for attempt in plan.attempts]
        return ModelExecutionPlan(attempts=attempts)

    def estimate_attempt(
        self,
        attempt: ModelAttemptInfo,
        context_budget: ContextBudgetResult,
    ) -> ModelAttemptInfo:
        token_estimate = self.token_estimator.estimate_attempt(
            attempt,
            context_budget,
            default_overhead_tokens=self.overhead_tokens,
        )
        input_tokens = token_estimate.input_tokens
        output_tokens = token_estimate.output_tokens
        input_cost = self._float_or_none(attempt.metadata.get("input_cost_per_million"))
        output_cost = self._float_or_none(attempt.metadata.get("output_cost_per_million"))
        estimated_cost = self._estimate_cost(input_tokens, output_tokens, input_cost, output_cost)
        context_window = self._int_or_none(attempt.metadata.get("context_window"))
        utilization = None
        if context_window and context_window > 0:
            utilization = min(1.0, (input_tokens + output_tokens) / context_window)

        metadata = {
            **attempt.metadata,
            "context_strategy": context_budget.profile.strategy,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_total_tokens": input_tokens + output_tokens,
            "estimated_context_tokens": context_budget.estimated_context_tokens,
            "reserved_response_tokens": output_tokens,
            "context_window_utilization": utilization,
            "cost_estimate_source": "registry_metadata" if estimated_cost is not None else "missing_cost_metadata",
            **token_estimate.metadata(),
        }
        return attempt.model_copy(
            update={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost,
                "metadata": metadata,
            }
        )

    def _estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_million: float | None,
        output_cost_per_million: float | None,
    ) -> float | None:
        if input_cost_per_million is None and output_cost_per_million is None:
            return None
        input_cost = (input_tokens / 1_000_000) * (input_cost_per_million or 0.0)
        output_cost = (output_tokens / 1_000_000) * (output_cost_per_million or 0.0)
        return round(input_cost + output_cost, 6)

    def _float_or_none(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    def _int_or_none(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None
