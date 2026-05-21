from __future__ import annotations

import os
import re
import shutil
import subprocess
import glob
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ProviderAccountManifest, ProviderCliBridgeInfo, ProviderCliBridgeManifest


SECRET_OUTPUT_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|bearer\s+)[^\s]+"
)


@dataclass(frozen=True)
class BridgeProbeTarget:
    command: list[str]
    display: str
    source: str
    cwd: str = ""
    env: dict[str, str] | None = None
    version_args: list[str] | None = None
    status_args: list[str] | None = None
    login_args: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CliBridgeAdapter:
    """Safe official-CLI detector.

    This adapter never reads token files or browser state. It only finds a CLI
    binary on PATH and runs short, explicit, read-only commands from the Aegis
    manifest. Work delegation can build on the same allowlisted command model.
    """

    def __init__(self, timeout_seconds: int = 4, project_root: Path | None = None):
        self.timeout_seconds = max(1, min(timeout_seconds, 15))
        self.project_root = Path(project_root).resolve() if project_root else None

    def probe(self, manifest: ProviderAccountManifest) -> ProviderCliBridgeInfo | None:
        bridge = manifest.cli_bridge
        if bridge is None:
            return None

        targets = list(self._candidate_targets(manifest, bridge))
        now = utc_now()
        if not targets:
            return ProviderCliBridgeInfo(
                provider_id=manifest.id,
                cli_name=bridge.cli_name or manifest.label,
                status="not_configured",
                auth_status="unknown",
                supported_delegation_modes=bridge.delegation_modes,
                last_probe_at=now,
                last_error="CLI binary or source-drop command was not found.",
                metadata={
                    "candidate_binaries": bridge.candidate_binaries,
                    "source_candidates": self._source_candidate_summary(manifest),
                },
            )

        target = targets[0]
        version = ""
        version_error = ""
        for candidate in targets:
            candidate_version_args = candidate.version_args if candidate.version_args is not None else bridge.version_args
            candidate_version, candidate_error = self._run_probe(candidate, candidate_version_args)
            target = candidate
            version = candidate_version
            version_error = candidate_error
            if not candidate_error:
                break

        version_args = target.version_args if target.version_args is not None else bridge.version_args
        status_args = target.status_args if target.status_args is not None else bridge.status_args
        login_args = target.login_args if target.login_args is not None else bridge.login_args
        auth_status = "unknown"
        status = "unknown" if not version_error else "error"
        last_error = version_error
        probe_command = self._format_command(target, version_args)

        if status_args:
            status_output, status_error = self._run_probe(target, status_args)
            probe_command = self._format_command(target, status_args)
            auth_status = self._classify_auth_status(status_output, status_error)
            if auth_status in {"linked", "not_configured"}:
                status = auth_status
            elif auth_status == "error":
                status = "error"
            elif not version_error:
                status = "linked"
            last_error = status_error

        return ProviderCliBridgeInfo(
            provider_id=manifest.id,
            cli_name=bridge.cli_name or manifest.label,
            binary_path=target.display,
            version=self._first_line(version),
            status=status,
            auth_status=auth_status,
            probe_command=probe_command,
            supported_delegation_modes=bridge.delegation_modes,
            last_probe_at=now,
            last_error=last_error,
            metadata={
                "candidate_binaries": bridge.candidate_binaries,
                "version_probe_error": version_error,
                "delegation_policy": "delegate_only_no_token_import",
                "login_command": self._format_command(target, login_args) if login_args else "",
                "detected_from": target.source,
                "cwd": target.cwd,
                **(target.metadata or {}),
            },
        )

    def _candidate_targets(
        self, manifest: ProviderAccountManifest, bridge: ProviderCliBridgeManifest
    ) -> list[BridgeProbeTarget]:
        metadata = manifest.metadata if isinstance(manifest.metadata, dict) else {}
        source_bridge = metadata.get("source_bridge") if isinstance(metadata.get("source_bridge"), dict) else {}
        prefer_source = bool(source_bridge.get("prefer_source"))

        path_targets = self._path_targets(bridge)
        source_targets = self._source_targets(manifest)
        targets = [*source_targets, *path_targets] if prefer_source else [*path_targets, *source_targets]

        seen: set[tuple[str, str]] = set()
        unique: list[BridgeProbeTarget] = []
        for target in targets:
            key = (target.cwd, "\0".join(target.command))
            if key in seen:
                continue
            seen.add(key)
            unique.append(target)
        return unique

    def targets_for(self, manifest: ProviderAccountManifest) -> list[BridgeProbeTarget]:
        bridge = manifest.cli_bridge
        if bridge is None:
            return []
        return self._candidate_targets(manifest, bridge)

    def source_roots_for(self, manifest: ProviderAccountManifest) -> list[Path]:
        metadata = manifest.metadata if isinstance(manifest.metadata, dict) else {}
        source_bridge = metadata.get("source_bridge") if isinstance(metadata.get("source_bridge"), dict) else {}
        if not source_bridge:
            return []
        return self._source_roots(source_bridge)

    def source_candidate_summary(self, manifest: ProviderAccountManifest) -> dict[str, Any]:
        return self._source_candidate_summary(manifest)

    def _path_targets(self, bridge: ProviderCliBridgeManifest) -> list[BridgeProbeTarget]:
        targets: list[BridgeProbeTarget] = []
        for binary in bridge.candidate_binaries:
            found = shutil.which(binary)
            if found:
                targets.append(
                    BridgeProbeTarget(
                        command=[found],
                        display=found,
                        source="path",
                        metadata={"binary_candidate": binary},
                    )
                )
        return targets

    def _source_targets(self, manifest: ProviderAccountManifest) -> list[BridgeProbeTarget]:
        metadata = manifest.metadata if isinstance(manifest.metadata, dict) else {}
        source_bridge = metadata.get("source_bridge") if isinstance(metadata.get("source_bridge"), dict) else {}
        if not source_bridge:
            return []

        roots = self._source_roots(source_bridge)
        targets: list[BridgeProbeTarget] = []

        for candidate in self._string_list(source_bridge.get("binary_candidates")):
            path = self._resolve_existing_path(candidate, roots, expect_dir=False)
            if path is None:
                continue
            targets.append(
                BridgeProbeTarget(
                    command=[str(path)],
                    display=str(path),
                    source="source_drop",
                    metadata={"source_candidate": candidate, "source_root": self._source_root_label(path, roots)},
                )
            )

        for candidate in self._string_list(source_bridge.get("binary_glob_candidates")):
            for path in self._glob_existing_files(candidate, roots):
                targets.append(
                    BridgeProbeTarget(
                        command=[str(path)],
                        display=str(path),
                        source="package_glob",
                        metadata={"source_candidate": candidate, "source_root": self._source_root_label(path, roots)},
                    )
                )

        for payload in source_bridge.get("command_candidates") if isinstance(source_bridge.get("command_candidates"), list) else []:
            if not isinstance(payload, dict):
                continue
            cwd = self._resolve_existing_path(str(payload.get("cwd") or "."), roots, expect_dir=True)
            command = self._string_list(payload.get("command"))
            if cwd is None or not command:
                continue
            command = [shutil.which(command[0]) or command[0], *command[1:]]
            env_payload = payload.get("env") if isinstance(payload.get("env"), dict) else {}
            env = {str(key): str(value) for key, value in env_payload.items()}
            targets.append(
                BridgeProbeTarget(
                    command=command,
                    display=str(payload.get("label") or self._format_command_parts(command)),
                    source="source_drop",
                    cwd=str(cwd),
                    env=env,
                    version_args=self._optional_string_list(payload.get("version_args")),
                    status_args=self._optional_string_list(payload.get("status_args")),
                    login_args=self._optional_string_list(payload.get("login_args")),
                    metadata={
                        "source_candidate": str(payload.get("cwd") or "."),
                        "source_root": self._source_root_label(cwd, roots),
                    },
                )
            )

        return targets

    def _run_probe(self, target: BridgeProbeTarget, args: list[str]) -> tuple[str, str]:
        if not args:
            return "", ""
        command = [*target.command, *args]
        env = os.environ.copy()
        if target.env:
            env.update(target.env)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=target.cwd or None,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
        except FileNotFoundError:
            return "", "CLI command disappeared before probe could run."
        except PermissionError:
            return "", "CLI command could not be executed because permission was denied."
        except subprocess.TimeoutExpired:
            return "", f"CLI probe timed out after {self.timeout_seconds} seconds."
        except Exception as exc:
            return "", f"CLI probe failed: {self._redact(str(exc))}"

        output = self._redact("\n".join(part for part in (completed.stdout, completed.stderr) if part))
        if completed.returncode == 0:
            return output, ""
        return output, self._redact(output or f"CLI probe exited with status {completed.returncode}.")

    def _classify_auth_status(self, output: str, error: str) -> str:
        text = f"{output}\n{error}".strip().lower()
        if error and any(
            marker in text
            for marker in ("not logged", "not authenticated", "login", "sign in", "sign-in", "auth method", "api_key")
        ):
            return "not_configured"
        if error:
            return "error"
        if any(marker in text for marker in ("logged in", "authenticated", "signed in", "using chatgpt")):
            return "linked"
        if any(marker in text for marker in ("not logged", "not authenticated", "login required", "sign in")):
            return "not_configured"
        return "unknown"

    def _format_command(self, target: BridgeProbeTarget, args: list[str]) -> str:
        command = self._format_command_parts([*target.command, *args])
        if target.cwd:
            return f"{command}  (cwd: {target.cwd})"
        return command

    def _format_command_parts(self, parts: list[str]) -> str:
        return " ".join(self._quote_command_part(part) for part in parts if part).strip()

    def _quote_command_part(self, value: str) -> str:
        text = str(value)
        if not text:
            return ""
        if any(char.isspace() for char in text) and not (text.startswith('"') and text.endswith('"')):
            return f'"{text}"'
        return text

    def _source_roots(self, source_bridge: dict[str, Any]) -> list[Path]:
        roots: list[Path] = []
        for env_name in ("AEGIS_AI_SOURCE_ROOT", "AEGIS_AI_ROOT"):
            value = os.environ.get(env_name, "").strip()
            if value:
                roots.append(Path(os.path.expandvars(value)).expanduser())

        for item in self._string_list(source_bridge.get("root_candidates")):
            roots.extend(self._resolve_root_candidate(item))

        if self.project_root is not None:
            roots.extend(
                [
                    self.project_root.parent.parent / "AI",
                    self.project_root.parent / "AI",
                    self.project_root / "AI",
                ]
            )

        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            try:
                resolved = root.resolve()
            except OSError:
                resolved = root.absolute()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(resolved)
        return unique

    def _resolve_root_candidate(self, value: str) -> list[Path]:
        expanded = Path(os.path.expandvars(value)).expanduser()
        if expanded.is_absolute() or self.project_root is None:
            return [expanded]
        return [
            self.project_root / expanded,
            self.project_root.parent / expanded,
            self.project_root.parent.parent / expanded,
        ]

    def _resolve_existing_path(self, value: str, roots: list[Path], *, expect_dir: bool) -> Path | None:
        expanded = Path(os.path.expandvars(value)).expanduser()
        candidates = [expanded] if expanded.is_absolute() else [root / expanded for root in roots]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate.absolute()
            if expect_dir and resolved.is_dir():
                return resolved
            if not expect_dir and resolved.is_file():
                return resolved
        return None

    def _glob_existing_files(self, value: str, roots: list[Path]) -> list[Path]:
        expanded = os.path.expandvars(value)
        pattern = Path(expanded).expanduser()
        patterns = [str(pattern)] if pattern.is_absolute() else [str(root / pattern) for root in roots]
        matches: list[Path] = []
        seen: set[str] = set()
        for item in patterns:
            for match in glob.glob(item):
                path = Path(match)
                try:
                    resolved = path.resolve()
                except OSError:
                    resolved = path.absolute()
                key = str(resolved).lower()
                if key in seen or not resolved.is_file():
                    continue
                seen.add(key)
                matches.append(resolved)
        return matches

    def _source_candidate_summary(self, manifest: ProviderAccountManifest) -> dict[str, Any]:
        metadata = manifest.metadata if isinstance(manifest.metadata, dict) else {}
        source_bridge = metadata.get("source_bridge") if isinstance(metadata.get("source_bridge"), dict) else {}
        return {
            "binary_candidates": self._string_list(source_bridge.get("binary_candidates")),
            "binary_glob_candidates": self._string_list(source_bridge.get("binary_glob_candidates")),
            "command_candidates": [
                str(item.get("label") or item.get("cwd") or "")
                for item in source_bridge.get("command_candidates", [])
                if isinstance(item, dict)
            ],
            "roots": [str(root) for root in self._source_roots(source_bridge)] if source_bridge else [],
        }

    def _source_root_label(self, path: Path, roots: list[Path]) -> str:
        for root in roots:
            try:
                path.relative_to(root)
                return str(root)
            except ValueError:
                continue
        return ""

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _optional_string_list(self, value: Any) -> list[str] | None:
        if value is None:
            return None
        return self._string_list(value)

    def _first_line(self, value: str) -> str:
        for line in value.splitlines():
            clean = line.strip()
            if clean:
                return clean[:240]
        return ""

    def _redact(self, value: str) -> str:
        return SECRET_OUTPUT_RE.sub("[redacted]", value).strip()[:2000]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
