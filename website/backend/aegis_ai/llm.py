# backend/llm.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

from .providers import (
    ProviderError,
    ProviderInventory,
    ProviderModelRecord,
    ProviderStatus,
    ProviderStreamEvent,
    build_provider_adapter,
)
from .settings import Settings


class LocalModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalModelStatus:
    ready: bool
    message: str


@dataclass(frozen=True)
class LocalModelRecord:
    id: str
    name: str
    provider: str
    api: str
    endpoint: str
    local: bool
    configured: bool
    available: bool
    ready: bool
    message: str
    size: int | None = None
    modified_at: str = ""
    capabilities: dict[str, bool] | None = None


@dataclass(frozen=True)
class LocalModelInventory:
    active_model: str
    active_api: str
    active_endpoint: str
    message: str
    models: list[LocalModelRecord]


class LocalModelClient:
    """Compatibility facade for the agent while provider adapters evolve behind it."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.endpoint = settings.aegis_model_endpoint.rstrip("/")
        self.model = settings.aegis_model_name.strip()
        self.api = settings.aegis_model_api.strip().lower()
        self.adapter = build_provider_adapter(settings)

    @property
    def label(self) -> str:
        return self.adapter.label

    async def status(self) -> LocalModelStatus:
        return self._status(await self.adapter.status())

    async def inventory(self) -> LocalModelInventory:
        return self._inventory(await self.adapter.inventory())

    async def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            return await self.adapter.complete_json(messages)
        except ProviderError as exc:
            raise LocalModelError(str(exc)) from exc

    def stream_text(
        self,
        messages: list[dict[str, str]],
        *,
        structured_json: bool = False,
    ) -> AsyncIterator[ProviderStreamEvent]:
        return self.adapter.stream_text(messages, structured_json=structured_json)

    def _status(self, status: ProviderStatus) -> LocalModelStatus:
        return LocalModelStatus(ready=status.ready, message=status.message)

    def _inventory(self, inventory: ProviderInventory) -> LocalModelInventory:
        return LocalModelInventory(
            active_model=inventory.active_model,
            active_api=inventory.active_api,
            active_endpoint=inventory.active_endpoint,
            message=inventory.message,
            models=[self._record(record) for record in inventory.models],
        )

    def _record(self, record: ProviderModelRecord) -> LocalModelRecord:
        return LocalModelRecord(
            id=record.id,
            name=record.name,
            provider=record.provider,
            api=record.api,
            endpoint=record.endpoint,
            local=record.local,
            configured=record.configured,
            available=record.available,
            ready=record.ready,
            message=record.message,
            size=record.size,
            modified_at=record.modified_at,
            capabilities=record.capabilities,
        )
