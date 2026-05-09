from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.approval_sandbox import ApprovalManager
from aegis_ai.commands import CommandRunner
from aegis_ai.schemas import FileChange
from aegis_ai.settings import Settings


class ApprovalAndCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.workspace = self.project_root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            sandbox_profile="standard",
            approval_tier="guided",
            aegis_command_allowlist="python,py",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_guided_auto_apply_blocks_risky_script_changes(self) -> None:
        manager = ApprovalManager("guided", "standard")
        approved, blocked = manager.partition_auto_apply_changes(
            [
                FileChange(action="create", path="app.py", content="print('ok')\n"),
                FileChange(action="create", path="deploy.ps1", content="Write-Host 'ship it'\n"),
            ]
        )

        self.assertEqual([item.path for item in approved], ["app.py"])
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0][0].path, "deploy.ps1")
        self.assertIn("manual", blocked[0][1].reason.lower())

    def test_guided_auto_apply_allows_new_project_metadata(self) -> None:
        manager = ApprovalManager("guided", "standard")
        approved, blocked = manager.partition_auto_apply_changes(
            [
                FileChange(action="create", path="pyproject.toml", content="[project]\nname='demo'\n"),
                FileChange(action="create", path="package.json", content='{"scripts":{}}\n'),
                FileChange(action="create", path="manifest.json", content='{"manifest_version":3}\n'),
                FileChange(action="create", path="app.json", content='{"expo":{}}\n'),
                FileChange(action="create", path="CMakePresets.json", content='{"version":3}\n'),
                FileChange(action="update", path="settings.toml", content="danger = true\n"),
            ]
        )

        self.assertEqual(
            [item.path for item in approved],
            ["pyproject.toml", "package.json", "manifest.json", "app.json", "CMakePresets.json"],
        )
        self.assertEqual([item[0].path for item in blocked], ["settings.toml"])

    def test_prompt_tier_keeps_auto_validation_manual(self) -> None:
        manager = ApprovalManager("prompt", "standard")
        allowed, reason = manager.should_auto_run_command("python -m compileall .", manual=False)

        self.assertFalse(allowed)
        self.assertIn("manual", reason.lower())

    def test_restricted_sandbox_blocks_validation_commands(self) -> None:
        runner = CommandRunner(self.settings)
        result = runner.run("python --version", self.workspace, sandbox_profile="restricted")

        self.assertFalse(result.allowed)
        self.assertIn("does not allow command execution", result.reason.lower())

    def test_default_allowlist_includes_native_build_tools(self) -> None:
        runner = CommandRunner(Settings(_env_file=None))

        self.assertIn("cmake", runner.allowed_commands)
        self.assertIn("ctest", runner.allowed_commands)
        self.assertIn("msbuild", runner.allowed_commands)
        self.assertIn("ninja", runner.allowed_commands)
        self.assertIn("gradlew", runner.allowed_commands)
        self.assertIn("mvnw", runner.allowed_commands)
        self.assertIn("yarn", runner.allowed_commands)
        self.assertIn("bun", runner.allowed_commands)
        self.assertIn("flutter", runner.allowed_commands)
        self.assertIn("swift", runner.allowed_commands)

    def test_local_project_wrappers_normalize_to_allowlisted_executable(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="gradlew,mvnw"))

        gradle = runner.run(".\\gradlew test", self.workspace)
        maven = runner.run("./mvnw test", self.workspace)

        self.assertTrue(gradle.allowed)
        self.assertTrue(maven.allowed)
        self.assertIn("could not start", gradle.reason.lower())
        self.assertIn("could not start", maven.reason.lower())

    def test_destructive_git_aliases_stay_blocked_when_git_is_allowlisted(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="git"))
        commands = (
            "git reset --hard",
            "git.exe reset --hard",
            '"C:\\Program Files\\Git\\cmd\\git.exe" reset --hard',
            "git -C . reset --hard",
            "git.exe -c core.safecrlf=false clean -fd",
            '"C:\\Program Files\\Git\\cmd\\git.exe" --work-tree=. checkout -- .',
        )

        for command in commands:
            with self.subTest(command=command):
                result = runner.run(command, self.workspace)

                self.assertFalse(result.allowed)
                self.assertIn("destructive-command denylist", result.reason)

    def test_windows_path_shim_commands_resolve_before_execution(self) -> None:
        if shutil.which("npm") is None:
            self.skipTest("npm is not available")

        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="npm"))

        result = runner.run("npm --version", self.workspace)

        self.assertTrue(result.allowed)
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn("Command finished", result.reason)

    def test_native_build_validation_can_use_vsdevcmd_wrapper(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="python,cmake,msbuild"))
        self.workspace.joinpath("CMakeLists.txt").write_text("project(Demo LANGUAGES CXX)\n", encoding="utf-8")
        self.workspace.joinpath("build.py").write_text("print('build')\n", encoding="utf-8")
        fake_vsdevcmd = self.project_root / "Microsoft Visual Studio" / "2022" / "Community" / "Common7" / "Tools" / "VsDevCmd.bat"
        fake_vsdevcmd.parent.mkdir(parents=True)
        fake_vsdevcmd.write_text("@echo off\n", encoding="utf-8")

        runner._find_vsdevcmd = lambda: fake_vsdevcmd  # type: ignore[method-assign]
        runner._native_toolchain_available = lambda first: False  # type: ignore[method-assign]
        runner._find_vs_ninja = lambda vsdevcmd: None  # type: ignore[method-assign]

        wrapped = runner._windows_native_toolchain_command_line(
            ["C:\\Python\\python.exe", "build.py"],
            "python",
            self.workspace,
        )

        self.assertIn("cmd.exe /d /c call", wrapped)
        wrapper_command = wrapped
        self.assertIn("call", wrapper_command)
        self.assertIn("VsDevCmd.bat", wrapper_command)
        self.assertIn("CMAKE_GENERATOR=NMake Makefiles", wrapper_command)
        self.assertIn("python.exe build.py", wrapper_command)

    def test_vsdevcmd_wrapper_prefers_vs_ninja_for_cmake_when_available(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="cmake"))
        self.workspace.joinpath("CMakeLists.txt").write_text("project(Demo LANGUAGES CXX)\n", encoding="utf-8")
        fake_vsdevcmd = self.project_root / "Microsoft Visual Studio" / "2022" / "Community" / "Common7" / "Tools" / "VsDevCmd.bat"
        fake_ninja = self.project_root / "Microsoft Visual Studio" / "2022" / "Community" / "Common7" / "IDE" / "CommonExtensions" / "Microsoft" / "CMake" / "Ninja" / "ninja.exe"
        fake_vsdevcmd.parent.mkdir(parents=True)
        fake_ninja.parent.mkdir(parents=True)
        fake_vsdevcmd.write_text("@echo off\n", encoding="utf-8")
        fake_ninja.write_text("", encoding="utf-8")

        runner._find_vsdevcmd = lambda: fake_vsdevcmd  # type: ignore[method-assign]
        runner._native_toolchain_available = lambda first: False  # type: ignore[method-assign]
        runner._find_vs_ninja = lambda vsdevcmd: fake_ninja  # type: ignore[method-assign]

        wrapped = runner._windows_native_toolchain_command_line(
            ["C:\\Program Files\\CMake\\bin\\cmake.exe", "-S", ".", "-B", "build"],
            "cmake",
            self.workspace,
        )

        self.assertIn("cmd.exe /d /c call", wrapped)
        wrapper_command = wrapped
        self.assertIn("CMAKE_GENERATOR=Ninja", wrapper_command)
        self.assertIn(f"CMAKE_MAKE_PROGRAM={fake_ninja}", wrapper_command)
        self.assertNotIn("CMAKE_GENERATOR=NMake Makefiles", wrapper_command)

    def test_windows_native_wrapper_env_removes_shell_metacharacter_path_entries(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="python"))
        unsafe_path = os.pathsep.join(
            [
                r"C:\Safe\Tools",
                r"C:\Users\gabri\Desktop\Aegis\Tools\04 Runtime & Engine Tools\ChatBot\website\node_modules\.bin",
                r"C:\AlsoSafe\bin",
            ]
        )

        with patch.dict(os.environ, {"PATH": unsafe_path, "Path": unsafe_path}, clear=False):
            env = runner._windows_native_wrapper_env()

        self.assertIn(r"C:\Safe\Tools", env["PATH"])
        self.assertIn(r"C:\AlsoSafe\bin", env["PATH"])
        self.assertNotIn("Runtime & Engine Tools", env["PATH"])

    def test_windows_cmake_default_build_dir_runs_from_short_temp_root(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only CMake path-shortening behavior")
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="cmake,ctest"))
        self.workspace.joinpath("CMakeLists.txt").write_text("project(Demo LANGUAGES CXX)\n", encoding="utf-8")

        configure = runner._windows_native_cmake_argv_with_short_build_dir(
            ["cmake", "-S", ".", "-B", "build"],
            "cmake",
            self.workspace,
        )
        build = runner._windows_native_cmake_argv_with_short_build_dir(
            ["cmake", "--build", "build"],
            "cmake",
            self.workspace,
        )
        ctest = runner._windows_native_cmake_argv_with_short_build_dir(
            ["ctest", "--test-dir", "build"],
            "ctest",
            self.workspace,
        )

        expected_build_dir = str(runner._windows_native_cmake_build_dir(self.workspace))
        self.assertEqual(configure[-1], expected_build_dir)
        self.assertEqual(build[-1], expected_build_dir)
        self.assertEqual(ctest[-1], expected_build_dir)
        self.assertNotIn(str(self.workspace / "build"), configure)

    def test_vsdevcmd_wrapper_stays_off_for_non_native_python_projects(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="python"))
        fake_vsdevcmd = self.project_root / "VS" / "Common7" / "Tools" / "VsDevCmd.bat"

        runner._find_vsdevcmd = lambda: fake_vsdevcmd  # type: ignore[method-assign]
        runner._native_toolchain_available = lambda first: False  # type: ignore[method-assign]

        wrapped = runner._windows_native_toolchain_command_line(
            ["C:\\Python\\python.exe", "build.py"],
            "python",
            self.workspace,
        )

        self.assertEqual(wrapped, "")

    def test_command_output_strips_ansi_sequences(self) -> None:
        runner = CommandRunner(self.settings)

        result = runner.run("python -c \"print('\\x1b[32mOK\\x1b[0m')\"", self.workspace)

        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK")

    def test_safe_and_chain_runs_as_sequential_allowed_commands(self) -> None:
        runner = CommandRunner(self.settings)

        result = runner.run(
            "python -c \"print('one')\" && python -c \"print('two')\"",
            self.workspace,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("one", result.stdout)
        self.assertIn("two", result.stdout)
        self.assertIn("Chained command finished", result.reason)
        self.assertEqual(len(result.steps), 2)
        self.assertIn("one", str(result.steps[0]["command"]))
        self.assertIn("two", str(result.steps[1]["command"]))
        self.assertTrue(all(step["ok"] for step in result.steps))

    def test_safe_and_chain_without_spaces_runs_as_sequential_allowed_commands(self) -> None:
        runner = CommandRunner(self.settings)

        result = runner.run(
            "python -c \"print('one')\"&&python -c \"print('two')\"",
            self.workspace,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("one", result.stdout)
        self.assertIn("two", result.stdout)
        self.assertIn("Chained command finished", result.reason)
        self.assertEqual(len(result.steps), 2)

    def test_quoted_shell_operator_text_stays_inside_single_command(self) -> None:
        runner = CommandRunner(self.settings)

        result = runner.run("python -c \"print('one&&two')\"", self.workspace)

        self.assertTrue(result.allowed)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), "one&&two")
        self.assertEqual(result.steps, [])

    def test_shell_operators_without_spaces_stay_blocked_when_not_safe_chain(self) -> None:
        runner = CommandRunner(Settings(_env_file=None))

        semicolon = runner.run("python --version;python --version", self.workspace)
        pipe = runner.run("python --version|python --version", self.workspace)

        self.assertFalse(semicolon.allowed)
        self.assertFalse(pipe.allowed)
        self.assertIn("shell operators", semicolon.reason.lower())
        self.assertIn("shell operators", pipe.reason.lower())

    def test_other_shell_operators_stay_blocked(self) -> None:
        runner = CommandRunner(Settings(_env_file=None))

        result = runner.run("python --version | python --version", self.workspace)

        self.assertFalse(result.allowed)
        self.assertIn("shell operators", result.reason.lower())

    def test_powershell_commands_are_limited_to_root_build_guard(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="powershell,pwsh"))

        command = runner.run("powershell -Command Write-Host ok", self.workspace)
        escaped = runner.run("pwsh -NoProfile -ExecutionPolicy Bypass -File ../build.ps1", self.workspace)

        self.assertFalse(command.allowed)
        self.assertFalse(escaped.allowed)
        self.assertIn("limited to the exact root build.ps1", command.reason)
        self.assertIn("limited to the exact root build.ps1", escaped.reason)

    def test_powershell_root_build_guard_can_run_when_allowlisted(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="powershell,pwsh"))
        self.workspace.joinpath("build.ps1").write_text("Write-Output 'guard ok'\n", encoding="utf-8")

        result = runner.run("powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1", self.workspace)

        self.assertTrue(result.allowed)
        self.assertNotIn("limited to the exact root build.ps1", result.reason)

    def test_powershell_windows_style_root_build_guard_can_run_when_allowlisted(self) -> None:
        runner = CommandRunner(Settings(_env_file=None, aegis_command_allowlist="powershell,pwsh"))
        self.workspace.joinpath("build.ps1").write_text("Write-Output 'guard ok'\n", encoding="utf-8")

        result = runner.run(r"powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1", self.workspace)

        self.assertTrue(result.allowed)
        self.assertNotIn("limited to the exact root build.ps1", result.reason)


if __name__ == "__main__":
    unittest.main()
