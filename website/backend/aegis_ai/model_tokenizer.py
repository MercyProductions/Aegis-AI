from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any

from .context_budget import CHARS_PER_TOKEN, ContextBudgetResult
from .schemas import ModelAttemptInfo


@dataclass(frozen=True)
class TokenizerProfile:
    family: str
    tokenizer: str
    chars_per_token: float = float(CHARS_PER_TOKEN)
    overhead_tokens: int = 900
    source: str = "deterministic_chars"
    confidence: float = 0.42
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TokenEstimate:
    input_tokens: int
    output_tokens: int
    family: str
    tokenizer: str
    source: str
    chars_per_token: float
    overhead_tokens: int
    confidence: float
    notes: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "token_estimator_family": self.family,
            "token_estimator": self.tokenizer,
            "token_estimate_source": self.source,
            "token_estimate_chars_per_token": self.chars_per_token,
            "token_estimate_overhead_tokens": self.overhead_tokens,
            "token_estimate_confidence": self.confidence,
            "token_estimate_notes": self.notes,
        }


class ModelTokenEstimator:
    """Provider-aware planning estimates with deterministic offline fallback.

    This layer does not contact model providers. When optional local tokenizer
    libraries are unavailable or raw text is not supplied, it uses provider and
    model-family profiles to adjust aggregate character-based estimates.
    """

    base_chars_per_token: float = float(CHARS_PER_TOKEN)

    def estimate_attempt(
        self,
        attempt: ModelAttemptInfo,
        context_budget: ContextBudgetResult,
        *,
        default_overhead_tokens: int = 900,
    ) -> TokenEstimate:
        profile = self.profile_for(
            provider_api=attempt.provider_api,
            model=attempt.model,
            endpoint=attempt.endpoint,
            provider_id=attempt.provider_id,
            provider_label=attempt.provider_label,
        )
        overhead_tokens = profile.overhead_tokens or default_overhead_tokens
        context_tokens = self.adjust_aggregate_tokens(context_budget.estimated_context_tokens, profile)
        output_tokens = max(0, int(context_budget.reserve_response_tokens))
        notes = list(profile.notes)
        if profile.source != "exact_tokenizer":
            notes.append("Derived from aggregate context-budget tokens; exact prompt text was not retokenized.")

        return TokenEstimate(
            input_tokens=max(0, context_tokens + overhead_tokens),
            output_tokens=output_tokens,
            family=profile.family,
            tokenizer=profile.tokenizer,
            source=profile.source,
            chars_per_token=profile.chars_per_token,
            overhead_tokens=overhead_tokens,
            confidence=profile.confidence,
            notes=notes,
        )

    def estimate_text(
        self,
        text: str,
        *,
        provider_api: str = "",
        model: str = "",
        endpoint: str = "",
        provider_id: str = "",
        provider_label: str = "",
    ) -> TokenEstimate:
        profile = self.profile_for(
            provider_api=provider_api,
            model=model,
            endpoint=endpoint,
            provider_id=provider_id,
            provider_label=provider_label,
        )
        exact_count = self._try_tiktoken_count(text, profile)
        if exact_count is not None:
            return TokenEstimate(
                input_tokens=exact_count,
                output_tokens=0,
                family=profile.family,
                tokenizer=profile.tokenizer,
                source="exact_tokenizer",
                chars_per_token=profile.chars_per_token,
                overhead_tokens=0,
                confidence=0.95,
                notes=["Estimated from local tokenizer library without contacting a provider."],
            )

        return TokenEstimate(
            input_tokens=max(0, round(len(text) / max(profile.chars_per_token, 1.0))),
            output_tokens=0,
            family=profile.family,
            tokenizer=profile.tokenizer,
            source=profile.source,
            chars_per_token=profile.chars_per_token,
            overhead_tokens=0,
            confidence=profile.confidence,
            notes=[*profile.notes, "Estimated from text length using provider-family profile."],
        )

    def adjust_aggregate_tokens(self, tokens: int, profile: TokenizerProfile) -> int:
        if tokens <= 0:
            return 0
        if profile.chars_per_token <= 0:
            return tokens
        multiplier = self.base_chars_per_token / profile.chars_per_token
        return max(1, round(tokens * multiplier))

    def profile_for(
        self,
        *,
        provider_api: str = "",
        model: str = "",
        endpoint: str = "",
        provider_id: str = "",
        provider_label: str = "",
    ) -> TokenizerProfile:
        haystack = " ".join([provider_api, model, endpoint, provider_id, provider_label]).strip().lower()
        api = provider_api.strip().lower()
        model_lower = model.strip().lower()

        if "claude" in haystack or api == "anthropic":
            return TokenizerProfile(
                family="anthropic_claude",
                tokenizer="anthropic_family_profile",
                chars_per_token=3.75,
                overhead_tokens=1150,
                source="provider_profile",
                confidence=0.58,
                notes=("Claude token estimates use an offline family profile until an Anthropic tokenizer is available.",),
            )

        if "perplexity" in haystack or "sonar" in haystack:
            return TokenizerProfile(
                family="perplexity_sonar",
                tokenizer="sonar_family_profile",
                chars_per_token=3.85,
                overhead_tokens=1000,
                source="provider_profile",
                confidence=0.52,
                notes=("Perplexity estimates include a modest research-route overhead.",),
            )

        if "qwen" in haystack:
            return TokenizerProfile(
                family="qwen_coder",
                tokenizer="qwen_family_profile",
                chars_per_token=3.55,
                overhead_tokens=850,
                source="provider_profile",
                confidence=0.54,
                notes=("Qwen/code models usually tokenize dense code slightly above the default estimate.",),
            )

        if "deepseek" in haystack:
            return TokenizerProfile(
                family="deepseek_code",
                tokenizer="deepseek_family_profile",
                chars_per_token=3.60,
                overhead_tokens=900,
                source="provider_profile",
                confidence=0.54,
                notes=("DeepSeek/code estimates use a code-biased offline family profile.",),
            )

        if any(name in haystack for name in ("llama", "mistral", "mixtral", "gemma")):
            return TokenizerProfile(
                family="local_open_weights",
                tokenizer="open_weights_family_profile",
                chars_per_token=3.90,
                overhead_tokens=850,
                source="provider_profile",
                confidence=0.50,
                notes=("Open-weight local models use a conservative local-family estimate.",),
            )

        if api == "openai" or any(name in model_lower for name in ("gpt-", "gpt4", "o1", "o3", "o4")):
            tokenizer = "o200k_base" if any(name in model_lower for name in ("gpt-4.1", "gpt-4o", "o1", "o3", "o4", "gpt-5")) else "cl100k_base"
            return TokenizerProfile(
                family="openai",
                tokenizer=tokenizer,
                chars_per_token=3.80,
                overhead_tokens=1050,
                source="provider_profile",
                confidence=0.64,
                notes=("OpenAI estimates can upgrade to local tiktoken counts when raw text is supplied.",),
            )

        if "openrouter" in haystack:
            return TokenizerProfile(
                family="openrouter_generic",
                tokenizer="router_family_profile",
                chars_per_token=3.80,
                overhead_tokens=1050,
                source="provider_profile",
                confidence=0.45,
                notes=("OpenRouter estimates are generic until the routed model family is explicit.",),
            )

        if api in {"ollama", "lmstudio", "openai-compatible"} or "127.0.0.1" in haystack or "localhost" in haystack:
            return TokenizerProfile(
                family="local_generic",
                tokenizer="local_generic_profile",
                chars_per_token=3.85,
                overhead_tokens=850,
                source="provider_profile",
                confidence=0.46,
                notes=("Local-compatible model family was not explicit; using a conservative local profile.",),
            )

        return TokenizerProfile(
            family="deterministic_default",
            tokenizer="chars_per_token_default",
            chars_per_token=float(CHARS_PER_TOKEN),
            overhead_tokens=900,
            source="deterministic_chars",
            confidence=0.38,
            notes=("No provider-specific tokenizer profile matched.",),
        )

    def _try_tiktoken_count(self, text: str, profile: TokenizerProfile) -> int | None:
        if profile.tokenizer not in {"cl100k_base", "o200k_base"}:
            return None
        try:
            tiktoken = importlib.import_module("tiktoken")
            encoding = tiktoken.get_encoding(profile.tokenizer)
        except Exception:
            return None
        try:
            return len(encoding.encode(text))
        except Exception:
            return None
