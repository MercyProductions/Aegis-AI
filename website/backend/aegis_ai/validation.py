from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import ValidationProfileResponse, ValidationRecipe, ValidationSuggestion, VerificationStep
from .storage import utc_now
from .validation_commands import POWERSHELL_BUILD_COMMAND as DEFAULT_POWERSHELL_BUILD_COMMAND
from .validation_commands import is_blocked_validation_launcher_command
from .validation_commands import is_safe_powershell_build_guard_command


@dataclass(frozen=True)
class ValidationCandidate:
    command: str
    label: str
    category: str
    reason: str
    priority: int


class ValidationManager:
    PROFILE_PATH = ".aegis/validation_profile.json"
    PROJECT_MANIFEST_PATH = ".aegis/project.json"
    COMMAND_HISTORY_PATH = ".aegis/command_history.json"
    POWERSHELL_BUILD_COMMAND = DEFAULT_POWERSHELL_BUILD_COMMAND

    def profile_snapshot(self, workspace_root: Path) -> ValidationProfileResponse:
        profile = self.load_profile(workspace_root)
        suggestions = self.discover_commands(workspace_root)

        if profile is None and suggestions:
            best = suggestions[0]
            profile = ValidationRecipe(
                command=best.command,
                label=best.label,
                source="detected",
                updated_at="",
                notes=best.reason,
            )

        return ValidationProfileResponse(
            workspace_root=str(workspace_root),
            profile=profile,
            suggestions=suggestions,
        )

    def load_profile(self, workspace_root: Path) -> ValidationRecipe | None:
        path = self._profile_path(workspace_root)
        if not self._is_file(path):
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None

        command = str(payload.get("command", "")).strip() if isinstance(payload, dict) else ""
        if not command:
            return None

        return ValidationRecipe(
            command=command,
            label=str(payload.get("label", "")).strip(),
            source=str(payload.get("source", "")).strip(),
            updated_at=str(payload.get("updated_at", "")).strip(),
            notes=str(payload.get("notes", "")).strip(),
        )

    def save_profile(
        self,
        workspace_root: Path,
        *,
        command: str,
        label: str = "",
        source: str = "manual",
        notes: str = "",
    ) -> ValidationRecipe:
        normalized_command = command.strip()
        if not normalized_command:
            raise ValueError("validation command cannot be empty")

        recipe = ValidationRecipe(
            command=normalized_command,
            label=label.strip() or normalized_command,
            source=source.strip() or "manual",
            updated_at=utc_now(),
            notes=notes.strip(),
        )

        path = self._profile_path(workspace_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_profile(path, recipe.model_dump_json(indent=2))
        return recipe

    def clear_profile(self, workspace_root: Path) -> None:
        path = self._profile_path(workspace_root)
        if not path.exists():
            return
        if not self._is_file(path):
            raise OSError(f"{path} is not a regular file")
        path.unlink()

    def remember_success(self, workspace_root: Path, recipe: ValidationRecipe) -> ValidationRecipe:
        current = self.load_profile(workspace_root)
        if current and current.source == "manual":
            return current

        return self.save_profile(
            workspace_root,
            command=recipe.command,
            label=recipe.label or recipe.command,
            source="learned",
            notes=recipe.notes,
        )

    def discover_commands(self, workspace_root: Path) -> list[ValidationSuggestion]:
        candidates: list[ValidationCandidate] = []

        manifest_candidate = self._manifest_candidate(workspace_root)
        if manifest_candidate is not None:
            candidates.append(manifest_candidate)

        history_candidate = self._history_candidate(workspace_root)
        if history_candidate is not None:
            candidates.append(history_candidate)

        has_python_build_runner = self._is_file(workspace_root / "build.py")
        has_powershell_build_runner = self._is_file(workspace_root / "build.ps1")
        has_build_runner = has_python_build_runner or has_powershell_build_runner
        if has_python_build_runner:
            candidates.append(
                ValidationCandidate(
                    "python build.py",
                    "Project build runner",
                    "build",
                    "Runs the workspace-provided build and smoke-test script.",
                    132,
                )
            )
        if has_powershell_build_runner:
            candidates.append(
                ValidationCandidate(
                    self.POWERSHELL_BUILD_COMMAND,
                    "PowerShell build runner",
                    "build",
                    "Runs the workspace-provided PowerShell build and packaging guard script.",
                    131,
                )
            )
        if self._is_file(workspace_root / "build.js"):
            candidates.append(
                ValidationCandidate(
                    "node build.js",
                    "Static site validator",
                    "build",
                    "Runs the workspace-provided dependency-free static site validation script.",
                    126,
                )
            )

        package_json = workspace_root / "package.json"
        if self._is_file(package_json):
            candidates.extend(self._node_candidates(package_json))

        if self._is_file(workspace_root / "Cargo.toml"):
            candidates.extend(
                [
                    ValidationCandidate("cargo test", "Cargo test suite", "test", "Runs Rust tests for the workspace.", 120),
                    ValidationCandidate("cargo check", "Cargo check", "build", "Runs a fast Rust compile check.", 90),
                ]
            )

        if self._is_file(workspace_root / "go.mod"):
            candidates.append(
                ValidationCandidate("go test ./...", "Go test suite", "test", "Runs Go tests across all packages.", 120)
            )

        csproj = self._first_existing(workspace_root.glob("*.csproj"))
        if csproj is not None:
            candidates.extend(
                [
                    ValidationCandidate("dotnet test", "dotnet test", "test", "Runs the .NET test suite.", 120),
                    ValidationCandidate("dotnet build", "dotnet build", "build", "Builds the .NET workspace.", 90),
                ]
            )
        elif not has_build_runner:
            native_project = self._first_existing(workspace_root.glob("*.vcxproj"))
            solution = self._first_existing(workspace_root.glob("*.sln"))
            if native_project is not None:
                candidates.append(
                    ValidationCandidate(
                        f"msbuild {native_project.name} /m /p:Configuration=Debug",
                        "MSBuild native project",
                        "build",
                        "Builds the native Visual C++ project in Debug configuration.",
                        95,
                    )
                )
            elif solution is not None:
                candidates.append(
                    ValidationCandidate(
                        f"msbuild {solution.name} /m /p:Configuration=Debug",
                        "MSBuild solution",
                        "build",
                        "Builds the Visual Studio solution in Debug configuration.",
                        92,
                    )
                )

        if self._is_file(workspace_root / "CMakeLists.txt") and not has_build_runner:
            candidates.extend(
                [
                    ValidationCandidate(
                        "cmake -S . -B build && cmake --build build",
                        "CMake configure and build",
                        "build",
                        "Configures a fresh CMake build directory when needed, then builds it.",
                        118,
                    ),
                    ValidationCandidate(
                        "ctest --test-dir build --output-on-failure",
                        "CTest suite",
                        "test",
                        "Runs tests from the CMake build directory.",
                        88,
                    ),
                ]
            )

        makefile = self._first_existing([workspace_root / "Makefile", workspace_root / "makefile"])
        if makefile is not None:
            make_text = self._read_text(makefile, limit=32_000).lower()
            if "\ntest:" in make_text or make_text.startswith("test:"):
                candidates.append(ValidationCandidate("make test", "Make test target", "test", "Runs the Makefile test target.", 92))
            candidates.append(ValidationCandidate("make", "Make build", "build", "Runs the default Makefile build target.", 82))

        if self._is_file(workspace_root / "pom.xml"):
            candidates.extend(
                [
                    ValidationCandidate("mvn test", "Maven test suite", "test", "Runs Maven tests.", 116),
                    ValidationCandidate("mvn package", "Maven package", "build", "Builds the Maven package.", 86),
                ]
            )

        if any(
            self._is_file(workspace_root / name)
            for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
        ):
            candidates.extend(
                [
                    ValidationCandidate("gradle test", "Gradle test suite", "test", "Runs Gradle tests.", 112),
                    ValidationCandidate("gradle build", "Gradle build", "build", "Builds the Gradle workspace.", 84),
                ]
            )

        if any(
            self._is_file(workspace_root / name)
            for name in ("pyproject.toml", "requirements.txt", "setup.py")
        ):
            candidates.extend(self._python_candidates(workspace_root))

        if any(
            self._is_file(workspace_root / name)
            for name in ("tsconfig.json", "vite.config.ts", "vite.config.js")
        ):
            candidates.append(
                ValidationCandidate("npx tsc --noEmit", "TypeScript typecheck", "typecheck", "Runs a no-emit TypeScript typecheck.", 85)
            )

        if self._is_file(workspace_root / "prisma" / "schema.prisma"):
            candidates.append(
                ValidationCandidate("npx prisma validate", "Prisma schema validation", "database", "Validates the Prisma database schema.", 104)
            )

        if self._first_existing(workspace_root.glob("**/*.sql")) is not None or any(
            self._is_file(workspace_root / name) for name in (".sqlfluff", ".sqlfluffignore")
        ):
            candidates.append(
                ValidationCandidate("sqlfluff lint .", "SQL lint", "database", "Lints SQL files for syntax and style issues.", 74)
            )

        deduped: dict[str, ValidationCandidate] = {}
        for candidate in candidates:
            current = deduped.get(candidate.command)
            if current is None or candidate.priority > current.priority:
                deduped[candidate.command] = candidate

        ranked = sorted(deduped.values(), key=lambda item: (-item.priority, item.command))
        return [
            ValidationSuggestion(
                command=item.command,
                label=item.label,
                category=item.category,
                reason=item.reason,
            )
            for item in ranked
        ]

    def verification_plan(
        self,
        workspace_root: Path,
        *,
        include_install: bool = False,
        max_steps: int = 8,
    ) -> list[VerificationStep]:
        suggestions: list[ValidationSuggestion] = []

        if include_install:
            install_command = self._manifest_install_command(workspace_root)
            if not install_command:
                install_command = self._inferred_install_command(workspace_root)
            if install_command:
                suggestions.append(
                    ValidationSuggestion(
                        command=install_command,
                        label="Install dependencies",
                        category="install",
                        reason="Loaded from the Aegis project manifest.",
                    )
                )

        profile = self.load_profile(workspace_root)
        discovered = self.discover_commands(workspace_root)
        if profile is not None and all(item.command != profile.command for item in discovered):
            suggestions.append(
                ValidationSuggestion(
                    command=profile.command,
                    label=profile.label or "Pinned validation",
                    category=profile.source or "manual",
                    reason=profile.notes or "Pinned validation profile for this workspace.",
                )
            )
        suggestions.extend(discovered)

        deduped: list[ValidationSuggestion] = []
        seen: set[str] = set()
        for suggestion in suggestions:
            command = suggestion.command.strip()
            if not command or command in seen:
                continue
            seen.add(command)
            deduped.append(suggestion)

        ranked = sorted(
            enumerate(deduped),
            key=lambda item: (self._phase_rank(self._phase_for(item[1])), item[0]),
        )

        steps: list[VerificationStep] = []
        step_index = 1
        step_limit = max(1, max_steps)
        for _, suggestion in ranked:
            if len(steps) >= step_limit:
                break
            chain_commands = self._safe_and_chain_segments(suggestion.command)
            chain_total = len(chain_commands)
            for chain_index, command in enumerate(chain_commands, start=1):
                step_suggestion = ValidationSuggestion(
                    command=command,
                    label=self._chain_step_label(suggestion, command, chain_index=chain_index, chain_total=chain_total),
                    category=suggestion.category,
                    reason=suggestion.reason,
                )
                phase = self._phase_for(step_suggestion)
                steps.append(
                    VerificationStep(
                        id=f"{phase}-{step_index}",
                        phase=phase,
                        command=command,
                        label=step_suggestion.label or command,
                        category=suggestion.category,
                        required=self._required_for_phase(phase),
                        reason=suggestion.reason,
                        source_command=suggestion.command if chain_total > 1 else "",
                        chain_index=chain_index if chain_total > 1 else 0,
                        chain_total=chain_total if chain_total > 1 else 0,
                    )
                )
                step_index += 1
        return steps

    def _safe_and_chain_segments(self, command: str) -> list[str]:
        stripped = command.strip()
        if not stripped:
            return []

        segments: list[str] = []
        current: list[str] = []
        quote: str | None = None
        index = 0
        while index < len(stripped):
            char = stripped[index]
            if quote is not None:
                current.append(char)
                if char == quote:
                    quote = None
                index += 1
                continue

            if char in ("'", '"'):
                quote = char
                current.append(char)
                index += 1
                continue

            if char == "&":
                if index + 1 < len(stripped) and stripped[index + 1] == "&":
                    segment = "".join(current).strip()
                    if not segment:
                        return [stripped]
                    segments.append(segment)
                    current = []
                    index += 2
                    continue
                return [stripped]

            if char in "|;<>":
                return [stripped]

            current.append(char)
            index += 1

        if quote is not None:
            return [stripped]

        segment = "".join(current).strip()
        if not segment:
            return [stripped]
        segments.append(segment)

        if len(segments) <= 1:
            return [stripped]
        return segments

    def _chain_step_label(
        self,
        suggestion: ValidationSuggestion,
        command: str,
        *,
        chain_index: int,
        chain_total: int,
    ) -> str:
        if chain_total <= 1:
            return suggestion.label or command
        phase = self._phase_for(
            ValidationSuggestion(
                command=command,
                label=suggestion.label,
                category=suggestion.category,
                reason=suggestion.reason,
            )
        )
        action = {
            "configure": "Configure",
            "build": "Build",
            "test": "Test",
            "typecheck": "Type-check",
            "lint": "Lint",
            "database": "Validate database",
            "install": "Install",
        }.get(phase, "Validate")
        return f"{suggestion.label or 'Verification'} ({action} {chain_index}/{chain_total})"

    def _manifest_candidate(self, workspace_root: Path) -> ValidationCandidate | None:
        payload = self._manifest_payload(workspace_root)
        if payload is None:
            return None

        command = str(payload.get("validation_command", "")).strip()
        if not command:
            return None

        label = str(payload.get("preset_label", "")).strip()
        if label:
            label = f"{label} validation"
        else:
            label = "Aegis project validation"

        return ValidationCandidate(
            command=command,
            label=label,
            category="manifest",
            reason="Loaded from .aegis/project.json generated by Aegis Project Builder.",
            priority=135,
        )

    def _history_candidate(self, workspace_root: Path) -> ValidationCandidate | None:
        payload = self._command_history_payload(workspace_root)
        if payload is None:
            return None

        commands_value = payload.get("commands")
        commands = commands_value if isinstance(commands_value, list) else []
        top_level_command = str(payload.get("validation_command", "")).strip()
        latest_success: dict | None = None
        matching_success: dict | None = None

        for item in reversed(commands):
            if not isinstance(item, dict):
                continue
            if not self._history_entry_is_successful_validation(item):
                continue
            command = str(item.get("command", "")).strip()
            if not self._safe_history_validation_command(command):
                continue
            if latest_success is None:
                latest_success = item
            if top_level_command and command == top_level_command:
                matching_success = item
                break

        command = ""
        source_entry: dict | None = None
        reason = "Recovered from a previous successful validation run in .aegis/command_history.json."
        if top_level_command and self._safe_history_validation_command(top_level_command):
            if matching_success is not None:
                command = top_level_command
                source_entry = matching_success
            elif not commands:
                command = top_level_command
                reason = "Recovered from .aegis/command_history.json validation metadata."
        if not command and latest_success is not None:
            command = str(latest_success.get("command", "")).strip()
            source_entry = latest_success

        if not command:
            return None

        category = str((source_entry or {}).get("category") or "").strip().lower()
        if category not in {"build", "test", "typecheck", "lint", "database", "validation", "validate"}:
            category = self._category_for_history_command(command)

        return ValidationCandidate(
            command=command,
            label="Remembered validation command",
            category=category,
            reason=reason,
            priority=133,
        )

    def _history_entry_is_successful_validation(self, item: dict) -> bool:
        kind = str(item.get("kind") or "").strip().lower()
        category = str(item.get("category") or "").strip().lower()
        command = str(item.get("command") or "").strip()
        if not command:
            return False
        if item.get("allowed") is False:
            return False
        status = str(item.get("status") or "").strip().lower()
        exit_code = item.get("exit_code")
        successful = status in {"passed", "success", "succeeded", "ok"} or exit_code == 0
        if not successful:
            return False
        if kind == "validation" or kind.startswith("verification:"):
            return True
        if category in {"build", "test", "typecheck", "lint", "database", "validation", "validate"}:
            return True
        return self._category_for_history_command(command) != "validate"

    def _safe_history_validation_command(self, command: str) -> bool:
        normalized = " ".join(command.strip().lower().split())
        if not normalized or len(command) > 500:
            return False
        if any(char in command for char in ("\n", "\r", "|", ";", "<", ">")):
            return False

        index = 0
        while index < len(command):
            if command[index] == "&":
                if index + 1 < len(command) and command[index + 1] == "&":
                    index += 2
                    continue
                return False
            index += 1

        if normalized.startswith(("powershell ", "powershell.exe ", "pwsh ", "pwsh.exe ")):
            return is_safe_powershell_build_guard_command(command)

        if is_blocked_validation_launcher_command(command):
            return False

        blocked_prefixes = (
            "npm install",
            "npm i ",
            "pnpm install",
            "yarn install",
            "bun install",
            "pip install",
            "python -m pip install",
            "uv add",
            "poetry add",
            "cargo install",
            "winget ",
            "choco ",
            "scoop ",
            "curl ",
            "wget ",
            "irm ",
            "iex ",
            "powershell ",
            "powershell.exe ",
            "pwsh ",
            "pwsh.exe ",
            "cmd /c ",
            "reg ",
            "regedit",
            "del ",
            "erase ",
            "rm ",
            "rmdir ",
            "remove-item",
            "format ",
            "shutdown",
            "taskkill",
            "git clean",
            "git reset",
            "git checkout",
            "git push",
            "npm publish",
            "docker ",
        )
        return not any(normalized == prefix.strip() or normalized.startswith(prefix) for prefix in blocked_prefixes)

    def _category_for_history_command(self, command: str) -> str:
        suggestion = ValidationSuggestion(
            command=command,
            label="Remembered validation command",
            category="validate",
            reason="Recovered from command history.",
        )
        return self._phase_for(suggestion)

    def _command_history_payload(self, workspace_root: Path) -> dict | None:
        path = workspace_root / self.COMMAND_HISTORY_PATH
        if not self._is_file(path):
            return None

        try:
            if path.stat().st_size > 512_000:
                return None
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None
        schema = str(payload.get("schema", "")).strip()
        if schema and schema != "aegis.command_history.v1":
            return None
        return payload

    def _manifest_payload(self, workspace_root: Path) -> dict | None:
        path = workspace_root / self.PROJECT_MANIFEST_PATH
        if not self._is_file(path):
            return None

        try:
            if path.stat().st_size > 64_000:
                return None
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None

        return payload if isinstance(payload, dict) else None

    def _manifest_install_command(self, workspace_root: Path) -> str:
        payload = self._manifest_payload(workspace_root)
        if payload is None:
            return ""
        return str(payload.get("install_command", "")).strip()

    def _inferred_install_command(self, workspace_root: Path) -> str:
        package_json = workspace_root / "package.json"
        if self._is_file(package_json):
            payload = self._read_json_object(package_json) or {}
            return self._node_install_command(workspace_root, payload)
        if self._is_file(workspace_root / "pyproject.toml"):
            if self._is_file(workspace_root / "uv.lock"):
                return "uv sync"
            if self._is_file(workspace_root / "poetry.lock"):
                return "poetry install"
            return "python -m pip install -e ."
        if self._is_file(workspace_root / "requirements.txt"):
            return "python -m pip install -r requirements.txt"
        if self._is_file(workspace_root / "Cargo.toml"):
            return "cargo fetch"
        if self._is_file(workspace_root / "go.mod"):
            return "go mod download"
        if self._first_existing(workspace_root.glob("*.csproj")) is not None:
            return "dotnet restore"
        if self._is_file(workspace_root / "pom.xml"):
            return "mvn dependency:resolve"
        return ""

    def _node_candidates(self, package_json: Path) -> list[ValidationCandidate]:
        payload = self._read_json_object(package_json)
        if payload is None:
            return [ValidationCandidate("npm run build", "Node build", "build", "Builds the Node workspace.", 90)]

        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if not isinstance(scripts, dict):
            return []

        manager = self._node_package_manager(package_json.parent, payload)
        candidates: list[ValidationCandidate] = []
        script_preferences: list[tuple[str, str, str, str, int]] = [
            ("test", self._node_run_command(manager, "test"), "Node test suite", "test", 120),
            ("test:ci", self._node_run_command(manager, "test:ci"), "CI test suite", "test", 122),
            ("build", self._node_run_command(manager, "build"), "Node build", "build", 100),
            ("typecheck", self._node_run_command(manager, "typecheck"), "TypeScript typecheck", "typecheck", 98),
            ("check", self._node_run_command(manager, "check"), "Project checks", "typecheck", 95),
            ("lint", self._node_run_command(manager, "lint"), "Lint checks", "lint", 70),
        ]

        for script_name, command, label, category, priority in script_preferences:
            if script_name in scripts:
                candidates.append(
                    ValidationCandidate(command, label, category, f"Runs the '{script_name}' package script.", priority)
                )

        return candidates

    def _python_candidates(self, workspace_root: Path) -> list[ValidationCandidate]:
        has_tests = self._is_dir(workspace_root / "tests") or any(
            self._is_file(workspace_root / name) for name in ("pytest.ini", "conftest.py")
        )
        candidates: list[ValidationCandidate] = []

        if has_tests:
            candidates.append(
                ValidationCandidate("python -m pytest", "Pytest suite", "test", "Runs Python tests with pytest.", 120)
            )

        candidates.append(
            ValidationCandidate(
                "python -m compileall .",
                "Python compile check",
                "build",
                "Compiles Python files to catch syntax issues quickly.",
                70,
            )
        )
        return candidates

    def _phase_for(self, suggestion: ValidationSuggestion) -> str:
        category = suggestion.category.strip().lower()
        text = f"{category} {suggestion.label} {suggestion.command}".lower()
        command_text = suggestion.command.lower()
        if "cmake" in command_text and " -s " in f" {command_text} ":
            return "configure"
        if "cmake" in command_text and "--build" in command_text:
            return "build"
        if category in {"install", "configure", "build", "typecheck", "database", "lint", "test", "validate"}:
            return category

        if any(token in text for token in ("npm install", "pnpm install", "yarn install", "pip install", "cargo fetch")):
            return "install"
        if "configure" in text:
            return "configure"
        if any(token in text for token in ("typecheck", "type-check", "tsc --noemit", "mypy", "pyright")):
            return "typecheck"
        if any(token in text for token in ("prisma", "sqlfluff", "migration", "database", "schema")):
            return "database"
        if any(token in text for token in ("lint", "ruff", "eslint", "clippy")):
            return "lint"
        if any(token in text for token in (" test", "pytest", "vitest", "jest", "ctest", "cargo test", "go test")):
            return "test"
        if any(token in text for token in ("build", "compile", "msbuild", "cmake --build", "dotnet build", "cargo check")):
            return "build"
        return "validate"

    def _phase_rank(self, phase: str) -> int:
        order = {
            "install": 0,
            "configure": 1,
            "build": 2,
            "typecheck": 3,
            "database": 4,
            "lint": 5,
            "test": 6,
            "validate": 7,
        }
        return order.get(phase, 99)

    def _required_for_phase(self, phase: str) -> bool:
        return phase not in {"lint"}

    def _read_json_object(self, path: Path) -> dict | None:
        try:
            if not self._is_file(path) or path.stat().st_size > 512_000:
                return None
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _node_package_manager(self, workspace_root: Path, payload: dict) -> str:
        raw = str(payload.get("packageManager") or "").lower()
        if raw.startswith("pnpm"):
            return "pnpm"
        if raw.startswith("yarn"):
            return "yarn"
        if raw.startswith("bun"):
            return "bun"
        if raw.startswith("npm"):
            return "npm"
        if self._is_file(workspace_root / "pnpm-lock.yaml"):
            return "pnpm"
        if self._is_file(workspace_root / "yarn.lock"):
            return "yarn"
        if self._is_file(workspace_root / "bun.lockb") or self._is_file(workspace_root / "bun.lock"):
            return "bun"
        return "npm"

    def _node_run_command(self, package_manager: str, script: str) -> str:
        if package_manager == "pnpm":
            return f"pnpm {script}"
        if package_manager == "yarn":
            return f"yarn {script}"
        if package_manager == "bun":
            return f"bun run {script}"
        if script == "test":
            return "npm test"
        return f"npm run {script}"

    def _node_install_command(self, workspace_root: Path, payload: dict) -> str:
        package_manager = self._node_package_manager(workspace_root, payload)
        if package_manager == "pnpm":
            return "pnpm install"
        if package_manager == "yarn":
            return "yarn install"
        if package_manager == "bun":
            return "bun install"
        return "npm install"

    def _first_existing(self, paths) -> Path | None:
        for path in paths:
            if self._is_file(path):
                return path
        return None

    def _is_file(self, path: Path) -> bool:
        try:
            return path.is_file()
        except OSError:
            return False

    def _write_profile(self, path: Path, text: str) -> None:
        tmp = path.with_name(f".{path.name}.tmp")
        try:
            tmp.write_text(text + "\n", encoding="utf-8")
            tmp.replace(path)
        except OSError:
            try:
                if tmp.is_file():
                    tmp.unlink()
            except OSError:
                pass
            raise

    def _is_dir(self, path: Path) -> bool:
        try:
            return path.is_dir()
        except OSError:
            return False

    def _read_text(self, path: Path, *, limit: int) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except OSError:
            return ""

    def _profile_path(self, workspace_root: Path) -> Path:
        return workspace_root / self.PROFILE_PATH
