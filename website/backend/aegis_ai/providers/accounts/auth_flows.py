from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AuthFlowKind = Literal["api_key", "oauth_browser", "device_code", "cli_bridge", "env_profile", "none"]


@dataclass(frozen=True)
class AuthFlowDescriptor:
    kind: AuthFlowKind
    implemented: bool
    summary: str
    security_boundary: str


FOUNDATION_AUTH_FLOWS: tuple[AuthFlowDescriptor, ...] = (
    AuthFlowDescriptor(
        kind="api_key",
        implemented=True,
        summary="Store the secret in the OS credential vault and keep only a credential reference in SQLite.",
        security_boundary="Aegis never stores the raw key in registry files, telemetry, or provider account rows.",
    ),
    AuthFlowDescriptor(
        kind="cli_bridge",
        implemented=True,
        summary="Detect official provider CLIs and delegate through allowlisted commands without importing tokens.",
        security_boundary="Aegis runs status/version probes only and does not read provider token files.",
    ),
    AuthFlowDescriptor(
        kind="oauth_browser",
        implemented=False,
        summary="Reserved for Aegis-owned OAuth app registrations with PKCE and state checks.",
        security_boundary="Do not copy OAuth client credentials from external CLIs.",
    ),
    AuthFlowDescriptor(
        kind="device_code",
        implemented=False,
        summary="Reserved for provider-supported device-code login initiated by Aegis.",
        security_boundary="Device codes must be user-visible and never logged after exchange.",
    ),
    AuthFlowDescriptor(
        kind="env_profile",
        implemented=False,
        summary="Reserved for official enterprise profiles such as AWS, Azure, and Google ADC.",
        security_boundary="Aegis records profile metadata and relies on official SDK or CLI auth.",
    ),
)
