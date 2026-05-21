from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from .diagnostic_redaction import redact_inline


DEFAULT_CORE_API_URL = "http://127.0.0.1:8788"
CORE_API_VERSION = "v1"
CORE_CONTRACT_VERSION_FIELD = "contract_version"
LEGACY_CORE_ENDPOINTS = {"health", "models"}


@dataclass(frozen=True)
class CoreBridgeResult:
    reachable: bool
    ok: bool
    status_code: int | None
    kind: str
    data: dict[str, Any] | list[Any] | None
    envelope: dict[str, Any] | None = None
    error: str = ""


def _workspace_text(workspace: str | Path) -> str:
    return str(Path(workspace).resolve())


def normalize_core_base_url(value: str, default: str = DEFAULT_CORE_API_URL) -> str:
    raw = (value or "").strip()
    if not raw:
        raw = default
    if "://" not in raw:
        raw = "http://" + raw

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return default

    if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(char.isspace() for char in parsed.netloc):
        return default
    if parsed.username or parsed.password:
        return default

    path = _strip_core_endpoint_path(parsed.path)

    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


def _strip_core_endpoint_path(path: str) -> str:
    cleaned = (path or "").rstrip("/")
    if not cleaned or cleaned == "/":
        return ""
    segments = [segment for segment in cleaned.split("/") if segment]
    lowered = [segment.lower() for segment in segments]
    if CORE_API_VERSION in lowered:
        index = lowered.index(CORE_API_VERSION)
        return "/" + "/".join(segments[:index]) if index else ""
    if lowered[-1] in LEGACY_CORE_ENDPOINTS:
        return "/" + "/".join(segments[:-1]) if len(segments) > 1 else ""
    return cleaned


