from __future__ import annotations

import re
from typing import Callable


CleanPathFragment = Callable[[str], str]


def windows_path_fragments(message: str, clean_fragment: CleanPathFragment) -> list[str]:
    fragments: list[str] = []
    for match in re.finditer(r"[A-Za-z]:[\\/]", message):
        start = match.start()
        end = match.end()
        while end < len(message):
            if message[end] in "\r\n\"'`<>|*?":
                break
            end += 1
        candidate = clean_fragment(message[start:end])
        if candidate and candidate not in fragments:
            fragments.append(candidate)
    return fragments


def message_without_explicit_paths(message: str, clean_fragment: CleanPathFragment) -> str:
    cleaned = message
    for path_fragment in windows_path_fragments(message, clean_fragment):
        cleaned = cleaned.replace(path_fragment, " ", 1)
    cleaned = re.sub(
        r"\b(?:at\s+this\s+(?:path|location)|in\s+this\s+(?:folder|directory)|at\s+this\s+folder)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.split())


def request_needs_project_shape(message_without_paths: str, *, expects_file_changes: bool) -> bool:
    if not expects_file_changes:
        return False
    lower = message_without_paths.lower()
    product_terms = (
        "website",
        "web site",
        "web app",
        "app",
        "application",
        "project",
        "dashboard",
        "api",
        "service",
        "database",
        "migration",
        "schema",
        "kernel",
        "driver",
        "dll",
        "exe",
        "executable",
        "library",
        "desktop",
        "console app",
        "console project",
        "bot",
        "cli",
        "extension",
        "module",
        "package",
    )
    simple_single_file_terms = (
        "snippet",
        "single file",
        "one file",
        "script that",
        "code to",
        "print hello",
        "hello world script",
    )
    if any(term in lower for term in simple_single_file_terms) and not any(
        term in lower
        for term in (
            "project",
            "app",
            "application",
            "website",
            "web app",
            "service",
            "driver",
            "database",
            "sln",
            "solution",
        )
    ):
        return False
    return any(term in lower for term in product_terms)


def request_mentions_cpp_project(message_without_paths: str) -> bool:
    lower = message_without_paths.lower()
    return any(
        term in lower
        for term in (
            "c++",
            "cpp",
            "cmake",
            "native project",
            "native app",
            "native tool",
            "visual studio",
            "sln",
            "vcxproj",
            "exe",
            "executable",
            "win32",
            "windows app",
            "windows desktop",
            "gui app",
            "dll",
            "shared library",
            "dynamic library",
            "windows internals",
            "minhook",
            "imgui",
            "console app",
            "console project",
        )
    )


def request_mentions_extension_project(message_without_paths: str) -> bool:
    lower = message_without_paths.lower()
    return any(
        term in lower
        for term in (
            "browser extension",
            "chrome extension",
            "edge extension",
            "manifest v3",
            " mv3",
            "vscode extension",
            "vs code extension",
            "visual studio code extension",
        )
    )


def request_mentions_python_app_project(message_without_paths: str) -> bool:
    lower = message_without_paths.lower()
    if "python" not in lower:
        return False
    if any(term in lower for term in ("api", "backend", "service", "fastapi", "flask")):
        return False
    return any(
        term in lower
        for term in (
            "cli",
            "command line",
            "command-line",
            "app",
            "application",
            "program",
            "tool",
            "script",
        )
    )


def request_mentions_web_project(message_without_paths: str, *, web_stack_negated: bool) -> bool:
    if web_stack_negated:
        return False
    lower = message_without_paths.lower()
    return any(
        term in lower
        for term in (
            "website",
            "web site",
            "web app",
            "landing",
            "frontend",
            "next",
            "react",
            "vite",
            "dashboard",
        )
    )


def request_mentions_desktop_project(message_without_paths: str) -> bool:
    lower = message_without_paths.lower()
    return any(
        term in lower
        for term in (
            "desktop app",
            "desktop application",
            "desktop tool",
            "desktop gui",
            "gui app",
            "gui tool",
            "windows app",
            "windows desktop",
            "native gui",
            "electron",
            "tauri",
            "wpf",
            "winforms",
            "qt app",
            "qt gui",
            "imgui",
            "dear imgui",
        )
    )


def request_mentions_specific_web_framework(message_without_paths: str) -> bool:
    lower = message_without_paths.lower()
    return any(
        term in lower
        for term in (
            "next",
            "next.js",
            "react",
            "vite",
            "vue",
            "nuxt",
            "svelte",
            "sveltekit",
            "astro",
            "remix",
            "angular",
            "electron",
            "tauri",
        )
    )
