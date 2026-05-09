from __future__ import annotations

import re

from ..schemas import WorkspaceFile, WorkspaceProjectManifest
from .contracts import AgentDraft


DOTNET_PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
DOTNET_SOURCE_SUFFIXES = (".cs", ".fs", ".fsi", ".fsx", ".vb", ".xaml")
DOTNET_SUFFIXES = DOTNET_PROJECT_SUFFIXES + DOTNET_SOURCE_SUFFIXES
VISUAL_STUDIO_SOLUTION_SUFFIXES = (".sln", ".slnx")
VISUAL_STUDIO_NATIVE_BUILD_SUFFIXES = VISUAL_STUDIO_SOLUTION_SUFFIXES + (".vcxproj", ".vcxproj.filters")


def draft_change_paths(draft: AgentDraft) -> set[str]:
    return {change.path.replace("\\", "/").lower().strip("/") for change in draft.changes}


def draft_change_payload_size(draft: AgentDraft) -> int:
    return sum(len(change.content or "") for change in draft.changes if change.action in {"create", "update"})


def draft_has_concrete_source_surface(draft: AgentDraft) -> bool:
    source_suffixes = (
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".asm",
        ".rc",
        *DOTNET_SOURCE_SUFFIXES,
        ".py",
        ".rs",
        ".go",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".html",
        ".css",
        ".sql",
        ".ps1",
        ".psm1",
        ".bat",
        ".cmd",
    )
    source_prefixes = (
        "src/",
        "app/",
        "pages/",
        "components/",
        "public/",
        "tests/",
        "test/",
        "driver/",
        "controller/",
        "host/",
        "library/",
        "cmd/",
        "internal/",
        "pkg/",
    )
    ignored_exact = {
        "readme.md",
        "license",
        "changelog.md",
        "patch_notes.md",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "package.json",
        "tsconfig.json",
        "pyproject.toml",
        "requirements.txt",
        "cargo.toml",
        "go.mod",
        "cmakelists.txt",
        "build.py",
        "build.ps1",
    }
    for change in draft.changes:
        if change.action not in {"create", "update"}:
            continue
        path = change.path.replace("\\", "/").lower().strip("/")
        if not path or path in ignored_exact or path.startswith(".aegis/"):
            continue
        if path.endswith(source_suffixes) or path.startswith(source_prefixes):
            return True
    return False


def manifest_contract_value(manifest: WorkspaceProjectManifest, key: str) -> str:
    value = manifest.mission_contract.get(key) if isinstance(manifest.mission_contract, dict) else ""
    return str(value or "").strip()


def manifest_stack_family(manifest: WorkspaceProjectManifest | None) -> str:
    if manifest is None:
        return ""
    preset_id = manifest_contract_value(manifest, "preset_id") or manifest.preset_id
    stack_family = manifest_contract_value(manifest, "stack_family")
    normalized_stack_family = stack_family.lower().strip()
    if normalized_stack_family in {"desktop", "desktop-app", "desktop_app"}:
        return "desktop"
    if preset_id in {
        "electron-react-ts",
        "tauri-react-ts",
        "python-tkinter-desktop",
        "dotnet-wpf-csharp",
        "cpp-imgui-win32-dx11",
    }:
        return "desktop"
    text = " ".join(
        str(item or "")
        for item in (
            stack_family,
            preset_id,
            manifest.preset_label,
            manifest.framework,
            manifest.language,
            " ".join(manifest.tags),
        )
    ).lower()
    manifest_tags = {tag.lower().strip() for tag in manifest.tags if tag.strip()}
    if "desktop" in manifest_tags and any(
        term in text
        for term in ("electron", "tauri", "tkinter", "wpf", "winforms", "xaml", "imgui", "desktop")
    ):
        return "desktop"
    if any(term in text for term in ("cpp", "c++", "cmake", "visual studio", "win32", "windows-internals", "kernel-driver")):
        return "native-cpp"
    if any(term in text for term in ("dotnet", ".net", "c#", "csharp", "f#", "fsharp", "vb.net", "visual basic", "wpf", "winforms")):
        return "dotnet"
    if "python" in text:
        return "python"
    if "rust" in text or "cargo" in text:
        return "rust"
    if re.search(r"\bgo\b", text) or "golang" in text:
        return "go"
    if any(term in text for term in ("next", "react", "vite", "web", "website", "frontend", "electron", "tauri", "expo")):
        return "web"
    return ""


