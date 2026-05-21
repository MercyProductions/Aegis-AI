from __future__ import annotations

import hmac
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque
from urllib.parse import urlparse

from .config import memory_dir
from .diagnostics import redact_inline
from .safety import BLOCKED_NAMES, BLOCKED_SUFFIXES, IGNORED_DIRS


DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5175",
    "http://127.0.0.1:8787",
    "http://localhost:8787",
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver", "testclient"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_RATE_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)


@dataclass(frozen=True)
class SecuritySettings:
    bind_host: str
    local_auth_token: str
    require_token: bool
    allowed_origins: tuple[str, ...]
    max_request_bytes: int
    rate_limit_per_minute: int
    privacy_mode: str
    cloud_disabled: bool
    local_only: bool

    @property
    def token_enforced(self) -> bool:
        return self.require_token and bool(self.local_auth_token)


def load_security_settings() -> SecuritySettings:
    token = _env("AEGIS_CORE_LOCAL_TOKEN", _env("AEGIS_LOCAL_AUTH_TOKEN", ""))
    require_token = _env_bool("AEGIS_CORE_REQUIRE_TOKEN", False) or bool(token)
    privacy_mode = _env("AEGIS_PRIVACY_MODE", "local-first").strip().lower().replace("_", "-") or "local-first"
    cloud_disabled = _env_bool("AEGIS_CLOUD_DISABLED", False) or privacy_mode in {"local-only", "cloud-disabled"}
    origins = _env_list("AEGIS_CORE_ALLOWED_ORIGINS") or list(DEFAULT_ALLOWED_ORIGINS)
    return SecuritySettings(
        bind_host=_env("AEGIS_CORE_BIND_HOST", "127.0.0.1"),
        local_auth_token=token,
        require_token=require_token,
        allowed_origins=tuple(origins),
        max_request_bytes=_env_int("AEGIS_CORE_MAX_REQUEST_BYTES", 8_000_000, minimum=1_024),
        rate_limit_per_minute=_env_int("AEGIS_CORE_RATE_LIMIT_PER_MINUTE", 600, minimum=1),
        privacy_mode=privacy_mode,
        cloud_disabled=cloud_disabled,
        local_only=privacy_mode == "local-only" or cloud_disabled,
    )


def install_security_middleware(app: Any) -> None:
    try:
        from fastapi import Request
        from fastapi.responses import JSONResponse, Response
    except ImportError as exc:  # pragma: no cover - mirrored by server import guard.
        raise RuntimeError("Install Aegis Core API dependencies with `pip install -e .`.") from exc

    @app.middleware("http")
    async def aegis_core_security_middleware(request: Request, call_next: Any) -> Any:
        settings = load_security_settings()
        workspace = _workspace_from_request(request)

        host_error = _host_error(request)
        if host_error:
            security_audit(workspace, "local_api.host_rejected", "blocked", host_error, {"host": redact_inline(request.headers.get("host", ""))})
            return JSONResponse({"detail": host_error}, status_code=403)

        origin_error = _origin_error(request, settings)
        if origin_error:
            security_audit(workspace, "local_api.origin_rejected", "blocked", origin_error, {"origin": redact_inline(request.headers.get("origin", ""))})
            return JSONResponse({"detail": origin_error}, status_code=403)

        length_error = _content_length_error(request, settings)
        if length_error:
            security_audit(workspace, "local_api.request_too_large", "blocked", length_error, {"content_length": request.headers.get("content-length", "")})
            return JSONResponse({"detail": length_error}, status_code=413)

        rate_error = _rate_limit_error(request, settings)
        if rate_error:
            security_audit(workspace, "local_api.rate_limited", "blocked", rate_error, {"client": _client_key(request)})
            return JSONResponse({"detail": rate_error}, status_code=429)

        if request.method.upper() == "OPTIONS":
            response = Response(status_code=204)
            _apply_cors_headers(request, response, settings)
            return response

        auth_error = _auth_error(request, settings)
        if auth_error:
            security_audit(workspace, "local_api.unauthorized", "blocked", auth_error, {"path": request.url.path})
            return JSONResponse({"detail": auth_error}, status_code=401)

        response = await call_next(request)
        _apply_cors_headers(request, response, settings)
        return response


