from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_cpp_templates import (
    cpp_cmake_dll_template,
    cpp_cmake_template,
    cpp_game_loop_template,
    cpp_imgui_win32_dx11_template,
    cpp_msvc_console_template,
    cpp_windows_internals_hooking_template,
    cpp_windows_service_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldCppTemplatesTests(unittest.TestCase):
    def test_cmake_cli_template_matches_project_scaffolder_wrapper(self) -> None:
        files = cpp_cmake_template("42 Native Tool")

        self.assertEqual(files, ProjectScaffolder._cpp_cmake_template("42 Native Tool"))
        self.assertIn("CMakeLists.txt", files)
        self.assertIn("include/app_42_native_tool/version.h", files)
        self.assertIn("src/main.cpp", files)
        self.assertIn("tests/smoke.cpp", files)
        self.assertIn(
            "project(app_42_native_tool VERSION 0.1.0 LANGUAGES CXX)",
            files["CMakeLists.txt"],
        )
        self.assertIn(
            'inline constexpr const char* kAppName = "42 Native Tool";',
            files["include/app_42_native_tool/version.h"],
        )
        self.assertIn("run_generated_app", files["build.py"])
        self.assertIn("std::getline(std::cin, line)", files["src/main.cpp"])

    def test_cmake_dll_template_matches_project_scaffolder_wrapper(self) -> None:
        files = cpp_cmake_dll_template("Runtime Plugin")

        self.assertEqual(files, ProjectScaffolder._cpp_cmake_dll_template("Runtime Plugin"))
        self.assertIn("CMakePresets.json", files)
        self.assertIn("include/runtime_plugin/library.h", files)
        self.assertIn("host/main.cpp", files)
        self.assertIn("src/library.cpp", files)
        self.assertIn(
            'extern "C" RUNTIME_PLUGIN_API int aegis_add',
            files["include/runtime_plugin/library.h"],
        )
        self.assertIn("Host loaded plugin:", files["host/main.cpp"])
        self.assertIn("run_host_validation", files["build.py"])

    def test_imgui_and_game_loop_templates_match_project_scaffolder_wrappers(self) -> None:
        imgui_files = cpp_imgui_win32_dx11_template("Level Inspector")
        game_files = cpp_game_loop_template("Arena Core")

        self.assertEqual(imgui_files, ProjectScaffolder._cpp_imgui_win32_dx11_template("Level Inspector"))
        self.assertEqual(game_files, ProjectScaffolder._cpp_game_loop_template("Arena Core"))
        self.assertIn("vendor/imgui_shim/imgui.h", imgui_files)
        self.assertIn("src/app_state.cpp", imgui_files)
        self.assertIn("render_editor_panels", imgui_files["src/app_state.cpp"])
        self.assertIn("include/arena_core/engine.h", game_files)
        self.assertIn("src/engine.cpp", game_files)
        self.assertIn("FixedStepSimulation", game_files["src/engine.cpp"])

    def test_windows_native_templates_match_project_scaffolder_wrappers(self) -> None:
        msvc_files = cpp_msvc_console_template("Hello Console")
        service_files = cpp_windows_service_template("Log Watcher")
        internals_files = cpp_windows_internals_hooking_template("Internals Hook Lab")

        self.assertEqual(msvc_files, ProjectScaffolder._cpp_msvc_console_template("Hello Console"))
        self.assertEqual(service_files, ProjectScaffolder._cpp_windows_service_template("Log Watcher"))
        self.assertEqual(
            internals_files,
            ProjectScaffolder._cpp_windows_internals_hooking_template("Internals Hook Lab"),
        )
        self.assertIn("Hello-Console.sln", msvc_files)
        self.assertIn("MSBUILD_EXE", msvc_files["build.py"])
        self.assertIn("src/service_main.cpp", service_files)
        self.assertIn("StartServiceCtrlDispatcherW", service_files["src/service_main.cpp"])
        self.assertIn("vendor/minhook_shim/MinHook.h", internals_files)
        self.assertIn("MinHookAdapter", internals_files["include/internals_hook_lab/minhook_adapter.h"])


if __name__ == "__main__":
    unittest.main()
