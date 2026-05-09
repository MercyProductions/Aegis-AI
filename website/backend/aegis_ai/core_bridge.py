from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


DEFAULT_CORE_API_URL = "http://127.0.0.1:8788"
CORE_API_VERSION = "v1"
CORE_CONTRACT_VERSION_FIELD = "contract_version"


@dataclass(frozen=True)
class CoreBridgeResult:
    reachable: bool
    ok: bool
    status_code: int | None
    kind: str
    data: dict[str, Any] | list[Any] | None
    envelope: dict[str, Any] | None = None
    error: str = ""


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

    path = parsed.path.rstrip("/")
    if "/v1" in path:
        path = path[: path.index("/v1")]

    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


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
    ) -> None:
        self.base_url = normalize_core_base_url(base_url)
        self.timeout_seconds = max(0.1, timeout_seconds)
        self.transport = transport

    @classmethod
    def from_settings(cls, settings: Any) -> "AegisCoreBridge":
        return cls(getattr(settings, "aegis_core_api_url", DEFAULT_CORE_API_URL))

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> CoreBridgeResult:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, payload: dict[str, Any]) -> CoreBridgeResult:
        return await self._request("POST", path, json=payload)

    async def shared_runtime_status(self, workspace: str | Path) -> dict[str, Any]:
        workspace_text = str(Path(workspace).resolve())
        params = {"workspace": workspace_text}
        results = {
            "health": await self.get("/v1/health", params=params),
            "models": await self.get("/v1/models", params=params),
            "settings": await self.get("/v1/settings", params=params),
            "memory": await self.get("/v1/memory", params=params),
            "diagnostics": await self.get("/v1/diagnostics", params=params),
            "dashboard": await self.get("/v1/ecosystem/dashboard", params=params),
        }
        errors = [f"{name}: {result.error}" for name, result in results.items() if result.error]
        reachable = any(result.reachable for result in results.values())
        ok = bool(results["health"].ok)
        contract_versions = {
            name: str(result.envelope.get(CORE_CONTRACT_VERSION_FIELD))
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
            "health": results["health"].envelope,
            "models": results["models"].envelope,
            "settings": results["settings"].envelope,
            "memory": results["memory"].envelope,
            "diagnostics": results["diagnostics"].envelope,
            "dashboard": results["dashboard"].envelope,
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
    ) -> CoreBridgeResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = await client.request(method, self._url(path), params=params, json=json)
            status_code = response.status_code
            response.raise_for_status()
            envelope = response.json()
            if not isinstance(envelope, dict):
                return CoreBridgeResult(
                    reachable=True,
                    ok=False,
                    status_code=status_code,
                    kind="",
                    data=None,
                    error="Core response was not a JSON object.",
                )
            return CoreBridgeResult(
                reachable=True,
                ok=bool(envelope.get("ok")),
                status_code=status_code,
                kind=str(envelope.get("kind") or ""),
                data=envelope.get("data"),
                envelope=envelope,
            )
        except (httpx.HTTPError, ValueError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) and exc.response else None
            return CoreBridgeResult(
                reachable=status_code is not None,
                ok=False,
                status_code=status_code,
                kind="",
                data=None,
                error=str(exc),
            )


def core_envelope_data(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {}
    data = envelope.get("data")
    return data if isinstance(data, dict) else {}


def core_task_to_website_task_summary(task: dict[str, Any] | None) -> dict[str, Any]:
    source = task if isinstance(task, dict) else {}
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    return {
        "id": str(source.get("id") or ""),
        "title": str(source.get("title") or "Untitled task"),
        "status": str(source.get("status") or "planned"),
        "kind": str(source.get("kind") or "general"),
        "source_client": str(source.get("source_client") or "unknown"),
        "updated_at": str(source.get("updated_at") or source.get("created_at") or ""),
        "summary": str(metadata.get("summary") or ""),
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
                "name": str(command.get("name") or ""),
                "command": " ".join(str(part) for part in raw) if isinstance(raw, list) else str(raw or ""),
                "reason": str(command.get("reason") or ""),
            }
        )

    raw_run_command = source.get("command")
    return {
        "ok": bool(source.get("ok", True)),
        "commands": normalized_commands,
        "command": " ".join(str(part) for part in raw_run_command) if isinstance(raw_run_command, list) else str(raw_run_command or ""),
        "returncode": source.get("returncode"),
        "stdout": str(source.get("stdout") or ""),
        "stderr": str(source.get("stderr") or ""),
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
    return {
        "workspace": str(data.get("workspace") or ""),
        "client_count": len([item for item in clients if isinstance(item, dict)]),
        "active_tasks": [core_task_to_website_task_summary(item) for item in active_tasks if isinstance(item, dict)],
        "recent_tasks": [core_task_to_website_task_summary(item) for item in recent_tasks if isinstance(item, dict)],
        "model_status": model_status,
        "validation": core_validation_to_website_validation(validation),
        "contract_version": str(envelope.get(CORE_CONTRACT_VERSION_FIELD) or "") if isinstance(envelope, dict) else "",
    }
