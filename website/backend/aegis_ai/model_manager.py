from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .model_registry import ModelRegistryManager
from .providers.base import is_local_endpoint
from .schemas import (
    ManagedModelInfo,
    ModelDeleteRequest,
    ModelDiskInfo,
    ModelManagerResponse,
    ModelOperationInfo,
    ModelPullLogSummary,
    ModelPullRequest,
)
from .settings import Settings


SAFE_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/+-]{1,160}$")
BYTES_PER_GB = 1024**3
MAX_MODEL_MANAGER_JSON_BYTES = 512_000


class ModelManager:
    def __init__(self, project_root: Path, settings: Settings, registry: ModelRegistryManager):
        self.project_root = project_root
        self.settings = settings
        self.registry = registry
        self.log_root = project_root / "logs" / "model-manager"
        self.operations_path = self.log_root / "operations.json"

    def snapshot(self, minimum_free_gb: float = 24.0) -> ModelManagerResponse:
        registry = self.registry.snapshot()
        installed = self._ollama_inventory_by_endpoint(registry.providers)
        disk = self._disk_info(minimum_free_gb=minimum_free_gb)
        operations = self._refresh_operations()
        models: list[ManagedModelInfo] = []
        seen: set[tuple[str, str, str]] = set()

        for provider in registry.providers:
            model_name = provider.model_name.strip()
            if not model_name:
                continue
            endpoint = provider.endpoint.strip().rstrip("/")
            key = (provider.api.strip().lower(), endpoint, model_name)
            if key in seen:
                continue
            seen.add(key)

            installed_record = installed.get(endpoint, {}).get(model_name)
            if installed_record is None and model_name.endswith(":latest"):
                installed_record = installed.get(endpoint, {}).get(model_name[: -len(":latest")])
            if installed_record is None and ":" not in model_name:
                installed_record = installed.get(endpoint, {}).get(f"{model_name}:latest")

            local = bool(provider.local)
            is_installed = installed_record is not None if local else bool(provider.configured)
            pullable = bool(local and provider.enabled and not is_installed and provider.api.strip().lower() == "ollama")
            models.append(
                ManagedModelInfo(
                    provider_id=provider.id,
                    label=provider.label,
                    api=provider.api,
                    endpoint=provider.endpoint,
                    name=model_name,
                    local=local,
                    enabled=provider.enabled,
                    installed=is_installed,
                    configured=provider.configured,
                    active=provider.id == registry.active_provider_id or model_name == registry.active_model,
                    pullable=pullable,
                    health=provider.health,
                    roles=provider.roles,
                    capabilities=provider.capabilities,
                    size_bytes=self._clean_int(installed_record.get("size")) if installed_record else None,
                    modified_at=str(installed_record.get("modified_at") or "") if installed_record else "",
                    estimated_pull_bytes=self._estimate_model_bytes(model_name) if local else None,
                    notes=provider.notes,
                )
            )

        models.sort(key=lambda item: (not item.active, not item.installed, not item.pullable, item.local, item.name.lower()))
        return ModelManagerResponse(
            ok=True,
            message=self._manager_message(disk, models),
            disk=disk,
            active_model=registry.active_model,
            active_provider_id=registry.active_provider_id,
            providers_total=len(registry.providers),
            local_total=sum(1 for item in models if item.local),
            installed_total=sum(1 for item in models if item.installed),
            pullable_total=sum(1 for item in models if item.pullable),
            cloud_total=sum(1 for item in models if not item.local),
            models=models,
            operations=operations[:20],
            pull_logs=self._pull_log_summaries(),
        )

    def pull_model(self, request: ModelPullRequest) -> ModelOperationInfo:
        model_name = self._validate_model_name(request.model_name)
        minimum_free_bytes = max(0, int(request.minimum_free_gb * BYTES_PER_GB))
        disk = self._disk_info(minimum_free_gb=request.minimum_free_gb)
        estimated_bytes = self._estimate_model_bytes(model_name)
        registry_models = self._local_registry_model_names()

        if model_name not in registry_models:
            raise ValueError("Model must exist in the local Ollama registry before it can be pulled.")
        if disk.free_bytes - (estimated_bytes or 0) < minimum_free_bytes:
            raise ValueError(
                "Not enough free disk space for this model with the configured safety reserve. "
                f"Free: {self._format_bytes(disk.free_bytes)}, estimated pull: {self._format_bytes(estimated_bytes or 0)}, "
                f"reserve: {self._format_bytes(minimum_free_bytes)}."
            )

        return self._start_ollama_operation(
            action="pull",
            model_name=model_name,
            args=["pull", model_name],
            message="Started Ollama model pull.",
            minimum_free_bytes=minimum_free_bytes,
            estimated_pull_bytes=estimated_bytes,
            free_bytes_before=disk.free_bytes,
        )

    def delete_model(self, request: ModelDeleteRequest) -> ModelOperationInfo:
        model_name = self._validate_model_name(request.model_name)
        confirm_model_name = request.confirm_model_name.strip()
        if confirm_model_name != model_name:
            raise ValueError("confirm_model_name must exactly match model_name.")
        if model_name == self.settings.aegis_model_name.strip():
            raise ValueError("The active model cannot be removed. Select another model first.")
        if model_name not in self._installed_local_model_names():
            raise ValueError("That model is not currently installed in local Ollama.")

        return self._start_ollama_operation(
            action="delete",
            model_name=model_name,
            args=["rm", model_name],
            message="Started Ollama model removal.",
            minimum_free_bytes=0,
            estimated_pull_bytes=None,
            free_bytes_before=self._disk_info().free_bytes,
        )

    def _disk_info(self, minimum_free_gb: float = 24.0) -> ModelDiskInfo:
        usage = shutil.disk_usage(self.project_root)
        model_store = self._model_store_path()
        model_store_bytes = self._directory_size(model_store)
        minimum_free_bytes = max(0, int(minimum_free_gb * BYTES_PER_GB))
        return ModelDiskInfo(
            drive_root=self.project_root.anchor,
            project_root=str(self.project_root),
            model_store_path=str(model_store),
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            model_store_bytes=model_store_bytes,
            free_percent=round((usage.free / usage.total) * 100.0, 2) if usage.total else 0.0,
            low_space=usage.free < minimum_free_bytes,
            minimum_free_bytes=minimum_free_bytes,
        )

    def _manager_message(self, disk: ModelDiskInfo, models: list[ManagedModelInfo]) -> str:
        installed = sum(1 for item in models if item.installed)
        pullable = sum(1 for item in models if item.pullable)
        if disk.low_space:
            return (
                f"Disk reserve is active. {self._format_bytes(disk.free_bytes)} free, "
                f"{self._format_bytes(disk.minimum_free_bytes)} reserved."
            )
        return f"{installed} local/cloud model targets are ready. {pullable} local Ollama models are available to pull."

    def _ollama_inventory_by_endpoint(self, providers: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
        endpoints = {
            provider.endpoint.strip().rstrip("/")
            for provider in providers
            if provider.api.strip().lower() == "ollama"
            and provider.endpoint.strip()
            and is_local_endpoint(provider.endpoint)
        }
        return {endpoint: self._ollama_tags(endpoint) for endpoint in endpoints}

    def _ollama_tags(self, endpoint: str) -> dict[str, dict[str, Any]]:
        url = f"{endpoint.rstrip('/')}/api/tags"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return {}

        records: dict[str, dict[str, Any]] = {}
        for item in payload.get("models", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            records[name] = item
            if name.endswith(":latest"):
                records.setdefault(name[: -len(":latest")], item)
            elif ":" not in name:
                records.setdefault(f"{name}:latest", item)
        return records

    def _local_registry_model_names(self) -> set[str]:
        names: set[str] = set()
        for provider in self.registry.snapshot().providers:
            if provider.local and provider.api.strip().lower() == "ollama" and provider.model_name.strip():
                names.add(provider.model_name.strip())
        return names

    def _installed_local_model_names(self) -> set[str]:
        names: set[str] = set()
        registry = self.registry.snapshot()
        installed = self._ollama_inventory_by_endpoint(registry.providers)
        for endpoint_inventory in installed.values():
            names.update(endpoint_inventory.keys())
        return names

    def _start_ollama_operation(
        self,
        *,
        action: str,
        model_name: str,
        args: list[str],
        message: str,
        minimum_free_bytes: int,
        estimated_pull_bytes: int | None,
        free_bytes_before: int | None,
    ) -> ModelOperationInfo:
        executable = self._ollama_executable()
        if not executable:
            raise ValueError("Ollama executable was not found on PATH or in the default install location.")

        self.log_root.mkdir(parents=True, exist_ok=True)
        operation_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        safe_name = self._safe_filename(model_name)
        stdout_path = self.log_root / f"{operation_id}-{safe_name}.out.log"
        stderr_path = self.log_root / f"{operation_id}-{safe_name}.err.log"
        stdout_file = stdout_path.open("ab")
        stderr_file = stderr_path.open("ab")

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(
                [executable, *args],
                cwd=str(self.project_root),
                stdout=stdout_file,
                stderr=stderr_file,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        finally:
            stdout_file.close()
            stderr_file.close()

        operation = ModelOperationInfo(
            id=operation_id,
            model_name=model_name,
            action=action,
            status="running",
            message=message,
            pid=process.pid,
            started_at=datetime.now(timezone.utc).isoformat(),
            stdout_log=str(stdout_path),
            stderr_log=str(stderr_path),
            minimum_free_bytes=minimum_free_bytes,
            estimated_pull_bytes=estimated_pull_bytes,
            free_bytes_before=free_bytes_before,
        )
        operations = [operation, *self._load_operations()]
        self._save_operations(operations[:80])
        return operation

    def _refresh_operations(self) -> list[ModelOperationInfo]:
        operations = self._load_operations()
        if not operations:
            return []

        installed = self._installed_local_model_names()
        changed = False
        refreshed: list[ModelOperationInfo] = []
        for operation in operations:
            if operation.status == "running" and operation.pid is not None and not self._pid_exists(operation.pid):
                operation.status = "completed" if operation.model_name in installed else "finished"
                operation.finished_at = datetime.now(timezone.utc).isoformat()
                operation.message = "Operation finished. Refresh inventory to confirm final model state."
                changed = True
            refreshed.append(operation)
        if changed:
            self._save_operations(refreshed)
        return refreshed

    def _load_operations(self) -> list[ModelOperationInfo]:
        if not self.operations_path.exists() or not self.operations_path.is_file():
            return []
        try:
            if self.operations_path.stat().st_size > MAX_MODEL_MANAGER_JSON_BYTES:
                return []
            payload = json.loads(self.operations_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        operations: list[ModelOperationInfo] = []
        for item in payload:
            if isinstance(item, dict):
                try:
                    operations.append(ModelOperationInfo.model_validate(item))
                except (TypeError, ValueError):
                    continue
        return operations

    def _save_operations(self, operations: list[ModelOperationInfo]) -> None:
        self.log_root.mkdir(parents=True, exist_ok=True)
        payload = [operation.model_dump() for operation in operations]
        tmp = self.operations_path.with_name(f".{self.operations_path.name}.tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            tmp.replace(self.operations_path)
        except OSError:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
            raise

    def _pull_log_summaries(self) -> list[ModelPullLogSummary]:
        summaries: list[ModelPullLogSummary] = []
        for path in (
            self.project_root / "logs" / "model-pulls" / "summary.json",
            self.project_root / "logs" / "model-pulls-mega" / "summary.json",
        ):
            if not path.exists() or not path.is_file():
                continue
            try:
                if path.stat().st_size > MAX_MODEL_MANAGER_JSON_BYTES:
                    continue
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            records = payload if isinstance(payload, list) else []
            statuses = [str(item.get("status") or "") for item in records if isinstance(item, dict)]
            latest_at = ""
            for item in records:
                if isinstance(item, dict):
                    latest_at = str(item.get("finished_at") or item.get("started_at") or latest_at)
            summaries.append(
                ModelPullLogSummary(
                    source=path.parent.name,
                    total=len(statuses),
                    pulled=sum(1 for status in statuses if status == "pulled"),
                    skipped=sum(1 for status in statuses if status.startswith("skipped")),
                    failed=sum(1 for status in statuses if status in {"failed", "error"} or status.startswith("failed")),
                    latest_at=latest_at,
                )
            )
        return summaries

    def _model_store_path(self) -> Path:
        configured = os.environ.get("OLLAMA_MODELS", "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return (Path.home() / ".ollama" / "models").resolve()

    def _directory_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        for child in path.rglob("*"):
            try:
                if child.is_file():
                    total += child.stat().st_size
            except OSError:
                continue
        return total

    def _estimate_model_bytes(self, model_name: str) -> int | None:
        lowered = model_name.lower()
        if any(term in lowered for term in ("embed", "minilm", "bge")):
            return int(2 * BYTES_PER_GB)
        patterns = [
            ("90b", 65),
            ("72b", 52),
            ("70b", 50),
            ("8x7b", 30),
            ("35b", 26),
            ("34b", 25),
            ("32b", 24),
            ("30b", 22),
            ("27b", 20),
            ("24b", 18),
            ("20b", 16),
            ("16b", 13),
            ("14b", 11),
            ("12b", 10),
            ("11b", 9),
            ("8b", 7),
            ("7b", 6),
            ("4b", 4),
            ("3b", 3),
            ("2b", 2),
            ("1.5b", 2),
            ("1b", 1),
        ]
        for suffix, gb in patterns:
            if suffix in lowered:
                return int(gb * BYTES_PER_GB)
        return int(8 * BYTES_PER_GB)

    def _ollama_executable(self) -> str:
        found = shutil.which("ollama")
        if found:
            return found
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = []
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe")
        candidates.append(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe")
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return ""

    def _validate_model_name(self, model_name: str) -> str:
        cleaned = model_name.strip()
        if not cleaned:
            raise ValueError("Model name is required.")
        if not SAFE_MODEL_NAME_RE.fullmatch(cleaned):
            raise ValueError("Model name contains unsupported characters.")
        return cleaned

    def _pid_exists(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _clean_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    def _safe_filename(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
        return cleaned.strip("._") or "model"

    def _format_bytes(self, value: int) -> str:
        if value >= BYTES_PER_GB:
            return f"{value / BYTES_PER_GB:.1f} GB"
        if value >= 1024**2:
            return f"{value / 1024**2:.1f} MB"
        return f"{value} B"
