from __future__ import annotations

import json
import hashlib
import re
import textwrap
import uuid
from pathlib import Path
from typing import Callable

from .commands import CommandResult, CommandRunner
from .project_scaffold_paths import (
    WINDOWS_PATH_ACTION_FOLLOWERS as SCAFFOLD_WINDOWS_PATH_ACTION_FOLLOWERS,
    WINDOWS_PATH_CONTEXTUAL_ACTIONS as SCAFFOLD_WINDOWS_PATH_CONTEXTUAL_ACTIONS,
    WINDOWS_PATH_STOP_PHRASES as SCAFFOLD_WINDOWS_PATH_STOP_PHRASES,
    WINDOWS_PATH_STRONG_STOP_PHRASES as SCAFFOLD_WINDOWS_PATH_STRONG_STOP_PHRASES,
    clean_windows_path_fragment as scaffold_clean_windows_path_fragment,
    extract_windows_path_from_prompt as scaffold_extract_windows_path_from_prompt,
    path_action_boundary_preserves_leaf as scaffold_path_action_boundary_preserves_leaf,
    path_action_stop_positions as scaffold_path_action_stop_positions,
    path_fragment_exists as scaffold_path_fragment_exists,
    path_instruction_separator_position as scaffold_path_instruction_separator_position,
    path_stop_phrase_is_boundary as scaffold_path_stop_phrase_is_boundary,
    prompt_without_windows_paths as scaffold_prompt_without_windows_paths,
    trailing_wrapper_belongs_to_path as scaffold_trailing_wrapper_belongs_to_path,
    trim_path_fragment as scaffold_trim_path_fragment,
)
from .prompt_intent import prompt_has_explanation_prefix, prompt_requests_execution_validation
from .scaffolding import template_method_name
from .schemas import (
    CommandRun,
    FileChange,
    ProjectBuildStage,
    ProjectScaffoldFile,
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    ProjectScaffoldResponse,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceInstructionFile,
    WorkspaceProjectManifest,
)
from .storage import utc_now
from .validation import ValidationManager
from .workspace import WorkspaceManager


TemplateBuilder = Callable[[str], dict[str, str]]


class ProjectScaffolder:
    """Deterministic project scaffolding that still uses workspace checkpoints."""

    SAFE_METADATA_REFRESH_PATHS = {
        ".aegis/command_history.json",
        ".aegis/decisions.md",
        ".aegis/file_index.json",
        ".aegis/instruction_status.json",
        ".aegis/known_errors.json",
        ".aegis/ROADMAP.md",
        ".aegis/project.json",
        ".aegis/validation_plan.json",
        ".gitignore",
        "AGENTS.md",
        "README.md",
    }
    WINDOWS_PATH_STOP_PHRASES = SCAFFOLD_WINDOWS_PATH_STOP_PHRASES
    WINDOWS_PATH_STRONG_STOP_PHRASES = SCAFFOLD_WINDOWS_PATH_STRONG_STOP_PHRASES
    WINDOWS_PATH_CONTEXTUAL_ACTIONS = SCAFFOLD_WINDOWS_PATH_CONTEXTUAL_ACTIONS
    WINDOWS_PATH_ACTION_FOLLOWERS = SCAFFOLD_WINDOWS_PATH_ACTION_FOLLOWERS
    TARGET_NAMED_WEB_PRESETS = {
        "nextjs-ts-tailwind",
        "vite-react-ts",
        "static-html-site",
    }
    PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS = {
        "cpp-imgui-win32-dx11",
        "cpp-game-loop-cmake",
        "python-game-file-analyzer",
        "cpp-windows-internals-hooking",
        "python-sln-refactor-tool",
        "windows-kernel-driver-controller",
    }
    PRESET_DEFAULT_PROJECT_NAMES = {
        "cpp-imgui-win32-dx11": "imgui-tool",
        "cpp-game-loop-cmake": "game-loop-sandbox",
        "python-game-file-analyzer": "game-file-analyzer",
        "cpp-windows-internals-hooking": "windows-internals-tool",
        "python-sln-refactor-tool": "solution-refactor-tool",
        "windows-kernel-driver-controller": "kernel-driver-controller",
    }
    INSTRUCTIONAL_PROJECT_NAME_TOKENS = {
        "build",
        "combine",
        "create",
        "enumerate",
        "extract",
        "generate",
        "inspect",
        "instrument",
        "make",
        "merge",
        "separate",
        "split",
        "tool",
        "write",
    }
    GENERIC_TARGET_NAMES = {
        "app",
        "application",
        "desktop",
        "folder",
        "new-folder",
        "project",
        "roblox",
        "site",
        "test",
        "tests",
        "untitled",
        "web",
        "website",
        "workspace",
    }

    def __init__(
        self,
        workspace: WorkspaceManager,
        validation: ValidationManager,
        *,
        commands: CommandRunner | None = None,
        sandbox_profile: str | None = None,
    ):
        self.workspace = workspace
        self.validation = validation
        self.commands = commands
        self.sandbox_profile = sandbox_profile

    @classmethod
    def presets(cls) -> list[ProjectScaffoldPreset]:
        return [
            ProjectScaffoldPreset(
                id="nextjs-ts-tailwind",
                label="Next.js TypeScript + Tailwind",
                framework="Next.js App Router",
                language="TypeScript",
                package_manager="npm",
                install_command="npm install",
                validation_command="npm run build",
                description="Production-ready web app shell with App Router, Tailwind, typed config, and a polished first screen.",
                tags=["web", "react", "full-stack", "tailwind"],
            ),
            ProjectScaffoldPreset(
                id="vite-react-ts",
                label="Vite React TypeScript",
                framework="Vite + React",
                language="TypeScript",
                package_manager="npm",
                install_command="npm install",
                validation_command="npm run build",
                description="Fast client app scaffold with Vite, React, TypeScript, and a focused dashboard surface.",
                tags=["web", "react", "spa", "vite"],
            ),
            ProjectScaffoldPreset(
                id="static-html-site",
                label="Static HTML Website",
                framework="HTML + CSS + JavaScript",
                language="JavaScript",
                package_manager="browser",
                install_command="",
                validation_command="node build.js",
                description="Dependency-free business website with responsive pages, contact form behavior, local preview server, and static validation.",
                tags=["web", "website", "html", "css", "javascript", "static"],
            ),
            ProjectScaffoldPreset(
                id="browser-extension-mv3",
                label="Browser Extension Manifest V3",
                framework="Chrome/Edge Manifest V3",
                language="JavaScript + HTML + CSS",
                package_manager="browser",
                install_command="",
                validation_command="python build.py",
                description="Package-free browser extension scaffold with MV3 manifest, popup, options page, background service worker, content script, and static validation.",
                tags=["browser", "extension", "chrome", "edge", "mv3"],
            ),
            ProjectScaffoldPreset(
                id="vscode-extension-js",
                label="VS Code Extension JavaScript",
                framework="VS Code Extension API",
                language="JavaScript",
                package_manager="node",
                install_command="",
                validation_command="python build.py",
                description="Package-free VS Code extension scaffold with command contributions, activation events, settings, status bar wiring, and static validation.",
                tags=["vscode", "extension", "javascript", "developer-tools"],
            ),
            ProjectScaffoldPreset(
                id="node-cli-js",
                label="Node.js CLI Tool",
                framework="Node.js",
                language="JavaScript",
                package_manager="node",
                install_command="",
                validation_command="node build.js",
                description="Package-free Node.js command-line tool with argument parsing, executable bin entrypoint, built-in node:test coverage, and static validation.",
                tags=["node", "javascript", "cli", "automation", "tool"],
            ),
            ProjectScaffoldPreset(
                id="node-http-api-js",
                label="Node.js HTTP API",
                framework="Node.js stdlib HTTP",
                language="JavaScript",
                package_manager="node",
                install_command="",
                validation_command="node build.js",
                description="Dependency-free REST API scaffold with health checks, JSON CRUD routes, in-memory storage, node:test coverage, and static validation.",
                tags=["api", "node", "javascript", "backend", "rest"],
            ),
            ProjectScaffoldPreset(
                id="node-fullstack-js",
                label="Node.js Full-Stack App",
                framework="Node.js stdlib HTTP + static frontend",
                language="JavaScript",
                package_manager="node",
                install_command="",
                validation_command="node build.js",
                description="Dependency-free full-stack CRUD app with static UI, JSON persistence, API routes, node:test coverage, and local preview server.",
                tags=["web", "full-stack", "node", "javascript", "crud", "dashboard"],
            ),
            ProjectScaffoldPreset(
                id="powershell-module",
                label="PowerShell Automation Module",
                framework="PowerShell module",
                language="PowerShell",
                package_manager="powershell",
                install_command="",
                validation_command="powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1",
                description="Dependency-free PowerShell module scaffold with manifest, exported functions, CLI script, parser validation, and smoke tests.",
                tags=["powershell", "automation", "windows", "module", "scripts"],
            ),
            ProjectScaffoldPreset(
                id="python-cli",
                label="Python CLI Package",
                framework="Python package",
                language="Python",
                package_manager="pip",
                install_command="python -m pip install -e .[dev]",
                validation_command="python build.py",
                description="Installable Python command-line project with pyproject metadata, package source, dependency-free build validation, and smoke tests.",
                tags=["python", "cli", "automation", "tests"],
            ),
            ProjectScaffoldPreset(
                id="python-tkinter-desktop",
                label="Python Tkinter Desktop App",
                framework="Python stdlib Tkinter",
                language="Python",
                package_manager="python",
                install_command="",
                validation_command="python build.py",
                description="Dependency-light desktop utility with a Tkinter GUI, app state layer, JSON persistence, and validation tests.",
                tags=["python", "desktop", "tkinter", "gui", "utility"],
            ),
            ProjectScaffoldPreset(
                id="python-stdlib-api",
                label="Python Stdlib HTTP API",
                framework="Python http.server",
                language="Python",
                package_manager="python",
                install_command="",
                validation_command="python build.py",
                description="Dependency-free Python REST API scaffold with JSON CRUD routes, file-backed storage, unittest coverage, and static compilation checks.",
                tags=["api", "python", "backend", "rest", "json"],
            ),
            ProjectScaffoldPreset(
                id="fastapi-python-api",
                label="FastAPI Python API",
                framework="FastAPI",
                language="Python",
                package_manager="pip",
                install_command="python -m pip install -e .[dev]",
                validation_command="python -m pytest",
                description="Typed FastAPI service with settings, health route, app factory, and API smoke tests.",
                tags=["api", "python", "fastapi", "backend"],
            ),
            ProjectScaffoldPreset(
                id="express-ts-api",
                label="Express TypeScript API",
                framework="Express",
                language="TypeScript",
                package_manager="npm",
                install_command="npm install",
                validation_command="npm run build",
                description="Node/Express API scaffold with TypeScript, config loading, health route, and production build script.",
                tags=["api", "node", "typescript", "backend"],
            ),
            ProjectScaffoldPreset(
                id="sqlite-python-db",
                label="SQLite Python Database Tool",
                framework="SQLite + Python stdlib",
                language="Python",
                package_manager="python",
                install_command="",
                validation_command="python build.py",
                description="Dependency-light database project with SQLite schema, seed data, CLI helpers, query examples, and validation tests.",
                tags=["database", "sqlite", "sql", "python", "cli"],
            ),
            ProjectScaffoldPreset(
                id="cpp-cmake-cli",
                label="C++ CMake CLI",
                framework="CMake",
                language="C++17",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Portable C++17 command-line project with CMake, include/source layout, and a tiny smoke test executable.",
                tags=["cpp", "cmake", "cli", "native"],
            ),
            ProjectScaffoldPreset(
                id="cpp-cmake-dll",
                label="C++ CMake DLL / Shared Library",
                framework="CMake",
                language="C++17",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Portable C++17 shared-library/DLL project with export macros, CMake build files, and a smoke-test executable.",
                tags=["cpp", "cmake", "dll", "shared-library", "native"],
            ),
            ProjectScaffoldPreset(
                id="cpp-imgui-win32-dx11",
                label="C++ Dear ImGui Win32/DX11 Tool",
                framework="CMake + Dear ImGui + Win32 + DirectX 11",
                language="C++20",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Native Dear ImGui desktop tool scaffold for game-dev editors, inspectors, debug panels, and internal tooling.",
                tags=["cpp", "imgui", "dear-imgui", "win32", "directx11", "game-dev", "tools"],
            ),
            ProjectScaffoldPreset(
                id="cpp-game-loop-cmake",
                label="C++ Game Loop Sandbox",
                framework="CMake",
                language="C++20",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Portable C++ game-development sandbox with fixed timestep loop, lightweight world state, asset registry, and smoke tests.",
                tags=["cpp", "game", "game-dev", "engine", "simulation", "cmake"],
            ),
            ProjectScaffoldPreset(
                id="python-game-file-analyzer",
                label="Game File / Asset Analyzer",
                framework="Python stdlib",
                language="Python",
                package_manager="python",
                install_command="",
                validation_command="python build.py",
                description="Dependency-free static analysis toolkit for owned/authorized game files, asset folders, binary headers, strings, entropy, and format reports.",
                tags=["python", "game-files", "asset-pipeline", "reverse-engineering", "binary-analysis", "tools"],
            ),
            ProjectScaffoldPreset(
                id="cpp-msvc-console-sln",
                label="C++ Visual Studio Console Solution",
                framework="Visual Studio / MSBuild",
                language="C++17",
                package_manager="msbuild",
                install_command="",
                validation_command="python build.py",
                description="Windows C++ console application with a Visual Studio solution, vcxproj, and a hello-world entrypoint that waits for Enter before closing.",
                tags=["cpp", "visual-studio", "sln", "console", "native", "windows"],
            ),
            ProjectScaffoldPreset(
                id="cpp-windows-service",
                label="C++ Windows Service",
                framework="CMake + Win32 Service API",
                language="C++17",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Native Windows service scaffold with service entrypoint, console mode, install/uninstall commands, CMake build files, and smoke tests.",
                tags=["windows", "service", "cpp", "cmake", "native", "system"],
            ),
            ProjectScaffoldPreset(
                id="cpp-windows-internals-hooking",
                label="C++ Windows Internals / Hooking Tool",
                framework="CMake + Win32 API + MinHook-style Abstraction",
                language="C++20",
                package_manager="cmake",
                install_command="",
                validation_command="python build.py",
                description="Authorized Windows internals and instrumentation scaffold with process/module inspection, hook-plan modeling, and MinHook-compatible boundaries.",
                tags=["windows", "internals", "cpp", "hooking", "minhook", "instrumentation", "diagnostics"],
            ),
            ProjectScaffoldPreset(
                id="python-sln-refactor-tool",
                label="Visual Studio Solution Merge/Split Tool",
                framework="Python Stdlib + Visual Studio Solution Parser",
                language="Python 3.11",
                package_manager="python",
                install_command="",
                validation_command="python build.py",
                description="Dependency-free tool for inspecting, merging, and splitting Visual Studio .sln/.vcxproj project collections.",
                tags=["visual-studio", "sln", "vcxproj", "solution", "refactor", "python"],
            ),
            ProjectScaffoldPreset(
                id="windows-kernel-driver-controller",
                label="Windows Kernel Driver + Controller",
                framework="Visual Studio / WDK",
                language="C/C++17",
                package_manager="msbuild",
                install_command="",
                validation_command="python build.py",
                description="Windows driver project plus a C++ controller app that communicates through a documented device IOCTL channel.",
                tags=["windows", "kernel", "driver", "wdk", "cpp", "controller"],
            ),
            ProjectScaffoldPreset(
                id="electron-react-ts",
                label="Electron React TypeScript",
                framework="Electron + Vite + React",
                language="TypeScript",
                package_manager="npm",
                install_command="npm install",
                validation_command="npm run build",
                description="Cross-platform desktop shell with Electron main/preload processes, Vite React renderer, and TypeScript build scripts.",
                tags=["desktop", "electron", "react", "typescript"],
            ),
            ProjectScaffoldPreset(
                id="expo-react-native-ts",
                label="Expo React Native TypeScript",
                framework="Expo",
                language="TypeScript",
                package_manager="npm",
                install_command="npm install",
                validation_command="npm run typecheck",
                description="Mobile app starter for iOS, Android, and web using Expo, React Native, typed screens, and app config.",
                tags=["mobile", "expo", "react-native", "typescript"],
            ),
            ProjectScaffoldPreset(
                id="django-python-web",
                label="Django Python Web App",
                framework="Django",
                language="Python",
                package_manager="pip",
                install_command="python -m pip install -r requirements.txt",
                validation_command="python manage.py test",
                description="Django web app with project settings, first app, health view, tests, and SQLite development defaults.",
                tags=["web", "python", "django", "backend"],
            ),
            ProjectScaffoldPreset(
                id="rust-cli",
                label="Rust CLI",
                framework="Cargo",
                language="Rust",
                package_manager="cargo",
                install_command="",
                validation_command="cargo test",
                description="Rust command-line starter with Cargo metadata, library logic, binary entrypoint, and unit tests.",
                tags=["rust", "cli", "native", "automation"],
            ),
            ProjectScaffoldPreset(
                id="go-http-api",
                label="Go HTTP API",
                framework="Go net/http",
                language="Go",
                package_manager="go",
                install_command="go mod tidy",
                validation_command="go test ./...",
                description="Small Go HTTP API service with typed handlers, health route, server wiring, and tests.",
                tags=["api", "go", "backend", "service"],
            ),
            ProjectScaffoldPreset(
                id="dotnet-webapi-csharp",
                label="ASP.NET Core C# Web API",
                framework="ASP.NET Core Minimal API",
                language="C#",
                package_manager="dotnet",
                install_command="dotnet restore",
                validation_command="dotnet test",
                description="C# solution with ASP.NET Core Minimal API project, xUnit tests, health endpoint, and typed app model.",
                tags=["api", "dotnet", "csharp", "backend"],
            ),
            ProjectScaffoldPreset(
                id="dotnet-console-csharp",
                label="C# .NET Console App",
                framework=".NET Console",
                language="C#",
                package_manager="dotnet",
                install_command="dotnet restore",
                validation_command="python build.py",
                description="Package-free C# console/exe project with a typed command engine, self-test mode, and build validation script.",
                tags=["dotnet", "csharp", "console", "cli", "exe"],
            ),
            ProjectScaffoldPreset(
                id="dotnet-wpf-csharp",
                label="C# WPF Desktop App",
                framework=".NET WPF",
                language="C# + XAML",
                package_manager="dotnet",
                install_command="dotnet restore",
                validation_command="python build.py",
                description="Native Windows WPF desktop app with XAML UI, testable state layer, and package-free smoke validation.",
                tags=["dotnet", "csharp", "wpf", "xaml", "desktop", "windows"],
            ),
            ProjectScaffoldPreset(
                id="tauri-react-ts",
                label="Tauri React TypeScript",
                framework="Tauri + Vite + React",
                language="TypeScript + Rust",
                package_manager="npm/cargo",
                install_command="npm install",
                validation_command="npm run build",
                description="Lightweight desktop app shell with Vite React frontend, Tauri Rust host config, and typed build scripts.",
                tags=["desktop", "tauri", "react", "rust"],
            ),
        ]

    def preview(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        return self._build(request, apply=False)

    def scaffold(self, request: ProjectScaffoldRequest) -> ProjectScaffoldResponse:
        return self._build(request, apply=True)

    def plan_from_prompt(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
        prompt = " ".join(request.prompt.split())
        if not prompt:
            raise ValueError("prompt is required")

        target_path = self._clean_windows_path_fragment(request.preferred_target_path.strip())
        if not target_path:
            target_path = self._extract_windows_path_from_prompt(prompt)
        intent_prompt = self._prompt_without_windows_paths(prompt, target_path=target_path)

        base_workspace = self.workspace.resolve_workspace(
            request.workspace_root,
            migrate_legacy=False,
            create=False,
        )
        target_probe = self.workspace.resolve_workspace(
            target_path if target_path else str(base_workspace),
            migrate_legacy=False,
            create=False,
        )
        existing_manifest = (
            self.workspace.load_project_manifest(target_probe)
            if target_probe.exists() and target_probe.is_dir()
            else None
        )
        existing_profile = (
            self.workspace.inspect_dependency_profile(target_probe)
            if target_probe.exists() and target_probe.is_dir()
            else WorkspaceDependencyProfile()
        )
        preset, confidence, reasons, detected_keywords = self._select_preset(intent_prompt)
        stack_locks = self._stack_lock_keywords_for_prompt(intent_prompt)
        for item in stack_locks:
            if item not in detected_keywords:
                detected_keywords.insert(0, item)
        continuity_preset_id = self._continuity_preset_id(
            prompt=prompt,
            target=target_probe,
            manifest=existing_manifest,
            profile=existing_profile,
        )
        if continuity_preset_id and self._stack_locks_conflict_with_preset(stack_locks, continuity_preset_id):
            if self._prompt_allows_stack_switch(intent_prompt or prompt, stack_locks):
                reasons.insert(0, "The current prompt declared a different stack than the saved workspace context.")
                detected_keywords.insert(0, "current prompt stack override")
                continuity_preset_id = ""
            else:
                reasons.insert(
                    0,
                    "The saved mission contract kept the existing workspace stack despite ambiguous follow-up wording.",
                )
                detected_keywords.insert(0, "mission-contract:locked-stack")
        if continuity_preset_id:
            preset = self._preset_for(continuity_preset_id)
            confidence = max(confidence, 0.92)
            reasons.insert(0, f"Existing workspace context selected {preset.label}.")
            detected_keywords.insert(0, "mission-contract:reuse")
            detected_keywords.insert(0, "existing workspace continuity")
        raw_name = self._project_name_from_prompt(intent_prompt or prompt)
        if not self._has_explicit_project_name(prompt):
            raw_name = (
                (existing_manifest.project_name or existing_manifest.title)
                if existing_manifest and continuity_preset_id
                else self._preset_default_project_name_if_needed(preset.id, raw_name)
            )
        if target_path and not self._has_explicit_project_name(prompt):
            target_leaf = Path(target_path).name
            target_has_project_manifest = existing_manifest is not None
            if (
                not continuity_preset_id
                and (
                self._should_use_target_leaf_project_name(preset.id, target_leaf)
                or (
                    not target_has_project_manifest
                    and (
                        self._target_leaf_is_specific(target_leaf)
                        or preset.id not in self.PROMPT_NAMED_ON_GENERIC_TARGET_PRESETS
                    )
                )
                )
            ):
                raw_name = target_leaf or raw_name
                if not self._target_leaf_is_specific(target_leaf):
                    raw_name = self._preset_default_project_name_if_needed(preset.id, raw_name)
        elif continuity_preset_id and not self._has_explicit_project_name(prompt):
            raw_name = raw_name or target_probe.name
        project_name = self._project_name(raw_name)
        install_command = self._command_for_project(preset.install_command, project_name)
        validation_command = self._command_for_project(preset.validation_command, project_name)
        if existing_manifest and continuity_preset_id:
            install_command = existing_manifest.install_command or install_command
            validation_command = existing_manifest.validation_command or validation_command
        run_validation = self._prompt_requests_validation(prompt)

        target = self.workspace.resolve_workspace(
            target_path if target_path else (str(target_probe) if continuity_preset_id else str(base_workspace / project_name)),
            migrate_legacy=False,
            create=False,
        )
        overwrite = self._should_update_existing_scaffold(prompt, target)

        scaffold_request = ProjectScaffoldRequest(
            target_path=str(target),
            preset_id=preset.id,
            project_name=project_name,
            prompt=prompt,
            overwrite=overwrite,
            install_command=install_command,
            validation_command=validation_command,
            include_gitignore=True,
            run_validation=run_validation,
        )
        execution_mode = "existing_validation" if self._should_validate_existing_project_only(
            prompt,
            target,
            scaffold_request,
            existing_profile,
        ) else "scaffold"
        if execution_mode == "existing_validation":
            validation_command = self._existing_project_validation_command(
                target,
                existing_profile,
                validation_command,
            )
            scaffold_request = scaffold_request.model_copy(
                update={"validation_command": validation_command}
            )
        primary_action = (
            "validate_existing_project"
            if execution_mode == "existing_validation"
            else "create_or_update_files"
        )
        plan_steps = self._default_plan_steps(preset, project_name, install_command, validation_command)
        risk_warnings = self._risk_warnings_for_target(target, overwrite=overwrite)
        assumptions = [
            "This is a planning result only; use preview or create before files are written.",
            "The target folder passed the configured Aegis workspace allowlist.",
        ]
        if raw_name == "aegis-app":
            assumptions.append("No explicit project name was found, so Aegis used a safe default name.")
        if not target_path:
            assumptions.append("No target folder was supplied, so Aegis placed the project under the active workspace root.")
        if run_validation:
            assumptions.append("The prompt asked Aegis to build, run, test, or validate the project, so validation is enabled for the scaffold request.")
        if continuity_preset_id:
            assumptions.append("Existing workspace manifest or build files were detected, so Aegis reused the current project stack instead of selecting a new scaffold from the follow-up prompt.")
        if execution_mode == "existing_validation":
            assumptions.append("This is an existing-project validation pass; Aegis will not generate starter files before build/test repair.")
        if stack_locks:
            assumptions.append("The prompt included explicit stack language, so Aegis will preserve that stack instead of drifting to a generic starter.")

        return ProjectScaffoldPlanResponse(
            ok=True,
            message=f"Planned {preset.label} from prompt.",
            prompt=prompt,
            execution_mode=execution_mode,
            primary_action=primary_action,
            confidence=confidence,
            preset=preset,
            project_name=project_name,
            target_path=str(target),
            install_command=install_command,
            validation_command=validation_command,
            overwrite=overwrite,
            include_gitignore=True,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            reasons=reasons,
            assumptions=assumptions,
            detected_keywords=detected_keywords,
            scaffold_request=scaffold_request,
        )

    def _build(self, request: ProjectScaffoldRequest, *, apply: bool) -> ProjectScaffoldResponse:
        request = self._normalize_scaffold_request_from_prompt(request)
        preset = self._preset_for(request.preset_id)
        project_name = self._project_name(request.project_name)
        target = self.workspace.resolve_workspace(request.target_path, migrate_legacy=False, create=apply)
        prompt = " ".join(request.prompt.split())
        existing_files = self.workspace.scan(target, max_files=160) if target.exists() else []
        existing_profile = (
            self.workspace.inspect_dependency_profile(target)
            if target.exists() and target.is_dir()
            else WorkspaceDependencyProfile()
        )
        plan_steps = self._default_plan_steps(
            preset,
            project_name,
            self._command_for_project(request.install_command.strip() or preset.install_command, project_name),
            self._command_for_project(request.validation_command.strip() or preset.validation_command, project_name),
        )
        pre_warnings: list[str] = []
        stages: list[ProjectBuildStage] = [
            ProjectBuildStage(
                id="intent",
                label="Read request and create visible plan",
                status="succeeded",
                detail=f"Selected {preset.label} for {project_name} and prepared {len(plan_steps)} execution step(s).",
            ),
            ProjectBuildStage(
                id="inspect",
                label="Inspect target workspace",
                status="succeeded" if target.exists() else "skipped",
                detail=self._inspection_detail(target, existing_files, existing_profile),
            )
        ]

        validation_command = self._command_for_project(request.validation_command.strip() or preset.validation_command, project_name)
        install_command = self._command_for_project(request.install_command.strip() or preset.install_command, project_name)
        if self._should_validate_existing_project_only(prompt, target, request, existing_profile):
            return self._existing_project_validation_response(
                request,
                apply=apply,
                target=target,
                preset=preset,
                project_name=project_name,
                install_command=install_command,
                validation_command=validation_command,
                existing_files=existing_files,
                existing_profile=existing_profile,
                plan_steps=plan_steps,
                stages=stages,
            )

        files = self._template_for(preset.id)(project_name)
        files = self._specialize_template_for_prompt(preset.id, project_name, prompt, files)
        if not request.include_gitignore:
            files.pop(".gitignore", None)
        if request.create_roadmap:
            files.update(
                self._roadmap_files(
                    preset,
                    project_name,
                    prompt=prompt,
                    install_command=install_command,
                    validation_command=validation_command,
                    max_repair_attempts=request.max_repair_attempts,
                )
            )
        files.update(
            self._aegis_handoff_files(
                preset,
                project_name,
                prompt=prompt,
                install_command=install_command,
                validation_command=validation_command,
            )
        )
        existing_entries = self._visible_entries(target)
        conflicting_paths = self._conflicting_paths(target, files)
        metadata_only_refresh = (
            self._is_metadata_only_refresh(target, conflicting_paths)
            and not self._has_non_metadata_entries(target)
        )
        if conflicting_paths and not request.overwrite and not metadata_only_refresh:
            original_target = target
            target = self._next_available_child_target(target, project_name)
            existing_entries = self._visible_entries(target)
            conflicting_paths = self._conflicting_paths(target, files)
            same_child_project = self._is_same_scaffold_project(target, preset.id, project_name)
            metadata_only_refresh = (
                self._is_metadata_only_refresh(target, conflicting_paths)
                and not self._has_non_metadata_entries(target)
            )
            if conflicting_paths and not metadata_only_refresh and not same_child_project:
                target = self._next_available_child_target(original_target, f"{project_name}-{preset.id}")
                existing_entries = self._visible_entries(target)
                conflicting_paths = self._conflicting_paths(target, files)
                same_child_project = self._is_same_scaffold_project(target, preset.id, project_name)
                metadata_only_refresh = (
                    self._is_metadata_only_refresh(target, conflicting_paths)
                    and not self._has_non_metadata_entries(target)
                )
            if same_child_project and conflicting_paths:
                pre_warnings.append(
                    "Requested target already contained another scaffold. Aegis reused the matching child project "
                    f"at {target} and refreshed its generated files."
                )
            else:
                pre_warnings.append(
                    "Requested target already contained scaffold-owned paths from another project. "
                    f"Aegis created a clean child project at {target} instead of stopping or overwriting files."
                )
        if existing_entries and not conflicting_paths:
            pre_warnings.append(
                "Target folder already contained files. Aegis wrote only non-conflicting scaffold files and left existing files untouched."
            )
        elif metadata_only_refresh and not request.overwrite:
            pre_warnings.append(
                "Target folder only contained Aegis scaffold metadata conflicts. Aegis refreshed metadata and left other files untouched."
            )
        elif conflicting_paths and request.overwrite:
            pre_warnings.append(
                "Target folder contained scaffold-owned files. Aegis updated only generated paths for this preset."
            )
        existing_files = self.workspace.scan(target, max_files=160) if target.exists() else []
        existing_profile = (
            self.workspace.inspect_dependency_profile(target)
            if target.exists() and target.is_dir()
            else WorkspaceDependencyProfile()
        )
        risk_warnings = self._risk_warnings_for_target(target, overwrite=request.overwrite)
        memory_files = self._project_memory_files(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            existing_files=existing_files,
            existing_profile=existing_profile,
            planned_files=files,
        )
        files.update(memory_files)
        memory_paths = sorted(memory_files)
        stages.append(
            ProjectBuildStage(
                id="structure",
                label="Generate project structure",
                status="succeeded",
                detail=f"Prepared {len(files)} scaffold file(s), including Aegis handoff metadata.",
            )
        )
        stages.append(
            ProjectBuildStage(
                id="roadmap",
                label="Create roadmap and handoff files",
                status="succeeded" if request.create_roadmap else "skipped",
                detail=(
                    "Added .aegis/ROADMAP.md with the visible plan, validation path, and repair loop expectations."
                    if request.create_roadmap
                    else "Roadmap creation was disabled for this request."
                ),
            )
        )

        changes: list[FileChange] = []
        file_infos: list[ProjectScaffoldFile] = []
        for relative_path, content in files.items():
            target_file = target / relative_path
            action = "update" if target_file.exists() else "create"
            changes.append(
                FileChange(
                    action=action,
                    path=relative_path,
                    content=content,
                    summary=f"{action.title()} {relative_path} for the {preset.label} preset.",
                )
            )
            file_infos.append(
                ProjectScaffoldFile(
                    path=relative_path,
                    action=action,
                    summary=f"{action.title()} scaffold file.",
                    size=len(content.encode("utf-8")),
                )
            )
        diff_summary = self._diff_summary(file_infos)
        stages.append(
            ProjectBuildStage(
                id="diff",
                label="Prepare file diff preview",
                status="succeeded",
                detail=", ".join(diff_summary) if diff_summary else "No file changes are planned.",
            )
        )

        apply_result = None
        validation: CommandRun | None = None
        applied: list[str] = []
        warnings: list[str] = []
        warnings.extend(pre_warnings)
        checkpoint: str | None = None
        if apply:
            apply_result = self.workspace.apply_changes(target, changes)
            applied.extend(apply_result.applied)
            warnings.extend(apply_result.warnings)
            checkpoint = apply_result.checkpoint
            stages.append(
                ProjectBuildStage(
                    id="apply",
                    label="Write files with checkpoint",
                    status="succeeded",
                    detail=f"Applied {len(apply_result.applied)} file change(s).",
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="apply",
                    label="Write files with checkpoint",
                    status="skipped",
                    detail="Preview mode only; no files were written.",
                )
            )

        if apply and validation_command:
            self.validation.save_profile(
                target,
                command=validation_command,
                label=f"{preset.label} validation",
                source="project_builder",
                notes="Generated by the Aegis Project Builder scaffold preset.",
            )

        install_run: CommandRun | None = None
        auto_install_before_validation = self._should_install_before_validation(
            preset,
            target,
            install_command=install_command,
            validation_command=validation_command,
            request=request,
        )
        should_run_install = apply and install_command and (request.run_install or auto_install_before_validation)
        if should_run_install:
            install_stage, install_run = self._run_command_stage(
                stage_id="install",
                label="Install dependencies",
                command=install_command,
                target=target,
            )
            if auto_install_before_validation:
                install_stage.detail = (
                    install_stage.detail.rstrip(".")
                    + ". Auto-ran before validation because this is a fresh dependency-managed scaffold."
                )
            stages.append(install_stage)
        else:
            stages.append(
                ProjectBuildStage(
                    id="install",
                    label="Install dependencies",
                    status="skipped" if install_command else "planned",
                    detail=(
                        "Install command captured but not run automatically."
                        if install_command
                        else "No install command is defined for this preset."
                    ),
                    command=install_command,
                )
            )

        if apply and request.run_validation and validation_command:
            validation_stage, validation = self._run_command_stage(
                stage_id="validate",
                label="Run build/test validation",
                command=validation_command,
                target=target,
            )
            stages.append(validation_stage)
        else:
            stages.append(
                ProjectBuildStage(
                    id="validate",
                    label="Run build/test validation",
                    status="skipped" if validation_command else "planned",
                    detail=(
                        "Validation command saved; enable validation to run it immediately after create."
                        if validation_command
                        else "No validation command is defined for this preset."
                    ),
                    command=validation_command,
                )
            )

        validation_failed = validation is not None and not self._command_ok(validation)
        if validation_failed and request.max_repair_attempts > 0:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="blocked" if validation and not validation.allowed else "planned",
                    detail=(
                        "Captured the failing validation output. The chat agent can now use this workspace, "
                        "the saved validation profile, and the error output for its auto-repair loop."
                    ),
                    command=validation_command,
                    output_excerpt=self._command_excerpt(validation) if validation else "",
                    error=(validation.summary or validation.reason) if validation else "",
                )
            )
            warnings.append(
                "Validation did not pass. Aegis captured the failure so the chat repair loop can work from real output."
            )
        elif validation is not None:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped" if self._command_ok(validation) else "planned",
                    detail=(
                        "Validation passed; no repair loop is needed."
                        if self._command_ok(validation)
                        else "Validation failed, but repair attempts are disabled for this project-builder request."
                    ),
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped",
                    detail="No validation output was produced, so no repair loop was started.",
                )
            )

        build_log_path = ""
        if apply:
            try:
                build_log_path = self._write_build_log(
                    target,
                    preset=preset,
                    project_name=project_name,
                    checkpoint=checkpoint,
                    install=install_run,
                    validation=validation,
                    install_command=install_command,
                    validation_command=validation_command,
                )
                if build_log_path:
                    stages.append(
                        ProjectBuildStage(
                            id="build-log",
                            label="Save build and validation log",
                            status="succeeded",
                            detail=f"Saved command output to {build_log_path}.",
                        )
                    )
            except OSError as exc:
                warnings.append(f"Could not write .aegis build log: {exc}")
                stages.append(
                    ProjectBuildStage(
                        id="build-log",
                        label="Save build and validation log",
                        status="failed",
                        detail="Command output was captured in memory, but the durable build log could not be written.",
                        error=str(exc),
                    )
                )

        if apply:
            memory_warnings = self._record_runtime_memory(
                target,
                preset=preset,
                project_name=project_name,
                checkpoint=checkpoint,
                install=install_run,
                validation=validation,
                install_command=install_command,
                validation_command=validation_command,
                build_log_path=build_log_path,
                prompt=prompt,
                applied=applied,
            )
            warnings.extend(memory_warnings)
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="succeeded",
                    detail=(
                        "Updated .aegis file index, command history, known-error memory, and instruction checkpoint."
                        if not memory_warnings
                        else "Project memory updated with warnings: " + "; ".join(memory_warnings[:2])
                    ),
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="skipped",
                    detail="Preview mode only; project memory files are shown in the diff but not written.",
                )
            )

        next_steps = [
            f"Open the workspace at {target}.",
            (
                f"Install dependencies with `{install_command}`."
                if install_command and not request.run_install
                else "Review dependency install output before adding the first feature."
            ),
            (
                f"Use the saved validation profile: `{validation_command}`."
                if validation_command and not request.run_validation
                else "Review captured validation output and continue the repair loop from the chat workspace."
            ),
            "Ask Auralith Prime for the first feature pass once the scaffold validates or the captured failure is repaired.",
        ]

        return ProjectScaffoldResponse(
            ok=True,
            message=(
                f"Created {preset.label} scaffold with {len(file_infos)} files."
                if apply
                else f"Previewed {preset.label} scaffold with {len(file_infos)} planned files."
            ),
            execution_mode="scaffold",
            primary_action="create_or_update_files",
            target_path=str(target),
            preset=preset,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            diff_summary=diff_summary,
            memory_paths=memory_paths,
            files=file_infos,
            file_change_count=len(file_infos),
            applied=applied,
            warnings=warnings,
            checkpoint=checkpoint,
            install_command=install_command,
            validation_command=validation_command,
            roadmap_path=".aegis/ROADMAP.md" if request.create_roadmap else "",
            build_log_path=build_log_path,
            stages=stages,
            validation=validation,
            next_steps=next_steps,
            workspace_files=self.workspace.scan(target, max_files=160) if target.exists() else [],
        )

    def _normalize_scaffold_request_from_prompt(self, request: ProjectScaffoldRequest) -> ProjectScaffoldRequest:
        prompt = " ".join(request.prompt.split())
        if not prompt:
            return request

        default_preset = ProjectScaffoldRequest.model_fields["preset_id"].default
        default_name = ProjectScaffoldRequest.model_fields["project_name"].default
        looks_unplanned = (
            request.preset_id == default_preset
            and request.project_name == default_name
            and not request.install_command.strip()
            and not request.validation_command.strip()
        )
        if not looks_unplanned:
            return request

        plan = self.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=prompt,
                preferred_target_path=request.target_path,
            )
        )
        planned = plan.scaffold_request
        return planned.model_copy(
            update={
                "target_path": request.target_path or planned.target_path,
                "prompt": request.prompt,
                "overwrite": request.overwrite or planned.overwrite,
                "include_gitignore": request.include_gitignore,
                "create_roadmap": request.create_roadmap,
                "run_install": request.run_install,
                "run_validation": request.run_validation or planned.run_validation,
                "max_repair_attempts": request.max_repair_attempts,
            }
        )

    def _existing_project_validation_response(
        self,
        request: ProjectScaffoldRequest,
        *,
        apply: bool,
        target: Path,
        preset: ProjectScaffoldPreset,
        project_name: str,
        install_command: str,
        validation_command: str,
        existing_files: list[WorkspaceFile],
        existing_profile: WorkspaceDependencyProfile,
        plan_steps: list[str],
        stages: list[ProjectBuildStage],
    ) -> ProjectScaffoldResponse:
        validation_command = self._existing_project_validation_command(
            target,
            existing_profile,
            validation_command,
        )
        warnings = [
            "Existing project mode: Aegis skipped starter-file generation and focused on the current workspace validation state."
        ]
        risk_warnings = self._risk_warnings_for_target(target, overwrite=request.overwrite)
        stages.append(
            ProjectBuildStage(
                id="structure",
                label="Skip scaffold generation",
                status="skipped",
                detail="The target already looks like a project and the prompt asked to build, validate, or repair it.",
            )
        )
        stages.append(
            ProjectBuildStage(
                id="diff",
                label="Prepare file diff preview",
                status="succeeded",
                detail="No starter files are planned for this existing-project pass.",
            )
        )
        stages.append(
            ProjectBuildStage(
                id="apply",
                label="Write files with checkpoint",
                status="skipped",
                detail="No file changes were needed before validation.",
            )
        )

        validation: CommandRun | None = None
        if apply and validation_command:
            self.validation.save_profile(
                target,
                command=validation_command,
                label=f"{preset.label} validation",
                source="project_builder_existing",
                notes="Existing project build/fix pass; no starter scaffold files were generated.",
            )

        stages.append(
            ProjectBuildStage(
                id="install",
                label="Install dependencies",
                status="skipped" if install_command else "planned",
                detail=(
                    "Install command captured but not run automatically for an existing project build/fix pass."
                    if install_command
                    else "No install command is defined for this project."
                ),
                command=install_command,
            )
        )

        if apply and request.run_validation and validation_command:
            validation_stage, validation = self._run_command_stage(
                stage_id="validate",
                label="Run existing project validation",
                command=validation_command,
                target=target,
            )
            stages.append(validation_stage)
        else:
            stages.append(
                ProjectBuildStage(
                    id="validate",
                    label="Run existing project validation",
                    status="skipped" if validation_command else "planned",
                    detail=(
                        "Validation command saved; enable validation to run it immediately."
                        if validation_command
                        else "No validation command could be inferred for this existing project."
                    ),
                    command=validation_command,
                )
            )

        if validation is not None and not self._command_ok(validation):
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="blocked" if not validation.allowed else "planned",
                    detail="Captured validation output for the chat repair loop without creating starter files.",
                    command=validation_command,
                    output_excerpt=self._command_excerpt(validation),
                    error=validation.summary or validation.reason,
                )
            )
            warnings.append("Validation did not pass. Aegis captured the failure for the repair loop.")
        elif validation is not None:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped",
                    detail="Validation passed; no repair loop is needed.",
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="repair",
                    label="Repair loop handoff",
                    status="skipped",
                    detail="No validation output was produced.",
                )
            )

        build_log_path = ""
        if apply:
            try:
                build_log_path = self._write_build_log(
                    target,
                    preset=preset,
                    project_name=project_name,
                    checkpoint=None,
                    install=None,
                    validation=validation,
                    install_command=install_command,
                    validation_command=validation_command,
                )
                if build_log_path:
                    stages.append(
                        ProjectBuildStage(
                            id="build-log",
                            label="Save build and validation log",
                            status="succeeded",
                            detail=f"Saved command output to {build_log_path}.",
                        )
                    )
            except OSError as exc:
                warnings.append(f"Could not write .aegis build log: {exc}")
                stages.append(
                    ProjectBuildStage(
                        id="build-log",
                        label="Save build and validation log",
                        status="failed",
                        detail="Command output was captured in memory, but the durable build log could not be written.",
                        error=str(exc),
                    )
                )

            memory_warnings = self._record_runtime_memory(
                target,
                preset=preset,
                project_name=project_name,
                checkpoint=None,
                install=None,
                validation=validation,
                install_command=install_command,
                validation_command=validation_command,
                build_log_path=build_log_path,
                prompt=request.prompt,
                applied=[],
            )
            warnings.extend(memory_warnings)
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="succeeded",
                    detail=(
                        "Updated .aegis file index, command history, known-error memory, and instruction checkpoint."
                        if not memory_warnings
                        else "Project memory updated with warnings: " + "; ".join(memory_warnings[:2])
                    ),
                )
            )
        else:
            stages.append(
                ProjectBuildStage(
                    id="memory",
                    label="Update project memory",
                    status="skipped",
                    detail="Preview mode only; project memory was not written.",
                )
            )

        next_steps = [
            f"Open the workspace at {target}.",
            (
                "Validation passed; continue with the next project task."
                if validation is not None and self._command_ok(validation)
                else "Review captured validation output and continue the repair loop from the chat workspace."
            ),
            "Ask Auralith Prime to continue from the saved .aegis command history and known-error memory.",
        ]

        return ProjectScaffoldResponse(
            ok=True,
            message=(
                "Validated existing project without generating starter files."
                if apply
                else "Previewed existing project validation pass without starter-file generation."
            ),
            execution_mode="existing_validation",
            primary_action="validate_existing_project",
            target_path=str(target),
            preset=preset,
            plan_steps=plan_steps,
            risk_warnings=risk_warnings,
            diff_summary=[],
            memory_paths=[],
            files=[],
            file_change_count=0,
            applied=[],
            warnings=warnings,
            checkpoint=None,
            install_command=install_command,
            validation_command=validation_command,
            roadmap_path="",
            build_log_path=build_log_path,
            stages=stages,
            validation=validation,
            next_steps=next_steps,
            workspace_files=self.workspace.scan(target, max_files=160) if target.exists() else existing_files,
        )

    @classmethod
    def _preset_for(cls, preset_id: str) -> ProjectScaffoldPreset:
        normalized = (preset_id or "").strip()
        for preset in cls.presets():
            if preset.id == normalized:
                return preset
        raise ValueError(f"unknown project scaffold preset: {preset_id}")

    @classmethod
    def _template_for(cls, preset_id: str) -> TemplateBuilder:
        return getattr(cls, template_method_name(preset_id))

    @classmethod
    def _specialize_template_for_prompt(
        cls,
        preset_id: str,
        project_name: str,
        prompt: str,
        files: dict[str, str],
    ) -> dict[str, str]:
        specialized = dict(files)
        if preset_id == "nextjs-ts-tailwind":
            specialized["components/app-shell.tsx"] = cls._nextjs_app_shell(project_name, prompt)
        elif preset_id == "vite-react-ts":
            specialized["src/App.tsx"] = cls._vite_app(project_name, prompt)
            specialized["src/styles.css"] = cls._vite_styles()
        elif preset_id == "static-html-site":
            specialized["index.html"] = cls._static_html_index(project_name, prompt)
        return specialized

    @staticmethod
    def _web_copy_profile(project_name: str, prompt: str) -> dict[str, object]:
        title = _title_from_name(project_name)
        text = f"{project_name} {prompt}".lower()

        if any(term in text for term in ("barber", "barbershop", "haircut", "fade", "beard", "shave")):
            brand = title.replace(" Website", "").replace(" Site", "").strip() or title
            return {
                "brand": brand,
                "eyebrow": "Neighborhood barber studio",
                "headline": f"{brand} keeps every cut sharp, calm, and appointment-ready.",
                "subhead": "A full-service barber site with booking calls to action, service cards, trust signals, hours, and a polished first screen ready for real content.",
                "primaryCta": "Book a chair",
                "secondaryCta": "View services",
                "stats": [
                    {"value": "30 min", "label": "Average cut window"},
                    {"value": "4.9", "label": "Client rating target"},
                    {"value": "6", "label": "Signature services"},
                ],
                "services": [
                    {"name": "Precision Cut", "detail": "Consultation, clipper work, scissor finish, and style check.", "price": "$32+"},
                    {"name": "Skin Fade", "detail": "Tight blend, clean neckline, and camera-ready finish.", "price": "$38+"},
                    {"name": "Beard Shape", "detail": "Line-up, sculpting, warm towel prep, and conditioning.", "price": "$24+"},
                    {"name": "Hot Towel Shave", "detail": "Classic straight-razor service with calm premium care.", "price": "$36+"},
                ],
                "process": [
                    "Choose a service and preferred time.",
                    "Confirm cut notes, beard goals, or photo reference.",
                    "Leave with aftercare tips and an easy rebook path.",
                ],
                "spotlight": "Built for a local shop that needs quick booking, clear services, and a premium but grounded brand presence.",
                "hours": ["Tue-Fri 9:00 AM - 7:00 PM", "Sat 9:00 AM - 4:00 PM", "Sun-Mon by request"],
            }

        if any(term in text for term in ("restaurant", "cafe", "coffee", "food", "menu", "bakery")):
            return {
                "brand": title,
                "eyebrow": "Hospitality website",
                "headline": f"{title} turns menu browsing into a smooth reservation path.",
                "subhead": "A responsive first pass for a venue with menu highlights, booking calls to action, location details, and daily feature content.",
                "primaryCta": "Reserve a table",
                "secondaryCta": "Explore menu",
                "stats": [
                    {"value": "12", "label": "Featured dishes"},
                    {"value": "3", "label": "Service windows"},
                    {"value": "24h", "label": "Booking response"},
                ],
                "services": [
                    {"name": "Seasonal Menu", "detail": "Rotating plates with clear categories and dietary notes.", "price": "Updated weekly"},
                    {"name": "Private Events", "detail": "Request flow for small gatherings and catered experiences.", "price": "Custom"},
                    {"name": "Online Ordering", "detail": "Simple pickup journey with featured specials.", "price": "Ready"},
                    {"name": "Gift Cards", "detail": "Prominent secondary revenue path for loyal guests.", "price": "Any amount"},
                ],
                "process": ["Browse menu highlights.", "Pick pickup, dine-in, or event inquiry.", "Confirm details and collect guest info."],
                "spotlight": "Built for a venue that needs strong visual rhythm, clear conversion paths, and simple content updates.",
                "hours": ["Lunch Tue-Sat", "Dinner Thu-Sun", "Events by inquiry"],
            }

        return {
            "brand": title,
            "eyebrow": "Aegis production scaffold",
            "headline": f"{title} is ready for a real first product pass.",
            "subhead": "A structured app starter with responsive sections, concrete calls to action, validation metadata, and enough surface area for the agent to continue building instead of stopping at a placeholder.",
            "primaryCta": "Start workflow",
            "secondaryCta": "Review roadmap",
            "stats": [
                {"value": "6+", "label": "Core sections"},
                {"value": "1", "label": "Validation profile"},
                {"value": "100%", "label": "Checkpointed writes"},
            ],
            "services": [
                {"name": "Workspace Dashboard", "detail": "Primary screen for status, activity, and next actions.", "price": "Ready"},
                {"name": "Data Model", "detail": "Clear room for entities, relationships, and persistence.", "price": "Planned"},
                {"name": "User Flow", "detail": "A first conversion path that can be made real in the next pass.", "price": "Next"},
                {"name": "Quality Loop", "detail": "Validation, repair, and project memory are wired from the start.", "price": "Active"},
            ],
            "process": ["Inspect the generated structure.", "Install dependencies.", "Run validation and continue the feature pass."],
            "spotlight": "Built to give Aegis enough real project shape to continue autonomously with code, tests, and refinements.",
            "hours": ["Build", "Validate", "Repair"],
        }

    @classmethod
    def _static_html_index(cls, project_name: str, prompt: str) -> str:
        profile = cls._web_copy_profile(project_name, prompt)

        def esc(value: object) -> str:
            return (
                str(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        brand = esc(profile["brand"])
        eyebrow = esc(profile["eyebrow"])
        headline = esc(profile["headline"])
        subhead = esc(profile["subhead"])
        primary_cta = esc(profile["primaryCta"])
        secondary_cta = esc(profile["secondaryCta"])
        spotlight = esc(profile["spotlight"])
        services = profile["services"] if isinstance(profile["services"], list) else []
        process = profile["process"] if isinstance(profile["process"], list) else []
        hours = profile["hours"] if isinstance(profile["hours"], list) else []
        stats = profile["stats"] if isinstance(profile["stats"], list) else []

        service_cards = "\n".join(
            _strip(
                f"""
                <article class="card">
                  <span class="card-kicker">{esc(service.get("price", "Ready"))}</span>
                  <h3>{esc(service.get("name", "Service"))}</h3>
                  <p>{esc(service.get("detail", "Ready to customize."))}</p>
                </article>
                """
            )
            for service in services[:4]
            if isinstance(service, dict)
        )
        feature_items = "\n".join(
            _strip(
                f"""
                <div>
                  <strong>Step {index}</strong>
                  <span>{esc(step)}</span>
                </div>
                """
            )
            for index, step in enumerate(process[:3], start=1)
        )
        stat_items = "\n".join(
            _strip(
                f"""
                <div class="hero-stat">
                  <strong>{esc(stat.get("value", "Ready"))}</strong>
                  <span>{esc(stat.get("label", "Project signal"))}</span>
                </div>
                """
            )
            for stat in stats[:3]
            if isinstance(stat, dict)
        )
        hour_items = "\n".join(f"<span>{esc(item)}</span>" for item in hours[:3])

        return _strip(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <meta name="description" content="{brand} responsive business website generated by Aegis." />
                <title>{brand}</title>
                <link rel="stylesheet" href="styles.css" />
              </head>
              <body>
                <header class="site-header">
                  <a class="brand" href="#top" aria-label="{brand} home">{brand}</a>
                  <nav class="nav" aria-label="Primary navigation">
                    <a href="#services">Services</a>
                    <a href="#work">Work</a>
                    <a href="#booking">Booking</a>
                    <a href="#contact">Contact</a>
                  </nav>
                </header>

                <main id="top">
                  <section class="hero section">
                    <div class="hero-copy">
                      <p class="eyebrow">{eyebrow}</p>
                      <h1>{headline}</h1>
                      <p class="lead">{subhead}</p>
                      <div class="hero-actions" aria-label="Primary actions">
                        <a class="button primary" href="#booking">{primary_cta}</a>
                        <a class="button secondary" href="#services">{secondary_cta}</a>
                      </div>
                    </div>
                    <div class="hero-panel" aria-label="Featured business highlights">
                      <span>Project focus</span>
                      <strong>{brand}</strong>
                      <p>{spotlight}</p>
                      <div class="hero-stats">{stat_items}</div>
                    </div>
                  </section>

                  <section id="services" class="section">
                    <div class="section-heading">
                      <p class="eyebrow">Services</p>
                      <h2>Clear offers, quick decisions, and a direct action path.</h2>
                    </div>
                    <div class="card-grid">
                      {service_cards}
                    </div>
                  </section>

                  <section id="work" class="section split">
                    <div>
                      <p class="eyebrow">Experience</p>
                      <h2>A focused site structure Aegis can keep expanding.</h2>
                    </div>
                    <div class="feature-list">
                      {feature_items}
                    </div>
                  </section>

                  <section id="booking" class="section booking">
                    <div class="section-heading">
                      <p class="eyebrow">Booking</p>
                      <h2>Capture the first customer action.</h2>
                    </div>
                    <form class="booking-form" data-booking-form>
                      <label>
                        Name
                        <input name="name" type="text" autocomplete="name" required />
                      </label>
                      <label>
                        Service
                        <select name="service" required>
                          <option value="">Choose a service</option>
                          <option>Signature Service</option>
                          <option>Express Option</option>
                          <option>Custom Session</option>
                        </select>
                      </label>
                      <label>
                        Preferred date
                        <input name="date" type="date" required />
                      </label>
                      <button class="button primary" type="submit">{primary_cta}</button>
                      <p class="form-status" data-form-status role="status" aria-live="polite"></p>
                    </form>
                  </section>
                </main>

                <footer id="contact" class="site-footer">
                  <div>
                    <strong>{brand}</strong>
                    <span>{hour_items}</span>
                  </div>
                  <a class="button secondary" href="mailto:hello@example.com">hello@example.com</a>
                </footer>

                <script src="scripts.js"></script>
              </body>
            </html>
            """
        )

    @classmethod
    def _nextjs_app_shell(cls, project_name: str, prompt: str) -> str:
        profile = json.dumps(cls._web_copy_profile(project_name, prompt), indent=2)
        return _strip(
            f"""
            const profile = {profile} as const;

            export function AppShell() {{
              return (
                <main className="min-h-screen bg-[#071018] text-slate-100">
                  <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 py-5 sm:px-8 lg:px-10">
                    <nav className="flex items-center justify-between border-b border-white/10 pb-4">
                      <div>
                        <p className="text-xs uppercase tracking-normal text-emerald-300">{{profile.eyebrow}}</p>
                        <p className="mt-1 text-lg font-semibold">{{profile.brand}}</p>
                      </div>
                      <a className="rounded-md border border-white/15 px-3 py-2 text-sm text-slate-200" href="#contact">
                        Contact
                      </a>
                    </nav>

                    <header className="grid flex-1 gap-8 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
                      <div>
                        <p className="text-sm text-cyan-200">Built with Aegis Project Builder</p>
                        <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight tracking-normal sm:text-5xl lg:text-6xl">
                          {{profile.headline}}
                        </h1>
                        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">{{profile.subhead}}</p>
                        <div className="mt-7 flex flex-wrap gap-3">
                          <a className="rounded-md bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950" href="#contact">
                            {{profile.primaryCta}}
                          </a>
                          <a className="rounded-md border border-white/15 px-4 py-3 text-sm text-slate-100" href="#services">
                            {{profile.secondaryCta}}
                          </a>
                        </div>
                      </div>

                      <aside className="border border-white/10 bg-white/[0.045] p-5">
                        <p className="text-sm text-slate-300">{{profile.spotlight}}</p>
                        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                          {{profile.stats.map((stat) => (
                            <div key={{stat.label}} className="border border-white/10 bg-slate-950/60 p-4">
                              <p className="text-3xl font-semibold text-white">{{stat.value}}</p>
                              <p className="mt-2 text-sm text-slate-400">{{stat.label}}</p>
                            </div>
                          ))}}
                        </div>
                      </aside>
                    </header>

                    <section id="services" className="grid gap-4 border-t border-white/10 py-8 md:grid-cols-2 xl:grid-cols-4">
                      {{profile.services.map((service) => (
                        <article key={{service.name}} className="border border-white/10 bg-[#0d1824] p-5">
                          <div className="flex items-start justify-between gap-3">
                            <h2 className="text-lg font-semibold">{{service.name}}</h2>
                            <span className="text-sm text-emerald-300">{{service.price}}</span>
                          </div>
                          <p className="mt-4 text-sm leading-6 text-slate-300">{{service.detail}}</p>
                        </article>
                      ))}}
                    </section>

                    <section className="grid gap-5 pb-10 lg:grid-cols-[0.85fr_1.15fr]">
                      <div className="border border-white/10 bg-white/[0.04] p-5">
                        <h2 className="text-xl font-semibold">How it works</h2>
                        <ol className="mt-5 space-y-3">
                          {{profile.process.map((step, index) => (
                            <li key={{step}} className="flex gap-3 text-sm text-slate-300">
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-400 text-xs font-bold text-slate-950">
                                {{index + 1}}
                              </span>
                              <span className="pt-1">{{step}}</span>
                            </li>
                          ))}}
                        </ol>
                      </div>

                      <div id="contact" className="border border-white/10 bg-[#101b26] p-5">
                        <h2 className="text-xl font-semibold">Contact and availability</h2>
                        <div className="mt-5 grid gap-3 md:grid-cols-3">
                          {{profile.hours.map((item) => (
                            <div key={{item}} className="border border-white/10 bg-slate-950/55 p-4 text-sm text-slate-300">
                              {{item}}
                            </div>
                          ))}}
                        </div>
                        <p className="mt-5 text-sm leading-6 text-slate-300">
                          Replace this panel with live booking, maps, payment, or CRM integration in the next Aegis pass.
                        </p>
                      </div>
                    </section>
                  </section>
                </main>
              );
            }}
            """
        )

    @classmethod
    def _vite_app(cls, project_name: str, prompt: str) -> str:
        profile = json.dumps(cls._web_copy_profile(project_name, prompt), indent=2)
        return _strip(
            f"""
            const profile = {profile} as const;

            export function App() {{
              return (
                <main className="shell">
                  <nav className="topbar">
                    <div>
                      <span>{{profile.eyebrow}}</span>
                      <strong>{{profile.brand}}</strong>
                    </div>
                    <a href="#contact">{{profile.primaryCta}}</a>
                  </nav>

                  <header className="hero">
                    <p>Production starter</p>
                    <h1>{{profile.headline}}</h1>
                    <span>{{profile.subhead}}</span>
                    <div className="heroActions">
                      <a className="primary" href="#services">{{profile.secondaryCta}}</a>
                      <a className="secondary" href="#contact">Contact</a>
                    </div>
                  </header>

                  <section className="stats">
                    {{profile.stats.map((stat) => (
                      <article key={{stat.label}}>
                        <strong>{{stat.value}}</strong>
                        <span>{{stat.label}}</span>
                      </article>
                    ))}}
                  </section>

                  <section id="services" className="services">
                    {{profile.services.map((service) => (
                      <article key={{service.name}}>
                        <div>
                          <h2>{{service.name}}</h2>
                          <span>{{service.price}}</span>
                        </div>
                        <p>{{service.detail}}</p>
                      </article>
                    ))}}
                  </section>

                  <section id="contact" className="handoff">
                    <div>
                      <h2>Next build path</h2>
                      <p>{{profile.spotlight}}</p>
                    </div>
                    <ol>
                      {{profile.process.map((step) => (
                        <li key={{step}}>{{step}}</li>
                      ))}}
                    </ol>
                  </section>
                </main>
              );
            }}
            """
        )

    @staticmethod
    def _vite_styles() -> str:
        return _strip(
            """
            :root {
              color: #eef4fb;
              background: #071018;
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }

            * {
              box-sizing: border-box;
            }

            html {
              scroll-behavior: smooth;
            }

            body {
              min-width: 320px;
              min-height: 100vh;
              margin: 0;
              background:
                radial-gradient(circle at 80% 10%, rgba(39, 221, 123, 0.16), transparent 28rem),
                linear-gradient(135deg, rgba(15, 30, 45, 0.92), rgba(7, 14, 24, 0.98)),
                #071018;
            }

            a {
              color: inherit;
              text-decoration: none;
            }

            .shell {
              width: min(1180px, calc(100vw - 32px));
              margin: 0 auto;
              padding: 24px 0 48px;
            }

            .topbar,
            .hero,
            .stats article,
            .services article,
            .handoff {
              border: 1px solid rgba(255, 255, 255, 0.12);
              background: rgba(255, 255, 255, 0.045);
            }

            .topbar {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 18px;
              padding: 16px;
            }

            .topbar div,
            .topbar strong,
            .topbar span {
              display: block;
            }

            .topbar span {
              color: #7dd3fc;
              font-size: 12px;
              text-transform: uppercase;
            }

            .topbar a,
            .primary,
            .secondary {
              border-radius: 6px;
              padding: 10px 14px;
              font-size: 14px;
              font-weight: 700;
            }

            .topbar a,
            .primary {
              background: #41e08f;
              color: #071018;
            }

            .secondary {
              border: 1px solid rgba(255, 255, 255, 0.16);
            }

            .hero {
              margin-top: 16px;
              padding: clamp(28px, 7vw, 78px);
            }

            .hero p {
              margin: 0 0 16px;
              color: #7dd3fc;
              font-size: 14px;
            }

            .hero h1 {
              max-width: 920px;
              margin: 0;
              font-size: clamp(38px, 7vw, 76px);
              line-height: 1;
              letter-spacing: 0;
            }

            .hero span {
              display: block;
              max-width: 760px;
              margin-top: 22px;
              color: #c1ccd8;
              line-height: 1.65;
            }

            .heroActions {
              display: flex;
              flex-wrap: wrap;
              gap: 12px;
              margin-top: 28px;
            }

            .stats,
            .services,
            .handoff {
              display: grid;
              gap: 14px;
              margin-top: 16px;
            }

            .stats {
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .stats article,
            .services article,
            .handoff {
              padding: 20px;
            }

            .stats strong {
              display: block;
              font-size: 32px;
            }

            .stats span,
            .services p,
            .handoff p,
            .handoff li {
              color: #c1ccd8;
              line-height: 1.6;
            }

            .services {
              grid-template-columns: repeat(4, minmax(0, 1fr));
            }

            .services article div {
              display: flex;
              align-items: start;
              justify-content: space-between;
              gap: 14px;
            }

            .services h2,
            .handoff h2 {
              margin: 0;
              font-size: 20px;
            }

            .services article div span {
              color: #41e08f;
              white-space: nowrap;
            }

            .handoff {
              grid-template-columns: 0.9fr 1.1fr;
            }

            .handoff ol {
              margin: 0;
              padding-left: 22px;
            }

            @media (max-width: 900px) {
              .stats,
              .services,
              .handoff {
                grid-template-columns: 1fr;
              }
            }
            """
        )

    @staticmethod
    def _default_plan_steps(
        preset: ProjectScaffoldPreset,
        project_name: str,
        install_command: str,
        validation_command: str,
    ) -> list[str]:
        steps = [
            "Detect project intent, requested path, and target stack from the prompt.",
            "Inspect the target folder before deciding whether to update in place or create a clean child project.",
            f"Generate the {preset.label} structure for `{project_name}` with Aegis metadata.",
            "Prepare a file diff preview so the user can see creates versus updates.",
            "Apply files through a checkpointed workspace write.",
        ]
        if install_command:
            steps.append(f"Capture install command `{install_command}` for the dependency pass.")
        if validation_command:
            steps.append(f"Run or save validation command `{validation_command}` and capture stdout/stderr.")
        steps.extend(
            [
                "Record command history, file index, known errors, and project decisions under `.aegis`.",
                "Hand off failed validation output to the repair loop with a bounded retry budget.",
            ]
        )
        return steps

    @staticmethod
    def _inspection_detail(
        target: Path,
        existing_files: list[WorkspaceFile],
        profile: WorkspaceDependencyProfile,
    ) -> str:
        if not target.exists():
            return "Target folder does not exist yet; Aegis will create it as a new project workspace."
        detected: list[str] = []
        if profile.project_type:
            detected.append(profile.project_type)
        detected.extend(profile.frameworks[:3])
        detected.extend(profile.languages[:3])
        detected_text = ", ".join(dict.fromkeys(detected)) if detected else "no framework manifest detected"
        return f"Scanned {len(existing_files)} file(s); detected {detected_text}."

    @classmethod
    def _should_validate_existing_project_only(
        cls,
        prompt: str,
        target: Path,
        request: ProjectScaffoldRequest,
        profile: WorkspaceDependencyProfile,
    ) -> bool:
        if not target.exists() or not target.is_dir():
            return False
        if not request.run_validation:
            return False
        if not cls._prompt_is_existing_project_validation_intent(prompt):
            return False
        if (target / ".aegis" / "project.json").exists():
            return True
        if profile.config_files or profile.build_systems or profile.validation_commands:
            return True
        return False

    @staticmethod
    def _prompt_is_existing_project_validation_intent(prompt: str) -> bool:
        lowered = f" {' '.join(prompt.lower().split())} "
        if prompt_has_explanation_prefix(prompt):
            return False

        create_terms = (
            " create ",
            " generate ",
            " scaffold ",
            " starter ",
            " write me ",
            " make me ",
            " build me ",
            " implement ",
            " add ",
            " new project ",
            " brand new ",
            " from scratch ",
            " set up ",
            " setup ",
        )
        if any(term in lowered for term in create_terms):
            return False

        return prompt_requests_execution_validation(
            prompt,
            extra_phrases=(
                "continue",
                "continue building",
                "continue the build",
                "finish",
                "keep going",
                "make it complete",
                "make this complete",
                "make it production ready",
                "make this production ready",
                "no errors",
                "production ready",
                "repair",
                "rebuild",
            ),
        )

    @staticmethod
    def _existing_project_validation_command(
        target: Path,
        profile: WorkspaceDependencyProfile,
        preferred_command: str,
    ) -> str:
        command = preferred_command.strip()
        if command == "python build.py" and not (target / "build.py").exists():
            command = ""
        if "cmake --build build" in command.lower() and not (target / "build").exists():
            return "cmake -S . -B build && cmake --build build --config Release"
        if command:
            return command
        if (target / "build.py").exists():
            return "python build.py"
        solution_files = sorted(target.glob("*.sln"))
        if solution_files:
            return f"msbuild {solution_files[0].name} /m /p:Configuration=Release"
        if (target / "CMakeLists.txt").exists():
            if (target / "build").exists():
                return "cmake --build build --config Release"
            return "cmake -S . -B build && cmake --build build --config Release"
        if profile.validation_commands:
            return profile.validation_commands[0]
        return ""

    @classmethod
    def _continuity_preset_id(
        cls,
        *,
        prompt: str,
        target: Path,
        manifest: WorkspaceProjectManifest | None,
        profile: WorkspaceDependencyProfile,
    ) -> str:
        if not target.exists() or not cls._prompt_should_reuse_existing_project(prompt):
            return ""

        if manifest is not None and cls._is_known_preset_id(manifest.preset_id):
            return manifest.preset_id
        if manifest is not None:
            contract_preset_id = str(manifest.mission_contract.get("preset_id", "")).strip()
            if cls._is_known_preset_id(contract_preset_id):
                return contract_preset_id

        config_files = {item.lower().replace("\\", "/") for item in profile.config_files}
        build_systems = {item.lower() for item in profile.build_systems}
        frameworks = {item.lower() for item in profile.frameworks}

        if "dll/shared library" in frameworks or any(item.endswith((".dll", ".lib", ".def", ".exp")) for item in config_files):
            return "cpp-cmake-dll"

        if any(item.endswith(".sln") or item.endswith(".vcxproj") for item in config_files):
            return "cpp-msvc-console-sln"

        if "cmakelists.txt" in config_files or "cmake" in build_systems:
            if any("imgui" in item for item in config_files) or (target / "vendor" / "imgui_shim").exists():
                return "cpp-imgui-win32-dx11"
            return "cpp-cmake-cli"

        if (target / "package.json").exists():
            if "electron" in frameworks:
                return "electron-react-ts"
            if "next.js" in frameworks:
                return "nextjs-ts-tailwind"
            if "vite" in frameworks or "react" in frameworks:
                return "vite-react-ts"
            return "node-fullstack-js"

        if (target / "index.html").exists():
            return "static-html-site"

        if (target / "pyproject.toml").exists() or (target / "requirements.txt").exists():
            if "fastapi" in frameworks:
                return "fastapi-python-api"
            return "python-cli"

        return ""

    @classmethod
    def _prompt_should_reuse_existing_project(cls, prompt: str) -> bool:
        lowered = f" {' '.join(prompt.lower().split())} "
        if any(
            phrase in lowered
            for phrase in (
                " new project ",
                " brand new ",
                " from scratch ",
                " different project ",
                " separate project ",
                " separate app ",
            )
        ):
            return False

        continuation_terms = (
            "also build",
            "add",
            "and build",
            "build it",
            "build this",
            "build the project",
            "compile it",
            "continue",
            "complete it",
            "complete the project",
            "existing",
            "finish",
            "fix",
            "improve",
            "launch it",
            "launch this",
            "launch the app",
            "launch the project",
            "make better",
            "optimize",
            "repair",
            "rebuild",
            "refine",
            "run it",
            "start it",
            "start this",
            "start the app",
            "start the project",
            "execute it",
            "execute this",
            "execute the app",
            "execute the project",
            "test it",
            "update",
            "validate",
            "verify",
            "work on",
            "already made",
            "already built",
            "keep going",
            "make it complete",
            "make this complete",
            "make it production ready",
            "make this production ready",
            "production ready",
            "my dll",
            "my library",
        )
        if any(term in lowered for term in continuation_terms):
            return True
        return len(lowered.split()) <= 10

    @classmethod
    def _is_known_preset_id(cls, preset_id: str) -> bool:
        normalized = (preset_id or "").strip()
        if not normalized:
            return False
        return any(preset.id == normalized for preset in cls.presets())

    @staticmethod
    def _should_update_existing_scaffold(prompt: str, target: Path) -> bool:
        lowered = prompt.lower()
        if not target.exists():
            return False

        if any(term in lowered for term in ("overwrite", "replace existing", "replace the existing", "regenerate")):
            return True

        update_intent = any(
            term in lowered
            for term in (
                "build it",
                "build this",
                "also build",
                "and build",
                "fix",
                "launch it",
                "launch this",
                "launch the app",
                "launch the project",
                "repair",
                "rebuild",
                "continue",
                "start it",
                "start this",
                "start the app",
                "start the project",
                "execute it",
                "execute this",
                "execute the app",
                "execute the project",
                "write me",
                "create",
                "generate",
                "complete",
            )
        )
        if not update_intent:
            return False

        if (target / ".aegis" / "project.json").exists():
            return True

        readme = target / "README.md"
        try:
            readme_text = readme.read_text(encoding="utf-8", errors="replace").lower()[:16_000] if readme.exists() else ""
        except OSError:
            readme_text = ""
        if "generated by aegis" in readme_text or "aegis c++ console app" in readme_text:
            return True

        cpp_request = any(term in lowered for term in ("c++", "cpp", "cmake", "sln", "console app", "console project"))
        if cpp_request and (target / "CMakeLists.txt").exists() and (target / "src" / "main.cpp").exists():
            return True
        if any(target.glob("*.sln")) or any(target.glob("*.vcxproj")):
            return True
        if (target / "CMakeLists.txt").exists():
            return True

        web_request = any(term in lowered for term in ("website", "web app", "landing page", "site"))
        if web_request and any((target / name).exists() for name in ("index.html", "app/page.tsx", "package.json")):
            return True

        return False

    @staticmethod
    def _prompt_requests_validation(prompt: str) -> bool:
        extra_terms = (
            "also build",
            "and build",
            "build this",
            "build the project",
            "continue",
            "continue building",
            "continue the build",
            "finish",
            "keep going",
            "make it complete",
            "make this complete",
            "make it production ready",
            "make this production ready",
            "production ready",
            "tests",
            "with tests",
            "include tests",
            "including tests",
            "and tests",
            "and validation",
            "with validation",
            "include validation",
            "including validation",
            "no errors",
            "ensure there are no errors",
        )
        return prompt_requests_execution_validation(prompt, extra_phrases=extra_terms)

    @staticmethod
    def _prompt_negates_web_stack(prompt: str) -> bool:
        normalized = re.sub(r"[^a-z0-9'\s]+", " ", prompt.lower())
        lowered = f" {' '.join(normalized.split())} "
        negated_phrases = (
            " without turning it into a website ",
            " without turning into a website ",
            " without turning this into a website ",
            " without converting it to a website ",
            " without converting into a website ",
            " without converting this to a website ",
            " without converting it into a website ",
            " without converting this into a website ",
            " without making a website ",
            " without making it a website ",
            " without making this a website ",
            " without making it into a website ",
            " without making this into a website ",
            " do not turn it into a website ",
            " do not convert it to a website ",
            " do not convert it into a website ",
            " do not make a website ",
            " do not make a web app ",
            " do not make this a web app ",
            " don't turn it into a website ",
            " don't convert it to a website ",
            " don't convert it into a website ",
            " don't make a website ",
            " don't make a web app ",
            " don't make this a web app ",
            " dont turn it into a website ",
            " dont convert it to a website ",
            " dont convert it into a website ",
            " dont make a website ",
            " dont make a web app ",
            " dont make this a web app ",
            " do not make it a website ",
            " do not make this a website ",
            " do not make it into a website ",
            " do not make this into a website ",
            " don't make it a website ",
            " don't make this a website ",
            " don't make it into a website ",
            " don't make this into a website ",
            " dont make it a website ",
            " dont make this a website ",
            " dont make it into a website ",
            " dont make this into a website ",
            " not a website ",
            " not a web app ",
            " not web app ",
            " no website ",
            " no web app ",
            " not web ",
            " instead of a website ",
        )
        return any(phrase in lowered for phrase in negated_phrases)

    @staticmethod
    def _preset_stack_locks(preset_id: str) -> set[str]:
        native_cpp = {
            "cpp-cmake-cli",
            "cpp-cmake-dll",
            "cpp-imgui-win32-dx11",
            "cpp-game-loop-cmake",
            "cpp-msvc-console-sln",
            "cpp-windows-service",
            "cpp-windows-internals-hooking",
            "windows-kernel-driver-controller",
        }
        web = {
            "nextjs-ts-tailwind",
            "vite-react-ts",
            "static-html-site",
            "node-fullstack-js",
            "express-ts-api",
            "node-http-api-js",
            "browser-extension-mv3",
            "vscode-extension-js",
        }
        python = {
            "python-cli",
            "python-tkinter-desktop",
            "python-stdlib-api",
            "fastapi-python-api",
            "django-python-web",
            "sqlite-python-db",
            "python-game-file-analyzer",
            "python-sln-refactor-tool",
        }
        desktop = {
            "electron-react-ts",
            "tauri-react-ts",
            "python-tkinter-desktop",
            "dotnet-wpf-csharp",
            "cpp-imgui-win32-dx11",
        }
        locks: set[str] = set()
        if preset_id in native_cpp:
            locks.add("stack-lock:native-cpp")
        if preset_id == "cpp-cmake-dll":
            locks.add("stack-lock:native-library")
        if preset_id == "windows-kernel-driver-controller":
            locks.add("stack-lock:windows-driver")
        if preset_id == "cpp-imgui-win32-dx11":
            locks.add("stack-lock:imgui-win32")
        if preset_id == "python-sln-refactor-tool":
            locks.add("stack-lock:solution-refactor")
            locks.add("stack-lock:native-cpp")
        if preset_id in desktop:
            locks.add("stack-lock:desktop")
        if preset_id in web:
            locks.add("stack-lock:web")
            if preset_id in {"nextjs-ts-tailwind", "vite-react-ts"}:
                locks.add("stack-lock:web-framework")
        if preset_id in python:
            locks.add("stack-lock:python")
        if preset_id == "rust-cli":
            locks.add("stack-lock:rust")
        if preset_id == "go-http-api":
            locks.add("stack-lock:go")
        if preset_id.startswith("dotnet-"):
            locks.add("stack-lock:dotnet")
        return locks

    @classmethod
    def _stack_locks_conflict_with_preset(cls, stack_locks: list[str], preset_id: str) -> bool:
        requested = set(stack_locks)
        if not requested:
            return False

        preset_locks = cls._preset_stack_locks(preset_id)
        if requested.issubset(preset_locks):
            return False

        specific_locks = {
            "stack-lock:native-library",
            "stack-lock:windows-driver",
            "stack-lock:imgui-win32",
            "stack-lock:solution-refactor",
        }
        if any(lock in requested and lock not in preset_locks for lock in specific_locks):
            return True

        requested_families: set[str] = set()
        if requested & {"stack-lock:native-cpp", "stack-lock:native-library", "stack-lock:windows-driver", "stack-lock:imgui-win32"}:
            requested_families.add("native")
        if "stack-lock:desktop" in requested:
            requested_families.add("desktop")
        if "stack-lock:solution-refactor" in requested:
            requested_families.add("solution-refactor")
        if requested & {"stack-lock:web", "stack-lock:web-framework"}:
            requested_families.add("web")
        if "stack-lock:python" in requested:
            requested_families.add("python")
        if "stack-lock:rust" in requested:
            requested_families.add("rust")
        if "stack-lock:go" in requested:
            requested_families.add("go")
        if "stack-lock:dotnet" in requested:
            requested_families.add("dotnet")

        preset_families: set[str] = set()
        if preset_locks & {"stack-lock:native-cpp", "stack-lock:native-library", "stack-lock:windows-driver", "stack-lock:imgui-win32"}:
            preset_families.add("native")
        if "stack-lock:desktop" in preset_locks:
            preset_families.add("desktop")
        if "stack-lock:solution-refactor" in preset_locks:
            preset_families.add("solution-refactor")
        if preset_locks & {"stack-lock:web", "stack-lock:web-framework"}:
            preset_families.add("web")
        if "stack-lock:python" in preset_locks:
            preset_families.add("python")
        if "stack-lock:rust" in preset_locks:
            preset_families.add("rust")
        if "stack-lock:go" in preset_locks:
            preset_families.add("go")
        if "stack-lock:dotnet" in preset_locks:
            preset_families.add("dotnet")

        return bool(requested_families and preset_families and requested_families.isdisjoint(preset_families))

    @classmethod
    def _prompt_allows_stack_switch(cls, prompt: str, stack_locks: list[str]) -> bool:
        if not stack_locks:
            return False

        lowered = f" {' '.join(prompt.lower().split())} "
        stack_switch_phrases = (
            " brand new ",
            " convert ",
            " convert it ",
            " convert this ",
            " different project ",
            " from scratch ",
            " migrate ",
            " new project ",
            " rebuild as ",
            " replace it with ",
            " replace this with ",
            " rewrite as ",
            " separate app ",
            " separate project ",
            " start over ",
            " turn it into ",
            " turn this into ",
        )
        if any(phrase in lowered for phrase in stack_switch_phrases):
            return True

        explicit_create_phrases = (
            " build a ",
            " build an ",
            " create a ",
            " create an ",
            " generate a ",
            " generate an ",
            " make a ",
            " make an ",
            " scaffold a ",
            " scaffold an ",
            " set up a ",
            " set up an ",
            " setup a ",
            " setup an ",
        )
        if any(phrase in lowered for phrase in explicit_create_phrases):
            return bool(
                set(stack_locks)
                & {
                    "stack-lock:native-cpp",
                    "stack-lock:native-library",
                    "stack-lock:windows-driver",
                    "stack-lock:imgui-win32",
                    "stack-lock:solution-refactor",
                    "stack-lock:web",
                    "stack-lock:web-framework",
                    "stack-lock:python",
                    "stack-lock:rust",
                    "stack-lock:go",
                    "stack-lock:dotnet",
                }
            )
        return False

    @classmethod
    def _stack_family_for_preset(cls, preset_id: str) -> str:
        locks = cls._preset_stack_locks(preset_id)
        if "stack-lock:solution-refactor" in locks:
            return "solution-refactor"
        if "stack-lock:desktop" in locks:
            return "desktop"
        if locks & {"stack-lock:native-cpp", "stack-lock:native-library", "stack-lock:windows-driver", "stack-lock:imgui-win32"}:
            return "native"
        if locks & {"stack-lock:web", "stack-lock:web-framework"}:
            return "web"
        if "stack-lock:python" in locks:
            return "python"
        if "stack-lock:rust" in locks:
            return "rust"
        if "stack-lock:go" in locks:
            return "go"
        if "stack-lock:dotnet" in locks:
            return "dotnet"
        return "general"

    @staticmethod
    def _stack_lock_keywords_for_prompt(prompt: str) -> list[str]:
        lowered = f" {' '.join(prompt.lower().split())} "
        web_negated = ProjectScaffolder._prompt_negates_web_stack(prompt)
        locks: list[str] = []

        def add(condition: bool, label: str) -> None:
            if condition and label not in locks:
                locks.append(label)

        add(
            any(term in lowered for term in (" c++ ", " cpp ", " cmake ", " visual studio ", " sln ", " vcxproj ")),
            "stack-lock:native-cpp",
        )
        add(
            any(term in lowered for term in (" merge ", " combine ", " split ", " separate ", " extract "))
            and any(term in lowered for term in (" sln ", " solution ", " solutions ", " vcxproj ", " visual studio ")),
            "stack-lock:solution-refactor",
        )
        add(any(term in lowered for term in (" kernel ", " driver ", " wdk ")), "stack-lock:windows-driver")
        add(any(term in lowered for term in (" dll ", " shared library ", " dynamic library ")), "stack-lock:native-library")
        add(any(term in lowered for term in (" imgui ", " directx ", " dx11 ", " win32 ")), "stack-lock:imgui-win32")
        add(
            any(
                term in lowered
                for term in (
                    " desktop ",
                    " desktop app ",
                    " desktop application ",
                    " gui ",
                    " gui app ",
                    " electron ",
                    " tauri ",
                    " tkinter ",
                    " wpf ",
                    " winforms ",
                    " xaml ",
                    " imgui ",
                )
            ),
            "stack-lock:desktop",
        )
        add(any(term in lowered for term in (" python ", " pyproject ", " fastapi ", " django ", " flask ")), "stack-lock:python")
        add(any(term in lowered for term in (" rust ", " cargo ")), "stack-lock:rust")
        add(any(term in lowered for term in (" golang ", " go.mod ", " go api ", " go cli ")), "stack-lock:go")
        add(any(term in lowered for term in (" c# ", " dotnet ", " .net ", " wpf ", " winforms ")), "stack-lock:dotnet")
        add(
            not web_negated
            and any(term in lowered for term in (" website ", " web app ", " landing page ", " frontend ", " frontend-style ", " dashboard ")),
            "stack-lock:web",
        )
        add(
            not web_negated and any(term in lowered for term in (" next.js ", " nextjs ", " vite ", " react ")),
            "stack-lock:web-framework",
        )
        return locks

    @staticmethod
    def _risk_warnings_for_target(target: Path, *, overwrite: bool) -> list[str]:
        warnings: list[str] = []
        if target.exists():
            visible = []
            try:
                visible = [entry for entry in target.iterdir() if entry.name != ".aegis"]
            except OSError:
                visible = []
            if visible and not overwrite:
                warnings.append(
                    "Target folder is not empty; Aegis will avoid overwriting existing visible files and may create a child project."
                )
            elif visible and overwrite:
                warnings.append(
                    "Overwrite is enabled for scaffold-owned paths; unrelated user files still remain protected."
                )
        else:
            warnings.append("Target folder will be created inside an allowed workspace root.")
        return warnings

    @classmethod
    def _project_memory_files(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
        plan_steps: list[str],
        risk_warnings: list[str],
        existing_files: list[WorkspaceFile],
        existing_profile: WorkspaceDependencyProfile,
        planned_files: dict[str, str],
    ) -> dict[str, str]:
        generated_paths = sorted(planned_files)
        memory_paths = [
            ".aegis/command_history.json",
            ".aegis/decisions.md",
            ".aegis/file_index.json",
            ".aegis/known_errors.json",
            ".aegis/validation_plan.json",
        ]
        indexed_paths = sorted({*generated_paths, *memory_paths})
        file_index = {
            "schema": "aegis.file_index.v1",
            "updated_at": utc_now(),
            "project_name": project_name,
            "preset_id": preset.id,
            "preset_label": preset.label,
            "generated_file_count": len(indexed_paths),
            "generated_files": [
                {
                    "path": path,
                    "kind": "text",
                    "size": len(planned_files.get(path, "").encode("utf-8")),
                    "source": "project_builder",
                }
                for path in indexed_paths
            ],
            "existing_workspace_snapshot": {
                "file_count": len(existing_files),
                "files": [file.model_dump() for file in existing_files[:80]],
            },
            "detected_profile": existing_profile.model_dump(),
        }
        command_history = {
            "schema": "aegis.command_history.v1",
            "updated_at": utc_now(),
            "commands": [
                {
                    "kind": "install",
                    "command": install_command,
                    "status": "planned" if install_command else "not-configured",
                    "source": "project_builder",
                },
                {
                    "kind": "validation",
                    "command": validation_command,
                    "status": "planned" if validation_command else "not-configured",
                    "source": "project_builder",
                },
            ],
        }
        known_errors = {
            "schema": "aegis.known_errors.v1",
            "updated_at": utc_now(),
            "errors": [],
        }
        validation_plan = cls._validation_plan_payload(
            preset,
            project_name,
            install_command=install_command,
            validation_command=validation_command,
            validation=None,
            build_log_path="",
        )
        decisions = _strip(
            f"""
            # Aegis Project Decisions

            Project: {_title_from_name(project_name)}
            Preset: {preset.label}
            Created: {utc_now()}

            ## Original Request

            {prompt or "No prompt was attached to this project-builder request."}

            ## Plan

            {cls._markdown_list(plan_steps)}

            ## Risk Notes

            {cls._markdown_list(risk_warnings or ["No special risk notes were detected for this scaffold pass."])}

            ## Commands

            - Install: {install_command or "not configured"}
            - Validate: {validation_command or "not configured"}

            ## Working Agreement

            - Use checkpointed changes before modifying generated files.
            - Record build/test failures in `.aegis/known_errors.json`.
            - Prefer small repair passes that rerun the failing command.
            - Keep user-created files outside generated scaffold paths untouched.
            """
        )
        return {
            ".aegis/command_history.json": json.dumps(command_history, indent=2) + "\n",
            ".aegis/decisions.md": decisions,
            ".aegis/file_index.json": json.dumps(file_index, indent=2) + "\n",
            ".aegis/known_errors.json": json.dumps(known_errors, indent=2) + "\n",
            ".aegis/validation_plan.json": json.dumps(validation_plan, indent=2) + "\n",
        }

    @staticmethod
    def _diff_summary(files: list[ProjectScaffoldFile]) -> list[str]:
        creates = sum(1 for file in files if file.action == "create")
        updates = sum(1 for file in files if file.action == "update")
        deletes = sum(1 for file in files if file.action == "delete")
        summary: list[str] = []
        if creates:
            summary.append(f"+ {creates} create")
        if updates:
            summary.append(f"~ {updates} update")
        if deletes:
            summary.append(f"- {deletes} delete")
        return summary

    def _record_runtime_memory(
        self,
        target: Path,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
        build_log_path: str,
        prompt: str,
        applied: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        try:
            files = self.workspace.scan(target, max_files=240)
            profile = self.workspace.inspect_dependency_profile(target)
            file_index = {
                "schema": "aegis.file_index.v1",
                "updated_at": utc_now(),
                "project_name": project_name,
                "preset_id": preset.id,
                "preset_label": preset.label,
                "workspace_file_count": len(files),
                "files": [file.model_dump() for file in files],
                "detected_profile": profile.model_dump(),
            }
            self._write_json_file(target / ".aegis" / "file_index.json", file_index)
        except OSError as exc:
            warnings.append(f"Could not refresh .aegis/file_index.json: {exc}")

        try:
            history_path = target / ".aegis" / "command_history.json"
            history = self._read_json_object(history_path, default={"schema": "aegis.command_history.v1", "commands": []})
            commands = history.get("commands")
            if not isinstance(commands, list):
                commands = []
            if install is not None:
                commands.append(
                    {
                        "kind": "install",
                        "command": install.command or install_command,
                        "cwd": install.cwd,
                        "status": "passed" if self._command_ok(install) else "failed",
                        "category": install.category,
                        "summary": install.summary or install.reason,
                        "exit_code": install.exit_code,
                        "timed_out": install.timed_out,
                        "steps": install.steps,
                        "failed_step": install.failed_step,
                        "failed_step_command": install.failed_step_command,
                        "diagnostics": install.diagnostics,
                        "checkpoint": checkpoint,
                        "build_log_path": build_log_path,
                        "created_at": utc_now(),
                    }
                )
            if validation is not None:
                commands.append(
                    {
                        "kind": "validation",
                        "command": validation.command or validation_command,
                        "cwd": validation.cwd,
                        "status": "passed" if self._command_ok(validation) else "failed",
                        "category": validation.category,
                        "summary": validation.summary or validation.reason,
                        "exit_code": validation.exit_code,
                        "timed_out": validation.timed_out,
                        "steps": validation.steps,
                        "failed_step": validation.failed_step,
                        "failed_step_command": validation.failed_step_command,
                        "diagnostics": validation.diagnostics,
                        "checkpoint": checkpoint,
                        "build_log_path": build_log_path,
                        "created_at": utc_now(),
                    }
                )
            elif validation_command:
                commands.append(
                    {
                        "kind": "validation",
                        "command": validation_command,
                        "status": "saved",
                        "summary": "Validation command saved for a later build or repair pass.",
                        "checkpoint": checkpoint,
                        "created_at": utc_now(),
                    }
                )
            if install_command:
                history["install_command"] = install_command
            history["validation_command"] = validation_command
            history["updated_at"] = utc_now()
            history["commands"] = commands[-80:]
            self._write_json_file(history_path, history)
        except OSError as exc:
            warnings.append(f"Could not update .aegis/command_history.json: {exc}")

        if validation is not None and not self._command_ok(validation):
            try:
                known_path = target / ".aegis" / "known_errors.json"
                known = self._read_json_object(known_path, default={"schema": "aegis.known_errors.v1", "errors": []})
                errors = known.get("errors")
                if not isinstance(errors, list):
                    errors = []
                errors.append(
                    {
                        "signature": self._error_signature(validation),
                        "category": validation.category or "unknown",
                        "command": validation.command,
                        "summary": validation.summary or validation.reason,
                        "exit_code": validation.exit_code,
                        "failed_step": validation.failed_step,
                        "failed_step_command": validation.failed_step_command,
                        "diagnostics": validation.diagnostics,
                        "output_excerpt": self._command_excerpt(validation, limit=1400),
                        "build_log_path": build_log_path,
                        "status": "open",
                        "created_at": utc_now(),
                    }
                )
                known["updated_at"] = utc_now()
                known["errors"] = errors[-60:]
                self._write_json_file(known_path, known)
            except OSError as exc:
                warnings.append(f"Could not update .aegis/known_errors.json: {exc}")

        try:
            validation_plan = self._validation_plan_payload(
                preset,
                project_name,
                install_command=install_command,
                validation_command=validation_command,
                validation=validation,
                build_log_path=build_log_path,
            )
            self._write_json_file(target / ".aegis" / "validation_plan.json", validation_plan)
        except OSError as exc:
            warnings.append(f"Could not update .aegis/validation_plan.json: {exc}")

        try:
            instruction_files = self.workspace.discover_instruction_files(
                target,
                max_files=12,
                referenced_text=f"{prompt}\nTODO.md\nPROJECT_TODO.md\nTASKS.md\nBACKLOG.md",
            )
            if instruction_files:
                self._write_instruction_status_checkpoint(
                    target,
                    instruction_files,
                    prompt=prompt,
                    validation=validation,
                    validation_command=validation_command,
                    build_log_path=build_log_path,
                    applied=applied,
                )
        except (OSError, ValueError) as exc:
            warnings.append(f"Could not update .aegis/instruction_status.json: {exc}")
        return warnings

    def _write_instruction_status_checkpoint(
        self,
        target: Path,
        instruction_files: list[WorkspaceInstructionFile],
        *,
        prompt: str,
        validation: CommandRun | None,
        validation_command: str,
        build_log_path: str,
        applied: list[str],
    ) -> None:
        files: list[dict[str, object]] = []
        for item in instruction_files[:12]:
            files.append(
                {
                    "path": item.path,
                    "title": item.title,
                    "kind": item.kind,
                    "score": item.score,
                    "open_items": item.pending_count,
                    "completed_items": item.completed_count,
                    "total_items": item.total_items,
                    "pending_items": [
                        self._status_text(pending, limit=220)
                        for pending in item.pending_items[:10]
                        if self._status_text(pending, limit=220)
                    ],
                    "summary": item.summary,
                }
            )

        open_items = sum(item.pending_count for item in instruction_files)
        completed_items = sum(item.completed_count for item in instruction_files)
        total_items = sum(item.total_items for item in instruction_files)
        first_pending = next(
            (
                pending.strip()
                for item in instruction_files
                for pending in item.pending_items
                if pending.strip()
            ),
            "",
        )

        if validation is None:
            validation_payload: dict[str, object] = {
                "status": "saved" if validation_command else "not_run",
                "command": validation_command,
                "summary": (
                    "Validation command saved for a later build or repair pass."
                    if validation_command
                    else "No validation command was recorded for this scaffold."
                ),
                "category": "",
                "exit_code": None,
                "build_log_path": build_log_path,
                "diagnostics": [],
            }
        else:
            validation_payload = {
                "status": "passed" if self._command_ok(validation) else "failed",
                "command": validation.command or validation_command,
                "summary": validation.summary or validation.reason,
                "category": validation.category,
                "exit_code": validation.exit_code,
                "timed_out": validation.timed_out,
                "build_log_path": build_log_path,
                "failed_step": validation.failed_step,
                "failed_step_command": validation.failed_step_command,
                "diagnostics": validation.diagnostics,
            }

        validation_failed = validation is not None and not self._command_ok(validation)
        validation_passed = validation is not None and self._command_ok(validation)
        if validation_failed:
            first_diagnostic = self._diagnostics_log(validation.diagnostics).splitlines()[0].removeprefix("- ").strip()
            repair_target = (
                first_diagnostic
                if first_diagnostic and first_diagnostic != "(none captured)"
                else f"the failure from `{validation.command or validation_command}`"
            )
            completion_status = "blocked"
            completion_score = 0.2
            should_continue = True
            reasons = ["Validation failed during scaffold/build, so repair must happen before expanding scope."]
            next_actions = [
                f"Repair {repair_target}.",
                "Rerun validation after the repair.",
            ]
        elif open_items:
            completion_status = "needs_work"
            completion_score = 0.72 if validation_passed else 0.55
            should_continue = True
            reasons = ["Tracked instruction or roadmap items are still open."]
            next_actions = [
                f"Continue the next open instruction item: {self._status_text(first_pending, limit=220)}"
                if first_pending
                else "Continue the next open instruction item.",
            ]
            if validation is None and validation_command:
                next_actions.append(f"Run the saved validation command: `{validation_command}`.")
        else:
            completion_status = "ready"
            completion_score = 1.0 if validation_passed else 0.82
            should_continue = False
            reasons = ["No open instruction items were detected in the tracked files."]
            next_actions = ["Summarize the current state and propose the next milestone."]

        if validation_failed:
            first_diagnostic = self._diagnostics_log(validation.diagnostics).splitlines()[0].removeprefix("- ").strip()
            if first_diagnostic and first_diagnostic != "(none captured)":
                recommendation = f"Repair validation diagnostic: {first_diagnostic}"
            else:
                recommendation = f"Repair validation failure from `{validation.command or validation_command}` before expanding scope."
        elif open_items and first_pending:
            recommendation = f"Continue the next open instruction item: {self._status_text(first_pending, limit=220)}"
        elif open_items:
            recommendation = "Continue the next open instruction item."
        elif validation is None and validation_command:
            recommendation = f"Run the saved validation command: `{validation_command}`."
        else:
            recommendation = "All tracked instruction items are currently complete; summarize the validated state and propose the next milestone."

        payload: dict[str, object] = {
            "schema": "aegis.instruction_status.v1",
            "updated_at": utc_now(),
            "source_message": self._status_text(prompt, limit=500),
            "instruction_file_count": len(files),
            "open_items": open_items,
            "completed_items": completed_items,
            "total_items": total_items,
            "files": files,
            "last_validation": validation_payload,
            "completion": {
                "status": completion_status,
                "score": completion_score,
                "should_continue": should_continue,
                "reasons": reasons,
                "next_actions": next_actions[:6],
            },
            "applied": [self._status_text(path, limit=220) for path in applied[-40:]],
            "recommendation": recommendation,
        }
        self._write_json_file(target / ".aegis" / "instruction_status.json", payload)

    @classmethod
    def _validation_plan_payload(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        install_command: str,
        validation_command: str,
        validation: CommandRun | None,
        build_log_path: str,
    ) -> dict[str, object]:
        steps: list[dict[str, object]] = []
        if install_command:
            steps.append(
                {
                    "id": "install-1",
                    "phase": "install",
                    "command": install_command,
                    "label": "Install dependencies",
                    "required": False,
                    "source_command": install_command,
                    "chain_index": 1,
                    "chain_total": 1,
                }
            )

        validation_segments = cls._split_safe_command_chain(validation_command)
        for index, command in enumerate(validation_segments, start=1):
            phase = cls._validation_step_phase(command)
            steps.append(
                {
                    "id": f"{phase}-{index}",
                    "phase": phase,
                    "command": command,
                    "label": cls._validation_step_label(command, index=index, total=len(validation_segments)),
                    "required": True,
                    "source_command": validation_command,
                    "chain_index": index,
                    "chain_total": len(validation_segments),
                }
            )

        last_run: dict[str, object]
        if validation is None:
            last_run = {
                "status": "not_run",
                "command": validation_command,
                "summary": "Validation has not run yet.",
                "exit_code": None,
                "build_log_path": build_log_path,
                "failed_step": "",
                "failed_step_command": "",
                "diagnostics": [],
            }
        else:
            last_run = {
                "status": "passed" if validation.allowed and not validation.timed_out and validation.exit_code == 0 else "failed",
                "command": validation.command or validation_command,
                "summary": validation.summary or validation.reason,
                "category": validation.category,
                "exit_code": validation.exit_code,
                "timed_out": validation.timed_out,
                "build_log_path": build_log_path,
                "steps": validation.steps,
                "failed_step": validation.failed_step or cls._failed_chain_step(validation),
                "failed_step_command": validation.failed_step_command,
                "diagnostics": validation.diagnostics,
            }

        return {
            "schema": "aegis.validation_plan.v1",
            "updated_at": utc_now(),
            "project_name": project_name,
            "preset_id": preset.id,
            "preset_label": preset.label,
            "install_command": install_command,
            "validation_command": validation_command,
            "steps": steps,
            "last_run": last_run,
            "notes": [
                "Run validation steps in order; stop at the first failed required step.",
                "Repair the smallest failing step before expanding project scope.",
                "After a repair, rerun the same validation command or its failed segment.",
            ],
        }

    @staticmethod
    def _split_safe_command_chain(command: str) -> list[str]:
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

    @staticmethod
    def _validation_step_phase(command: str) -> str:
        lowered = command.lower()
        spaced = f" {lowered} "
        if "cmake" in lowered and " -s " in spaced:
            return "configure"
        if ("cmake" in lowered and "--build" in lowered) or "msbuild" in lowered or "dotnet build" in lowered:
            return "build"
        if any(token in lowered for token in ("npm run build", "pnpm build", "yarn build", "vite build", "cargo check")):
            return "build"
        if any(token in lowered for token in ("npm test", "pnpm test", "yarn test", "pytest", "vitest", "jest", "ctest", "cargo test", "go test")):
            return "test"
        if any(token in lowered for token in ("typecheck", "type-check", "tsc --noemit", "mypy", "pyright")):
            return "typecheck"
        if any(token in lowered for token in ("prisma", "sqlfluff", "migration", "schema")):
            return "database"
        if any(token in lowered for token in ("lint", "ruff", "eslint", "clippy")):
            return "lint"
        return "validation"

    @staticmethod
    def _validation_step_label(command: str, *, index: int, total: int) -> str:
        lowered = command.lower()
        if " -s " in f" {lowered} " and " -b " in f" {lowered} " and "cmake" in lowered:
            return "Configure CMake build directory"
        if "cmake --build" in lowered:
            return "Build CMake project"
        if lowered.startswith("ctest "):
            return "Run CTest suite"
        if "npm run build" in lowered or "pnpm build" in lowered or "yarn build" in lowered:
            return "Build web project"
        if "npm test" in lowered or "pnpm test" in lowered or "pytest" in lowered:
            return "Run test suite"
        if total > 1:
            return f"Validation step {index}"
        return "Run validation command"

    @staticmethod
    def _failed_chain_step(validation: CommandRun) -> str:
        if validation.failed_step:
            return validation.failed_step
        match = re.search(r"step\s+(\d+)", validation.reason or "", flags=re.IGNORECASE)
        return match.group(1) if match else ""

    @staticmethod
    def _failed_step_parts_from_steps(steps: list[dict[str, object]]) -> tuple[str, str]:
        for raw_step in steps:
            if raw_step.get("ok"):
                continue
            step_index = ProjectScaffolder._status_text(raw_step.get("index"), limit=20)
            command = ProjectScaffolder._status_text(raw_step.get("command"), limit=260)
            return step_index, command
        return "", ""

    @staticmethod
    def _status_text(value: object, *, default: str = "", limit: int = 220) -> str:
        if value is None:
            return default
        text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            return default
        if len(text) > limit:
            return text[: max(0, limit - 1)].rstrip() + "..."
        return text

    @staticmethod
    def _read_json_object(path: Path, *, default: dict[str, object]) -> dict[str, object]:
        if not path.exists():
            return dict(default)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return dict(default)
        return payload if isinstance(payload, dict) else dict(default)

    @staticmethod
    def _write_json_file(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_build_log(
        self,
        target: Path,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
    ) -> str:
        if install is None and validation is None:
            return ""

        timestamp = re.sub(r"[^0-9A-Za-z]+", "-", utc_now()).strip("-") or "now"
        log_name = f"{timestamp}-{uuid.uuid4().hex[:8]}.md"
        relative_path = f".aegis/build_logs/{log_name}"
        path = target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._build_log_content(
            preset=preset,
            project_name=project_name,
            checkpoint=checkpoint,
            install=install,
            validation=validation,
            install_command=install_command,
            validation_command=validation_command,
        )
        path.write_text(content, encoding="utf-8")
        return relative_path

    def _build_log_content(
        self,
        *,
        preset: ProjectScaffoldPreset,
        project_name: str,
        checkpoint: str | None,
        install: CommandRun | None,
        validation: CommandRun | None,
        install_command: str,
        validation_command: str,
    ) -> str:
        sections = [
            "# Aegis Build Log",
            "",
            f"- Created: {utc_now()}",
            f"- Project: {_title_from_name(project_name)}",
            f"- Preset: {preset.label}",
            f"- Checkpoint: {checkpoint or 'none'}",
            f"- Install command: {install_command or 'not configured'}",
            f"- Validation command: {validation_command or 'not configured'}",
            "",
        ]
        if install is not None:
            sections.append(self._command_log_section("Install", install))
        if validation is not None:
            sections.append(self._command_log_section("Validation", validation))
        return "\n".join(sections).rstrip() + "\n"

    @classmethod
    def _command_log_section(cls, title: str, run: CommandRun) -> str:
        return "\n".join(
            [
                f"## {title}",
                "",
                f"- Command: {run.command}",
                f"- CWD: {run.cwd}",
                f"- Allowed: {str(run.allowed).lower()}",
                f"- Exit code: {run.exit_code if run.exit_code is not None else 'none'}",
                f"- Timed out: {str(run.timed_out).lower()}",
                f"- Category: {run.category or 'unknown'}",
                f"- Summary: {run.summary or run.reason or 'No summary was provided.'}",
                "",
                "### Diagnostics",
                "",
                cls._diagnostics_log(run.diagnostics),
                "",
                "### Stdout",
                "",
                "```text",
                cls._log_text(run.stdout),
                "```",
                "",
                "### Stderr",
                "",
                "```text",
                cls._log_text(run.stderr),
                "```",
                "",
                "### Reason",
                "",
                "```text",
                cls._log_text(run.reason),
                "```",
                "",
            ]
        )

    @staticmethod
    def _log_text(value: str, *, limit: int = 20000) -> str:
        text = (value or "").strip()
        if not text:
            return "(empty)"
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... output truncated ..."

    @staticmethod
    def _diagnostics_log(diagnostics: list[dict[str, object]]) -> str:
        if not diagnostics:
            return "(none captured)"
        lines: list[str] = []
        for diagnostic in diagnostics[:12]:
            display = ProjectScaffolder._diagnostic_display(diagnostic)
            if display:
                lines.append(f"- {display}")
        return "\n".join(lines) if lines else "(none captured)"

    @staticmethod
    def _diagnostic_display(diagnostic: dict[str, object]) -> str:
        file = ProjectScaffolder._status_text(diagnostic.get("file"), limit=180)
        if not file:
            return ""
        line = ProjectScaffolder._status_text(diagnostic.get("line"), limit=20)
        column = ProjectScaffolder._status_text(diagnostic.get("column"), limit=20)
        location = file
        if line:
            location += f":{line}"
        if column:
            location += f":{column}"
        severity = ProjectScaffolder._status_text(diagnostic.get("severity"), limit=40)
        code = ProjectScaffolder._status_text(diagnostic.get("code"), limit=40)
        message = ProjectScaffolder._status_text(diagnostic.get("message"), limit=220)
        detail = " ".join(part for part in (severity, code) if part)
        if detail and message:
            return f"{location} {detail}: {message}"
        if detail:
            return f"{location} {detail}"
        if message:
            return f"{location}: {message}"
        return location

    @staticmethod
    def _extract_validation_diagnostics(result: CommandResult, *, limit: int = 12) -> list[dict[str, object]]:
        text = "\n".join(part for part in (result.stderr, result.stdout, result.reason) if part).strip()
        if not text:
            return []

        diagnostics: list[dict[str, object]] = []
        seen: set[tuple[str, int | None, int | None, str, str]] = set()

        def add(
            *,
            file: str,
            line: str | int | None = None,
            column: str | int | None = None,
            severity: str = "error",
            code: str = "",
            message: str = "",
            raw: str = "",
        ) -> None:
            if len(diagnostics) >= limit:
                return
            clean_file = ProjectScaffolder._normalize_diagnostic_path(file)
            if not clean_file:
                return
            line_no = ProjectScaffolder._to_positive_int(line)
            column_no = ProjectScaffolder._to_positive_int(column)
            clean_severity = (severity or "error").lower().replace("fatal error", "error")
            clean_code = ProjectScaffolder._status_text(code, limit=40)
            clean_message = ProjectScaffolder._status_text(message or raw, limit=260)
            key = (clean_file.lower(), line_no, column_no, clean_code.lower(), clean_message.lower())
            if key in seen:
                return
            seen.add(key)
            diagnostics.append(
                {
                    "file": clean_file,
                    "line": line_no,
                    "column": column_no,
                    "severity": clean_severity,
                    "code": clean_code,
                    "message": clean_message,
                    "raw": ProjectScaffolder._status_text(raw, limit=360),
                }
            )

        lines = [line.rstrip() for line in text.splitlines()]
        msvc_or_ts = re.compile(
            r"^\s*(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*"
            r"(?P<severity>fatal error|error|warning|note)\s*"
            r"(?:(?P<code>[A-Za-z]{1,8}\d{2,6})\s*:)?\s*(?P<message>.+)\s*$",
            re.IGNORECASE,
        )
        gcc_or_clang = re.compile(
            r"^\s*(?P<file>(?:[A-Za-z]:)?[^:\n]+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
            r"(?P<severity>fatal error|error|warning|note)\s*:?\s*"
            r"(?:(?P<code>[A-Za-z]{1,8}\d{2,6})\s*:)?\s*(?P<message>.+)\s*$",
            re.IGNORECASE,
        )
        python_traceback = re.compile(
            r'^\s*File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<message>.+))?\s*$',
            re.IGNORECASE,
        )

        for index, raw_line in enumerate(lines):
            line = ProjectScaffolder._strip_ansi(raw_line).strip()
            if not line:
                continue
            match = msvc_or_ts.match(line) or gcc_or_clang.match(line)
            if match:
                add(raw=line, **match.groupdict())
                continue
            match = python_traceback.match(line)
            if match:
                next_message = ""
                for followup in lines[index + 1 : index + 4]:
                    candidate = ProjectScaffolder._strip_ansi(followup).strip()
                    if candidate and not candidate.startswith("File "):
                        next_message = candidate
                        break
                groups = match.groupdict()
                add(
                    file=groups.get("file") or "",
                    line=groups.get("line"),
                    severity="error",
                    message=next_message or groups.get("message") or "Python traceback frame",
                    raw=line,
                )

        return diagnostics

    @staticmethod
    def _normalize_diagnostic_path(path: str) -> str:
        clean = ProjectScaffolder._strip_ansi(path).strip().strip("\"'")
        clean = clean.replace("\\", "/")
        clean = re.sub(r"^\./+", "", clean)
        while clean.startswith("../"):
            clean = clean[3:]
        if len(clean) > 260:
            clean = clean[-260:]
        return clean

    @staticmethod
    def _to_positive_int(value: str | int | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text or "")

    @staticmethod
    def _error_signature(validation: CommandRun) -> str:
        text = "|".join(
            [
                validation.category or "unknown",
                validation.command,
                validation.summary or validation.reason,
                ProjectScaffolder._command_excerpt(validation, limit=400),
            ]
        )
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]

    @staticmethod
    def _markdown_list(items: list[str]) -> str:
        if not items:
            return "- None"
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _roadmap_files(
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
        max_repair_attempts: int,
    ) -> dict[str, str]:
        title = _title_from_name(project_name)
        requested_goal = prompt or "No original prompt was attached to this project-builder request."
        install_line = install_command or "No install command configured."
        validation_line = validation_command or "No validation command configured."
        first_pass_items = ProjectScaffolder._first_product_pass_items(preset, prompt)
        first_pass_checklist = "\n".join(f"- [ ] {item}" for item in first_pass_items)
        return {
            ".aegis/ROADMAP.md": _strip(
                f"""
                # {title} Roadmap

                ## Original Goal

                {requested_goal}

                ## Selected Stack

                - Preset: {preset.label}
                - Framework: {preset.framework}
                - Language: {preset.language}
                - Package manager: {preset.package_manager or "manual"}

                ## Visible Build Loop

                1. Read the user goal and choose the closest supported stack.
                2. Generate the project structure and Aegis handoff metadata.
                3. Save install and validation commands into the project manifest.
                4. Write files through a checkpointed workspace operation.
                5. Run the validation command when requested and capture stdout/stderr.
                6. If validation fails, continue with up to {max_repair_attempts} repair attempt(s) in the chat agent.

                ## Commands

                Install:

                ```bash
                {install_line}
                ```

                Validate:

                ```bash
                {validation_line}
                ```

                ## First Product Pass

                {first_pass_checklist}

                ## Autopilot Rules

                - Keep every major change tied to validation output.
                - Repair build, syntax, or runtime failures before expanding scope.
                - When a checklist item is completed and validated, change only that item from [ ] to [x].
                """
            )
        }

    @staticmethod
    def _aegis_handoff_files(
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
    ) -> dict[str, str]:
        title = _title_from_name(project_name)
        first_pass_items = ProjectScaffolder._first_product_pass_items(preset, prompt)
        manifest = {
            "schema": "aegis.project.v1",
            "project_name": project_name,
            "title": title,
            "preset_id": preset.id,
            "preset_label": preset.label,
            "framework": preset.framework,
            "language": preset.language,
            "package_manager": preset.package_manager,
            "install_command": install_command,
            "validation_command": validation_command,
            "original_prompt": prompt,
            "tags": preset.tags,
            "generated_by": "Aegis Project Builder",
            "mission_contract": ProjectScaffolder._mission_contract(
                preset,
                project_name,
                prompt=prompt,
                install_command=install_command,
                validation_command=validation_command,
            ),
            "agent_handoff": {
                "primary_goal": "Turn the scaffold into a polished, working product through small checkpointed passes.",
                "first_pass": first_pass_items,
                "safety": [
                    "Do not run destructive commands without an explicit user request.",
                    "Keep generated secrets out of source control and use environment variables.",
                    "Prefer small patches with validation after each meaningful change.",
                ],
            },
        }
        tags = ", ".join(preset.tags) if preset.tags else "none"
        return {
            ".aegis/project.json": json.dumps(manifest, indent=2) + "\n",
            "AGENTS.md": _strip(
                f"""
                # Aegis Agent Handoff

                Project: {title}
                Preset: {preset.label}
                Stack: {preset.framework} / {preset.language}
                Tags: {tags}

                ## User Goal

                {prompt or "No original prompt was attached to this project-builder request."}

                ## Commands

                Install dependencies:

                ```bash
                {install_command or "Add an install command for this stack."}
                ```

                Validate the project:

                ```bash
                {validation_command or "Add a validation command for this stack."}
                ```

                ## First Product Pass

                {ProjectScaffolder._numbered_list(first_pass_items)}

                ## Safety Notes

                - Do not commit secrets, tokens, local database files, or generated build artifacts.
                - Keep file writes inside this project workspace.
                - Ask before destructive cleanup, dependency removal, or broad rewrites.
                """
            ),
        }

    @classmethod
    def _mission_contract(
        cls,
        preset: ProjectScaffoldPreset,
        project_name: str,
        *,
        prompt: str,
        install_command: str,
        validation_command: str,
    ) -> dict[str, object]:
        return {
            "schema": "aegis.mission_contract.v1",
            "project_name": project_name,
            "preset_id": preset.id,
            "preset_label": preset.label,
            "stack_family": cls._stack_family_for_preset(preset.id),
            "stack_locks": sorted(cls._preset_stack_locks(preset.id)),
            "framework": preset.framework,
            "language": preset.language,
            "package_manager": preset.package_manager,
            "original_prompt": prompt,
            "install_command": install_command,
            "validation_command": validation_command,
            "continuity_policy": "Reuse this project stack for follow-up prompts unless the user clearly asks for a new project, migration, rewrite, or stack conversion.",
        }

    @staticmethod
    def _numbered_list(items: list[str]) -> str:
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))

    @staticmethod
    def _first_product_pass_items(preset: ProjectScaffoldPreset, prompt: str) -> list[str]:
        lowered = f"{preset.id} {' '.join(preset.tags)} {prompt}".lower()

        if any(term in lowered for term in ("barber", "barbershop", "haircut", "fade", "beard", "shave")):
            return [
                "Turn the first screen into a complete barber landing flow with services, trust signals, hours, and clear booking calls to action.",
                "Wire the booking/contact interaction so name, service, time, and contact fields give visible validation or confirmation feedback.",
                "Add realistic barber-specific copy for services, pricing, testimonials, location, and appointment expectations.",
                "Validate the site and fix layout, TypeScript, CSS, or asset errors before marking the page ready.",
            ]

        if preset.id in {"nextjs-ts-tailwind", "vite-react-ts", "static-html-site"}:
            return [
                "Build the requested website content into full responsive sections instead of leaving generic placeholder copy.",
                "Add one working user interaction such as contact, booking, filtering, navigation, or form feedback.",
                "Polish mobile and desktop spacing, empty states, hover states, and accessible labels around the primary workflow.",
                "Run the saved validation command and repair any syntax, type, or stylesheet issues.",
            ]

        if preset.id in {"node-fullstack-js", "express-ts-api", "fastapi-python-api", "go-http-api", "dotnet-webapi-csharp", "django-python-web"}:
            return [
                "Implement the first real API or full-stack workflow with route handlers, input validation, and realistic sample data.",
                "Connect the workflow to storage, in-memory state, or the scaffolded persistence layer with clear error responses.",
                "Add a smoke test or self-test that exercises the main happy path and one invalid-input path.",
                "Run install and validation commands, then repair failing imports, scripts, schema, or server startup errors.",
            ]

        if preset.id in {"sqlite-python-db"}:
            return [
                "Expand the schema around the requested domain with primary keys, indexes, seed data, and a practical report query.",
                "Add a migration or reset script that can rebuild the local database from source files.",
                "Add a validation script that runs schema creation, seed loading, and at least one report query.",
                "Document safe backup, restore, and destructive reset expectations before broader data work.",
            ]

        if preset.id in {"cpp-cmake-cli", "cpp-msvc-console-sln", "dotnet-console-csharp", "rust-cli", "node-cli-js", "python-cli", "powershell-module"}:
            return [
                "Complete the requested command-line behavior with argument handling, console output, and a deterministic smoke path.",
                "Add or update the build/self-test script so validation compiles or runs the tool without manual steps.",
                "Document how to build, run, and verify the executable from a clean terminal.",
                "Run validation and repair compiler, script, path, or missing-entry-point errors.",
            ]

        if preset.id in {"cpp-cmake-dll"}:
            return [
                "Define the exported API surface with headers, versioning notes, and a small host-side smoke test.",
                "Implement safe input validation and predictable error returns for the first exported function.",
                "Add a build/test path that compiles the DLL and verifies exports or the smoke host.",
                "Document ABI, architecture, and runtime dependency expectations before adding more exports.",
            ]

        if preset.id in {"cpp-imgui-win32-dx11"}:
            return [
                "Build the first real ImGui tool panel with state, controls, status output, and a clear game/tooling workflow.",
                "Separate UI state, rendering, and backend logic so future panels can be added without a rewrite.",
                "Add a smoke build path and document required Windows SDK, compiler, and graphics dependencies.",
                "Validate the project and repair CMake, Win32, DirectX, or entry-point errors before adding visual polish.",
            ]

        if preset.id in {"cpp-game-loop-cmake"}:
            return [
                "Implement the first playable or inspectable game loop slice with update, render, input, timing, and shutdown paths.",
                "Add simple entity/state data that proves the loop can evolve into a larger game or simulation.",
                "Create a smoke test around deterministic engine state or frame-step behavior.",
                "Run validation and repair compiler, CMake, or platform errors before adding more systems.",
            ]

        if preset.id in {"python-game-file-analyzer"}:
            return [
                "Implement file inspection for the requested game or asset format with safe reads, metadata extraction, and clear reports.",
                "Add sample fixtures or generated binary test data that can validate parser behavior without private game files.",
                "Report offsets, sizes, signatures, entropy, and suspected structures without modifying source assets.",
                "Run validation and repair parser, CLI, fixture, or report-generation errors.",
            ]

        if preset.id in {"cpp-windows-internals-hooking"}:
            return [
                "Build the authorized Windows internals diagnostics workflow with process/module enumeration and clear status output.",
                "Keep any MinHook or hooking examples limited to owned test processes and documented diagnostic use cases.",
                "Add build-time checks and a smoke test or dry-run mode that avoids modifying unrelated processes.",
                "Validate the project and repair compiler, linker, architecture, or Windows SDK errors.",
            ]

        if preset.id in {"python-sln-refactor-tool"}:
            return [
                "Implement solution/project discovery for .sln, .vcxproj, .csproj, and shared property files.",
                "Add dry-run merge, split, and extraction reports that list exact files and references before any write.",
                "Add fixtures covering two-project merge and single-project extraction scenarios.",
                "Run validation and repair parser, path, or project-reference errors before enabling write mode.",
            ]

        if preset.id in {"windows-kernel-driver-controller"}:
            return [
                "Complete the safe controller/driver sample handshake with explicit IOCTL definitions and user-mode validation.",
                "Keep driver behavior limited to owned sample communication, diagnostics, and documented development flows.",
                "Add build, signing, deployment, and test-mode notes without hiding or bypassing platform protections.",
                "Validate what can be built locally and capture any missing WDK, SDK, signing, or configuration blockers.",
            ]

        if preset.id in {"electron-react-ts", "tauri-react-ts", "python-tkinter-desktop", "dotnet-wpf-csharp"}:
            return [
                "Implement the first complete desktop workflow with navigation, state, error feedback, and saved settings or sample data.",
                "Wire the native/backend bridge or local service boundary with typed request and response handling.",
                "Polish default and fullscreen layouts so the app feels usable before adding secondary features.",
                "Run validation and repair packaging, bridge, build, or UI type errors.",
            ]

        if preset.id in {"expo-react-native-ts"}:
            return [
                "Implement the first mobile workflow with navigation, state, form validation, and platform-safe styling.",
                "Add realistic sample data and empty/loading/error states for the main screen.",
                "Check small-screen layout constraints before broad visual polish.",
                "Run validation and repair Metro, TypeScript, package, or platform configuration errors.",
            ]

        return [
            "Replace starter copy, placeholder state, and sample data with the user's requested product behavior.",
            "Add the first end-to-end workflow before broad visual polish.",
            "Add or update validation coverage around the first real feature.",
            "Run validation and repair build, syntax, or runtime errors before expanding scope.",
        ]

    def _run_command_stage(
        self,
        *,
        stage_id: str,
        label: str,
        command: str,
        target: Path,
    ) -> tuple[ProjectBuildStage, CommandRun | None]:
        if self.commands is None:
            return (
                ProjectBuildStage(
                    id=stage_id,
                    label=label,
                    status="blocked",
                    detail="Command runner is not available in this runtime.",
                    command=command,
                    error="Command runner unavailable.",
                ),
                None,
            )

        result = self.commands.run(command, target, sandbox_profile=self.sandbox_profile)
        run = self._command_run(result, label=label)
        ok = self._command_ok(run)
        status = "succeeded" if ok else ("blocked" if not run.allowed else "failed")
        return (
            ProjectBuildStage(
                id=stage_id,
                label=label,
                status=status,
                detail=run.summary or run.reason,
                command=command,
                output_excerpt=self._command_excerpt(run),
                error="" if ok else (run.summary or run.reason),
            ),
            run,
        )

    @staticmethod
    def _command_run(result: CommandResult, *, label: str) -> CommandRun:
        category = ProjectScaffolder._categorize_command_result(result)
        summary = ProjectScaffolder._summarize_command_result(result, category=category, label=label)
        failed_step, failed_step_command = ProjectScaffolder._failed_step_parts_from_steps(list(result.steps))
        return CommandRun(
            command=result.command,
            cwd=result.cwd,
            allowed=result.allowed,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            reason=result.reason,
            category=category,
            summary=summary,
            steps=list(result.steps),
            failed_step=failed_step,
            failed_step_command=failed_step_command,
            diagnostics=ProjectScaffolder._extract_validation_diagnostics(result),
        )

    @staticmethod
    def _command_ok(run: CommandRun) -> bool:
        return run.allowed and not run.timed_out and run.exit_code == 0

    @staticmethod
    def _command_excerpt(run: CommandRun, *, limit: int = 1600) -> str:
        parts = []
        if run.stdout.strip():
            parts.append(run.stdout.strip())
        if run.stderr.strip():
            parts.append("[stderr]\n" + run.stderr.strip())
        if not parts and run.reason.strip():
            parts.append(run.reason.strip())
        text = "\n".join(parts)
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... output truncated ..."

    @staticmethod
    def _categorize_command_result(result: CommandResult) -> str:
        if result.timed_out:
            return "timeout"
        if not result.allowed:
            return "permission"
        if result.exit_code == 0:
            return "success"

        text = "\n".join(
            [
                result.command,
                result.reason,
                result.stdout[-4000:],
                result.stderr[-4000:],
            ]
        ).lower()
        if any(token in text for token in ("syntaxerror", "parseerror", "unexpected token", "expected ':'", "expected ')'")):
            return "syntax"
        if any(token in text for token in ("module not found", "cannot find module", "no module named", "importerror", "modulenotfounderror", "could not resolve")):
            return "dependency"
        if any(token in text for token in ("type error", "typeerror", "typescript", "tsc", "mypy", "pyright", "typecheck", "type-check")):
            return "typecheck"
        if any(token in text for token in ("assertionerror", "failed", "expected", "pytest", "jest", "vitest", "failing test", "test suite")):
            return "test"
        if any(token in text for token in ("build", "compile", "compilation", "error ts", "vite", "webpack", "cargo", "dotnet build")):
            return "build"
        if any(token in text for token in ("traceback", "exception", "runtimeerror", "referenceerror", "valueerror")):
            return "runtime"
        return "unknown"

    @staticmethod
    def _summarize_command_result(result: CommandResult, *, category: str, label: str) -> str:
        if result.timed_out:
            return f"{label} timed out before finishing."
        if not result.allowed:
            return result.reason or f"{label} was blocked by the current sandbox or command allowlist."
        if result.exit_code == 0:
            return f"{label} completed successfully."
        summaries = {
            "syntax": f"{label} failed with a syntax or parse error.",
            "dependency": f"{label} failed because a dependency, import, or module could not be resolved.",
            "typecheck": f"{label} failed with a type-checking error.",
            "test": f"{label} failed because the test suite reported a failure.",
            "build": f"{label} failed during build or compilation.",
            "runtime": f"{label} failed because code raised a runtime exception.",
            "permission": f"{label} was blocked by the current sandbox or command allowlist.",
            "unknown": f"{label} failed, but the root cause was not classified cleanly.",
        }
        return summaries.get(category, summaries["unknown"])

    @staticmethod
    def _visible_entries(target: Path) -> list[Path]:
        try:
            return [entry for entry in target.iterdir() if entry.name != ".aegis"]
        except OSError:
            return []

    @staticmethod
    def _conflicting_paths(target: Path, files: dict[str, str]) -> list[str]:
        return sorted(relative_path for relative_path in files if (target / relative_path).exists())

    @classmethod
    def _has_non_metadata_entries(cls, target: Path) -> bool:
        try:
            for entry in target.iterdir():
                relative = entry.name.replace("\\", "/")
                if entry.is_dir() and relative == ".aegis":
                    continue
                if relative not in cls.SAFE_METADATA_REFRESH_PATHS:
                    return True
        except OSError:
            return False
        return False

    @staticmethod
    def _next_available_child_target(target: Path, project_name: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-project"
        primary = target / safe_name
        if (primary / ".aegis" / "project.json").exists():
            return primary
        candidates = [primary]
        candidates.extend(target / f"{safe_name}-{index}" for index in range(2, 100))
        for candidate in candidates:
            if not candidate.exists():
                return candidate
        return target / f"{safe_name}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _is_same_scaffold_project(target: Path, preset_id: str, project_name: str) -> bool:
        manifest_path = target / ".aegis" / "project.json"
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return (
            str(manifest.get("preset_id", "")) == preset_id
            and str(manifest.get("project_name", "")) == project_name
        )

    @classmethod
    def _is_metadata_only_refresh(cls, target: Path, conflicting_paths: list[str]) -> bool:
        if not conflicting_paths:
            return False
        if not (target / ".aegis" / "project.json").exists():
            return False
        normalized = {path.replace("\\", "/") for path in conflicting_paths}
        return normalized.issubset(cls.SAFE_METADATA_REFRESH_PATHS)

    @staticmethod
    def _command_for_project(command: str, project_name: str) -> str:
        return command.replace("{project_name}", project_name).replace("{project_title}", _title_from_name(project_name))

    @staticmethod
    def _should_install_before_validation(
        preset: ProjectScaffoldPreset,
        target: Path,
        *,
        install_command: str,
        validation_command: str,
        request: ProjectScaffoldRequest,
    ) -> bool:
        if request.run_install or not request.run_validation or not install_command or not validation_command:
            return False
        package_manager = preset.package_manager.lower()
        normalized_install = " ".join(install_command.lower().split())
        explicit_install_override = bool(request.install_command.strip())
        if "npm" in package_manager:
            return (
                (explicit_install_override or "npm install" in normalized_install)
                and (target / "package.json").exists()
                and not (target / "node_modules").exists()
            )
        if any(token in package_manager for token in ("pip", "python")):
            has_python_manifest = (target / "pyproject.toml").exists() or (target / "requirements.txt").exists()
            return (explicit_install_override or "pip install" in normalized_install) and has_python_manifest and not (target / ".venv").exists()
        if "dotnet" in package_manager:
            has_dotnet_manifest = (target / f"{preset.id}.sln").exists() or any(target.rglob("*.csproj"))
            has_restore_assets = any(target.rglob("project.assets.json"))
            return (explicit_install_override or "dotnet restore" in normalized_install) and has_dotnet_manifest and not has_restore_assets
        if package_manager == "go":
            return (explicit_install_override or "go mod tidy" in normalized_install) and (target / "go.mod").exists() and not (target / "go.sum").exists()
        if package_manager == "cargo":
            return (explicit_install_override or "cargo fetch" in normalized_install) and (target / "Cargo.toml").exists() and not (target / "Cargo.lock").exists()
        return False

    @staticmethod
    def _has_explicit_project_name(prompt: str) -> bool:
        return re.search(r"\b(?:named|called|titled)\s+", prompt, re.IGNORECASE) is not None

    @staticmethod
    def _project_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", (value or "").strip()).strip("-_").lower()
        return cleaned or "aegis-app"

    @classmethod
    def _preset_default_project_name_if_needed(cls, preset_id: str, raw_name: str) -> str:
        default_name = cls.PRESET_DEFAULT_PROJECT_NAMES.get(preset_id, "")
        if not default_name:
            return raw_name

        slug = cls._project_name(raw_name)
        if slug in cls.GENERIC_TARGET_NAMES or slug == "aegis-app":
            return default_name
        if cls._looks_like_instructional_project_name(slug):
            return default_name
        return raw_name

    @classmethod
    def _looks_like_instructional_project_name(cls, slug: str) -> bool:
        tokens = [token for token in slug.split("-") if token]
        if not tokens:
            return True
        if tokens[0] in {"app", "project", "tool"}:
            return True
        return any(token in cls.INSTRUCTIONAL_PROJECT_NAME_TOKENS for token in tokens[:3])

    @classmethod
    def _should_use_target_leaf_project_name(cls, preset_id: str, target_leaf: str) -> bool:
        return preset_id in cls.TARGET_NAMED_WEB_PRESETS and cls._target_leaf_is_specific(target_leaf)

    @classmethod
    def _target_leaf_is_specific(cls, target_leaf: str) -> bool:
        slug = cls._project_name(target_leaf)
        return slug not in cls.GENERIC_TARGET_NAMES

    @classmethod
    def _extract_windows_path_from_prompt(cls, prompt: str) -> str:
        return scaffold_extract_windows_path_from_prompt(prompt)

    @classmethod
    def _clean_windows_path_fragment(cls, value: str) -> str:
        return scaffold_clean_windows_path_fragment(value)

    @classmethod
    def _path_action_stop_positions(cls, candidate: str, *, before: int | None = None) -> list[int]:
        return scaffold_path_action_stop_positions(candidate, before=before)

    @classmethod
    def _path_stop_phrase_is_boundary(cls, lowered_candidate: str, position: int, phrase: str) -> bool:
        return scaffold_path_stop_phrase_is_boundary(lowered_candidate, position, phrase)

    @staticmethod
    def _path_action_boundary_preserves_leaf(candidate: str, action_position: int) -> bool:
        return scaffold_path_action_boundary_preserves_leaf(candidate, action_position)

    @classmethod
    def _path_instruction_separator_position(cls, candidate: str) -> int | None:
        return scaffold_path_instruction_separator_position(candidate)

    @classmethod
    def _trim_path_fragment(cls, candidate: str) -> str:
        return scaffold_trim_path_fragment(candidate)

    @staticmethod
    def _trailing_wrapper_belongs_to_path(candidate: str) -> bool:
        return scaffold_trailing_wrapper_belongs_to_path(candidate)

    @staticmethod
    def _path_fragment_exists(candidate: str) -> bool:
        return scaffold_path_fragment_exists(candidate)

    @classmethod
    def _prompt_without_windows_paths(cls, prompt: str, *, target_path: str = "") -> str:
        return scaffold_prompt_without_windows_paths(prompt, target_path=target_path)

    @classmethod
    def _project_name_from_prompt(cls, prompt: str) -> str:
        lowered = prompt.lower()
        if re.search(r"\bkernel\s+driver\b", lowered):
            if "controller" in lowered or "desktop app" in lowered or "communication" in lowered:
                return "kernel-driver-controller"
            return "kernel-driver"

        explicit = re.search(
            r"\b(?:named|called|titled)\s+([A-Za-z0-9][A-Za-z0-9 _-]{1,64}?)(?=\s+(?:as|that|for|with|using|to|which|and)\b|[,.!?]|$)",
            prompt,
            re.IGNORECASE,
        )
        if explicit:
            return explicit.group(1)

        stop_words = {
            "a",
            "accept",
            "an",
            "and",
            "app",
            "application",
            "as",
            "at",
            "backend",
            "build",
            "brown",
            "cli",
            "cmake",
            "code",
            "create",
            "dashboard",
            "desktop",
            "django",
            "electron",
            "expo",
            "express",
            "fastapi",
            "for",
            "frontend",
            "full",
            "generate",
            "go",
            "how",
            "input",
            "its",
            "make",
            "me",
            "native",
            "next",
            "nextjs",
            "node",
            "project",
            "python",
            "react",
            "react-native",
            "requires",
            "rust",
            "scaffold",
            "tauri",
            "service",
            "site",
            "starter",
            "syscalls",
            "that",
            "the",
            "this",
            "typescript",
            "using",
            "uses",
            "vite",
            "web",
            "website",
            "with",
        }
        tokens = re.findall(r"[A-Za-z0-9]+", lowered)
        useful = [token for token in tokens if token not in stop_words and len(token) > 1]
        return "-".join(useful[:4]) if useful else "aegis-app"

    @staticmethod
    def _keyword_in_prompt(prompt: str, keyword: str) -> bool:
        term = (keyword or "").strip().lower()
        if not term:
            return False
        if re.fullmatch(r"[a-z0-9+#.]+", term):
            boundary = rf"(?<![a-z0-9+#.]){re.escape(term)}(?![a-z0-9+#.])"
            return re.search(boundary, prompt) is not None
        return term in prompt

    @classmethod
    def _select_preset(cls, prompt: str) -> tuple[ProjectScaffoldPreset, float, list[str], list[str]]:
        lowered = prompt.lower()
        web_negated = cls._prompt_negates_web_stack(prompt)
        rules: dict[str, list[str]] = {
            "nextjs-ts-tailwind": [
                "next",
                "next.js",
                "app router",
                "full stack",
                "full-stack",
                "saas",
                "dashboard",
                "website",
                "web app",
                "landing",
                "auth",
                "production web",
            ],
            "vite-react-ts": [
                "vite",
                "single page",
                "spa",
                "frontend",
                "client app",
                "react app",
                "portfolio",
                "static site",
            ],
            "static-html-site": [
                "static website",
                "static site",
                "html website",
                "html css",
                "plain html",
                "landing page",
                "business website",
                "brochure site",
                "marketing site",
                "portfolio site",
                "barber website",
                "salon website",
                "restaurant website",
                "website",
            ],
            "browser-extension-mv3": [
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "mv3",
                "content script",
                "background service worker",
                "extension popup",
                "popup extension",
            ],
            "vscode-extension-js": [
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "code extension",
                "extension command",
                "extension api",
                "developer extension",
            ],
            "node-cli-js": [
                "node cli",
                "node.js cli",
                "javascript cli",
                "js cli",
                "npm cli",
                "node command line",
                "node command-line",
                "node tool",
                "javascript tool",
                "package bin",
            ],
            "node-http-api-js": [
                "node http api",
                "node.js http api",
                "node api",
                "node.js api",
                "javascript api",
                "js api",
                "rest api",
                "json api",
                "http api",
                "api server",
                "backend api",
                "backend service",
            ],
            "node-fullstack-js": [
                "full stack",
                "full-stack",
                "full stack app",
                "full-stack app",
                "full application",
                "web app with api",
                "frontend and backend",
                "frontend backend",
                "dashboard app",
                "admin dashboard",
                "crud app",
                "crud dashboard",
                "task tracker",
                "project tracker",
                "inventory app",
                "booking app",
            ],
            "powershell-module": [
                "powershell",
                "ps1",
                "psm1",
                "psd1",
                "powershell module",
                "powershell script",
                "windows automation",
                "admin script",
                "automation module",
                "script module",
            ],
            "python-cli": [
                "cli",
                "command line",
                "command-line",
                "terminal",
                "automation",
                "script",
                "local tool",
                "python tool",
            ],
            "python-tkinter-desktop": [
                "tkinter",
                "python desktop",
                "desktop utility",
                "gui utility",
                "local desktop",
                "simple desktop",
                "lightweight desktop",
                "python gui",
                "stdlib gui",
            ],
            "python-stdlib-api": [
                "python rest api",
                "python json api",
                "python http api",
                "python backend api",
                "python backend service",
                "python api server",
                "stdlib api",
                "http.server",
                "no dependency python api",
                "dependency free python api",
            ],
            "fastapi-python-api": [
                "fastapi",
                "python api",
                "rest api",
                "api",
                "backend",
                "service",
                "microservice",
            ],
            "express-ts-api": [
                "express",
                "node",
                "node.js",
                "typescript api",
                "ts api",
                "rest api",
                "api",
                "backend",
                "service",
            ],
            "sqlite-python-db": [
                "database",
                "sqlite",
                "sqlite3",
                "sql",
                "schema",
                "migration",
                "migrations",
                "seed data",
                "data model",
                "crud",
                "queries",
                "tables",
            ],
            "electron-react-ts": [
                "electron",
                "desktop app",
                "desktop",
                "native desktop",
                "windows app",
                "cross-platform desktop",
                "preload",
            ],
            "expo-react-native-ts": [
                "expo",
                "react native",
                "react-native",
                "mobile",
                "ios",
                "android",
                "phone app",
                "tablet",
            ],
            "django-python-web": [
                "django",
                "python web",
                "server rendered",
                "admin panel",
                "cms",
                "models",
                "views",
            ],
            "cpp-cmake-cli": [
                "c++",
                "cpp",
                "cmake",
                "native",
                "binary",
                "desktop cli",
                "console app",
                "console application",
                "command line",
                "command-line",
                "hello world",
            ],
            "cpp-cmake-dll": [
                "dll",
                "shared library",
                "dynamic library",
                "native library",
                "plugin library",
                "library",
                "exports",
                "exported function",
            ],
            "cpp-imgui-win32-dx11": [
                "imgui",
                "dear imgui",
                "immediate mode gui",
                "immediate-mode gui",
                "debug overlay",
                "game editor",
                "editor tool",
                "tooling gui",
                "win32 gui",
                "directx11",
                "directx 11",
            ],
            "cpp-game-loop-cmake": [
                "game loop",
                "game engine",
                "game development",
                "game dev",
                "ecs",
                "entity component",
                "simulation",
                "asset registry",
                "level system",
                "gameplay system",
                "native game",
            ],
            "python-game-file-analyzer": [
                "game file",
                "game files",
                "asset file",
                "asset files",
                "asset bundle",
                "asset bundles",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse-engineer",
                "reverse engineering",
                "pak",
                "wad",
                "bundle",
                "archive",
                "strings",
                "entropy",
                "hex",
            ],
            "cpp-msvc-console-sln": [
                "visual studio",
                ".sln",
                "sln",
                "solution",
                "vcxproj",
                "msbuild",
                "console project",
                "windows console",
            ],
            "cpp-windows-service": [
                "windows service",
                "win32 service",
                "service control manager",
                "scm",
                "background service",
                "system service",
                "service app",
                "service application",
                "install service",
                "uninstall service",
            ],
            "cpp-windows-internals-hooking": [
                "windows internals",
                "win32 internals",
                "ntdll",
                "winapi",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "process modules",
                "module enumeration",
                "export table",
                "iat",
                "eiat",
            ],
            "python-sln-refactor-tool": [
                "merge sln",
                "merge two sln",
                "merge solutions",
                "combine sln",
                "combine projects",
                "combine solutions",
                "split sln",
                "split solution",
                "split a project",
                "separate project",
                "extract project",
                "into its own sln",
                "solution refactor",
                "solution merger",
                "solution splitter",
                "vcxproj refactor",
            ],
            "windows-kernel-driver-controller": [
                "kernel driver",
                "driver",
                "wdk",
                "syscall",
                "syscalls",
                "ioctl",
                "deviceiocontrol",
                "kernel",
                "ring0",
                "desktop app controller",
            ],
            "rust-cli": [
                "rust",
                "cargo",
                "rust cli",
                "native cli",
                "systems",
                "binary",
            ],
            "go-http-api": [
                "golang",
                "go api",
                "go service",
                "go http",
                "net/http",
                "go backend",
            ],
            "dotnet-webapi-csharp": [
                "asp.net",
                "aspnet",
                ".net",
                "dotnet",
                "c#",
                "csharp",
                "minimal api",
                "web api",
            ],
            "dotnet-console-csharp": [
                "c# console",
                "csharp console",
                ".net console",
                "dotnet console",
                "c# cli",
                "csharp cli",
                "dotnet cli",
                "c# exe",
                ".net exe",
                "console app",
                "console application",
            ],
            "dotnet-wpf-csharp": [
                "wpf",
                "xaml",
                "c# desktop",
                "csharp desktop",
                ".net desktop",
                "dotnet desktop",
                "windows desktop app",
                "windows gui",
                "desktop gui",
            ],
            "tauri-react-ts": [
                "tauri",
                "rust desktop",
                "lightweight desktop",
                "small desktop",
                "desktop rust",
            ],
        }
        if web_negated:
            web_terms = {
                "website",
                "web app",
                "landing",
                "landing page",
                "static website",
                "static site",
                "html website",
                "business website",
                "brochure site",
                "marketing site",
                "portfolio site",
                "barber website",
                "salon website",
                "restaurant website",
                "production web",
            }
            for preset_id in ("nextjs-ts-tailwind", "vite-react-ts", "static-html-site", "node-fullstack-js"):
                rules[preset_id] = [term for term in rules.get(preset_id, []) if term not in web_terms]
        scores = {preset.id: 0 for preset in cls.presets()}
        hits: dict[str, list[str]] = {preset_id: [] for preset_id in scores}
        for preset_id, terms in rules.items():
            for term in terms:
                if cls._keyword_in_prompt(lowered, term):
                    scores[preset_id] += 3 if len(term) > 4 else 2
                    hits[preset_id].append(term)

        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "node")
            or cls._keyword_in_prompt(lowered, "express")
            or cls._keyword_in_prompt(lowered, "typescript")
            or cls._keyword_in_prompt(lowered, "ts")
        ):
            scores["express-ts-api"] += 5
            hits["express-ts-api"].append("api + node/typescript")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "python") or cls._keyword_in_prompt(lowered, "fastapi")
        ):
            scores["fastapi-python-api"] += 5
            hits["fastapi-python-api"].append("api + python")
        if (
            cls._keyword_in_prompt(lowered, "python")
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("api", "rest api", "json api", "http api", "backend", "service", "crud")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("fastapi", "django", "flask", "react", "next", "vite", "desktop", "tkinter")
            )
        ):
            scores["python-stdlib-api"] += 14
            hits["python-stdlib-api"].append("dependency-free python api")
        if (
            cls._keyword_in_prompt(lowered, "react")
            and not cls._keyword_in_prompt(lowered, "next")
            and "full stack" not in lowered
            and "full-stack" not in lowered
        ):
            scores["vite-react-ts"] += 3
            hits["vite-react-ts"].append("react client")
        if (
            not web_negated
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "website",
                    "web site",
                    "landing page",
                    "business website",
                    "brochure site",
                    "marketing site",
                    "portfolio site",
                    "barber website",
                    "salon website",
                    "restaurant website",
                    "static site",
                    "static website",
                    "html website",
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "next",
                    "next.js",
                    "react",
                    "vite",
                    "full stack",
                    "full-stack",
                    "dashboard",
                    "saas",
                    "auth",
                    "api",
                    "backend",
                    "electron",
                    "tauri",
                    "mobile",
                    "django",
                )
            )
        ):
            scores["static-html-site"] += 10
            hits["static-html-site"].append("dependency-free website")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "content script",
                "background service worker",
                "extension popup",
            )
        ):
            scores["browser-extension-mv3"] += 16
            hits["browser-extension-mv3"].append("browser extension")
        if (
            cls._keyword_in_prompt(lowered, "extension")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("chrome", "edge", "browser", "web"))
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("vscode", "visual studio code"))
        ):
            scores["browser-extension-mv3"] += 9
            hits["browser-extension-mv3"].append("extension target")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "extension command",
                "extension api",
            )
        ):
            scores["vscode-extension-js"] += 16
            hits["vscode-extension-js"].append("vs code extension")
        if (
            cls._keyword_in_prompt(lowered, "extension")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("vscode", "vs code", "visual studio code"))
        ):
            scores["vscode-extension-js"] += 10
            hits["vscode-extension-js"].append("developer tool extension")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("node", "node.js", "javascript", "js", "npm"))
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("cli", "command line", "command-line", "local tool", "automation", "package bin", "executable")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "express", "web api", "rest api", "browser extension"))
        ):
            scores["node-cli-js"] += 12
            hits["node-cli-js"].append("node cli/tool")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("rest api", "json api", "http api", "api server", "backend api", "backend service")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "express",
                    "typescript",
                    "ts api",
                    "fastapi",
                    "python",
                    "django",
                    "go",
                    "golang",
                    ".net",
                    "dotnet",
                    "c#",
                    "csharp",
                    "asp.net",
                )
            )
        ):
            scores["node-http-api-js"] += 12
            hits["node-http-api-js"].append("dependency-free node api")
        if (
            not web_negated
            and (
                any(
                    cls._keyword_in_prompt(lowered, term)
                    for term in (
                        "full stack",
                        "full-stack",
                        "web app with api",
                        "frontend and backend",
                        "frontend backend",
                        "crud app",
                        "crud dashboard",
                        "task tracker",
                        "project tracker",
                        "inventory app",
                        "booking app",
                    )
                )
                or (
                    any(cls._keyword_in_prompt(lowered, term) for term in ("dashboard", "web app", "admin"))
                    and any(cls._keyword_in_prompt(lowered, term) for term in ("crud", "api", "backend", "database", "json persistence", "tasks"))
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "next",
                    "next.js",
                    "react",
                    "vite",
                    "express",
                    "typescript",
                    "fastapi",
                    "python",
                    "django",
                    "go",
                    "golang",
                    ".net",
                    "dotnet",
                    "c#",
                    "csharp",
                    "electron",
                    "tauri",
                    "mobile",
                    "react native",
                )
            )
        ):
            scores["node-fullstack-js"] += 14
            hits["node-fullstack-js"].append("dependency-free full-stack app")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "powershell",
                    "ps1",
                    "psm1",
                    "psd1",
                    "powershell module",
                    "powershell script",
                    "windows automation",
                    "admin script",
                    "automation module",
                )
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in (
                    "kernel",
                    "driver",
                    "windows service",
                    "win32 service",
                    "c++",
                    "cpp",
                    "c#",
                    "csharp",
                    ".net",
                    "dotnet",
                    "wpf",
                    "xaml",
                    "api",
                    "web app",
                    "website",
                )
            )
        ):
            scores["powershell-module"] += 14
            hits["powershell-module"].append("powershell automation")
        if cls._keyword_in_prompt(lowered, "react") and (
            cls._keyword_in_prompt(lowered, "electron") or cls._keyword_in_prompt(lowered, "desktop")
        ):
            scores["electron-react-ts"] += 6
            hits["electron-react-ts"].append("react desktop")
        if cls._keyword_in_prompt(lowered, "react") and (
            cls._keyword_in_prompt(lowered, "mobile")
            or cls._keyword_in_prompt(lowered, "native")
            or cls._keyword_in_prompt(lowered, "expo")
        ):
            scores["expo-react-native-ts"] += 6
            hits["expo-react-native-ts"].append("react mobile")
        if cls._keyword_in_prompt(lowered, "python") and (
            cls._keyword_in_prompt(lowered, "django")
            or cls._keyword_in_prompt(lowered, "admin")
            or "server rendered" in lowered
        ):
            scores["django-python-web"] += 6
            hits["django-python-web"].append("python django web")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("tkinter", "python desktop", "python gui", "desktop utility", "gui utility")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react native", "web"))
        ):
            scores["python-tkinter-desktop"] += 12
            hits["python-tkinter-desktop"].append("python desktop gui")
        if (
            cls._keyword_in_prompt(lowered, "desktop")
            and cls._keyword_in_prompt(lowered, "python")
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react"))
        ):
            scores["python-tkinter-desktop"] += 8
            hits["python-tkinter-desktop"].append("python desktop")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, "go") or cls._keyword_in_prompt(lowered, "golang")
        ):
            scores["go-http-api"] += 7
            hits["go-http-api"].append("api + go")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("database", "sqlite", "sqlite3", "schema", "migration", "migrations", "crud")
        ):
            scores["sqlite-python-db"] += 10
            hits["sqlite-python-db"].append("database project")
        if cls._keyword_in_prompt(lowered, "sql") and not any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("asp.net", ".net", "dotnet", "c#", "csharp")
        ):
            scores["sqlite-python-db"] += 4
            hits["sqlite-python-db"].append("sql")
        if cls._keyword_in_prompt(lowered, "api") and (
            cls._keyword_in_prompt(lowered, ".net")
            or cls._keyword_in_prompt(lowered, "dotnet")
            or cls._keyword_in_prompt(lowered, "c#")
            or cls._keyword_in_prompt(lowered, "csharp")
        ):
            scores["dotnet-webapi-csharp"] += 7
            hits["dotnet-webapi-csharp"].append("api + dotnet/csharp")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in (".net", "dotnet", "c#", "csharp"))
            and any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("console", "cli", "command line", "command-line", "exe", "executable", "local tool")
            )
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "asp.net", "web api", "http"))
        ):
            scores["dotnet-console-csharp"] += 12
            hits["dotnet-console-csharp"].append("c# console/exe")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("wpf", "xaml", "c# desktop", "csharp desktop", ".net desktop", "dotnet desktop"))
            or (
                cls._keyword_in_prompt(lowered, "desktop")
                and any(cls._keyword_in_prompt(lowered, term) for term in ("c#", "csharp", ".net", "dotnet"))
                and not any(cls._keyword_in_prompt(lowered, term) for term in ("electron", "tauri", "react", "api"))
            )
        ):
            scores["dotnet-wpf-csharp"] += 14
            hits["dotnet-wpf-csharp"].append("c# wpf desktop")
        if cls._keyword_in_prompt(lowered, "react") and cls._keyword_in_prompt(lowered, "tauri"):
            scores["tauri-react-ts"] += 12
            hits["tauri-react-ts"].append("tauri react desktop")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("sln", "solution", "visual studio", "vcxproj", "msbuild")
        ):
            scores["cpp-msvc-console-sln"] += 12
            hits["cpp-msvc-console-sln"].append("c++ visual studio solution")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "dll",
                "dll host",
                "shared library",
                "dynamic library",
                "native library",
                "plugin library",
                "plugin host",
                "exported api",
                "exported symbols",
                "loadlibrary",
                "getprocaddress",
            )
        ):
            scores["cpp-cmake-dll"] += 18
            hits["cpp-cmake-dll"].append("c++ dll/shared library with host loader")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("dll", "shared library", "dynamic library", "native library", "plugin library")
        ) and any(
            cls._keyword_in_prompt(lowered, term)
            for term in ("native", "plugin", "project", "existing", "library", "refine", "optimize", "clean up")
        ):
            scores["cpp-cmake-dll"] += 14
            hits["cpp-cmake-dll"].append("native dll/plugin library")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "imgui",
                "dear imgui",
                "immediate mode gui",
                "immediate-mode gui",
                "debug overlay",
                "game editor",
                "editor tool",
                "tooling gui",
            )
        ):
            scores["cpp-imgui-win32-dx11"] += 18
            hits["cpp-imgui-win32-dx11"].append("dear imgui game/tooling ui")
        if (
            any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("game loop", "game engine", "game development", "game dev", "ecs", "entity component", "simulation")
            )
            and not any(
                cls._keyword_in_prompt(lowered, term)
                for term in ("website", "web app", "api", "backend", "mobile", "react", "next", "vite")
            )
        ):
            scores["cpp-game-loop-cmake"] += 14
            hits["cpp-game-loop-cmake"].append("native game loop")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "game file",
                "game files",
                "asset file",
                "asset files",
                "asset bundle",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse-engineer",
                "reverse engineering",
                "pak",
                "wad",
                "hex",
                "entropy",
            )
        ):
            scores["python-game-file-analyzer"] += 18
            hits["python-game-file-analyzer"].append("game file/asset analysis")
        if (cls._keyword_in_prompt(lowered, "c++") or cls._keyword_in_prompt(lowered, "cpp")) and cls._keyword_in_prompt(lowered, "console"):
            if any(cls._keyword_in_prompt(lowered, term) for term in ("sln", "solution", "visual studio", "vcxproj", "msbuild")):
                scores["cpp-msvc-console-sln"] += 4
                hits["cpp-msvc-console-sln"].append("c++ console solution")
            else:
                scores["cpp-cmake-cli"] += 14
                hits["cpp-cmake-cli"].append("c++ console app")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "windows service",
                "win32 service",
                "service control manager",
                "background service",
                "system service",
                "install service",
                "uninstall service",
            )
        ):
            scores["cpp-windows-service"] += 16
            hits["cpp-windows-service"].append("windows service")
        if (
            cls._keyword_in_prompt(lowered, "service")
            and any(cls._keyword_in_prompt(lowered, term) for term in ("windows", "win32", "native", "c++", "cpp"))
            and not any(cls._keyword_in_prompt(lowered, term) for term in ("api", "http", "rest", "fastapi", "express"))
        ):
            scores["cpp-windows-service"] += 8
            hits["cpp-windows-service"].append("native service app")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "windows internals",
                "win32 internals",
                "ntdll",
                "winapi",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "process modules",
                "module enumeration",
                "export table",
                "iat",
            )
        ):
            scores["cpp-windows-internals-hooking"] += 18
            hits["cpp-windows-internals-hooking"].append("windows internals/instrumentation")
        if any(
            cls._keyword_in_prompt(lowered, term)
            for term in (
                "merge sln",
                "merge two sln",
                "merge solutions",
                "combine sln",
                "combine projects",
                "combine solutions",
                "split sln",
                "split solution",
                "split a project",
                "separate project",
                "extract project",
                "into its own sln",
                "solution refactor",
                "solution merger",
                "solution splitter",
            )
        ):
            scores["python-sln-refactor-tool"] += 34
            hits["python-sln-refactor-tool"].append("visual studio solution merge/split")
        if (
            any(cls._keyword_in_prompt(lowered, term) for term in ("merge", "combine", "split", "separate", "extract"))
            and any(cls._keyword_in_prompt(lowered, term) for term in ("sln", "solution", "solutions", "vcxproj", "project"))
        ):
            scores["python-sln-refactor-tool"] += 22
            hits["python-sln-refactor-tool"].append("visual studio solution merge/split")
            hits["python-sln-refactor-tool"].append("solution project restructuring")
        if "kernel driver" in lowered or ("driver" in lowered and ("kernel" in lowered or "wdk" in lowered)):
            scores["windows-kernel-driver-controller"] += 16
            hits["windows-kernel-driver-controller"].append("windows kernel driver")
        if ("controller" in lowered or "desktop app" in lowered) and ("kernel" in lowered or "driver" in lowered):
            scores["windows-kernel-driver-controller"] += 8
            hits["windows-kernel-driver-controller"].append("driver controller app")
        if ("syscall" in lowered or "syscalls" in lowered or "communication" in lowered) and ("kernel" in lowered or "driver" in lowered):
            scores["windows-kernel-driver-controller"] += 5
            hits["windows-kernel-driver-controller"].append("user/kernel communication")
        generic_app = re.search(r"\b(app|application|program|software)\b", lowered) is not None
        web_or_service_context = any(
            term in lowered
            for term in (
                "website",
                "web site",
                "web app",
                "frontend",
                "landing",
                "landing page",
                "static website",
                "static site",
                "business website",
                "brochure site",
                "dashboard",
                "saas",
                "api",
                "backend",
                "service",
                "mobile",
                "phone",
                "ios",
                "android",
                "react native",
                "expo",
                "tauri",
                "electron",
                "next",
                "vite",
                "react app",
                "browser extension",
                "chrome extension",
                "edge extension",
                "webextension",
                "manifest v3",
                "manifest mv3",
                "content script",
                "vs code extension",
                "vscode extension",
                "visual studio code extension",
                "node cli",
                "node.js cli",
                "javascript cli",
                "node tool",
                "powershell",
                "ps1",
                "psm1",
                "powershell module",
                "windows automation",
                "admin script",
                "driver",
                "kernel",
                "wdk",
                "tkinter",
                "python desktop",
                "desktop utility",
                "gui utility",
                "wpf",
                "xaml",
                "c# desktop",
                ".net desktop",
                "windows service",
                "win32 service",
                "background service",
                "system service",
                "windows internals",
                "win32 internals",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "merge sln",
                "merge solutions",
                "combine sln",
                "combine solutions",
                "split sln",
                "split solution",
                "solution refactor",
                "c++",
                "cpp",
                "cmake",
                "console",
                "dll",
                "imgui",
                "dear imgui",
                "game loop",
                "game engine",
                "game development",
                "game dev",
                "asset registry",
                "game file",
                "asset file",
                "asset bundle",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse engineering",
                "full stack",
                "full-stack",
                "crud",
                "task tracker",
                "project tracker",
                "inventory app",
                "booking app",
                "library",
                "shared library",
                "dynamic library",
                "database",
                "sqlite",
                "schema",
                "sql",
            )
        )
        if generic_app and not web_or_service_context:
            scores["electron-react-ts"] += 4
            hits["electron-react-ts"].append("generic application")
        if "full project" in lowered or "full app" in lowered or "from scratch" in lowered:
            scores["nextjs-ts-tailwind"] += 2
            hits["nextjs-ts-tailwind"].append("full project")

        ranked_ids = [
            "windows-kernel-driver-controller",
            "tauri-react-ts",
            "expo-react-native-ts",
            "dotnet-wpf-csharp",
            "electron-react-ts",
            "vscode-extension-js",
            "browser-extension-mv3",
            "dotnet-webapi-csharp",
            "dotnet-console-csharp",
            "go-http-api",
            "sqlite-python-db",
            "python-sln-refactor-tool",
            "python-game-file-analyzer",
            "cpp-windows-internals-hooking",
            "cpp-imgui-win32-dx11",
            "cpp-game-loop-cmake",
            "cpp-windows-service",
            "cpp-msvc-console-sln",
            "cpp-cmake-dll",
            "cpp-cmake-cli",
            "rust-cli",
            "django-python-web",
            "node-fullstack-js",
            "node-http-api-js",
            "powershell-module",
            "express-ts-api",
            "fastapi-python-api",
            "node-cli-js",
            "python-tkinter-desktop",
            "python-stdlib-api",
            "static-html-site",
            "nextjs-ts-tailwind",
            "vite-react-ts",
            "python-cli",
        ]
        best_id = max(ranked_ids, key=lambda preset_id: scores[preset_id])
        if scores[best_id] == 0:
            best_id = "nextjs-ts-tailwind"
            hits[best_id].append("default full project")

        preset = cls._preset_for(best_id)
        best_hits = list(dict.fromkeys(hits[best_id]))
        score = scores[best_id]
        confidence = min(0.94, 0.52 + (score * 0.045))
        reasons = [
            f"Selected {preset.label} because the prompt matched: {', '.join(best_hits)}."
            if best_hits
            else f"Selected {preset.label} as the safest general starter.",
            f"Default install command: {preset.install_command or 'none required'}.",
            f"Default validation command: {preset.validation_command or 'not configured'}.",
        ]
        return preset, confidence, reasons, best_hits

    @staticmethod
    def _python_package_name(project_name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", project_name.replace("-", "_")).strip("_").lower()
        if not cleaned:
            return "aegis_app"
        if cleaned[0].isdigit():
            cleaned = f"app_{cleaned}"
        return cleaned

    @staticmethod
    def _manifest_package_name(project_name: str, fallback_prefix: str = "aegis") -> str:
        cleaned = ProjectScaffolder._project_name(project_name)
        if cleaned[0].isdigit():
            cleaned = f"{fallback_prefix}-{cleaned}"
        return cleaned

    @staticmethod
    def _nextjs_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "scripts": {{
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "lint": "next lint",
                    "typecheck": "tsc --noEmit"
                  }},
                  "dependencies": {{
                    "next": "15.5.15",
                    "react": "19.2.5",
                    "react-dom": "19.2.5"
                  }},
                  "devDependencies": {{
                    "@types/node": "^22.10.1",
                    "@types/react": "^19.2.14",
                    "@types/react-dom": "^19.2.3",
                    "autoprefixer": "^10.4.20",
                    "eslint": "^9.16.0",
                    "eslint-config-next": "15.5.15",
                    "postcss": "^8.4.49",
                    "tailwindcss": "^3.4.19",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2017",
                    "lib": ["dom", "dom.iterable", "esnext"],
                    "allowJs": false,
                    "skipLibCheck": true,
                    "strict": true,
                    "noEmit": true,
                    "esModuleInterop": true,
                    "module": "esnext",
                    "moduleResolution": "bundler",
                    "resolveJsonModule": true,
                    "isolatedModules": true,
                    "jsx": "preserve",
                    "incremental": true,
                    "plugins": [{ "name": "next" }],
                    "paths": { "@/*": ["./*"] }
                  },
                  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
                  "exclude": ["node_modules"]
                }
                """
            ),
            "next.config.mjs": _strip(
                """
                /** @type {import('next').NextConfig} */
                const nextConfig = {
                  reactStrictMode: true
                };

                export default nextConfig;
                """
            ),
            "postcss.config.mjs": _strip(
                """
                const config = {
                  plugins: {
                    tailwindcss: {},
                    autoprefixer: {}
                  }
                };

                export default config;
                """
            ),
            "tailwind.config.ts": _strip(
                """
                import type { Config } from "tailwindcss";

                const config: Config = {
                  content: [
                    "./app/**/*.{js,ts,jsx,tsx,mdx}",
                    "./components/**/*.{js,ts,jsx,tsx,mdx}"
                  ],
                  theme: {
                    extend: {
                      colors: {
                        ink: "#09111d",
                        signal: "#27dd7b",
                        cobalt: "#6aa7ff",
                        amber: "#e0b15f"
                      }
                    }
                  },
                  plugins: []
                };

                export default config;
                """
            ),
            "app/layout.tsx": _strip(
                f"""
                import type {{ Metadata }} from "next";
                import type {{ ReactNode }} from "react";
                import "./globals.css";

                export const metadata: Metadata = {{
                  title: "{title}",
                  description: "A production-ready application scaffold generated by Aegis."
                }};

                export default function RootLayout({{
                  children
                }}: Readonly<{{
                  children: ReactNode;
                }}>) {{
                  return (
                    <html lang="en">
                      <body>{{children}}</body>
                    </html>
                  );
                }}
                """
            ),
            "app/page.tsx": _strip(
                """
                import { AppShell } from "@/components/app-shell";

                export default function Home() {
                  return <AppShell />;
                }
                """
            ),
            "app/globals.css": _strip(
                """
                @tailwind base;
                @tailwind components;
                @tailwind utilities;

                :root {
                  color-scheme: dark;
                  background: #060b12;
                  color: #edf3f8;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  min-height: 100vh;
                  margin: 0;
                  background:
                    linear-gradient(120deg, rgba(21, 34, 51, 0.88), rgba(7, 12, 20, 0.96)),
                    #060b12;
                  font-family: Arial, Helvetica, sans-serif;
                }
                """
            ),
            "components/app-shell.tsx": _strip(
                f"""
                const metrics = [
                  ["Ship readiness", "86%", "Validation profile saved"],
                  ["Open tasks", "12", "Prioritized for the next pass"],
                  ["Latency budget", "240ms", "Client interactions stay fast"]
                ];

                const actions = [
                  "Define the first real user workflow",
                  "Connect authentication and persistence",
                  "Add CI validation before release"
                ];

                export function AppShell() {{
                  return (
                    <main className="min-h-screen px-6 py-6 text-slate-100">
                      <section className="mx-auto flex max-w-6xl flex-col gap-6">
                        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
                          <div>
                            <p className="text-sm text-emerald-300">Aegis project scaffold</p>
                            <h1 className="mt-2 text-4xl font-semibold tracking-normal">{title}</h1>
                            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                              A clean starting point for a real product: typed components, responsive layout,
                              validation wiring, and space for the first feature pass.
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <button className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950">
                              New workflow
                            </button>
                            <button className="rounded-lg border border-white/14 px-4 py-2 text-sm text-slate-200">
                              Review plan
                            </button>
                          </div>
                        </header>

                        <section className="grid gap-3 md:grid-cols-3">
                          {{metrics.map(([label, value, detail]) => (
                            <article key={{label}} className="rounded-lg border border-white/10 bg-white/[0.045] p-4">
                              <p className="text-xs uppercase tracking-normal text-slate-400">{{label}}</p>
                              <p className="mt-3 text-2xl font-semibold">{{value}}</p>
                              <p className="mt-2 text-sm text-slate-300">{{detail}}</p>
                            </article>
                          ))}}
                        </section>

                        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                          <div className="rounded-lg border border-white/10 bg-slate-950/40 p-5">
                            <h2 className="text-lg font-semibold">Product cockpit</h2>
                            <div className="mt-5 grid gap-3">
                              {{["Design the core entity model", "Build the API surface", "Harden permissions"].map((item, index) => (
                                <div key={{item}} className="flex items-center justify-between rounded-lg border border-white/10 bg-slate-900/70 px-4 py-3">
                                  <span className="text-sm text-slate-200">{{item}}</span>
                                  <span className="text-xs text-slate-400">Step {{index + 1}}</span>
                                </div>
                              ))}}
                            </div>
                          </div>

                          <aside className="rounded-lg border border-white/10 bg-white/[0.045] p-5">
                            <h2 className="text-lg font-semibold">Next actions</h2>
                            <ul className="mt-4 space-y-3">
                              {{actions.map((action) => (
                                <li key={{action}} className="rounded-lg bg-slate-950/50 p-3 text-sm text-slate-300">
                                  {{action}}
                                </li>
                              ))}}
                            </ul>
                          </aside>
                        </section>
                      </section>
                    </main>
                  );
                }}
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                .next
                out
                dist
                .env
                .env.local
                npm-debug.log*
                pnpm-debug.log*
                yarn-debug.log*
                yarn-error.log*
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                This project was generated by Aegis Project Builder.

                ## Getting started

                ```bash
                npm install
                npm run dev
                ```

                ## Validation

                ```bash
                npm run build
                ```
                """
            ),
        }

    @staticmethod
    def _vite_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "type": "module",
                  "scripts": {{
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "preview": "vite preview",
                    "typecheck": "tsc -b"
                  }},
                  "dependencies": {{
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0"
                  }},
                  "devDependencies": {{
                    "@vitejs/plugin-react": "^4.3.4",
                    "@types/react": "^19.0.1",
                    "@types/react-dom": "^19.0.1",
                    "vite": "^6.0.3",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                    <title>{title}</title>
                  </head>
                  <body>
                    <div id="root"></div>
                    <script type="module" src="/src/main.tsx"></script>
                  </body>
                </html>
                """
            ),
            "vite.config.ts": _strip(
                """
                import { defineConfig } from "vite";
                import react from "@vitejs/plugin-react";

                export default defineConfig({
                  plugins: [react()]
                });
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": true,
                    "lib": ["DOM", "DOM.Iterable", "ES2020"],
                    "allowJs": false,
                    "skipLibCheck": true,
                    "esModuleInterop": true,
                    "allowSyntheticDefaultImports": true,
                    "strict": true,
                    "forceConsistentCasingInFileNames": true,
                    "module": "ESNext",
                    "moduleResolution": "Node",
                    "resolveJsonModule": true,
                    "isolatedModules": true,
                    "noEmit": true,
                    "jsx": "react-jsx"
                  },
                  "include": ["src"],
                  "references": []
                }
                """
            ),
            "src/main.tsx": _strip(
                """
                import React from "react";
                import ReactDOM from "react-dom/client";
                import { App } from "./App";
                import "./styles.css";

                ReactDOM.createRoot(document.getElementById("root")!).render(
                  <React.StrictMode>
                    <App />
                  </React.StrictMode>
                );
                """
            ),
            "src/App.tsx": _strip(
                f"""
                const workstreams = [
                  ["Architecture", "Define data flows and API boundaries"],
                  ["Interface", "Build the first complete user path"],
                  ["Quality", "Add validation before expanding features"]
                ];

                export function App() {{
                  return (
                    <main className="shell">
                      <header className="hero">
                        <p>Aegis Vite scaffold</p>
                        <h1>{title}</h1>
                        <span>Ready for a focused first implementation pass.</span>
                      </header>

                      <section className="grid">
                        {{workstreams.map(([title, detail]) => (
                          <article key={{title}} className="panel">
                            <strong>{{title}}</strong>
                            <span>{{detail}}</span>
                          </article>
                        ))}}
                      </section>
                    </main>
                  );
                }}
                """
            ),
            "src/styles.css": _strip(
                """
                :root {
                  color: #eef4fb;
                  background: #07101a;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  min-width: 320px;
                  min-height: 100vh;
                  margin: 0;
                  background:
                    linear-gradient(135deg, rgba(31, 46, 66, 0.88), rgba(7, 14, 24, 0.96)),
                    #07101a;
                }

                .shell {
                  width: min(1120px, calc(100vw - 32px));
                  margin: 0 auto;
                  padding: 40px 0;
                }

                .hero {
                  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                  padding-bottom: 28px;
                }

                .hero p {
                  margin: 0 0 12px;
                  color: #43e08b;
                  font-size: 14px;
                }

                .hero h1 {
                  margin: 0;
                  font-size: 48px;
                  line-height: 1.04;
                  letter-spacing: 0;
                }

                .hero span {
                  display: block;
                  max-width: 660px;
                  margin-top: 16px;
                  color: #b9c5d3;
                }

                .grid {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 14px;
                  margin-top: 24px;
                }

                .panel {
                  min-height: 138px;
                  border: 1px solid rgba(255, 255, 255, 0.12);
                  border-radius: 8px;
                  background: rgba(255, 255, 255, 0.045);
                  padding: 18px;
                }

                .panel strong,
                .panel span {
                  display: block;
                }

                .panel span {
                  margin-top: 12px;
                  color: #b9c5d3;
                  line-height: 1.55;
                }

                @media (max-width: 760px) {
                  .grid {
                    grid-template-columns: 1fr;
                  }

                  .hero h1 {
                    font-size: 36px;
                  }
                }
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                .env
                .env.local
                npm-debug.log*
                pnpm-debug.log*
                yarn-debug.log*
                yarn-error.log*
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Generated by Aegis Project Builder.

                ```bash
                npm install
                npm run dev
                ```

                Validate with:

                ```bash
                npm run build
                ```
                """
            ),
        }

    @staticmethod
    def _static_html_site_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-static-site"
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        package_json = {
            "name": package_name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "description": "Dependency-free static website scaffold generated by Aegis.",
            "scripts": {
                "start": "node server.js",
                "validate": "node build.js",
            },
            "engines": {"node": ">=20"},
        }
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <meta name="description" content="{html_title} is a polished responsive business website generated by Aegis." />
                    <title>{html_title}</title>
                    <link rel="stylesheet" href="styles.css" />
                  </head>
                  <body>
                    <header class="site-header">
                      <a class="brand" href="#top" aria-label="{html_title} home">{html_title}</a>
                      <nav class="nav" aria-label="Primary navigation">
                        <a href="#services">Services</a>
                        <a href="#work">Work</a>
                        <a href="#booking">Booking</a>
                        <a href="#contact">Contact</a>
                      </nav>
                    </header>

                    <main id="top">
                      <section class="hero section">
                        <div class="hero-copy">
                          <p class="eyebrow">Premium local service</p>
                          <h1>{html_title}</h1>
                          <p class="lead">A fast, responsive website starter with clear sections, strong calls to action, and no dependency install step.</p>
                          <div class="hero-actions" aria-label="Primary actions">
                            <a class="button primary" href="#booking">Book a visit</a>
                            <a class="button secondary" href="#services">View services</a>
                          </div>
                        </div>
                        <div class="hero-panel" aria-label="Featured business highlights">
                          <span>Open today</span>
                          <strong>9:00 AM - 7:00 PM</strong>
                          <p>Walk-ins, appointments, and private sessions ready to customize.</p>
                        </div>
                      </section>

                      <section id="services" class="section">
                        <div class="section-heading">
                          <p class="eyebrow">Services</p>
                          <h2>Built for repeat customers and first-time visitors.</h2>
                        </div>
                        <div class="card-grid">
                          <article class="card">
                            <span class="card-kicker">01</span>
                            <h3>Signature Service</h3>
                            <p>Clear, premium copy block for the main offer your customer should notice first.</p>
                          </article>
                          <article class="card">
                            <span class="card-kicker">02</span>
                            <h3>Express Option</h3>
                            <p>Fast service path with simple details, pricing room, and a visible booking route.</p>
                          </article>
                          <article class="card">
                            <span class="card-kicker">03</span>
                            <h3>Custom Session</h3>
                            <p>Flexible package for longer appointments, special requests, or premium clients.</p>
                          </article>
                        </div>
                      </section>

                      <section id="work" class="section split">
                        <div>
                          <p class="eyebrow">Experience</p>
                          <h2>Clean layout, strong contrast, and sections users can scan fast.</h2>
                        </div>
                        <div class="feature-list">
                          <div>
                            <strong>Responsive</strong>
                            <span>Desktop and mobile layouts use stable spacing and readable type.</span>
                          </div>
                          <div>
                            <strong>Interactive</strong>
                            <span>Booking form feedback, active navigation, and smooth scrolling are wired in.</span>
                          </div>
                          <div>
                            <strong>Validated</strong>
                            <span>The included Node validator checks required files and JavaScript syntax.</span>
                          </div>
                        </div>
                      </section>

                      <section id="booking" class="section booking">
                        <div class="section-heading">
                          <p class="eyebrow">Booking</p>
                          <h2>Capture the first customer action.</h2>
                        </div>
                        <form class="booking-form" data-booking-form>
                          <label>
                            Name
                            <input name="name" type="text" autocomplete="name" required />
                          </label>
                          <label>
                            Service
                            <select name="service" required>
                              <option value="">Choose a service</option>
                              <option>Signature Service</option>
                              <option>Express Option</option>
                              <option>Custom Session</option>
                            </select>
                          </label>
                          <label>
                            Preferred date
                            <input name="date" type="date" required />
                          </label>
                          <button class="button primary" type="submit">Request booking</button>
                          <p class="form-status" data-form-status role="status" aria-live="polite"></p>
                        </form>
                      </section>
                    </main>

                    <footer id="contact" class="site-footer">
                      <div>
                        <strong>{html_title}</strong>
                        <span>Ready to personalize with real address, hours, images, and service pricing.</span>
                      </div>
                      <a class="button secondary" href="mailto:hello@example.com">hello@example.com</a>
                    </footer>

                    <script src="scripts.js"></script>
                  </body>
                </html>
                """
            ),
            "styles.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  --bg: #07100d;
                  --panel: #111b17;
                  --panel-strong: #17241f;
                  --text: #f4f0e8;
                  --muted: #b7b0a3;
                  --accent: #2bd77f;
                  --accent-strong: #f2c46d;
                  --border: rgba(255, 255, 255, 0.12);
                  font-family: Arial, Helvetica, sans-serif;
                }

                * {
                  box-sizing: border-box;
                }

                html {
                  scroll-behavior: smooth;
                }

                body {
                  min-width: 320px;
                  margin: 0;
                  background:
                    linear-gradient(120deg, rgba(43, 215, 127, 0.08), transparent 38%),
                    linear-gradient(180deg, #0b1411 0%, #050807 100%);
                  color: var(--text);
                }

                a {
                  color: inherit;
                  text-decoration: none;
                }

                .site-header,
                .site-footer,
                .section {
                  width: min(1120px, calc(100vw - 32px));
                  margin: 0 auto;
                }

                .site-header {
                  position: sticky;
                  top: 0;
                  z-index: 10;
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  min-height: 72px;
                  border-bottom: 1px solid var(--border);
                  background: rgba(7, 16, 13, 0.92);
                  backdrop-filter: blur(14px);
                }

                .brand {
                  font-weight: 800;
                  letter-spacing: 0;
                }

                .nav {
                  display: flex;
                  gap: 18px;
                  color: var(--muted);
                  font-size: 14px;
                }

                .nav a:hover,
                .nav a.is-active {
                  color: var(--accent);
                }

                .section {
                  padding: 76px 0;
                }

                .hero {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) 360px;
                  gap: 32px;
                  align-items: end;
                  min-height: calc(100vh - 120px);
                }

                .eyebrow {
                  margin: 0 0 12px;
                  color: var(--accent);
                  font-size: 13px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                h1,
                h2,
                h3,
                p {
                  margin-top: 0;
                }

                h1 {
                  max-width: 780px;
                  margin-bottom: 18px;
                  font-size: clamp(44px, 8vw, 92px);
                  line-height: 0.98;
                  letter-spacing: 0;
                }

                h2 {
                  max-width: 760px;
                  margin-bottom: 0;
                  font-size: clamp(30px, 4vw, 52px);
                  line-height: 1.05;
                  letter-spacing: 0;
                }

                h3 {
                  margin-bottom: 12px;
                  font-size: 20px;
                }

                .lead {
                  max-width: 620px;
                  color: var(--muted);
                  font-size: 18px;
                  line-height: 1.65;
                }

                .hero-actions {
                  display: flex;
                  flex-wrap: wrap;
                  gap: 12px;
                  margin-top: 26px;
                }

                .button {
                  display: inline-flex;
                  align-items: center;
                  justify-content: center;
                  min-height: 44px;
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  padding: 0 18px;
                  font-weight: 700;
                  cursor: pointer;
                }

                .button.primary {
                  border-color: transparent;
                  background: var(--accent);
                  color: #03100a;
                }

                .button.secondary {
                  background: rgba(255, 255, 255, 0.05);
                  color: var(--text);
                }

                .hero-panel,
                .card,
                .booking-form,
                .feature-list div {
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: rgba(255, 255, 255, 0.045);
                }

                .hero-panel {
                  padding: 24px;
                }

                .hero-panel span,
                .site-footer span,
                .feature-list span,
                .card p,
                .form-status {
                  color: var(--muted);
                  line-height: 1.55;
                }

                .hero-panel strong {
                  display: block;
                  margin: 10px 0;
                  color: var(--accent-strong);
                  font-size: 28px;
                }

                .hero-stats {
                  display: grid;
                  gap: 10px;
                  margin-top: 18px;
                }

                .hero-stat {
                  display: flex;
                  justify-content: space-between;
                  gap: 12px;
                  border-top: 1px solid var(--border);
                  padding-top: 10px;
                }

                .hero-stat strong {
                  margin: 0;
                  color: var(--text);
                  font-size: 18px;
                }

                .section-heading {
                  display: grid;
                  gap: 10px;
                  margin-bottom: 24px;
                }

                .card-grid {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 16px;
                }

                .card {
                  min-height: 210px;
                  padding: 22px;
                }

                .card-kicker {
                  display: inline-flex;
                  margin-bottom: 22px;
                  color: var(--accent-strong);
                  font-weight: 800;
                }

                .split {
                  display: grid;
                  grid-template-columns: 0.9fr 1.1fr;
                  gap: 24px;
                  align-items: start;
                }

                .feature-list {
                  display: grid;
                  gap: 12px;
                }

                .feature-list div {
                  padding: 18px;
                }

                .feature-list strong,
                .feature-list span {
                  display: block;
                }

                .feature-list span {
                  margin-top: 8px;
                }

                .booking {
                  border-top: 1px solid var(--border);
                }

                .booking-form {
                  display: grid;
                  grid-template-columns: repeat(3, minmax(0, 1fr));
                  gap: 14px;
                  padding: 18px;
                }

                label {
                  display: grid;
                  gap: 8px;
                  color: var(--muted);
                  font-size: 14px;
                }

                input,
                select {
                  min-height: 44px;
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: var(--panel);
                  color: var(--text);
                  padding: 0 12px;
                  font: inherit;
                }

                .form-status {
                  grid-column: 1 / -1;
                  min-height: 24px;
                  margin: 0;
                }

                .site-footer {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 16px;
                  border-top: 1px solid var(--border);
                  padding: 28px 0;
                }

                .site-footer strong,
                .site-footer span {
                  display: block;
                }

                .site-footer span {
                  margin-top: 6px;
                }

                @media (max-width: 860px) {
                  .site-header,
                  .site-footer {
                    align-items: flex-start;
                    flex-direction: column;
                    padding: 16px 0;
                  }

                  .nav {
                    flex-wrap: wrap;
                  }

                  .hero,
                  .split,
                  .card-grid,
                  .booking-form {
                    grid-template-columns: 1fr;
                  }

                  .hero {
                    min-height: auto;
                    padding-top: 48px;
                  }
                }
                """
            ),
            "scripts.js": _strip(
                """
                const bookingForm = document.querySelector('[data-booking-form]');
                const formStatus = document.querySelector('[data-form-status]');
                const navLinks = [...document.querySelectorAll('.nav a')];

                bookingForm?.addEventListener('submit', (event) => {
                  event.preventDefault();
                  const data = new FormData(bookingForm);
                  const name = String(data.get('name') || 'there').trim();
                  const service = String(data.get('service') || 'your service').trim();
                  formStatus.textContent = `Thanks, ${name}. Your ${service} request is ready to wire to a backend or booking provider.`;
                  bookingForm.reset();
                });

                const sectionObserver = new IntersectionObserver((entries) => {
                  const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

                  if (!visible) {
                    return;
                  }

                  navLinks.forEach((link) => {
                    link.classList.toggle('is-active', link.hash === `#${visible.target.id}`);
                  });
                }, { threshold: [0.4, 0.65] });

                document.querySelectorAll('main section[id], footer[id]').forEach((section) => {
                  sectionObserver.observe(section);
                });
                """
            ),
            "server.js": _strip(
                """
                import { createServer } from 'node:http';
                import { readFile } from 'node:fs/promises';
                import { extname, join, normalize } from 'node:path';

                const root = process.cwd();
                const port = Number.parseInt(process.env.PORT || '4173', 10);
                const contentTypes = {
                  '.html': 'text/html; charset=utf-8',
                  '.css': 'text/css; charset=utf-8',
                  '.js': 'text/javascript; charset=utf-8',
                  '.json': 'application/json; charset=utf-8'
                };

                createServer(async (request, response) => {
                  try {
                    const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);
                    const safePath = normalize(url.pathname === '/' ? '/index.html' : url.pathname).replace(/^([/\\\\])+/, '');
                    const filePath = join(root, safePath);
                    const data = await readFile(filePath);
                    response.writeHead(200, { 'content-type': contentTypes[extname(filePath)] || 'application/octet-stream' });
                    response.end(data);
                  } catch {
                    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
                    response.end('Not found');
                  }
                }).listen(port, () => {
                  console.log(`Static site available at http://127.0.0.1:${port}`);
                });
                """
            ),
            "build.js": _strip(
                """
                import { spawnSync } from 'node:child_process';
                import { existsSync, readFileSync } from 'node:fs';

                const requiredFiles = [
                  'index.html',
                  'styles.css',
                  'scripts.js',
                  'server.js'
                ];

                for (const file of requiredFiles) {
                  if (!existsSync(file)) {
                    console.error('Missing required file:', file);
                    process.exit(1);
                  }
                }

                const html = readFileSync('index.html', 'utf8');
                const css = readFileSync('styles.css', 'utf8');

                for (const required of ['id="services"', 'id="work"', 'id="booking"', 'id="contact"', 'scripts.js', 'styles.css']) {
                  if (!html.includes(required)) {
                    console.error('index.html is missing:', required);
                    process.exit(1);
                  }
                }

                for (const required of [':root', '.hero', '.card-grid', '@media']) {
                  if (!css.includes(required)) {
                    console.error('styles.css is missing:', required);
                    process.exit(1);
                  }
                }

                const checks = [
                  ['node', ['--check', 'scripts.js']],
                  ['node', ['--check', 'server.js']]
                ];

                for (const [command, args] of checks) {
                  console.log('Running:', command, ...args);
                  const completed = spawnSync(command, args, { stdio: 'inherit' });
                  if (completed.status !== 0) {
                    process.exit(completed.status ?? 1);
                  }
                }

                console.log('Static website scaffold passed validation.');
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                coverage
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free static website scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                node build.js
                ```

                ## Preview

                ```powershell
                node server.js
                ```

                Then open `http://127.0.0.1:4173`.
                """
            ),
        }

    @staticmethod
    def _browser_extension_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        manifest = {
            "manifest_version": 3,
            "name": title,
            "version": "0.1.0",
            "description": "A Manifest V3 browser extension generated by Aegis.",
            "permissions": ["activeTab", "storage", "scripting"],
            "host_permissions": ["<all_urls>"],
            "background": {
                "service_worker": "src/background.js",
                "type": "module",
            },
            "action": {
                "default_title": title,
                "default_popup": "popup/popup.html",
            },
            "options_page": "options/options.html",
            "content_scripts": [
                {
                    "matches": ["<all_urls>"],
                    "js": ["src/content.js"],
                    "run_at": "document_idle",
                }
            ],
        }
        return {
            "manifest.json": json.dumps(manifest, indent=2) + "\n",
            "src/background.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                chrome.runtime.onInstalled.addListener(async () => {
                  const existing = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
                  console.info('Aegis extension installed and settings initialized.');
                });

                chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
                  if (message?.type === 'AEGIS_GET_SETTINGS') {
                    chrome.storage.sync.get(DEFAULT_SETTINGS).then((settings) => {
                      sendResponse({ ok: true, settings });
                    });
                    return true;
                  }

                  if (message?.type === 'AEGIS_SET_BADGE') {
                    chrome.action.setBadgeText({ text: message.text ?? '' });
                    chrome.action.setBadgeBackgroundColor({ color: DEFAULT_SETTINGS.accentColor });
                    sendResponse({ ok: true });
                    return false;
                  }

                  return false;
                });
                """
            ),
            "src/content.js": _strip(
                """
                (() => {
                  const ROOT_ID = 'aegis-extension-marker';

                  const applyMarker = async () => {
                    const response = await chrome.runtime.sendMessage({ type: 'AEGIS_GET_SETTINGS' });
                    const settings = response?.settings ?? {};
                    if (!settings.enabled || document.getElementById(ROOT_ID)) {
                      return;
                    }

                    const marker = document.createElement('div');
                    marker.id = ROOT_ID;
                    marker.textContent = 'Aegis';
                    marker.style.position = 'fixed';
                    marker.style.right = '16px';
                    marker.style.bottom = '16px';
                    marker.style.zIndex = '2147483647';
                    marker.style.padding = '8px 10px';
                    marker.style.borderRadius = '8px';
                    marker.style.background = settings.accentColor ?? '#27de7d';
                    marker.style.color = '#071018';
                    marker.style.font = '600 12px system-ui, sans-serif';
                    marker.style.boxShadow = '0 12px 32px rgba(0, 0, 0, 0.24)';
                    document.documentElement.appendChild(marker);
                  };

                  applyMarker().catch((error) => {
                    console.debug('Aegis marker skipped:', error);
                  });
                })();
                """
            ),
            "popup/popup.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <title>{html_title}</title>
                    <link rel="stylesheet" href="popup.css" />
                  </head>
                  <body>
                    <main>
                      <p class="eyebrow">Browser extension</p>
                      <h1>{html_title}</h1>
                      <p id="status">Loading settings...</p>
                      <label class="toggle">
                        <input id="enabled" type="checkbox" />
                        <span>Enable page marker</span>
                      </label>
                      <button id="save">Save</button>
                    </main>
                    <script src="popup.js"></script>
                  </body>
                </html>
                """
            ),
            "popup/popup.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                  background: #071018;
                  color: #edf7f3;
                }

                body {
                  width: 320px;
                  margin: 0;
                  background: #071018;
                }

                main {
                  padding: 18px;
                }

                .eyebrow {
                  margin: 0 0 6px;
                  color: #27de7d;
                  font-size: 12px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                h1 {
                  margin: 0 0 12px;
                  font-size: 22px;
                }

                p {
                  color: #aab7c4;
                  line-height: 1.5;
                }

                .toggle {
                  display: flex;
                  gap: 10px;
                  align-items: center;
                  margin: 18px 0;
                }

                button {
                  width: 100%;
                  border: 0;
                  border-radius: 8px;
                  padding: 10px 12px;
                  background: #27de7d;
                  color: #071018;
                  font-weight: 700;
                }
                """
            ),
            "popup/popup.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                const enabledInput = document.querySelector('#enabled');
                const statusText = document.querySelector('#status');
                const saveButton = document.querySelector('#save');

                const loadSettings = async () => {
                  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  enabledInput.checked = settings.enabled;
                  statusText.textContent = settings.enabled
                    ? 'The content script marker is enabled.'
                    : 'The content script marker is disabled.';
                };

                const saveSettings = async () => {
                  await chrome.storage.sync.set({
                    ...DEFAULT_SETTINGS,
                    enabled: enabledInput.checked
                  });
                  await chrome.runtime.sendMessage({
                    type: 'AEGIS_SET_BADGE',
                    text: enabledInput.checked ? 'ON' : ''
                  });
                  statusText.textContent = 'Settings saved. Reload the page to apply content-script changes.';
                };

                saveButton.addEventListener('click', () => {
                  saveSettings().catch((error) => {
                    statusText.textContent = `Save failed: ${error.message}`;
                  });
                });

                loadSettings().catch((error) => {
                  statusText.textContent = `Load failed: ${error.message}`;
                });
                """
            ),
            "options/options.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <title>{html_title} Options</title>
                    <link rel="stylesheet" href="options.css" />
                  </head>
                  <body>
                    <main>
                      <p class="eyebrow">Extension options</p>
                      <h1>{html_title}</h1>
                      <label>
                        Accent color
                        <input id="accentColor" type="color" value="#27de7d" />
                      </label>
                      <button id="save">Save Options</button>
                      <p id="status"></p>
                    </main>
                    <script src="options.js"></script>
                  </body>
                </html>
                """
            ),
            "options/options.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                  background: #071018;
                  color: #edf7f3;
                }

                body {
                  margin: 0;
                  min-height: 100vh;
                  background: #071018;
                }

                main {
                  max-width: 720px;
                  padding: 42px;
                }

                .eyebrow {
                  color: #27de7d;
                  font-size: 12px;
                  font-weight: 700;
                  text-transform: uppercase;
                }

                label {
                  display: grid;
                  gap: 10px;
                  margin: 24px 0;
                  color: #aab7c4;
                }

                button {
                  border: 0;
                  border-radius: 8px;
                  padding: 10px 14px;
                  background: #27de7d;
                  color: #071018;
                  font-weight: 700;
                }
                """
            ),
            "options/options.js": _strip(
                """
                const DEFAULT_SETTINGS = {
                  enabled: true,
                  accentColor: '#27de7d'
                };

                const colorInput = document.querySelector('#accentColor');
                const statusText = document.querySelector('#status');
                const saveButton = document.querySelector('#save');

                const loadOptions = async () => {
                  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
                  colorInput.value = settings.accentColor;
                };

                const saveOptions = async () => {
                  await chrome.storage.sync.set({
                    ...DEFAULT_SETTINGS,
                    accentColor: colorInput.value
                  });
                  statusText.textContent = 'Options saved.';
                };

                saveButton.addEventListener('click', () => {
                  saveOptions().catch((error) => {
                    statusText.textContent = `Save failed: ${error.message}`;
                  });
                });

                loadOptions().catch((error) => {
                  statusText.textContent = `Load failed: ${error.message}`;
                });
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import json
                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path, PurePosixPath


                ROOT = Path(__file__).resolve().parent


                def resolve_extension_path(relative: str) -> Path:
                    parts = PurePosixPath(relative).parts
                    if not parts or any(part in ("", ".", "..") for part in parts):
                        raise ValueError(f"invalid extension path: {relative}")
                    path = (ROOT / Path(*parts)).resolve()
                    if not path.is_relative_to(ROOT.resolve()):
                        raise ValueError(f"extension path escapes project root: {relative}")
                    if not path.exists():
                        raise FileNotFoundError(f"manifest references missing file: {relative}")
                    return path


                def validate_manifest() -> list[Path]:
                    manifest_path = ROOT / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest.get("manifest_version") != 3:
                        raise ValueError("manifest_version must be 3")
                    if not manifest.get("name"):
                        raise ValueError("manifest name is required")
                    if not manifest.get("version"):
                        raise ValueError("manifest version is required")

                    referenced: list[Path] = []
                    background = manifest.get("background", {})
                    if "service_worker" not in background:
                        raise ValueError("background.service_worker is required")
                    referenced.append(resolve_extension_path(background["service_worker"]))

                    action = manifest.get("action", {})
                    if "default_popup" not in action:
                        raise ValueError("action.default_popup is required")
                    referenced.append(resolve_extension_path(action["default_popup"]))

                    if "options_page" in manifest:
                        referenced.append(resolve_extension_path(manifest["options_page"]))

                    for content_script in manifest.get("content_scripts", []):
                        for script in content_script.get("js", []):
                            referenced.append(resolve_extension_path(script))

                    for required in [
                        "popup/popup.js",
                        "popup/popup.css",
                        "options/options.js",
                        "options/options.css",
                    ]:
                        referenced.append(resolve_extension_path(required))

                    return referenced


                def syntax_check_javascript() -> int:
                    node = shutil.which("node")
                    if node is None:
                        print("Node.js not found; skipped JavaScript syntax checks.")
                        return 0

                    scripts = [
                        "src/background.js",
                        "src/content.js",
                        "popup/popup.js",
                        "options/options.js",
                    ]
                    for script in scripts:
                        path = resolve_extension_path(script)
                        command = [node, "--check", str(path)]
                        print("Running:", " ".join(command))
                        completed = subprocess.run(command, cwd=str(ROOT), text=True)
                        if completed.returncode != 0:
                            return completed.returncode
                    return 0


                def main() -> int:
                    try:
                        referenced = validate_manifest()
                    except Exception as exc:
                        print(f"Manifest validation failed: {exc}", file=sys.stderr)
                        return 1

                    print(f"Validated manifest with {len(referenced)} referenced file(s).")
                    code = syntax_check_javascript()
                    if code != 0:
                        return code
                    print("Browser extension scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                dist
                *.zip
                .env
                node_modules
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Browser extension scaffold generated by Aegis Project Builder.

                ## What It Includes

                - `manifest.json` using Manifest V3.
                - `src/background.js` service worker.
                - `src/content.js` page content script.
                - `popup/` browser-action popup.
                - `options/` extension options page.
                - `build.py` static validation for manifest references and JavaScript syntax.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Load In Chrome Or Edge

                1. Open the browser extensions page.
                2. Enable developer mode.
                3. Choose "Load unpacked".
                4. Select this project folder.
                """
            ),
        }

    @staticmethod
    def _vscode_extension_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        extension_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-extension"
        command_prefix = extension_name
        config_prefix = extension_name
        package_json = {
            "name": extension_name,
            "displayName": title,
            "description": "A VS Code extension generated by Aegis Project Builder.",
            "version": "0.1.0",
            "publisher": "aegis",
            "engines": {"vscode": "^1.90.0"},
            "categories": ["Other"],
            "activationEvents": [
                f"onCommand:{command_prefix}.hello",
                f"onCommand:{command_prefix}.openPanel",
            ],
            "main": "./extension.js",
            "contributes": {
                "commands": [
                    {
                        "command": f"{command_prefix}.hello",
                        "title": f"{title}: Hello",
                    },
                    {
                        "command": f"{command_prefix}.openPanel",
                        "title": f"{title}: Open Panel",
                    },
                ],
                "configuration": {
                    "title": title,
                    "properties": {
                        f"{config_prefix}.enableStatusBar": {
                            "type": "boolean",
                            "default": True,
                            "description": "Show the extension status bar item.",
                        }
                    },
                },
            },
        }
        js_title = title.replace("\\", "\\\\").replace("'", "\\'")
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "extension.js": _strip(
                f"""
                const vscode = require('vscode');

                const EXTENSION_TITLE = '{js_title}';
                const CONFIG_PREFIX = '{config_prefix}';
                const COMMAND_HELLO = '{command_prefix}.hello';
                const COMMAND_OPEN_PANEL = '{command_prefix}.openPanel';

                function activate(context) {{
                  const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
                  statusItem.text = '$(sparkle) ' + EXTENSION_TITLE;
                  statusItem.tooltip = EXTENSION_TITLE + ' is active';
                  statusItem.command = COMMAND_OPEN_PANEL;

                  const syncStatusItem = () => {{
                    const enabled = vscode.workspace
                      .getConfiguration(CONFIG_PREFIX)
                      .get('enableStatusBar', true);
                    if (enabled) {{
                      statusItem.show();
                    }} else {{
                      statusItem.hide();
                    }}
                  }};

                  context.subscriptions.push(statusItem);
                  context.subscriptions.push(
                    vscode.workspace.onDidChangeConfiguration((event) => {{
                      if (event.affectsConfiguration(CONFIG_PREFIX + '.enableStatusBar')) {{
                        syncStatusItem();
                      }}
                    }})
                  );

                  context.subscriptions.push(
                    vscode.commands.registerCommand(COMMAND_HELLO, () => {{
                      vscode.window.showInformationMessage(EXTENSION_TITLE + ' command is ready.');
                    }})
                  );

                  context.subscriptions.push(
                    vscode.commands.registerCommand(COMMAND_OPEN_PANEL, () => {{
                      openPanel(context.extensionUri);
                    }})
                  );

                  syncStatusItem();
                }}

                function openPanel(extensionUri) {{
                  const panel = vscode.window.createWebviewPanel(
                    '{extension_name}.panel',
                    EXTENSION_TITLE,
                    vscode.ViewColumn.One,
                    {{
                      enableScripts: false,
                      localResourceRoots: [extensionUri]
                    }}
                  );
                  panel.webview.html = getWebviewHtml();
                }}

                function getWebviewHtml() {{
                  return [
                    '<!doctype html>',
                    '<html lang="en">',
                    '<head>',
                    '<meta charset="utf-8" />',
                    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
                    '<style>',
                    ':root {{ color-scheme: dark; font-family: system-ui, sans-serif; background: #071018; color: #edf7f3; }}',
                    'body {{ margin: 0; padding: 28px; }}',
                    '.eyebrow {{ color: #27de7d; font-weight: 700; text-transform: uppercase; font-size: 12px; }}',
                    'h1 {{ margin: 8px 0 12px; }}',
                    'p {{ color: #aab7c4; line-height: 1.6; }}',
                    '</style>',
                    '</head>',
                    '<body>',
                    '<p class="eyebrow">VS Code extension</p>',
                    '<h1>{html_title}</h1>',
                    '<p>This panel is ready for your first command, workspace scan, or project automation feature.</p>',
                    '</body>',
                    '</html>'
                  ].join('');
                }}

                function deactivate() {{
                  // VS Code disposes registered subscriptions automatically.
                }}

                module.exports = {{
                  activate,
                  deactivate,
                  getWebviewHtml
                }};
                """
            ),
            ".vscode/launch.json": _strip(
                """
                {
                  "version": "0.2.0",
                  "configurations": [
                    {
                      "name": "Run Extension",
                      "type": "extensionHost",
                      "request": "launch",
                      "args": ["--extensionDevelopmentPath=${workspaceFolder}"]
                    }
                  ]
                }
                """
            ),
            ".vscodeignore": _strip(
                """
                .vscode/**
                .aegis/**
                build.py
                *.log
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import json
                import shutil
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent


                def validate_package() -> Path:
                    package_path = ROOT / "package.json"
                    package = json.loads(package_path.read_text(encoding="utf-8"))
                    main_value = package.get("main")
                    if not main_value:
                        raise ValueError("package.json main is required")
                    main_path = (ROOT / main_value).resolve()
                    if not main_path.is_relative_to(ROOT.resolve()) or not main_path.exists():
                        raise FileNotFoundError(f"main entry does not exist: {main_value}")
                    if not package.get("engines", {}).get("vscode"):
                        raise ValueError("engines.vscode is required")

                    activation_commands = {
                        event.removeprefix("onCommand:")
                        for event in package.get("activationEvents", [])
                        if isinstance(event, str) and event.startswith("onCommand:")
                    }
                    contributed_commands = {
                        command.get("command")
                        for command in package.get("contributes", {}).get("commands", [])
                        if isinstance(command, dict)
                    }
                    if not contributed_commands:
                        raise ValueError("at least one contributed command is required")
                    missing_activation = contributed_commands - activation_commands
                    if missing_activation:
                        raise ValueError(f"commands missing activation events: {sorted(missing_activation)}")

                    properties = package.get("contributes", {}).get("configuration", {}).get("properties", {})
                    if not properties:
                        raise ValueError("configuration properties are required")
                    return main_path


                def syntax_check(script: Path) -> int:
                    node = shutil.which("node")
                    if node is None:
                        print("Node.js not found; skipped JavaScript syntax check.")
                        return 0
                    command = [node, "--check", str(script)]
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))


                def main() -> int:
                    try:
                        main_path = validate_package()
                    except Exception as exc:
                        print(f"VS Code extension validation failed: {exc}", file=sys.stderr)
                        return 1
                    code = syntax_check(main_path)
                    if code != 0:
                        return code
                    print("VS Code extension scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                VS Code extension scaffold generated by Aegis Project Builder.

                ## What It Includes

                - `package.json` with command, activation, and settings contributions.
                - `extension.js` with command registration, status bar wiring, and a starter webview panel.
                - `.vscode/launch.json` for Extension Host debugging.
                - `build.py` static validation for package metadata and JavaScript syntax.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run In VS Code

                Open this folder in VS Code and press `F5` to launch an Extension Development Host.
                """
            ),
        }

    @staticmethod
    def _node_cli_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-node-cli"
        js_title = title.replace("\\", "\\\\").replace("'", "\\'")
        package_json = {
            "name": package_name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "description": "A package-free Node.js CLI scaffold generated by Aegis.",
            "bin": {package_name: "./bin/cli.js"},
            "scripts": {
                "start": "node bin/cli.js",
                "test": "node --test tests/commands.test.js",
                "validate": "node build.js",
            },
            "engines": {"node": ">=20"},
        }
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "bin/cli.js": _strip(
                """
                #!/usr/bin/env node

                import { runCli } from '../src/commands.js';

                const result = runCli(process.argv.slice(2));

                if (result.stdout) {
                  console.log(result.stdout);
                }

                if (result.stderr) {
                  console.error(result.stderr);
                }

                process.exitCode = result.exitCode;
                """
            ),
            "src/commands.js": _strip(
                """
                export const APP_TITLE = '__TITLE__';

                export function parseArgs(args) {
                  const options = {
                    name: 'Aegis',
                    repeat: 1,
                    uppercase: false,
                    json: false
                  };

                  for (let index = 0; index < args.length; index += 1) {
                    const token = args[index];
                    if (token === '--name') {
                      options.name = readValue(args, index, token);
                      index += 1;
                    } else if (token === '--repeat') {
                      const raw = readValue(args, index, token);
                      const repeat = Number.parseInt(raw, 10);
                      if (!Number.isInteger(repeat) || repeat < 1 || repeat > 25) {
                        throw new Error('--repeat must be an integer from 1 to 25.');
                      }
                      options.repeat = repeat;
                      index += 1;
                    } else if (token === '--uppercase') {
                      options.uppercase = true;
                    } else if (token === '--json') {
                      options.json = true;
                    } else if (token === '--help' || token === '-h') {
                      options.help = true;
                    } else {
                      throw new Error('Unknown argument: ' + token);
                    }
                  }

                  if (!options.name.trim()) {
                    throw new Error('--name cannot be empty.');
                  }

                  return options;
                }

                export function buildLines(options) {
                  const lines = [];
                  for (let index = 1; index <= options.repeat; index += 1) {
                    const text = APP_TITLE + ' ready for ' + options.name + ' (' + index + '/' + options.repeat + ')';
                    lines.push(options.uppercase ? text.toUpperCase() : text);
                  }
                  return lines;
                }

                export function runCli(args) {
                  try {
                    const options = parseArgs(args);
                    if (options.help) {
                      return {
                        exitCode: 0,
                        stdout: usage(),
                        stderr: ''
                      };
                    }

                    const lines = buildLines(options);
                    return {
                      exitCode: 0,
                      stdout: options.json
                        ? JSON.stringify({ app: APP_TITLE, lines }, null, 2)
                        : lines.join('\\n'),
                      stderr: ''
                    };
                  } catch (error) {
                    return {
                      exitCode: 2,
                      stdout: '',
                      stderr: error.message + '\\n\\n' + usage()
                    };
                  }
                }

                function readValue(args, index, option) {
                  if (index + 1 >= args.length) {
                    throw new Error(option + ' requires a value.');
                  }
                  return args[index + 1];
                }

                function usage() {
                  return [
                    APP_TITLE,
                    '',
                    'Usage:',
                    '  node bin/cli.js [--name VALUE] [--repeat 1-25] [--uppercase] [--json]',
                    '',
                    'Examples:',
                    '  node bin/cli.js --name Aegis --repeat 2',
                    '  node bin/cli.js --json'
                  ].join('\\n');
                }
                """
            ).replace("__TITLE__", js_title),
            "tests/commands.test.js": _strip(
                """
                import test from 'node:test';
                import assert from 'node:assert/strict';

                import { buildLines, parseArgs, runCli } from '../src/commands.js';

                test('parseArgs reads name, repeat, and flags', () => {
                  const options = parseArgs(['--name', 'Mercy', '--repeat', '2', '--uppercase']);
                  assert.equal(options.name, 'Mercy');
                  assert.equal(options.repeat, 2);
                  assert.equal(options.uppercase, true);
                });

                test('buildLines creates repeatable output', () => {
                  const lines = buildLines({ name: 'Aegis', repeat: 2, uppercase: false });
                  assert.equal(lines.length, 2);
                  assert.match(lines[0], /Aegis/);
                });

                test('runCli returns an error for invalid repeat values', () => {
                  const result = runCli(['--repeat', '0']);
                  assert.equal(result.exitCode, 2);
                  assert.match(result.stderr, /--repeat/);
                });
                """
            ),
            "build.js": _strip(
                """
                import { spawnSync } from 'node:child_process';
                import { existsSync } from 'node:fs';

                const requiredFiles = [
                  'package.json',
                  'bin/cli.js',
                  'src/commands.js',
                  'tests/commands.test.js'
                ];

                for (const file of requiredFiles) {
                  if (!existsSync(file)) {
                    console.error('Missing required file:', file);
                    process.exit(1);
                  }
                }

                const commands = [
                  ['node', ['--check', 'bin/cli.js']],
                  ['node', ['--check', 'src/commands.js']],
                  ['node', ['--test', 'tests/commands.test.js']],
                  ['node', ['bin/cli.js', '--name', 'Validation', '--repeat', '2']]
                ];

                for (const [command, args] of commands) {
                  console.log('Running:', command, ...args);
                  const completed = spawnSync(command, args, {
                    stdio: 'inherit'
                  });
                  if (completed.status !== 0) {
                    process.exit(completed.status ?? 1);
                  }
                }

                console.log('Node.js CLI scaffold passed validation.');
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                coverage
                dist
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Node.js CLI scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                node build.js
                ```

                ## Run

                ```powershell
                node bin/cli.js --name Aegis --repeat 2
                node bin/cli.js --json
                ```

                The package also exposes a bin entry in `package.json` for later packaging or `npm link` workflows.
                """
            ),
        }

    @staticmethod
    def _node_http_api_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-node-api"
        package_json = {
            "name": package_name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "description": "Dependency-free Node.js HTTP API scaffold generated by Aegis.",
            "scripts": {
                "start": "node src/server.js",
                "test": "node --test tests/api.test.js",
                "validate": "node build.js",
            },
            "engines": {"node": ">=20"},
        }
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "src/store.js": _strip(
                """
                export function createItemStore(initialItems = []) {
                  let nextId = 1;
                  const items = new Map();

                  for (const item of initialItems) {
                    const id = String(item.id ?? nextId++);
                    items.set(id, {
                      id,
                      name: String(item.name ?? 'Untitled item'),
                      status: String(item.status ?? 'active'),
                      createdAt: item.createdAt ?? new Date().toISOString()
                    });
                  }

                  return {
                    list() {
                      return [...items.values()];
                    },
                    find(id) {
                      return items.get(String(id)) ?? null;
                    },
                    create(payload) {
                      const name = String(payload?.name ?? '').trim();
                      if (!name) {
                        throw new Error('name is required');
                      }
                      const id = String(nextId++);
                      const item = {
                        id,
                        name,
                        status: String(payload?.status ?? 'active'),
                        createdAt: new Date().toISOString()
                      };
                      items.set(id, item);
                      return item;
                    }
                  };
                }
                """
            ),
            "src/server.js": _strip(
                """
                import { createServer } from 'node:http';
                import { pathToFileURL } from 'node:url';

                import { createItemStore } from './store.js';

                const defaultStore = createItemStore([
                  { id: 'seed-1', name: 'First API item', status: 'active' }
                ]);

                export function createApiServer({ store = defaultStore } = {}) {
                  return createServer(async (request, response) => {
                    const url = new URL(request.url ?? '/', 'http://localhost');
                    const method = request.method ?? 'GET';

                    try {
                      if (method === 'GET' && url.pathname === '/health') {
                        return sendJson(response, 200, {
                          ok: true,
                          service: 'aegis-node-api',
                          timestamp: new Date().toISOString()
                        });
                      }

                      if (method === 'GET' && url.pathname === '/api/items') {
                        return sendJson(response, 200, { items: store.list() });
                      }

                      if (method === 'POST' && url.pathname === '/api/items') {
                        const payload = await readJson(request);
                        const item = store.create(payload);
                        return sendJson(response, 201, { item });
                      }

                      const itemMatch = url.pathname.match(/^\\/api\\/items\\/([^/]+)$/);
                      if (method === 'GET' && itemMatch) {
                        const item = store.find(itemMatch[1]);
                        if (!item) {
                          return sendJson(response, 404, { error: 'item not found' });
                        }
                        return sendJson(response, 200, { item });
                      }

                      return sendJson(response, 404, { error: 'route not found' });
                    } catch (error) {
                      return sendJson(response, 400, { error: error.message });
                    }
                  });
                }

                async function readJson(request) {
                  const chunks = [];
                  let size = 0;

                  for await (const chunk of request) {
                    size += chunk.length;
                    if (size > 1_000_000) {
                      throw new Error('request body is too large');
                    }
                    chunks.push(chunk);
                  }

                  const body = Buffer.concat(chunks).toString('utf8').trim();
                  if (!body) {
                    return {};
                  }

                  try {
                    return JSON.parse(body);
                  } catch {
                    throw new Error('request body must be valid JSON');
                  }
                }

                function sendJson(response, statusCode, payload) {
                  const body = JSON.stringify(payload, null, 2);
                  response.writeHead(statusCode, {
                    'access-control-allow-origin': '*',
                    'content-type': 'application/json; charset=utf-8'
                  });
                  response.end(body);
                }

                if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
                  const port = Number.parseInt(process.env.PORT || '8788', 10);
                  createApiServer().listen(port, '127.0.0.1', () => {
                    console.log(`API listening at http://127.0.0.1:${port}`);
                  });
                }
                """
            ),
            "tests/api.test.js": _strip(
                """
                import test from 'node:test';
                import assert from 'node:assert/strict';

                import { createApiServer } from '../src/server.js';
                import { createItemStore } from '../src/store.js';

                test('health endpoint returns service status', async () => {
                  const fixture = await startServer();
                  try {
                    const response = await fetch(`${fixture.baseUrl}/health`);
                    const payload = await response.json();
                    assert.equal(response.status, 200);
                    assert.equal(payload.ok, true);
                  } finally {
                    await fixture.close();
                  }
                });

                test('item routes list, create, and fetch records', async () => {
                  const fixture = await startServer();
                  try {
                    const listResponse = await fetch(`${fixture.baseUrl}/api/items`);
                    const listPayload = await listResponse.json();
                    assert.equal(listResponse.status, 200);
                    assert.equal(listPayload.items.length, 1);

                    const createResponse = await fetch(`${fixture.baseUrl}/api/items`, {
                      method: 'POST',
                      headers: { 'content-type': 'application/json' },
                      body: JSON.stringify({ name: 'Generated item', status: 'queued' })
                    });
                    const createPayload = await createResponse.json();
                    assert.equal(createResponse.status, 201);
                    assert.equal(createPayload.item.name, 'Generated item');

                    const getResponse = await fetch(`${fixture.baseUrl}/api/items/${createPayload.item.id}`);
                    const getPayload = await getResponse.json();
                    assert.equal(getResponse.status, 200);
                    assert.equal(getPayload.item.status, 'queued');
                  } finally {
                    await fixture.close();
                  }
                });

                test('invalid JSON returns a client error', async () => {
                  const fixture = await startServer();
                  try {
                    const response = await fetch(`${fixture.baseUrl}/api/items`, {
                      method: 'POST',
                      headers: { 'content-type': 'application/json' },
                      body: '{not json'
                    });
                    const payload = await response.json();
                    assert.equal(response.status, 400);
                    assert.match(payload.error, /valid JSON/);
                  } finally {
                    await fixture.close();
                  }
                });

                async function startServer() {
                  const store = createItemStore([{ id: 'seed', name: 'Seed item', status: 'active' }]);
                  const server = createApiServer({ store });
                  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
                  const address = server.address();
                  return {
                    baseUrl: `http://${address.address}:${address.port}`,
                    close: () => new Promise((resolve, reject) => {
                      server.close((error) => (error ? reject(error) : resolve()));
                    })
                  };
                }
                """
            ),
            "build.js": _strip(
                """
                import { spawnSync } from 'node:child_process';
                import { existsSync, readFileSync } from 'node:fs';

                const requiredFiles = [
                  'package.json',
                  'src/server.js',
                  'src/store.js',
                  'tests/api.test.js'
                ];

                for (const file of requiredFiles) {
                  if (!existsSync(file)) {
                    console.error('Missing required file:', file);
                    process.exit(1);
                  }
                }

                const server = readFileSync('src/server.js', 'utf8');
                for (const marker of ['/health', '/api/items', 'createApiServer', 'readJson']) {
                  if (!server.includes(marker)) {
                    console.error('src/server.js is missing:', marker);
                    process.exit(1);
                  }
                }

                const commands = [
                  ['node', ['--check', 'src/server.js']],
                  ['node', ['--check', 'src/store.js']],
                  ['node', ['--test', 'tests/api.test.js']]
                ];

                for (const [command, args] of commands) {
                  console.log('Running:', command, ...args);
                  const completed = spawnSync(command, args, { stdio: 'inherit' });
                  if (completed.status !== 0) {
                    process.exit(completed.status ?? 1);
                  }
                }

                console.log('Node.js HTTP API scaffold passed validation.');
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                coverage
                dist
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free Node.js HTTP API scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                node build.js
                ```

                ## Run

                ```powershell
                node src/server.js
                ```

                ## Endpoints

                - `GET /health`
                - `GET /api/items`
                - `POST /api/items`
                - `GET /api/items/:id`
                """
            ),
        }

    @staticmethod
    def _node_fullstack_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = re.sub(r"[^a-z0-9-]+", "-", project_name.lower()).strip("-") or "aegis-fullstack-app"
        html_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        package_json = {
            "name": package_name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "description": "Dependency-free full-stack app scaffold generated by Aegis.",
            "scripts": {
                "start": "node src/server.js",
                "test": "node --test tests/fullstack.test.js",
                "validate": "node build.js",
            },
            "engines": {"node": ">=20"},
        }
        return {
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "public/index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <meta name="description" content="{html_title} full-stack app generated by Aegis." />
                    <title>{html_title}</title>
                    <link rel="stylesheet" href="/styles.css" />
                  </head>
                  <body>
                    <main class="app-shell">
                      <header class="hero">
                        <div>
                          <p class="eyebrow">Full-stack workspace</p>
                          <h1>{html_title}</h1>
                          <p class="lead">A no-install app starter with a static frontend, JSON-backed API, task workflow, and validation tests.</p>
                        </div>
                        <section class="status-panel" aria-label="Project status">
                          <span>Local API</span>
                          <strong data-health>Checking...</strong>
                          <p>Backed by Node.js stdlib HTTP and a JSON data file.</p>
                        </section>
                      </header>

                      <section class="workspace-grid">
                        <form class="task-form" data-task-form>
                          <div>
                            <p class="eyebrow">Create</p>
                            <h2>Add a work item</h2>
                          </div>
                          <label>
                            Title
                            <input name="title" type="text" placeholder="Design customer dashboard" required />
                          </label>
                          <label>
                            Priority
                            <select name="priority">
                              <option>High</option>
                              <option selected>Medium</option>
                              <option>Low</option>
                            </select>
                          </label>
                          <button type="submit">Add task</button>
                          <p class="form-status" data-status role="status" aria-live="polite"></p>
                        </form>

                        <section class="task-board" aria-labelledby="task-board-title">
                          <div class="board-header">
                            <div>
                              <p class="eyebrow">Dashboard</p>
                              <h2 id="task-board-title">Active tasks</h2>
                            </div>
                            <button data-refresh type="button">Refresh</button>
                          </div>
                          <div class="task-list" data-task-list></div>
                        </section>
                      </section>
                    </main>
                    <script src="/app.js"></script>
                  </body>
                </html>
                """
            ),
            "public/styles.css": _strip(
                """
                :root {
                  color-scheme: dark;
                  --bg: #071018;
                  --panel: #0f1b25;
                  --panel-strong: #142331;
                  --text: #eef6ff;
                  --muted: #aab8c6;
                  --accent: #36e08a;
                  --warning: #f4c55f;
                  --border: rgba(255, 255, 255, 0.12);
                  font-family: Arial, Helvetica, sans-serif;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  min-width: 320px;
                  min-height: 100vh;
                  margin: 0;
                  background:
                    linear-gradient(135deg, rgba(54, 224, 138, 0.12), transparent 32%),
                    linear-gradient(180deg, #08141d 0%, #04080d 100%);
                  color: var(--text);
                }

                button,
                input,
                select {
                  font: inherit;
                }

                button {
                  min-height: 42px;
                  border: 0;
                  border-radius: 8px;
                  background: var(--accent);
                  color: #04120b;
                  cursor: pointer;
                  font-weight: 800;
                  padding: 0 16px;
                }

                button.secondary,
                [data-refresh] {
                  border: 1px solid var(--border);
                  background: rgba(255, 255, 255, 0.05);
                  color: var(--text);
                }

                .app-shell {
                  width: min(1180px, calc(100vw - 32px));
                  margin: 0 auto;
                  padding: 36px 0;
                }

                .hero {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) 330px;
                  gap: 18px;
                  align-items: stretch;
                  border-bottom: 1px solid var(--border);
                  padding-bottom: 28px;
                }

                .eyebrow {
                  margin: 0 0 10px;
                  color: var(--accent);
                  font-size: 12px;
                  font-weight: 800;
                  text-transform: uppercase;
                }

                h1,
                h2,
                p {
                  margin-top: 0;
                }

                h1 {
                  max-width: 780px;
                  margin-bottom: 14px;
                  font-size: clamp(42px, 7vw, 82px);
                  line-height: 1;
                  letter-spacing: 0;
                }

                h2 {
                  margin-bottom: 0;
                  font-size: 26px;
                  letter-spacing: 0;
                }

                .lead,
                .status-panel p,
                .form-status,
                .task-meta {
                  color: var(--muted);
                  line-height: 1.55;
                }

                .status-panel,
                .task-form,
                .task-board,
                .task-card {
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: rgba(255, 255, 255, 0.045);
                }

                .status-panel {
                  padding: 20px;
                }

                .status-panel span,
                .status-panel strong {
                  display: block;
                }

                .status-panel strong {
                  margin: 10px 0;
                  color: var(--warning);
                  font-size: 24px;
                }

                .workspace-grid {
                  display: grid;
                  grid-template-columns: 360px minmax(0, 1fr);
                  gap: 18px;
                  padding-top: 24px;
                }

                .task-form,
                .task-board {
                  padding: 18px;
                }

                .task-form {
                  align-self: start;
                  display: grid;
                  gap: 14px;
                }

                label {
                  display: grid;
                  gap: 8px;
                  color: var(--muted);
                  font-size: 14px;
                }

                input,
                select {
                  min-height: 42px;
                  border: 1px solid var(--border);
                  border-radius: 8px;
                  background: var(--panel);
                  color: var(--text);
                  padding: 0 12px;
                }

                .board-header,
                .task-card {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 14px;
                }

                .task-list {
                  display: grid;
                  gap: 12px;
                  margin-top: 18px;
                }

                .task-card {
                  background: var(--panel-strong);
                  padding: 14px;
                }

                .task-card h3 {
                  margin: 0 0 6px;
                  font-size: 18px;
                }

                .task-actions {
                  display: flex;
                  gap: 8px;
                  flex-wrap: wrap;
                }

                .empty-state {
                  border: 1px dashed var(--border);
                  border-radius: 8px;
                  color: var(--muted);
                  padding: 24px;
                  text-align: center;
                }

                @media (max-width: 860px) {
                  .hero,
                  .workspace-grid {
                    grid-template-columns: 1fr;
                  }

                  .board-header,
                  .task-card {
                    align-items: flex-start;
                    flex-direction: column;
                  }
                }
                """
            ),
            "public/app.js": _strip(
                """
                const healthEl = document.querySelector('[data-health]');
                const form = document.querySelector('[data-task-form]');
                const statusEl = document.querySelector('[data-status]');
                const listEl = document.querySelector('[data-task-list]');
                const refreshButton = document.querySelector('[data-refresh]');

                async function requestJson(path, options = {}) {
                  const response = await fetch(path, {
                    ...options,
                    headers: {
                      'content-type': 'application/json',
                      ...(options.headers || {})
                    }
                  });
                  const payload = await response.json();
                  if (!response.ok) {
                    throw new Error(payload.error || 'Request failed');
                  }
                  return payload;
                }

                function renderTasks(tasks) {
                  if (!tasks.length) {
                    listEl.innerHTML = '<div class="empty-state">No tasks yet. Add the first item to begin.</div>';
                    return;
                  }

                  listEl.innerHTML = tasks.map((task) => `
                    <article class="task-card">
                      <div>
                        <h3>${escapeHtml(task.title)}</h3>
                        <p class="task-meta">${escapeHtml(task.priority)} priority · ${escapeHtml(task.status)}</p>
                      </div>
                      <div class="task-actions">
                        <button class="secondary" data-complete="${task.id}" type="button">Complete</button>
                        <button class="secondary" data-delete="${task.id}" type="button">Delete</button>
                      </div>
                    </article>
                  `).join('');
                }

                async function loadTasks() {
                  const payload = await requestJson('/api/tasks');
                  renderTasks(payload.tasks);
                }

                async function checkHealth() {
                  try {
                    const payload = await requestJson('/api/health');
                    healthEl.textContent = payload.ok ? 'Online' : 'Needs attention';
                  } catch {
                    healthEl.textContent = 'Offline';
                  }
                }

                form?.addEventListener('submit', async (event) => {
                  event.preventDefault();
                  const data = new FormData(form);
                  try {
                    await requestJson('/api/tasks', {
                      method: 'POST',
                      body: JSON.stringify({
                        title: data.get('title'),
                        priority: data.get('priority')
                      })
                    });
                    statusEl.textContent = 'Task added.';
                    form.reset();
                    await loadTasks();
                  } catch (error) {
                    statusEl.textContent = error.message;
                  }
                });

                listEl?.addEventListener('click', async (event) => {
                  const button = event.target.closest('button');
                  if (!button) {
                    return;
                  }

                  try {
                    if (button.dataset.complete) {
                      await requestJson(`/api/tasks/${button.dataset.complete}`, {
                        method: 'PATCH',
                        body: JSON.stringify({ status: 'complete' })
                      });
                    }
                    if (button.dataset.delete) {
                      await requestJson(`/api/tasks/${button.dataset.delete}`, { method: 'DELETE' });
                    }
                    await loadTasks();
                  } catch (error) {
                    statusEl.textContent = error.message;
                  }
                });

                refreshButton?.addEventListener('click', loadTasks);

                function escapeHtml(value) {
                  return String(value)
                    .replaceAll('&', '&amp;')
                    .replaceAll('<', '&lt;')
                    .replaceAll('>', '&gt;')
                    .replaceAll('"', '&quot;')
                    .replaceAll("'", '&#039;');
                }

                checkHealth();
                loadTasks().catch((error) => {
                  statusEl.textContent = error.message;
                });
                """
            ),
            "src/store.js": _strip(
                """
                import { randomUUID } from 'node:crypto';
                import { mkdir, readFile, writeFile } from 'node:fs/promises';
                import { dirname } from 'node:path';

                const defaultSeed = [
                  { id: 'seed-1', title: 'Review generated scaffold', priority: 'High', status: 'active' },
                  { id: 'seed-2', title: 'Connect real project data', priority: 'Medium', status: 'active' }
                ];

                export function createJsonStore({ filePath = 'data/tasks.json', seed = defaultSeed } = {}) {
                  let loaded = false;
                  let state = { tasks: [] };

                  async function load() {
                    if (loaded) {
                      return;
                    }

                    try {
                      const payload = JSON.parse(await readFile(filePath, 'utf8'));
                      state = { tasks: Array.isArray(payload.tasks) ? payload.tasks : [] };
                    } catch (error) {
                      if (error.code !== 'ENOENT') {
                        throw error;
                      }
                      state = {
                        tasks: seed.map((task) => ({
                          ...task,
                          createdAt: task.createdAt ?? new Date().toISOString()
                        }))
                      };
                      await save();
                    }
                    loaded = true;
                  }

                  async function save() {
                    await mkdir(dirname(filePath), { recursive: true });
                    await writeFile(filePath, JSON.stringify(state, null, 2), 'utf8');
                  }

                  return {
                    async listTasks() {
                      await load();
                      return state.tasks;
                    },
                    async createTask(payload) {
                      await load();
                      const title = String(payload?.title ?? '').trim();
                      if (!title) {
                        throw new Error('title is required');
                      }
                      const task = {
                        id: randomUUID(),
                        title,
                        priority: normalizePriority(payload?.priority),
                        status: 'active',
                        createdAt: new Date().toISOString()
                      };
                      state.tasks = [task, ...state.tasks];
                      await save();
                      return task;
                    },
                    async updateTask(id, payload) {
                      await load();
                      const index = state.tasks.findIndex((task) => task.id === id);
                      if (index === -1) {
                        return null;
                      }
                      state.tasks[index] = {
                        ...state.tasks[index],
                        title: payload?.title ? String(payload.title).trim() : state.tasks[index].title,
                        priority: payload?.priority ? normalizePriority(payload.priority) : state.tasks[index].priority,
                        status: payload?.status ? String(payload.status) : state.tasks[index].status,
                        updatedAt: new Date().toISOString()
                      };
                      await save();
                      return state.tasks[index];
                    },
                    async deleteTask(id) {
                      await load();
                      const before = state.tasks.length;
                      state.tasks = state.tasks.filter((task) => task.id !== id);
                      if (state.tasks.length === before) {
                        return false;
                      }
                      await save();
                      return true;
                    }
                  };
                }

                function normalizePriority(value) {
                  const priority = String(value ?? 'Medium');
                  return ['High', 'Medium', 'Low'].includes(priority) ? priority : 'Medium';
                }
                """
            ),
            "src/server.js": _strip(
                """
                import { createServer } from 'node:http';
                import { readFile } from 'node:fs/promises';
                import { extname, join, normalize } from 'node:path';
                import { pathToFileURL } from 'node:url';

                import { createJsonStore } from './store.js';

                const contentTypes = {
                  '.html': 'text/html; charset=utf-8',
                  '.css': 'text/css; charset=utf-8',
                  '.js': 'text/javascript; charset=utf-8',
                  '.json': 'application/json; charset=utf-8'
                };

                export function createAppServer({ store = createJsonStore(), publicDir = join(process.cwd(), 'public') } = {}) {
                  return createServer(async (request, response) => {
                    const url = new URL(request.url ?? '/', 'http://localhost');
                    const method = request.method ?? 'GET';

                    try {
                      if (url.pathname.startsWith('/api/')) {
                        return await handleApi({ method, url, request, response, store });
                      }

                      if (method !== 'GET') {
                        return sendJson(response, 405, { error: 'method not allowed' });
                      }

                      return await serveStatic(url.pathname, response, publicDir);
                    } catch (error) {
                      return sendJson(response, 500, { error: error.message });
                    }
                  });
                }

                async function handleApi({ method, url, request, response, store }) {
                  if (method === 'GET' && url.pathname === '/api/health') {
                    return sendJson(response, 200, {
                      ok: true,
                      service: 'aegis-fullstack-app',
                      timestamp: new Date().toISOString()
                    });
                  }

                  if (method === 'GET' && url.pathname === '/api/tasks') {
                    return sendJson(response, 200, { tasks: await store.listTasks() });
                  }

                  if (method === 'POST' && url.pathname === '/api/tasks') {
                    const task = await store.createTask(await readJson(request));
                    return sendJson(response, 201, { task });
                  }

                  const taskMatch = url.pathname.match(/^\\/api\\/tasks\\/([^/]+)$/);
                  if (taskMatch && method === 'PATCH') {
                    const task = await store.updateTask(taskMatch[1], await readJson(request));
                    return task
                      ? sendJson(response, 200, { task })
                      : sendJson(response, 404, { error: 'task not found' });
                  }

                  if (taskMatch && method === 'DELETE') {
                    const deleted = await store.deleteTask(taskMatch[1]);
                    return deleted
                      ? sendJson(response, 200, { ok: true })
                      : sendJson(response, 404, { error: 'task not found' });
                  }

                  return sendJson(response, 404, { error: 'route not found' });
                }

                async function serveStatic(pathname, response, publicDir) {
                  const normalized = normalize(pathname === '/' ? '/index.html' : pathname).replace(/^[/\\\\]+/, '');
                  if (normalized.startsWith('..')) {
                    return sendJson(response, 403, { error: 'forbidden' });
                  }

                  try {
                    const filePath = join(publicDir, normalized);
                    const data = await readFile(filePath);
                    response.writeHead(200, { 'content-type': contentTypes[extname(filePath)] || 'application/octet-stream' });
                    response.end(data);
                  } catch {
                    sendJson(response, 404, { error: 'file not found' });
                  }
                }

                async function readJson(request) {
                  const chunks = [];
                  let size = 0;

                  for await (const chunk of request) {
                    size += chunk.length;
                    if (size > 1_000_000) {
                      throw new Error('request body is too large');
                    }
                    chunks.push(chunk);
                  }

                  const body = Buffer.concat(chunks).toString('utf8').trim();
                  if (!body) {
                    return {};
                  }

                  try {
                    return JSON.parse(body);
                  } catch {
                    throw new Error('request body must be valid JSON');
                  }
                }

                function sendJson(response, statusCode, payload) {
                  response.writeHead(statusCode, { 'content-type': 'application/json; charset=utf-8' });
                  response.end(JSON.stringify(payload, null, 2));
                }

                if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
                  const port = Number.parseInt(process.env.PORT || '8790', 10);
                  createAppServer().listen(port, '127.0.0.1', () => {
                    console.log(`Full-stack app listening at http://127.0.0.1:${port}`);
                  });
                }
                """
            ),
            "tests/fullstack.test.js": _strip(
                """
                import test from 'node:test';
                import assert from 'node:assert/strict';
                import { mkdtemp, rm } from 'node:fs/promises';
                import { tmpdir } from 'node:os';
                import { join } from 'node:path';

                import { createAppServer } from '../src/server.js';
                import { createJsonStore } from '../src/store.js';

                test('serves the frontend shell and health endpoint', async () => {
                  const fixture = await startServer();
                  try {
                    const page = await fetch(`${fixture.baseUrl}/`);
                    const html = await page.text();
                    assert.equal(page.status, 200);
                    assert.match(html, /data-task-form/);

                    const health = await fetch(`${fixture.baseUrl}/api/health`);
                    const payload = await health.json();
                    assert.equal(health.status, 200);
                    assert.equal(payload.ok, true);
                  } finally {
                    await fixture.close();
                  }
                });

                test('task API creates, updates, lists, and deletes tasks', async () => {
                  const fixture = await startServer();
                  try {
                    const created = await fetch(`${fixture.baseUrl}/api/tasks`, {
                      method: 'POST',
                      headers: { 'content-type': 'application/json' },
                      body: JSON.stringify({ title: 'Ship validation loop', priority: 'High' })
                    });
                    const createdPayload = await created.json();
                    assert.equal(created.status, 201);
                    assert.equal(createdPayload.task.priority, 'High');

                    const updated = await fetch(`${fixture.baseUrl}/api/tasks/${createdPayload.task.id}`, {
                      method: 'PATCH',
                      headers: { 'content-type': 'application/json' },
                      body: JSON.stringify({ status: 'complete' })
                    });
                    const updatedPayload = await updated.json();
                    assert.equal(updated.status, 200);
                    assert.equal(updatedPayload.task.status, 'complete');

                    const listed = await fetch(`${fixture.baseUrl}/api/tasks`);
                    const listedPayload = await listed.json();
                    assert.equal(listed.status, 200);
                    assert.ok(listedPayload.tasks.some((task) => task.id === createdPayload.task.id));

                    const deleted = await fetch(`${fixture.baseUrl}/api/tasks/${createdPayload.task.id}`, { method: 'DELETE' });
                    const deletedPayload = await deleted.json();
                    assert.equal(deleted.status, 200);
                    assert.equal(deletedPayload.ok, true);
                  } finally {
                    await fixture.close();
                  }
                });

                async function startServer() {
                  const tempDir = await mkdtemp(join(tmpdir(), 'aegis-fullstack-'));
                  const store = createJsonStore({ filePath: join(tempDir, 'tasks.json'), seed: [] });
                  const server = createAppServer({ store, publicDir: join(process.cwd(), 'public') });
                  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
                  const address = server.address();
                  return {
                    baseUrl: `http://${address.address}:${address.port}`,
                    close: async () => {
                      await new Promise((resolve, reject) => {
                        server.close((error) => (error ? reject(error) : resolve()));
                      });
                      await rm(tempDir, { recursive: true, force: true });
                    }
                  };
                }
                """
            ),
            "build.js": _strip(
                """
                import { spawnSync } from 'node:child_process';
                import { existsSync, readFileSync } from 'node:fs';

                const requiredFiles = [
                  'package.json',
                  'public/index.html',
                  'public/styles.css',
                  'public/app.js',
                  'src/server.js',
                  'src/store.js',
                  'tests/fullstack.test.js'
                ];

                for (const file of requiredFiles) {
                  if (!existsSync(file)) {
                    console.error('Missing required file:', file);
                    process.exit(1);
                  }
                }

                const html = readFileSync('public/index.html', 'utf8');
                const server = readFileSync('src/server.js', 'utf8');
                const store = readFileSync('src/store.js', 'utf8');

                for (const marker of ['data-task-form', 'data-task-list', '/app.js']) {
                  if (!html.includes(marker)) {
                    console.error('public/index.html is missing:', marker);
                    process.exit(1);
                  }
                }

                for (const marker of ['/api/health', '/api/tasks', 'createAppServer', 'serveStatic']) {
                  if (!server.includes(marker)) {
                    console.error('src/server.js is missing:', marker);
                    process.exit(1);
                  }
                }

                for (const marker of ['createJsonStore', 'createTask', 'updateTask', 'deleteTask']) {
                  if (!store.includes(marker)) {
                    console.error('src/store.js is missing:', marker);
                    process.exit(1);
                  }
                }

                const commands = [
                  ['node', ['--check', 'public/app.js']],
                  ['node', ['--check', 'src/server.js']],
                  ['node', ['--check', 'src/store.js']],
                  ['node', ['--test', 'tests/fullstack.test.js']]
                ];

                for (const [command, args] of commands) {
                  console.log('Running:', command, ...args);
                  const completed = spawnSync(command, args, { stdio: 'inherit' });
                  if (completed.status !== 0) {
                    process.exit(completed.status ?? 1);
                  }
                }

                console.log('Node.js full-stack scaffold passed validation.');
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                data
                coverage
                dist
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free full-stack app scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                node build.js
                ```

                ## Run

                ```powershell
                node src/server.js
                ```

                Then open `http://127.0.0.1:8790`.

                ## Included Surface

                - Static frontend in `public/`
                - JSON-backed task store in `src/store.js`
                - API routes in `src/server.js`
                - Node test coverage in `tests/fullstack.test.js`
                """
            ),
        }

    @staticmethod
    def _python_stdlib_api_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        distribution_name = ProjectScaffolder._manifest_package_name(project_name)
        title = _title_from_name(project_name)
        server_module = f"{package_name}.server"
        return {
            "pyproject.toml": _strip(
                f"""
                [project]
                name = "{distribution_name}"
                version = "0.1.0"
                description = "Dependency-free Python HTTP API scaffold generated by Aegis."
                requires-python = ">=3.11"
                dependencies = []

                [tool.aegis]
                validation = "python build.py"
                """
            ),
            f"src/{package_name}/__init__.py": _strip(
                """
                __version__ = "0.1.0"
                """
            ),
            f"src/{package_name}/store.py": _strip(
                """
                from __future__ import annotations

                import json
                import threading
                import uuid
                from datetime import datetime, timezone
                from pathlib import Path
                from typing import Any


                def utc_now() -> str:
                    return datetime.now(timezone.utc).isoformat()


                class JsonItemStore:
                    def __init__(self, path: Path | str, seed: list[dict[str, Any]] | None = None):
                        self.path = Path(path)
                        self.seed = seed if seed is not None else [
                            {"id": "seed-1", "name": "First item", "status": "active", "created_at": utc_now()}
                        ]
                        self._items: list[dict[str, Any]] = []
                        self._loaded = False
                        self._lock = threading.RLock()

                    def list_items(self) -> list[dict[str, Any]]:
                        with self._lock:
                            self._load()
                            return [dict(item) for item in self._items]

                    def get_item(self, item_id: str) -> dict[str, Any] | None:
                        with self._lock:
                            self._load()
                            for item in self._items:
                                if item["id"] == item_id:
                                    return dict(item)
                            return None

                    def create_item(self, payload: dict[str, Any]) -> dict[str, Any]:
                        name = str(payload.get("name", "")).strip()
                        if not name:
                            raise ValueError("name is required")

                        with self._lock:
                            self._load()
                            item = {
                                "id": uuid.uuid4().hex,
                                "name": name,
                                "status": str(payload.get("status", "active")),
                                "created_at": utc_now(),
                            }
                            self._items.insert(0, item)
                            self._save()
                            return dict(item)

                    def update_item(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
                        with self._lock:
                            self._load()
                            for index, item in enumerate(self._items):
                                if item["id"] != item_id:
                                    continue
                                updated = dict(item)
                                if "name" in payload:
                                    name = str(payload["name"]).strip()
                                    if not name:
                                        raise ValueError("name cannot be empty")
                                    updated["name"] = name
                                if "status" in payload:
                                    updated["status"] = str(payload["status"])
                                updated["updated_at"] = utc_now()
                                self._items[index] = updated
                                self._save()
                                return dict(updated)
                            return None

                    def delete_item(self, item_id: str) -> bool:
                        with self._lock:
                            self._load()
                            before = len(self._items)
                            self._items = [item for item in self._items if item["id"] != item_id]
                            if len(self._items) == before:
                                return False
                            self._save()
                            return True

                    def _load(self) -> None:
                        if self._loaded:
                            return
                        if self.path.exists():
                            payload = json.loads(self.path.read_text(encoding="utf-8"))
                            items = payload.get("items", [])
                            self._items = items if isinstance(items, list) else []
                        else:
                            self._items = [dict(item) for item in self.seed]
                            self._save()
                        self._loaded = True

                    def _save(self) -> None:
                        self.path.parent.mkdir(parents=True, exist_ok=True)
                        self.path.write_text(json.dumps({"items": self._items}, indent=2) + "\\n", encoding="utf-8")
                """
            ),
            f"src/{package_name}/server.py": _strip(
                """
                from __future__ import annotations

                import json
                import os
                from http import HTTPStatus
                from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
                from pathlib import Path
                from urllib.parse import urlparse

                from .store import JsonItemStore


                def make_handler(store: JsonItemStore):
                    class ApiHandler(BaseHTTPRequestHandler):
                        server_version = "__TITLE__/0.1"

                        def do_OPTIONS(self) -> None:
                            self._send_json(HTTPStatus.NO_CONTENT, {})

                        def do_GET(self) -> None:
                            path = urlparse(self.path).path
                            if path == "/health":
                                return self._send_json(HTTPStatus.OK, {"ok": True, "service": "__PACKAGE__", "version": "0.1.0"})
                            if path == "/api/items":
                                return self._send_json(HTTPStatus.OK, {"items": store.list_items()})
                            item_id = self._item_id(path)
                            if item_id:
                                item = store.get_item(item_id)
                                if item is None:
                                    return self._send_json(HTTPStatus.NOT_FOUND, {"error": "item not found"})
                                return self._send_json(HTTPStatus.OK, {"item": item})
                            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

                        def do_POST(self) -> None:
                            path = urlparse(self.path).path
                            if path != "/api/items":
                                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                            try:
                                item = store.create_item(self._read_json())
                            except ValueError as error:
                                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                            return self._send_json(HTTPStatus.CREATED, {"item": item})

                        def do_PATCH(self) -> None:
                            item_id = self._item_id(urlparse(self.path).path)
                            if not item_id:
                                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                            try:
                                item = store.update_item(item_id, self._read_json())
                            except ValueError as error:
                                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                            if item is None:
                                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "item not found"})
                            return self._send_json(HTTPStatus.OK, {"item": item})

                        def do_DELETE(self) -> None:
                            item_id = self._item_id(urlparse(self.path).path)
                            if not item_id:
                                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                            if not store.delete_item(item_id):
                                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "item not found"})
                            return self._send_json(HTTPStatus.OK, {"ok": True})

                        def log_message(self, _format: str, *_args: object) -> None:
                            return

                        def _item_id(self, path: str) -> str:
                            prefix = "/api/items/"
                            return path[len(prefix):] if path.startswith(prefix) and len(path) > len(prefix) else ""

                        def _read_json(self) -> dict:
                            length = int(self.headers.get("content-length", "0") or "0")
                            if length > 1_000_000:
                                raise ValueError("request body is too large")
                            raw = self.rfile.read(length).decode("utf-8").strip() if length else "{}"
                            try:
                                payload = json.loads(raw or "{}")
                            except json.JSONDecodeError as error:
                                raise ValueError("request body must be valid JSON") from error
                            if not isinstance(payload, dict):
                                raise ValueError("request body must be a JSON object")
                            return payload

                        def _send_json(self, status: HTTPStatus, payload: dict) -> None:
                            body = b"" if status == HTTPStatus.NO_CONTENT else json.dumps(payload, indent=2).encode("utf-8")
                            self.send_response(status)
                            self.send_header("access-control-allow-origin", "*")
                            self.send_header("access-control-allow-methods", "GET, POST, PATCH, DELETE, OPTIONS")
                            self.send_header("access-control-allow-headers", "content-type")
                            self.send_header("content-type", "application/json; charset=utf-8")
                            self.send_header("content-length", str(len(body)))
                            self.end_headers()
                            if body:
                                self.wfile.write(body)

                    return ApiHandler


                def create_server(
                    host: str = "127.0.0.1",
                    port: int = 8788,
                    *,
                    store: JsonItemStore | None = None,
                    data_path: Path | str | None = None,
                ) -> ThreadingHTTPServer:
                    resolved_store = store or JsonItemStore(Path(data_path or "data/items.json"))
                    return ThreadingHTTPServer((host, port), make_handler(resolved_store))


                def main() -> int:
                    host = os.environ.get("HOST", "127.0.0.1")
                    port = int(os.environ.get("PORT", "8788"))
                    server = create_server(host=host, port=port)
                    print(f"__TITLE__ listening at http://{host}:{port}")
                    try:
                        server.serve_forever()
                    except KeyboardInterrupt:
                        pass
                    finally:
                        server.server_close()
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ).replace("__PACKAGE__", package_name).replace("__TITLE__", title),
            "tests/test_api.py": _strip(
                """
                from __future__ import annotations

                import json
                import sys
                import tempfile
                import threading
                import unittest
                import urllib.error
                import urllib.request
                from pathlib import Path

                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

                from __PACKAGE__.server import create_server
                from __PACKAGE__.store import JsonItemStore


                class ApiTests(unittest.TestCase):
                    def setUp(self) -> None:
                        self.tempdir = tempfile.TemporaryDirectory()
                        data_path = Path(self.tempdir.name) / "items.json"
                        store = JsonItemStore(data_path, seed=[])
                        self.server = create_server(port=0, store=store)
                        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                        self.thread.start()
                        host, port = self.server.server_address
                        self.base_url = f"http://{host}:{port}"

                    def tearDown(self) -> None:
                        self.server.shutdown()
                        self.server.server_close()
                        self.thread.join(timeout=5)
                        self.tempdir.cleanup()

                    def test_health_endpoint(self) -> None:
                        status, payload = self.request("/health")
                        self.assertEqual(status, 200)
                        self.assertTrue(payload["ok"])

                    def test_item_crud_flow(self) -> None:
                        status, payload = self.request("/api/items")
                        self.assertEqual(status, 200)
                        self.assertEqual(payload["items"], [])

                        status, payload = self.request("/api/items", method="POST", payload={"name": "Generated item", "status": "queued"})
                        self.assertEqual(status, 201)
                        item = payload["item"]
                        self.assertEqual(item["name"], "Generated item")

                        status, payload = self.request(f"/api/items/{item['id']}", method="PATCH", payload={"status": "complete"})
                        self.assertEqual(status, 200)
                        self.assertEqual(payload["item"]["status"], "complete")

                        status, payload = self.request(f"/api/items/{item['id']}", method="DELETE")
                        self.assertEqual(status, 200)
                        self.assertTrue(payload["ok"])

                    def test_invalid_json_returns_client_error(self) -> None:
                        request = urllib.request.Request(
                            self.base_url + "/api/items",
                            data=b"{not json",
                            method="POST",
                            headers={"content-type": "application/json"},
                        )
                        with self.assertRaises(urllib.error.HTTPError) as raised:
                            urllib.request.urlopen(request, timeout=10)
                        error = raised.exception
                        try:
                            self.assertEqual(error.code, 400)
                        finally:
                            error.close()

                    def request(self, path: str, *, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
                        data = None if payload is None else json.dumps(payload).encode("utf-8")
                        request = urllib.request.Request(
                            self.base_url + path,
                            data=data,
                            method=method,
                            headers={"content-type": "application/json"},
                        )
                        with urllib.request.urlopen(request, timeout=10) as response:
                            return response.status, json.loads(response.read().decode("utf-8"))


                if __name__ == "__main__":
                    unittest.main()
                """
            ).replace("__PACKAGE__", package_name),
            "build.py": _strip(
                """
                from __future__ import annotations

                import os
                import py_compile
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                REQUIRED = [
                    "pyproject.toml",
                    "src/__PACKAGE__/__init__.py",
                    "src/__PACKAGE__/store.py",
                    "src/__PACKAGE__/server.py",
                    "tests/test_api.py",
                ]


                def main() -> int:
                    for relative in REQUIRED:
                        path = ROOT / relative
                        if not path.exists():
                            print(f"Missing required file: {relative}", file=sys.stderr)
                            return 1
                        if path.suffix == ".py":
                            py_compile.compile(str(path), doraise=True)

                    env = os.environ.copy()
                    src = str(ROOT / "src")
                    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
                    completed = subprocess.run(
                        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                        cwd=ROOT,
                        env=env,
                    )
                    if completed.returncode != 0:
                        return completed.returncode
                    print("Python stdlib HTTP API scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ).replace("__PACKAGE__", package_name),
            ".gitignore": _strip(
                """
                .venv
                __pycache__
                .pytest_cache
                data
                *.pyc
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free Python HTTP API scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run

                ```powershell
                $env:PYTHONPATH = "src"
                python -m {server_module}
                ```

                ## Endpoints

                - `GET /health`
                - `GET /api/items`
                - `POST /api/items`
                - `PATCH /api/items/:id`
                - `DELETE /api/items/:id`
                """
            ),
        }

    @staticmethod
    def _powershell_module_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        module_name = "".join(word[:1].upper() + word[1:] for word in re.split(r"[-_\s]+", project_name) if word)
        module_name = re.sub(r"[^A-Za-z0-9]", "", module_name) or "AegisAutomation"
        if not re.match(r"^[A-Za-z]", module_name):
            module_name = f"Aegis{module_name}"
        module_guid = str(uuid.uuid4())
        return {
            f"src/{module_name}.psm1": _strip(
                """
                Set-StrictMode -Version Latest

                function Write-AegisLog {
                    [CmdletBinding()]
                    param(
                        [Parameter(Mandatory = $true)]
                        [ValidateNotNullOrEmpty()]
                        [string]$Message,

                        [ValidateSet('Info', 'Warning', 'Error')]
                        [string]$Level = 'Info'
                    )

                    $entry = [pscustomobject]@{
                        Timestamp = (Get-Date).ToUniversalTime().ToString('o')
                        Level = $Level
                        Message = $Message
                    }
                    Write-Host ('[{0}] {1}' -f $entry.Level, $entry.Message)
                    return $entry
                }

                function Get-AegisSystemSummary {
                    [CmdletBinding()]
                    param(
                        [string]$Path = (Get-Location).Path
                    )

                    $resolvedPath = $Path
                    if (Test-Path -LiteralPath $Path) {
                        $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
                    }

                    return [pscustomobject]@{
                        ComputerName = $env:COMPUTERNAME
                        UserName = $env:USERNAME
                        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
                        TargetPath = $resolvedPath
                        Timestamp = (Get-Date).ToUniversalTime().ToString('o')
                    }
                }

                function Test-AegisPath {
                    [CmdletBinding()]
                    param(
                        [Parameter(Mandatory = $true)]
                        [ValidateNotNullOrEmpty()]
                        [string]$Path,

                        [switch]$Create
                    )

                    $exists = Test-Path -LiteralPath $Path
                    if (-not $exists -and $Create) {
                        [void](New-Item -ItemType Directory -Path $Path -Force)
                        $exists = $true
                    }

                    return [pscustomobject]@{
                        Path = $Path
                        Exists = $exists
                        Created = [bool]($Create -and $exists)
                    }
                }

                Export-ModuleMember -Function Write-AegisLog, Get-AegisSystemSummary, Test-AegisPath
                """
            ),
            f"src/{module_name}.psd1": _strip(
                """
                @{
                    RootModule = '__MODULE__.psm1'
                    ModuleVersion = '0.1.0'
                    GUID = '__GUID__'
                    Author = 'Aegis Project Builder'
                    CompanyName = 'Aegis'
                    Copyright = '(c) Aegis. All rights reserved.'
                    Description = 'Dependency-free PowerShell automation module generated by Aegis.'
                    PowerShellVersion = '5.1'
                    FunctionsToExport = @('Write-AegisLog', 'Get-AegisSystemSummary', 'Test-AegisPath')
                    CmdletsToExport = @()
                    VariablesToExport = @()
                    AliasesToExport = @()
                }
                """
            ).replace("__MODULE__", module_name).replace("__GUID__", module_guid),
            f"scripts/Invoke-{module_name}.ps1": _strip(
                r"""
                [CmdletBinding()]
                param(
                    [string]$Path = (Get-Location).Path,
                    [switch]$EnsurePath
                )

                $ErrorActionPreference = 'Stop'
                Set-StrictMode -Version Latest

                $manifestPath = Join-Path $PSScriptRoot '..\src\__MODULE__.psd1'
                Import-Module $manifestPath -Force

                if ($EnsurePath) {
                    Test-AegisPath -Path $Path -Create | Format-List | Out-String | Write-Host
                }

                $summary = Get-AegisSystemSummary -Path $Path
                Write-AegisLog -Message ('Loaded __MODULE__ for {0}' -f $summary.TargetPath) -Level Info | Out-Null
                $summary | ConvertTo-Json -Depth 4
                """
            ).replace("__MODULE__", module_name),
            "tests/Smoke.Tests.ps1": _strip(
                r"""
                $ErrorActionPreference = 'Stop'
                Set-StrictMode -Version Latest

                $moduleRoot = Join-Path $PSScriptRoot '..\src'
                $manifestPath = Join-Path $moduleRoot '__MODULE__.psd1'
                Test-ModuleManifest -Path $manifestPath | Out-Null
                Import-Module $manifestPath -Force

                $requiredCommands = @(
                    'Write-AegisLog',
                    'Get-AegisSystemSummary',
                    'Test-AegisPath'
                )
                foreach ($commandName in $requiredCommands) {
                    if (-not (Get-Command -Name $commandName -ErrorAction SilentlyContinue)) {
                        throw ('Missing exported command: {0}' -f $commandName)
                    }
                }

                $summary = Get-AegisSystemSummary -Path $PSScriptRoot
                if (-not $summary.PowerShellVersion) {
                    throw 'Expected PowerShell version in system summary.'
                }

                $tempPath = Join-Path ([System.IO.Path]::GetTempPath()) ('aegis-module-' + [guid]::NewGuid().ToString('N'))
                $pathResult = Test-AegisPath -Path $tempPath -Create
                try {
                    if (-not $pathResult.Exists) {
                        throw 'Expected Test-AegisPath to create the requested directory.'
                    }
                }
                finally {
                    if (Test-Path -LiteralPath $tempPath) {
                        Remove-Item -LiteralPath $tempPath -Recurse -Force
                    }
                }

                $logEntry = Write-AegisLog -Message 'smoke' -Level Info
                if ($logEntry.Message -ne 'smoke') {
                    throw 'Expected Write-AegisLog to return the logged message.'
                }

                Write-Host 'PowerShell module smoke tests passed.'
                """
            ).replace("__MODULE__", module_name),
            "build.ps1": _strip(
                r"""
                [CmdletBinding()]
                param()

                $ErrorActionPreference = 'Stop'
                Set-StrictMode -Version Latest

                $root = Split-Path -Parent $MyInvocation.MyCommand.Path
                $requiredFiles = @(
                    'src\__MODULE__.psm1',
                    'src\__MODULE__.psd1',
                    'scripts\Invoke-__MODULE__.ps1',
                    'tests\Smoke.Tests.ps1'
                )

                foreach ($relativePath in $requiredFiles) {
                    $path = Join-Path $root $relativePath
                    if (-not (Test-Path -LiteralPath $path)) {
                        throw ('Missing required file: {0}' -f $relativePath)
                    }
                }

                foreach ($relativePath in $requiredFiles) {
                    $path = Join-Path $root $relativePath
                    $content = Get-Content -LiteralPath $path -Raw
                    $parseErrors = $null
                    [void][System.Management.Automation.PSParser]::Tokenize($content, [ref]$parseErrors)
                    if ($parseErrors -and $parseErrors.Count -gt 0) {
                        $details = ($parseErrors | ForEach-Object { '{0}:{1} {2}' -f $_.Token.StartLine, $_.Token.StartColumn, $_.Message }) -join [Environment]::NewLine
                        throw ('PowerShell parser errors in {0}:{1}{2}' -f $relativePath, [Environment]::NewLine, $details)
                    }
                }

                $manifestPath = Join-Path $root 'src\__MODULE__.psd1'
                Test-ModuleManifest -Path $manifestPath | Out-Null
                & (Join-Path $root 'tests\Smoke.Tests.ps1')

                Write-Host 'PowerShell module scaffold passed validation.'
                """
            ).replace("__MODULE__", module_name),
            ".gitignore": _strip(
                """
                *.log
                *.tmp
                .env
                .vscode
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free PowerShell automation module scaffold generated by Aegis Project Builder.

                ## Validate

                ```powershell
                powershell -NoProfile -ExecutionPolicy Bypass -File .\\build.ps1
                ```

                ## Run

                ```powershell
                powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\Invoke-{module_name}.ps1 -Path . -EnsurePath
                ```

                ## Exports

                - `Write-AegisLog`
                - `Get-AegisSystemSummary`
                - `Test-AegisPath`
                """
            ),
        }

    @staticmethod
    def _python_cli_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        distribution_name = ProjectScaffolder._manifest_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "pyproject.toml": _strip(
                f"""
                [build-system]
                requires = ["setuptools>=69", "wheel"]
                build-backend = "setuptools.build_meta"

                [project]
                name = "{distribution_name}"
                version = "0.1.0"
                description = "A Python CLI scaffold generated by Aegis."
                readme = "README.md"
                requires-python = ">=3.11"
                dependencies = []

                [project.optional-dependencies]
                dev = ["pytest>=8.0"]

                [project.scripts]
                {package_name} = "{package_name}.main:main"

                [tool.pytest.ini_options]
                testpaths = ["tests"]
                pythonpath = ["src"]
                """
            ),
            f"src/{package_name}/__init__.py": '__all__ = ["__version__"]\n__version__ = "0.1.0"\n',
            f"src/{package_name}/main.py": _strip(
                f"""
                from __future__ import annotations

                import argparse


                def build_parser() -> argparse.ArgumentParser:
                    parser = argparse.ArgumentParser(prog="{package_name}", description="{title} command line interface")
                    parser.add_argument("--name", default="Aegis", help="Name to greet.")
                    return parser


                def run(name: str) -> str:
                    return f"Hello, {{name}}. {title} is ready."


                def main() -> int:
                    args = build_parser().parse_args()
                    print(run(args.name))
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            "tests/test_smoke.py": _strip(
                f"""
                from {package_name}.main import run


                def test_run_returns_message() -> None:
                    assert "Aegis" in run("Aegis")
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import compileall
                import importlib
                import pathlib
                import sys


                ROOT = pathlib.Path(__file__).resolve().parent
                SRC = ROOT / "src"
                TESTS = ROOT / "tests"


                def main() -> int:
                    sys.path.insert(0, str(SRC))
                    if not compileall.compile_dir(str(SRC), quiet=1):
                        raise SystemExit("Source compilation failed.")
                    if TESTS.exists() and not compileall.compile_dir(str(TESTS), quiet=1):
                        raise SystemExit("Test compilation failed.")
                    module = importlib.import_module("{package_name}.main")
                    message = module.run("Aegis")
                    if "Aegis" not in message:
                        raise SystemExit("Smoke check failed.")
                    print("Python CLI scaffold passed validation.")
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                .venv
                __pycache__
                .pytest_cache
                .mypy_cache
                dist
                build
                *.egg-info
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Generated by Aegis Project Builder.

                ## Setup

                ```bash
                python -m pip install -e .[dev]
                ```

                ## Run

                ```bash
                {package_name} --name Aegis
                ```

                ## Validation

                ```bash
                python build.py
                ```

                Optional pytest smoke tests are included for projects that install the `dev` extra.
                """
            ),
        }

    @staticmethod
    def _python_tkinter_desktop_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        distribution_name = ProjectScaffolder._manifest_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "pyproject.toml": _strip(
                f"""
                [build-system]
                requires = ["setuptools>=69", "wheel"]
                build-backend = "setuptools.build_meta"

                [project]
                name = "{distribution_name}"
                version = "0.1.0"
                description = "A dependency-light Python desktop app scaffold generated by Aegis."
                readme = "README.md"
                requires-python = ">=3.11"
                dependencies = []

                [project.scripts]
                {package_name} = "{package_name}.main:main"
                """
            ),
            f"src/{package_name}/__init__.py": _strip(
                """
                __all__ = ["__version__"]
                __version__ = "0.1.0"
                """
            ),
            f"src/{package_name}/state.py": _strip(
                """
                from __future__ import annotations

                import json
                from dataclasses import asdict, dataclass
                from pathlib import Path
                from typing import Any


                @dataclass(slots=True)
                class TaskItem:
                    id: int
                    title: str
                    done: bool = False


                class TaskStore:
                    def __init__(self, items: list[TaskItem] | None = None) -> None:
                        self.items = list(items or [])

                    def add(self, title: str) -> TaskItem:
                        cleaned = title.strip()
                        if not cleaned:
                            raise ValueError("title is required")
                        next_id = max((item.id for item in self.items), default=0) + 1
                        item = TaskItem(id=next_id, title=cleaned)
                        self.items.append(item)
                        return item

                    def toggle(self, item_id: int) -> TaskItem:
                        for item in self.items:
                            if item.id == item_id:
                                item.done = not item.done
                                return item
                        raise KeyError(f"task not found: {item_id}")

                    def remove(self, item_id: int) -> None:
                        before = len(self.items)
                        self.items = [item for item in self.items if item.id != item_id]
                        if len(self.items) == before:
                            raise KeyError(f"task not found: {item_id}")

                    def remaining_count(self) -> int:
                        return sum(1 for item in self.items if not item.done)

                    def to_json(self) -> list[dict[str, Any]]:
                        return [asdict(item) for item in self.items]

                    @classmethod
                    def from_json(cls, payload: list[dict[str, Any]]) -> "TaskStore":
                        return cls(
                            [
                                TaskItem(
                                    id=int(row["id"]),
                                    title=str(row["title"]),
                                    done=bool(row.get("done", False)),
                                )
                                for row in payload
                            ]
                        )

                    @classmethod
                    def load(cls, path: Path) -> "TaskStore":
                        if not path.exists():
                            return cls()
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        if not isinstance(payload, list):
                            raise ValueError("task store file must contain a list")
                        return cls.from_json(payload)

                    def save(self, path: Path) -> None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
                """
            ),
            f"src/{package_name}/app.py": _strip(
                f"""
                from __future__ import annotations

                from pathlib import Path
                import tkinter as tk
                from tkinter import messagebox, ttk

                from .state import TaskItem, TaskStore


                APP_TITLE = "{title}"
                DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "tasks.json"


                class DesktopApp:
                    def __init__(self, root: tk.Tk) -> None:
                        self.root = root
                        self.store = TaskStore.load(DATA_PATH)
                        self.selected_id: int | None = None

                        root.title(APP_TITLE)
                        root.geometry("720x460")
                        root.minsize(560, 360)

                        self.title_var = tk.StringVar()
                        self.status_var = tk.StringVar()

                        self._build_layout()
                        self._refresh()

                    def _build_layout(self) -> None:
                        self.root.columnconfigure(0, weight=1)
                        self.root.rowconfigure(1, weight=1)

                        header = ttk.Frame(self.root, padding=(16, 14, 16, 8))
                        header.grid(row=0, column=0, sticky="ew")
                        header.columnconfigure(0, weight=1)

                        title = ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 18, "bold"))
                        title.grid(row=0, column=0, sticky="w")

                        entry = ttk.Entry(header, textvariable=self.title_var)
                        entry.grid(row=1, column=0, sticky="ew", pady=(12, 0))
                        entry.bind("<Return>", lambda _event: self.add_task())

                        add_button = ttk.Button(header, text="Add", command=self.add_task)
                        add_button.grid(row=1, column=1, padx=(10, 0), pady=(12, 0))

                        body = ttk.Frame(self.root, padding=(16, 8, 16, 8))
                        body.grid(row=1, column=0, sticky="nsew")
                        body.columnconfigure(0, weight=1)
                        body.rowconfigure(0, weight=1)

                        self.listbox = tk.Listbox(body, activestyle="none", borderwidth=0, highlightthickness=1)
                        self.listbox.grid(row=0, column=0, sticky="nsew")
                        self.listbox.bind("<<ListboxSelect>>", self._on_select)

                        actions = ttk.Frame(body)
                        actions.grid(row=0, column=1, sticky="ns", padx=(12, 0))

                        ttk.Button(actions, text="Toggle", command=self.toggle_selected).grid(row=0, column=0, sticky="ew")
                        ttk.Button(actions, text="Remove", command=self.remove_selected).grid(row=1, column=0, sticky="ew", pady=(8, 0))
                        ttk.Button(actions, text="Save", command=self.save).grid(row=2, column=0, sticky="ew", pady=(8, 0))

                        footer = ttk.Label(self.root, textvariable=self.status_var, padding=(16, 8, 16, 14))
                        footer.grid(row=2, column=0, sticky="ew")

                    def _on_select(self, _event: object) -> None:
                        selection = self.listbox.curselection()
                        if not selection:
                            self.selected_id = None
                            return
                        index = selection[0]
                        self.selected_id = self.store.items[index].id

                    def _task_label(self, item: TaskItem) -> str:
                        mark = "[x]" if item.done else "[ ]"
                        return f"{{mark}} {{item.title}}"

                    def _refresh(self) -> None:
                        self.listbox.delete(0, tk.END)
                        for item in self.store.items:
                            self.listbox.insert(tk.END, self._task_label(item))
                        remaining = self.store.remaining_count()
                        self.status_var.set(f"{{len(self.store.items)}} tasks, {{remaining}} remaining")

                    def add_task(self) -> None:
                        try:
                            self.store.add(self.title_var.get())
                        except ValueError as exc:
                            messagebox.showwarning(APP_TITLE, str(exc))
                            return
                        self.title_var.set("")
                        self.save(show_message=False)
                        self._refresh()

                    def toggle_selected(self) -> None:
                        if self.selected_id is None:
                            return
                        self.store.toggle(self.selected_id)
                        self.save(show_message=False)
                        self._refresh()

                    def remove_selected(self) -> None:
                        if self.selected_id is None:
                            return
                        self.store.remove(self.selected_id)
                        self.selected_id = None
                        self.save(show_message=False)
                        self._refresh()

                    def save(self, *, show_message: bool = True) -> None:
                        self.store.save(DATA_PATH)
                        if show_message:
                            messagebox.showinfo(APP_TITLE, f"Saved {{DATA_PATH}}")


                def run_app() -> int:
                    root = tk.Tk()
                    DesktopApp(root)
                    root.mainloop()
                    return 0
                """
            ),
            f"src/{package_name}/main.py": _strip(
                """
                from __future__ import annotations

                from .app import run_app


                def main() -> int:
                    return run_app()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            "tests/test_state.py": _strip(
                f"""
                from pathlib import Path
                import sys
                import tempfile
                import unittest

                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

                from {package_name}.state import TaskStore


                class TaskStoreTests(unittest.TestCase):
                    def test_store_add_toggle_and_remove(self) -> None:
                        store = TaskStore()
                        item = store.add("Write validation")
                        self.assertEqual(item.id, 1)
                        self.assertEqual(store.remaining_count(), 1)

                        store.toggle(item.id)
                        self.assertEqual(store.remaining_count(), 0)

                        store.remove(item.id)
                        self.assertEqual(store.items, [])

                    def test_store_round_trips_json_file(self) -> None:
                        with tempfile.TemporaryDirectory() as tempdir:
                            path = Path(tempdir) / "tasks.json"
                            store = TaskStore()
                            store.add("Persist data")
                            store.save(path)

                            loaded = TaskStore.load(path)
                            self.assertEqual(loaded.to_json(), store.to_json())


                if __name__ == "__main__":
                    unittest.main()
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import compileall
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent


                def main() -> int:
                    if not compileall.compile_dir(str(ROOT / "src"), force=True, quiet=1):
                        return 1

                    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                __pycache__
                *.pyc
                .venv
                .pytest_cache
                data/*.json
                dist
                build
                *.egg-info
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-light Python desktop app generated by Aegis Project Builder.

                ## What It Includes

                - Tkinter GUI in `src/{package_name}/app.py`.
                - Testable task state and JSON persistence in `src/{package_name}/state.py`.
                - Unit tests that validate app logic without launching a window.
                - `build.py` that compiles source files and runs the test suite.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run

                ```powershell
                $env:PYTHONPATH = "src"
                python -m {package_name}.main
                ```
                """
            ),
        }

    @staticmethod
    def _fastapi_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        distribution_name = ProjectScaffolder._manifest_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "pyproject.toml": _strip(
                f"""
                [build-system]
                requires = ["setuptools>=69", "wheel"]
                build-backend = "setuptools.build_meta"

                [project]
                name = "{distribution_name}"
                version = "0.1.0"
                description = "A FastAPI service scaffold generated by Aegis."
                readme = "README.md"
                requires-python = ">=3.11"
                dependencies = [
                  "fastapi>=0.115",
                  "pydantic-settings>=2.6",
                  "uvicorn[standard]>=0.30"
                ]

                [project.optional-dependencies]
                dev = ["httpx>=0.27", "pytest>=8.0"]

                [tool.pytest.ini_options]
                testpaths = ["tests"]
                pythonpath = ["src"]
                """
            ),
            f"src/{package_name}/__init__.py": '__all__ = ["__version__"]\n__version__ = "0.1.0"\n',
            f"src/{package_name}/settings.py": _strip(
                f"""
                from __future__ import annotations

                from pydantic_settings import BaseSettings, SettingsConfigDict


                class Settings(BaseSettings):
                    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

                    app_name: str = "{title}"
                    environment: str = "development"
                    api_prefix: str = "/api"


                def get_settings() -> Settings:
                    return Settings()
                """
            ),
            f"src/{package_name}/main.py": _strip(
                f"""
                from __future__ import annotations

                from fastapi import FastAPI

                from .settings import get_settings


                def create_app() -> FastAPI:
                    settings = get_settings()
                    app = FastAPI(title=settings.app_name, version="0.1.0")

                    @app.get("/health")
                    async def health() -> dict[str, str]:
                        return {{"status": "ok", "service": settings.app_name, "environment": settings.environment}}

                    @app.get(f"{{settings.api_prefix}}/status")
                    async def api_status() -> dict[str, str]:
                        return {{"status": "ready"}}

                    return app


                app = create_app()
                """
            ),
            "tests/test_health.py": _strip(
                f"""
                from fastapi.testclient import TestClient

                from {package_name}.main import create_app


                def test_health_endpoint() -> None:
                    client = TestClient(create_app())
                    response = client.get("/health")

                    assert response.status_code == 200
                    assert response.json()["status"] == "ok"
                """
            ),
            ".env.example": _strip(
                f"""
                APP_NAME="{title}"
                ENVIRONMENT=development
                API_PREFIX=/api
                """
            ),
            ".gitignore": _strip(
                """
                .venv
                __pycache__
                .pytest_cache
                .mypy_cache
                dist
                build
                *.egg-info
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                FastAPI service generated by Aegis Project Builder.

                ## Setup

                ```bash
                python -m pip install -e .[dev]
                ```

                ## Run

                ```bash
                uvicorn {package_name}.main:app --reload
                ```

                ## Validation

                ```bash
                python -m pytest
                ```
                """
            ),
        }

    @staticmethod
    def _express_ts_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "type": "module",
                  "scripts": {{
                    "dev": "tsx watch src/server.ts",
                    "build": "tsc -p tsconfig.json",
                    "start": "node dist/server.js",
                    "typecheck": "tsc -p tsconfig.json --noEmit"
                  }},
                  "dependencies": {{
                    "dotenv": "^16.4.7",
                    "express": "^4.21.2"
                  }},
                  "devDependencies": {{
                    "@types/express": "^5.0.0",
                    "@types/node": "^22.10.1",
                    "tsx": "^4.19.2",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2022",
                    "module": "NodeNext",
                    "moduleResolution": "NodeNext",
                    "strict": true,
                    "esModuleInterop": true,
                    "skipLibCheck": true,
                    "forceConsistentCasingInFileNames": true,
                    "outDir": "dist",
                    "rootDir": "src"
                  },
                  "include": ["src/**/*.ts"]
                }
                """
            ),
            "src/config.ts": _strip(
                f"""
                import "dotenv/config";

                export const config = {{
                  appName: process.env.APP_NAME ?? "{title}",
                  nodeEnv: process.env.NODE_ENV ?? "development",
                  port: Number(process.env.PORT ?? 3000)
                }};
                """
            ),
            "src/routes/health.ts": _strip(
                """
                import { Router } from "express";

                import { config } from "../config.js";

                export const healthRouter = Router();

                healthRouter.get("/health", (_request, response) => {
                  response.json({
                    status: "ok",
                    service: config.appName,
                    environment: config.nodeEnv
                  });
                });
                """
            ),
            "src/server.ts": _strip(
                """
                import express from "express";

                import { config } from "./config.js";
                import { healthRouter } from "./routes/health.js";

                export function createApp() {
                  const app = express();

                  app.use(express.json({ limit: "1mb" }));
                  app.use(healthRouter);
                  app.get("/api/status", (_request, response) => {
                    response.json({ status: "ready" });
                  });

                  return app;
                }

                if (process.env.NODE_ENV !== "test") {
                  createApp().listen(config.port, () => {
                    console.log(`${config.appName} listening on http://127.0.0.1:${config.port}`);
                  });
                }
                """
            ),
            ".env.example": _strip(
                f"""
                APP_NAME="{title}"
                NODE_ENV=development
                PORT=3000
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                .env
                npm-debug.log*
                pnpm-debug.log*
                yarn-debug.log*
                yarn-error.log*
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Express TypeScript API generated by Aegis Project Builder.

                ```bash
                npm install
                npm run dev
                ```

                Validate with:

                ```bash
                npm run build
                ```
                """
            ),
        }

    @staticmethod
    def _sqlite_python_db_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "schema.sql": _strip(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS app_metadata (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS inventory_items (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL UNIQUE,
                  category TEXT NOT NULL DEFAULT 'general',
                  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
                  notes TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_inventory_items_category
                  ON inventory_items(category);

                CREATE INDEX IF NOT EXISTS idx_inventory_items_status
                  ON inventory_items(status);

                CREATE TRIGGER IF NOT EXISTS trg_inventory_items_updated_at
                AFTER UPDATE ON inventory_items
                FOR EACH ROW
                BEGIN
                  UPDATE inventory_items SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;

                CREATE VIEW IF NOT EXISTS inventory_summary AS
                SELECT
                  category,
                  COUNT(*) AS item_count,
                  COALESCE(SUM(quantity), 0) AS total_quantity
                FROM inventory_items
                WHERE status = 'active'
                GROUP BY category;
                """
            ),
            "seed.sql": _strip(
                f"""
                INSERT OR REPLACE INTO app_metadata(key, value)
                VALUES ('project_name', '{title}');

                INSERT OR IGNORE INTO inventory_items(name, category, quantity, notes)
                VALUES
                  ('Starter Record', 'general', 3, 'Generated seed row used by smoke tests.'),
                  ('Backlog Item', 'planning', 7, 'Represents work waiting for a feature pass.'),
                  ('Validated Item', 'quality', 1, 'Confirms the schema, seed, and reporting path are active.');
                """
            ),
            "queries/report.sql": _strip(
                """
                SELECT
                  category,
                  item_count,
                  total_quantity
                FROM inventory_summary
                ORDER BY category;
                """
            ),
            f"src/{package_name}/__init__.py": _strip(
                """
                from .database import DEFAULT_DB, add_item, initialize_database, list_items, summary

                __all__ = [
                    "DEFAULT_DB",
                    "add_item",
                    "initialize_database",
                    "list_items",
                    "summary",
                ]
                """
            ),
            f"src/{package_name}/database.py": _strip(
                """
                from __future__ import annotations

                import sqlite3
                from contextlib import closing
                from pathlib import Path
                from typing import Any


                ROOT = Path(__file__).resolve().parents[2]
                SCHEMA_PATH = ROOT / "schema.sql"
                SEED_PATH = ROOT / "seed.sql"
                DEFAULT_DB = ROOT / "data" / "app.sqlite3"


                def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
                    path = Path(db_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    connection = sqlite3.connect(path)
                    connection.row_factory = sqlite3.Row
                    connection.execute("PRAGMA foreign_keys = ON")
                    return connection


                def run_script(connection: sqlite3.Connection, script_path: Path) -> None:
                    connection.executescript(script_path.read_text(encoding="utf-8"))


                def initialize_database(
                    db_path: Path | str = DEFAULT_DB,
                    *,
                    seed: bool = True,
                    reset: bool = False,
                ) -> Path:
                    path = Path(db_path)
                    if reset and path.exists():
                        path.unlink()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with closing(connect(path)) as connection:
                        run_script(connection, SCHEMA_PATH)
                        if seed:
                            run_script(connection, SEED_PATH)
                        connection.commit()
                    return path


                def add_item(
                    db_path: Path | str,
                    name: str,
                    *,
                    category: str = "general",
                    quantity: int = 0,
                    notes: str = "",
                ) -> int:
                    if not name.strip():
                        raise ValueError("name is required")
                    if quantity < 0:
                        raise ValueError("quantity must be greater than or equal to zero")
                    with closing(connect(db_path)) as connection:
                        cursor = connection.execute(
                            "INSERT INTO inventory_items(name, category, quantity, notes) VALUES (?, ?, ?, ?)",
                            (name.strip(), category.strip() or "general", quantity, notes.strip()),
                        )
                        connection.commit()
                        return int(cursor.lastrowid)


                def list_items(db_path: Path | str = DEFAULT_DB) -> list[dict[str, Any]]:
                    with closing(connect(db_path)) as connection:
                        rows = connection.execute(
                            '''
                            SELECT id, name, category, quantity, status, notes, created_at, updated_at
                            FROM inventory_items
                            ORDER BY category, name
                            '''
                        ).fetchall()
                    return [dict(row) for row in rows]


                def summary(db_path: Path | str = DEFAULT_DB) -> dict[str, Any]:
                    with closing(connect(db_path)) as connection:
                        total = connection.execute(
                            '''
                            SELECT
                              COUNT(*) AS item_count,
                              COALESCE(SUM(quantity), 0) AS total_quantity
                            FROM inventory_items
                            WHERE status = 'active'
                            '''
                        ).fetchone()
                        categories = connection.execute(
                            '''
                            SELECT category, item_count, total_quantity
                            FROM inventory_summary
                            ORDER BY category
                            '''
                        ).fetchall()
                    return {
                        "item_count": int(total["item_count"] or 0),
                        "total_quantity": int(total["total_quantity"] or 0),
                        "categories": [dict(row) for row in categories],
                    }
                """
            ),
            f"src/{package_name}/cli.py": _strip(
                f"""
                from __future__ import annotations

                import argparse
                import json
                from pathlib import Path

                from .database import DEFAULT_DB, add_item, initialize_database, list_items, summary


                def _db_path(value: str | None) -> Path:
                    return Path(value) if value else DEFAULT_DB


                def command_init(args: argparse.Namespace) -> int:
                    path = initialize_database(_db_path(args.db), seed=not args.no_seed, reset=args.reset)
                    print(f"Initialized database: {{path}}")
                    return 0


                def command_add(args: argparse.Namespace) -> int:
                    initialize_database(_db_path(args.db), seed=True, reset=False)
                    item_id = add_item(
                        _db_path(args.db),
                        args.name,
                        category=args.category,
                        quantity=args.quantity,
                        notes=args.notes,
                    )
                    print(f"Added item #{{item_id}}")
                    return 0


                def command_list(args: argparse.Namespace) -> int:
                    initialize_database(_db_path(args.db), seed=True, reset=False)
                    print(json.dumps(list_items(_db_path(args.db)), indent=2))
                    return 0


                def command_summary(args: argparse.Namespace) -> int:
                    initialize_database(_db_path(args.db), seed=True, reset=False)
                    print(json.dumps(summary(_db_path(args.db)), indent=2))
                    return 0


                def command_validate(args: argparse.Namespace) -> int:
                    path = initialize_database(_db_path(args.db), seed=True, reset=args.reset)
                    add_item(path, "Validation Runtime Record", category="quality", quantity=2)
                    report = summary(path)
                    if report["item_count"] < 4:
                        raise RuntimeError("database validation expected at least four active records")
                    if report["total_quantity"] < 13:
                        raise RuntimeError("database validation expected seeded and runtime quantities")
                    print(json.dumps({{"database": str(path), "summary": report}}, indent=2))
                    return 0


                def build_parser() -> argparse.ArgumentParser:
                    parser = argparse.ArgumentParser(description="{title} database utility")
                    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
                    subparsers = parser.add_subparsers(dest="command", required=True)

                    init = subparsers.add_parser("init", help="Create schema and optional seed data.")
                    init.add_argument("--reset", action="store_true", help="Delete the selected database before initializing.")
                    init.add_argument("--no-seed", action="store_true", help="Create schema without seed rows.")
                    init.set_defaults(func=command_init)

                    add = subparsers.add_parser("add", help="Insert an inventory item.")
                    add.add_argument("name")
                    add.add_argument("--category", default="general")
                    add.add_argument("--quantity", type=int, default=0)
                    add.add_argument("--notes", default="")
                    add.set_defaults(func=command_add)

                    list_cmd = subparsers.add_parser("list", help="List inventory items as JSON.")
                    list_cmd.set_defaults(func=command_list)

                    summary_cmd = subparsers.add_parser("summary", help="Print category and total counts.")
                    summary_cmd.set_defaults(func=command_summary)

                    validate = subparsers.add_parser("validate", help="Run a database smoke validation.")
                    validate.add_argument("--reset", action="store_true", help="Reset the selected validation database first.")
                    validate.set_defaults(func=command_validate)
                    return parser


                def main(argv: list[str] | None = None) -> int:
                    parser = build_parser()
                    args = parser.parse_args(argv)
                    return int(args.func(args))


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            "tests/test_database.py": _strip(
                f"""
                from __future__ import annotations

                import sys
                import tempfile
                import unittest
                from pathlib import Path


                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

                from {package_name}.database import add_item, initialize_database, list_items, summary


                class DatabaseTests(unittest.TestCase):
                    def test_initialize_creates_seeded_database(self) -> None:
                        with tempfile.TemporaryDirectory() as tmp:
                            db_path = Path(tmp) / "test.sqlite3"
                            initialize_database(db_path, reset=True)

                            items = list_items(db_path)
                            report = summary(db_path)

                            self.assertGreaterEqual(len(items), 3)
                            self.assertGreaterEqual(report["item_count"], 3)
                            self.assertGreaterEqual(report["total_quantity"], 11)

                    def test_add_item_updates_summary(self) -> None:
                        with tempfile.TemporaryDirectory() as tmp:
                            db_path = Path(tmp) / "test.sqlite3"
                            initialize_database(db_path, reset=True)
                            item_id = add_item(db_path, "New Part", category="parts", quantity=4)

                            self.assertGreater(item_id, 0)
                            names = {{item["name"] for item in list_items(db_path)}}
                            report = summary(db_path)
                            self.assertIn("New Part", names)
                            self.assertGreaterEqual(report["total_quantity"], 15)


                if __name__ == "__main__":
                    unittest.main()
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import os
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                PYTHONPATH = str(ROOT / "src")


                def run(command: list[str]) -> int:
                    env = os.environ.copy()
                    env["PYTHONPATH"] = PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, env=env)
                    return completed.returncode


                def main() -> int:
                    validation_db = ROOT / "data" / "validation.sqlite3"
                    code = run([
                        sys.executable,
                        "-m",
                        "{package_name}.cli",
                        "--db",
                        str(validation_db),
                        "validate",
                        "--reset",
                    ])
                    if code != 0:
                        return code
                    return run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                __pycache__
                *.pyc
                .venv
                data/*.sqlite3
                data/*.db
                data/*.sqlite
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                SQLite database project generated by Aegis Project Builder.

                ## What It Includes

                - `schema.sql` with metadata, inventory records, indexes, trigger, and summary view.
                - `seed.sql` with repeatable starter data.
                - `queries/report.sql` with a reusable reporting query.
                - `src/{package_name}/database.py` with connection, initialization, insert, list, and summary helpers.
                - `src/{package_name}/cli.py` with `init`, `add`, `list`, `summary`, and `validate` commands.
                - `tests/test_database.py` covering schema initialization and CRUD summary behavior.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Use

                ```powershell
                $env:PYTHONPATH = "src"
                python -m {package_name}.cli init --reset
                python -m {package_name}.cli add "Example Item" --category parts --quantity 4
                python -m {package_name}.cli summary
                ```
                """
            ),
        }

    @staticmethod
    def _cpp_cmake_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 17)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_executable(${{PROJECT_NAME}} src/main.cpp)
                target_include_directories(${{PROJECT_NAME}} PRIVATE include)

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_include_directories(${{PROJECT_NAME}}_smoke PRIVATE include)
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            f"include/{native_name}/version.h": _strip(
                f"""
                #pragma once

                namespace {native_name} {{
                inline constexpr const char* kAppName = "{title}";
                inline constexpr const char* kVersion = "0.1.0";
                }}
                """
            ),
            "src/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <string>

                #include "{native_name}/version.h"

                int main(int argc, char** argv)
                {{
                    const char* name = argc > 1 ? argv[1] : "Aegis";
                    std::cout << "Hello, world!\\n";
                    std::cout << {native_name}::kAppName << " " << {native_name}::kVersion
                              << " ready for " << name << "\\n";
                    if (argc <= 1 || std::string(argv[1]) != "--aegis-validate")
                    {{
                        std::cout << "Press Enter to close...";
                        std::string line;
                        std::getline(std::cin, line);
                    }}
                    return 0;
                }}
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include <cassert>
                #include <string>

                #include "{native_name}/version.h"

                int main()
                {{
                    assert(std::string({native_name}::kVersion) == "0.1.0");
                    return 0;
                }}
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_NAME = "{native_name}"
                BUILD_DIR = Path(
                    os.environ.get(
                        "AEGIS_CMAKE_BUILD_DIR",
                        Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                    )
                )


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True)
                    return completed.returncode


                def find_app_executable() -> Path | None:
                    names = {{APP_NAME, APP_NAME + ".exe"}}
                    for candidate in BUILD_DIR.rglob("*"):
                        if candidate.is_file() and candidate.name in names:
                            return candidate
                    return None


                def run_generated_app() -> int:
                    app = find_app_executable()
                    if app is None:
                        print("Generated executable was not found under build/.", file=sys.stderr)
                        return 2
                    command = [str(app), "--aegis-validate"]
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Hello, world!" not in completed.stdout:
                        print("Generated app ran, but expected hello-world output was not found.", file=sys.stderr)
                        return 1
                    return 0


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                    if code != 0:
                        return code

                    code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                    if code != 0:
                        return code

                    return run_generated_app()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                .vs
                .vscode
                *.user
                *.obj
                *.pdb
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C++ CMake CLI generated by Aegis Project Builder.

                ## Build

                ```bash
                cmake -S . -B build
                cmake --build build
                ```

                ## Validation

                ```bash
                python build.py
                ```
                """
            ),
        }


    @staticmethod
    def _cpp_cmake_dll_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        macro_base = re.sub(r"[^A-Za-z0-9_]+", "_", native_name).strip("_").upper() or "AEGIS_LIBRARY"
        export_macro = f"{macro_base}_API"
        build_macro = f"{macro_base}_EXPORTS"
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 17)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_library(${{PROJECT_NAME}} SHARED
                  src/library.cpp
                )
                target_include_directories(${{PROJECT_NAME}}
                  PUBLIC
                    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
                    $<INSTALL_INTERFACE:include>
                )
                target_compile_definitions(${{PROJECT_NAME}} PRIVATE {build_macro})
                target_compile_features(${{PROJECT_NAME}} PUBLIC cxx_std_17)

                add_executable(${{PROJECT_NAME}}_host host/main.cpp)
                target_include_directories(${{PROJECT_NAME}}_host PRIVATE include)
                target_compile_features(${{PROJECT_NAME}}_host PRIVATE cxx_std_17)
                target_link_libraries(${{PROJECT_NAME}}_host PRIVATE ${{CMAKE_DL_LIBS}})

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}})
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            "CMakePresets.json": _strip(
                """
                {
                  "version": 6,
                  "configurePresets": [
                    {
                      "name": "default",
                      "displayName": "Default build",
                      "generator": "Ninja",
                      "binaryDir": "${sourceDir}/build",
                      "cacheVariables": {
                        "CMAKE_BUILD_TYPE": "Release",
                        "BUILD_TESTING": "ON"
                      }
                    }
                  ],
                  "buildPresets": [
                    {
                      "name": "default",
                      "configurePreset": "default"
                    }
                  ],
                  "testPresets": [
                    {
                      "name": "default",
                      "configurePreset": "default",
                      "output": {
                        "outputOnFailure": true
                      }
                    }
                  ]
                }
                """
            ),
            f"include/{native_name}/library.h": _strip(
                f"""
                #pragma once

                #if defined(_WIN32)
                  #if defined({build_macro})
                    #define {export_macro} __declspec(dllexport)
                  #else
                    #define {export_macro} __declspec(dllimport)
                  #endif
                #else
                  #define {export_macro} __attribute__((visibility("default")))
                #endif

                extern "C" {export_macro} int aegis_add(int left, int right);
                extern "C" {export_macro} const char* aegis_library_name();
                extern "C" {export_macro} const char* aegis_plugin_version();
                extern "C" {export_macro} const char* aegis_plugin_description();
                """
            ),
            "src/library.cpp": _strip(
                f"""
                #include "{native_name}/library.h"

                int aegis_add(int left, int right)
                {{
                    return left + right;
                }}

                const char* aegis_library_name()
                {{
                    return "{title}";
                }}

                const char* aegis_plugin_version()
                {{
                    return "0.1.0";
                }}

                const char* aegis_plugin_description()
                {{
                    return "Aegis generated native DLL/shared-library plugin with a stable exported C ABI.";
                }}
                """
            ),
            "host/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <stdexcept>
                #include <string>

                #if defined(_WIN32)
                #define WIN32_LEAN_AND_MEAN
                #include <windows.h>
                #else
                #include <dlfcn.h>
                #endif

                namespace {{

                class SharedLibrary {{
                public:
                    explicit SharedLibrary(const std::string& path)
                    {{
                #if defined(_WIN32)
                        handle_ = LoadLibraryA(path.c_str());
                #else
                        handle_ = dlopen(path.c_str(), RTLD_NOW);
                #endif
                        if (handle_ == nullptr)
                        {{
                            throw std::runtime_error("Unable to load plugin library: " + path);
                        }}
                    }}

                    ~SharedLibrary()
                    {{
                #if defined(_WIN32)
                        if (handle_ != nullptr)
                        {{
                            FreeLibrary(static_cast<HMODULE>(handle_));
                        }}
                #else
                        if (handle_ != nullptr)
                        {{
                            dlclose(handle_);
                        }}
                #endif
                    }}

                    SharedLibrary(const SharedLibrary&) = delete;
                    SharedLibrary& operator=(const SharedLibrary&) = delete;

                    template <typename Fn>
                    Fn symbol(const char* name) const
                    {{
                #if defined(_WIN32)
                        FARPROC value = GetProcAddress(static_cast<HMODULE>(handle_), name);
                #else
                        void* value = dlsym(handle_, name);
                #endif
                        if (value == nullptr)
                        {{
                            throw std::runtime_error(std::string("Missing exported symbol: ") + name);
                        }}
                        return reinterpret_cast<Fn>(value);
                    }}

                private:
                    void* handle_{{nullptr}};
                }};

                }} // namespace

                int main(int argc, char** argv)
                {{
                    const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";
                    const int library_arg = validate ? 2 : 1;
                    if (argc <= library_arg)
                    {{
                        std::cerr << "Usage: {native_name}_host [--aegis-validate] <path-to-plugin-library>\\n";
                        return 2;
                    }}

                    try
                    {{
                        SharedLibrary library(argv[library_arg]);
                        using AddFn = int (*)(int, int);
                        using StringFn = const char* (*)();

                        const auto add = library.symbol<AddFn>("aegis_add");
                        const auto name = library.symbol<StringFn>("aegis_library_name");
                        const auto version = library.symbol<StringFn>("aegis_plugin_version");
                        const auto description = library.symbol<StringFn>("aegis_plugin_description");

                        const int result = add(21, 21);
                        std::cout << "Host loaded plugin: " << name() << "\\n";
                        std::cout << "Plugin version: " << version() << "\\n";
                        std::cout << "Plugin description: " << description() << "\\n";
                        std::cout << "aegis_add(21, 21)=" << result << "\\n";

                        if (result != 42 || std::string(name()).empty() || std::string(version()).empty())
                        {{
                            std::cerr << "Plugin validation failed.\\n";
                            return 3;
                        }}

                        if (!validate)
                        {{
                            std::cout << "Press Enter to close...";
                            std::string line;
                            std::getline(std::cin, line);
                        }}
                        return 0;
                    }}
                    catch (const std::exception& error)
                    {{
                        std::cerr << error.what() << "\\n";
                        return 1;
                    }}
                }}
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include <cstring>

                #include "{native_name}/library.h"

                int main()
                {{
                    if (aegis_add(2, 3) != 5) {{
                        return 1;
                    }}
                    if (std::strlen(aegis_library_name()) == 0) {{
                        return 2;
                    }}
                    if (std::strlen(aegis_plugin_version()) == 0) {{
                        return 3;
                    }}
                    return std::strlen(aegis_plugin_description()) > 0 ? 0 : 4;
                }}
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_NAME = "{native_name}"
                BUILD_DIR = Path(
                    os.environ.get(
                        "AEGIS_CMAKE_BUILD_DIR",
                        Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                    )
                )


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    return completed.returncode


                def find_built_file(names: set[str]) -> Path | None:
                    for candidate in BUILD_DIR.rglob("*"):
                        if candidate.is_file() and candidate.name in names:
                            return candidate
                    return None


                def find_plugin_library() -> Path | None:
                    return find_built_file({{
                        APP_NAME + ".dll",
                        "lib" + APP_NAME + ".so",
                        "lib" + APP_NAME + ".dylib",
                    }})


                def find_host_executable() -> Path | None:
                    return find_built_file({{
                        APP_NAME + "_host",
                        APP_NAME + "_host.exe",
                    }})


                def run_host_validation() -> int:
                    host = find_host_executable()
                    library = find_plugin_library()
                    if host is None:
                        print("Generated host executable was not found under build/.", file=sys.stderr)
                        return 3
                    if library is None:
                        print("Generated plugin library was not found under build/.", file=sys.stderr)
                        return 4
                    completed = subprocess.run(
                        [str(host), "--aegis-validate", str(library)],
                        cwd=str(ROOT),
                        text=True,
                        capture_output=True,
                    )
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Host loaded plugin:" not in completed.stdout or "aegis_add(21, 21)=42" not in completed.stdout:
                        print("Expected host/plugin validation output was not found.", file=sys.stderr)
                        return 5
                    return 0


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    configure = ["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator]
                    code = run(configure)
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                    if code != 0:
                        return code

                    code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                    if code != 0:
                        return code

                    return run_host_validation()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                *.dll
                *.lib
                *.exp
                *.so
                *.dylib
                *.out
                *.obj
                *.pdb
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C++17 DLL/shared-library project generated by Aegis Project Builder.

                ## What It Includes

                - `include/{native_name}/library.h` with portable export macros.
                - `src/library.cpp` with exported example functions.
                - `host/main.cpp` with a runtime loader that verifies exported symbols.
                - `tests/smoke.cpp` linked against the library.
                - `build.py` that configures, builds, runs CTest, and launches the host validation path.

                ## Build And Validate

                ```powershell
                python build.py
                ```

                The generated library exports:

                - `aegis_add(int left, int right)`
                - `aegis_library_name()`
                - `aegis_plugin_version()`
                - `aegis_plugin_description()`
                """
            ),
        }


    @staticmethod
    def _cpp_imgui_win32_dx11_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 20)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_library(${{PROJECT_NAME}}_core
                  src/app_state.cpp
                )
                target_include_directories(${{PROJECT_NAME}}_core PUBLIC include vendor/imgui_shim)
                target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_20)

                add_executable(${{PROJECT_NAME}} src/main.cpp)
                target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            f"include/{native_name}/app_state.h": _strip(
                f"""
                #pragma once

                #include <cstdint>
                #include <string>
                #include <vector>

                namespace {native_name} {{

                struct FrameMetrics {{
                    float delta_seconds{{1.0f / 60.0f}};
                    float frame_time_ms{{16.67f}};
                    int draw_calls{{0}};
                    int visible_entities{{0}};
                }};

                struct ToolLogEntry {{
                    std::string level;
                    std::string message;
                }};

                class AppState {{
                public:
                    AppState();

                    void add_log(std::string level, std::string message);
                    void tick(float delta_seconds);

                    [[nodiscard]] const FrameMetrics& metrics() const noexcept;
                    [[nodiscard]] const std::vector<ToolLogEntry>& log() const noexcept;
                    [[nodiscard]] std::string summary() const;

                private:
                    FrameMetrics metrics_;
                    std::vector<ToolLogEntry> log_;
                }};

                void render_editor_panels(AppState& state);

                }} // namespace {native_name}
                """
            ),
            "src/app_state.cpp": _strip(
                f"""
                #include "{native_name}/app_state.h"

                #include <algorithm>
                #include <cstddef>
                #include <sstream>
                #include <utility>

                #include "imgui.h"

                namespace {native_name} {{

                AppState::AppState()
                {{
                    add_log("info", "Aegis ImGui tooling scaffold initialized.");
                    add_log("info", "Use this project for editors, overlays, debug panels, and game tooling.");
                }}

                void AppState::add_log(std::string level, std::string message)
                {{
                    log_.push_back(ToolLogEntry{{std::move(level), std::move(message)}});
                    if (log_.size() > 200)
                    {{
                        log_.erase(log_.begin(), log_.begin() + static_cast<std::ptrdiff_t>(log_.size() - 200));
                    }}
                }}

                void AppState::tick(float delta_seconds)
                {{
                    metrics_.delta_seconds = delta_seconds;
                    metrics_.frame_time_ms = delta_seconds * 1000.0f;
                    metrics_.draw_calls += 3;
                    metrics_.visible_entities = std::max(1, metrics_.visible_entities + 1);
                }}

                const FrameMetrics& AppState::metrics() const noexcept
                {{
                    return metrics_;
                }}

                const std::vector<ToolLogEntry>& AppState::log() const noexcept
                {{
                    return log_;
                }}

                std::string AppState::summary() const
                {{
                    std::ostringstream stream;
                    stream << "Inspector panels ready: viewport, assets, frame metrics, logs";
                    stream << " | logs=" << log_.size();
                    stream << " | visible_entities=" << metrics_.visible_entities;
                    return stream.str();
                }}

                void render_editor_panels(AppState& state)
                {{
                    const FrameMetrics& frame = state.metrics();

                    if (ImGui::Begin("Aegis Game Tool"))
                    {{
                        ImGui::TextUnformatted("Viewport, entity inspector, and asset workflow shell");
                        ImGui::Separator();
                        ImGui::Text("Delta: %.4f", frame.delta_seconds);
                        ImGui::Text("Frame time: %.2f ms", frame.frame_time_ms);
                        ImGui::Text("Draw calls: %d", frame.draw_calls);
                        ImGui::Text("Visible entities: %d", frame.visible_entities);
                    }}
                    ImGui::End();

                    if (ImGui::Begin("Asset Browser"))
                    {{
                        ImGui::TextUnformatted("Drop parsers, importers, and package viewers here.");
                    }}
                    ImGui::End();

                    if (ImGui::Begin("Tool Log"))
                    {{
                        for (const ToolLogEntry& entry : state.log())
                        {{
                            ImGui::Text("[%s] %s", entry.level.c_str(), entry.message.c_str());
                        }}
                    }}
                    ImGui::End();
                }}

                }} // namespace {native_name}
                """
            ),
            "src/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <string>

                #include "imgui.h"
                #include "{native_name}/app_state.h"

                int main(int argc, char** argv)
                {{
                    const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                    ImGui::CreateContext();
                    {native_name}::AppState state;
                    state.tick(1.0f / 60.0f);
                    {native_name}::render_editor_panels(state);
                    ImGui::Render();

                    const std::string summary = state.summary();
                    std::cout << "{title} Dear ImGui tooling starter\\n";
                    std::cout << summary << "\\n";

                    if (summary.find("Inspector panels ready") == std::string::npos)
                    {{
                        std::cerr << "ImGui tool shell did not render expected panels.\\n";
                        ImGui::DestroyContext();
                        return 2;
                    }}

                    if (!validate)
                    {{
                        std::cout << "Press Enter to close...";
                        std::string line;
                        std::getline(std::cin, line);
                    }}

                    ImGui::DestroyContext();
                    return 0;
                }}
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include <string>

                #include "{native_name}/app_state.h"

                int main()
                {{
                    {native_name}::AppState state;
                    state.tick(1.0f / 120.0f);
                    state.add_log("test", "smoke validation");

                    const std::string summary = state.summary();
                    if (summary.find("Inspector panels ready") == std::string::npos)
                    {{
                        return 1;
                    }}
                    return state.log().empty() ? 2 : 0;
                }}
                """
            ),
            "vendor/imgui_shim/imgui.h": _strip(
                """
                #pragma once

                #include <cstdarg>

                namespace ImGui {

                inline void CreateContext() {}
                inline void DestroyContext() {}
                inline void Render() {}
                inline bool Begin(const char*) { return true; }
                inline void End() {}
                inline void Separator() {}
                inline void TextUnformatted(const char*) {}
                inline void Text(const char*, ...) {}

                } // namespace ImGui
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_NAME = "{native_name}"
                BUILD_DIR = Path(
                    os.environ.get(
                        "AEGIS_CMAKE_BUILD_DIR",
                        Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                    )
                )


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    return completed.returncode


                def find_app_executable() -> Path | None:
                    names = {{APP_NAME, APP_NAME + ".exe"}}
                    build_root = ROOT / "build"
                    for candidate in build_root.rglob("*"):
                        if candidate.is_file() and candidate.name in names:
                            return candidate
                    return None


                def run_generated_app() -> int:
                    app = find_app_executable()
                    if app is None:
                        print("Generated ImGui tool executable was not found under build/.", file=sys.stderr)
                        return 3
                    completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Dear ImGui tooling starter" not in completed.stdout:
                        print("Expected ImGui tooling validation output was not found.", file=sys.stderr)
                        return 4
                    return 0


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake 3.20+ is required to validate this ImGui scaffold.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    code = run(["cmake", "-S", ".", "-B", "build", "-DBUILD_TESTING=ON", *generator])
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", "build", "--config", "Release"])
                    if code != 0:
                        return code

                    code = run(["ctest", "--test-dir", "build", "-C", "Release", "--output-on-failure"])
                    if code != 0:
                        return code

                    return run_generated_app()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                .vs
                .vscode
                *.user
                *.obj
                *.pdb
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C++20 Dear ImGui-style game tooling scaffold generated by Aegis Project Builder.

                ## What This Gives You

                - A validated CMake project for ImGui-style editor panels and game tooling.
                - `AppState` for frame metrics, entity/asset workflow state, and tool logs.
                - A dependency-free ImGui validation shim so the project can build immediately.
                - A clear place to swap in real Dear ImGui Win32/DX11 backends when you are ready.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Upgrading To Real Dear ImGui

                Replace `vendor/imgui_shim/imgui.h` with the official Dear ImGui source tree and update
                `CMakeLists.txt` to compile `imgui.cpp`, `imgui_draw.cpp`, `imgui_tables.cpp`,
                `imgui_widgets.cpp`, and the Win32/DX11 backend files from `backends/`.
                """
            ),
        }


    @staticmethod
    def _cpp_game_loop_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 20)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_library(${{PROJECT_NAME}}_engine src/engine.cpp)
                target_include_directories(${{PROJECT_NAME}}_engine PUBLIC include)
                target_compile_features(${{PROJECT_NAME}}_engine PUBLIC cxx_std_20)

                add_executable(${{PROJECT_NAME}} src/main.cpp)
                target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_engine)

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_engine)
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            f"include/{native_name}/engine.h": _strip(
                f"""
                #pragma once

                #include <cstddef>
                #include <cstdint>
                #include <string>
                #include <unordered_map>
                #include <vector>

                namespace {native_name} {{

                struct AssetRecord {{
                    std::string id;
                    std::string path;
                    std::string type;
                }};

                struct SimulationStats {{
                    std::uint64_t tick{{0}};
                    double elapsed_seconds{{0.0}};
                    std::size_t loaded_assets{{0}};
                }};

                class AssetRegistry {{
                public:
                    bool add(AssetRecord record);
                    [[nodiscard]] const AssetRecord* find(const std::string& id) const;
                    [[nodiscard]] std::size_t size() const noexcept;

                private:
                    std::unordered_map<std::string, AssetRecord> assets_;
                }};

                class FixedStepSimulation {{
                public:
                    explicit FixedStepSimulation(double step_seconds = 1.0 / 60.0);

                    void load_default_assets();
                    void tick();
                    void run_for_ticks(std::uint64_t count);

                    [[nodiscard]] const SimulationStats& stats() const noexcept;
                    [[nodiscard]] const AssetRegistry& assets() const noexcept;
                    [[nodiscard]] std::string validation_report() const;

                private:
                    double step_seconds_;
                    SimulationStats stats_;
                    AssetRegistry assets_;
                }};

                }} // namespace {native_name}
                """
            ),
            "src/engine.cpp": _strip(
                f"""
                #include "{native_name}/engine.h"

                #include <sstream>
                #include <utility>

                namespace {native_name} {{

                bool AssetRegistry::add(AssetRecord record)
                {{
                    if (record.id.empty() || record.path.empty())
                    {{
                        return false;
                    }}
                    const std::string id = record.id;
                    return assets_.emplace(id, std::move(record)).second;
                }}

                const AssetRecord* AssetRegistry::find(const std::string& id) const
                {{
                    const auto found = assets_.find(id);
                    return found == assets_.end() ? nullptr : &found->second;
                }}

                std::size_t AssetRegistry::size() const noexcept
                {{
                    return assets_.size();
                }}

                FixedStepSimulation::FixedStepSimulation(double step_seconds)
                    : step_seconds_(step_seconds)
                {{
                }}

                void FixedStepSimulation::load_default_assets()
                {{
                    assets_.add(AssetRecord{{"player", "assets/player.placeholder", "entity"}});
                    assets_.add(AssetRecord{{"level_01", "assets/level_01.placeholder", "level"}});
                    assets_.add(AssetRecord{{"debug_font", "assets/debug_font.placeholder", "font"}});
                    stats_.loaded_assets = assets_.size();
                }}

                void FixedStepSimulation::tick()
                {{
                    ++stats_.tick;
                    stats_.elapsed_seconds += step_seconds_;
                    stats_.loaded_assets = assets_.size();
                }}

                void FixedStepSimulation::run_for_ticks(std::uint64_t count)
                {{
                    for (std::uint64_t index = 0; index < count; ++index)
                    {{
                        tick();
                    }}
                }}

                const SimulationStats& FixedStepSimulation::stats() const noexcept
                {{
                    return stats_;
                }}

                const AssetRegistry& FixedStepSimulation::assets() const noexcept
                {{
                    return assets_;
                }}

                std::string FixedStepSimulation::validation_report() const
                {{
                    std::ostringstream stream;
                    stream << "Game loop validation passed"
                           << " | ticks=" << stats_.tick
                           << " | elapsed=" << stats_.elapsed_seconds
                           << " | assets=" << stats_.loaded_assets;
                    return stream.str();
                }}

                }} // namespace {native_name}
                """
            ),
            "src/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <string>

                #include "{native_name}/engine.h"

                int main(int argc, char** argv)
                {{
                    const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                    {native_name}::FixedStepSimulation simulation;
                    simulation.load_default_assets();
                    simulation.run_for_ticks(validate ? 5 : 120);

                    std::cout << "{title} game sandbox\\n";
                    std::cout << simulation.validation_report() << "\\n";

                    if (simulation.stats().tick == 0 || simulation.assets().find("player") == nullptr)
                    {{
                        std::cerr << "Simulation did not load required starter state.\\n";
                        return 2;
                    }}

                    if (!validate)
                    {{
                        std::cout << "Press Enter to close...";
                        std::string line;
                        std::getline(std::cin, line);
                    }}
                    return 0;
                }}
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include "{native_name}/engine.h"

                #include <string>

                int main()
                {{
                    {native_name}::FixedStepSimulation simulation;
                    simulation.load_default_assets();
                    simulation.run_for_ticks(8);

                    if (simulation.stats().tick != 8)
                    {{
                        return 1;
                    }}
                    if (simulation.assets().find("level_01") == nullptr)
                    {{
                        return 2;
                    }}
                    return simulation.validation_report().find("Game loop validation passed") == std::string::npos ? 3 : 0;
                }}
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_NAME = "{native_name}"
                BUILD_DIR = Path(
                    os.environ.get(
                        "AEGIS_CMAKE_BUILD_DIR",
                        Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                    )
                )


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    return completed.returncode


                def find_app_executable() -> Path | None:
                    names = {{APP_NAME, APP_NAME + ".exe"}}
                    for candidate in BUILD_DIR.rglob("*"):
                        if candidate.is_file() and candidate.name in names:
                            return candidate
                    return None


                def run_generated_app() -> int:
                    app = find_app_executable()
                    if app is None:
                        print("Generated game sandbox executable was not found under build/.", file=sys.stderr)
                        return 3
                    completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Game loop validation passed" not in completed.stdout:
                        print("Expected game-loop validation output was not found.", file=sys.stderr)
                        return 4
                    return 0


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake 3.20+ is required to validate this game sandbox.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                    if code != 0:
                        return code

                    code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                    if code != 0:
                        return code

                    return run_generated_app()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                .vs
                .vscode
                *.user
                *.obj
                *.pdb
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C++20 game-loop sandbox generated by Aegis Project Builder.

                ## Included Systems

                - Fixed-step simulation loop.
                - Asset registry for game/editor tooling.
                - CLI validation mode for automated build repair loops.
                - Smoke test that validates ticks, assets, and reporting.

                ## Validate

                ```powershell
                python build.py
                ```
                """
            ),
        }


    @staticmethod
    def _python_game_file_analyzer_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        analyzer_py = _strip(
            """
            from __future__ import annotations

            import hashlib
            import json
            import math
            import string
            from dataclasses import asdict, dataclass
            from pathlib import Path
            from typing import Iterable


            SIGNATURES: tuple[tuple[bytes, str], ...] = (
                (b"\\x89PNG\\r\\n\\x1a\\n", "png-image"),
                (b"DDS ", "directdraw-surface"),
                (b"RIFF", "riff-container"),
                (b"OggS", "ogg-audio"),
                (b"PK\\x03\\x04", "zip-or-packed-archive"),
                (b"MZ", "portable-executable"),
                (b"\\x7fELF", "elf-binary"),
                (b"SQLite format 3\\x00", "sqlite-database"),
                (b"{", "json-or-text"),
            )


            @dataclass(frozen=True)
            class FileAnalysis:
                path: str
                size: int
                sha256: str
                extension: str
                detected_format: str
                entropy: float
                first_bytes_hex: str
                strings: list[str]

                def to_dict(self) -> dict[str, object]:
                    return asdict(self)


            def shannon_entropy(data: bytes) -> float:
                if not data:
                    return 0.0
                counts = [0] * 256
                for byte in data:
                    counts[byte] += 1
                entropy = 0.0
                length = len(data)
                for count in counts:
                    if count:
                        probability = count / length
                        entropy -= probability * math.log2(probability)
                return round(entropy, 4)


            def extract_strings(data: bytes, *, minimum: int = 4, limit: int = 40) -> list[str]:
                printable = set(string.printable.encode("ascii"))
                found: list[str] = []
                current = bytearray()
                for byte in data:
                    if byte in printable and byte not in b"\\r\\n\\t\\x0b\\x0c":
                        current.append(byte)
                        continue
                    if len(current) >= minimum:
                        found.append(current.decode("ascii", errors="replace"))
                        if len(found) >= limit:
                            return found
                    current.clear()
                if len(current) >= minimum and len(found) < limit:
                    found.append(current.decode("ascii", errors="replace"))
                return found


            def detect_format(data: bytes, path: Path) -> str:
                for magic, label in SIGNATURES:
                    if data.startswith(magic):
                        if label == "riff-container" and len(data) >= 12:
                            subtype = data[8:12].decode("ascii", errors="replace").strip()
                            return f"riff-{subtype.lower() or 'container'}"
                        return label
                extension_map = {
                    ".pak": "game-package",
                    ".wad": "wad-archive",
                    ".bundle": "asset-bundle",
                    ".bank": "audio-bank",
                    ".uasset": "unreal-asset",
                    ".unity3d": "unity-asset-bundle",
                    ".dat": "data-blob",
                    ".bin": "binary-blob",
                }
                return extension_map.get(path.suffix.lower(), "unknown")


            def analyze_file(path: str | Path) -> FileAnalysis:
                file_path = Path(path)
                data = file_path.read_bytes()
                return FileAnalysis(
                    path=str(file_path),
                    size=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    extension=file_path.suffix.lower(),
                    detected_format=detect_format(data, file_path),
                    entropy=shannon_entropy(data),
                    first_bytes_hex=data[:32].hex(" "),
                    strings=extract_strings(data),
                )


            def iter_files(root: str | Path) -> Iterable[Path]:
                root_path = Path(root)
                if root_path.is_file():
                    yield root_path
                    return
                for path in sorted(root_path.rglob("*")):
                    if path.is_file():
                        yield path


            def analyze_tree(root: str | Path, *, max_files: int = 500) -> dict[str, object]:
                root_path = Path(root)
                files = [analyze_file(path).to_dict() for path in list(iter_files(root_path))[:max_files]]
                formats: dict[str, int] = {}
                for file in files:
                    detected = str(file["detected_format"])
                    formats[detected] = formats.get(detected, 0) + 1
                return {
                    "root": str(root_path),
                    "file_count": len(files),
                    "formats": formats,
                    "files": files,
                }


            def to_json_report(payload: dict[str, object]) -> str:
                return json.dumps(payload, indent=2, sort_keys=True)
            """
        )
        cli_py = _strip(
            """
            from __future__ import annotations

            import argparse
            from pathlib import Path

            from .analyzer import analyze_tree, to_json_report


            def build_parser() -> argparse.ArgumentParser:
                parser = argparse.ArgumentParser(description="Analyze owned or authorized game files and asset folders.")
                parser.add_argument("target", help="File or folder to analyze.")
                parser.add_argument("--json", dest="json_path", help="Optional path for a JSON report.")
                parser.add_argument("--max-files", type=int, default=500, help="Maximum files to scan in a folder.")
                return parser


            def main(argv: list[str] | None = None) -> int:
                args = build_parser().parse_args(argv)
                report = analyze_tree(args.target, max_files=args.max_files)
                output = to_json_report(report)
                print(output)
                if args.json_path:
                    Path(args.json_path).write_text(output + "\\n", encoding="utf-8")
                return 0


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )
        test_py = _strip(
            """
            from pathlib import Path
            import tempfile
            import unittest

            from __PACKAGE__.analyzer import analyze_file, analyze_tree


            ROOT = Path(__file__).resolve().parents[1]


            class AnalyzerTests(unittest.TestCase):
                def test_sample_asset_extracts_strings_and_hash(self) -> None:
                    result = analyze_file(ROOT / "samples" / "sample_asset.bin")

                    self.assertEqual(result.extension, ".bin")
                    self.assertEqual(result.detected_format, "binary-blob")
                    self.assertEqual(len(result.sha256), 64)
                    self.assertIn("AEGIS_SAMPLE_ASSET", result.strings)

                def test_tree_report_counts_formats(self) -> None:
                    with tempfile.TemporaryDirectory() as tempdir:
                        root = Path(tempdir)
                        (root / "texture.dds").write_bytes(b"DDS " + bytes(range(16)))
                        (root / "bundle.pak").write_bytes(b"PACKED_ASSET_TABLE")

                        report = analyze_tree(root)

                    self.assertEqual(report["file_count"], 2)
                    self.assertEqual(report["formats"]["directdraw-surface"], 1)
                    self.assertEqual(report["formats"]["game-package"], 1)


            if __name__ == "__main__":
                unittest.main()
            """
        ).replace("__PACKAGE__", package_name)
        build_py = _strip(
            f"""
            from __future__ import annotations

            import compileall
            import subprocess
            import sys
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def main() -> int:
                if not compileall.compile_dir(str(ROOT / "{package_name}"), quiet=1):
                    return 1

                code = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
                if code != 0:
                    return code

                report_path = ROOT / "analysis-report.json"
                code = run([
                    sys.executable,
                    "-m",
                    "{package_name}.cli",
                    "samples",
                    "--json",
                    str(report_path),
                ])
                if code != 0:
                    return code
                if not report_path.exists():
                    print("Expected analysis report was not written.", file=sys.stderr)
                    return 2
                print("Game file analyzer validation passed")
                return 0


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )
        return {
            f"{package_name}/__init__.py": "__all__ = [\"analyzer\"]\n",
            f"{package_name}/analyzer.py": analyzer_py,
            f"{package_name}/cli.py": cli_py,
            "tests/test_analyzer.py": test_py,
            "samples/sample_asset.bin": "AEGIS_SAMPLE_ASSET\nmesh=training_cube\ntexture=debug_grid\n",
            "build.py": build_py,
            ".gitignore": _strip(
                """
                __pycache__
                .pytest_cache
                analysis-report.json
                *.pyc
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free Python toolkit for analyzing owned or authorized game files,
                asset bundles, binary blobs, and custom file formats.

                ## Capabilities

                - Magic-byte and extension based format guesses.
                - SHA-256 hashing, size, first-byte previews, printable string extraction, and entropy.
                - Folder reports for asset-pack and file-format triage.
                - JSON output for follow-up tooling.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run

                ```powershell
                python -m {package_name}.cli samples --json analysis-report.json
                ```
                """
            ),
        }


    @staticmethod
    def _cpp_msvc_console_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-console"
        root_namespace = re.sub(r"[^A-Za-z0-9_]+", "_", safe_name).strip("_") or "AegisConsole"
        if root_namespace[0].isdigit():
            root_namespace = f"App_{root_namespace}"
        project_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.cpp.msvc.{safe_name}")).upper() + "}"
        source_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.cpp.msvc.{safe_name}.source")).upper() + "}"
        return {
            f"{safe_name}.sln": _strip(
                f"""
                Microsoft Visual Studio Solution File, Format Version 12.00
                # Visual Studio Version 17
                VisualStudioVersion = 17.0.31903.59
                MinimumVisualStudioVersion = 10.0.40219.1
                Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{safe_name}", "{safe_name}.vcxproj", "{project_guid}"
                EndProject
                Global
                    GlobalSection(SolutionConfigurationPlatforms) = preSolution
                        Debug|x64 = Debug|x64
                        Release|x64 = Release|x64
                    EndGlobalSection
                    GlobalSection(ProjectConfigurationPlatforms) = postSolution
                        {project_guid}.Debug|x64.ActiveCfg = Debug|x64
                        {project_guid}.Debug|x64.Build.0 = Debug|x64
                        {project_guid}.Release|x64.ActiveCfg = Release|x64
                        {project_guid}.Release|x64.Build.0 = Release|x64
                    EndGlobalSection
                    GlobalSection(SolutionProperties) = preSolution
                        HideSolutionNode = FALSE
                    EndGlobalSection
                EndGlobal
                """
            ),
            f"{safe_name}.vcxproj": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup Label="ProjectConfigurations">
                    <ProjectConfiguration Include="Debug|x64">
                      <Configuration>Debug</Configuration>
                      <Platform>x64</Platform>
                    </ProjectConfiguration>
                    <ProjectConfiguration Include="Release|x64">
                      <Configuration>Release</Configuration>
                      <Platform>x64</Platform>
                    </ProjectConfiguration>
                  </ItemGroup>
                  <PropertyGroup Label="Globals">
                    <VCProjectVersion>17.0</VCProjectVersion>
                    <Keyword>Win32Proj</Keyword>
                    <ProjectGuid>{project_guid}</ProjectGuid>
                    <RootNamespace>{root_namespace}</RootNamespace>
                    <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>true</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>false</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <WholeProgramOptimization>true</WholeProgramOptimization>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
                  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <SDLCheck>true</SDLCheck>
                      <ConformanceMode>true</ConformanceMode>
                      <LanguageStandard>stdcpp17</LanguageStandard>
                    </ClCompile>
                    <Link>
                      <SubSystem>Console</SubSystem>
                    </Link>
                  </ItemDefinitionGroup>
                  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <FunctionLevelLinking>true</FunctionLevelLinking>
                      <IntrinsicFunctions>true</IntrinsicFunctions>
                      <SDLCheck>true</SDLCheck>
                      <ConformanceMode>true</ConformanceMode>
                      <LanguageStandard>stdcpp17</LanguageStandard>
                    </ClCompile>
                    <Link>
                      <SubSystem>Console</SubSystem>
                      <EnableCOMDATFolding>true</EnableCOMDATFolding>
                      <OptimizeReferences>true</OptimizeReferences>
                    </Link>
                  </ItemDefinitionGroup>
                  <ItemGroup>
                    <ClCompile Include="src\\main.cpp" />
                  </ItemGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
                </Project>
                """
            ),
            f"{safe_name}.vcxproj.filters": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup>
                    <Filter Include="Source Files">
                      <UniqueIdentifier>{source_filter_guid}</UniqueIdentifier>
                      <Extensions>cpp;c;cc;cxx</Extensions>
                    </Filter>
                  </ItemGroup>
                  <ItemGroup>
                    <ClCompile Include="src\\main.cpp">
                      <Filter>Source Files</Filter>
                    </ClCompile>
                  </ItemGroup>
                </Project>
                """
            ),
            "src/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <string>

                int main()
                {{
                    std::cout << "Hello, world!" << std::endl;
                    std::cout << "{title} is running." << std::endl;
                    std::cout << "Press Enter to close...";

                    std::string line;
                    std::getline(std::cin, line);
                    return 0;
                }}
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                SOLUTION = Path(__file__).resolve().with_name("{safe_name}.sln")


                def candidate_msbuild_paths() -> list[Path]:
                    candidates: list[Path] = []
                    explicit = os.environ.get("MSBUILD_EXE")
                    if explicit:
                        candidates.append(Path(explicit))

                    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
                    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
                    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
                    if vswhere.exists():
                        try:
                            completed = subprocess.run(
                                [
                                    str(vswhere),
                                    "-latest",
                                    "-products",
                                    "*",
                                    "-requires",
                                    "Microsoft.Component.MSBuild",
                                    "-find",
                                    r"MSBuild\\**\\Bin\\MSBuild.exe",
                                ],
                                text=True,
                                capture_output=True,
                                check=False,
                            )
                            for line in completed.stdout.splitlines():
                                if line.strip():
                                    candidates.append(Path(line.strip()))
                        except OSError:
                            pass

                    for root in (Path(program_files), Path(program_files_x86)):
                        vs2022 = root / "Microsoft Visual Studio" / "2022"
                        for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "MSBuild.exe")
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "amd64" / "MSBuild.exe")

                    on_path = shutil.which("msbuild")
                    if on_path:
                        candidates.append(Path(on_path))
                    return candidates


                def find_msbuild() -> Path | None:
                    seen: set[str] = set()
                    for candidate in candidate_msbuild_paths():
                        key = str(candidate).lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        if candidate.exists():
                            return candidate
                    return None


                def main() -> int:
                    if not SOLUTION.exists():
                        print(f"Solution not found: {{SOLUTION}}", file=sys.stderr)
                        return 2
                    msbuild = find_msbuild()
                    if msbuild is None:
                        print(
                            "MSBuild was not found. Install Visual Studio 2022 Build Tools "
                            "or set the MSBUILD_EXE environment variable.",
                            file=sys.stderr,
                        )
                        return 2

                    command = [
                        str(msbuild),
                        str(SOLUTION),
                        "/p:Configuration=Release",
                        "/p:Platform=x64",
                    ]
                    print("Running:", " ".join(command))
                    build_code = subprocess.call(command, cwd=str(SOLUTION.parent))
                    if build_code != 0:
                        return build_code

                    expected = SOLUTION.parent / "x64" / "Release" / "{safe_name}.exe"
                    candidates = [expected] if expected.exists() else []
                    candidates.extend(SOLUTION.parent.rglob("{safe_name}.exe"))
                    exe = next((candidate for candidate in candidates if candidate.is_file()), None)
                    if exe is None:
                        print("Compiled console executable was not found after MSBuild.", file=sys.stderr)
                        return 2

                    run_command = [str(exe)]
                    print("Running:", " ".join(run_command))
                    completed = subprocess.run(run_command, cwd=str(SOLUTION.parent), input="\\n", text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Hello, world!" not in completed.stdout:
                        print("Generated console app ran, but expected hello-world output was not found.", file=sys.stderr)
                        return 1
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                .vs
                x64
                Debug
                Release
                *.user
                *.obj
                *.pdb
                *.ilk
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Visual Studio C++ console solution generated by Aegis Project Builder.

                ## Build

                ```powershell
                python build.py
                ```

                ## Run

                `python build.py` builds the solution and runs the compiled console executable from `x64/Release`.
                The app prints `Hello, world!` and waits for Enter before closing.
                """
            ),
        }


    @staticmethod
    def _cpp_windows_service_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        service_symbol = re.sub(r"[^A-Za-z0-9]+", " ", title).title().replace(" ", "") or "AegisService"
        display_name = title if "service" in title.lower() else f"{title} Service"
        cpp_title = title.replace("\\", "\\\\").replace('"', '\\"')
        service_name_wide = service_symbol.replace("\\", "\\\\").replace('"', '\\"')
        display_name_wide = display_name.replace("\\", "\\\\").replace('"', '\\"')
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 17)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_library(${{PROJECT_NAME}}_core
                  src/service_core.cpp
                )
                target_include_directories(${{PROJECT_NAME}}_core PUBLIC include)
                target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_17)

                add_executable(${{PROJECT_NAME}}
                  src/service_main.cpp
                )
                target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

                if(WIN32)
                  target_compile_definitions(${{PROJECT_NAME}} PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
                  target_link_libraries(${{PROJECT_NAME}} PRIVATE advapi32)
                endif()

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            "CMakePresets.json": _strip(
                """
                {
                  "version": 6,
                  "configurePresets": [
                    {
                      "name": "default",
                      "displayName": "Default build",
                      "generator": "Ninja",
                      "binaryDir": "${sourceDir}/build",
                      "cacheVariables": {
                        "CMAKE_BUILD_TYPE": "Release",
                        "BUILD_TESTING": "ON"
                      }
                    }
                  ],
                  "buildPresets": [
                    {
                      "name": "default",
                      "configurePreset": "default"
                    }
                  ],
                  "testPresets": [
                    {
                      "name": "default",
                      "configurePreset": "default",
                      "output": {
                        "outputOnFailure": true
                      }
                    }
                  ]
                }
                """
            ),
            f"include/{native_name}/service_core.h": _strip(
                f"""
                #pragma once

                #include <string>
                #include <string_view>

                namespace {native_name} {{

                inline constexpr const char* kProductName = "{cpp_title}";

                struct ServiceTick {{
                    int heartbeat;
                    std::string message;
                }};

                int normalize_interval_seconds(int requested_seconds);
                ServiceTick next_tick(std::string_view service_name, int previous_heartbeat);

                }}
                """
            ),
            "src/service_core.cpp": _strip(
                f"""
                #include "{native_name}/service_core.h"

                #include <algorithm>
                #include <sstream>

                namespace {native_name} {{

                int normalize_interval_seconds(int requested_seconds)
                {{
                    return std::clamp(requested_seconds, 1, 300);
                }}

                ServiceTick next_tick(std::string_view service_name, int previous_heartbeat)
                {{
                    ServiceTick tick{{previous_heartbeat + 1, {{}}}};
                    std::ostringstream message;
                    message << service_name << " heartbeat " << tick.heartbeat;
                    tick.message = message.str();
                    return tick;
                }}

                }}
                """
            ),
            "src/service_main.cpp": _strip(
                f"""
                #include "{native_name}/service_core.h"

                #include <atomic>
                #include <chrono>
                #include <iostream>
                #include <string>
                #include <thread>

                #if defined(_WIN32)
                #include <windows.h>

                namespace {{

                constexpr const wchar_t* kServiceName = L"{service_name_wide}";
                constexpr const wchar_t* kDisplayName = L"{display_name_wide}";

                std::atomic_bool g_stop_requested{{false}};
                SERVICE_STATUS_HANDLE g_status_handle = nullptr;
                SERVICE_STATUS g_status{{}};

                void log_line(const std::string& message)
                {{
                    std::cout << message << std::endl;
                    OutputDebugStringA((message + "\\n").c_str());
                }}

                void set_service_status(DWORD state, DWORD exit_code = NO_ERROR, DWORD wait_hint = 0)
                {{
                    if (g_status_handle == nullptr) {{
                        return;
                    }}

                    static DWORD checkpoint = 1;
                    g_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
                    g_status.dwCurrentState = state;
                    g_status.dwControlsAccepted =
                        state == SERVICE_RUNNING ? (SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN) : 0;
                    g_status.dwWin32ExitCode = exit_code;
                    g_status.dwServiceSpecificExitCode = 0;
                    g_status.dwWaitHint = wait_hint;
                    g_status.dwCheckPoint =
                        (state == SERVICE_RUNNING || state == SERVICE_STOPPED) ? 0 : checkpoint++;
                    SetServiceStatus(g_status_handle, &g_status);
                }}

                int run_worker_loop(bool console_mode)
                {{
                    int heartbeat = 0;
                    const int interval = {native_name}::normalize_interval_seconds(1);
                    while (!g_stop_requested.load()) {{
                        auto tick = {native_name}::next_tick("{cpp_title}", heartbeat);
                        heartbeat = tick.heartbeat;
                        log_line(tick.message);
                        if (console_mode && heartbeat >= 3) {{
                            break;
                        }}
                        std::this_thread::sleep_for(std::chrono::seconds(interval));
                    }}
                    return 0;
                }}

                void WINAPI control_handler(DWORD control)
                {{
                    switch (control) {{
                    case SERVICE_CONTROL_STOP:
                    case SERVICE_CONTROL_SHUTDOWN:
                        g_stop_requested.store(true);
                        set_service_status(SERVICE_STOP_PENDING, NO_ERROR, 1000);
                        break;
                    default:
                        break;
                    }}
                }}

                void WINAPI service_main(DWORD, LPWSTR*)
                {{
                    g_status_handle = RegisterServiceCtrlHandlerW(kServiceName, control_handler);
                    if (g_status_handle == nullptr) {{
                        return;
                    }}

                    set_service_status(SERVICE_START_PENDING, NO_ERROR, 1000);
                    g_stop_requested.store(false);
                    set_service_status(SERVICE_RUNNING);
                    run_worker_loop(false);
                    set_service_status(SERVICE_STOPPED);
                }}

                std::wstring current_executable()
                {{
                    std::wstring buffer(MAX_PATH, L'\\0');
                    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
                    if (length == 0) {{
                        return {{}};
                    }}
                    buffer.resize(length);
                    return buffer;
                }}

                DWORD install_service()
                {{
                    SC_HANDLE manager = OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CREATE_SERVICE);
                    if (manager == nullptr) {{
                        return GetLastError();
                    }}

                    std::wstring command = L"\\"" + current_executable() + L"\\"";
                    SC_HANDLE service = CreateServiceW(
                        manager,
                        kServiceName,
                        kDisplayName,
                        SERVICE_ALL_ACCESS,
                        SERVICE_WIN32_OWN_PROCESS,
                        SERVICE_DEMAND_START,
                        SERVICE_ERROR_NORMAL,
                        command.c_str(),
                        nullptr,
                        nullptr,
                        nullptr,
                        nullptr,
                        nullptr);

                    if (service == nullptr) {{
                        DWORD error = GetLastError();
                        CloseServiceHandle(manager);
                        return error == ERROR_SERVICE_EXISTS ? ERROR_SUCCESS : error;
                    }}

                    CloseServiceHandle(service);
                    CloseServiceHandle(manager);
                    return ERROR_SUCCESS;
                }}

                DWORD uninstall_service()
                {{
                    SC_HANDLE manager = OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CONNECT);
                    if (manager == nullptr) {{
                        return GetLastError();
                    }}

                    SC_HANDLE service = OpenServiceW(manager, kServiceName, DELETE | SERVICE_STOP | SERVICE_QUERY_STATUS);
                    if (service == nullptr) {{
                        DWORD error = GetLastError();
                        CloseServiceHandle(manager);
                        return error == ERROR_SERVICE_DOES_NOT_EXIST ? ERROR_SUCCESS : error;
                    }}

                    SERVICE_STATUS status{{}};
                    ControlService(service, SERVICE_CONTROL_STOP, &status);
                    DWORD error = DeleteService(service) ? ERROR_SUCCESS : GetLastError();
                    CloseServiceHandle(service);
                    CloseServiceHandle(manager);
                    return error;
                }}

                int run_service_dispatcher()
                {{
                    SERVICE_TABLE_ENTRYW table[] = {{
                        {{const_cast<LPWSTR>(kServiceName), service_main}},
                        {{nullptr, nullptr}},
                    }};
                    if (StartServiceCtrlDispatcherW(table)) {{
                        return 0;
                    }}
                    DWORD error = GetLastError();
                    if (error == ERROR_FAILED_SERVICE_CONTROLLER_CONNECT) {{
                        return run_worker_loop(true);
                    }}
                    std::cerr << "StartServiceCtrlDispatcher failed with error " << error << std::endl;
                    return 1;
                }}

                }}

                int main(int argc, char** argv)
                {{
                    if (argc > 1) {{
                        const std::string command = argv[1];
                        if (command == "--console") {{
                            return run_worker_loop(true);
                        }}
                        if (command == "--install") {{
                            DWORD error = install_service();
                            if (error != ERROR_SUCCESS) {{
                                std::cerr << "Install failed with error " << error << std::endl;
                                return 1;
                            }}
                            std::cout << "Service installed: {service_symbol}" << std::endl;
                            return 0;
                        }}
                        if (command == "--uninstall") {{
                            DWORD error = uninstall_service();
                            if (error != ERROR_SUCCESS) {{
                                std::cerr << "Uninstall failed with error " << error << std::endl;
                                return 1;
                            }}
                            std::cout << "Service removed: {service_symbol}" << std::endl;
                            return 0;
                        }}
                    }}

                    return run_service_dispatcher();
                }}

                #else

                int main()
                {{
                    int heartbeat = 0;
                    for (int index = 0; index < 3; ++index) {{
                        auto tick = {native_name}::next_tick("{cpp_title}", heartbeat);
                        heartbeat = tick.heartbeat;
                        std::cout << tick.message << std::endl;
                    }}
                    return heartbeat == 3 ? 0 : 1;
                }}

                #endif
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include <cassert>
                #include <string>

                #include "{native_name}/service_core.h"

                int main()
                {{
                    assert({native_name}::normalize_interval_seconds(-4) == 1);
                    assert({native_name}::normalize_interval_seconds(500) == 300);

                    auto first = {native_name}::next_tick("SmokeService", 0);
                    assert(first.heartbeat == 1);
                    assert(first.message.find("SmokeService") != std::string::npos);

                    auto second = {native_name}::next_tick("SmokeService", first.heartbeat);
                    assert(second.heartbeat == 2);
                    return 0;
                }}
                """
            ),
            "build.py": _strip(
                """
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True)
                    return completed.returncode


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    code = run(["cmake", "-S", ".", "-B", "build", "-DBUILD_TESTING=ON", *generator])
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", "build", "--config", "Release"])
                    if code != 0:
                        return code

                    return run(["ctest", "--test-dir", "build", "-C", "Release", "--output-on-failure"])


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                .vs
                .vscode
                *.user
                *.obj
                *.pdb
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Native C++ Windows service scaffold generated by Aegis Project Builder.

                ## What It Includes

                - `src/service_main.cpp` with a Win32 service entry point, console fallback, and install/uninstall commands.
                - `src/service_core.cpp` and `include/{native_name}/service_core.h` with testable service logic.
                - `tests/smoke.cpp` validating core service behavior without installing the service.
                - `build.py` that configures, builds, and runs CTest through CMake.

                ## Build And Validate

                ```powershell
                python build.py
                ```

                ## Run In Console Mode

                ```powershell
                .\\build\\Release\\{native_name}.exe --console
                ```

                ## Install Or Remove The Service

                Run an elevated terminal before installing or removing Windows services.

                ```powershell
                .\\build\\Release\\{native_name}.exe --install
                .\\build\\Release\\{native_name}.exe --uninstall
                ```
                """
            ),
        }


    @staticmethod
    def _cpp_windows_internals_hooking_template(project_name: str) -> dict[str, str]:
        native_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        return {
            "CMakeLists.txt": _strip(
                f"""
                cmake_minimum_required(VERSION 3.20)

                project({native_name} VERSION 0.1.0 LANGUAGES CXX)

                set(CMAKE_CXX_STANDARD 20)
                set(CMAKE_CXX_STANDARD_REQUIRED ON)
                set(CMAKE_CXX_EXTENSIONS OFF)

                add_library(${{PROJECT_NAME}}_core
                  src/instrumentation.cpp
                )
                target_include_directories(${{PROJECT_NAME}}_core PUBLIC include vendor/minhook_shim)
                target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_20)

                if(WIN32)
                  target_compile_definitions(${{PROJECT_NAME}}_core PUBLIC WIN32_LEAN_AND_MEAN NOMINMAX)
                  target_link_libraries(${{PROJECT_NAME}}_core PUBLIC psapi)
                endif()

                add_executable(${{PROJECT_NAME}} src/main.cpp)
                target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

                include(CTest)
                if(BUILD_TESTING)
                  add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
                  target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
                  add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
                endif()
                """
            ),
            f"include/{native_name}/instrumentation.h": _strip(
                f"""
                #pragma once

                #include <cstddef>
                #include <cstdint>
                #include <string>
                #include <vector>

                namespace {native_name} {{

                struct ModuleInfo {{
                    std::string name;
                    std::string path;
                    std::uintptr_t base_address{{0}};
                    std::size_t image_size{{0}};
                }};

                struct HookPlan {{
                    std::string target_module;
                    std::string target_symbol;
                    std::string replacement_symbol;
                    bool enabled{{false}};
                }};

                class HookRegistry {{
                public:
                    bool add_plan(HookPlan plan);
                    bool set_enabled(const std::string& target_symbol, bool enabled);
                    [[nodiscard]] const std::vector<HookPlan>& plans() const noexcept;
                    [[nodiscard]] std::string summary() const;

                private:
                    std::vector<HookPlan> plans_;
                }};

                std::vector<ModuleInfo> enumerate_current_process_modules();
                std::string describe_windows_internals_scope();

                }} // namespace {native_name}
                """
            ),
            f"include/{native_name}/minhook_adapter.h": _strip(
                f"""
                #pragma once

                #include <string>

                #include <MinHook.h>

                #include "{native_name}/instrumentation.h"

                namespace {native_name} {{

                enum class HookApplyResult {{
                    ready,
                    invalid_plan,
                    invalid_address,
                    backend_error,
                }};

                struct HookInstallPreview {{
                    HookApplyResult result{{HookApplyResult::backend_error}};
                    MH_STATUS backend_status{{MH_ERROR_NOT_INITIALIZED}};
                    std::string message;

                    [[nodiscard]] bool ok() const noexcept
                    {{
                        return result == HookApplyResult::ready && backend_status == MH_OK;
                    }}
                }};

                class MinHookAdapter {{
                public:
                    HookApplyResult validate_plan(const HookPlan& plan) const
                    {{
                        if (plan.target_module.empty() || plan.target_symbol.empty() || plan.replacement_symbol.empty())
                        {{
                            return HookApplyResult::invalid_plan;
                        }}
                        return HookApplyResult::ready;
                    }}

                    HookInstallPreview install_preview(
                        const HookPlan& plan,
                        void* target_address,
                        void* replacement_address,
                        void** original_address) const
                    {{
                        const HookApplyResult plan_result = validate_plan(plan);
                        if (plan_result != HookApplyResult::ready)
                        {{
                            return HookInstallPreview{{plan_result, MH_ERROR_INVALID_PARAMETER, "Invalid hook plan."}};
                        }}
                        if (target_address == nullptr || replacement_address == nullptr)
                        {{
                            return HookInstallPreview{{HookApplyResult::invalid_address, MH_ERROR_INVALID_PARAMETER, "Target and replacement addresses are required."}};
                        }}

                        MH_STATUS status = MH_Initialize();
                        if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED)
                        {{
                            return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                        }}
                        status = MH_CreateHook(target_address, replacement_address, original_address);
                        if (status != MH_OK)
                        {{
                            return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                        }}
                        status = MH_EnableHook(target_address);
                        if (status != MH_OK)
                        {{
                            return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                        }}
                        return HookInstallPreview{{HookApplyResult::ready, MH_OK, "Hook preview validated through MinHook-compatible API boundary."}};
                    }}

                    const char* backend_name() const noexcept
                    {{
                        return "MinHook API-compatible adapter";
                    }}
                }};

                }} // namespace {native_name}
                """
            ),
            "src/instrumentation.cpp": _strip(
                f"""
                #include "{native_name}/instrumentation.h"

                #include <algorithm>
                #include <sstream>
                #include <utility>

                #if defined(_WIN32)
                #include <windows.h>
                #include <psapi.h>
                #endif

                namespace {native_name} {{

                bool HookRegistry::add_plan(HookPlan plan)
                {{
                    if (plan.target_module.empty() || plan.target_symbol.empty() || plan.replacement_symbol.empty())
                    {{
                        return false;
                    }}
                    const auto duplicate = std::find_if(plans_.begin(), plans_.end(), [&](const HookPlan& existing) {{
                        return existing.target_module == plan.target_module && existing.target_symbol == plan.target_symbol;
                    }});
                    if (duplicate != plans_.end())
                    {{
                        return false;
                    }}
                    plans_.push_back(std::move(plan));
                    return true;
                }}

                bool HookRegistry::set_enabled(const std::string& target_symbol, bool enabled)
                {{
                    for (HookPlan& plan : plans_)
                    {{
                        if (plan.target_symbol == target_symbol)
                        {{
                            plan.enabled = enabled;
                            return true;
                        }}
                    }}
                    return false;
                }}

                const std::vector<HookPlan>& HookRegistry::plans() const noexcept
                {{
                    return plans_;
                }}

                std::string HookRegistry::summary() const
                {{
                    std::size_t enabled = 0;
                    for (const HookPlan& plan : plans_)
                    {{
                        enabled += plan.enabled ? 1U : 0U;
                    }}
                    std::ostringstream stream;
                    stream << "Hook plans=" << plans_.size() << " enabled=" << enabled;
                    return stream.str();
                }}

                std::vector<ModuleInfo> enumerate_current_process_modules()
                {{
                    std::vector<ModuleInfo> modules;
                #if defined(_WIN32)
                    HMODULE handles[1024]{{}};
                    DWORD needed = 0;
                    HANDLE process = GetCurrentProcess();
                    if (EnumProcessModules(process, handles, sizeof(handles), &needed))
                    {{
                        const std::size_t count = needed / sizeof(HMODULE);
                        for (std::size_t index = 0; index < count; ++index)
                        {{
                            char path[MAX_PATH]{{}};
                            MODULEINFO info{{}};
                            GetModuleFileNameExA(process, handles[index], path, MAX_PATH);
                            GetModuleInformation(process, handles[index], &info, sizeof(info));
                            ModuleInfo module;
                            module.path = path;
                            const auto slash = module.path.find_last_of("\\\\/");
                            module.name = slash == std::string::npos ? module.path : module.path.substr(slash + 1);
                            module.base_address = reinterpret_cast<std::uintptr_t>(info.lpBaseOfDll);
                            module.image_size = static_cast<std::size_t>(info.SizeOfImage);
                            modules.push_back(std::move(module));
                        }}
                    }}
                #else
                    modules.push_back(ModuleInfo{{"current-process", "portable-validation-stub", 0, 0}});
                #endif
                    return modules;
                }}

                std::string describe_windows_internals_scope()
                {{
                    return "Windows internals scaffold: modules, exported symbols, diagnostics, and authorized MinHook-style instrumentation boundaries.";
                }}

                }} // namespace {native_name}
                """
            ),
            "src/main.cpp": _strip(
                f"""
                #include <iostream>
                #include <string>

                #include "{native_name}/instrumentation.h"
                #include "{native_name}/minhook_adapter.h"

                namespace {{
                int observed_create_file_stub()
                {{
                    return 7;
                }}

                int replacement_create_file_stub()
                {{
                    return 8;
                }}
                }} // namespace

                int main(int argc, char** argv)
                {{
                    const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                    {native_name}::HookRegistry registry;
                    registry.add_plan({native_name}::HookPlan{{"kernel32.dll", "CreateFileW", "ObservedCreateFileW", false}});
                    registry.set_enabled("CreateFileW", true);

                    {native_name}::MinHookAdapter adapter;
                    void* original = nullptr;
                    const auto install = adapter.install_preview(
                        registry.plans().front(),
                        reinterpret_cast<void*>(&observed_create_file_stub),
                        reinterpret_cast<void*>(&replacement_create_file_stub),
                        &original);
                    const auto modules = {native_name}::enumerate_current_process_modules();

                    std::cout << "{title} Windows internals tool\\n";
                    std::cout << {native_name}::describe_windows_internals_scope() << "\\n";
                    std::cout << registry.summary() << "\\n";
                    std::cout << "Modules observed=" << modules.size() << "\\n";
                    std::cout << "Hook backend=" << adapter.backend_name() << "\\n";
                    std::cout << "Hook preview=" << install.message << "\\n";

                    if (!install.ok() || original == nullptr || modules.empty())
                    {{
                        std::cerr << "Instrumentation validation failed.\\n";
                        return 2;
                    }}

                    if (!validate)
                    {{
                        std::cout << "Press Enter to close...";
                        std::string line;
                        std::getline(std::cin, line);
                    }}
                    return 0;
                }}
                """
            ),
            "tests/smoke.cpp": _strip(
                f"""
                #include <string>

                #include "{native_name}/instrumentation.h"
                #include "{native_name}/minhook_adapter.h"

                namespace {{
                int target_stub()
                {{
                    return 1;
                }}

                int replacement_stub()
                {{
                    return 2;
                }}
                }} // namespace

                int main()
                {{
                    {native_name}::HookRegistry registry;
                    if (!registry.add_plan({native_name}::HookPlan{{"user32.dll", "MessageBoxW", "ObservedMessageBoxW", false}}))
                    {{
                        return 1;
                    }}
                    if (registry.add_plan({native_name}::HookPlan{{"user32.dll", "MessageBoxW", "OtherMessageBoxW", false}}))
                    {{
                        return 2;
                    }}
                    if (!registry.set_enabled("MessageBoxW", true))
                    {{
                        return 3;
                    }}

                    {native_name}::MinHookAdapter adapter;
                    if (adapter.validate_plan(registry.plans().front()) != {native_name}::HookApplyResult::ready)
                    {{
                        return 4;
                    }}
                    void* original = nullptr;
                    const auto preview = adapter.install_preview(
                        registry.plans().front(),
                        reinterpret_cast<void*>(&target_stub),
                        reinterpret_cast<void*>(&replacement_stub),
                        &original);
                    if (!preview.ok() || original == nullptr)
                    {{
                        return 7;
                    }}
                    if (registry.summary().find("enabled=1") == std::string::npos)
                    {{
                        return 5;
                    }}
                    return {native_name}::enumerate_current_process_modules().empty() ? 6 : 0;
                }}
                """
            ),
            "vendor/minhook_shim/MinHook.h": _strip(
                """
                #pragma once

                #ifdef __cplusplus
                extern "C" {
                #endif

                typedef enum MH_STATUS {
                    MH_OK = 0,
                    MH_ERROR_ALREADY_INITIALIZED = 1,
                    MH_ERROR_NOT_INITIALIZED = 2,
                    MH_ERROR_INVALID_PARAMETER = 3,
                } MH_STATUS;

                #define MH_ALL_HOOKS ((void*)0)

                static inline const char* MH_StatusToString(MH_STATUS status)
                {
                    switch (status)
                    {
                    case MH_OK:
                        return "MH_OK";
                    case MH_ERROR_ALREADY_INITIALIZED:
                        return "MH_ERROR_ALREADY_INITIALIZED";
                    case MH_ERROR_NOT_INITIALIZED:
                        return "MH_ERROR_NOT_INITIALIZED";
                    case MH_ERROR_INVALID_PARAMETER:
                        return "MH_ERROR_INVALID_PARAMETER";
                    default:
                        return "MH_UNKNOWN";
                    }
                }

                static inline MH_STATUS MH_Initialize(void)
                {
                    return MH_OK;
                }

                static inline MH_STATUS MH_Uninitialize(void)
                {
                    return MH_OK;
                }

                static inline MH_STATUS MH_CreateHook(void* target, void* detour, void** original)
                {
                    if (target == 0 || detour == 0)
                    {
                        return MH_ERROR_INVALID_PARAMETER;
                    }
                    if (original != 0)
                    {
                        *original = target;
                    }
                    return MH_OK;
                }

                static inline MH_STATUS MH_EnableHook(void* target)
                {
                    return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
                }

                static inline MH_STATUS MH_DisableHook(void* target)
                {
                    return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
                }

                static inline MH_STATUS MH_RemoveHook(void* target)
                {
                    return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
                }

                #ifdef __cplusplus
                }
                #endif
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import hashlib
                import os
                import shutil
                import subprocess
                import sys
                import tempfile
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_NAME = "{native_name}"
                BUILD_DIR = Path(
                    os.environ.get(
                        "AEGIS_CMAKE_BUILD_DIR",
                        Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                    )
                )


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    return completed.returncode


                def find_app_executable() -> Path | None:
                    names = {{APP_NAME, APP_NAME + ".exe"}}
                    for candidate in BUILD_DIR.rglob("*"):
                        if candidate.is_file() and candidate.name in names:
                            return candidate
                    return None


                def run_generated_app() -> int:
                    app = find_app_executable()
                    if app is None:
                        print("Generated Windows internals executable was not found under the CMake build directory.", file=sys.stderr)
                        return 3
                    completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                    if completed.stdout:
                        print(completed.stdout, end="")
                    if completed.stderr:
                        print(completed.stderr, end="", file=sys.stderr)
                    if completed.returncode != 0:
                        return completed.returncode
                    if "Windows internals tool" not in completed.stdout:
                        print("Expected Windows internals validation output was not found.", file=sys.stderr)
                        return 4
                    return 0


                def main() -> int:
                    if shutil.which("cmake") is None:
                        print("CMake 3.20+ is required to validate this Windows internals scaffold.", file=sys.stderr)
                        return 2

                    generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                    code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                    if code != 0:
                        return code

                    code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                    if code != 0:
                        return code

                    code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                    if code != 0:
                        return code

                    return run_generated_app()


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                build
                out
                .vs
                .vscode
                *.user
                *.obj
                *.pdb
                *.exe
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C++20 Windows internals and authorized instrumentation scaffold.

                ## Included

                - Current-process module enumeration through Win32/PSAPI when built on Windows.
                - A `HookRegistry` for planning, toggling, and validating hook definitions.
                - A `MinHookAdapter` boundary with an embedded `vendor/minhook_shim/MinHook.h` API-compatible validation shim.
                - CMake validation and smoke tests that do not patch memory or require elevated privileges.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Notes

                This scaffold is for your own applications, diagnostics, modding APIs, internal tooling,
                and authorized research. Keep real hook installation isolated behind `MinHookAdapter`,
                add explicit process/module allow-lists, and record every active hook in the registry.
                Replace `vendor/minhook_shim` with the official MinHook source when you are ready to link real hooks.
                """
            ),
        }


    @staticmethod
    def _python_sln_refactor_tool_template(project_name: str) -> dict[str, str]:
        package_name = ProjectScaffolder._python_package_name(project_name)
        title = _title_from_name(project_name)
        sln_py = _strip(
            r"""
            from __future__ import annotations

            import json
            import re
            import shutil
            import xml.etree.ElementTree as ET
            from dataclasses import dataclass
            from pathlib import Path
            from pathlib import PureWindowsPath


            PROJECT_RE = re.compile(
                r'^\s*Project\("(?P<type_guid>[^"]+)"\) = "(?P<name>[^"]+)", "(?P<path>[^"]+)", "(?P<guid>[^"]+)"$',
                re.MULTILINE,
            )


            @dataclass(frozen=True)
            class SolutionProject:
                type_guid: str
                name: str
                path: str
                guid: str
                source_solution: str = ""


            @dataclass(frozen=True)
            class SolutionDocument:
                path: Path
                projects: list[SolutionProject]


            @dataclass(frozen=True)
            class MaterializeReport:
                output_solution: str
                project_count: int
                copied_projects: int
                included_references: int
                missing_projects: list[str]

                def to_json(self) -> str:
                    return json.dumps(
                        {
                            "output_solution": self.output_solution,
                            "project_count": self.project_count,
                            "copied_projects": self.copied_projects,
                            "included_references": self.included_references,
                            "missing_projects": self.missing_projects,
                        },
                        indent=2,
                        sort_keys=True,
                    )


            @dataclass(frozen=True)
            class VcxProjectAnalysis:
                path: str
                name: str
                root_namespace: str
                configuration_types: list[str]
                platform_toolsets: list[str]
                imports: list[str]
                property_sheets: list[str]
                project_references: list[str]
                include_directories: list[str]
                library_directories: list[str]
                additional_dependencies: list[str]
                source_files: list[str]
                header_files: list[str]
                resource_files: list[str]
                unresolved_macros: list[str]

                def to_dict(self) -> dict[str, object]:
                    return {
                        "path": self.path,
                        "name": self.name,
                        "root_namespace": self.root_namespace,
                        "configuration_types": self.configuration_types,
                        "platform_toolsets": self.platform_toolsets,
                        "imports": self.imports,
                        "property_sheets": self.property_sheets,
                        "project_references": self.project_references,
                        "include_directories": self.include_directories,
                        "library_directories": self.library_directories,
                        "additional_dependencies": self.additional_dependencies,
                        "source_files": self.source_files,
                        "header_files": self.header_files,
                        "resource_files": self.resource_files,
                        "unresolved_macros": self.unresolved_macros,
                    }

                def to_json(self) -> str:
                    return json.dumps(self.to_dict(), indent=2, sort_keys=True)


            @dataclass(frozen=True)
            class SolutionGraph:
                path: str
                project_count: int
                edges: dict[str, list[str]]
                build_order: list[str]
                cycles: list[list[str]]
                missing_references: list[str]

                def to_dict(self) -> dict[str, object]:
                    return {
                        "path": self.path,
                        "project_count": self.project_count,
                        "edges": self.edges,
                        "build_order": self.build_order,
                        "cycles": self.cycles,
                        "missing_references": self.missing_references,
                    }

                def to_json(self) -> str:
                    return json.dumps(self.to_dict(), indent=2, sort_keys=True)


            def parse_projects(text: str, *, source_solution: str | Path = "") -> list[SolutionProject]:
                source = str(source_solution) if source_solution else ""
                return [
                    SolutionProject(
                        type_guid=match.group("type_guid"),
                        name=match.group("name"),
                        path=match.group("path"),
                        guid=match.group("guid"),
                        source_solution=source,
                    )
                    for match in PROJECT_RE.finditer(text)
                ]


            def read_solution(path: str | Path) -> list[SolutionProject]:
                return read_solution_document(path).projects


            def read_solution_document(path: str | Path) -> SolutionDocument:
                solution = Path(path).resolve()
                text = solution.read_text(encoding="utf-8", errors="replace")
                return SolutionDocument(path=solution, projects=parse_projects(text, source_solution=solution))


            def _solution_relative_path(value: str) -> Path:
                parsed = PureWindowsPath(value)
                if parsed.is_absolute() or parsed.drive:
                    raise ValueError(f"solution project path must be relative: {value}")
                parts = [part for part in parsed.parts if part not in ("", "\\", "/")]
                if not parts or any(part == ".." for part in parts):
                    raise ValueError(f"solution project path escapes the workspace: {value}")
                return Path(*parts)


            def _project_file_path(base: Path, project: SolutionProject) -> Path:
                return base / _solution_relative_path(project.path)


            def _project_absolute_path(project: SolutionProject) -> Path | None:
                if not project.source_solution:
                    return None
                return _project_file_path(Path(project.source_solution).parent, project).resolve()


            def _dedupe_projects(projects: list[SolutionProject]) -> list[SolutionProject]:
                unique: dict[str, SolutionProject] = {}
                for project in projects:
                    unique.setdefault(project.guid.upper(), project)
                return list(unique.values())


            def render_solution(projects: list[SolutionProject], *, solution_guid: str = "{00000000-0000-0000-0000-000000000001}") -> str:
                unique = _dedupe_projects(projects)

                lines = [
                    "Microsoft Visual Studio Solution File, Format Version 12.00",
                    "# Visual Studio Version 17",
                    "VisualStudioVersion = 17.0.31903.59",
                    "MinimumVisualStudioVersion = 10.0.40219.1",
                ]
                for project in unique:
                    lines.append(f'Project("{project.type_guid}") = "{project.name}", "{project.path}", "{project.guid}"')
                    lines.append("EndProject")
                lines.extend(
                    [
                        "Global",
                        "\tGlobalSection(SolutionConfigurationPlatforms) = preSolution",
                        "\t\tDebug|x64 = Debug|x64",
                        "\t\tRelease|x64 = Release|x64",
                        "\tEndGlobalSection",
                        "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution",
                    ]
                )
                for project in unique:
                    guid = project.guid
                    lines.extend(
                        [
                            f"\t\t{guid}.Debug|x64.ActiveCfg = Debug|x64",
                            f"\t\t{guid}.Debug|x64.Build.0 = Debug|x64",
                            f"\t\t{guid}.Release|x64.ActiveCfg = Release|x64",
                            f"\t\t{guid}.Release|x64.Build.0 = Release|x64",
                        ]
                    )
                lines.extend(
                    [
                        "\tEndGlobalSection",
                        "\tGlobalSection(SolutionProperties) = preSolution",
                        "\t\tHideSolutionNode = FALSE",
                        "\tEndGlobalSection",
                        "\tGlobalSection(ExtensibilityGlobals) = postSolution",
                        f"\t\tSolutionGuid = {solution_guid}",
                        "\tEndGlobalSection",
                        "EndGlobal",
                        "",
                    ]
                )
                return "\n".join(lines)


            def merge_solutions(paths: list[str | Path]) -> str:
                projects: list[SolutionProject] = []
                for path in paths:
                    projects.extend(read_solution(path))
                return render_solution(projects)


            def split_solution(path: str | Path, project_names: list[str]) -> str:
                wanted = {name.lower() for name in project_names}
                projects = [project for project in read_solution(path) if project.name.lower() in wanted]
                if not projects:
                    raise ValueError("no matching projects found in solution")
                return render_solution(projects)


            def _resolve_project_reference(project_file: Path, reference: str) -> Path:
                parsed = PureWindowsPath(reference)
                if parsed.is_absolute() or parsed.drive:
                    return Path(str(parsed)).resolve()
                return (project_file.parent / Path(*parsed.parts)).resolve()


            def _expand_project_references(projects: list[SolutionProject], document: SolutionDocument) -> list[SolutionProject]:
                by_path: dict[Path, SolutionProject] = {}
                for candidate in document.projects:
                    absolute = _project_absolute_path(candidate)
                    if absolute is not None:
                        by_path[absolute] = candidate

                expanded: list[SolutionProject] = []
                seen_guids: set[str] = set()
                queue = list(projects)
                while queue:
                    project = queue.pop(0)
                    guid = project.guid.upper()
                    if guid in seen_guids:
                        continue
                    seen_guids.add(guid)
                    expanded.append(project)

                    project_file = _project_absolute_path(project)
                    if project_file is None or project_file.suffix.lower() != ".vcxproj" or not project_file.exists():
                        continue
                    for reference in analyze_vcxproj(project_file).project_references:
                        referenced_file = _resolve_project_reference(project_file, reference)
                        referenced = by_path.get(referenced_file)
                        if referenced is not None and referenced.guid.upper() not in seen_guids:
                            queue.append(referenced)
                return expanded


            def _copy_project_folder(project: SolutionProject, output_dir: Path) -> tuple[bool, str]:
                if not project.source_solution:
                    return False, f"{project.name}: missing source solution"

                source_solution = Path(project.source_solution)
                source_project = _project_file_path(source_solution.parent, project)
                destination_project = _project_file_path(output_dir, project)
                if not source_project.exists():
                    return False, f"{project.name}: missing {source_project}"

                destination_project.parent.mkdir(parents=True, exist_ok=True)
                if source_project.parent == source_solution.parent:
                    shutil.copy2(source_project, destination_project)
                    return True, str(destination_project)

                shutil.copytree(source_project.parent, destination_project.parent, dirs_exist_ok=True)
                return True, str(destination_project)


            def materialize_merge(
                paths: list[str | Path],
                out_solution: str | Path,
                *,
                copy_projects: bool = False,
                include_references: bool = False,
            ) -> MaterializeReport:
                output = Path(out_solution)
                output.parent.mkdir(parents=True, exist_ok=True)
                projects: list[SolutionProject] = []
                reference_count = 0
                for path in paths:
                    document = read_solution_document(path)
                    base_projects = document.projects
                    expanded = _expand_project_references(base_projects, document) if include_references else base_projects
                    reference_count += max(0, len(_dedupe_projects(expanded)) - len(_dedupe_projects(base_projects)))
                    projects.extend(expanded)

                unique = _dedupe_projects(projects)
                output.write_text(render_solution(unique), encoding="utf-8")
                copied = 0
                missing: list[str] = []
                if copy_projects:
                    for project in unique:
                        ok, message = _copy_project_folder(project, output.parent)
                        if ok:
                            copied += 1
                        else:
                            missing.append(message)
                return MaterializeReport(str(output), len(unique), copied, reference_count, missing)


            def materialize_split(
                path: str | Path,
                project_names: list[str],
                out_solution: str | Path,
                *,
                copy_projects: bool = False,
                include_references: bool = False,
            ) -> MaterializeReport:
                document = read_solution_document(path)
                wanted = {name.lower() for name in project_names}
                projects = [project for project in document.projects if project.name.lower() in wanted]
                if not projects:
                    raise ValueError("no matching projects found in solution")
                base_count = len(_dedupe_projects(projects))
                if include_references:
                    projects = _expand_project_references(projects, document)
                reference_count = max(0, len(_dedupe_projects(projects)) - base_count)

                output = Path(out_solution)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(render_solution(projects), encoding="utf-8")
                copied = 0
                missing: list[str] = []
                if copy_projects:
                    for project in projects:
                        ok, message = _copy_project_folder(project, output.parent)
                        if ok:
                            copied += 1
                        else:
                            missing.append(message)
                return MaterializeReport(str(output), len(_dedupe_projects(projects)), copied, reference_count, missing)


            def _xml_local_name(tag: str) -> str:
                return tag.rsplit("}", 1)[-1] if "}" in tag else tag


            def _node_texts(root: ET.Element, name: str) -> list[str]:
                values: list[str] = []
                for node in root.iter():
                    if _xml_local_name(node.tag) != name:
                        continue
                    text = (node.text or "").strip()
                    if text:
                        values.append(text)
                return _dedupe_text(values)


            def _node_includes(root: ET.Element, name: str) -> list[str]:
                values: list[str] = []
                for node in root.iter():
                    if _xml_local_name(node.tag) != name:
                        continue
                    include = (node.attrib.get("Include") or "").strip()
                    if include:
                        values.append(include)
                return _dedupe_text(values)


            def _split_msbuild_list(values: list[str]) -> list[str]:
                parts: list[str] = []
                for value in values:
                    for part in value.split(";"):
                        part = part.strip()
                        if not part or part.startswith("%("):
                            continue
                        parts.append(part)
                return _dedupe_text(parts)


            def _dedupe_text(values: list[str]) -> list[str]:
                result: list[str] = []
                seen: set[str] = set()
                for value in values:
                    if value in seen:
                        continue
                    seen.add(value)
                    result.append(value)
                return result


            def _macro_values(values: list[str]) -> list[str]:
                macros: list[str] = []
                for value in values:
                    macros.extend(re.findall(r"\$\([^)]+\)", value))
                return _dedupe_text(macros)


            def analyze_vcxproj(path: str | Path) -> VcxProjectAnalysis:
                project = Path(path).resolve()
                tree = ET.parse(project)
                root = tree.getroot()

                imports: list[str] = []
                property_sheets: list[str] = []
                for node in root.iter():
                    if _xml_local_name(node.tag) != "Import":
                        continue
                    value = (node.attrib.get("Project") or "").strip()
                    if not value:
                        continue
                    imports.append(value)
                    parent_label = (node.attrib.get("Label") or "").strip().lower()
                    if "props" in value.lower() or parent_label == "propertysheets":
                        property_sheets.append(value)

                include_directories = _split_msbuild_list(_node_texts(root, "AdditionalIncludeDirectories"))
                library_directories = _split_msbuild_list(_node_texts(root, "AdditionalLibraryDirectories"))
                additional_dependencies = _split_msbuild_list(_node_texts(root, "AdditionalDependencies"))
                source_files = _node_includes(root, "ClCompile")
                header_files = _node_includes(root, "ClInclude")
                resource_files = _node_includes(root, "ResourceCompile")
                project_references = _node_includes(root, "ProjectReference")
                configuration_types = _node_texts(root, "ConfigurationType")
                platform_toolsets = _node_texts(root, "PlatformToolset")
                root_namespaces = _node_texts(root, "RootNamespace")
                macro_source = (
                    imports
                    + property_sheets
                    + project_references
                    + include_directories
                    + library_directories
                    + additional_dependencies
                    + source_files
                    + header_files
                    + resource_files
                )

                return VcxProjectAnalysis(
                    path=str(project),
                    name=project.stem,
                    root_namespace=root_namespaces[0] if root_namespaces else "",
                    configuration_types=configuration_types,
                    platform_toolsets=platform_toolsets,
                    imports=_dedupe_text(imports),
                    property_sheets=_dedupe_text(property_sheets),
                    project_references=project_references,
                    include_directories=include_directories,
                    library_directories=library_directories,
                    additional_dependencies=additional_dependencies,
                    source_files=source_files,
                    header_files=header_files,
                    resource_files=resource_files,
                    unresolved_macros=_macro_values(macro_source),
                )


            def analyze_workspace(path: str | Path) -> list[VcxProjectAnalysis]:
                target = Path(path).resolve()
                if target.suffix.lower() == ".vcxproj":
                    return [analyze_vcxproj(target)]
                if target.suffix.lower() == ".sln":
                    document = read_solution_document(target)
                    analyses: list[VcxProjectAnalysis] = []
                    for project in document.projects:
                        project_path = _project_file_path(document.path.parent, project)
                        if project_path.suffix.lower() == ".vcxproj" and project_path.exists():
                            analyses.append(analyze_vcxproj(project_path))
                    return analyses
                return [analyze_vcxproj(item) for item in sorted(target.rglob("*.vcxproj"))]


            def build_solution_graph(path: str | Path) -> SolutionGraph:
                document = read_solution_document(path)
                by_path: dict[Path, SolutionProject] = {}
                for project in document.projects:
                    absolute = _project_absolute_path(project)
                    if absolute is not None:
                        by_path[absolute] = project

                edges: dict[str, list[str]] = {project.name: [] for project in document.projects}
                missing_references: list[str] = []
                for project in document.projects:
                    project_file = _project_absolute_path(project)
                    if project_file is None or project_file.suffix.lower() != ".vcxproj":
                        continue
                    if not project_file.exists():
                        missing_references.append(f"{project.name}: missing project file {project_file}")
                        continue
                    for reference in analyze_vcxproj(project_file).project_references:
                        referenced_file = _resolve_project_reference(project_file, reference)
                        referenced = by_path.get(referenced_file)
                        if referenced is None:
                            missing_references.append(f"{project.name}: missing reference {reference}")
                            continue
                        edges[project.name].append(referenced.name)

                edges = {name: _dedupe_text(references) for name, references in edges.items()}
                state: dict[str, str] = {}
                stack: list[str] = []
                cycles: list[list[str]] = []
                build_order: list[str] = []

                def visit(name: str) -> None:
                    status = state.get(name)
                    if status == "visiting":
                        if name in stack:
                            cycles.append(stack[stack.index(name):] + [name])
                        return
                    if status == "visited":
                        return

                    state[name] = "visiting"
                    stack.append(name)
                    for dependency in edges.get(name, []):
                        if dependency in edges:
                            visit(dependency)
                    stack.pop()
                    state[name] = "visited"
                    if name not in build_order:
                        build_order.append(name)

                for project in document.projects:
                    visit(project.name)

                return SolutionGraph(
                    path=str(document.path),
                    project_count=len(document.projects),
                    edges=edges,
                    build_order=build_order,
                    cycles=cycles,
                    missing_references=_dedupe_text(missing_references),
                )
            """
        )
        cli_py = _strip(
            r"""
            from __future__ import annotations

            import argparse

            from .sln import analyze_workspace, build_solution_graph, materialize_merge, materialize_split, read_solution


            def build_parser() -> argparse.ArgumentParser:
                parser = argparse.ArgumentParser(description="Inspect, merge, or split Visual Studio solution files.")
                sub = parser.add_subparsers(dest="command", required=True)

                inspect = sub.add_parser("inspect")
                inspect.add_argument("solution")

                analyze = sub.add_parser("analyze")
                analyze.add_argument("path")

                graph = sub.add_parser("graph")
                graph.add_argument("solution")

                build_order = sub.add_parser("build-order")
                build_order.add_argument("solution")

                merge = sub.add_parser("merge")
                merge.add_argument("solutions", nargs="+")
                merge.add_argument("--out", required=True)
                merge.add_argument("--copy-projects", action="store_true")
                merge.add_argument("--include-references", action="store_true")

                split = sub.add_parser("split")
                split.add_argument("solution")
                split.add_argument("--project", action="append", required=True)
                split.add_argument("--out", required=True)
                split.add_argument("--copy-projects", action="store_true")
                split.add_argument("--include-references", action="store_true")
                return parser


            def main(argv: list[str] | None = None) -> int:
                args = build_parser().parse_args(argv)
                if args.command == "inspect":
                    projects = read_solution(args.solution)
                    for project in projects:
                        print(f"{project.name}\\t{project.path}\\t{project.guid}")
                    return 0
                if args.command == "analyze":
                    for analysis in analyze_workspace(args.path):
                        print(analysis.to_json())
                    return 0
                if args.command == "graph":
                    print(build_solution_graph(args.solution).to_json())
                    return 0
                if args.command == "build-order":
                    graph = build_solution_graph(args.solution)
                    for name in graph.build_order:
                        print(name)
                    return 0
                if args.command == "merge":
                    report = materialize_merge(
                        args.solutions,
                        args.out,
                        copy_projects=args.copy_projects,
                        include_references=args.include_references,
                    )
                    print(report.to_json())
                    return 0
                if args.command == "split":
                    report = materialize_split(
                        args.solution,
                        args.project,
                        args.out,
                        copy_projects=args.copy_projects,
                        include_references=args.include_references,
                    )
                    print(report.to_json())
                    return 0
                return 2


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )
        test_py = _strip(
            r"""
            from pathlib import Path
            import tempfile
            import unittest

            from __PACKAGE__.sln import analyze_workspace, build_solution_graph, materialize_merge, materialize_split, merge_solutions, parse_projects, split_solution


            ROOT = Path(__file__).resolve().parents[1]


            class SolutionRefactorTests(unittest.TestCase):
                def test_parse_and_merge_solutions(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"
                    two = ROOT / "samples" / "AppTwo.sln"

                    merged = merge_solutions([one, two])
                    projects = parse_projects(merged)

                    self.assertEqual([project.name for project in projects], ["AppOne", "Shared", "AppTwo"])
                    self.assertIn("AppOne\\AppOne.vcxproj", merged)
                    self.assertIn("Shared\\Shared.vcxproj", merged)
                    self.assertIn("AppTwo\\AppTwo.vcxproj", merged)

                def test_split_solution_by_project_name(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"

                    with tempfile.TemporaryDirectory() as tempdir:
                        target = Path(tempdir) / "OnlyAppOne.sln"
                        target.write_text(split_solution(one, ["AppOne"]), encoding="utf-8")
                        text = target.read_text(encoding="utf-8")

                    self.assertIn("AppOne", text)
                    self.assertNotIn("MissingProject", text)

                def test_materialize_merge_and_split_copy_project_folders(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"
                    two = ROOT / "samples" / "AppTwo.sln"

                    with tempfile.TemporaryDirectory() as tempdir:
                        merged = Path(tempdir) / "merged" / "Merged.sln"
                        split = Path(tempdir) / "split" / "OnlyAppTwo.sln"

                        merge_report = materialize_merge([one, two], merged, copy_projects=True, include_references=True)
                        split_report = materialize_split(merged, ["AppTwo"], split, copy_projects=True)

                        self.assertEqual(merge_report.project_count, 3)
                        self.assertEqual(merge_report.copied_projects, 3)
                        self.assertEqual(split_report.project_count, 1)
                        self.assertEqual(split_report.copied_projects, 1)
                        self.assertTrue((merged.parent / "AppOne" / "AppOne.vcxproj").exists())
                        self.assertTrue((merged.parent / "Shared" / "Shared.vcxproj").exists())
                        self.assertTrue((merged.parent / "AppTwo" / "AppTwo.vcxproj").exists())
                        self.assertTrue((split.parent / "AppTwo" / "AppTwo.vcxproj").exists())

                def test_split_can_include_referenced_projects(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"

                    with tempfile.TemporaryDirectory() as tempdir:
                        split = Path(tempdir) / "split" / "AppOneWithRefs.sln"

                        report = materialize_split(one, ["AppOne"], split, copy_projects=True, include_references=True)
                        text = split.read_text(encoding="utf-8")

                        self.assertEqual(report.project_count, 2)
                        self.assertEqual(report.included_references, 1)
                        self.assertEqual(report.copied_projects, 2)
                        self.assertIn("AppOne", text)
                        self.assertIn("Shared", text)
                        self.assertTrue((split.parent / "AppOne" / "AppOne.vcxproj").exists())
                        self.assertTrue((split.parent / "Shared" / "Shared.vcxproj").exists())

                def test_solution_graph_orders_project_references_first(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"

                    graph = build_solution_graph(one)

                    self.assertEqual(graph.project_count, 2)
                    self.assertEqual(graph.edges["AppOne"], ["Shared"])
                    self.assertLess(graph.build_order.index("Shared"), graph.build_order.index("AppOne"))
                    self.assertEqual(graph.cycles, [])
                    self.assertEqual(graph.missing_references, [])

                def test_analyze_solution_native_project_metadata(self) -> None:
                    one = ROOT / "samples" / "AppOne.sln"

                    analyses = analyze_workspace(one)

                    self.assertEqual(len(analyses), 2)
                    analysis = next(item for item in analyses if item.name == "AppOne")
                    self.assertEqual(analysis.root_namespace, "AppOne")
                    self.assertIn("Application", analysis.configuration_types)
                    self.assertIn("v143", analysis.platform_toolsets)
                    self.assertIn("src\\main.cpp", analysis.source_files)
                    self.assertIn("include\\app.h", analysis.header_files)
                    self.assertIn("include", analysis.include_directories)
                    self.assertIn("d3d11.lib", analysis.additional_dependencies)
                    self.assertIn("..\\Shared\\Shared.vcxproj", analysis.project_references)
                    self.assertIn("$(ProjectDir)", analysis.unresolved_macros)


            if __name__ == "__main__":
                unittest.main()
            """
        ).replace("__PACKAGE__", package_name)
        sample_one = _strip(
            """
            Microsoft Visual Studio Solution File, Format Version 12.00
            # Visual Studio Version 17
            Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AppOne", "AppOne\\AppOne.vcxproj", "{11111111-1111-1111-1111-111111111111}"
            EndProject
            Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "Shared", "Shared\\Shared.vcxproj", "{33333333-3333-3333-3333-333333333333}"
            EndProject
            Global
            EndGlobal
            """
        )
        sample_two = _strip(
            """
            Microsoft Visual Studio Solution File, Format Version 12.00
            # Visual Studio Version 17
            Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AppTwo", "AppTwo\\AppTwo.vcxproj", "{22222222-2222-2222-2222-222222222222}"
            EndProject
            Global
            EndGlobal
            """
        )
        sample_vcxproj = _strip(
            """
            <?xml version="1.0" encoding="utf-8"?>
            <Project DefaultTargets="Build" ToolsVersion="17.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemGroup Label="ProjectConfigurations">
                <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
                <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
              </ItemGroup>
              <PropertyGroup Label="Globals">
                <ProjectGuid>{PROJECT_GUID}</ProjectGuid>
                <Keyword>Win32Proj</Keyword>
                <RootNamespace>SampleNativeProject</RootNamespace>
              </PropertyGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
              <PropertyGroup Label="Configuration">
                <ConfigurationType>Application</ConfigurationType>
                <PlatformToolset>v143</PlatformToolset>
              </PropertyGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
              <ImportGroup Label="PropertySheets">
                <Import Project="$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props" />
                <Import Project="build\\shared.props" />
              </ImportGroup>
              <ItemDefinitionGroup>
                <ClCompile>
                  <AdditionalIncludeDirectories>include;$(ProjectDir)generated;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
                </ClCompile>
                <Link>
                  <AdditionalLibraryDirectories>lib;$(OutDir);%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
                  <AdditionalDependencies>user32.lib;d3d11.lib;%(AdditionalDependencies)</AdditionalDependencies>
                </Link>
              </ItemDefinitionGroup>
              <ItemGroup>
                <ClCompile Include="src\\main.cpp" />
                <ClInclude Include="include\\app.h" />
                {PROJECT_REFERENCE}
              </ItemGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
            </Project>
            """
        )
        sample_cpp = _strip(
            """
            #include <iostream>

            int main()
            {
                std::cout << "sample native project" << std::endl;
                return 0;
            }
            """
        )
        build_py = _strip(
            fr"""
            from __future__ import annotations

            import compileall
            import subprocess
            import sys
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def main() -> int:
                if not compileall.compile_dir(str(ROOT / "{package_name}"), quiet=1):
                    return 1
                code = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
                if code != 0:
                    return code
                merged = ROOT / "merged" / "merged.sln"
                split = ROOT / "split" / "split.sln"
                code = run([sys.executable, "-m", "{package_name}.cli", "merge", "samples/AppOne.sln", "samples/AppTwo.sln", "--out", str(merged), "--copy-projects"])
                if code != 0:
                    return code
                with_refs = ROOT / "split" / "app_one_with_refs.sln"
                code = run([sys.executable, "-m", "{package_name}.cli", "split", "samples/AppOne.sln", "--project", "AppOne", "--out", str(with_refs), "--copy-projects", "--include-references"])
                if code != 0:
                    return code
                code = run([sys.executable, "-m", "{package_name}.cli", "split", str(merged), "--project", "AppTwo", "--out", str(split), "--copy-projects"])
                if code != 0:
                    return code
                code = run([sys.executable, "-m", "{package_name}.cli", "analyze", "samples/AppOne.sln"])
                if code != 0:
                    return code
                code = run([sys.executable, "-m", "{package_name}.cli", "graph", "samples/AppOne.sln"])
                if code != 0:
                    return code
                code = run([sys.executable, "-m", "{package_name}.cli", "build-order", "samples/AppOne.sln"])
                if code != 0:
                    return code
                if "AppTwo" not in split.read_text(encoding="utf-8"):
                    print("Expected split solution output was not generated.", file=sys.stderr)
                    return 2
                if not (merged.parent / "AppOne" / "AppOne.vcxproj").exists():
                    print("Merged workspace did not copy AppOne.vcxproj.", file=sys.stderr)
                    return 3
                if not (merged.parent / "AppTwo" / "AppTwo.vcxproj").exists():
                    print("Merged workspace did not copy AppTwo.vcxproj.", file=sys.stderr)
                    return 4
                if not (split.parent / "AppTwo" / "AppTwo.vcxproj").exists():
                    print("Split workspace did not copy AppTwo.vcxproj.", file=sys.stderr)
                    return 5
                if not (with_refs.parent / "Shared" / "Shared.vcxproj").exists():
                    print("Reference-aware split did not copy Shared.vcxproj.", file=sys.stderr)
                    return 6
                if "d3d11.lib" not in (ROOT / "samples" / "AppOne" / "AppOne.vcxproj").read_text(encoding="utf-8"):
                    print("Sample project dependency metadata was not generated.", file=sys.stderr)
                    return 7
                print("Visual Studio solution refactor validation passed")
                return 0


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        )
        return {
            f"{package_name}/__init__.py": "__all__ = [\"sln\"]\n",
            f"{package_name}/sln.py": sln_py,
            f"{package_name}/cli.py": cli_py,
            "tests/test_sln.py": test_py,
            "samples/AppOne.sln": sample_one,
            "samples/AppTwo.sln": sample_two,
            "samples/AppOne/AppOne.vcxproj": (
                sample_vcxproj
                .replace("SampleNativeProject", "AppOne")
                .replace("{PROJECT_GUID}", "{11111111-1111-1111-1111-111111111111}")
                .replace("{PROJECT_REFERENCE}", '<ProjectReference Include="..\\Shared\\Shared.vcxproj"><Project>{33333333-3333-3333-3333-333333333333}</Project></ProjectReference>')
            ),
            "samples/AppOne/src/main.cpp": sample_cpp.replace("sample native project", "AppOne"),
            "samples/AppOne/include/app.h": "#pragma once\nconst char* app_name();\n",
            "samples/AppTwo/AppTwo.vcxproj": (
                sample_vcxproj
                .replace("SampleNativeProject", "AppTwo")
                .replace("{PROJECT_GUID}", "{22222222-2222-2222-2222-222222222222}")
                .replace("{PROJECT_REFERENCE}", "")
            ),
            "samples/AppTwo/src/main.cpp": sample_cpp.replace("sample native project", "AppTwo"),
            "samples/AppTwo/include/app.h": "#pragma once\nconst char* app_name();\n",
            "samples/Shared/Shared.vcxproj": (
                sample_vcxproj
                .replace("SampleNativeProject", "Shared")
                .replace("{PROJECT_GUID}", "{33333333-3333-3333-3333-333333333333}")
                .replace("{PROJECT_REFERENCE}", "")
            ),
            "samples/Shared/src/main.cpp": sample_cpp.replace("sample native project", "Shared"),
            "samples/Shared/include/app.h": "#pragma once\nconst char* shared_name();\n",
            "build.py": build_py,
            ".gitignore": _strip(
                """
                __pycache__
                .pytest_cache
                merged
                split
                *.pyc
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Dependency-free Visual Studio solution refactor tool for combining `.sln`
                files, splitting projects into standalone solutions, copying referenced `.vcxproj`
                folders into a new output workspace, and inspecting project paths.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Examples

                ```powershell
                python -m {package_name}.cli inspect samples/AppOne.sln
                python -m {package_name}.cli analyze samples/AppOne.sln
                python -m {package_name}.cli graph samples/AppOne.sln
                python -m {package_name}.cli build-order samples/AppOne.sln
                python -m {package_name}.cli merge samples/AppOne.sln samples/AppTwo.sln --out merged/merged.sln --copy-projects --include-references
                python -m {package_name}.cli split merged/merged.sln --project AppTwo --out split/split.sln --copy-projects
                python -m {package_name}.cli split samples/AppOne.sln --project AppOne --out split/app_one_with_refs.sln --copy-projects --include-references
                ```
                """
            ),
        }


    @staticmethod
    def _windows_kernel_driver_controller_template(project_name: str) -> dict[str, str]:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-driver"
        title = _title_from_name(safe_name)
        pascal_name = re.sub(r"[^A-Za-z0-9]+", " ", safe_name).title().replace(" ", "") or "AegisDriver"
        solution_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.solution.{safe_name}")).upper() + "}"
        driver_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.kernel.{safe_name}")).upper() + "}"
        controller_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.controller.{safe_name}")).upper() + "}"
        driver_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.kernel.{safe_name}.source")).upper() + "}"
        controller_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.driver.controller.{safe_name}.source")).upper() + "}"
        driver_project = f"{safe_name}Driver"
        controller_project = f"{safe_name}Controller"
        return {
            f"{safe_name}.sln": _strip(
                f"""
                Microsoft Visual Studio Solution File, Format Version 12.00
                # Visual Studio Version 17
                VisualStudioVersion = 17.0.31903.59
                MinimumVisualStudioVersion = 10.0.40219.1
                Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{driver_project}", "driver\\{driver_project}.vcxproj", "{driver_guid}"
                EndProject
                Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{controller_project}", "controller\\{controller_project}.vcxproj", "{controller_guid}"
                EndProject
                Global
                    GlobalSection(SolutionConfigurationPlatforms) = preSolution
                        Debug|x64 = Debug|x64
                        Release|x64 = Release|x64
                    EndGlobalSection
                    GlobalSection(ProjectConfigurationPlatforms) = postSolution
                        {driver_guid}.Debug|x64.ActiveCfg = Debug|x64
                        {driver_guid}.Debug|x64.Build.0 = Debug|x64
                        {driver_guid}.Release|x64.ActiveCfg = Release|x64
                        {driver_guid}.Release|x64.Build.0 = Release|x64
                        {controller_guid}.Debug|x64.ActiveCfg = Debug|x64
                        {controller_guid}.Debug|x64.Build.0 = Debug|x64
                        {controller_guid}.Release|x64.ActiveCfg = Release|x64
                        {controller_guid}.Release|x64.Build.0 = Release|x64
                    EndGlobalSection
                    GlobalSection(SolutionProperties) = preSolution
                        HideSolutionNode = FALSE
                    EndGlobalSection
                    GlobalSection(ExtensibilityGlobals) = postSolution
                        SolutionGuid = {solution_guid}
                    EndGlobalSection
                EndGlobal
                """
            ),
            f"driver/{driver_project}.vcxproj": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project DefaultTargets="Build" ToolsVersion="12.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup Label="ProjectConfigurations">
                    <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
                    <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
                  </ItemGroup>
                  <PropertyGroup Label="Globals">
                    <ProjectGuid>{driver_guid}</ProjectGuid>
                    <RootNamespace>{pascal_name}Driver</RootNamespace>
                    <TargetName>{driver_project}</TargetName>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                    <ConfigurationType>Driver</ConfigurationType>
                    <DriverType>WDM</DriverType>
                    <PlatformToolset>WindowsKernelModeDriver10.0</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                    <ConfigurationType>Driver</ConfigurationType>
                    <DriverType>WDM</DriverType>
                    <PlatformToolset>WindowsKernelModeDriver10.0</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
                  <ItemDefinitionGroup>
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <TreatWarningAsError>false</TreatWarningAsError>
                      <PreprocessorDefinitions>_KERNEL_MODE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
                    </ClCompile>
                  </ItemDefinitionGroup>
                  <ItemGroup>
                    <ClCompile Include="driver.c" />
                    <ClInclude Include="public.h" />
                  </ItemGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
                </Project>
                """
            ),
            f"driver/{driver_project}.vcxproj.filters": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup>
                    <Filter Include="Source Files">
                      <UniqueIdentifier>{driver_filter_guid}</UniqueIdentifier>
                      <Extensions>c;cpp;h</Extensions>
                    </Filter>
                  </ItemGroup>
                  <ItemGroup>
                    <ClCompile Include="driver.c"><Filter>Source Files</Filter></ClCompile>
                    <ClInclude Include="public.h"><Filter>Source Files</Filter></ClInclude>
                  </ItemGroup>
                </Project>
                """
            ),
            "driver/public.h": _strip(
                """
                #pragma once

                #ifdef _KERNEL_MODE
                #include <ntddk.h>
                #else
                #include <winioctl.h>
                #endif

                #define AEGIS_DEVICE_NT_NAME L"\\\\Device\\\\AegisKernelBridge"
                #define AEGIS_DEVICE_DOS_NAME L"\\\\DosDevices\\\\AegisKernelBridge"
                #define AEGIS_USER_DEVICE_PATH L"\\\\\\\\.\\\\AegisKernelBridge"
                #define IOCTL_AEGIS_PING CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_READ_DATA | FILE_WRITE_DATA)

                typedef struct _AEGIS_PING_REQUEST {
                    unsigned int version;
                    char message[128];
                } AEGIS_PING_REQUEST;

                typedef struct _AEGIS_PING_RESPONSE {
                    unsigned int version;
                    char message[128];
                } AEGIS_PING_RESPONSE;
                """
            ),
            "driver/driver.c": _strip(
                """
                #include "public.h"
                #include <ntstrsafe.h>

                static void AegisUnload(_In_ PDRIVER_OBJECT DriverObject);
                static NTSTATUS AegisCreateClose(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp);
                static NTSTATUS AegisDeviceControl(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp);
                static void AegisComplete(_Inout_ PIRP Irp, _In_ NTSTATUS Status, _In_ ULONG_PTR Information);

                NTSTATUS DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
                {
                    UNREFERENCED_PARAMETER(RegistryPath);
                    UNICODE_STRING deviceName;
                    UNICODE_STRING symbolicName;
                    PDEVICE_OBJECT deviceObject = NULL;

                    RtlInitUnicodeString(&deviceName, AEGIS_DEVICE_NT_NAME);
                    NTSTATUS status = IoCreateDevice(DriverObject, 0, &deviceName, FILE_DEVICE_UNKNOWN, FILE_DEVICE_SECURE_OPEN, FALSE, &deviceObject);
                    if (!NT_SUCCESS(status)) {
                        return status;
                    }

                    RtlInitUnicodeString(&symbolicName, AEGIS_DEVICE_DOS_NAME);
                    status = IoCreateSymbolicLink(&symbolicName, &deviceName);
                    if (!NT_SUCCESS(status)) {
                        IoDeleteDevice(deviceObject);
                        return status;
                    }

                    for (ULONG i = 0; i <= IRP_MJ_MAXIMUM_FUNCTION; ++i) {
                        DriverObject->MajorFunction[i] = AegisCreateClose;
                    }
                    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = AegisDeviceControl;
                    DriverObject->DriverUnload = AegisUnload;
                    deviceObject->Flags &= ~DO_DEVICE_INITIALIZING;
                    return STATUS_SUCCESS;
                }

                static void AegisUnload(_In_ PDRIVER_OBJECT DriverObject)
                {
                    UNICODE_STRING symbolicName;
                    RtlInitUnicodeString(&symbolicName, AEGIS_DEVICE_DOS_NAME);
                    IoDeleteSymbolicLink(&symbolicName);
                    if (DriverObject->DeviceObject != NULL) {
                        IoDeleteDevice(DriverObject->DeviceObject);
                    }
                }

                static NTSTATUS AegisCreateClose(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
                {
                    UNREFERENCED_PARAMETER(DeviceObject);
                    AegisComplete(Irp, STATUS_SUCCESS, 0);
                    return STATUS_SUCCESS;
                }

                static NTSTATUS AegisDeviceControl(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
                {
                    UNREFERENCED_PARAMETER(DeviceObject);
                    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
                    ULONG code = stack->Parameters.DeviceIoControl.IoControlCode;
                    ULONG outputLength = stack->Parameters.DeviceIoControl.OutputBufferLength;
                    void* systemBuffer = Irp->AssociatedIrp.SystemBuffer;

                    if (code != IOCTL_AEGIS_PING) {
                        AegisComplete(Irp, STATUS_INVALID_DEVICE_REQUEST, 0);
                        return STATUS_INVALID_DEVICE_REQUEST;
                    }
                    if (systemBuffer == NULL || outputLength < sizeof(AEGIS_PING_RESPONSE)) {
                        AegisComplete(Irp, STATUS_BUFFER_TOO_SMALL, 0);
                        return STATUS_BUFFER_TOO_SMALL;
                    }

                    AEGIS_PING_RESPONSE* response = (AEGIS_PING_RESPONSE*)systemBuffer;
                    RtlZeroMemory(response, sizeof(*response));
                    response->version = 1;
                    RtlStringCbCopyA(response->message, sizeof(response->message), "Aegis kernel bridge online");
                    AegisComplete(Irp, STATUS_SUCCESS, sizeof(*response));
                    return STATUS_SUCCESS;
                }

                static void AegisComplete(_Inout_ PIRP Irp, _In_ NTSTATUS Status, _In_ ULONG_PTR Information)
                {
                    Irp->IoStatus.Status = Status;
                    Irp->IoStatus.Information = Information;
                    IoCompleteRequest(Irp, IO_NO_INCREMENT);
                }
                """
            ),
            f"controller/{controller_project}.vcxproj": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup Label="ProjectConfigurations">
                    <ProjectConfiguration Include="Debug|x64"><Configuration>Debug</Configuration><Platform>x64</Platform></ProjectConfiguration>
                    <ProjectConfiguration Include="Release|x64"><Configuration>Release</Configuration><Platform>x64</Platform></ProjectConfiguration>
                  </ItemGroup>
                  <PropertyGroup Label="Globals">
                    <VCProjectVersion>17.0</VCProjectVersion>
                    <Keyword>Win32Proj</Keyword>
                    <ProjectGuid>{controller_guid}</ProjectGuid>
                    <RootNamespace>{pascal_name}Controller</RootNamespace>
                    <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>true</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                    <ConfigurationType>Application</ConfigurationType>
                    <UseDebugLibraries>false</UseDebugLibraries>
                    <PlatformToolset>v143</PlatformToolset>
                    <WholeProgramOptimization>true</WholeProgramOptimization>
                    <CharacterSet>Unicode</CharacterSet>
                  </PropertyGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
                  <ItemDefinitionGroup>
                    <ClCompile>
                      <WarningLevel>Level4</WarningLevel>
                      <SDLCheck>true</SDLCheck>
                      <ConformanceMode>true</ConformanceMode>
                      <LanguageStandard>stdcpp17</LanguageStandard>
                      <AdditionalIncludeDirectories>..\\driver;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
                    </ClCompile>
                    <Link>
                      <SubSystem>Console</SubSystem>
                    </Link>
                  </ItemDefinitionGroup>
                  <ItemGroup>
                    <ClCompile Include="main.cpp" />
                  </ItemGroup>
                  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
                </Project>
                """
            ),
            f"controller/{controller_project}.vcxproj.filters": _strip(
                f"""
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                  <ItemGroup>
                    <Filter Include="Source Files">
                      <UniqueIdentifier>{controller_filter_guid}</UniqueIdentifier>
                      <Extensions>cpp;cxx;cc</Extensions>
                    </Filter>
                  </ItemGroup>
                  <ItemGroup>
                    <ClCompile Include="main.cpp"><Filter>Source Files</Filter></ClCompile>
                  </ItemGroup>
                </Project>
                """
            ),
            "controller/main.cpp": _strip(
                """
                #include <windows.h>
                #include <iostream>
                #include <string>
                #include "../driver/public.h"

                int main()
                {
                    std::wcout << L"Aegis driver controller starting..." << std::endl;

                    HANDLE device = CreateFileW(AEGIS_USER_DEVICE_PATH, GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
                    if (device == INVALID_HANDLE_VALUE) {
                        std::wcout << L"Driver device is not open yet. Load the signed driver, then run this controller again." << std::endl;
                        std::wcout << L"Press Enter to close...";
                        std::wstring line;
                        std::getline(std::wcin, line);
                        return 1;
                    }

                    AEGIS_PING_REQUEST request{};
                    request.version = 1;
                    strcpy_s(request.message, "hello from user mode");

                    AEGIS_PING_RESPONSE response{};
                    DWORD bytesReturned = 0;
                    BOOL ok = DeviceIoControl(device, IOCTL_AEGIS_PING, &request, sizeof(request), &response, sizeof(response), &bytesReturned, nullptr);
                    CloseHandle(device);

                    if (!ok) {
                        std::wcout << L"DeviceIoControl failed with error " << GetLastError() << std::endl;
                        std::wcout << L"Press Enter to close...";
                        std::wstring line;
                        std::getline(std::wcin, line);
                        return 2;
                    }

                    std::cout << "Kernel response: " << response.message << std::endl;
                    std::cout << "Bytes returned: " << bytesReturned << std::endl;
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                    return 0;
                }
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import os
                import shutil
                import subprocess
                import sys
                from pathlib import Path

                ROOT = Path(__file__).resolve().parent
                CONTROLLER_PROJECT = ROOT / "controller" / "{controller_project}.vcxproj"
                DRIVER_PROJECT = ROOT / "driver" / "{driver_project}.vcxproj"

                def candidate_msbuild_paths() -> list[Path]:
                    candidates: list[Path] = []
                    explicit = os.environ.get("MSBUILD_EXE")
                    if explicit:
                        candidates.append(Path(explicit))
                    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
                    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
                    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
                    if vswhere.exists():
                        completed = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.Component.MSBuild", "-find", r"MSBuild\\**\\Bin\\MSBuild.exe"], text=True, capture_output=True, check=False)
                        for line in completed.stdout.splitlines():
                            if line.strip():
                                candidates.append(Path(line.strip()))
                    for root in (Path(program_files), Path(program_files_x86)):
                        vs2022 = root / "Microsoft Visual Studio" / "2022"
                        for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "MSBuild.exe")
                            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "amd64" / "MSBuild.exe")
                    on_path = shutil.which("msbuild")
                    if on_path:
                        candidates.append(Path(on_path))
                    return candidates

                def find_msbuild() -> Path | None:
                    seen: set[str] = set()
                    for candidate in candidate_msbuild_paths():
                        key = str(candidate).lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        if candidate.exists():
                            return candidate
                    return None

                def run_msbuild(msbuild: Path, project: Path) -> int:
                    command = [str(msbuild), str(project), "/p:Configuration=Release", "/p:Platform=x64"]
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))

                def main() -> int:
                    msbuild = find_msbuild()
                    if msbuild is None:
                        print("MSBuild was not found. Set MSBUILD_EXE or install Visual Studio Build Tools.", file=sys.stderr)
                        return 2
                    controller_rc = run_msbuild(msbuild, CONTROLLER_PROJECT)
                    build_driver = "--driver" in sys.argv or os.environ.get("AEGIS_BUILD_DRIVER") == "1"
                    if not build_driver:
                        print("Controller built. Driver project is present; pass --driver or set AEGIS_BUILD_DRIVER=1 for the WDK driver build.")
                        return controller_rc
                    driver_rc = run_msbuild(msbuild, DRIVER_PROJECT)
                    return controller_rc or driver_rc

                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                .vs
                x64
                Debug
                Release
                *.user
                *.obj
                *.pdb
                *.ilk
                *.exe
                *.sys
                *.cat
                *.inf
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Windows driver/controller starter generated by Aegis Project Builder.

                ## Layout

                - `driver/` contains a WDM driver skeleton with a named device and IOCTL handler.
                - `controller/` contains a C++ console controller that opens the device and calls `DeviceIoControl`.
                - `driver/public.h` shares the IOCTL contract between user mode and kernel mode.

                ## Build

                ```powershell
                python build.py
                ```

                `python build.py` builds the user-mode controller and builds the driver automatically when the WDK is detected. Use `python build.py --driver` to force a driver build.
                """
            ),
        }


    @staticmethod
    def _electron_react_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "main": "dist/main/index.js",
                  "scripts": {{
                    "dev": "electron-vite dev",
                    "build": "tsc --noEmit && electron-vite build",
                    "preview": "electron-vite preview"
                  }},
                  "dependencies": {{
                    "@vitejs/plugin-react": "^4.3.4",
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0"
                  }},
                  "devDependencies": {{
                    "@swc/core": "^1.15.32",
                    "@types/node": "^22.10.1",
                    "@types/react": "^19.0.1",
                    "@types/react-dom": "^19.0.1",
                    "electron": "^33.2.1",
                    "electron-vite": "^5.0.0",
                    "typescript": "^5.7.2",
                    "vite": "^6.0.3"
                  }}
                }}
                """
            ),
            "electron.vite.config.ts": _strip(
                """
                import { defineConfig, externalizeDepsPlugin } from 'electron-vite';
                import react from '@vitejs/plugin-react';

                export default defineConfig({
                  main: {
                    plugins: [externalizeDepsPlugin()]
                  },
                  preload: {
                    plugins: [externalizeDepsPlugin()]
                  },
                  renderer: {
                    plugins: [react()]
                  }
                });
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "jsx": "react-jsx",
                    "strict": true,
                    "skipLibCheck": true,
                    "isolatedModules": true,
                    "types": ["node"]
                  },
                  "include": ["src/**/*.ts", "src/**/*.tsx", "electron.vite.config.ts"]
                }
                """
            ),
            "src/main/index.ts": _strip(
                """
                import { app, BrowserWindow } from 'electron';
                import { join } from 'node:path';

                const createWindow = () => {
                  const win = new BrowserWindow({
                    width: 1280,
                    height: 820,
                    minWidth: 960,
                    minHeight: 680,
                    backgroundColor: '#071018',
                    webPreferences: {
                      preload: join(__dirname, '../preload/index.js'),
                      contextIsolation: true,
                      nodeIntegration: false
                    }
                  });

                  if (process.env.ELECTRON_RENDERER_URL) {
                    win.loadURL(process.env.ELECTRON_RENDERER_URL);
                  } else {
                    win.loadFile(join(__dirname, '../renderer/index.html'));
                  }
                };

                app.whenReady().then(createWindow);
                app.on('window-all-closed', () => {
                  if (process.platform !== 'darwin') app.quit();
                });
                """
            ),
            "src/preload/index.ts": _strip(
                """
                import { contextBridge } from 'electron';

                contextBridge.exposeInMainWorld('AegisDesktop', {
                  platform: process.platform
                });
                """
            ),
            "src/renderer/index.html": _strip(
                f"""
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                    <title>{title}</title>
                  </head>
                  <body>
                    <div id="root"></div>
                    <script type="module" src="/src/main.tsx"></script>
                  </body>
                </html>
                """
            ),
            "src/renderer/src/main.tsx": _strip(
                """
                import React from 'react';
                import { createRoot } from 'react-dom/client';
                import { App } from './App';
                import './styles.css';

                createRoot(document.getElementById('root')!).render(
                  <React.StrictMode>
                    <App />
                  </React.StrictMode>
                );
                """
            ),
            "src/renderer/src/App.tsx": _strip(
                f"""
                const actions = ['Plan', 'Build', 'Validate', 'Ship'];

                export function App() {{
                  return (
                    <main className="shell">
                      <section className="hero">
                        <p className="eyebrow">Desktop workspace</p>
                        <h1>{title}</h1>
                        <p>Native-ready Electron shell with a secure preload bridge and React renderer.</p>
                      </section>
                      <section className="grid">
                        {{actions.map((action) => (
                          <article key={{action}}>
                            <span>{{action}}</span>
                            <p>Wire this lane to the app workflow you want Aegis to automate next.</p>
                          </article>
                        ))}}
                      </section>
                    </main>
                  );
                }}
                """
            ),
            "src/renderer/src/styles.css": _strip(
                """
                :root {
                  color: #edf7f3;
                  background: #071018;
                  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }

                body { margin: 0; min-height: 100vh; }
                .shell { min-height: 100vh; padding: 48px; background: radial-gradient(circle at top left, #123b35, transparent 34%), #071018; }
                .hero { max-width: 760px; }
                .eyebrow { color: #27de7d; text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; }
                h1 { font-size: 48px; margin: 8px 0 16px; }
                p { color: #aab7c4; line-height: 1.65; }
                .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 36px; }
                article { border: 1px solid #203040; border-radius: 8px; background: #0c1620; padding: 18px; }
                span { color: #27de7d; font-weight: 700; }
                @media (max-width: 860px) { .shell { padding: 28px; } .grid { grid-template-columns: 1fr; } h1 { font-size: 36px; } }
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                out
                *.log
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Electron React TypeScript desktop app generated by Aegis Project Builder.

                ```bash
                npm install
                npm run dev
                npm run build
                ```
                """
            ),
        }


    @staticmethod
    def _expo_react_native_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "scripts": {{
                    "start": "expo start",
                    "android": "expo start --android",
                    "ios": "expo start --ios",
                    "web": "expo start --web",
                    "typecheck": "tsc --noEmit"
                  }},
                  "dependencies": {{
                    "@expo/vector-icons": "^14.0.4",
                    "expo": "^52.0.20",
                    "expo-status-bar": "~2.0.0",
                    "react": "18.3.1",
                    "react-native": "0.76.5",
                    "react-native-safe-area-context": "4.12.0"
                  }},
                  "devDependencies": {{
                    "@types/react": "~18.3.12",
                    "typescript": "^5.7.2"
                  }}
                }}
                """
            ),
            "app.json": _strip(
                f"""
                {{
                  "expo": {{
                    "name": "{title}",
                    "slug": "{project_name}",
                    "version": "0.1.0",
                    "orientation": "portrait",
                    "userInterfaceStyle": "dark",
                    "splash": {{
                      "backgroundColor": "#071018"
                    }},
                    "assetBundlePatterns": ["**/*"],
                    "ios": {{ "supportsTablet": true }},
                    "android": {{ "adaptiveIcon": {{ "backgroundColor": "#071018" }} }}
                  }}
                }}
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "extends": "expo/tsconfig.base",
                  "compilerOptions": {
                    "strict": true,
                    "noUncheckedIndexedAccess": true
                  }
                }
                """
            ),
            "App.tsx": _strip(
                """
                import { StatusBar } from 'expo-status-bar';
                import { SafeAreaView } from 'react-native-safe-area-context';
                import { HomeScreen } from './src/screens/HomeScreen';
                import { colors } from './src/theme';

                export default function App() {
                  return (
                    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
                      <StatusBar style="light" />
                      <HomeScreen />
                    </SafeAreaView>
                  );
                }
                """
            ),
            "src/theme.ts": _strip(
                """
                export const colors = {
                  background: '#071018',
                  panel: '#0c1620',
                  border: '#203040',
                  text: '#edf7f3',
                  muted: '#9aa8b6',
                  accent: '#27de7d'
                };
                """
            ),
            "src/screens/HomeScreen.tsx": _strip(
                f"""
                import {{ StyleSheet, Text, View }} from 'react-native';
                import {{ colors }} from '../theme';

                const lanes = ['Capture', 'Reason', 'Act'];

                export function HomeScreen() {{
                  return (
                    <View style={{styles.screen}}>
                      <Text style={{styles.eyebrow}}>Mobile workspace</Text>
                      <Text style={{styles.title}}>{title}</Text>
                      <Text style={{styles.subtitle}}>Expo starter ready for iOS, Android, and web.</Text>
                      <View style={{styles.grid}}>
                        {{lanes.map((lane) => (
                          <View key={{lane}} style={{styles.card}}>
                            <Text style={{styles.cardTitle}}>{{lane}}</Text>
                            <Text style={{styles.cardText}}>Connect this lane to your first mobile workflow.</Text>
                          </View>
                        ))}}
                      </View>
                    </View>
                  );
                }}

                const styles = StyleSheet.create({{
                  screen: {{ flex: 1, padding: 24, justifyContent: 'center' }},
                  eyebrow: {{ color: colors.accent, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' }},
                  title: {{ color: colors.text, fontSize: 40, fontWeight: '800', marginTop: 10 }},
                  subtitle: {{ color: colors.muted, fontSize: 16, marginTop: 12, lineHeight: 24 }},
                  grid: {{ gap: 12, marginTop: 28 }},
                  card: {{ backgroundColor: colors.panel, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 16 }},
                  cardTitle: {{ color: colors.text, fontWeight: '800', fontSize: 18 }},
                  cardText: {{ color: colors.muted, marginTop: 6, lineHeight: 20 }}
                }});
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                .expo
                dist
                npm-debug.log*
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Expo React Native app generated by Aegis Project Builder.

                ```bash
                npm install
                npm run start
                npm run typecheck
                ```
                """
            ),
        }


    @staticmethod
    def _django_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        return {
            "requirements.txt": _strip(
                """
                Django>=5.1,<5.2
                """
            ),
            "manage.py": _strip(
                """
                #!/usr/bin/env python
                import os
                import sys

                def main() -> None:
                    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                    from django.core.management import execute_from_command_line
                    execute_from_command_line(sys.argv)

                if __name__ == "__main__":
                    main()
                """
            ),
            "config/__init__.py": "",
            "config/settings.py": _strip(
                f"""
                from pathlib import Path

                BASE_DIR = Path(__file__).resolve().parent.parent
                SECRET_KEY = "django-insecure-change-me"
                DEBUG = True
                ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

                INSTALLED_APPS = [
                    "django.contrib.admin",
                    "django.contrib.auth",
                    "django.contrib.contenttypes",
                    "django.contrib.sessions",
                    "django.contrib.messages",
                    "django.contrib.staticfiles",
                    "core",
                ]

                MIDDLEWARE = [
                    "django.middleware.security.SecurityMiddleware",
                    "django.contrib.sessions.middleware.SessionMiddleware",
                    "django.middleware.common.CommonMiddleware",
                    "django.middleware.csrf.CsrfViewMiddleware",
                    "django.contrib.auth.middleware.AuthenticationMiddleware",
                    "django.contrib.messages.middleware.MessageMiddleware",
                    "django.middleware.clickjacking.XFrameOptionsMiddleware",
                ]

                ROOT_URLCONF = "config.urls"
                TEMPLATES = [
                    {{
                        "BACKEND": "django.template.backends.django.DjangoTemplates",
                        "DIRS": [BASE_DIR / "templates"],
                        "APP_DIRS": True,
                        "OPTIONS": {{"context_processors": [
                            "django.template.context_processors.request",
                            "django.contrib.auth.context_processors.auth",
                            "django.contrib.messages.context_processors.messages",
                        ]}},
                    }}
                ]
                WSGI_APPLICATION = "config.wsgi.application"
                DATABASES = {{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}}}
                LANGUAGE_CODE = "en-us"
                TIME_ZONE = "UTC"
                USE_I18N = True
                USE_TZ = True
                STATIC_URL = "static/"
                DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
                AEGIS_APP_NAME = "{title}"
                """
            ),
            "config/urls.py": _strip(
                """
                from django.contrib import admin
                from django.urls import include, path

                urlpatterns = [
                    path("admin/", admin.site.urls),
                    path("", include("core.urls")),
                ]
                """
            ),
            "config/asgi.py": _strip(
                """
                import os
                from django.core.asgi import get_asgi_application

                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                application = get_asgi_application()
                """
            ),
            "config/wsgi.py": _strip(
                """
                import os
                from django.core.wsgi import get_wsgi_application

                os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
                application = get_wsgi_application()
                """
            ),
            "core/__init__.py": "",
            "core/apps.py": _strip(
                """
                from django.apps import AppConfig

                class CoreConfig(AppConfig):
                    default_auto_field = "django.db.models.BigAutoField"
                    name = "core"
                """
            ),
            "core/urls.py": _strip(
                """
                from django.urls import path
                from . import views

                urlpatterns = [
                    path("", views.home, name="home"),
                    path("health/", views.health, name="health"),
                ]
                """
            ),
            "core/views.py": _strip(
                """
                from django.conf import settings
                from django.http import JsonResponse
                from django.shortcuts import render

                def home(request):
                    return render(request, "core/home.html", {"app_name": settings.AEGIS_APP_NAME})

                def health(request):
                    return JsonResponse({"ok": True, "app": settings.AEGIS_APP_NAME})
                """
            ),
            "core/tests.py": _strip(
                """
                from django.test import Client, TestCase

                class HealthTests(TestCase):
                    def test_health_route(self):
                        response = Client().get("/health/")
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.json()["ok"])
                """
            ),
            "templates/core/home.html": _strip(
                """
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>{{ app_name }}</title>
                    <style>
                      body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #071018; color: #edf7f3; font-family: system-ui, sans-serif; }
                      main { width: min(720px, calc(100vw - 48px)); }
                      p { color: #9aa8b6; line-height: 1.7; }
                      strong { color: #27de7d; }
                    </style>
                  </head>
                  <body>
                    <main>
                      <strong>Django workspace</strong>
                      <h1>{{ app_name }}</h1>
                      <p>Your server-rendered app is ready for models, views, templates, auth, and admin workflows.</p>
                    </main>
                  </body>
                </html>
                """
            ),
            ".gitignore": _strip(
                """
                __pycache__
                *.pyc
                db.sqlite3
                .env
                .venv
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Django web app generated by Aegis Project Builder.

                ```bash
                python -m pip install -r requirements.txt
                python manage.py migrate
                python manage.py runserver
                python manage.py test
                ```
                """
            ),
        }


    @staticmethod
    def _rust_cli_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        crate_name = ProjectScaffolder._python_package_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "Cargo.toml": _strip(
                f"""
                [package]
                name = "{package_name}"
                version = "0.1.0"
                edition = "2021"

                [lib]
                name = "{crate_name}"
                path = "src/lib.rs"

                [[bin]]
                name = "{package_name}"
                path = "src/main.rs"
                """
            ),
            "src/lib.rs": _strip(
                f"""
                pub fn greeting(target: &str) -> String {{
                    format!("{title} ready for {{target}}")
                }}

                #[cfg(test)]
                mod tests {{
                    use super::greeting;

                    #[test]
                    fn builds_greeting() {{
                        assert!(greeting("Aegis").contains("Aegis"));
                    }}
                }}
                """
            ),
            "src/main.rs": _strip(
                f"""
                use {crate_name}::greeting;

                fn main() {{
                    let target = std::env::args().nth(1).unwrap_or_else(|| "Aegis".to_string());
                    println!("{{}}", greeting(&target));
                }}
                """
            ),
            ".gitignore": _strip(
                """
                target
                Cargo.lock
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Rust CLI generated by Aegis Project Builder.

                ```bash
                cargo run -- Aegis
                cargo test
                ```
                """
            ),
        }


    @staticmethod
    def _go_http_api_template(project_name: str) -> dict[str, str]:
        module_name = f"example.com/{ProjectScaffolder._manifest_package_name(project_name)}"
        title = _title_from_name(project_name)
        return {
            "go.mod": _strip(
                f"""
                module {module_name}

                go 1.22
                """
            ),
            "cmd/server/main.go": _strip(
                f"""
                package main

                import (
                    "log"
                    "net/http"

                    "{module_name}/internal/api"
                )

                func main() {{
                    mux := api.NewRouter("{title}")
                    log.Println("listening on http://127.0.0.1:8080")
                    if err := http.ListenAndServe(":8080", mux); err != nil {{
                        log.Fatal(err)
                    }}
                }}
                """
            ),
            "internal/api/router.go": _strip(
                """
                package api

                import (
                    "encoding/json"
                    "net/http"
                )

                type HealthResponse struct {
                    OK  bool   `json:"ok"`
                    App string `json:"app"`
                }

                func NewRouter(appName string) http.Handler {
                    mux := http.NewServeMux()
                    mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
                        w.Header().Set("Content-Type", "application/json")
                        _ = json.NewEncoder(w).Encode(HealthResponse{OK: true, App: appName})
                    })
                    return mux
                }
                """
            ),
            "internal/api/router_test.go": _strip(
                """
                package api

                import (
                    "net/http"
                    "net/http/httptest"
                    "testing"
                )

                func TestHealth(t *testing.T) {
                    request := httptest.NewRequest(http.MethodGet, "/health", nil)
                    recorder := httptest.NewRecorder()

                    NewRouter("Aegis").ServeHTTP(recorder, request)

                    if recorder.Code != http.StatusOK {
                        t.Fatalf("expected 200, got %d", recorder.Code)
                    }
                }
                """
            ),
            ".gitignore": _strip(
                """
                bin
                coverage.out
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Go HTTP API generated by Aegis Project Builder.

                ```bash
                go mod tidy
                go run ./cmd/server
                go test ./...
                ```
                """
            ),
        }


    @staticmethod
    def _dotnet_webapi_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        safe_name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]+", project_name) if part) or "AegisApi"
        return {
            f"{safe_name}.sln": _strip(
                f"""
                Microsoft Visual Studio Solution File, Format Version 12.00
                # Visual Studio Version 17
                Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "{safe_name}.Api", "src/{safe_name}.Api/{safe_name}.Api.csproj", "{{11111111-1111-1111-1111-111111111111}}"
                EndProject
                Project("{{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}}") = "{safe_name}.Tests", "tests/{safe_name}.Tests/{safe_name}.Tests.csproj", "{{22222222-2222-2222-2222-222222222222}}"
                EndProject
                Global
                EndGlobal
                """
            ),
            f"src/{safe_name}.Api/{safe_name}.Api.csproj": _strip(
                """
                <Project Sdk="Microsoft.NET.Sdk.Web">
                  <PropertyGroup>
                    <TargetFramework>net8.0</TargetFramework>
                    <Nullable>enable</Nullable>
                    <ImplicitUsings>enable</ImplicitUsings>
                  </PropertyGroup>
                </Project>
                """
            ),
            f"src/{safe_name}.Api/Program.cs": _strip(
                f"""
                var builder = WebApplication.CreateBuilder(args);
                var app = builder.Build();

                app.MapGet("/health", () => Results.Ok(new HealthResponse(true, "{title}")));
                app.MapGet("/", () => Results.Ok(new {{ app = "{title}", status = "ready" }}));

                app.Run();

                public partial class Program {{ }}
                public sealed record HealthResponse(bool Ok, string App);
                """
            ),
            f"tests/{safe_name}.Tests/{safe_name}.Tests.csproj": _strip(
                f"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>net8.0</TargetFramework>
                    <Nullable>enable</Nullable>
                    <ImplicitUsings>enable</ImplicitUsings>
                    <IsPackable>false</IsPackable>
                  </PropertyGroup>
                  <ItemGroup>
                    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.0.11" />
                    <PackageReference Include="xunit" Version="2.9.2" />
                    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
                  </ItemGroup>
                  <ItemGroup>
                    <ProjectReference Include="../../src/{safe_name}.Api/{safe_name}.Api.csproj" />
                  </ItemGroup>
                </Project>
                """
            ),
            f"tests/{safe_name}.Tests/HealthTests.cs": _strip(
                """
                using System.Net;
                using Microsoft.AspNetCore.Mvc.Testing;
                using Xunit;

                public sealed class HealthTests : IClassFixture<WebApplicationFactory<Program>>
                {
                    private readonly WebApplicationFactory<Program> _factory;

                    public HealthTests(WebApplicationFactory<Program> factory)
                    {
                        _factory = factory;
                    }

                    [Fact]
                    public async Task Health_ReturnsOk()
                    {
                        var response = await _factory.CreateClient().GetAsync("/health");
                        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                    }
                }
                """
            ),
            ".gitignore": _strip(
                """
                bin
                obj
                .vs
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                ASP.NET Core Minimal API generated by Aegis Project Builder.

                ```bash
                dotnet restore
                dotnet run --project src/{safe_name}.Api
                dotnet test
                ```
                """
            ),
        }


    @staticmethod
    def _dotnet_console_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        safe_name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]+", project_name) if part) or "AegisTool"
        cs_title = title.replace("\\", "\\\\").replace('"', '\\"')
        return {
            f"src/{safe_name}/{safe_name}.csproj": _strip(
                """
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <OutputType>Exe</OutputType>
                    <TargetFramework>net8.0</TargetFramework>
                    <ImplicitUsings>enable</ImplicitUsings>
                    <Nullable>enable</Nullable>
                    <AssemblyName>$(MSBuildProjectName)</AssemblyName>
                  </PropertyGroup>
                </Project>
                """
            ),
            f"src/{safe_name}/Program.cs": _strip(
                f"""
                using {safe_name};

                return ConsoleApp.Run(args);
                """
            ),
            f"src/{safe_name}/ToolEngine.cs": _strip(
                f"""
                namespace {safe_name};

                public sealed record AppOptions(string Name, int Count, bool SelfTest);

                public static class ConsoleApp
                {{
                    public static int Run(string[] args)
                    {{
                        try
                        {{
                            var options = Parse(args);
                            if (options.SelfTest)
                            {{
                                return RunSelfTest();
                            }}

                            foreach (var line in BuildOutput(options))
                            {{
                                Console.WriteLine(line);
                            }}
                            return 0;
                        }}
                        catch (ArgumentException ex)
                        {{
                            Console.Error.WriteLine(ex.Message);
                            PrintUsage();
                            return 2;
                        }}
                    }}

                    public static AppOptions Parse(IReadOnlyList<string> args)
                    {{
                        var name = "Aegis";
                        var count = 1;
                        var selfTest = false;

                        for (var index = 0; index < args.Count; index++)
                        {{
                            var token = args[index];
                            switch (token)
                            {{
                                case "--self-test":
                                    selfTest = true;
                                    break;
                                case "--name":
                                    name = ReadValue(args, ref index, "--name");
                                    break;
                                case "--count":
                                    var rawCount = ReadValue(args, ref index, "--count");
                                    if (!int.TryParse(rawCount, out count) || count < 1 || count > 25)
                                    {{
                                        throw new ArgumentException("--count must be an integer from 1 to 25.");
                                    }}
                                    break;
                                case "--help":
                                case "-h":
                                    PrintUsage();
                                    Environment.ExitCode = 0;
                                    break;
                                default:
                                    throw new ArgumentException($"Unknown argument: {{token}}");
                            }}
                        }}

                        return new AppOptions(name.Trim(), count, selfTest);
                    }}

                    public static IReadOnlyList<string> BuildOutput(AppOptions options)
                    {{
                        if (string.IsNullOrWhiteSpace(options.Name))
                        {{
                            throw new ArgumentException("--name cannot be empty.");
                        }}

                        var lines = new List<string>();
                        for (var index = 1; index <= options.Count; index++)
                        {{
                            lines.Add($"{cs_title} ready for {{options.Name}} ({{index}}/{{options.Count}})");
                        }}
                        return lines;
                    }}

                    private static string ReadValue(IReadOnlyList<string> args, ref int index, string option)
                    {{
                        if (index + 1 >= args.Count)
                        {{
                            throw new ArgumentException($"{{option}} requires a value.");
                        }}

                        index++;
                        return args[index];
                    }}

                    private static int RunSelfTest()
                    {{
                        var parsed = Parse(new[] {{ "--name", "Validation", "--count", "2" }});
                        var output = BuildOutput(parsed);
                        if (parsed.Name != "Validation" || parsed.Count != 2 || output.Count != 2)
                        {{
                            Console.Error.WriteLine("Self-test failed: parser/output mismatch.");
                            return 1;
                        }}
                        if (!output[0].Contains("{cs_title}") || !output[0].Contains("Validation"))
                        {{
                            Console.Error.WriteLine("Self-test failed: output content mismatch.");
                            return 1;
                        }}

                        Console.WriteLine("Self-test passed.");
                        return 0;
                    }}

                    private static void PrintUsage()
                    {{
                        Console.WriteLine("{cs_title}");
                        Console.WriteLine("Usage: {safe_name} [--name VALUE] [--count 1-25]");
                    }}
                }}
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import shutil
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                PROJECT = ROOT / "src" / "{safe_name}" / "{safe_name}.csproj"


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))


                def main() -> int:
                    if shutil.which("dotnet") is None:
                        print(".NET SDK was not found on PATH. Install .NET 8+ and rerun this script.", file=sys.stderr)
                        return 2

                    if not PROJECT.exists():
                        print(f"Project file not found: {{PROJECT}}", file=sys.stderr)
                        return 2

                    code = run(["dotnet", "restore", str(PROJECT)])
                    if code != 0:
                        return code

                    code = run(["dotnet", "build", str(PROJECT), "--configuration", "Release", "--no-restore"])
                    if code != 0:
                        return code

                    return run(
                        [
                            "dotnet",
                            "run",
                            "--project",
                            str(PROJECT),
                            "--configuration",
                            "Release",
                            "--no-build",
                            "--",
                            "--self-test",
                        ]
                    )


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                bin
                obj
                .vs
                .vscode
                *.user
                *.suo
                *.nupkg
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C# .NET console/exe project generated by Aegis Project Builder.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run

                ```powershell
                dotnet run --project src/{safe_name}/{safe_name}.csproj -- --name Aegis --count 3
                ```

                ## Publish A Windows Executable

                ```powershell
                dotnet publish src/{safe_name}/{safe_name}.csproj -c Release -r win-x64 --self-contained false
                ```
                """
            ),
        }


    @staticmethod
    def _dotnet_wpf_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        safe_name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]+", project_name) if part) or "AegisDesktop"
        cs_title = title.replace("\\", "\\\\").replace('"', '\\"')
        xaml_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        return {
            f"src/{safe_name}/{safe_name}.csproj": _strip(
                """
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <OutputType>WinExe</OutputType>
                    <TargetFramework>net8.0-windows</TargetFramework>
                    <UseWPF>true</UseWPF>
                    <Nullable>enable</Nullable>
                    <ImplicitUsings>enable</ImplicitUsings>
                  </PropertyGroup>
                </Project>
                """
            ),
            f"src/{safe_name}/App.xaml": _strip(
                f"""
                <Application x:Class="{safe_name}.App"
                             xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                             xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
                             StartupUri="MainWindow.xaml">
                  <Application.Resources>
                    <SolidColorBrush x:Key="AppBackground" Color="#071018" />
                    <SolidColorBrush x:Key="PanelBackground" Color="#0C1620" />
                    <SolidColorBrush x:Key="AccentBrush" Color="#27DE7D" />
                    <SolidColorBrush x:Key="TextBrush" Color="#EDF7F3" />
                    <SolidColorBrush x:Key="MutedBrush" Color="#9AA8B6" />
                  </Application.Resources>
                </Application>
                """
            ),
            f"src/{safe_name}/App.xaml.cs": _strip(
                f"""
                using System.Windows;

                namespace {safe_name};

                public partial class App : Application
                {{
                }}
                """
            ),
            f"src/{safe_name}/DashboardState.cs": _strip(
                f"""
                namespace {safe_name};

                public sealed class DashboardState
                {{
                    private readonly List<string> _activity = new();

                    public DashboardState()
                    {{
                        _activity.Add("Project initialized");
                        _activity.Add("Validation ready");
                    }}

                    public int BuildCount {{ get; private set; }}
                    public IReadOnlyList<string> Activity => _activity;

                    public void RecordBuild(string label)
                    {{
                        if (string.IsNullOrWhiteSpace(label))
                        {{
                            throw new ArgumentException("label is required", nameof(label));
                        }}

                        BuildCount++;
                        _activity.Insert(0, $"{cs_title}: {{label.Trim()}} #{{BuildCount}}");
                    }}

                    public string Summary()
                    {{
                        return BuildCount == 0
                            ? "{cs_title} is ready."
                            : $"{cs_title} has recorded {{BuildCount}} build event(s).";
                    }}

                    public bool SelfCheck()
                    {{
                        RecordBuild("Smoke validation");
                        return BuildCount == 1 && Activity[0].Contains("Smoke validation", StringComparison.Ordinal);
                    }}
                }}
                """
            ),
            f"src/{safe_name}/MainWindow.xaml": _strip(
                f"""
                <Window x:Class="{safe_name}.MainWindow"
                        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
                        Title="{xaml_title}"
                        Width="980"
                        Height="640"
                        MinWidth="760"
                        MinHeight="480"
                        Background="{{StaticResource AppBackground}}">
                  <Grid Margin="28">
                    <Grid.RowDefinitions>
                      <RowDefinition Height="Auto" />
                      <RowDefinition Height="*" />
                      <RowDefinition Height="Auto" />
                    </Grid.RowDefinitions>

                    <StackPanel>
                      <TextBlock Text="Desktop workspace"
                                 Foreground="{{StaticResource AccentBrush}}"
                                 FontSize="13"
                                 FontWeight="SemiBold" />
                      <TextBlock Text="{xaml_title}"
                                 Foreground="{{StaticResource TextBrush}}"
                                 FontSize="34"
                                 FontWeight="Bold"
                                 Margin="0,8,0,4" />
                      <TextBlock Text="Native WPF shell with a testable state layer and package-free validation."
                                 Foreground="{{StaticResource MutedBrush}}"
                                 FontSize="15" />
                    </StackPanel>

                    <Border Grid.Row="1"
                            Margin="0,26,0,18"
                            Padding="20"
                            CornerRadius="8"
                            Background="{{StaticResource PanelBackground}}">
                      <Grid>
                        <Grid.ColumnDefinitions>
                          <ColumnDefinition Width="2*" />
                          <ColumnDefinition Width="*" />
                        </Grid.ColumnDefinitions>

                        <ListBox x:Name="ActivityList"
                                 Background="#071018"
                                 Foreground="{{StaticResource TextBrush}}"
                                 BorderBrush="#203040" />

                        <StackPanel Grid.Column="1" Margin="20,0,0,0">
                          <TextBlock Text="Status"
                                     Foreground="{{StaticResource AccentBrush}}"
                                     FontSize="16"
                                     FontWeight="SemiBold" />
                          <TextBlock x:Name="SummaryText"
                                     Foreground="{{StaticResource TextBrush}}"
                                     TextWrapping="Wrap"
                                     Margin="0,10,0,18" />
                          <Button Content="Record Build Event"
                                  Padding="12,8"
                                  Click="RecordBuild_Click" />
                        </StackPanel>
                      </Grid>
                    </Border>

                    <TextBlock Grid.Row="2"
                               Foreground="{{StaticResource MutedBrush}}"
                               Text="Generated by Aegis Project Builder." />
                  </Grid>
                </Window>
                """
            ),
            f"src/{safe_name}/MainWindow.xaml.cs": _strip(
                f"""
                using System.Windows;

                namespace {safe_name};

                public partial class MainWindow : Window
                {{
                    private readonly DashboardState _state = new();

                    public MainWindow()
                    {{
                        InitializeComponent();
                        Refresh();
                    }}

                    private void RecordBuild_Click(object sender, RoutedEventArgs e)
                    {{
                        _state.RecordBuild("Manual desktop action");
                        Refresh();
                    }}

                    private void Refresh()
                    {{
                        SummaryText.Text = _state.Summary();
                        ActivityList.ItemsSource = null;
                        ActivityList.ItemsSource = _state.Activity;
                    }}
                }}
                """
            ),
            f"tests/{safe_name}.Smoke/{safe_name}.Smoke.csproj": _strip(
                f"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <OutputType>Exe</OutputType>
                    <TargetFramework>net8.0-windows</TargetFramework>
                    <Nullable>enable</Nullable>
                    <ImplicitUsings>enable</ImplicitUsings>
                  </PropertyGroup>
                  <ItemGroup>
                    <ProjectReference Include="../../src/{safe_name}/{safe_name}.csproj" />
                  </ItemGroup>
                </Project>
                """
            ),
            f"tests/{safe_name}.Smoke/Program.cs": _strip(
                f"""
                using {safe_name};

                var state = new DashboardState();
                if (!state.SelfCheck())
                {{
                    Console.Error.WriteLine("DashboardState self-check failed.");
                    return 1;
                }}

                state.RecordBuild("Console smoke");
                if (state.BuildCount != 2 || !state.Summary().Contains("2 build event", StringComparison.Ordinal))
                {{
                    Console.Error.WriteLine("DashboardState summary failed.");
                    return 1;
                }}

                Console.WriteLine("WPF smoke passed.");
                return 0;
                """
            ),
            "build.py": _strip(
                f"""
                from __future__ import annotations

                import shutil
                import subprocess
                import sys
                from pathlib import Path


                ROOT = Path(__file__).resolve().parent
                APP_PROJECT = ROOT / "src" / "{safe_name}" / "{safe_name}.csproj"
                SMOKE_PROJECT = ROOT / "tests" / "{safe_name}.Smoke" / "{safe_name}.Smoke.csproj"


                def run(command: list[str]) -> int:
                    print("Running:", " ".join(command))
                    return subprocess.call(command, cwd=str(ROOT))


                def main() -> int:
                    if shutil.which("dotnet") is None:
                        print(".NET SDK was not found on PATH. Install .NET 8+ and rerun this script.", file=sys.stderr)
                        return 2

                    for project in (APP_PROJECT, SMOKE_PROJECT):
                        if not project.exists():
                            print(f"Project file not found: {{project}}", file=sys.stderr)
                            return 2

                    code = run(["dotnet", "restore", str(APP_PROJECT)])
                    if code != 0:
                        return code
                    code = run(["dotnet", "restore", str(SMOKE_PROJECT)])
                    if code != 0:
                        return code
                    code = run(["dotnet", "build", str(APP_PROJECT), "--configuration", "Release", "--no-restore"])
                    if code != 0:
                        return code
                    code = run(["dotnet", "build", str(SMOKE_PROJECT), "--configuration", "Release", "--no-restore"])
                    if code != 0:
                        return code
                    return run(["dotnet", "run", "--project", str(SMOKE_PROJECT), "--configuration", "Release", "--no-build"])


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            ),
            ".gitignore": _strip(
                """
                bin
                obj
                .vs
                .vscode
                *.user
                *.suo
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                C# WPF desktop app generated by Aegis Project Builder.

                ## Validate

                ```powershell
                python build.py
                ```

                ## Run

                ```powershell
                dotnet run --project src/{safe_name}/{safe_name}.csproj
                ```

                The validation script builds the GUI project, builds a separate smoke console, and runs the smoke console without opening the WPF window.
                """
            ),
        }


    @staticmethod
    def _tauri_react_template(project_name: str) -> dict[str, str]:
        title = _title_from_name(project_name)
        package_name = ProjectScaffolder._manifest_package_name(project_name)
        return {
            "package.json": _strip(
                f"""
                {{
                  "name": "{package_name}",
                  "version": "0.1.0",
                  "private": true,
                  "type": "module",
                  "scripts": {{
                    "dev": "tauri dev",
                    "build": "vite build && tauri build",
                    "web:dev": "vite",
                    "web:build": "vite build"
                  }},
                  "dependencies": {{
                    "@tauri-apps/api": "^2.2.0",
                    "@vitejs/plugin-react": "^4.3.4",
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0"
                  }},
                  "devDependencies": {{
                    "@tauri-apps/cli": "^2.2.0",
                    "@types/react": "^19.0.1",
                    "@types/react-dom": "^19.0.1",
                    "typescript": "^5.7.2",
                    "vite": "^6.0.3"
                  }}
                }}
                """
            ),
            "index.html": _strip(
                f"""
                <div id="root"></div>
                <script type="module" src="/src/main.tsx"></script>
                <title>{title}</title>
                """
            ),
            "src/main.tsx": _strip(
                """
                import React from 'react';
                import { createRoot } from 'react-dom/client';
                import { App } from './App';
                import './styles.css';

                createRoot(document.getElementById('root')!).render(
                  <React.StrictMode>
                    <App />
                  </React.StrictMode>
                );
                """
            ),
            "src/App.tsx": _strip(
                f"""
                import {{ invoke }} from '@tauri-apps/api/core';

                export function App() {{
                  async function greet() {{
                    const response = await invoke<string>('greet', {{ name: 'Aegis' }});
                    alert(response);
                  }}

                  return (
                    <main className="shell">
                      <p className="eyebrow">Tauri workspace</p>
                      <h1>{title}</h1>
                      <p>Lightweight desktop app with a Rust host and React UI.</p>
                      <button onClick={{greet}}>Ping Rust Host</button>
                    </main>
                  );
                }}
                """
            ),
            "src/styles.css": _strip(
                """
                :root { background: #071018; color: #edf7f3; font-family: Inter, system-ui, sans-serif; }
                body { margin: 0; }
                .shell { min-height: 100vh; display: grid; align-content: center; gap: 18px; padding: 48px; }
                .eyebrow { color: #27de7d; font-size: 12px; font-weight: 800; text-transform: uppercase; }
                h1 { font-size: 48px; margin: 0; }
                p { color: #9aa8b6; max-width: 620px; line-height: 1.7; }
                button { width: fit-content; border: 0; border-radius: 8px; padding: 12px 16px; background: #27de7d; color: #071018; font-weight: 800; }
                """
            ),
            "tsconfig.json": _strip(
                """
                {
                  "compilerOptions": {
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "jsx": "react-jsx",
                    "strict": true,
                    "skipLibCheck": true
                  },
                  "include": ["src"]
                }
                """
            ),
            "src-tauri/Cargo.toml": _strip(
                f"""
                [package]
                name = "{package_name}"
                version = "0.1.0"
                edition = "2021"

                [dependencies]
                tauri = {{ version = "2.2.0", features = [] }}
                tauri-build = "2.0.4"
                serde = {{ version = "1", features = ["derive"] }}
                serde_json = "1"

                [build-dependencies]
                tauri-build = "2.0.4"
                """
            ),
            "src-tauri/tauri.conf.json": _strip(
                f"""
                {{
                  "$schema": "https://schema.tauri.app/config/2",
                  "productName": "{title}",
                  "version": "0.1.0",
                  "identifier": "com.aegis.{project_name}",
                  "build": {{
                    "beforeDevCommand": "npm run web:dev",
                    "devUrl": "http://localhost:5173",
                    "beforeBuildCommand": "npm run web:build",
                    "frontendDist": "../dist"
                  }},
                  "app": {{
                    "windows": [{{ "title": "{title}", "width": 1200, "height": 780 }}]
                  }}
                }}
                """
            ),
            "src-tauri/build.rs": _strip(
                """
                fn main() {
                    tauri_build::build()
                }
                """
            ),
            "src-tauri/src/main.rs": _strip(
                """
                #[tauri::command]
                fn greet(name: &str) -> String {
                    format!("Aegis host ready for {name}")
                }

                fn main() {
                    tauri::Builder::default()
                        .invoke_handler(tauri::generate_handler![greet])
                        .run(tauri::generate_context!())
                        .expect("error while running tauri application");
                }
                """
            ),
            ".gitignore": _strip(
                """
                node_modules
                dist
                src-tauri/target
                .env
                """
            ),
            "README.md": _strip(
                f"""
                # {title}

                Tauri React TypeScript app generated by Aegis Project Builder.

                ```bash
                npm install
                npm run dev
                npm run build
                ```
                """
            ),
        }


def _strip(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _title_from_name(project_name: str) -> str:
    words = [part for part in re.split(r"[-_]+", project_name) if part]
    return " ".join(word[:1].upper() + word[1:] for word in words) or "Aegis App"
