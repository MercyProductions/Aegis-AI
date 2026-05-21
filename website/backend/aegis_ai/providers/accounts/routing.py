from __future__ import annotations

from .models import ProviderAccountStatus


def provider_route_weight(provider: ProviderAccountStatus, *, private_task: bool = False, long_context: bool = False) -> float:
    """Small foundation scoring helper for account-aware routing previews."""

    manifest = provider.manifest
    status = str(provider.connection_status).lower()
    capabilities = {item.strip().lower() for item in manifest.capabilities}
    score = 0.0

    if getattr(provider, "execution_ready", False):
        score += 3.0
    readiness = str(getattr(provider, "readiness", "") or "").lower()
    if status == "linked":
        score += 4.0
    elif readiness == "runtime_verified":
        score += 2.0
    elif status == "unknown" and provider.cli_bridge and provider.cli_bridge.binary_path:
        score += 1.5
    elif status in {"limited", "expired", "error"}:
        score -= 3.0
    elif status == "not_configured":
        score -= 2.0

    if private_task and ("local" in capabilities or manifest.kind == "local"):
        score += 3.0
    if long_context and ("long_context" in capabilities or "large_context" in capabilities):
        score += 2.0
    if "code" in capabilities:
        score += 0.75
    if "agent_delegation" in capabilities:
        score += 0.5

    return score
