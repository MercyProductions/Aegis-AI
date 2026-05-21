from __future__ import annotations

import hmac
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque
from urllib.parse import urlparse

from .settings import PROJECT_ROOT, Settings
from .storage import utc_now


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver", "testclient"}
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5175",
    "http://127.0.0.1:5176",
    "http://localhost:5176",
    "http://127.0.0.1:5177",
    "http://localhost:5177",
    "http://127.0.0.1:5193",
    "http://localhost:5193",
    "http://127.0.0.1:5194",
    "http://localhost:5194",
)
_RATE_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)


def install_security_middleware(app: Any, settings: Settings) -> None:
    try:
        from fastapi import Request
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install Website backend dependencies first.") from exc

    @app.middleware("http")
    async def website_security_middleware(request: Request, call_next: Any) -> Any:
        origin_error = _origin_error(request, settings)
        if origin_error:
            audit_event("website.origin_rejected", "blocked", origin_error, {"origin": _redact(request.headers.get("origin", ""))})
            return JSONResponse({"detail": origin_error}, status_code=403)

        length_error = _content_length_error(request, settings)
        if length_error:
            audit_event("website.request_too_large", "blocked", length_error, {"content_length": request.headers.get("content-length", "")})
            return JSONResponse({"detail": length_error}, status_code=413)

        rate_error = _rate_limit_error(request, settings)
        if rate_error:
            audit_event("website.rate_limited", "blocked", rate_error, {"client": _client_key(request)})
            return JSONResponse({"detail": rate_error}, status_code=429)

        auth_error = _local_api_auth_error(request, settings)
        if auth_error:
            audit_event("website.local_api_unauthorized", "blocked", auth_error, {"path": request.url.path})
            return JSONResponse({"detail": auth_error}, status_code=401)

        return await call_next(request)


def trust_status(settings: Settings, *, core_status: dict[str, Any] | None = None) -> dict[str, Any]:
    privacy_mode = _privacy_mode(settings)
    token_configured = bool(settings.aegis_local_api_token.strip())
    return {
        "generated_at": utc_now(),
        "website": {
            "localhost_origin_guard": True,
            "allowed_origins": _allowed_origins(settings),
            "local_api_token_required": bool(settings.aegis_require_local_api_token),
            "local_api_token_configured": token_configured,
            "csrf_strategy": "Browser requests are origin-checked; bearer token enforcement is available through AEGIS_LOCAL_API_TOKEN.",
            "max_request_bytes": int(settings.aegis_max_request_bytes),
            "rate_limit_per_minute": int(settings.aegis_rate_limit_per_minute),
            "audit_path": str(_audit_path()),
        },
        "privacy": {
            "mode": privacy_mode,
            "local_only": privacy_mode in {"local_only", "local-only", "cloud_disabled", "cloud-disabled"},
            "cloud_disabled": bool(settings.aegis_cloud_disabled) or privacy_mode in {"cloud_disabled", "cloud-disabled"},
            "prompt_redaction": bool(settings.aegis_feedback_redaction_enabled),
            "provider_usage_warnings": True,
        },
        "credentials": {
            "provider_key_storage": "Core OS credential store preferred; Website account links store references/status, not plaintext keys.",
            "responses_mask_keys": True,
            "logs_redacted": True,
        },
        "workspace": {
            "allowed_roots_enforced": True,
            "explicit_workspace_paths_allowed": bool(settings.aegis_allow_explicit_workspace_paths),
            "path_traversal_rejected": True,
            "secret_like_paths_blocked": True,
            "checkpoint_before_apply": True,
        },
        "core": core_status or {},
    }


def audit_event(event: str, status: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
    record = {
        "timestamp": utc_now(),
        "event": _redact(event),
        "status": _redact(status),
        "detail": _redact(detail),
        "metadata": _redact_json(metadata or {}),
    }
    try:
        path = _audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        return


def _origin_error(request: Any, settings: Settings) -> str:
    origin = request.headers.get("origin")
    if not origin:
        return ""
    if _origin_allowed(origin, _allowed_origins(settings)):
        return ""
    return "Aegis Website backend rejected an untrusted browser origin."


def _origin_allowed(origin: str, allowed: list[str]) -> bool:
    normalized = origin.rstrip("/")
    if normalized in allowed:
        return True
    parsed = urlparse(normalized)
    return parsed.hostname in LOOPBACK_HOSTS and parsed.scheme in {"http", "https"}


def _content_length_error(request: Any, settings: Settings) -> str:
    value = request.headers.get("content-length")
    if not value:
        return ""
    try:
        length = int(value)
    except ValueError:
        return "Invalid Content-Length header."
    if length > int(settings.aegis_max_request_bytes):
        return f"Request body exceeds Website backend limit of {settings.aegis_max_request_bytes} bytes."
    return ""


def _rate_limit_error(request: Any, settings: Settings) -> str:
    key = _client_key(request)
    if key in {"testclient", "testserver"}:
        return ""
    now = time.monotonic()
    bucket = _RATE_BUCKETS[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= int(settings.aegis_rate_limit_per_minute):
        return "Website backend local API rate limit exceeded."
    bucket.append(now)
    return ""


def _local_api_auth_error(request: Any, settings: Settings) -> str:
    if not bool(settings.aegis_require_local_api_token):
        return ""
    token = settings.aegis_local_api_token.strip()
    if not token:
        return "Website local API token is required but AEGIS_LOCAL_API_TOKEN is not configured."
    supplied = _request_token(request)
    if not supplied or not hmac.compare_digest(supplied, token):
        return "Website local API token is required."
    return ""


def _request_token(request: Any) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return (request.headers.get("x-aegis-local-token") or request.query_params.get("aegis_token") or "").strip()


def _client_key(request: Any) -> str:
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "") or request.headers.get("host") or "unknown").lower()


def _allowed_origins(settings: Settings) -> list[str]:
    configured = [item.strip().rstrip("/") for item in settings.aegis_allowed_origins.split(",") if item.strip()]
    return configured or list(DEFAULT_ALLOWED_ORIGINS)


def _privacy_mode(settings: Settings) -> str:
    return settings.aegis_privacy_mode.strip().lower().replace("-", "_") or "local_first"


def _audit_path() -> Path:
    return PROJECT_ROOT / ".aegis" / "security-audit.jsonl"


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {_redact(str(key)): _redact_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _redact(value: str) -> str:
    text = str(value)
    lowered = text.lower()
    if any(marker in lowered for marker in ("api_key", "authorization", "bearer ", "password", "secret", "token")):
        return "[redacted secret-like value]"
    return text
