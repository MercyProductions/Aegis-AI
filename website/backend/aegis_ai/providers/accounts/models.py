from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AuthMode = Literal["api_key", "oauth_browser", "device_code", "cli_bridge", "env_profile", "none"]
ConnectionStatus = Literal["not_configured", "linked", "expired", "limited", "offline", "error", "unknown"]


class ProviderCliBridgeManifest(BaseModel):
    cli_name: str = ""
    candidate_binaries: list[str] = Field(default_factory=list)
    version_args: list[str] = Field(default_factory=lambda: ["--version"])
    status_args: list[str] = Field(default_factory=list)
    login_args: list[str] = Field(default_factory=list)
    delegation_modes: list[str] = Field(default_factory=list)
    notes: str = ""


class ProviderAccountManifest(BaseModel):
    id: str
    label: str
    kind: str = "cloud"
    description: str = ""
    auth_modes: list[AuthMode] = Field(default_factory=list)
    default_auth_mode: AuthMode = "api_key"
    credential_env_vars: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    model_families: list[str] = Field(default_factory=list)
    quota_status: str = "unknown"
    docs_url: str = ""
    security_notes: list[str] = Field(default_factory=list)
    cli_bridge: ProviderCliBridgeManifest | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("auth_modes", "credential_env_vars", "capabilities", "model_families", "security_notes")
    @classmethod
    def _clean_string_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value or []:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned


class ProviderLinkedAccount(BaseModel):
    account_id: str
    provider_id: str
    provider_label: str = ""
    auth_mode: AuthMode | str = "api_key"
    status: ConnectionStatus | str = "unknown"
    account_label: str = ""
    subject_hash: str = ""
    credential_ref: str = ""
    credential_hint: str = ""
    session_ref: str = ""
    scopes: list[str] = Field(default_factory=list)
    quota_status: str = "unknown"
    expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_validated_at: str = ""
    last_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSessionInfo(BaseModel):
    session_id: str
    account_id: str
    provider_id: str
    auth_mode: AuthMode | str = "api_key"
    status: ConnectionStatus | str = "unknown"
    credential_ref: str = ""
    refresh_supported: bool = False
    expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_refresh_at: str = ""
    last_refresh_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderCliBridgeInfo(BaseModel):
    provider_id: str
    cli_name: str = ""
    binary_path: str = ""
    version: str = ""
    status: ConnectionStatus | str = "unknown"
    auth_status: ConnectionStatus | str = "unknown"
    probe_command: str = ""
    supported_delegation_modes: list[str] = Field(default_factory=list)
    last_probe_at: str = ""
    last_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSourceRootInfo(BaseModel):
    path: str
    exists: bool = False
    provider_ids: list[str] = Field(default_factory=list)
    provider_labels: list[str] = Field(default_factory=list)
    child_count: int = 0
    modified_at: str = ""
    last_probe_at: str = ""
    updated_after_probe: bool = False
    freshness: str = "unknown"
    freshness_label: str = "Unknown"
    freshness_detail: str = ""


class ProviderSourceDropInfo(BaseModel):
    provider_id: str
    provider_label: str = ""
    cli_name: str = ""
    source_root: str = ""
    detected_from: str = ""
    source_candidate: str = ""
    path: str = ""
    cwd: str = ""
    display: str = ""
    command: str = ""
    version: str = ""
    status: str = "detected"
    auth_status: str = "unknown"
    last_probe_at: str = ""
    modified_at: str = ""
    updated_after_probe: bool = False
    freshness: str = "unknown"
    freshness_label: str = "Unknown"
    freshness_detail: str = ""
    refresh_actions: list["ProviderSourceRefreshAction"] = Field(default_factory=list)
    last_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSourceRefreshAction(BaseModel):
    id: str
    label: str = ""
    cwd: str = ""
    command: str = ""
    command_parts: list[str] = Field(default_factory=list, exclude=True)
    available: bool = False
    detail: str = ""
    timeout_seconds: int = 120


class ProviderSourceRefreshRequest(BaseModel):
    provider_id: str
    action_id: str = ""
    source_root: str = ""
    source_candidate: str = ""
    dry_run: bool = False


class ProviderSourceRefreshResponse(BaseModel):
    ok: bool = False
    provider_id: str
    provider_label: str = ""
    action_id: str = ""
    action_label: str = ""
    status: Literal["planned", "completed", "failed", "timed_out", "not_configured", "unsupported"] | str = "failed"
    command: str = ""
    cwd: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    snapshot: "ProviderAccountsResponse | None" = None


