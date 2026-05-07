from __future__ import annotations

from pathlib import Path

from .agent_runtime import AgentDraft
from .schemas import FileChange


def harden_native_cpp_draft(
    draft: AgentDraft,
    *,
    request_mentions_cpp_project: bool,
    workspace_root: Path,
    change_paths: set[str],
) -> AgentDraft:
    existing_build_py = (workspace_root / "build.py").exists()
    has_cpp_entry = any(path.endswith((".cpp", ".cxx", ".cc", ".hpp", ".h")) for path in change_paths) or _workspace_has_any(
        workspace_root,
        ("src/main.cpp", "main.cpp"),
    )
    has_cmake = "cmakelists.txt" in change_paths or (workspace_root / "CMakeLists.txt").exists()
    cpp_request = request_mentions_cpp_project or has_cpp_entry or has_cmake

    if not cpp_request or not has_cmake or not has_cpp_entry:
        return draft

    removed_shell_scripts = drop_shell_only_cpp_validation_changes(draft)
    if "build.py" in change_paths or existing_build_py:
        prefer_python_build_command(draft)
        if removed_shell_scripts:
            draft.warnings.append(
                "Aegis removed shell-only C++ validation scripts and kept `python build.py` as the portable validator."
            )
        return draft

    draft.changes.append(
        FileChange(
            action="create",
            path="build.py",
            summary="Add a Windows-friendly one-command CMake build validator.",
            content=cmake_build_py_content(),
        )
    )
    prefer_python_build_command(draft)
    message = "Aegis added build.py so C++ CMake projects validate with `python build.py` instead of a shell-only script."
    if removed_shell_scripts:
        message += f" Removed shell-only validation file(s): {', '.join(removed_shell_scripts)}."
    draft.warnings.append(message)
    return draft


def drop_shell_only_cpp_validation_changes(draft: AgentDraft) -> list[str]:
    kept: list[FileChange] = []
    removed: list[str] = []
    for change in draft.changes:
        path = change.path.replace("\\", "/").lower()
        summary = change.summary.lower()
        content = (change.content or "").lower()
        search_text = f"{path} {summary} {content[:800]}"
        looks_like_build_script = any(term in search_text for term in ("cmake", "build", "validate"))
        if change.action in {"create", "update"} and path.endswith(".sh") and looks_like_build_script:
            removed.append(change.path)
            continue
        kept.append(change)
    draft.changes = kept
    return removed


def prefer_python_build_command(draft: AgentDraft) -> None:
    rewritten: list[dict[str, str]] = []
    saw_build_py = False
    for command in draft.proposed_commands:
        raw = str(command.get("command") or "").strip()
        reason = str(command.get("reason") or "").strip()
        lowered = raw.lower()
        if raw == "python build.py":
            saw_build_py = True
            rewritten.append(command)
            continue
        if "cmake" in lowered and any(operator in lowered for operator in ("&&", "||", ";")):
            if not saw_build_py:
                rewritten.append(
                    {
                        "command": "python build.py",
                        "reason": reason or "Configure and build the C++ project with the portable validator.",
                    }
                )
                saw_build_py = True
            continue
        if ".sh" in lowered or lowered.startswith("bash ") or lowered.startswith("sh "):
            if not saw_build_py:
                rewritten.append(
                    {
                        "command": "python build.py",
                        "reason": reason or "Build and validate the C++ project with the cross-platform validator.",
                    }
                )
                saw_build_py = True
            continue
        rewritten.append(command)

    if not saw_build_py:
        rewritten.append(
            {
                "command": "python build.py",
                "reason": "Configure and build the C++ project with CMake.",
            }
        )
    draft.proposed_commands = rewritten


def cmake_build_py_content() -> str:
    return """from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    print(f"> {' '.join(command)}")
    return subprocess.run(command, cwd=ROOT, text=True, check=True, **kwargs)


def target_names() -> list[str]:
    cmake = ROOT / "CMakeLists.txt"
    if not cmake.exists():
        return []
    text = cmake.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    for match in re.finditer(r"add_executable\\s*\\(\\s*([^\\s\\)]+)", text, flags=re.IGNORECASE):
        name = match.group(1).strip().strip('"')
        if name and name not in names:
            names.append(name)
    return names


def executable_candidates() -> list[Path]:
    names = target_names()
    wanted = {name for name in names}
    wanted.update(f"{name}.exe" for name in names)
    candidates: list[Path] = []

    if wanted:
        for path in BUILD_DIR.rglob("*"):
            if path.is_file() and path.name in wanted and "CMakeFiles" not in path.parts:
                candidates.append(path)

    if candidates:
        return sorted(candidates, key=lambda path: (preferred_folder_rank(path), str(path)))

    suffixes = {".exe"} if os.name == "nt" else {""}
    for path in BUILD_DIR.rglob("*"):
        if not path.is_file() or "CMakeFiles" in path.parts:
            continue
        if os.name == "nt":
            if path.suffix.lower() == ".exe":
                candidates.append(path)
        elif os.access(path, os.X_OK) and path.suffix in suffixes:
            candidates.append(path)
    return sorted(candidates, key=lambda path: (preferred_folder_rank(path), str(path)))


def preferred_folder_rank(path: Path) -> int:
    lowered = [part.lower() for part in path.parts]
    if "release" in lowered:
        return 0
    if "relwithdebinfo" in lowered:
        return 1
    if "debug" in lowered:
        return 2
    return 3


def smoke_run_executable() -> int:
    executable = next(iter(executable_candidates()), None)
    if executable is None:
        print("Build completed, but no runnable executable was found under build/.", file=sys.stderr)
        return 3

    command = [str(executable), "--aegis-validate"]
    print(f"> {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        input="\\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.returncode != 0:
        print(f"Smoke run failed with exit code {completed.returncode}.", file=sys.stderr)
        return completed.returncode
    if not completed.stdout.strip():
        print("Smoke run completed but produced no console output.", file=sys.stderr)
        return 4
    print("Build and smoke run passed.")
    return 0


def main() -> int:
    if shutil.which("cmake") is None:
        print("CMake is required to build this project.", file=sys.stderr)
        return 2

    run(["cmake", "-S", ".", "-B", "build"])
    run(["cmake", "--build", "build", "--config", "Release"])
    return smoke_run_executable()


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _workspace_has_any(workspace_root: Path, relative_paths: tuple[str, ...]) -> bool:
    return any((workspace_root / relative_path).exists() for relative_path in relative_paths)
