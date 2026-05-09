# backend/commands.py
from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .approval_sandbox import SandboxProfileManager
from .settings import Settings


DANGEROUS_COMMAND_PARTS = {
    " del ",
    " erase ",
    " format ",
    " rd ",
    " rmdir ",
    " remove-item",
    " shutdown",
    " stop-computer",
    " reset-computer",
    " set-executionpolicy",
    " git reset",
    " git clean",
}

SHELL_METACHARS = {
    "|",
    "||",
    "&",
    "&&",
    ";",
    ">>",
    ">",
    "<<",
    "<",
}

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SHELL_OPERATOR_SCAN_ORDER = ("&&", "||", ">>", "<<", "|", "&", ";", ">", "<")


@dataclass(frozen=True)
class CommandResult:
    command: str
    cwd: str
    allowed: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    reason: str
    steps: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.allowed and not self.timed_out and self.exit_code == 0


class CommandRunner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sandbox_profiles = SandboxProfileManager()
        self.allowed_commands = {
            item.strip().lower()
            for item in settings.aegis_command_allowlist.split(",")
            if item.strip()
        }

    def run(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int | None = None,
        sandbox_profile: str | None = None,
    ) -> CommandResult:
        stripped = command.strip()
        normalized = f" {stripped.lower()} "
        profile_name = sandbox_profile or self.settings.sandbox_profile

        try:
            profile = self.sandbox_profiles.get_profile(profile_name)
        except ValueError as exc:
            return self._blocked(command, cwd, str(exc))

        if not stripped:
            return self._blocked(command, cwd, "Empty command.")

        if any(part in normalized for part in DANGEROUS_COMMAND_PARTS):
            return self._blocked(command, cwd, "Command matched the destructive-command denylist.")

        tokenized = self._space_unquoted_shell_metacharacters(stripped)
        try:
            argv = shlex.split(tokenized, posix=True)
        except ValueError as exc:
            return self._blocked(command, cwd, f"Command could not be parsed safely: {exc}")

        if not argv:
            return self._blocked(command, cwd, "Empty command.")

        if self._contains_shell_metacharacters(argv):
            if self._is_safe_and_chain(argv):
                return self._run_and_chain(
                    command=command,
                    cwd=cwd,
                    argv=argv,
                    timeout_seconds=timeout_seconds,
                    sandbox_profile=profile.name,
                    output_limit=profile.max_output_size,
                )
            return self._blocked(command, cwd, "Shell operators and command chaining are not allowed.")

        first = self._normalize_executable(argv[0])
        if not first:
            return self._blocked(command, cwd, "Empty command.")

        if first in {"powershell", "pwsh"} and not self._is_safe_powershell_build_guard(argv):
            return self._blocked(
                command,
                cwd,
                "PowerShell commands are limited to the exact root build.ps1 validation guard.",
            )

        if profile.max_execution_time <= 0:
            return self._blocked(command, cwd, f"Sandbox profile '{profile.name}' does not allow command execution.")

        if not self.sandbox_profiles.is_command_allowed(executable=first, command=stripped, profile_name=profile.name):
            return self._blocked(command, cwd, f"Sandbox profile '{profile.name}' blocked this command.")

        if first not in self.allowed_commands:
            return self._blocked(command, cwd, f"Command '{first}' is not in the allowlist.")

        effective_timeout = timeout_seconds or self.settings.aegis_command_timeout_seconds
        effective_timeout = min(effective_timeout, profile.max_execution_time)
        run_argv = [self._resolve_executable_path(argv[0]), *argv[1:]]
        run_argv = self._windows_native_cmake_argv_with_short_build_dir(run_argv, first, cwd)

        execution_command: str | list[str] = run_argv
        execution_env: dict[str, str] | None = None
        windows_native_wrapper = self._windows_native_toolchain_command_line(run_argv, first, cwd)
        if windows_native_wrapper:
            execution_command = windows_native_wrapper
            execution_env = self._windows_native_wrapper_env()

        try:
            completed = subprocess.run(
                execution_command,
                cwd=str(cwd),
                env=execution_env,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                cwd=str(cwd),
                allowed=True,
                exit_code=None,
                stdout=self._trim_output(exc.stdout or "", limit=profile.max_output_size),
                stderr=self._trim_output(exc.stderr or "", limit=profile.max_output_size),
                timed_out=True,
                reason="Command timed out.",
            )
        except OSError as exc:
            return CommandResult(
                command=command,
                cwd=str(cwd),
                allowed=True,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                reason="Command could not start.",
            )

        return CommandResult(
            command=command,
            cwd=str(cwd),
            allowed=True,
            exit_code=completed.returncode,
            stdout=self._trim_output(completed.stdout, limit=profile.max_output_size),
            stderr=self._trim_output(completed.stderr, limit=profile.max_output_size),
            timed_out=False,
            reason="Command finished.",
        )

    def _blocked(self, command: str, cwd: Path, reason: str) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=str(cwd),
            allowed=False,
            exit_code=None,
            stdout="",
            stderr="",
            timed_out=False,
            reason=reason,
        )

    def _first_token(self, command: str) -> str:
        stripped = command.strip()
        if not stripped:
            return ""
        try:
            argv = shlex.split(stripped, posix=True)
        except ValueError:
            return ""
        if not argv:
            return ""
        return self._normalize_executable(argv[0])

    def _normalize_executable(self, value: str) -> str:
        first = value.strip("\"'").replace("\\", "/").lower()
        first = first.rsplit("/", 1)[-1]
        if first.startswith(".") and not first.startswith("..") and len(first) > 1:
            first = first[1:]
        for suffix in (".exe", ".cmd", ".bat", ".ps1"):
            if first.endswith(suffix):
                first = first[: -len(suffix)]
        return first

    def _is_safe_powershell_build_guard(self, argv: list[str]) -> bool:
        if len(argv) != 6:
            return False
        args = [item.strip("\"'").lower() for item in argv[1:]]
        script = args[4].replace("\\", "/").rstrip("/")
        return args[:4] == ["-noprofile", "-executionpolicy", "bypass", "-file"] and script in {
            "./build.ps1",
            "build.ps1",
        }

    def _resolve_executable_path(self, value: str) -> str:
        resolved = shutil.which(value)
        return resolved or value

    def _windows_native_toolchain_command_line(self, run_argv: list[str], first: str, cwd: Path) -> str:
        if os.name != "nt":
            return ""
        if not self._needs_windows_native_toolchain(first, run_argv, cwd):
            return ""
        if self._native_toolchain_available(first):
            return ""

        vsdevcmd = self._find_vsdevcmd()
        if vsdevcmd is None:
            return ""

        user_command = subprocess.list2cmdline(run_argv)
        generator_env = self._windows_cmake_generator_environment(vsdevcmd)
        return f'cmd.exe /d /c call "{vsdevcmd}" -arch=x64 -host_arch=x64 >nul && {generator_env}{user_command}'

    def _windows_native_wrapper_env(self) -> dict[str, str]:
        env = os.environ.copy()
        path_value = env.get("PATH") or env.get("Path") or ""
        if path_value:
            safe_parts = [
                item
                for item in path_value.split(os.pathsep)
                if item and not any(marker in item for marker in ("&", "|", "<", ">"))
            ]
            env["PATH"] = os.pathsep.join(safe_parts)
            env["Path"] = env["PATH"]
        return env

    def _needs_windows_native_toolchain(self, first: str, run_argv: list[str], cwd: Path) -> bool:
        has_native_project = (
            (cwd / "CMakeLists.txt").exists()
            or any(cwd.glob("*.sln"))
            or any(cwd.glob("*.vcxproj"))
        )
        if not has_native_project:
            return False

        if first in {"cmake", "ctest", "msbuild", "ninja"}:
            return True

        if first in {"python", "py"}:
            return any(Path(arg.strip("\"'")).name.lower() == "build.py" for arg in run_argv[1:])

        return False

    def _windows_native_cmake_argv_with_short_build_dir(self, run_argv: list[str], first: str, cwd: Path) -> list[str]:
        if os.name != "nt" or first not in {"cmake", "ctest"}:
            return run_argv
        if not (cwd / "CMakeLists.txt").exists():
            return run_argv

        short_build_dir = str(self._windows_native_cmake_build_dir(cwd))
        rewritten = list(run_argv)

        for index, arg in enumerate(rewritten):
            lower = arg.lower()
            if lower in {"-b", "--build", "--test-dir"} and index + 1 < len(rewritten):
                if self._is_default_cmake_build_dir(rewritten[index + 1]):
                    rewritten[index + 1] = short_build_dir
            elif lower.startswith("-b") and len(arg) > 2 and self._is_default_cmake_build_dir(arg[2:]):
                rewritten[index] = "-B" + short_build_dir

        return rewritten

    def _is_default_cmake_build_dir(self, value: str) -> bool:
        normalized = value.strip("\"'").replace("\\", "/").rstrip("/").lower()
        return normalized in {"build", "./build", ".build"}

    def _windows_native_cmake_build_dir(self, cwd: Path) -> Path:
        digest = hashlib.sha1(str(cwd.resolve()).encode("utf-8")).hexdigest()[:12]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", cwd.name).strip(".-") or "project"
        return Path(tempfile.gettempdir()) / "aegis-cmake-validation" / f"{safe_name}-{digest}"

    def _native_toolchain_available(self, first: str) -> bool:
        if first == "msbuild":
            return shutil.which("msbuild.exe") is not None or shutil.which("msbuild") is not None
        if first in {"cmake", "ctest", "ninja", "python", "py"}:
            return any(
                shutil.which(tool) is not None
                for tool in ("cl.exe", "cl", "g++.exe", "g++", "clang++.exe", "clang++", "gcc.exe", "gcc")
            )
        return True

    def _find_vsdevcmd(self) -> Path | None:
        candidates: list[Path] = []
        program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
        for root_value in program_files:
            if not root_value:
                continue
            root = Path(root_value) / "Microsoft Visual Studio"
            for version in ("2022", "17", "2019", "18"):
                for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                    candidates.append(root / version / edition / "Common7" / "Tools" / "VsDevCmd.bat")

        for candidate in candidates:
            if candidate.exists():
                return candidate

        vswhere_root = os.environ.get("ProgramFiles(x86)")
        if not vswhere_root:
            return None
        vswhere = Path(vswhere_root) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if not vswhere.exists():
            return None

        try:
            completed = subprocess.run(
                [
                    str(vswhere),
                    "-latest",
                    "-products",
                    "*",
                    "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-find",
                    r"Common7\Tools\VsDevCmd.bat",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
                check=False,
            )
        except OSError:
            return None

        for line in completed.stdout.splitlines():
            candidate = Path(line.strip())
            if candidate.exists():
                return candidate
        return None

    def _windows_cmake_generator_environment(self, vsdevcmd: Path) -> str:
        normalized_parts = {part.lower() for part in vsdevcmd.parts}
        if "2022" not in normalized_parts and "17" not in normalized_parts:
            return ""
        ninja = self._find_vs_ninja(vsdevcmd)
        if ninja is not None:
            return (
                'set "CMAKE_GENERATOR=Ninja" && '
                f'set "CMAKE_MAKE_PROGRAM={ninja}" && '
                'set "CMAKE_GENERATOR_PLATFORM=" && '
            )
        return 'set "CMAKE_GENERATOR=NMake Makefiles" && set "CMAKE_GENERATOR_PLATFORM=" && '

    def _find_vs_ninja(self, vsdevcmd: Path) -> Path | None:
        install_root = vsdevcmd.parent.parent.parent
        candidate = install_root / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake" / "Ninja" / "ninja.exe"
        if candidate.exists():
            return candidate
        resolved = shutil.which("ninja.exe") or shutil.which("ninja")
        return Path(resolved) if resolved else None

    def _contains_shell_metacharacters(self, argv: list[str]) -> bool:
        return any(token in SHELL_METACHARS for token in argv)

    def _space_unquoted_shell_metacharacters(self, command: str) -> str:
        """Make shell operators tokenizable without treating quoted text as syntax."""
        parts: list[str] = []
        quote: str | None = None
        index = 0
        length = len(command)

        while index < length:
            char = command[index]

            if quote:
                parts.append(char)
                if char == "\\" and index + 1 < length:
                    index += 1
                    parts.append(command[index])
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char in {"'", '"'}:
                quote = char
                parts.append(char)
                index += 1
                continue

            operator = next((item for item in SHELL_OPERATOR_SCAN_ORDER if command.startswith(item, index)), "")
            if operator:
                if parts and not parts[-1].isspace():
                    parts.append(" ")
                parts.append(operator)
                next_index = index + len(operator)
                if next_index < length and not command[next_index].isspace():
                    parts.append(" ")
                index = next_index
                continue

            parts.append(char)
            index += 1

        return "".join(parts)

    def _is_safe_and_chain(self, argv: list[str]) -> bool:
        return "&&" in argv and all(token == "&&" or token not in SHELL_METACHARS for token in argv)

    def _split_and_chain(self, argv: list[str]) -> list[list[str]] | None:
        segments: list[list[str]] = []
        current: list[str] = []
        for token in argv:
            if token == "&&":
                if not current:
                    return None
                segments.append(current)
                current = []
                continue
            current.append(token)
        if not current:
            return None
        segments.append(current)
        return segments

    def _run_and_chain(
        self,
        *,
        command: str,
        cwd: Path,
        argv: list[str],
        timeout_seconds: int | None,
        sandbox_profile: str,
        output_limit: int,
    ) -> CommandResult:
        segments = self._split_and_chain(argv)
        if not segments:
            return self._blocked(command, cwd, "Command chain is incomplete.")

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        step_results: list[dict[str, object]] = []
        for index, segment in enumerate(segments, start=1):
            segment_command = shlex.join(segment)
            result = self.run(
                segment_command,
                cwd,
                timeout_seconds=timeout_seconds,
                sandbox_profile=sandbox_profile,
            )
            if result.stdout:
                stdout_parts.append(f"$ {segment_command}\n{result.stdout}".rstrip())
            if result.stderr:
                stderr_parts.append(f"$ {segment_command}\n{result.stderr}".rstrip())
            step_results.append(
                {
                    "index": index,
                    "command": segment_command,
                    "allowed": result.allowed,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "reason": result.reason,
                    "ok": result.ok,
                }
            )
            if not result.ok:
                reason = f"Chained command stopped at step {index}: {result.reason}"
                return CommandResult(
                    command=command,
                    cwd=str(cwd),
                    allowed=result.allowed,
                    exit_code=result.exit_code,
                    stdout=self._trim_output("\n".join(stdout_parts), limit=output_limit),
                    stderr=self._trim_output("\n".join(stderr_parts), limit=output_limit),
                    timed_out=result.timed_out,
                    reason=reason,
                    steps=step_results,
                )

        return CommandResult(
            command=command,
            cwd=str(cwd),
            allowed=True,
            exit_code=0,
            stdout=self._trim_output("\n".join(stdout_parts), limit=output_limit),
            stderr=self._trim_output("\n".join(stderr_parts), limit=output_limit),
            timed_out=False,
            reason="Chained command finished.",
            steps=step_results,
        )

    def _trim_output(self, text: str | bytes, limit: int = 12000) -> str:
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        return self._trim(ANSI_ESCAPE_RE.sub("", text), limit=limit)

    def _trim(self, text: str, limit: int = 12000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... output truncated ..."