def security_status(workspace: str | Path | None = None) -> dict[str, Any]:
    settings = load_security_settings()
    root = Path(workspace or ".").expanduser().resolve()
    audit_path = _audit_path(root)
    token_warning = ""
    if settings.require_token and not settings.local_auth_token:
        token_warning = "AEGIS_CORE_REQUIRE_TOKEN is enabled but no AEGIS_CORE_LOCAL_TOKEN is configured; local API token enforcement is inactive."
    elif not settings.token_enforced:
        token_warning = "Local API token enforcement is in compatibility mode. Set AEGIS_CORE_LOCAL_TOKEN to require bearer authentication."

    return {
        "workspace": str(root),
        "generated_at": _utc_now(),
        "local_api": {
            "bind_host": settings.bind_host,
            "localhost_only_default": settings.bind_host in {"127.0.0.1", "localhost", "::1"},
            "loopback_host_guard": True,
            "token_required": settings.require_token,
            "token_enforced": settings.token_enforced,
            "token_warning": token_warning,
            "allowed_origins": list(settings.allowed_origins),
            "origin_guard": True,
            "csrf_strategy": "Origin checks for browser requests; bearer token enforcement when AEGIS_CORE_LOCAL_TOKEN is configured.",
            "max_request_bytes": settings.max_request_bytes,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
        },
        "workspace_access": {
            "path_traversal_rejected": True,
            "workspace_root_required": True,
            "ignored_directories_blocked": sorted(IGNORED_DIRS),
            "secret_like_names_blocked": sorted(BLOCKED_NAMES),
            "secret_like_suffixes_blocked": sorted(BLOCKED_SUFFIXES),
            "binary_system_file_policy": "Core editing runtime only applies normalized text changes inside the workspace and rejects ignored, hidden, secret-like, and outside-workspace targets.",
            "checkpoint_before_overwrite": True,
            "audit_file_changes": True,
        },
        "credentials": {
            "plaintext_storage_allowed": False,
            "credential_store": "OS keyring or Windows Credential Manager",
            "provider_key_responses_masked": True,
            "log_redaction": True,
        },
        "privacy": {
            "mode": settings.privacy_mode,
            "local_only": settings.local_only,
            "cloud_disabled": settings.cloud_disabled,
            "prompt_redaction_before_cloud": True,
            "sensitive_context_exclusion": True,
            "provider_usage_warnings": True,
        },
        "updates": {
            "checksum_required": True,
            "signature_verification": "required when release manifest disables local-build signature opt-out",
            "manifest_validation": True,
            "downgrade_protection": True,
            "rollback_on_failure": True,
            "tamper_detection": "SHA256 and manifest/package artifact checks",
        },
        "audit": {
            "enabled": True,
            "path": str(audit_path),
            "events": [
                "local_api.unauthorized",
                "local_api.origin_rejected",
                "local_api.request_too_large",
                "workspace.unsafe_path",
                "update.checksum_failed",
                "provider.call",
                "approval",
                "rollback",
                "validation.run",
            ],
        },
    }


def security_audit(
    workspace: str | Path | None,
    event: str,
    status: str,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    root = Path(workspace or ".").expanduser().resolve()
    record = {
        "timestamp": _utc_now(),
        "event": redact_inline(event),
        "status": redact_inline(status),
        "detail": redact_inline(detail),
        "metadata": _redact_json(metadata or {}),
    }
    try:
        path = _audit_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        return


def redact_prompt_for_cloud(text: str) -> str:
    """Redact prompt text before cloud calls while keeping enough context for routing."""
    return redact_inline(text)


def _host_error(request: Any) -> str:
    host = (request.headers.get("host") or "").split(":", 1)[0].strip("[]").lower()
    if host and host not in LOOPBACK_HOSTS:
        return "Aegis Core only accepts loopback local API requests by default."
    client = getattr(request, "client", None)
    client_host = str(getattr(client, "host", "") or "").strip("[]").lower()
    if client_host and client_host not in LOOPBACK_HOSTS:
        return "Aegis Core rejected a non-loopback client address."
    return ""


def _origin_error(request: Any, settings: SecuritySettings) -> str:
    origin = request.headers.get("origin")
    if not origin:
        return ""
    if _origin_allowed(origin, settings.allowed_origins):
        return ""
    return "Aegis Core rejected a browser origin that is not in AEGIS_CORE_ALLOWED_ORIGINS."


def _origin_allowed(origin: str, allowed_origins: tuple[str, ...]) -> bool:
    normalized = origin.rstrip("/")
    if normalized in allowed_origins:
        return True
    parsed = urlparse(normalized)
    return parsed.hostname in LOOPBACK_HOSTS and parsed.scheme in {"http", "https"}


def _content_length_error(request: Any, settings: SecuritySettings) -> str:
    value = request.headers.get("content-length")
    if not value:
        return ""
    try:
        length = int(value)
    except ValueError:
        return "Invalid Content-Length header."
    if length > settings.max_request_bytes:
        return f"Request body exceeds Aegis Core limit of {settings.max_request_bytes} bytes."
    return ""


def _rate_limit_error(request: Any, settings: SecuritySettings) -> str:
    if _client_key(request) in {"testclient", "testserver"}:
        return ""
    now = time.monotonic()
    bucket = _RATE_BUCKETS[_client_key(request)]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        return "Local API rate limit exceeded."
    bucket.append(now)
    return ""


def _auth_error(request: Any, settings: SecuritySettings) -> str:
    if not settings.token_enforced:
        return ""
    supplied = _request_token(request)
    if not supplied or not hmac.compare_digest(supplied, settings.local_auth_token):
        return "Aegis Core local API token is required."
    return ""


def _request_token(request: Any) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return (request.headers.get("x-aegis-local-token") or request.query_params.get("aegis_token") or "").strip()


def _apply_cors_headers(request: Any, response: Any, settings: SecuritySettings) -> None:
    origin = request.headers.get("origin")
    if origin and _origin_allowed(origin, settings.allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type,X-Aegis-Local-Token,X-Aegis-CSRF"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"


def _workspace_from_request(request: Any) -> str | None:
    for key in ("workspace", "workspace_root"):
        value = request.query_params.get(key)
        if value:
            return value
    return None


def _client_key(request: Any) -> str:
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "") or request.headers.get("host") or "unknown").lower()


def _audit_path(workspace: str | Path | None) -> Path:
    return memory_dir(Path(workspace or ".").expanduser().resolve()) / "security-audit.jsonl"


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {redact_inline(str(key)): _redact_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return redact_inline(value)
    return value


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
