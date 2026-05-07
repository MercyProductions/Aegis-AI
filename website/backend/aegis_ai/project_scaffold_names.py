from __future__ import annotations

import re


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
PROMPT_NAME_STOP_WORDS = {
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


def has_explicit_project_name(prompt: str) -> bool:
    return re.search(r"\b(?:named|called|titled)\s+", prompt, re.IGNORECASE) is not None


def project_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", (value or "").strip()).strip("-_").lower()
    return cleaned or "aegis-app"


def preset_default_project_name_if_needed(preset_id: str, raw_name: str) -> str:
    default_name = PRESET_DEFAULT_PROJECT_NAMES.get(preset_id, "")
    if not default_name:
        return raw_name

    slug = project_name(raw_name)
    if slug in GENERIC_TARGET_NAMES or slug == "aegis-app":
        return default_name
    if looks_like_instructional_project_name(slug):
        return default_name
    return raw_name


def looks_like_instructional_project_name(slug: str) -> bool:
    tokens = [token for token in slug.split("-") if token]
    if not tokens:
        return True
    if tokens[0] in {"app", "project", "tool"}:
        return True
    return any(token in INSTRUCTIONAL_PROJECT_NAME_TOKENS for token in tokens[:3])


def should_use_target_leaf_project_name(preset_id: str, target_leaf: str) -> bool:
    return preset_id in TARGET_NAMED_WEB_PRESETS and target_leaf_is_specific(target_leaf)


def target_leaf_is_specific(target_leaf: str) -> bool:
    slug = project_name(target_leaf)
    return slug not in GENERIC_TARGET_NAMES


def project_name_from_prompt(prompt: str) -> str:
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

    tokens = re.findall(r"[A-Za-z0-9]+", lowered)
    useful = [token for token in tokens if token not in PROMPT_NAME_STOP_WORDS and len(token) > 1]
    return "-".join(useful[:4]) if useful else "aegis-app"