def draft_stack_families(draft: AgentDraft) -> set[str]:
    paths = draft_change_paths(draft)
    families: set[str] = set()
    web_config = {
        "package.json",
        "index.html",
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
        "vite.config.js",
        "vite.config.ts",
        "vite.config.mjs",
        "tailwind.config.js",
        "tailwind.config.ts",
    }
    if any(path in web_config for path in paths) or any(
        path.startswith(("app/", "pages/", "components/", "public/"))
        or path.endswith((".tsx", ".jsx", ".html", ".css"))
        for path in paths
    ):
        families.add("web")
    if any(path.endswith((".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".asm", ".rc")) for path in paths) or any(
        path == "cmakelists.txt" or path.endswith(VISUAL_STUDIO_NATIVE_BUILD_SUFFIXES)
        for path in paths
    ):
        families.add("native-cpp")
    if any(
        (path.endswith(".py") and path != "build.py")
        or path in {"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"}
        for path in paths
    ):
        families.add("python")
    if any(path.endswith(DOTNET_SUFFIXES) or path.endswith(VISUAL_STUDIO_SOLUTION_SUFFIXES) for path in paths):
        families.add("dotnet")
    if any(path == "cargo.toml" or path.endswith(".rs") for path in paths):
        families.add("rust")
    if any(path == "go.mod" or path.endswith(".go") for path in paths):
        families.add("go")
    if draft_has_desktop_host_surface(draft):
        families.add("desktop")
    return families


def workspace_stack_family(files: list[WorkspaceFile]) -> str:
    paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
    if not paths:
        return ""

    has_electron_host = any(
        path in {"electron.vite.config.ts", "electron.vite.config.js"}
        or path.startswith(("src/main/", "src/preload/"))
        for path in paths
    )
    has_tauri_host = any(path.startswith("src-tauri/") for path in paths)
    has_wpf_host = any(path.endswith("mainwindow.xaml") or path.endswith(DOTNET_PROJECT_SUFFIXES) for path in paths) and any(
        path.endswith(".xaml")
        for path in paths
    )
    if has_electron_host or has_tauri_host or has_wpf_host:
        return "desktop"

    has_native = any(path.endswith(VISUAL_STUDIO_NATIVE_BUILD_SUFFIXES) for path in paths) or any(
        path in {"cmakelists.txt", "cmakepresets.json", "makefile"}
        for path in paths
    ) or any(path.endswith((".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".asm", ".rc", ".inf")) for path in paths)
    has_dotnet = any(path.endswith(DOTNET_SUFFIXES) for path in paths)
    has_python = any(path in {"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"} for path in paths) or any(
        path.endswith(".py") and path != "build.py"
        for path in paths
    )

    if has_native:
        return "native-cpp"
    if has_dotnet:
        return "dotnet"
    if has_python:
        return "python"
    if any(path == "cargo.toml" or path.endswith(".rs") for path in paths):
        return "rust"
    if any(path == "go.mod" or path.endswith(".go") for path in paths):
        return "go"
    if any(path in {"package.json", "index.html"} or path.endswith((".tsx", ".jsx", ".html", ".css")) for path in paths):
        return "web"
    return ""


def stack_family_label(family: str) -> str:
    return {
        "native-cpp": "native C++/CMake/Visual Studio",
        "dotnet": ".NET",
        "python": "Python",
        "rust": "Rust",
        "go": "Go",
        "web": "web/frontend",
        "desktop": "desktop application",
    }.get(family, family)


def important_project_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower().strip("/")
    if not normalized:
        return False
    if normalized.startswith(".aegis/"):
        return True

    important_exact = {
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "agents.md",
        "readme.md",
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "vite.config.js",
        "vite.config.ts",
        "vite.config.mjs",
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "tailwind.config.js",
        "tailwind.config.ts",
        "postcss.config.js",
        "postcss.config.mjs",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "cargo.toml",
        "go.mod",
        "cmakelists.txt",
        "cmakepresets.json",
        "makefile",
        "build.py",
    }
    if normalized in important_exact:
        return True

    important_roots = (
        "src/",
        "app/",
        "pages/",
        "components/",
        "public/",
        "tests/",
        "test/",
        "driver/",
        "controller/",
        "host/",
        "library/",
        "include/",
        "cmd/",
        "internal/",
        "pkg/",
    )
    if normalized.startswith(important_roots):
        return True

    important_suffixes = (
        *VISUAL_STUDIO_NATIVE_BUILD_SUFFIXES,
        *DOTNET_PROJECT_SUFFIXES,
        ".props",
        ".targets",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        *DOTNET_SOURCE_SUFFIXES,
        ".py",
        ".rs",
        ".go",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".html",
        ".css",
        ".sql",
        ".ps1",
        ".psm1",
        ".bat",
        ".cmd",
    )
    return normalized.endswith(important_suffixes)


def looks_like_next_workspace(files: list[WorkspaceFile]) -> bool:
    paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
    return (
        "next.config.js" in paths
        or "next.config.mjs" in paths
        or "next.config.ts" in paths
        or any(path.startswith("app/") for path in paths)
    ) and ("package.json" in paths or "tsconfig.json" in paths)


def draft_has_desktop_host_surface(draft: AgentDraft) -> bool:
    paths = draft_change_paths(draft)
    if not paths:
        return False

    if any(
        path in {"electron.vite.config.ts", "electron.vite.config.js"}
        or path.startswith(("src/main/", "src/preload/"))
        for path in paths
    ):
        return True
    if any(path.startswith("src-tauri/") for path in paths):
        return True
    if any(path.endswith("mainwindow.xaml") or path.endswith(DOTNET_PROJECT_SUFFIXES) for path in paths) and any(
        path.endswith(".xaml") for path in paths
    ):
        return True

    text = "\n".join(
        (change.content or "").lower()
        for change in draft.changes
        if change.action in {"create", "update"}
    )
    if any(token in text for token in ("import tkinter", "from tkinter", "pyside6", "pyqt6", "pyqt5")):
        return True
    if any(token in text for token in ("imgui::", "dear imgui", "winmain", "createwindow", "directx", "dx11")):
        return True

    return False
