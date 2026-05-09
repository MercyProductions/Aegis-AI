from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .prompt_intent import prompt_has_explanation_prefix, prompt_requests_execution_validation
from .schemas import WorkspaceDependencyProfile, WorkspaceProjectManifest


POWERSHELL_BUILD_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"


def should_validate_existing_project_only(
    prompt: str,
    target: Path,
    *,
    run_validation: bool,
    profile: WorkspaceDependencyProfile,
) -> bool:
    if not target.exists() or not target.is_dir():
        return False
    if not run_validation:
        return False
    if not prompt_is_existing_project_validation_intent(prompt):
        return False
    if (target / ".aegis" / "project.json").exists():
        return True
    if profile.config_files or profile.build_systems or profile.validation_commands:
        return True
    return False


def prompt_is_existing_project_validation_intent(prompt: str) -> bool:
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


def existing_project_validation_command(
    target: Path,
    profile: WorkspaceDependencyProfile,
    preferred_command: str,
) -> str:
    command = preferred_command.strip()
    if command == "python build.py" and not (target / "build.py").exists():
        command = ""
    if _is_root_powershell_build_command(command) and not (target / "build.ps1").exists():
        command = ""
    if "cmake --build build" in command.lower() and not (target / "build").exists():
        return "cmake -S . -B build && cmake --build build --config Release"
    if command:
        return command
    if (target / "build.py").exists():
        return "python build.py"
    if (target / "build.ps1").exists():
        return POWERSHELL_BUILD_COMMAND
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


def _is_root_powershell_build_command(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    if not normalized.startswith(("powershell ", "pwsh ")):
        return False
    return any(
        marker in f" {normalized} "
        for marker in (" -file ./build.ps1 ", " -file .\\build.ps1 ", " -file build.ps1 ")
    )


def continuity_preset_id(
    *,
    prompt: str,
    target: Path,
    manifest: WorkspaceProjectManifest | None,
    profile: WorkspaceDependencyProfile,
    known_preset_ids: Iterable[str],
) -> str:
    known_presets = {preset_id.strip() for preset_id in known_preset_ids if preset_id.strip()}
    if not target.exists() or not prompt_should_reuse_existing_project(prompt):
        return ""

    if manifest is not None and manifest.preset_id in known_presets:
        return manifest.preset_id
    if manifest is not None:
        contract_preset_id = str(manifest.mission_contract.get("preset_id", "")).strip()
        if contract_preset_id in known_presets:
            return contract_preset_id

    config_files = {item.lower().replace("\\", "/") for item in profile.config_files}
    build_systems = {item.lower() for item in profile.build_systems}
    frameworks = {item.lower() for item in profile.frameworks}

    has_powershell_module_source = any(
        path.exists()
        for path in (
            *target.glob("*.psm1"),
            *target.glob("*.psd1"),
            *target.glob("src/*.psm1"),
            *target.glob("src/*.psd1"),
        )
    )
    if has_powershell_module_source and (target / "build.ps1").exists() and "powershell-module" in known_presets:
        return "powershell-module"

    if "dll/shared library" in frameworks or any(
        item.endswith((".dll", ".lib", ".def", ".exp")) for item in config_files
    ):
        return "cpp-cmake-dll"

    if any(item.endswith(".sln") or item.endswith(".vcxproj") for item in config_files):
        return "cpp-msvc-console-sln"

    if "cmakelists.txt" in config_files or "cmake" in build_systems:
        if any("imgui" in item for item in config_files) or (
            target / "vendor" / "imgui_shim"
        ).exists():
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


def prompt_should_reuse_existing_project(prompt: str) -> bool:
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


def should_update_existing_scaffold(prompt: str, target: Path) -> bool:
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
        readme_text = (
            readme.read_text(encoding="utf-8", errors="replace").lower()[:16_000]
            if readme.exists()
            else ""
        )
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


def prompt_requests_validation(prompt: str) -> bool:
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