class ProviderSourceRefreshJobInfo(BaseModel):
    id: str
    provider_id: str
    provider_label: str = ""
    action_id: str = ""
    action_label: str = ""
    source_root: str = ""
    source_candidate: str = ""
    status: Literal[
        "queued",
        "running",
        "completed",
        "failed",
        "timed_out",
        "not_configured",
        "unsupported",
        "interrupted",
        "canceled",
    ] | str = "queued"
    command: str = ""
    cwd: str = ""
    pid: int | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSourceRefreshJobResponse(BaseModel):
    job: ProviderSourceRefreshJobInfo
    snapshot: "ProviderAccountsResponse | None" = None


class ProviderSourceRefreshJobsResponse(BaseModel):
    jobs: list[ProviderSourceRefreshJobInfo] = Field(default_factory=list)
    snapshot: "ProviderAccountsResponse | None" = None


class ProviderRouteSafety(BaseModel):
    route_type: (
        Literal["local_endpoint", "api_key", "cli_bridge", "environment_profile", "oauth_pending", "unsupported"]
        | str
    ) = "unsupported"
    privacy_boundary: Literal["local", "cloud", "enterprise_cloud", "provider_cli", "unknown"] | str = "unknown"
    secret_policy: str = ""
    secret_storage: (
        Literal["none", "os_credential_store", "provider_cli_only", "environment_profile", "oauth_pending"] | str
    ) = "none"
    cloud_context_requires_consent: bool = False
    sends_workspace_context: bool = False
    cost_boundary: str = ""
    quota_boundary: str = ""
    latency_boundary: str = ""
    fallback_policy: str = ""
    diagnostics_safe: bool = True
    user_action_required: str = ""


class ProviderAccountStatus(BaseModel):
    manifest: ProviderAccountManifest
    account: ProviderLinkedAccount | None = None
    cli_bridge: ProviderCliBridgeInfo | None = None
    connection_status: ConnectionStatus | str = "not_configured"
    primary_auth_mode: AuthMode | str = "api_key"
    fallback_eligible: bool = False
    setup_actions: list[str] = Field(default_factory=list)
    execution_ready: bool = False
    readiness: str = "setup_required"
    readiness_label: str = "Setup Required"
    readiness_detail: str = ""
    routing_weight: float = 0.0
    quota_status: str = "unknown"
    model_limit_summary: str = "Provider limits are unknown until Aegis observes responses or the provider exposes quota metadata."
    route_safety: ProviderRouteSafety = Field(default_factory=ProviderRouteSafety)


class ProviderAccountsResponse(BaseModel):
    generated_at: str
    credential_store_available: bool
    providers: list[ProviderAccountStatus] = Field(default_factory=list)
    accounts: list[ProviderLinkedAccount] = Field(default_factory=list)
    sessions: list[ProviderSessionInfo] = Field(default_factory=list)
    cli_bridges: list[ProviderCliBridgeInfo] = Field(default_factory=list)
    source_roots: list[ProviderSourceRootInfo] = Field(default_factory=list)
    source_drops: list[ProviderSourceDropInfo] = Field(default_factory=list)
    source_refresh_jobs: list[ProviderSourceRefreshJobInfo] = Field(default_factory=list)
    security_notes: list[str] = Field(default_factory=list)


class ProviderApiKeyLinkRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=8192)
    account_label: str = Field(default="", max_length=160)
    scopes: list[str] = Field(default_factory=list)

    @field_validator("api_key")
    @classmethod
    def _clean_api_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("API key is required.")
        return cleaned


class ProviderAccountLinkResponse(BaseModel):
    ok: bool = True
    account: ProviderLinkedAccount
    snapshot: ProviderAccountsResponse


class ProviderCliProbeRequest(BaseModel):
    provider_id: str = ""


class ProviderCliLoginResponse(BaseModel):
    ok: bool = False
    provider_id: str
    provider_label: str = ""
    status: Literal["launched", "not_configured", "unsupported", "failed"] | str = "failed"
    command: str = ""
    cwd: str = ""
    pid: int | None = None
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    snapshot: ProviderAccountsResponse | None = None


class ProviderSourceRootOpenRequest(BaseModel):
    path: str = ""


class ProviderSourceRootOpenResponse(BaseModel):
    ok: bool = False
    path: str = ""
    pid: int | None = None
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    snapshot: ProviderAccountsResponse | None = None
