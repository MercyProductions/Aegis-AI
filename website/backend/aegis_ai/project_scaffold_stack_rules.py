from __future__ import annotations

import re


def prompt_negates_web_stack(prompt: str) -> bool:
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


def preset_stack_locks(preset_id: str) -> set[str]:
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


def stack_locks_conflict_with_preset(stack_locks: list[str], preset_id: str) -> bool:
    requested = set(stack_locks)
    if not requested:
        return False

    preset_locks = preset_stack_locks(preset_id)
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

    requested_families = stack_families_from_locks(requested)
    preset_families = stack_families_from_locks(preset_locks)

    return bool(requested_families and preset_families and requested_families.isdisjoint(preset_families))


def prompt_allows_stack_switch(prompt: str, stack_locks: list[str]) -> bool:
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


def stack_family_for_preset(preset_id: str) -> str:
    locks = preset_stack_locks(preset_id)
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


def stack_lock_keywords_for_prompt(prompt: str) -> list[str]:
    lowered = f" {' '.join(prompt.lower().split())} "
    web_negated = prompt_negates_web_stack(prompt)
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


def stack_families_from_locks(locks: set[str]) -> set[str]:
    families: set[str] = set()
    if locks & {"stack-lock:native-cpp", "stack-lock:native-library", "stack-lock:windows-driver", "stack-lock:imgui-win32"}:
        families.add("native")
    if "stack-lock:desktop" in locks:
        families.add("desktop")
    if "stack-lock:solution-refactor" in locks:
        families.add("solution-refactor")
    if locks & {"stack-lock:web", "stack-lock:web-framework"}:
        families.add("web")
    if "stack-lock:python" in locks:
        families.add("python")
    if "stack-lock:rust" in locks:
        families.add("rust")
    if "stack-lock:go" in locks:
        families.add("go")
    if "stack-lock:dotnet" in locks:
        families.add("dotnet")
    return families
