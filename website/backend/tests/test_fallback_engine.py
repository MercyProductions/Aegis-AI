from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.fallback import FallbackEngine
from aegis_ai.schemas import WorkspaceFile
from aegis_ai.settings import Settings


class FallbackEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FallbackEngine(Settings(_env_file=None))
        self.workspace = Path("C:/Aegis/TestWorkspace")

    def change_paths_for(self, message: str) -> list[str]:
        _reply, _plan, changes, _warnings = self.engine.respond(
            message,
            "build",
            self.workspace,
            [],
        )
        return [change.path for change in changes]

    def test_generic_app_request_does_not_default_to_static_website(self) -> None:
        paths = self.change_paths_for("Build an app called Field Notes")

        self.assertIn("pyproject.toml", paths)
        self.assertIn("build.py", paths)
        self.assertIn("src/aegis_app/main.py", paths)
        self.assertIn("tests/test_smoke.py", paths)
        self.assertNotIn("index.html", paths)
        self.assertNotIn("styles.css", paths)

    def test_python_cli_request_generates_app_with_build_runner(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a Python CLI app that accepts --name, prints a greeting, includes a smoke test, and run validation.",
            "build",
            self.workspace,
            [],
        )

        paths = [change.path for change in changes]
        self.assertIn("pyproject.toml", paths)
        self.assertIn("build.py", paths)
        self.assertIn("src/aegis_app/main.py", paths)
        self.assertIn("tests/test_smoke.py", paths)
        self.assertNotIn("requirements.txt", paths)
        self.assertNotIn("app/main.py", paths)

        build_runner = next(change.content or "" for change in changes if change.path == "build.py")
        readme = next(change.content or "" for change in changes if change.path == "README.md")
        pyproject = next(change.content or "" for change in changes if change.path == "pyproject.toml")
        self.assertIn("Python app validation passed", build_runner)
        self.assertIn("python build.py", readme)
        self.assertIn('pythonpath = ["src"]', pyproject)

    def test_python_cli_request_with_website_in_path_still_generates_python_app(self) -> None:
        paths = self.change_paths_for(
            r"At this path C:\Users\gabri\Desktop\Aegis\Website\ChatBot\workspace\sample "
            "create a Python CLI app that accepts --name, prints a greeting, and run validation."
        )

        self.assertIn("pyproject.toml", paths)
        self.assertIn("build.py", paths)
        self.assertIn("src/aegis_app/main.py", paths)
        self.assertNotIn("index.html", paths)
        self.assertNotIn("app/main.py", paths)

    def test_explicit_website_request_still_generates_web_starter(self) -> None:
        paths = self.change_paths_for("Create a website landing page for Field Notes")

        self.assertIn("index.html", paths)
        self.assertIn("styles.css", paths)
        self.assertIn("app.js", paths)
        self.assertIn("build.js", paths)

    def test_explicit_vite_react_request_generates_vite_project(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a Vite React website for a premium barber shop and validate the build.",
            "build",
            self.workspace,
            [],
        )

        paths = [change.path for change in changes]
        self.assertIn("package.json", paths)
        self.assertIn("vite.config.ts", paths)
        self.assertIn("src/main.tsx", paths)
        self.assertIn("src/App.tsx", paths)
        self.assertIn("src/styles.css", paths)
        self.assertNotIn("build.js", paths)

        package_json = next(change.content or "" for change in changes if change.path == "package.json")
        app = next(change.content or "" for change in changes if change.path == "src/App.tsx")
        self.assertIn('"vite"', package_json)
        self.assertIn('"react"', package_json)
        self.assertIn("Prime Cut Barbershop", app)

    def test_explicit_next_request_generates_next_project(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a Next.js website for a premium barber shop and validate the build.",
            "build",
            self.workspace,
            [],
        )

        paths = [change.path for change in changes]
        self.assertIn("package.json", paths)
        self.assertIn("next.config.mjs", paths)
        self.assertIn("app/page.tsx", paths)
        self.assertIn("app/layout.tsx", paths)
        self.assertIn("components/app-shell.tsx", paths)
        self.assertNotIn("build.js", paths)

        package_json = next(change.content or "" for change in changes if change.path == "package.json")
        app_shell = next(change.content or "" for change in changes if change.path == "components/app-shell.tsx")
        self.assertIn('"next"', package_json)
        self.assertIn("Prime Cut Barbershop", app_shell)

    def test_react_native_request_does_not_route_to_vite(self) -> None:
        paths = self.change_paths_for("Create a React Native mobile app with Expo and TypeScript")

        self.assertIn("app.json", paths)
        self.assertIn("App.tsx", paths)
        self.assertIn("src/screens/HomeScreen.tsx", paths)
        self.assertNotIn("vite.config.ts", paths)
        self.assertNotIn("src/main.tsx", paths)

    def test_electron_request_routes_to_desktop_template(self) -> None:
        paths = self.change_paths_for("Create an Electron React desktop app with TypeScript")

        self.assertIn("electron.vite.config.ts", paths)
        self.assertIn("src/main/index.ts", paths)
        self.assertIn("src/preload/index.ts", paths)
        self.assertIn("src/renderer/src/App.tsx", paths)
        self.assertNotIn("app/page.tsx", paths)

    def test_tauri_request_routes_to_tauri_template(self) -> None:
        paths = self.change_paths_for("Create a Tauri React desktop app")

        self.assertIn("src-tauri/Cargo.toml", paths)
        self.assertIn("src-tauri/src/main.rs", paths)
        self.assertIn("src/App.tsx", paths)
        self.assertNotIn("electron.vite.config.ts", paths)

    def test_browser_extension_request_routes_to_mv3_template(self) -> None:
        paths = self.change_paths_for("Create a Chrome browser extension with manifest v3")

        self.assertIn("manifest.json", paths)
        self.assertIn("src/background.js", paths)
        self.assertIn("popup/popup.html", paths)
        self.assertNotIn("index.html", paths)

    def test_native_specialized_requests_route_before_generic_cpp(self) -> None:
        driver_paths = self.change_paths_for("Create a Windows kernel driver with a controller app")
        dll_paths = self.change_paths_for("Create a C++ DLL shared library with CMake")
        imgui_paths = self.change_paths_for("Create a Dear ImGui C++ game editor tool with asset panels")
        game_paths = self.change_paths_for("Create a native game loop sandbox with an asset registry")
        analyzer_paths = self.change_paths_for("Create a game file analyzer for owned asset bundles and pak files")
        internals_paths = self.change_paths_for("Create a C++ Windows internals MinHook instrumentation tool")
        sln_paths = self.change_paths_for("Create a tool to merge two sln solutions and split a project into its own sln")

        self.assertIn("driver/driver.c", driver_paths)
        self.assertIn("controller/main.cpp", driver_paths)
        self.assertIn("include/testworkspace/library.h", dll_paths)
        self.assertIn("src/library.cpp", dll_paths)
        self.assertNotIn("src/main.cpp", dll_paths)
        self.assertIn("vendor/imgui_shim/imgui.h", imgui_paths)
        self.assertIn("src/app_state.cpp", imgui_paths)
        self.assertIn("src/engine.cpp", game_paths)
        self.assertIn("tests/smoke.cpp", game_paths)
        self.assertTrue(any(path.endswith("/analyzer.py") or path.endswith("\\analyzer.py") for path in analyzer_paths))
        self.assertIn("samples/sample_asset.bin", analyzer_paths)
        self.assertIn("src/instrumentation.cpp", internals_paths)
        self.assertTrue(any(path.endswith("/minhook_adapter.h") or path.endswith("\\minhook_adapter.h") for path in internals_paths))
        self.assertTrue(any(path.endswith("/sln.py") or path.endswith("\\sln.py") for path in sln_paths))
        self.assertIn("samples/AppOne.sln", sln_paths)

    def test_explicit_native_prompt_beats_existing_next_workspace_shape(self) -> None:
        next_files = [
            WorkspaceFile(path="package.json", size=120, kind="text"),
            WorkspaceFile(path="next.config.mjs", size=80, kind="text"),
            WorkspaceFile(path="app/page.tsx", size=200, kind="text"),
        ]

        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a C++ DLL shared library with CMake and a host executable",
            "build",
            self.workspace,
            next_files,
        )

        paths = {change.path.replace("\\", "/").lower() for change in changes}
        self.assertIn("src/library.cpp", paths)
        self.assertIn("host/main.cpp", paths)
        self.assertIn("cmakelists.txt", paths)
        self.assertNotIn("app/page.tsx", paths)
        self.assertNotIn("src/app.tsx", paths)
        self.assertNotIn("next.config.mjs", paths)

    def test_runtime_language_requests_route_to_matching_templates(self) -> None:
        rust_paths = self.change_paths_for("Create a Rust CLI app")
        go_paths = self.change_paths_for("Create a Go HTTP API")
        dotnet_paths = self.change_paths_for("Create a C# WPF desktop app")

        self.assertIn("Cargo.toml", rust_paths)
        self.assertIn("src/main.rs", rust_paths)
        self.assertIn("go.mod", go_paths)
        self.assertIn("cmd/server/main.go", go_paths)
        self.assertTrue(any(path.endswith(".csproj") for path in dotnet_paths))
        self.assertTrue(any(path.endswith("MainWindow.xaml") for path in dotnet_paths))

    def test_complete_website_request_generates_full_static_site(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Complete a full barber styled website for Rick Cullers",
            "build",
            self.workspace,
            [],
        )

        paths = [change.path for change in changes]
        self.assertIn("index.html", paths)
        self.assertIn("styles.css", paths)
        self.assertIn("app.js", paths)
        self.assertIn("build.js", paths)
        index = next(change.content or "" for change in changes if change.path == "index.html")
        build_runner = next(change.content or "" for change in changes if change.path == "build.js")
        readme = next(change.content or "" for change in changes if change.path == "README.md")
        self.assertIn("Services", index)
        self.assertIn("Pricing", index)
        self.assertIn("booking", index.lower())
        self.assertIn("Static site validation passed", build_runner)
        self.assertIn("id=\"booking\"", build_runner)
        self.assertIn("node build.js", readme)

    def test_complete_static_site_validator_runs_with_node(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is not available")

        _reply, _plan, changes, _warnings = self.engine.respond(
            "Complete a full barber styled website for Rick Cullers",
            "build",
            self.workspace,
            [],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for change in changes:
                target = root / change.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content or "", encoding="utf-8")

            result = subprocess.run(
                ["node", "build.js"],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
            )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Static site validation passed", result.stdout)

    def test_existing_next_workspace_gets_stack_native_changes(self) -> None:
        files = [
            WorkspaceFile(path="package.json", kind="text", size=100),
            WorkspaceFile(path="app/page.tsx", kind="text", size=100),
            WorkspaceFile(path="app/layout.tsx", kind="text", size=100),
            WorkspaceFile(path="next.config.mjs", kind="text", size=100),
            WorkspaceFile(path="tsconfig.json", kind="text", size=100),
        ]

        _reply, _plan, changes, _warnings = self.engine.respond(
            "Complete a full barber styled website",
            "build",
            self.workspace,
            files,
        )

        paths = [change.path for change in changes]
        actions = {change.path: change.action for change in changes}
        self.assertIn("app/page.tsx", paths)
        self.assertIn("components/app-shell.tsx", paths)
        self.assertIn("app/globals.css", paths)
        self.assertNotIn("index.html", paths)
        self.assertEqual(actions["app/page.tsx"], "update")
        self.assertEqual(actions["app/layout.tsx"], "update")
        self.assertEqual(actions["app/globals.css"], "create")
        self.assertEqual(actions["components/app-shell.tsx"], "create")

    def test_existing_native_dll_continuation_does_not_generate_web_or_starter_files(self) -> None:
        files = [
            WorkspaceFile(path="ExistingNativeDll.vcxproj", kind="text", size=1500),
            WorkspaceFile(path="include/aegis/plugin.h", kind="text", size=340),
            WorkspaceFile(path="src/plugin.cpp", kind="text", size=900),
            WorkspaceFile(path="src/dllmain.cpp", kind="text", size=260),
        ]

        _reply, plan, changes, warnings = self.engine.respond(
            (
                "At this path C:\\Users\\gabri\\Desktop\\Aegis Native DLL "
                "work on my existing DLL that I already made, add diagnostics UI, build it, "
                "and do not make a website."
            ),
            "build",
            self.workspace,
            files,
        )

        paths = {change.path.replace("\\", "/").lower() for change in changes}
        self.assertIn("build.py", paths)
        self.assertNotIn("index.html", paths)
        self.assertNotIn("package.json", paths)
        self.assertNotIn("app/page.tsx", paths)
        self.assertNotIn("src/main.cpp", paths)
        self.assertTrue(any("preserved the existing workspace stack" in warning for warning in warnings))
        self.assertTrue(any("Preserve the existing workspace stack" in step for step in plan))

    def test_existing_native_dll_continuation_does_not_rewrite_existing_build_helper(self) -> None:
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=500),
            WorkspaceFile(path="src/library.cpp", kind="text", size=900),
            WorkspaceFile(path="build.py", kind="text", size=700),
        ]

        _reply, _plan, changes, warnings = self.engine.respond(
            "continue improving this existing C++ DLL project and build it",
            "build",
            self.workspace,
            files,
        )

        self.assertEqual(changes, [])
        self.assertTrue(any("preserved the existing workspace stack" in warning for warning in warnings))

    def test_existing_slnx_workspace_gets_msbuild_validation_helper(self) -> None:
        files = [
            WorkspaceFile(path="Modern.slnx", kind="text", size=500),
            WorkspaceFile(path="src/main.cpp", kind="text", size=900),
        ]

        _reply, _plan, changes, warnings = self.engine.respond(
            "continue improving this existing Visual Studio solution and build it",
            "build",
            self.workspace,
            files,
        )

        self.assertEqual([change.path for change in changes], ["build.py"])
        self.assertIn("*.slnx", changes[0].content or "")
        self.assertIn(".sln/.slnx", changes[0].content or "")
        self.assertTrue(any("preserved the existing workspace stack" in warning for warning in warnings))

    def test_existing_native_project_allows_explicit_fresh_rebuild_request(self) -> None:
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=100),
            WorkspaceFile(path="src/app.cpp", kind="text", size=100),
        ]

        _reply, _plan, changes, _warnings = self.engine.respond(
            "rebuild from scratch as a fresh C++ console app",
            "build",
            self.workspace,
            files,
        )

        paths = {change.path.replace("\\", "/").lower() for change in changes}
        self.assertIn("cmakelists.txt", paths)
        self.assertIn("src/main.cpp", paths)
        self.assertIn("build.py", paths)

    def test_cpp_console_project_generates_buildable_sources(self) -> None:
        paths = self.change_paths_for("Create a C++ console app that prints hello world")

        self.assertIn("CMakeLists.txt", paths)
        self.assertIn("src/main.cpp", paths)
        self.assertIn("build.py", paths)
        self.assertIn("README.md", paths)

        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a C++ console app that prints hello world",
            "build",
            self.workspace,
            [],
        )
        build_runner = next(change.content or "" for change in changes if change.path == "build.py")
        readme = next(change.content or "" for change in changes if change.path == "README.md")
        main_cpp = next(change.content or "" for change in changes if change.path == "src/main.cpp")
        self.assertIn("Hello, world!", main_cpp)
        self.assertIn("--no-wait", build_runner)
        self.assertIn("python build.py", readme)
        self.assertNotIn("&&", readme)

    def test_cpp_path_build_request_generates_buildable_sources(self) -> None:
        paths = self.change_paths_for(
            "At this path create a C++ console project that prints Hello, world!, waits for user input before closing, and build it."
        )

        self.assertIn("CMakeLists.txt", paths)
        self.assertIn("src/main.cpp", paths)
        self.assertIn("build.py", paths)
        self.assertIn("README.md", paths)

    def test_cpp_sln_request_generates_visual_studio_solution_sources(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Create a C++ console app with a sln that prints hello world",
            "build",
            self.workspace,
            [],
        )

        paths = [change.path for change in changes]
        self.assertIn("TestWorkspace.sln", paths)
        self.assertIn("TestWorkspace.vcxproj", paths)
        self.assertIn("TestWorkspace.vcxproj.filters", paths)
        self.assertIn("src/main.cpp", paths)
        self.assertIn("build.py", paths)
        self.assertNotIn("CMakeLists.txt", paths)

        build_runner = next(change.content or "" for change in changes if change.path == "build.py")
        main_cpp = next(change.content or "" for change in changes if change.path == "src/main.cpp")
        self.assertIn("MSBuild", build_runner)
        self.assertIn("Hello, world!", main_cpp)

    def test_cpp_workspace_followup_uses_cpp_stack_without_repeating_language(self) -> None:
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=100),
            WorkspaceFile(path="src/main.cpp", kind="text", size=100),
        ]

        _reply, _plan, changes, _warnings = self.engine.respond(
            "build it and fix any errors",
            "build",
            self.workspace,
            files,
        )

        paths = [change.path for change in changes]
        self.assertIn("build.py", paths)
        self.assertNotIn("CMakeLists.txt", paths)
        self.assertNotIn("src/main.cpp", paths)
        self.assertNotIn("index.html", paths)

    def test_build_word_without_product_is_not_scaffolded(self) -> None:
        _reply, _plan, changes, _warnings = self.engine.respond(
            "Build confidence by explaining the architecture",
            "build",
            self.workspace,
            [],
        )

        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
