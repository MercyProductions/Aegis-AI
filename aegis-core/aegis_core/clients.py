from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory import ProjectMemory, utc_now


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
    registration = ClientRegistration(
        client_id=client_id,
        client_type=client_type,
        name=name,
        version=version,
        capabilities=capabilities or [],
        last_seen=utc_now(),
    )
    clients[client_id] = registration.to_dict()
    _write_clients(memory, clients)
    return clients[client_id]


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
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}
    if isinstance(data, list):
        return {
            str(item.get("client_id")): item
            for item in data
            if isinstance(item, dict) and item.get("client_id")
        }
    return {}


def _write_clients(memory: ProjectMemory, clients: dict[str, dict[str, Any]]) -> None:
    memory.write_json("clients.json", clients)