class AegisCoreBridge:
    """Optional Website-to-Core bridge for stable shared runtime reads.

    The bridge is intentionally thin. It lets the Website backend observe Core
    health, models, settings, memory, diagnostics, and dashboard contracts
    without moving rich Website /api workflows into Core.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_CORE_API_URL,
        *,
        timeout_seconds: float = 2.5,
        transport: httpx.AsyncBaseTransport | None = None,
        local_auth_token: str = "",
    ) -> None:
        self.base_url = normalize_core_base_url(base_url)
        self.timeout_seconds = max(0.1, timeout_seconds)
        self.transport = transport
        self.local_auth_token = str(local_auth_token or "").strip()

    @classmethod
    def from_settings(cls, settings: Any) -> "AegisCoreBridge":
        return cls(
            getattr(settings, "aegis_core_api_url", DEFAULT_CORE_API_URL),
            local_auth_token=getattr(settings, "aegis_core_local_token", "") or getattr(settings, "aegis_local_api_token", ""),
        )

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        expected_kind: str | None = None,
    ) -> CoreBridgeResult:
        return await self._request("GET", path, params=params, expected_kind=expected_kind)

    async def post(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        expected_kind: str | None = None,
    ) -> CoreBridgeResult:
        return await self._request("POST", path, json=payload, expected_kind=expected_kind)

    async def health_status(self, workspace: str | Path) -> CoreBridgeResult:
        return await self.get("/v1/health", params={"workspace": _workspace_text(workspace)}, expected_kind="health")

    async def model_status(self, workspace: str | Path) -> CoreBridgeResult:
        return await self.get("/v1/models", params={"workspace": _workspace_text(workspace)}, expected_kind="models")

    async def settings_status(self, workspace: str | Path) -> CoreBridgeResult:
        return await self.get("/v1/settings", params={"workspace": _workspace_text(workspace)}, expected_kind="settings")

    async def diagnostics_status(self, workspace: str | Path) -> CoreBridgeResult:
        return await self.get("/v1/diagnostics", params={"workspace": _workspace_text(workspace)}, expected_kind="diagnostics.summary")

    async def dashboard_status(self, workspace: str | Path) -> CoreBridgeResult:
        return await self.get(
            "/v1/ecosystem/dashboard",
            params={"workspace": _workspace_text(workspace)},
            expected_kind="ecosystem.dashboard",
        )

    async def update_settings(self, workspace: str | Path, settings: dict[str, Any]) -> CoreBridgeResult:
        return await self.post(
            "/v1/settings",
            payload={"workspace": _workspace_text(workspace), "settings": settings},
            expected_kind="settings.updated",
        )

    async def low_risk_runtime_status(self, workspace: str | Path) -> dict[str, CoreBridgeResult]:
        names = ("health", "models", "settings", "diagnostics")
        results = await asyncio.gather(
            self.health_status(workspace),
            self.model_status(workspace),
            self.settings_status(workspace),
            self.diagnostics_status(workspace),
        )
        return dict(zip(names, results, strict=True))

    async def shared_runtime_status(self, workspace: str | Path) -> dict[str, Any]:
        workspace_text = _workspace_text(workspace)
        params = {"workspace": workspace_text}
        health, models, settings, memory, diagnostics, dashboard = await asyncio.gather(
            self.health_status(workspace),
            self.model_status(workspace),
            self.settings_status(workspace),
            self.get("/v1/memory", params=params, expected_kind="memory.summary"),
            self.diagnostics_status(workspace),
            self.dashboard_status(workspace),
        )
        results = {
            "health": health,
            "models": models,
            "settings": settings,
            "memory": memory,
            "diagnostics": diagnostics,
            "dashboard": dashboard,
        }
        errors = [f"{name}: {result.error}" for name, result in results.items() if result.error]
        reachable = any(result.reachable for result in results.values())
        ok = bool(results["health"].ok)
        contract_versions = {
            name: _redact_core_text(result.envelope.get(CORE_CONTRACT_VERSION_FIELD))
            for name, result in results.items()
            if isinstance(result.envelope, dict) and result.envelope.get(CORE_CONTRACT_VERSION_FIELD)
        }
        contract_version = next(iter(contract_versions.values()), "")

        return {
            "ok": ok,
            "reachable": reachable,
            "core_url": self.base_url,
            "api_version": CORE_API_VERSION,
            "contract_version": contract_version,
            "contract_versions": contract_versions,
            "workspace": workspace_text,
            "ownership": {
                "shared_runtime": "aegis-core",
                "application_runtime": "website-backend",
                "migration_phase": "unified-contract-client-compatibility-phase",
            },
            "health": _redact_core_envelope(results["health"].envelope),
            "models": _redact_core_envelope(results["models"].envelope),
            "settings": _redact_core_envelope(results["settings"].envelope),
            "memory": _redact_core_envelope(results["memory"].envelope),
            "diagnostics": _redact_core_envelope(results["diagnostics"].envelope),
            "dashboard": _redact_core_envelope(results["dashboard"].envelope),
            "errors": errors,
        }

    def _url(self, path: str) -> str:
        suffix = "/" + path.lstrip("/")
        return self.base_url.rstrip("/") + suffix

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        expected_kind: str | None = None,
    ) -> CoreBridgeResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.request(method, self._url(path), params=params, json=json, headers=self._headers())
            status_code = response.status_code
            response.raise_for_status()
            try:
                envelope = response.json()
            except ValueError as exc:
                return CoreBridgeResult(
                    reachable=True,
                    ok=False,
                    status_code=status_code,
                    kind="",
                    data=None,
                    error=f"Core response was not valid JSON: {exc}",
                )
            if not isinstance(envelope, dict):
                return CoreBridgeResult(
                    reachable=True,
                    ok=False,
                    status_code=status_code,
                    kind="",
                    data=None,
                    error="Core response was not a JSON object.",
                )
            contract_error = _core_envelope_contract_error(envelope, expected_kind)
            redacted_envelope = _redact_core_envelope(envelope)
            redacted_data = _redact_core_result_data(envelope.get("data"))
            if contract_error:
                return CoreBridgeResult(
                    reachable=True,
                    ok=False,
                    status_code=status_code,
                    kind=_redact_core_text(envelope.get("kind") or ""),
                    data=redacted_data,
                    envelope=redacted_envelope,
                    error=contract_error,
                )
            ok = bool(envelope.get("ok"))
            return CoreBridgeResult(
                reachable=True,
                ok=ok,
                status_code=status_code,
                kind=_redact_core_text(envelope.get("kind") or ""),
                data=redacted_data,
                envelope=redacted_envelope,
                error="" if ok else core_envelope_error(envelope),
            )
        except (httpx.HTTPError, ValueError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) and exc.response else None
            return CoreBridgeResult(
                reachable=status_code is not None,
                ok=False,
                status_code=status_code,
                kind="",
                data=None,
                error=_redact_core_error_text(str(exc)),
            )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.local_auth_token:
            headers["Authorization"] = f"Bearer {self.local_auth_token}"
            headers["X-Aegis-Local-Token"] = self.local_auth_token
        return headers


def _core_envelope_contract_error(envelope: dict[str, Any], expected_kind: str | None) -> str:
    api_version = str(envelope.get("api_version") or "")
    if api_version != CORE_API_VERSION:
        safe_api_version = _redact_core_error_text(api_version) or "missing"
        return f"Core response used unexpected api_version: {safe_api_version}."
    if expected_kind:
        kind = str(envelope.get("kind") or "")
        if kind != expected_kind:
            safe_kind = _redact_core_error_text(kind) or "missing"
            return f"Core response kind mismatch: expected {expected_kind}, got {safe_kind}."
    return ""


def core_envelope_error(envelope: dict[str, Any] | None) -> str:
    if not isinstance(envelope, dict):
        return "Core response was unavailable."
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    detail = data.get("error") or data.get("message") or envelope.get("detail")
    if detail:
        return _redact_core_error_text(str(detail))
    deprecations = envelope.get("deprecations")
    if isinstance(deprecations, list) and deprecations:
        return _redact_core_error_text("; ".join(str(item) for item in deprecations if str(item).strip()))
    return "Core returned ok=false."


def _redact_core_error_text(text: str) -> str:
    return _redact_core_text(text)


def _redact_core_text(text: object) -> str:
    return redact_inline(str(text))


def _redact_core_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_core_text(value)
    if isinstance(value, list):
        return [_redact_core_value(item) for item in value]
    if isinstance(value, dict):
        return {
            _redact_core_text(key) if isinstance(key, str) else key: _redact_core_value(item)
            for key, item in value.items()
        }
    return value


def _redact_core_envelope(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    redacted = _redact_core_value(envelope) if isinstance(envelope, dict) else None
    return redacted if isinstance(redacted, dict) else None


def _redact_core_result_data(data: Any) -> dict[str, Any] | list[Any] | None:
    redacted = _redact_core_value(data)
    return redacted if isinstance(redacted, (dict, list)) else None


def core_envelope_data(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {}
    data = envelope.get("data")
    return data if isinstance(data, dict) else {}


def core_task_to_website_task_summary(task: dict[str, Any] | None) -> dict[str, Any]:
    source = task if isinstance(task, dict) else {}
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    return {
        "id": _redact_core_text(source.get("id") or ""),
        "title": _redact_core_text(source.get("title") or "Untitled task"),
        "status": _redact_core_text(source.get("status") or "planned"),
        "kind": _redact_core_text(source.get("kind") or "general"),
        "source_client": _redact_core_text(source.get("source_client") or "unknown"),
        "updated_at": _redact_core_text(source.get("updated_at") or source.get("created_at") or ""),
        "summary": _redact_core_text(metadata.get("summary") or ""),
    }


def core_validation_to_website_validation(validation: dict[str, Any] | None) -> dict[str, Any]:
    source = validation if isinstance(validation, dict) else {}
    commands = source.get("commands") if isinstance(source.get("commands"), list) else []
    normalized_commands = []
    for command in commands:
        if not isinstance(command, dict):
            continue
        raw = command.get("command")
        normalized_commands.append(
            {
                "name": _redact_core_text(command.get("name") or ""),
                "command": _redact_core_text(
                    " ".join(str(part) for part in raw) if isinstance(raw, list) else str(raw or "")
                ),
                "reason": _redact_core_text(command.get("reason") or ""),
            }
        )

    raw_run_command = source.get("command")
    return {
        "ok": bool(source.get("ok", True)),
        "commands": normalized_commands,
        "command": _redact_core_text(
            " ".join(str(part) for part in raw_run_command) if isinstance(raw_run_command, list) else str(raw_run_command or "")
        ),
        "returncode": source.get("returncode"),
        "stdout": _redact_core_text(source.get("stdout") or ""),
        "stderr": _redact_core_text(source.get("stderr") or ""),
        "blocked": bool(source.get("blocked", False)),
        "timed_out": bool(source.get("timed_out", False)),
        "start_failed": bool(source.get("start_failed", False)),
    }


def core_dashboard_to_website_runtime_status(envelope: dict[str, Any] | None) -> dict[str, Any]:
    data = core_envelope_data(envelope)
    clients = data.get("clients") if isinstance(data.get("clients"), list) else []
    active_tasks = data.get("active_tasks") if isinstance(data.get("active_tasks"), list) else []
    recent_tasks = data.get("recent_tasks") if isinstance(data.get("recent_tasks"), list) else []
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    model_status = data.get("model_status") if isinstance(data.get("model_status"), dict) else {}
    redacted_model_status = _redact_core_value(model_status)
    return {
        "workspace": str(data.get("workspace") or ""),
        "client_count": len([item for item in clients if isinstance(item, dict)]),
        "active_tasks": [core_task_to_website_task_summary(item) for item in active_tasks if isinstance(item, dict)],
        "recent_tasks": [core_task_to_website_task_summary(item) for item in recent_tasks if isinstance(item, dict)],
        "model_status": redacted_model_status if isinstance(redacted_model_status, dict) else {},
        "validation": core_validation_to_website_validation(validation),
        "contract_version": str(envelope.get(CORE_CONTRACT_VERSION_FIELD) or "") if isinstance(envelope, dict) else "",
    }
