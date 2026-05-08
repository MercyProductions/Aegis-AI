from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.commands import CommandResult, CommandRunner
from aegis_ai.project_scaffolder import ProjectScaffolder
from aegis_ai.schemas import ProjectScaffoldPlanRequest, ProjectScaffoldRequest
from aegis_ai.settings import Settings
from aegis_ai.validation import ValidationManager
from aegis_ai.workspace import WorkspaceManager


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def run(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int | None = None,
        sandbox_profile: str | None = None,
    ) -> CommandResult:
        self.commands.append(command)
        return CommandResult(
            command=command,
            cwd=str(cwd),
            allowed=True,
            exit_code=0,
            stdout=f"{command} ok\n",
            stderr="",
            timed_out=False,
            reason="Command finished.",
        )


class ProjectScaffolderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
        )
        self.workspace = WorkspaceManager(self.project_root, self.settings)
        self.validation = ValidationManager()
        self.scaffolder = ProjectScaffolder(self.workspace, self.validation)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_presets_include_web_and_python_targets(self) -> None:
        preset_ids = {preset.id for preset in ProjectScaffolder.presets()}

        self.assertIn("nextjs-ts-tailwind", preset_ids)
        self.assertIn("vite-react-ts", preset_ids)
        self.assertIn("static-html-site", preset_ids)
        self.assertIn("browser-extension-mv3", preset_ids)
        self.assertIn("vscode-extension-js", preset_ids)
        self.assertIn("node-cli-js", preset_ids)
        self.assertIn("node-http-api-js", preset_ids)
        self.assertIn("node-fullstack-js", preset_ids)
        self.assertIn("powershell-module", preset_ids)
        self.assertIn("python-cli", preset_ids)
        self.assertIn("python-tkinter-desktop", preset_ids)
        self.assertIn("python-stdlib-api", preset_ids)
        self.assertIn("fastapi-python-api", preset_ids)
        self.assertIn("express-ts-api", preset_ids)
        self.assertIn("sqlite-python-db", preset_ids)
        self.assertIn("cpp-cmake-cli", preset_ids)
        self.assertIn("cpp-cmake-dll", preset_ids)
        self.assertIn("cpp-imgui-win32-dx11", preset_ids)
        self.assertIn("cpp-game-loop-cmake", preset_ids)
        self.assertIn("python-game-file-analyzer", preset_ids)
        self.assertIn("cpp-msvc-console-sln", preset_ids)
        self.assertIn("cpp-windows-service", preset_ids)
        self.assertIn("cpp-windows-internals-hooking", preset_ids)
        self.assertIn("python-sln-refactor-tool", preset_ids)
        self.assertIn("windows-kernel-driver-controller", preset_ids)
        self.assertIn("electron-react-ts", preset_ids)
        self.assertIn("expo-react-native-ts", preset_ids)
        self.assertIn("django-python-web", preset_ids)
        self.assertIn("rust-cli", preset_ids)
        self.assertIn("go-http-api", preset_ids)
        self.assertIn("dotnet-webapi-csharp", preset_ids)
        self.assertIn("dotnet-console-csharp", preset_ids)
        self.assertIn("dotnet-wpf-csharp", preset_ids)
        self.assertIn("tauri-react-ts", preset_ids)

    def test_preview_does_not_create_target_or_checkpoint(self) -> None:
        target = self.project_root / "workspace" / "preview-only"

        result = self.scaffolder.preview(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="express-ts-api",
                project_name="Preview API",
            )
        )

        self.assertTrue(result.ok)
        self.assertIn("Previewed", result.message)
        self.assertFalse(target.exists())
        self.assertEqual(result.checkpoint, None)
        self.assertEqual(result.applied, [])
        self.assertIn("package.json", [file.path for file in result.files])
        self.assertIn("AGENTS.md", [file.path for file in result.files])
        self.assertIn(".aegis/project.json", [file.path for file in result.files])
        self.assertIn(".aegis/ROADMAP.md", [file.path for file in result.files])
        self.assertIn(".aegis/file_index.json", [file.path for file in result.files])
        self.assertIn(".aegis/known_errors.json", [file.path for file in result.files])
        self.assertEqual(result.roadmap_path, ".aegis/ROADMAP.md")
        self.assertTrue(any(stage.id == "validate" for stage in result.stages))
        self.assertTrue(result.plan_steps)
        self.assertTrue(result.diff_summary)

    def test_prompt_plan_selects_stack_name_and_target_without_writing(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Build a Node Express TypeScript API called Invoice Hub with REST endpoints",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.preset.id, "express-ts-api")
        self.assertEqual(result.project_name, "invoice-hub")
        self.assertEqual(result.scaffold_request.preset_id, "express-ts-api")
        self.assertEqual(result.scaffold_request.target_path, result.target_path)
        self.assertFalse(Path(result.target_path).exists())
        self.assertIn("api + node/typescript", result.detected_keywords)

    def test_prompt_plan_routes_generic_rest_api_to_dependency_free_node_api(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Build a REST API called Inventory Gateway with JSON CRUD endpoints and tests",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.preset.id, "node-http-api-js")
        self.assertEqual(result.project_name, "inventory-gateway")
        self.assertEqual(result.validation_command, "node build.js")
        self.assertIn("dependency-free node api", result.detected_keywords)

    def test_prompt_plan_routes_generic_fullstack_crud_app_to_dependency_free_fullstack(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a full-stack CRUD dashboard app called Task Ops with frontend and backend tests",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.preset.id, "node-fullstack-js")
        self.assertEqual(result.project_name, "task-ops")
        self.assertEqual(result.validation_command, "node build.js")
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("dependency-free full-stack app", result.detected_keywords)

    def test_prompt_plan_routes_python_rest_api_to_stdlib_api_without_fastapi(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a Python REST API called Inventory Bridge with JSON CRUD endpoints and unittest coverage",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.preset.id, "python-stdlib-api")
        self.assertEqual(result.project_name, "inventory-bridge")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("dependency-free python api", result.detected_keywords)

    def test_prompt_plan_routes_powershell_automation_to_module(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a PowerShell module called Admin Toolkit with admin automation functions and smoke tests",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.preset.id, "powershell-module")
        self.assertEqual(result.project_name, "admin-toolkit")
        self.assertEqual(result.validation_command, "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1")
        self.assertIn("powershell automation", result.detected_keywords)

    def test_prompt_plan_prefers_python_api_and_native_cpp(self) -> None:
        api_result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create a Python FastAPI backend called Metrics API")
        )
        cpp_result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Make a native C++ CMake command-line tool called Asset Packager")
        )

        self.assertEqual(api_result.preset.id, "fastapi-python-api")
        self.assertEqual(api_result.project_name, "metrics-api")
        self.assertEqual(cpp_result.preset.id, "cpp-cmake-cli")
        self.assertEqual(cpp_result.project_name, "asset-packager")

    def test_prompt_plan_routes_cpp_sln_to_visual_studio_solution(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} please create a C++ console project with an sln "
                    "that prints to console hello world and requires a user to press enter for the app to close"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.project_name, "roblox")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)
        self.assertIn("explicit stack language", " ".join(result.assumptions))

    def test_cpp_cmake_build_runner_avoids_ninja_on_windows(self) -> None:
        files = ProjectScaffolder._cpp_cmake_template("stress-console")
        build_py = files["build.py"]

        self.assertIn("import os", build_py)
        self.assertIn("AEGIS_CMAKE_BUILD_DIR", build_py)
        self.assertIn('os.name != "nt"', build_py)
        self.assertIn('"Hello, world!"', build_py)

    def test_windows_internals_build_runner_uses_short_external_build_dir(self) -> None:
        files = ProjectScaffolder._cpp_windows_internals_hooking_template("internals-hook-lab")
        build_py = files["build.py"]

        self.assertIn("import hashlib", build_py)
        self.assertIn("import tempfile", build_py)
        self.assertIn("AEGIS_CMAKE_BUILD_DIR", build_py)
        self.assertIn('"-B", str(BUILD_DIR)', build_py)
        self.assertIn('"--build", str(BUILD_DIR)', build_py)
        self.assertIn('"--test-dir", str(BUILD_DIR)', build_py)
        self.assertNotIn('(ROOT / "build")', build_py)

    def test_prompt_path_stops_before_repeated_at_this_path_phrase(self) -> None:
        target = self.project_root / "workspace" / "Aegis Game Dumper"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"{target} at this path create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.project_name, "aegis-game-dumper")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertNotIn("at this path", result.target_path.lower())
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)

    def test_prompt_path_keeps_action_words_inside_folder_names(self) -> None:
        target = self.project_root / "workspace" / "Aegis Build Tools New"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing, then build it"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.project_name, "aegis-build-tools-new")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)

    def test_prompt_path_stops_before_design_instruction(self) -> None:
        target = self.project_root / "workspace" / "Designed DLL"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} design and build a C++ DLL project "
                    "with CMake and validate it"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.project_name, "designed-dll")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertNotIn("design and", result.target_path.lower())
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)

    def test_prompt_path_keeps_design_inside_folder_names(self) -> None:
        target = self.project_root / "workspace" / "Aegis Design Tools"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.project_name, "aegis-design-tools")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)

    def test_prompt_path_stops_before_natural_refinement_verbs(self) -> None:
        cases = (
            (
                "Aegis Native DLL",
                "refine my existing DLL project and build it",
                "cpp-cmake-dll",
                ("refine my",),
            ),
            (
                "Native Plugin",
                "refine my DLL plugin; it is not a website and should stay native",
                "cpp-cmake-dll",
                ("refine my",),
            ),
            (
                "Aegis Native Tool",
                "optimize this existing C++ CMake project and run validation",
                "cpp-cmake-cli",
                ("optimize this",),
            ),
            (
                "Aegis Cleanup Tool",
                "clean up this C++ console project with an sln and make sure it builds",
                "cpp-msvc-console-sln",
                ("clean up this",),
            ),
            (
                "Barber Website",
                "improve this existing website and add a booking section",
                "static-html-site",
                ("improve this",),
            ),
        )

        for folder_name, instruction, expected_preset, forbidden_fragments in cases:
            with self.subTest(folder_name=folder_name):
                target = self.project_root / "workspace" / folder_name
                target.mkdir(parents=True, exist_ok=True)
                result = self.scaffolder.plan_from_prompt(
                    ProjectScaffoldPlanRequest(prompt=f"at this path {target} {instruction}")
                )

                self.assertEqual(result.preset.id, expected_preset)
                self.assertEqual(result.target_path, str(target.resolve()))
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, result.target_path.lower())

    def test_prompt_path_keeps_natural_refinement_words_inside_folder_names(self) -> None:
        target = self.project_root / "workspace" / "Aegis Optimize Tools"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.project_name, "aegis-optimize-tools")
        self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_trims_instruction_separators_after_target(self) -> None:
        cases = (
            (
                "Aegis Native DLL",
                " - refine my existing DLL project and build it",
                "cpp-cmake-dll",
            ),
            (
                "Aegis Native Tool",
                ": optimize this existing C++ CMake project and run validation",
                "cpp-cmake-cli",
            ),
            (
                "Aegis Cleanup Tool",
                "; clean up this C++ solution and make sure it builds",
                "cpp-msvc-console-sln",
            ),
            (
                "Barber Website",
                ", improve this existing website and add a booking section",
                "static-html-site",
            ),
        )

        for folder_name, instruction, expected_preset in cases:
            with self.subTest(folder_name=folder_name, instruction=instruction):
                target = self.project_root / "workspace" / folder_name
                result = self.scaffolder.plan_from_prompt(
                    ProjectScaffoldPlanRequest(prompt=f"at this path {target}{instruction}")
                )

                self.assertEqual(result.preset.id, expected_preset)
                self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_keeps_hyphenated_folder_names(self) -> None:
        target = self.project_root / "workspace" / "Aegis-Optimize-Tools"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} create a C++ console app and build it"
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.project_name, "aegis-optimize-tools")
        self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_keeps_balanced_wrapper_punctuation_in_folder_names(self) -> None:
        cases = (
            ("Aegis Tool (1)", "cpp-cmake-cli"),
            ("Aegis Tool [Beta]", "cpp-cmake-cli"),
            ("Aegis Tool {Draft}", "cpp-cmake-cli"),
            ("Rick Culler's Website", "static-html-site"),
        )

        for folder_name, expected_preset in cases:
            with self.subTest(folder_name=folder_name):
                target = self.project_root / "workspace" / folder_name
                prompt = (
                    f"at this path {target} create a barber website"
                    if "Website" in folder_name
                    else f"at this path {target} create a C++ console app and build it"
                )
                result = self.scaffolder.plan_from_prompt(ProjectScaffoldPlanRequest(prompt=prompt))

                self.assertEqual(result.preset.id, expected_preset)
                self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_strips_unbalanced_wrapper_punctuation(self) -> None:
        target = self.project_root / "workspace" / "Aegis Tool"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"(at this path {target}) create a C++ console app and build it"
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_keeps_instruction_like_words_inside_folder_names(self) -> None:
        cases = (
            "Aegis Tool With Tests",
            "Aegis Built Using CMake",
            "Aegis Game And Then Some",
            "Aegis Project For Me",
            "Aegis If Tool",
        )

        for folder_name in cases:
            with self.subTest(folder_name=folder_name):
                target = self.project_root / "workspace" / folder_name
                result = self.scaffolder.plan_from_prompt(
                    ProjectScaffoldPlanRequest(
                        prompt=f"at this path {target} create a C++ console app and build it"
                    )
                )

                self.assertEqual(result.preset.id, "cpp-cmake-cli")
                self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_path_still_stops_at_instruction_connectors(self) -> None:
        target = self.project_root / "workspace" / "Aegis Tool"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} with CMake and validate it"
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue(result.scaffold_request.run_validation)

    def test_prompt_plan_routes_solution_merge_without_swallowing_target_path(self) -> None:
        target = self.project_root / "workspace" / "Solution Tool"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} combine two Visual Studio sln projects "
                    "into one and preserve project references"
                )
            )
        )

        self.assertEqual(result.preset.id, "python-sln-refactor-tool")
        self.assertEqual(result.project_name, "solution-tool")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:solution-refactor", result.detected_keywords)
        self.assertIn("stack-lock:native-cpp", result.detected_keywords)
        self.assertIn("visual studio solution merge/split", result.detected_keywords)
        self.assertNotIn("combine two", result.target_path.lower())

    def test_prompt_plan_routes_solution_split_without_swallowing_target_path(self) -> None:
        target = self.project_root / "workspace" / "Solution Extractor"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} separate one project out of a Visual Studio solution "
                    "into its own project"
                )
            )
        )

        self.assertEqual(result.preset.id, "python-sln-refactor-tool")
        self.assertEqual(result.project_name, "solution-extractor")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:solution-refactor", result.detected_keywords)
        self.assertIn("visual studio solution merge/split", result.detected_keywords)
        self.assertNotIn("separate one project", result.target_path.lower())

    def test_prompt_only_scaffold_infers_cpp_sln_before_writing(self) -> None:
        target = self.project_root / "workspace" / "Roblox"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt=(
                    f"at this path {target} create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing"
                ),
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "scaffold")
        self.assertEqual(result.primary_action, "create_or_update_files")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "python build.py")
        self.assertEqual(result.file_change_count, len(result.files))
        self.assertTrue(any(file.path.endswith(".sln") for file in result.files))
        self.assertTrue((target / "src" / "main.cpp").exists())

    def test_prompt_only_scaffold_build_intent_runs_validation(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        commands = RecordingCommandRunner()
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=commands)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt=(
                    f"at this path {target} create a C++ console project with an sln "
                    "that prints hello world and waits for user input before closing, and also build it"
                ),
                max_repair_attempts=0,
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIsNotNone(result.validation)
        self.assertEqual(commands.commands, ["python build.py"])
        self.assertEqual({stage.id: stage.status for stage in result.stages}.get("validate"), "succeeded")

    def test_prompt_validation_intent_supports_launch_start_execute_language(self) -> None:
        self.assertTrue(ProjectScaffolder._prompt_requests_validation("launch the app"))
        self.assertTrue(ProjectScaffolder._prompt_requests_validation("start the project"))
        self.assertTrue(ProjectScaffolder._prompt_requests_validation("execute it please"))
        self.assertFalse(ProjectScaffolder._prompt_requests_validation("how do I launch it?"))
        self.assertFalse(ProjectScaffolder._prompt_requests_validation("show me how to start it"))

    def test_command_run_extracts_diagnostics_into_scaffold_logs(self) -> None:
        result = CommandResult(
            command="npm run build",
            cwd=str(self.project_root),
            allowed=True,
            exit_code=2,
            stdout="app/page.tsx(7,12): error TS2304: Cannot find name 'AppShell'.\n",
            stderr="",
            timed_out=False,
            reason="Command finished.",
        )

        run = ProjectScaffolder._command_run(result, label="Validation")

        self.assertEqual(len(run.diagnostics), 1)
        diagnostic = run.diagnostics[0]
        self.assertEqual(diagnostic["file"], "app/page.tsx")
        self.assertEqual(diagnostic["line"], 7)
        self.assertEqual(diagnostic["column"], 12)
        self.assertEqual(diagnostic["severity"], "error")
        self.assertEqual(diagnostic["code"], "TS2304")
        self.assertIn("AppShell", diagnostic["message"])

        log_section = ProjectScaffolder._command_log_section("Validation", run)
        self.assertIn("### Diagnostics", log_section)
        self.assertIn("app/page.tsx:7:12 error TS2304", log_section)

        target = self.project_root / "workspace" / "diagnostic-status"
        target.mkdir(parents=True)
        (target / "TODO.md").write_text("- [ ] Build must pass\n", encoding="utf-8")
        ProjectScaffolder._write_instruction_status_checkpoint(
            self.scaffolder,
            target,
            self.workspace.discover_instruction_files(target),
            prompt="build it",
            validation=run,
            validation_command="npm run build",
            build_log_path=".aegis/build_logs/failing.md",
            applied=["app/page.tsx"],
        )
        status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))
        self.assertIn("app/page.tsx:7:12 error TS2304", status["recommendation"])
        self.assertIn("app/page.tsx:7:12 error TS2304", status["completion"]["next_actions"][0])

    def test_prompt_plan_routes_cpp_console_app_without_sln_to_cmake(self) -> None:
        target = self.project_root / "workspace" / "Roblox" / "Test 1"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text("# Aegis C++ Console App\n", encoding="utf-8")
        (target / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
        (target / "src" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this location {target} write me a C++ console app that prints hello world "
                    "and also build it"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.execution_mode, "scaffold")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "python build.py")
        self.assertTrue(result.overwrite)
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("validation is enabled", " ".join(result.assumptions))

    def test_prompt_plan_reuses_existing_manifest_for_followup_build(self) -> None:
        target = self.project_root / "workspace" / "Roblox" / "Test 1"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "roblox-test-one",
                    "preset_id": "cpp-msvc-console-sln",
                    "preset_label": "C++ Visual Studio Console Solution",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "build.py").write_text("print('build ok')\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} build it and fix any errors",
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.project_name, "roblox-test-one")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "python build.py")
        self.assertTrue(result.overwrite)
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("Existing workspace", " ".join(result.assumptions))

    def test_prompt_plan_reuses_existing_build_files_for_failed_build_followup(self) -> None:
        target = self.project_root / "workspace" / "Existing Console"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(ExistingConsole LANGUAGES CXX)\n"
            "add_executable(ExistingConsole src/main.cpp)\n",
            encoding="utf-8",
        )
        (target / "src" / "main.cpp").write_text(
            "#include <iostream>\nint main(){std::cout << \"hello\"; return 0;}\n",
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="continue from the last failed build",
                workspace_root=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("Existing workspace", " ".join(result.assumptions))

    def test_prompt_plan_bare_continue_validates_existing_manifest_project(self) -> None:
        target = self.project_root / "workspace" / "Native Plugin"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "native-plugin",
                    "preset_id": "cpp-cmake-dll",
                    "preset_label": "C++ DLL/Shared Library",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(NativePlugin LANGUAGES CXX)\n"
            "add_library(NativePlugin SHARED src/plugin.cpp)\n",
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="continue",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_prompt_plan_bare_continue_validates_existing_build_files_without_manifest(self) -> None:
        target = self.project_root / "workspace" / "Native No Manifest"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(NativeNoManifest LANGUAGES CXX)\n"
            "add_executable(NativeNoManifest src/main.cpp)\n",
            encoding="utf-8",
        )
        (target / "src" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="keep going and make it production ready",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_prompt_plan_negated_web_ui_followup_preserves_existing_native_stack(self) -> None:
        target = self.project_root / "workspace" / "Native Plugin"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "native-plugin",
                    "preset_id": "cpp-cmake-dll",
                    "preset_label": "C++ DLL/Shared Library",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="add a settings UI but do not turn it into a website",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.execution_mode, "scaffold")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("existing workspace continuity", result.detected_keywords)
        self.assertNotIn("current prompt stack override", result.detected_keywords)
        self.assertNotIn("stack-lock:web", result.detected_keywords)

    def test_prompt_plan_without_making_website_preserves_existing_solution_stack(self) -> None:
        target = self.project_root / "workspace" / "Console Tool"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "console-tool",
                    "preset_id": "cpp-msvc-console-sln",
                    "preset_label": "C++ Visual Studio Console Solution",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "ConsoleTool.sln").write_text(
            "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="add a dashboard to show logs without making a website",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "scaffold")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("existing workspace continuity", result.detected_keywords)
        self.assertNotIn("current prompt stack override", result.detected_keywords)
        self.assertNotIn("stack-lock:web", result.detected_keywords)

    def test_prompt_plan_do_not_make_website_keeps_native_stack_lock_clean(self) -> None:
        target = self.project_root / "workspace" / "Aegis Native DLL"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} refine my existing DLL project, add a diagnostics UI, "
                    "keep it native, build it, and do not make a website."
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:native-library", result.detected_keywords)
        self.assertNotIn("stack-lock:web", result.detected_keywords)
        self.assertNotIn("dependency-free website", result.detected_keywords)

    def test_prompt_plan_accidental_frontend_word_keeps_native_mission_contract(self) -> None:
        target = self.project_root / "workspace" / "Native Diagnostics DLL"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "native-diagnostics-dll",
                    "preset_id": "cpp-cmake-dll",
                    "preset_label": "C++ DLL/Shared Library",
                    "validation_command": "python build.py",
                    "mission_contract": {
                        "schema": "aegis.mission_contract.v1",
                        "preset_id": "cpp-cmake-dll",
                        "stack_family": "native",
                        "stack_locks": ["stack-lock:native-cpp", "stack-lock:native-library"],
                    },
                }
            ),
            encoding="utf-8",
        )
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(NativeDiagnosticsDll LANGUAGES CXX)\n"
            "add_library(NativeDiagnosticsDll SHARED src/plugin.cpp)\n",
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="continue the roadmap and add a frontend-style diagnostics dashboard without changing stacks",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("stack-lock:web", result.detected_keywords)
        self.assertIn("mission-contract:locked-stack", result.detected_keywords)
        self.assertIn("mission-contract:reuse", result.detected_keywords)
        self.assertIn("existing workspace continuity", result.detected_keywords)
        self.assertNotIn("current prompt stack override", result.detected_keywords)

    def test_prompt_plan_mission_contract_preset_is_used_when_manifest_preset_is_missing(self) -> None:
        target = self.project_root / "workspace" / "Manifest Contract Only"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "manifest-contract-only",
                    "preset_id": "",
                    "preset_label": "",
                    "validation_command": "python build.py",
                    "mission_contract": {
                        "schema": "aegis.mission_contract.v1",
                        "preset_id": "cpp-imgui-win32-dx11",
                        "stack_family": "native",
                        "stack_locks": ["stack-lock:native-cpp", "stack-lock:imgui-win32"],
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="continue",
                workspace_root=str(target),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-imgui-win32-dx11")
        self.assertIn("mission-contract:reuse", result.detected_keywords)
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_prompt_plan_current_stack_overrides_stale_web_manifest(self) -> None:
        target = self.project_root / "workspace" / "Aegis Native Plugin"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "old-web-site",
                    "preset_id": "static-html-site",
                    "preset_label": "Static HTML/CSS/JS Website",
                    "validation_command": "node build.js",
                }
            ),
            encoding="utf-8",
        )
        (target / "index.html").write_text("<main>stale web project</main>\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} create a C++ DLL plugin called Aegis Native Plugin "
                    "with a host executable and build it"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("current prompt stack override", result.detected_keywords)
        self.assertNotIn("existing workspace continuity", result.detected_keywords)
        self.assertIn("stack-lock:native-library", result.detected_keywords)
        self.assertTrue(result.scaffold_request.run_validation)

    def test_scaffold_native_request_does_not_emit_web_files_from_stale_manifest(self) -> None:
        target = self.project_root / "workspace" / "Aegis Native Plugin"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "old-web-site",
                    "preset_id": "static-html-site",
                    "preset_label": "Static HTML/CSS/JS Website",
                }
            ),
            encoding="utf-8",
        )
        (target / "package.json").write_text('{"scripts":{"build":"vite build"}}\n', encoding="utf-8")

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt=(
                    f"at this path {target} create a C++ DLL shared library with CMake, "
                    "a host executable, and a validation smoke test"
                ),
                overwrite=True,
                run_validation=False,
            )
        )

        paths = {file.path.replace("\\", "/").lower() for file in result.files}
        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertIn("src/library.cpp", paths)
        self.assertIn("host/main.cpp", paths)
        self.assertIn("cmakelists.txt", paths)
        self.assertNotIn("app/page.tsx", paths)
        self.assertNotIn("src/app.tsx", paths)
        self.assertNotIn("vite.config.ts", paths)
        self.assertNotIn("next.config.mjs", paths)

    def test_prompt_plan_launches_existing_manifest_without_new_scaffold(self) -> None:
        target = self.project_root / "workspace" / "Existing Launch App"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "existing-launch-app",
                    "preset_id": "python-cli",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "build.py").write_text("print('launch ok')\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} launch the app",
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "python build.py")
        self.assertTrue(result.overwrite)
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("Existing workspace", " ".join(result.assumptions))

    def test_prompt_plan_launches_existing_manifest_from_embedded_path(self) -> None:
        target = self.project_root / "workspace" / "Existing Launch App"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "existing-launch-app",
                    "preset_id": "python-cli",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "build.py").write_text("print('launch ok')\n", encoding="utf-8")

        for action in (
            "launch the app",
            "start the project",
            "execute it please",
            "run it please",
            "verify the build",
            "check for errors",
            "ensure there are no errors",
        ):
            with self.subTest(action=action):
                result = self.scaffolder.plan_from_prompt(
                    ProjectScaffoldPlanRequest(
                        prompt=f"at this path {target} {action}",
                    )
                )

                self.assertEqual(result.execution_mode, "existing_validation")
                self.assertEqual(result.primary_action, "validate_existing_project")
                self.assertEqual(result.target_path, str(target.resolve()))
                self.assertEqual(result.validation_command, "python build.py")
                self.assertTrue(result.scaffold_request.run_validation)

    def test_prompt_plan_reuses_existing_electron_project_with_valid_preset_id(self) -> None:
        target = self.project_root / "workspace" / "Existing Electron App"
        target.mkdir(parents=True, exist_ok=True)
        (target / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"build": "electron-vite build"},
                    "dependencies": {"electron": "^30.0.0"},
                    "devDependencies": {"electron-vite": "^2.0.0"},
                }
            ),
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} build it and fix any errors",
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "electron-react-ts")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_desktop_presets_have_desktop_stack_locks(self) -> None:
        for preset_id in ("electron-react-ts", "tauri-react-ts", "python-tkinter-desktop", "dotnet-wpf-csharp"):
            with self.subTest(preset_id=preset_id):
                locks = ProjectScaffolder._preset_stack_locks(preset_id)

                self.assertIn("stack-lock:desktop", locks)
                self.assertEqual(ProjectScaffolder._stack_family_for_preset(preset_id), "desktop")

        self.assertTrue(ProjectScaffolder._stack_locks_conflict_with_preset(["stack-lock:desktop"], "static-html-site"))
        self.assertFalse(
            ProjectScaffolder._stack_locks_conflict_with_preset(
                ["stack-lock:desktop", "stack-lock:web-framework"],
                "electron-react-ts",
            )
        )

    def test_prompt_plan_uses_nonexistent_embedded_path_without_action_suffix(self) -> None:
        target = self.project_root / "workspace" / "New Launch Tool"

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} create a Python CLI called New Launch Tool and build it",
            )
        )

        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue(result.scaffold_request.run_validation)

    def test_prompt_plan_reuses_existing_visual_studio_solution_without_manifest(self) -> None:
        target = self.project_root / "workspace" / "Existing Native"
        target.mkdir(parents=True, exist_ok=True)
        (target / "ExistingNative.sln").write_text(
            "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            encoding="utf-8",
        )
        (target / "ExistingNative.vcxproj").write_text("<Project></Project>\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=f"at this path {target} build it and make sure there are no errors",
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "msbuild ExistingNative.sln /m /p:Configuration=Release")
        self.assertTrue(result.overwrite)
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_prompt_plan_reuses_existing_dll_project_for_refinement(self) -> None:
        target = self.project_root / "workspace" / "Aegis Game Dumper"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "AegisGameDumper.vcxproj").write_text(
            "<Project><PropertyGroup><ConfigurationType>DynamicLibrary</ConfigurationType></PropertyGroup></Project>\n",
            encoding="utf-8",
        )
        (target / "src" / "dllmain.cpp").write_text(
            "#include <windows.h>\nBOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID){return TRUE;}\n",
            encoding="utf-8",
        )

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} work on my existing DLL that I already made "
                    "and refine the native project without turning it into a website"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIn("existing workspace continuity", result.detected_keywords)
        self.assertIn("stack-lock:native-library", result.detected_keywords)
        self.assertNotIn("stack-lock:web", result.detected_keywords)
        self.assertNotIn("dependency-free website", result.detected_keywords)
        self.assertNotIn("web", result.preset.id)
        self.assertIn("DLL/Shared Library", self.workspace.inspect_dependency_profile(target).frameworks)

    def test_prompt_plan_reuses_existing_cmake_project_with_configure_build_command(self) -> None:
        target = self.project_root / "workspace" / "Existing CMake"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(ExistingCMake LANGUAGES CXX)\n"
            "add_executable(ExistingCMake src/main.cpp)\n",
            encoding="utf-8",
        )
        (target / "src" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="you didn't build it, build it and fix any errors",
                workspace_root=str(target),
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(
            result.validation_command,
            "cmake -S . -B build && cmake --build build --config Release",
        )
        self.assertEqual(result.scaffold_request.validation_command, result.validation_command)
        self.assertTrue(result.scaffold_request.run_validation)
        self.assertIn("existing workspace continuity", result.detected_keywords)

    def test_scaffold_followup_build_validates_existing_manifest_without_new_files(self) -> None:
        target = self.project_root / "workspace" / "Roblox" / "Test 1"
        manifest = target / ".aegis" / "project.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "roblox-test-one",
                    "preset_id": "cpp-msvc-console-sln",
                    "validation_command": "python build.py",
                }
            ),
            encoding="utf-8",
        )
        (target / "build.py").write_text("print('build ok')\n", encoding="utf-8")
        commands = RecordingCommandRunner()
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=commands)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt=f"at this path {target} build it and fix any errors",
                max_repair_attempts=0,
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.files, [])
        self.assertEqual(result.file_change_count, 0)
        self.assertEqual(result.applied, [])
        self.assertIsNone(result.checkpoint)
        self.assertEqual(result.validation_command, "python build.py")
        self.assertEqual(commands.commands, ["python build.py"])
        self.assertIn("Validated existing project", result.message)
        self.assertFalse((target / "roblox-test-one.sln").exists())
        self.assertIn("Existing project mode", "\n".join(result.warnings))

    def test_scaffold_followup_build_uses_existing_sln_command_without_manifest(self) -> None:
        target = self.project_root / "workspace" / "Existing Native"
        target.mkdir(parents=True, exist_ok=True)
        (target / "ExistingNative.sln").write_text(
            "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            encoding="utf-8",
        )
        (target / "ExistingNative.vcxproj").write_text("<Project></Project>\n", encoding="utf-8")
        commands = RecordingCommandRunner()
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=commands)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt=f"at this path {target} build it and make sure there are no errors",
                max_repair_attempts=0,
            )
        )

        self.assertEqual(result.preset.id, "cpp-msvc-console-sln")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.files, [])
        self.assertEqual(result.file_change_count, 0)
        self.assertEqual(result.applied, [])
        self.assertEqual(result.validation_command, "msbuild ExistingNative.sln /m /p:Configuration=Release")
        self.assertEqual(commands.commands, ["msbuild ExistingNative.sln /m /p:Configuration=Release"])
        self.assertFalse((target / "existing-native.sln").exists())

    def test_scaffold_followup_build_uses_existing_cmake_configure_chain(self) -> None:
        target = self.project_root / "workspace" / "Existing CMake"
        (target / "src").mkdir(parents=True, exist_ok=True)
        (target / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(ExistingCMake LANGUAGES CXX)\n"
            "add_executable(ExistingCMake src/main.cpp)\n",
            encoding="utf-8",
        )
        (target / "src" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")
        commands = RecordingCommandRunner()
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=commands)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                prompt="you didn't build it, build it and fix any errors",
                max_repair_attempts=0,
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.execution_mode, "existing_validation")
        self.assertEqual(result.primary_action, "validate_existing_project")
        self.assertEqual(result.files, [])
        self.assertEqual(result.applied, [])
        self.assertEqual(
            result.validation_command,
            "cmake -S . -B build && cmake --build build --config Release",
        )
        self.assertEqual(commands.commands, [result.validation_command])
        self.assertFalse((target / "existing-cmake").exists())

    def test_cpp_console_prompt_scaffold_builds_and_runs_validation(self) -> None:
        if shutil.which("cmake") is None:
            self.skipTest("CMake is required for the C++ end-to-end scaffold build smoke test.")

        target = self.project_root / "workspace" / "Roblox" / "Test 1"
        target.mkdir(parents=True, exist_ok=True)
        (target / "server.log").write_text("existing log file should be preserved\n", encoding="utf-8")
        command_runner = CommandRunner(self.settings)
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=command_runner)

        plan = scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this location {target} write me a C++ console app that prints hello world "
                    "to console and requires user input to close the console, and also build it"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(plan.preset.id, "cpp-cmake-cli")
        self.assertEqual(plan.target_path, str(target.resolve()))
        self.assertEqual(plan.validation_command, "python build.py")
        self.assertTrue(plan.scaffold_request.run_validation)

        request = plan.scaffold_request.model_copy(update={"max_repair_attempts": 0})
        result = scaffolder.scaffold(request)

        main_cpp = (target / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertTrue(result.ok)
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertTrue((target / "server.log").exists())
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIsNotNone(result.validation)
        self.assertTrue(result.validation.allowed)
        self.assertEqual(result.validation.exit_code, 0, result.validation.stderr or result.validation.stdout)
        self.assertIn("Hello, world!", result.validation.stdout)
        self.assertIn("Press Enter to close", main_cpp)
        self.assertIn("std::getline(std::cin, line)", main_cpp)
        self.assertEqual(
            {stage.id: stage.status for stage in result.stages}.get("validate"),
            "succeeded",
        )
        profile = self.validation.load_profile(target.resolve())
        self.assertIsNotNone(profile)
        self.assertEqual(profile.command, "python build.py")

    def test_prompt_plan_extracts_cpp_path_before_instruction_text(self) -> None:
        target = self.project_root / "workspace" / "Roblox" / "Test 1"
        target.mkdir(parents=True, exist_ok=True)

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this location {target} write me a C++ console app that prints hello world "
                    "and also build it"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-cli")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.project_name, "test-1")
        self.assertTrue(result.scaffold_request.run_validation)

    def test_prompt_plan_routes_cpp_dll_to_shared_library_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a C++ DLL plugin called Image Filters with exported API functions and a host exe"
            )
        )

        self.assertEqual(result.preset.id, "cpp-cmake-dll")
        self.assertEqual(result.project_name, "image-filters")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("c++ dll/shared library with host loader", result.detected_keywords)

    def test_prompt_plan_routes_imgui_game_loop_and_file_analysis(self) -> None:
        imgui = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a Dear ImGui C++ game editor tool called Level Inspector with asset panels"
            )
        )
        game_loop = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Build a native game loop sandbox called Arena Core with an asset registry and smoke tests"
            )
        )
        analyzer = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a game file analyzer called Game File Analyzer for owned asset bundles, pak files, strings, and entropy"
            )
        )

        self.assertEqual(imgui.preset.id, "cpp-imgui-win32-dx11")
        self.assertEqual(imgui.validation_command, "python build.py")
        self.assertIn("dear imgui game/tooling ui", imgui.detected_keywords)
        self.assertEqual(game_loop.preset.id, "cpp-game-loop-cmake")
        self.assertEqual(game_loop.validation_command, "python build.py")
        self.assertIn("native game loop", game_loop.detected_keywords)
        self.assertEqual(analyzer.preset.id, "python-game-file-analyzer")
        self.assertEqual(analyzer.project_name, "game-file-analyzer")
        self.assertIn("game file/asset analysis", analyzer.detected_keywords)

    def test_prompt_plan_routes_windows_internals_and_solution_refactor_tools(self) -> None:
        internals = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a C++ Windows internals MinHook instrumentation tool for module enumeration"
            )
        )
        sln_tool = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a tool to merge two Visual Studio sln solutions into one and split one project into its own solution"
            )
        )

        self.assertEqual(internals.preset.id, "cpp-windows-internals-hooking")
        self.assertEqual(internals.validation_command, "python build.py")
        self.assertIn("windows internals/instrumentation", internals.detected_keywords)
        self.assertEqual(sln_tool.preset.id, "python-sln-refactor-tool")
        self.assertEqual(sln_tool.project_name, "solution-refactor-tool")
        self.assertEqual(sln_tool.validation_command, "python build.py")
        self.assertIn("visual studio solution merge/split", sln_tool.detected_keywords)

    def test_specialized_native_prompts_do_not_use_generic_target_folder_as_name(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} create a tool to merge two Visual Studio sln "
                    "solutions into one and split one project into its own solution"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "python-sln-refactor-tool")
        self.assertEqual(result.project_name, "solution-refactor-tool")
        self.assertEqual(result.target_path, str(target.resolve()))

    def test_prompt_plan_uses_requested_website_path_without_desktop_bias(self) -> None:
        target = self.project_root / "workspace" / "Desktop" / "Rick Cullers Website"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this location {target} create a barber styled website for me please, "
                    "use whatever language you think is best"
                )
            )
        )

        self.assertEqual(result.preset.id, "static-html-site")
        self.assertEqual(result.project_name, "rick-cullers-website")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "node build.js")
        self.assertIn("dependency-free website", result.detected_keywords)
        self.assertIn("stack-lock:web", result.detected_keywords)

    def test_prompt_plan_trims_requested_path_before_completion_instruction(self) -> None:
        target = self.project_root / "workspace" / "Desktop" / "Rick Cullers Website"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this location {target} complete a full barber styled website "
                    "with booking calls to action"
                )
            )
        )

        self.assertEqual(result.preset.id, "static-html-site")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.project_name, "rick-cullers-website")

    def test_prompt_plan_preferred_website_path_name_wins_with_existing_metadata(self) -> None:
        target = self.project_root / "workspace" / "Desktop" / "Rick Cullers Website"
        (target / ".aegis").mkdir(parents=True, exist_ok=True)
        (target / ".aegis" / "project.json").write_text('{"schema":"aegis.project.v1"}\n', encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="create a barber styled website for me please, use whatever language you think is best",
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "static-html-site")
        self.assertEqual(result.project_name, "rick-cullers-website")
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertEqual(result.validation_command, "node build.js")

    def test_prompt_plan_routes_kernel_driver_to_driver_controller(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        (target / ".aegis").mkdir(parents=True, exist_ok=True)
        (target / ".aegis" / "project.json").write_text('{"schema":"aegis.project.v1"}\n', encoding="utf-8")

        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} please create a kernel driver that uses syscalls as its "
                    "communication, with a desktop app controller that shows how to accept its communication"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "windows-kernel-driver-controller")
        self.assertEqual(result.project_name, "kernel-driver-controller")
        self.assertEqual(result.validation_command, "python build.py")

    def test_prompt_plan_ignores_generic_target_folder_for_kernel_driver(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    f"at this path {target} please create a kernel driver that uses syscalls as its "
                    "communication, with a desktop app controller that shows how to accept its communication"
                ),
                preferred_target_path=str(target),
            )
        )

        self.assertEqual(result.preset.id, "windows-kernel-driver-controller")
        self.assertEqual(result.project_name, "kernel-driver-controller")
        self.assertEqual(result.validation_command, "python build.py")

    def test_prompt_plan_routes_windows_service_to_native_service_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt=(
                    "Create a native Windows service called Log Watcher Service "
                    "with install and uninstall commands plus a console debug mode"
                )
            )
        )

        self.assertEqual(result.preset.id, "cpp-windows-service")
        self.assertEqual(result.project_name, "log-watcher-service")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("windows service", result.detected_keywords)

    def test_prompt_plan_stops_explicit_name_before_stack_phrase(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a full project from scratch called Brown Tracker as a Next.js dashboard app"
            )
        )

        self.assertEqual(result.preset.id, "nextjs-ts-tailwind")
        self.assertEqual(result.project_name, "brown-tracker")

    def test_prompt_plan_routes_mobile_desktop_django_and_rust(self) -> None:
        mobile = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create an Expo React Native mobile app called Field Notes")
        )
        desktop = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Build an Electron React desktop app called Ops Desk")
        )
        django = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create a Django admin panel called Content Hub")
        )
        rust = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Make a Rust CLI called Log Slicer")
        )

        self.assertEqual(mobile.preset.id, "expo-react-native-ts")
        self.assertEqual(desktop.preset.id, "electron-react-ts")
        self.assertEqual(django.preset.id, "django-python-web")
        self.assertEqual(rust.preset.id, "rust-cli")

    def test_prompt_plan_generic_app_does_not_default_to_website(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Build an app called Field Notes")
        )

        self.assertEqual(result.preset.id, "electron-react-ts")
        self.assertEqual(result.project_name, "field-notes")
        self.assertIn("generic application", result.detected_keywords)

    def test_prompt_plan_routes_python_desktop_to_tkinter_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a Python Tkinter desktop utility called Task Pad with local JSON storage"
            )
        )

        self.assertEqual(result.preset.id, "python-tkinter-desktop")
        self.assertEqual(result.project_name, "task-pad")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("python desktop gui", result.detected_keywords)

    def test_dependency_managed_scaffold_auto_installs_before_validation(self) -> None:
        target = self.project_root / "workspace" / "metrics-api"
        command_runner = RecordingCommandRunner()
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=command_runner)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="fastapi-python-api",
                project_name="Metrics API",
                run_validation=True,
            )
        )

        stages = {stage.id: stage for stage in result.stages}
        self.assertEqual(command_runner.commands, ["python -m pip install -e .[dev]", "python -m pytest"])
        self.assertEqual(stages["install"].status, "succeeded")
        self.assertIn("Auto-ran before validation", stages["install"].detail)
        self.assertEqual(stages["validate"].status, "succeeded")
        self.assertEqual(result.validation_command, "python -m pytest")

    def test_prompt_plan_routes_database_to_sqlite_tool(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Build a SQLite database app called Parts Ledger with schema, seed data, CRUD helpers, and reports"
            )
        )

        self.assertEqual(result.preset.id, "sqlite-python-db")
        self.assertEqual(result.project_name, "parts-ledger")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("database project", result.detected_keywords)

    def test_prompt_plan_routes_browser_extension_to_mv3_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a Chrome extension called Tab Scout with a popup, content script, and background service worker"
            )
        )

        self.assertEqual(result.preset.id, "browser-extension-mv3")
        self.assertEqual(result.project_name, "tab-scout")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("browser extension", result.detected_keywords)

    def test_prompt_plan_routes_vscode_extension_to_extension_api_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a VS Code extension called Snippet Runner with commands and a status bar item"
            )
        )

        self.assertEqual(result.preset.id, "vscode-extension-js")
        self.assertEqual(result.project_name, "snippet-runner")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertIn("vs code extension", result.detected_keywords)

    def test_prompt_plan_routes_node_cli_to_node_tool_preset(self) -> None:
        result = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(
                prompt="Create a Node.js CLI tool called Log Formatter with arguments and a package bin entry"
            )
        )

        self.assertEqual(result.preset.id, "node-cli-js")
        self.assertEqual(result.project_name, "log-formatter")
        self.assertEqual(result.validation_command, "node build.js")
        self.assertIn("node cli/tool", result.detected_keywords)

    def test_prompt_plan_routes_go_dotnet_and_tauri(self) -> None:
        go_api = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Build a Go HTTP API called Relay Service")
        )
        dotnet = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create a C# ASP.NET Core Web API called Billing Gateway")
        )
        dotnet_console = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create a C# console exe called Log Cutter with arguments and a self test")
        )
        dotnet_wpf = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Create a C# WPF desktop app called Task Board with a native XAML interface")
        )
        tauri = self.scaffolder.plan_from_prompt(
            ProjectScaffoldPlanRequest(prompt="Make a Tauri React desktop app called Control Deck")
        )

        self.assertEqual(go_api.preset.id, "go-http-api")
        self.assertEqual(dotnet.preset.id, "dotnet-webapi-csharp")
        self.assertEqual(dotnet_console.preset.id, "dotnet-console-csharp")
        self.assertEqual(dotnet_console.project_name, "log-cutter")
        self.assertIn("c# console/exe", dotnet_console.detected_keywords)
        self.assertEqual(dotnet_wpf.preset.id, "dotnet-wpf-csharp")
        self.assertEqual(dotnet_wpf.project_name, "task-board")
        self.assertIn("c# wpf desktop", dotnet_wpf.detected_keywords)
        self.assertEqual(tauri.preset.id, "tauri-react-ts")

    def test_occupied_target_creates_clean_child_without_overwrite(self) -> None:
        target = self.project_root / "workspace" / "existing-app"
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text("existing\n", encoding="utf-8")

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vite-react-ts",
                project_name="Existing App",
                overwrite=False,
            )
        )

        self.assertEqual(result.target_path, str((target / "existing-app").resolve()))
        self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "existing\n")
        self.assertTrue((target / "existing-app" / "package.json").exists())
        self.assertIn("clean child project", "\n".join(result.warnings))

    def test_scaffold_refreshes_only_aegis_metadata_conflicts_without_overwrite(self) -> None:
        target = self.project_root / "workspace" / "metadata-only-app"
        (target / ".aegis").mkdir(parents=True, exist_ok=True)
        (target / ".aegis" / "project.json").write_text('{"schema":"aegis.project.v1"}\n', encoding="utf-8")
        (target / ".aegis" / "ROADMAP.md").write_text("# Old roadmap\n", encoding="utf-8")
        (target / "README.md").write_text("# Old scaffold README\n", encoding="utf-8")
        (target / "AGENTS.md").write_text("# Old handoff\n", encoding="utf-8")
        (target / ".gitignore").write_text("old-build\n", encoding="utf-8")

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-msvc-console-sln",
                project_name="metadata-only-app",
                overwrite=False,
            )
        )

        self.assertTrue(result.ok)
        self.assertTrue((target / "metadata-only-app.sln").exists())
        self.assertTrue((target / "src" / "main.cpp").exists())
        self.assertIn("metadata conflicts", "\n".join(result.warnings))

    def test_occupied_target_reuses_matching_child_project(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text("old root project\n", encoding="utf-8")
        child = target / "kernel-driver-controller"
        first = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(child),
                preset_id="windows-kernel-driver-controller",
                project_name="kernel-driver-controller",
            )
        )

        second = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="windows-kernel-driver-controller",
                project_name="kernel-driver-controller",
            )
        )

        self.assertEqual(first.target_path, second.target_path)
        self.assertEqual(second.target_path, str(child.resolve()))
        self.assertFalse((target / "kernel-driver-controller-2").exists())
        self.assertIn("reused the matching child project", "\n".join(second.warnings))

    def test_scaffold_allows_non_conflicting_files_in_existing_target(self) -> None:
        target = self.project_root / "workspace" / "Roblox"
        target.mkdir(parents=True, exist_ok=True)
        (target / "server.log").write_text("existing log\n", encoding="utf-8")

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-msvc-console-sln",
                project_name="roblox",
                overwrite=False,
            )
        )

        paths = [file.path for file in result.files]
        self.assertIn("roblox.sln", paths)
        self.assertIn("roblox.vcxproj", paths)
        self.assertIn("build.py", paths)
        self.assertIn("src/main.cpp", paths)
        self.assertTrue((target / "server.log").exists())
        self.assertTrue((target / "roblox.sln").exists())
        self.assertTrue((target / "build.py").exists())
        self.assertIn("non-conflicting scaffold files", "\n".join(result.warnings))

    def test_cpp_sln_template_waits_for_enter(self) -> None:
        target = self.project_root / "workspace" / "console-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-msvc-console-sln",
                project_name="Console App",
            )
        )

        main_cpp = (target / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("Hello, world!", main_cpp)
        self.assertIn("Press Enter to close", main_cpp)
        self.assertIn("std::getline(std::cin, line)", main_cpp)
        self.assertIn("MSBUILD_EXE", (target / "build.py").read_text(encoding="utf-8"))
        self.assertIn("console-app.sln", [file.path for file in result.files])

    def test_sqlite_database_template_creates_schema_cli_and_tests(self) -> None:
        target = self.project_root / "workspace" / "parts-ledger"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="sqlite-python-db",
                project_name="Parts Ledger",
            )
        )

        paths = [file.path for file in result.files]
        schema = (target / "schema.sql").read_text(encoding="utf-8")
        cli = (target / "src" / "parts_ledger" / "cli.py").read_text(encoding="utf-8")
        build = (target / "build.py").read_text(encoding="utf-8")
        self.assertTrue(result.ok)
        self.assertIn("inventory_items", schema)
        self.assertIn("inventory_summary", schema)
        self.assertIn("command_validate", cli)
        self.assertIn("unittest", build)
        self.assertIn("schema.sql", paths)
        self.assertIn("seed.sql", paths)
        self.assertIn("queries/report.sql", paths)
        self.assertIn("tests/test_database.py", paths)
        self.assertEqual(result.validation_command, "python build.py")

    def test_cpp_dll_template_exports_functions_and_smoke_test(self) -> None:
        target = self.project_root / "workspace" / "image-filters"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-cmake-dll",
                project_name="Image Filters",
            )
        )

        header = (target / "include" / "image_filters" / "library.h").read_text(encoding="utf-8")
        source = (target / "src" / "library.cpp").read_text(encoding="utf-8")
        host = (target / "host" / "main.cpp").read_text(encoding="utf-8")
        smoke = (target / "tests" / "smoke.cpp").read_text(encoding="utf-8")
        build_script = (target / "build.py").read_text(encoding="utf-8")
        readme = (target / "README.md").read_text(encoding="utf-8")
        project_manifest = json.loads((target / ".aegis" / "project.json").read_text(encoding="utf-8"))
        self.assertTrue(result.ok)
        self.assertIn("IMAGE_FILTERS_API", header)
        self.assertIn("__declspec(dllexport)", header)
        self.assertIn("extern \"C\" IMAGE_FILTERS_API int aegis_add", header)
        self.assertIn("aegis_plugin_version", header)
        self.assertIn("aegis_plugin_description", header)
        self.assertIn("aegis_library_name", source)
        self.assertIn("Aegis generated native DLL/shared-library plugin", source)
        self.assertIn("LoadLibraryA", host)
        self.assertIn("GetProcAddress", host)
        self.assertIn("Host loaded plugin", host)
        self.assertIn("aegis_add(2, 3)", smoke)
        self.assertIn("run_host_validation", build_script)
        self.assertIn("aegis_add(21, 21)=42", build_script)
        self.assertIn("host/main.cpp", readme)
        self.assertIn("CMakeLists.txt", [file.path for file in result.files])
        self.assertIn("host/main.cpp", [file.path for file in result.files])
        self.assertIn("python build.py", result.validation_command)
        self.assertEqual(project_manifest["mission_contract"]["schema"], "aegis.mission_contract.v1")
        self.assertEqual(project_manifest["mission_contract"]["preset_id"], "cpp-cmake-dll")
        self.assertEqual(project_manifest["mission_contract"]["stack_family"], "native")
        self.assertIn("stack-lock:native-library", project_manifest["mission_contract"]["stack_locks"])

    def test_cpp_dll_template_validates_runtime_host_loader(self) -> None:
        target = self.project_root / "workspace" / "runtime-plugin"
        command_runner = CommandRunner(self.settings)
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=command_runner)

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-cmake-dll",
                project_name="Runtime Plugin",
                run_validation=True,
                max_repair_attempts=0,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.exit_code, 0, result.validation.stderr or result.validation.stdout)
        self.assertIn("Host loaded plugin: Runtime Plugin", result.validation.stdout)
        self.assertIn("aegis_add(21, 21)=42", result.validation.stdout)

    def test_static_html_site_scaffold_creates_complete_validated_website(self) -> None:
        target = self.project_root / "workspace" / "rick-cullers-static"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="static-html-site",
                project_name="Rick Cullers Website",
                prompt="Create a barber styled website for Rick Cullers with service cards and booking calls to action.",
            )
        )

        html = (target / "index.html").read_text(encoding="utf-8")
        css = (target / "styles.css").read_text(encoding="utf-8")
        build = (target / "build.js").read_text(encoding="utf-8")
        package = json.loads((target / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(result.ok)
        self.assertTrue((target / "scripts.js").exists())
        self.assertTrue((target / "server.js").exists())
        self.assertIn("Neighborhood barber studio", html)
        self.assertIn("Hot Towel Shave", html)
        self.assertIn("Book a chair", html)
        self.assertIn(".hero-stats", css)
        self.assertIn("'--check', 'scripts.js'", build)
        self.assertEqual(package["scripts"]["validate"], "node build.js")
        self.assertEqual(result.validation_command, "node build.js")

    def test_nextjs_scaffold_creates_files_checkpoint_and_validation_profile(self) -> None:
        target = self.project_root / "workspace" / "next-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="nextjs-ts-tailwind",
                project_name="Aegis Portal",
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.target_path, str(target.resolve()))
        self.assertIsNotNone(result.checkpoint)
        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "AGENTS.md").exists())
        self.assertTrue((target / ".aegis" / "project.json").exists())
        self.assertTrue((target / ".aegis" / "ROADMAP.md").exists())
        self.assertTrue((target / ".aegis" / "instruction_status.json").exists())
        self.assertTrue((target / ".aegis" / "validation_plan.json").exists())
        self.assertTrue((target / "app" / "page.tsx").exists())
        self.assertTrue((target / "components" / "app-shell.tsx").exists())
        self.assertEqual(result.validation_command, "npm run build")
        self.assertTrue(result.plan_steps)
        self.assertIn(".aegis/decisions.md", result.memory_paths)
        self.assertIn(".aegis/validation_plan.json", result.memory_paths)
        manifest = json.loads((target / ".aegis" / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "aegis.project.v1")
        self.assertEqual(manifest["preset_id"], "nextjs-ts-tailwind")
        self.assertEqual(manifest["validation_command"], "npm run build")
        decisions = (target / ".aegis" / "decisions.md").read_text(encoding="utf-8")
        self.assertIn("Aegis Project Decisions", decisions)
        file_index = json.loads((target / ".aegis" / "file_index.json").read_text(encoding="utf-8"))
        self.assertEqual(file_index["schema"], "aegis.file_index.v1")
        self.assertGreaterEqual(file_index["workspace_file_count"], 1)
        instruction_status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))
        self.assertEqual(instruction_status["schema"], "aegis.instruction_status.v1")
        self.assertGreaterEqual(instruction_status["open_items"], 1)
        self.assertGreaterEqual(instruction_status["instruction_file_count"], 1)
        self.assertEqual(instruction_status["last_validation"]["status"], "saved")
        self.assertIn("Continue the next open instruction item", instruction_status["recommendation"])
        self.assertNotIn("Preset:", instruction_status["recommendation"])
        self.assertIn(".aegis/ROADMAP.md", [item["path"] for item in instruction_status["files"]])
        validation_plan = json.loads((target / ".aegis" / "validation_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(validation_plan["schema"], "aegis.validation_plan.v1")
        self.assertEqual(validation_plan["validation_command"], "npm run build")
        self.assertEqual(validation_plan["last_run"]["status"], "not_run")
        self.assertIn("npm run build", [step["command"] for step in validation_plan["steps"]])
        profile = self.validation.load_profile(target.resolve())
        self.assertIsNotNone(profile)
        self.assertEqual(profile.command, "npm run build")
        self.assertIn("package.json", [file.path for file in result.workspace_files])
        stage_statuses = {stage.id: stage.status for stage in result.stages}
        self.assertEqual(stage_statuses["apply"], "succeeded")
        self.assertEqual(stage_statuses["memory"], "succeeded")
        self.assertEqual(stage_statuses["validate"], "skipped")

    def test_nextjs_scaffold_specializes_barber_website_copy_from_prompt(self) -> None:
        target = self.project_root / "workspace" / "rick-cullers"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="nextjs-ts-tailwind",
                project_name="Rick Cullers Website",
                prompt="Create a barber styled website for Rick Cullers with service cards and booking calls to action.",
            )
        )

        app_shell = (target / "components" / "app-shell.tsx").read_text(encoding="utf-8")
        layout = (target / "app" / "layout.tsx").read_text(encoding="utf-8")
        self.assertTrue(result.ok)
        self.assertIn("Neighborhood barber studio", app_shell)
        self.assertIn("Hot Towel Shave", app_shell)
        self.assertIn("Book a chair", app_shell)
        self.assertIn("import type { ReactNode } from \"react\";", layout)
        self.assertGreater(len(app_shell), 6500)

    def test_barber_scaffold_writes_stack_aware_autopilot_checklist(self) -> None:
        target = self.project_root / "workspace" / "rick-cullers-checklist"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="static-html-site",
                project_name="Rick Cullers Website",
                prompt="Create a barber styled website for Rick Cullers with a polished appointment flow.",
            )
        )

        self.assertTrue(result.ok)
        roadmap = (target / ".aegis" / "ROADMAP.md").read_text(encoding="utf-8")
        project = json.loads((target / ".aegis" / "project.json").read_text(encoding="utf-8"))
        instruction_status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))

        self.assertIn("- [ ] Turn the first screen into a complete barber landing flow", roadmap)
        self.assertIn("- [ ] Wire the booking/contact interaction", roadmap)
        self.assertIn("barber landing flow", project["agent_handoff"]["first_pass"][0])
        self.assertIn("Continue the next open instruction item: Turn the first screen into a complete barber landing flow", instruction_status["recommendation"])

    def test_cmake_scaffold_instruction_status_ignores_stack_metadata(self) -> None:
        target = self.project_root / "workspace" / "cmake-metadata-filter"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-cmake-cli",
                project_name="CMake Metadata Filter",
                validation_command="cmake -S . -B build && cmake --build build",
            )
        )

        self.assertTrue(result.ok)
        instruction_status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))
        pending_text = "\n".join(
            pending
            for file in instruction_status["files"]
            for pending in file.get("pending_items", [])
        )
        self.assertNotIn("Preset:", pending_text)
        self.assertNotIn("Framework:", pending_text)
        self.assertNotIn("Package manager:", pending_text)
        self.assertNotIn("CMake CLI", instruction_status["recommendation"])
        validation_plan = json.loads((target / ".aegis" / "validation_plan.json").read_text(encoding="utf-8"))
        self.assertEqual([step["phase"] for step in validation_plan["steps"]], ["configure", "build"])
        self.assertEqual([step["command"] for step in validation_plan["steps"]], ["cmake -S . -B build", "cmake --build build"])

    def test_cpp_console_scaffold_writes_console_build_autopilot_checklist(self) -> None:
        target = self.project_root / "workspace" / "cpp-console-checklist"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-cmake-cli",
                project_name="Hello Console",
                prompt="Create a C++ console app that prints hello world and waits for Enter.",
            )
        )

        self.assertTrue(result.ok)
        roadmap = (target / ".aegis" / "ROADMAP.md").read_text(encoding="utf-8")
        project = json.loads((target / ".aegis" / "project.json").read_text(encoding="utf-8"))
        instruction_status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))

        self.assertIn("- [ ] Complete the requested command-line behavior", roadmap)
        self.assertIn("- [ ] Add or update the build/self-test script", roadmap)
        self.assertIn("command-line behavior", project["agent_handoff"]["first_pass"][0])
        self.assertIn("Complete the requested command-line behavior", instruction_status["recommendation"])

    def test_vite_scaffold_specializes_barber_website_copy_from_prompt(self) -> None:
        target = self.project_root / "workspace" / "vite-barber"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vite-react-ts",
                project_name="Rick Cullers Website",
                prompt="Create a barber styled website for Rick Cullers with a polished appointment flow.",
            )
        )

        app = (target / "src" / "App.tsx").read_text(encoding="utf-8")
        styles = (target / "src" / "styles.css").read_text(encoding="utf-8")
        self.assertTrue(result.ok)
        self.assertIn("Skin Fade", app)
        self.assertIn("Book a chair", app)
        self.assertIn(".services", styles)
        self.assertGreater(len(app), 3000)

    def test_scaffold_can_run_validation_and_capture_output(self) -> None:
        target = self.project_root / "workspace" / "validated-app"
        scaffolder = ProjectScaffolder(
            self.workspace,
            self.validation,
            commands=CommandRunner(self.settings),
            sandbox_profile="standard",
        )

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="python-cli",
                project_name="Validated Tool",
                prompt="Create a Python CLI called Validated Tool",
                validation_command="python -c \"print('project ok')\"",
                run_validation=True,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.exit_code, 0)
        self.assertIn("project ok", result.validation.stdout)
        self.assertTrue(result.build_log_path.startswith(".aegis/build_logs/"))
        build_log = (target / result.build_log_path).read_text(encoding="utf-8")
        self.assertIn("Aegis Build Log", build_log)
        self.assertIn("python -c \"print('project ok')\"", build_log)
        self.assertIn("project ok", build_log)
        command_history = json.loads((target / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        self.assertTrue(any(command.get("status") == "passed" for command in command_history["commands"]))
        self.assertTrue(any(command.get("build_log_path") == result.build_log_path for command in command_history["commands"]))
        instruction_status = json.loads((target / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))
        self.assertEqual(instruction_status["last_validation"]["status"], "passed")
        self.assertEqual(instruction_status["last_validation"]["build_log_path"], result.build_log_path)
        self.assertEqual(instruction_status["completion"]["status"], "needs_work")
        self.assertTrue(instruction_status["completion"]["should_continue"])
        validation_plan = json.loads((target / ".aegis" / "validation_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(validation_plan["last_run"]["status"], "passed")
        self.assertEqual(validation_plan["last_run"]["build_log_path"], result.build_log_path)
        self.assertIn("python -c", validation_plan["steps"][-1]["command"])
        self.assertIn("project ok", validation_plan["steps"][-1]["command"])
        stage_statuses = {stage.id: stage.status for stage in result.stages}
        self.assertEqual(stage_statuses["validate"], "succeeded")
        self.assertEqual(stage_statuses["build-log"], "succeeded")
        roadmap = (target / ".aegis" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("Create a Python CLI called Validated Tool", roadmap)

    def test_project_memory_json_reader_accepts_utf8_bom(self) -> None:
        path = self.project_root / "workspace" / "bom" / ".aegis" / "command_history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\ufeff{"schema":"aegis.command_history.v1","commands":[]}', encoding="utf-8")

        payload = ProjectScaffolder._read_json_object(path, default={})

        self.assertEqual(payload["schema"], "aegis.command_history.v1")

    def test_validation_plan_splits_safe_native_build_chain(self) -> None:
        preset = ProjectScaffolder._preset_for("cpp-cmake-cli")

        payload = ProjectScaffolder._validation_plan_payload(
            preset,
            "Native Tool",
            install_command="",
            validation_command="cmake -S . -B build && cmake --build build",
            validation=None,
            build_log_path="",
        )

        self.assertEqual([step["command"] for step in payload["steps"]], ["cmake -S . -B build", "cmake --build build"])
        self.assertEqual([step["phase"] for step in payload["steps"]], ["configure", "build"])
        self.assertEqual([step["id"] for step in payload["steps"]], ["configure-1", "build-2"])
        self.assertEqual(payload["steps"][0]["label"], "Configure CMake build directory")
        self.assertEqual(payload["steps"][1]["label"], "Build CMake project")

    def test_validation_plan_preserves_quoted_windows_chain_commands(self) -> None:
        preset = ProjectScaffolder._preset_for("cpp-cmake-cli")
        command = '"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build && "C:\\Program Files\\CMake\\bin\\cmake.exe" --build build'

        payload = ProjectScaffolder._validation_plan_payload(
            preset,
            "Native Tool",
            install_command="",
            validation_command=command,
            validation=None,
            build_log_path="",
        )

        self.assertEqual(
            [step["command"] for step in payload["steps"]],
            [
                '"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build',
                '"C:\\Program Files\\CMake\\bin\\cmake.exe" --build build',
            ],
        )
        self.assertEqual([step["phase"] for step in payload["steps"]], ["configure", "build"])
        self.assertEqual(payload["steps"][0]["source_command"], command)

    def test_validation_plan_keeps_unsafe_or_malformed_chains_single_step(self) -> None:
        cases = [
            "python build.py | more && python smoke.py",
            "python build.py & python smoke.py",
            "python build.py &&",
            '"python build.py && python smoke.py',
        ]

        for command in cases:
            with self.subTest(command=command):
                self.assertEqual(ProjectScaffolder._split_safe_command_chain(command), [command])

    def test_fresh_node_scaffold_installs_before_validation(self) -> None:
        target = self.project_root / "workspace" / "fresh-web"
        scaffolder = ProjectScaffolder(
            self.workspace,
            self.validation,
            commands=CommandRunner(self.settings),
            sandbox_profile="standard",
        )

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vite-react-ts",
                project_name="Fresh Web",
                install_command="python -c \"print('install ok')\"",
                validation_command="python -c \"print('build ok')\"",
                run_validation=True,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.exit_code, 0)
        self.assertIn("build ok", result.validation.stdout)
        build_log = (target / result.build_log_path).read_text(encoding="utf-8")
        self.assertIn("Install", build_log)
        self.assertIn("install ok", build_log)
        self.assertIn("Validation", build_log)
        self.assertIn("build ok", build_log)
        stages = {stage.id: stage for stage in result.stages}
        self.assertEqual(stages["install"].status, "succeeded")
        self.assertIn("Auto-ran before validation", stages["install"].detail)

    def test_validation_failure_is_recorded_as_known_error(self) -> None:
        target = self.project_root / "workspace" / "failing-app"
        scaffolder = ProjectScaffolder(
            self.workspace,
            self.validation,
            commands=CommandRunner(self.settings),
            sandbox_profile="standard",
        )

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="python-cli",
                project_name="Failing Tool",
                validation_command="python -c \"import sys; sys.exit(2)\"",
                run_validation=True,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.exit_code, 2)
        known_errors = json.loads((target / ".aegis" / "known_errors.json").read_text(encoding="utf-8"))
        self.assertEqual(known_errors["schema"], "aegis.known_errors.v1")
        self.assertEqual(known_errors["errors"][0]["status"], "open")
        self.assertEqual(known_errors["errors"][0]["category"], "unknown")
        self.assertEqual(known_errors["errors"][0]["build_log_path"], result.build_log_path)
        build_log = (target / result.build_log_path).read_text(encoding="utf-8")
        self.assertIn("Exit code: 2", build_log)
        self.assertIn("Run build/test validation failed", build_log)

    def test_overwrite_updates_only_scaffold_owned_files(self) -> None:
        target = self.project_root / "workspace" / "vite-app"
        first = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(target), preset_id="vite-react-ts", project_name="Vite App")
        )
        custom = target / "notes.txt"
        custom.write_text("keep me\n", encoding="utf-8")

        second = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vite-react-ts",
                project_name="Vite App",
                overwrite=True,
            )
        )

        self.assertIsNotNone(first.checkpoint)
        self.assertIsNotNone(second.checkpoint)
        self.assertTrue(custom.exists())
        self.assertIn("keep me", custom.read_text(encoding="utf-8"))
        self.assertTrue(any(file.action == "update" for file in second.files))

    def test_python_cli_scaffold_uses_safe_package_name(self) -> None:
        target = self.project_root / "workspace" / "python-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(target), preset_id="python-cli", project_name="123 My Tool")
        )

        self.assertEqual(result.install_command, "python -m pip install -e .[dev]")
        self.assertEqual(result.validation_command, "python build.py")
        self.assertTrue((target / "src" / "app_123_my_tool" / "main.py").exists())
        self.assertTrue((target / "tests" / "test_smoke.py").exists())
        self.assertTrue((target / "build.py").exists())
        self.assertIn('name = "aegis-123-my-tool"', (target / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.validation.load_profile(target.resolve()).command, "python build.py")

    def test_scaffold_manifest_names_are_safe_for_human_project_titles(self) -> None:
        project_name = "123 Rick Cullers Website"
        expected_name = "aegis-123-rick-cullers-website"
        cases = [
            ("nextjs-ts-tailwind", "package.json", "json-name"),
            ("vite-react-ts", "package.json", "json-name"),
            ("express-ts-api", "package.json", "json-name"),
            ("electron-react-ts", "package.json", "json-name"),
            ("expo-react-native-ts", "package.json", "json-name"),
            ("tauri-react-ts", "package.json", "json-name"),
            ("python-stdlib-api", "pyproject.toml", "python-project-name"),
            ("python-cli", "pyproject.toml", "python-project-name"),
            ("python-tkinter-desktop", "pyproject.toml", "python-project-name"),
            ("fastapi-python-api", "pyproject.toml", "python-project-name"),
            ("rust-cli", "Cargo.toml", "cargo-package-name"),
            ("tauri-react-ts", "src-tauri/Cargo.toml", "cargo-package-name"),
            ("go-http-api", "go.mod", "go-module-name"),
        ]

        for preset_id, manifest_path, manifest_type in cases:
            with self.subTest(preset_id=preset_id, manifest_path=manifest_path):
                target = self.project_root / "workspace" / "manifest-names" / preset_id
                self.scaffolder.scaffold(
                    ProjectScaffoldRequest(
                        target_path=str(target),
                        preset_id=preset_id,
                        project_name=project_name,
                    )
                )

                manifest = (target / manifest_path).read_text(encoding="utf-8")
                if manifest_type == "json-name":
                    self.assertEqual(json.loads(manifest)["name"], expected_name)
                elif manifest_type in {"python-project-name", "cargo-package-name"}:
                    self.assertIn(f'name = "{expected_name}"', manifest)
                else:
                    self.assertIn(f"module example.com/{expected_name}", manifest)

    def test_python_cli_default_validation_runs_without_pytest_install(self) -> None:
        target = self.project_root / "workspace" / "python-cli-validated"
        scaffolder = ProjectScaffolder(
            self.workspace,
            self.validation,
            commands=CommandRunner(self.settings),
            sandbox_profile="standard",
        )

        result = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="python-cli",
                project_name="Report Tool",
                run_validation=True,
            )
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.command, "python build.py")
        self.assertEqual(result.validation.exit_code, 0)
        self.assertIn("Python CLI scaffold passed validation", result.validation.stdout)

    def test_fastapi_and_cpp_presets_create_expected_entrypoints(self) -> None:
        api_target = self.project_root / "workspace" / "api-app"
        cpp_target = self.project_root / "workspace" / "cpp-app"

        api_result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(api_target), preset_id="fastapi-python-api", project_name="Aegis API")
        )
        cpp_result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(cpp_target), preset_id="cpp-cmake-cli", project_name="Aegis Native")
        )

        self.assertTrue((api_target / "src" / "aegis_api" / "main.py").exists())
        self.assertTrue((api_target / "tests" / "test_health.py").exists())
        self.assertEqual(api_result.validation_command, "python -m pytest")
        self.assertTrue((cpp_target / "CMakeLists.txt").exists())
        self.assertTrue((cpp_target / "src" / "main.cpp").exists())
        self.assertTrue((cpp_target / "build.py").exists())
        cpp_build = (cpp_target / "build.py").read_text(encoding="utf-8")
        cpp_main = (cpp_target / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("ctest", cpp_build)
        self.assertIn("run_generated_app", cpp_build)
        self.assertIn('APP_NAME = "aegis_native"', cpp_build)
        self.assertIn('names = {APP_NAME, APP_NAME + ".exe"}', cpp_build)
        self.assertNotIn("{native_name}", cpp_build)
        self.assertNotIn("{{APP_NAME", cpp_build)
        self.assertIn("Hello, world!", cpp_main)
        self.assertEqual(cpp_result.validation_command, "python build.py")

    def test_python_tkinter_desktop_scaffold_creates_gui_state_and_tests(self) -> None:
        target = self.project_root / "workspace" / "tkinter-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="python-tkinter-desktop",
                project_name="Task Pad",
            )
        )

        self.assertTrue((target / "src" / "task_pad" / "app.py").exists())
        self.assertTrue((target / "src" / "task_pad" / "state.py").exists())
        self.assertTrue((target / "src" / "task_pad" / "main.py").exists())
        self.assertTrue((target / "tests" / "test_state.py").exists())
        self.assertTrue((target / "build.py").exists())
        self.assertIn("tkinter", (target / "src" / "task_pad" / "app.py").read_text(encoding="utf-8"))
        self.assertIn("compileall", (target / "build.py").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_windows_kernel_driver_controller_creates_driver_and_controller(self) -> None:
        target = self.project_root / "workspace" / "driver-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="windows-kernel-driver-controller",
                project_name="Kernel Bridge",
            )
        )

        self.assertTrue((target / "kernel-bridge.sln").exists())
        self.assertTrue((target / "driver" / "public.h").exists())
        self.assertTrue((target / "driver" / "driver.c").exists())
        self.assertTrue((target / "controller" / "main.cpp").exists())
        self.assertIn("DeviceIoControl", (target / "controller" / "main.cpp").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_cpp_visual_studio_console_validation_runs_built_executable(self) -> None:
        target = self.project_root / "workspace" / "sln-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-msvc-console-sln",
                project_name="Hello Console",
            )
        )

        build_script = (target / "build.py").read_text(encoding="utf-8")
        self.assertTrue((target / "hello-console.sln").exists())
        self.assertIn('input="\\n"', build_script)
        self.assertIn("Hello, world!", build_script)
        self.assertEqual(result.validation_command, "python build.py")

    def test_windows_service_scaffold_creates_service_entrypoint_and_smoke_tests(self) -> None:
        target = self.project_root / "workspace" / "service-app"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="cpp-windows-service",
                project_name="Log Watcher Service",
            )
        )

        self.assertTrue((target / "CMakeLists.txt").exists())
        self.assertTrue((target / "src" / "service_main.cpp").exists())
        self.assertTrue((target / "src" / "service_core.cpp").exists())
        self.assertTrue((target / "include" / "log_watcher_service" / "service_core.h").exists())
        self.assertTrue((target / "tests" / "smoke.cpp").exists())
        service_main = (target / "src" / "service_main.cpp").read_text(encoding="utf-8")
        self.assertIn("StartServiceCtrlDispatcherW", service_main)
        self.assertIn("--install", service_main)
        self.assertIn("--uninstall", service_main)
        self.assertEqual(result.validation_command, "python build.py")

    def test_game_development_presets_create_expected_entrypoints(self) -> None:
        imgui_target = self.project_root / "workspace" / "imgui-tool"
        game_target = self.project_root / "workspace" / "game-loop"
        analyzer_target = self.project_root / "workspace" / "asset-analyzer"
        command_runner = CommandRunner(self.settings)
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=command_runner)

        imgui = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(imgui_target),
                preset_id="cpp-imgui-win32-dx11",
                project_name="Level Inspector",
            )
        )
        game_loop = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(game_target),
                preset_id="cpp-game-loop-cmake",
                project_name="Arena Core",
            )
        )
        analyzer = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(analyzer_target),
                preset_id="python-game-file-analyzer",
                project_name="Game File Analyzer",
                run_validation=True,
            )
        )

        self.assertTrue((imgui_target / "src" / "app_state.cpp").exists())
        self.assertTrue((imgui_target / "vendor" / "imgui_shim" / "imgui.h").exists())
        self.assertIn("render_editor_panels", (imgui_target / "src" / "app_state.cpp").read_text(encoding="utf-8"))
        self.assertEqual(imgui.validation_command, "python build.py")
        self.assertTrue((game_target / "include" / "arena_core" / "engine.h").exists())
        self.assertTrue((game_target / "src" / "engine.cpp").exists())
        self.assertTrue((game_target / "tests" / "smoke.cpp").exists())
        self.assertIn("FixedStepSimulation", (game_target / "src" / "engine.cpp").read_text(encoding="utf-8"))
        self.assertEqual(game_loop.validation_command, "python build.py")
        self.assertTrue((analyzer_target / "game_file_analyzer" / "analyzer.py").exists())
        self.assertTrue((analyzer_target / "game_file_analyzer" / "cli.py").exists())
        self.assertTrue((analyzer_target / "samples" / "sample_asset.bin").exists())
        self.assertIsNotNone(analyzer.validation)
        self.assertEqual(analyzer.validation.exit_code, 0, analyzer.validation.stderr or analyzer.validation.stdout)
        self.assertIn("Game file analyzer validation passed", analyzer.validation.stdout)

    def test_windows_internals_and_solution_refactor_presets_validate(self) -> None:
        internals_target = self.project_root / "workspace" / "internals-tool"
        sln_target = self.project_root / "workspace" / "sln-tool"
        command_runner = CommandRunner(self.settings)
        scaffolder = ProjectScaffolder(self.workspace, self.validation, commands=command_runner)

        internals = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(internals_target),
                preset_id="cpp-windows-internals-hooking",
                project_name="Internals Hook Lab",
                run_validation=True,
                max_repair_attempts=0,
            )
        )
        sln_tool = scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(sln_target),
                preset_id="python-sln-refactor-tool",
                project_name="Solution Surgeon",
                run_validation=True,
                max_repair_attempts=0,
            )
        )

        self.assertTrue((internals_target / "src" / "instrumentation.cpp").exists())
        minhook_adapter = internals_target / "include" / "internals_hook_lab" / "minhook_adapter.h"
        minhook_shim = internals_target / "vendor" / "minhook_shim" / "MinHook.h"
        self.assertTrue(minhook_adapter.exists())
        self.assertTrue(minhook_shim.exists())
        self.assertIn("install_preview", minhook_adapter.read_text(encoding="utf-8"))
        self.assertIn("MH_CreateHook", minhook_adapter.read_text(encoding="utf-8"))
        self.assertIn("MH_CreateHook", minhook_shim.read_text(encoding="utf-8"))
        self.assertIn("official MinHook", (internals_target / "README.md").read_text(encoding="utf-8"))
        self.assertIsNotNone(internals.validation)
        self.assertEqual(internals.validation.exit_code, 0, internals.validation.stderr or internals.validation.stdout)
        self.assertIn("Windows internals tool", internals.validation.stdout)
        self.assertIn("Hook preview=Hook preview validated through MinHook-compatible API boundary.", internals.validation.stdout)
        self.assertTrue((sln_target / "solution_surgeon" / "sln.py").exists())
        self.assertTrue((sln_target / "samples" / "AppOne.sln").exists())
        sln_source = (sln_target / "solution_surgeon" / "sln.py").read_text(encoding="utf-8")
        sln_cli = (sln_target / "solution_surgeon" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("materialize_merge", sln_source)
        self.assertIn("materialize_split", sln_source)
        self.assertIn("analyze_vcxproj", sln_source)
        self.assertIn("analyze_workspace", sln_source)
        self.assertIn("build_solution_graph", sln_source)
        self.assertIn("build_order", sln_source)
        self.assertIn("copy_projects", sln_source)
        self.assertIn("--copy-projects", sln_cli)
        self.assertIn("--include-references", sln_cli)
        self.assertIn('sub.add_parser("analyze")', sln_cli)
        self.assertIn('sub.add_parser("graph")', sln_cli)
        self.assertIn('sub.add_parser("build-order")', sln_cli)
        self.assertTrue((sln_target / "samples" / "AppOne" / "AppOne.vcxproj").exists())
        self.assertTrue((sln_target / "samples" / "Shared" / "Shared.vcxproj").exists())
        self.assertTrue((sln_target / "samples" / "AppTwo" / "AppTwo.vcxproj").exists())
        self.assertIn("d3d11.lib", (sln_target / "samples" / "AppOne" / "AppOne.vcxproj").read_text(encoding="utf-8"))
        self.assertIn("ProjectReference", (sln_target / "samples" / "AppOne" / "AppOne.vcxproj").read_text(encoding="utf-8"))
        self.assertIsNotNone(sln_tool.validation)
        self.assertEqual(sln_tool.validation.exit_code, 0, sln_tool.validation.stderr or sln_tool.validation.stdout)
        self.assertIn("Visual Studio solution refactor validation passed", sln_tool.validation.stdout)
        self.assertTrue((sln_target / "merged" / "AppOne" / "AppOne.vcxproj").exists())
        self.assertTrue((sln_target / "merged" / "Shared" / "Shared.vcxproj").exists())
        self.assertTrue((sln_target / "merged" / "AppTwo" / "AppTwo.vcxproj").exists())
        self.assertTrue((sln_target / "split" / "Shared" / "Shared.vcxproj").exists())
        self.assertTrue((sln_target / "split" / "AppTwo" / "AppTwo.vcxproj").exists())

    def test_new_platform_presets_create_expected_entrypoints(self) -> None:
        electron_target = self.project_root / "workspace" / "electron-app"
        mobile_target = self.project_root / "workspace" / "mobile-app"
        django_target = self.project_root / "workspace" / "django-app"
        rust_target = self.project_root / "workspace" / "rust-app"

        electron = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(electron_target), preset_id="electron-react-ts", project_name="Ops Desk")
        )
        mobile = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(mobile_target), preset_id="expo-react-native-ts", project_name="Field Notes")
        )
        django = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(django_target), preset_id="django-python-web", project_name="Content Hub")
        )
        rust = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(rust_target), preset_id="rust-cli", project_name="Log Slicer")
        )

        self.assertTrue((electron_target / "src" / "main" / "index.ts").exists())
        self.assertEqual(electron.validation_command, "npm run build")
        electron_package = json.loads((electron_target / "package.json").read_text(encoding="utf-8"))
        electron_html = (electron_target / "src" / "renderer" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(electron_package["devDependencies"]["electron-vite"], "^5.0.0")
        self.assertIn("@swc/core", electron_package["devDependencies"])
        self.assertIn('src="/src/main.tsx"', electron_html)
        self.assertNotIn("/src/renderer/src/main.tsx", electron_html)
        self.assertTrue((mobile_target / "App.tsx").exists())
        self.assertEqual(mobile.validation_command, "npm run typecheck")
        self.assertTrue((django_target / "manage.py").exists())
        self.assertTrue((django_target / "core" / "views.py").exists())
        self.assertEqual(django.validation_command, "python manage.py test")
        self.assertTrue((rust_target / "Cargo.toml").exists())
        self.assertTrue((rust_target / "src" / "main.rs").exists())
        self.assertEqual(rust.validation_command, "cargo test")

    def test_go_dotnet_and_tauri_presets_create_expected_entrypoints(self) -> None:
        go_target = self.project_root / "workspace" / "go-api"
        dotnet_target = self.project_root / "workspace" / "dotnet-api"
        tauri_target = self.project_root / "workspace" / "tauri-app"

        go_api = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(go_target), preset_id="go-http-api", project_name="Relay Service")
        )
        dotnet = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(dotnet_target), preset_id="dotnet-webapi-csharp", project_name="Billing Gateway")
        )
        tauri = self.scaffolder.scaffold(
            ProjectScaffoldRequest(target_path=str(tauri_target), preset_id="tauri-react-ts", project_name="Control Deck")
        )

        self.assertTrue((go_target / "go.mod").exists())
        self.assertTrue((go_target / "cmd" / "server" / "main.go").exists())
        self.assertEqual(go_api.validation_command, "go test ./...")
        self.assertTrue((dotnet_target / "src" / "BillingGateway.Api" / "Program.cs").exists())
        self.assertTrue((dotnet_target / "tests" / "BillingGateway.Tests" / "HealthTests.cs").exists())
        self.assertEqual(dotnet.validation_command, "dotnet test")
        self.assertTrue((tauri_target / "src-tauri" / "tauri.conf.json").exists())
        self.assertTrue((tauri_target / "src" / "App.tsx").exists())
        self.assertEqual(tauri.validation_command, "npm run build")

    def test_dotnet_console_scaffold_creates_exe_entrypoint_and_self_test(self) -> None:
        target = self.project_root / "workspace" / "dotnet-console"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="dotnet-console-csharp",
                project_name="Log Cutter",
            )
        )

        self.assertTrue((target / "src" / "LogCutter" / "LogCutter.csproj").exists())
        self.assertTrue((target / "src" / "LogCutter" / "Program.cs").exists())
        self.assertTrue((target / "src" / "LogCutter" / "ToolEngine.cs").exists())
        self.assertTrue((target / "build.py").exists())
        tool_engine = (target / "src" / "LogCutter" / "ToolEngine.cs").read_text(encoding="utf-8")
        self.assertIn("--self-test", tool_engine)
        self.assertIn("BuildOutput", tool_engine)
        self.assertIn("dotnet", (target / "build.py").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_dotnet_wpf_scaffold_creates_xaml_app_and_smoke_project(self) -> None:
        target = self.project_root / "workspace" / "dotnet-wpf"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="dotnet-wpf-csharp",
                project_name="Task Board",
            )
        )

        self.assertTrue((target / "src" / "TaskBoard" / "TaskBoard.csproj").exists())
        self.assertTrue((target / "src" / "TaskBoard" / "App.xaml").exists())
        self.assertTrue((target / "src" / "TaskBoard" / "MainWindow.xaml").exists())
        self.assertTrue((target / "src" / "TaskBoard" / "DashboardState.cs").exists())
        self.assertTrue((target / "tests" / "TaskBoard.Smoke" / "TaskBoard.Smoke.csproj").exists())
        self.assertTrue((target / "build.py").exists())
        self.assertIn("<UseWPF>true</UseWPF>", (target / "src" / "TaskBoard" / "TaskBoard.csproj").read_text(encoding="utf-8"))
        self.assertIn("DashboardState", (target / "tests" / "TaskBoard.Smoke" / "Program.cs").read_text(encoding="utf-8"))
        self.assertIn("dotnet", (target / "build.py").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_browser_extension_scaffold_creates_manifest_popup_and_validation(self) -> None:
        target = self.project_root / "workspace" / "browser-extension"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="browser-extension-mv3",
                project_name="Tab Scout",
            )
        )

        self.assertTrue((target / "manifest.json").exists())
        self.assertTrue((target / "src" / "background.js").exists())
        self.assertTrue((target / "src" / "content.js").exists())
        self.assertTrue((target / "popup" / "popup.html").exists())
        self.assertTrue((target / "popup" / "popup.js").exists())
        self.assertTrue((target / "options" / "options.html").exists())
        self.assertTrue((target / "build.py").exists())
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["action"]["default_popup"], "popup/popup.html")
        self.assertEqual(manifest["background"]["service_worker"], "src/background.js")
        self.assertIn("validate_manifest", (target / "build.py").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_vscode_extension_scaffold_creates_package_commands_and_validation(self) -> None:
        target = self.project_root / "workspace" / "vscode-extension"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="vscode-extension-js",
                project_name="Snippet Runner",
            )
        )

        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "extension.js").exists())
        self.assertTrue((target / ".vscode" / "launch.json").exists())
        self.assertTrue((target / "build.py").exists())
        package = json.loads((target / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["main"], "./extension.js")
        self.assertIn("onCommand:snippet-runner.hello", package["activationEvents"])
        commands = {entry["command"] for entry in package["contributes"]["commands"]}
        self.assertIn("snippet-runner.hello", commands)
        self.assertIn("snippet-runner.openPanel", commands)
        self.assertIn("validate_package", (target / "build.py").read_text(encoding="utf-8"))
        self.assertEqual(result.validation_command, "python build.py")

    def test_node_cli_scaffold_creates_bin_entrypoint_tests_and_validation(self) -> None:
        target = self.project_root / "workspace" / "node-cli"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="node-cli-js",
                project_name="Log Formatter",
            )
        )

        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "bin" / "cli.js").exists())
        self.assertTrue((target / "src" / "commands.js").exists())
        self.assertTrue((target / "tests" / "commands.test.js").exists())
        self.assertTrue((target / "build.js").exists())
        package = json.loads((target / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["bin"]["log-formatter"], "./bin/cli.js")
        self.assertEqual(package["scripts"]["validate"], "node build.js")
        self.assertEqual(package["scripts"]["test"], "node --test tests/commands.test.js")
        build_script = (target / "build.js").read_text(encoding="utf-8")
        self.assertIn("'--test', 'tests/commands.test.js'", build_script)
        self.assertNotIn("shell:", build_script)
        self.assertEqual(result.validation_command, "node build.js")

    def test_node_http_api_scaffold_creates_routes_tests_and_validation(self) -> None:
        target = self.project_root / "workspace" / "node-api"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="node-http-api-js",
                project_name="Inventory Gateway",
            )
        )

        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "src" / "server.js").exists())
        self.assertTrue((target / "src" / "store.js").exists())
        self.assertTrue((target / "tests" / "api.test.js").exists())
        self.assertTrue((target / "build.js").exists())
        package = json.loads((target / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["scripts"]["validate"], "node build.js")
        self.assertEqual(package["scripts"]["test"], "node --test tests/api.test.js")
        server = (target / "src" / "server.js").read_text(encoding="utf-8")
        build_script = (target / "build.js").read_text(encoding="utf-8")
        self.assertIn("/health", server)
        self.assertIn("/api/items", server)
        self.assertIn("'--test', 'tests/api.test.js'", build_script)
        self.assertNotIn("shell:", build_script)
        self.assertEqual(result.validation_command, "node build.js")

    def test_node_fullstack_scaffold_creates_ui_api_store_tests_and_validation(self) -> None:
        target = self.project_root / "workspace" / "node-fullstack"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="node-fullstack-js",
                project_name="Task Ops",
            )
        )

        self.assertTrue((target / "package.json").exists())
        self.assertTrue((target / "public" / "index.html").exists())
        self.assertTrue((target / "public" / "styles.css").exists())
        self.assertTrue((target / "public" / "app.js").exists())
        self.assertTrue((target / "src" / "server.js").exists())
        self.assertTrue((target / "src" / "store.js").exists())
        self.assertTrue((target / "tests" / "fullstack.test.js").exists())
        self.assertTrue((target / "build.js").exists())
        package = json.loads((target / "package.json").read_text(encoding="utf-8"))
        html = (target / "public" / "index.html").read_text(encoding="utf-8")
        server = (target / "src" / "server.js").read_text(encoding="utf-8")
        store = (target / "src" / "store.js").read_text(encoding="utf-8")
        build_script = (target / "build.js").read_text(encoding="utf-8")
        self.assertEqual(package["scripts"]["validate"], "node build.js")
        self.assertEqual(package["scripts"]["test"], "node --test tests/fullstack.test.js")
        self.assertIn("data-task-form", html)
        self.assertIn("/api/tasks", server)
        self.assertIn("createJsonStore", store)
        self.assertIn("'--test', 'tests/fullstack.test.js'", build_script)
        self.assertNotIn("shell:", build_script)
        self.assertEqual(result.validation_command, "node build.js")

    def test_python_stdlib_api_scaffold_creates_package_routes_tests_and_validation(self) -> None:
        target = self.project_root / "workspace" / "python-api"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="python-stdlib-api",
                project_name="Inventory Bridge",
            )
        )

        self.assertTrue((target / "pyproject.toml").exists())
        self.assertTrue((target / "src" / "inventory_bridge" / "server.py").exists())
        self.assertTrue((target / "src" / "inventory_bridge" / "store.py").exists())
        self.assertTrue((target / "tests" / "test_api.py").exists())
        self.assertTrue((target / "build.py").exists())
        server = (target / "src" / "inventory_bridge" / "server.py").read_text(encoding="utf-8")
        store = (target / "src" / "inventory_bridge" / "store.py").read_text(encoding="utf-8")
        tests = (target / "tests" / "test_api.py").read_text(encoding="utf-8")
        build_script = (target / "build.py").read_text(encoding="utf-8")
        self.assertIn("/health", server)
        self.assertIn("/api/items", server)
        self.assertIn("JsonItemStore", store)
        self.assertIn("urllib.request", tests)
        self.assertIn("error.close()", tests)
        self.assertIn("unittest", build_script)
        self.assertEqual(result.validation_command, "python build.py")

    def test_powershell_module_scaffold_creates_manifest_script_tests_and_validation(self) -> None:
        target = self.project_root / "workspace" / "powershell-module"

        result = self.scaffolder.scaffold(
            ProjectScaffoldRequest(
                target_path=str(target),
                preset_id="powershell-module",
                project_name="Admin Toolkit",
            )
        )

        self.assertTrue((target / "src" / "AdminToolkit.psm1").exists())
        self.assertTrue((target / "src" / "AdminToolkit.psd1").exists())
        self.assertTrue((target / "scripts" / "Invoke-AdminToolkit.ps1").exists())
        self.assertTrue((target / "tests" / "Smoke.Tests.ps1").exists())
        self.assertTrue((target / "build.ps1").exists())
        module = (target / "src" / "AdminToolkit.psm1").read_text(encoding="utf-8")
        manifest = (target / "src" / "AdminToolkit.psd1").read_text(encoding="utf-8")
        build_script = (target / "build.ps1").read_text(encoding="utf-8")
        tests = (target / "tests" / "Smoke.Tests.ps1").read_text(encoding="utf-8")
        self.assertIn("Export-ModuleMember", module)
        self.assertIn("FunctionsToExport", manifest)
        self.assertIn("Test-ModuleManifest", build_script)
        self.assertIn("PSParser", build_script)
        self.assertIn("Test-AegisPath", tests)
        self.assertEqual(result.validation_command, "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1")


if __name__ == "__main__":
    unittest.main()
