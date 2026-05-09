from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory import ProjectMemory, utc_now


class ClientRegistryPersistenceError(RuntimeError):
    """Raised when a shared client registration cannot be persisted."""


@dataclass
class ClientRegistration:
    client_id: str
    client_type: str
    name: str
    version: str
    capabilities: list[str]
    last_seen: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_type": self.client_type,
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
        }


def register_client(
    workspace: str | Path,
    client_id: str,
    client_type: str,
    name: str,
    version: str,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    memory = ProjectMemory(workspace)
    memory.ensure()
    clients = _load_clients(memory)
    client_id = str(client_id or "").strip() or "unknown-client"
    registration = ClientRegistration(
        client_id=client_id,
        client_type=str(client_type or "unknown").strip() or "unknown",
        name=str(name or client_id or "Unknown Client").strip() or "Unknown Client",
        version=str(version or "unknown").strip() or "unknown",
        capabilities=_clean_capabilities(capabilities),
        last_seen=utc_now(),
    )
    clients[client_id] = registration.to_dict()
    _write_clients(memory, clients)
    persisted = _load_clients(memory).get(client_id)
    if persisted != clients[client_id]:
        raise ClientRegistryPersistenceError(
            f"Could not persist client registration at {memory.root / 'clients.json'}. "
            "Check that the workspace .aegis path is a writable directory."
        )
    return persisted


def list_clients(workspace: str | Path) -> list[dict[str, Any]]:
    memory = ProjectMemory(workspace)
    memory.ensure()
    clients = _load_clients(memory)
    return sorted(clients.values(), key=lambda item: item.get("last_seen", ""), reverse=True)


def _load_clients(memory: ProjectMemory) -> dict[str, dict[str, Any]]:
    path = memory.root / "clients.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    clients: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        for key, item in data.items():
            client = _normalize_client(item, fallback_client_id=str(key))
            if client is not None:
                clients[client["client_id"]] = client
        return clients
    if not isinstance(data, list):
        return {}

    for item in data:
        client = _normalize_client(item)
        if client is not None:
            clients[client["client_id"]] = client
    return clients


def _normalize_client(item: Any, fallback_client_id: str = "") -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    client_id = str(item.get("client_id") or fallback_client_id or "").strip()
    if not client_id:
        return None
    return {
        "client_id": client_id,
        "client_type": str(item.get("client_type") or "unknown").strip() or "unknown",
        "name": str(item.get("name") or client_id).strip() or client_id,
        "version": str(item.get("version") or "unknown").strip() or "unknown",
        "capabilities": _clean_capabilities(item.get("capabilities")),
        "last_seen": str(item.get("last_seen") or ""),
    }


def _clean_capabilities(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _write_clients(memory: ProjectMemory, clients: dict[str, dict[str, Any]]) -> None:
    memory.write_json("clients.json", clients)
