from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.validation import ValidationManager


class ValidationManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.manager = ValidationManager()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_command_history(self, payload: dict) -> None:
        history_path = self.workspace / ".aegis" / "command_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_discovers_ranked_node_validation_commands(self) -> None:
        (self.workspace / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {
                        "build": "vite build",
                        "test": "vitest run",
                        "typecheck": "tsc --noEmit",
                    }
                }
            ),
            encoding="utf-8",
        )

        snapshot = self.manager.profile_snapshot(self.workspace)

        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "npm test")
        self.assertGreaterEqual(len(snapshot.suggestions), 3)
        self.assertEqual(snapshot.suggestions[0].command, "npm test")

    def test_discovers_node_validation_commands_with_utf8_bom(self) -> None:
        package_json = json.dumps({"scripts": {"test": "node smoke.js"}})
        (self.workspace / "package.json").write_text(package_json, encoding="utf-8-sig")

        snapshot = self.manager.profile_snapshot(self.workspace)

        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "npm test")
        self.assertEqual(snapshot.suggestions[0].command, "npm test")

    def test_node_validation_respects_package_manager_and_install_inference(self) -> None:
        (self.workspace / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "pnpm@9.0.0",
                    "scripts": {
                        "build": "vite build",
                        "test": "vitest run",
                        "typecheck": "tsc --noEmit",
                    },
                }
            ),
            encoding="utf-8",
        )

        snapshot = self.manager.profile_snapshot(self.workspace)
        pipeline = self.manager.verification_plan(self.workspace, include_install=True)

        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "pnpm test")
        self.assertEqual(pipeline[0].phase, "install")
        self.assertEqual(pipeline[0].command, "pnpm install")
        self.assertIn("pnpm typecheck", [step.command for step in pipeline])

    def test_validation_discovery_ignores_damaged_marker_directories(self) -> None:
        marker_dirs = (
            "build.py",
            "build.js",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "Project.csproj",
            "Native.vcxproj",
            "Demo.sln",
            "CMakeLists.txt",
            "Makefile",
            "pom.xml",
            "build.gradle",
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "tsconfig.json",
            "vite.config.ts",
            ".sqlfluff",
            "schema.sql",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lock",
            "uv.lock",
            "poetry.lock",
            "prisma/schema.prisma",
        )
        for relative in marker_dirs:
            (self.workspace / relative).mkdir(parents=True)

        suggestions = self.manager.discover_commands(self.workspace)
        pipeline = self.manager.verification_plan(self.workspace, include_install=True)

        self.assertEqual([item.command for item in suggestions], [])
        self.assertEqual([step.command for step in pipeline], [])

        (self.workspace / "package.json").rmdir()
        (self.workspace / "package.json").write_text(
            json.dumps({"scripts": {"build": "vite build"}}),
            encoding="utf-8",
        )

        suggestions = self.manager.discover_commands(self.workspace)
        pipeline = self.manager.verification_plan(self.workspace, include_install=True)

        self.assertEqual(suggestions[0].command, "npm run build")
        self.assertEqual(pipeline[0].command, "npm install")

    def test_project_manifest_validation_command_wins_over_detected_scripts(self) -> None:
        (self.workspace / "package.json").write_text(
            json.dumps({"scripts": {"test": "vitest run", "build": "vite build"}}),
            encoding="utf-8",
        )
        manifest_path = self.workspace / ".aegis" / "project.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "preset_label": "Vite React TypeScript",
                    "validation_command": "npm run build",
                }
            ),
            encoding="utf-8",
        )

        snapshot = self.manager.profile_snapshot(self.workspace)

        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "npm run build")
        self.assertEqual(snapshot.suggestions[0].category, "manifest")
        self.assertEqual(snapshot.suggestions[0].command, "npm run build")

    def test_command_history_validation_command_recovers_when_profile_is_missing(self) -> None:
        (self.workspace / "build.py").write_text("print('generic')\n", encoding="utf-8")
        self.write_command_history(
            {
                "schema": "aegis.command_history.v1",
                "validation_command": "python custom_build.py",
                "commands": [
                    {
                        "kind": "validation",
                        "command": "python custom_build.py",
                        "status": "passed",
                        "category": "build",
                        "exit_code": 0,
                        "allowed": True,
                    }
                ],
            }
        )

        snapshot = self.manager.profile_snapshot(self.workspace)

        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "python custom_build.py")
        self.assertEqual(snapshot.suggestions[0].command, "python custom_build.py")
        self.assertEqual(snapshot.suggestions[0].category, "build")

    def test_command_history_uses_latest_success_when_top_level_command_failed(self) -> None:
        (self.workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(native_tool)\n",
            encoding="utf-8",
        )
        self.write_command_history(
            {
                "schema": "aegis.command_history.v1",
                "validation_command": "python broken_validator.py",
                "commands": [
                    {
                        "kind": "validation",
                        "command": "python working_validator.py",
                        "status": "passed",
                        "category": "build",
                        "exit_code": 0,
                        "allowed": True,
                    },
                    {
                        "kind": "validation",
                        "command": "python broken_validator.py",
                        "status": "failed",
                        "category": "build",
                        "exit_code": 1,
                        "allowed": True,
                    },
                ],
            }
        )

        suggestions = self.manager.discover_commands(self.workspace)

        self.assertEqual(suggestions[0].command, "python working_validator.py")
        self.assertEqual(suggestions[0].category, "build")

    def test_command_history_failed_commands_do_not_override_detected_validation(self) -> None:
        (self.workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(native_tool)\n",
            encoding="utf-8",
        )
        self.write_command_history(
            {
                "schema": "aegis.command_history.v1",
                "validation_command": "python broken_validator.py",
                "commands": [
                    {
                        "kind": "validation",
                        "command": "python broken_validator.py",
                        "status": "failed",
                        "category": "build",
                        "exit_code": 1,
                        "allowed": True,
                    }
                ],
            }
        )

        suggestions = self.manager.discover_commands(self.workspace)

        self.assertEqual(suggestions[0].command, "cmake -S . -B build && cmake --build build")

    def test_command_history_install_or_destructive_commands_are_not_recovered(self) -> None:
        (self.workspace / "package.json").write_text(
            json.dumps({"scripts": {"build": "vite build"}}),
            encoding="utf-8",
        )
        self.write_command_history(
            {
                "schema": "aegis.command_history.v1",
                "validation_command": "npm install",
                "commands": [
                    {
                        "kind": "validation",
                        "command": "npm install",
                        "status": "passed",
                        "category": "install",
                        "exit_code": 0,
                        "allowed": True,
                    },
                    {
                        "kind": "validation",
                        "command": "Remove-Item -Recurse .",
                        "status": "passed",
                        "category": "build",
                        "exit_code": 0,
                        "allowed": True,
                    },
                ],
            }
        )

        suggestions = self.manager.discover_commands(self.workspace)

        self.assertEqual(suggestions[0].command, "npm run build")
        self.assertNotIn("npm install", [item.command for item in suggestions])
        self.assertNotIn("Remove-Item -Recurse .", [item.command for item in suggestions])

    def test_discovers_native_cmake_validation_commands(self) -> None:
        (self.workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(native_tool)\n",
            encoding="utf-8",
        )

        suggestions = self.manager.discover_commands(self.workspace)
        commands = [item.command for item in suggestions]

        self.assertEqual(suggestions[0].command, "cmake -S . -B build && cmake --build build")
        self.assertIn("cmake -S . -B build && cmake --build build", commands)
        self.assertIn("ctest --test-dir build --output-on-failure", commands)

        snapshot = self.manager.profile_snapshot(self.workspace)
        self.assertIsNotNone(snapshot.profile)
        self.assertEqual(snapshot.profile.command, "cmake -S . -B build && cmake --build build")

        pipeline = self.manager.verification_plan(self.workspace)
        self.assertEqual(pipeline[0].command, "cmake -S . -B build")
        self.assertEqual(pipeline[0].phase, "configure")
        self.assertEqual(pipeline[0].source_command, "cmake -S . -B build && cmake --build build")
        self.assertEqual(pipeline[0].chain_index, 1)
        self.assertEqual(pipeline[0].chain_total, 2)
        self.assertEqual(pipeline[1].command, "cmake --build build")
        self.assertEqual(pipeline[1].phase, "build")
        self.assertEqual(pipeline[1].source_command, "cmake -S . -B build && cmake --build build")
        self.assertEqual(pipeline[1].chain_index, 2)
        self.assertEqual(pipeline[1].chain_total, 2)
        self.assertEqual(pipeline[2].command, "ctest --test-dir build --output-on-failure")
        self.assertEqual(pipeline[2].phase, "test")

    def test_verification_plan_completes_started_safe_chains_when_step_budget_is_low(self) -> None:
        (self.workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(native_tool)\n",
            encoding="utf-8",
        )

        pipeline = self.manager.verification_plan(self.workspace, max_steps=1)

        self.assertGreaterEqual(len(pipeline), 2)
        self.assertEqual(pipeline[0].command, "cmake -S . -B build")
        self.assertEqual(pipeline[0].phase, "configure")
        self.assertEqual(pipeline[1].command, "cmake --build build")
        self.assertEqual(pipeline[1].phase, "build")
        self.assertEqual(pipeline[0].chain_total, 2)
        self.assertEqual(pipeline[1].chain_total, 2)

    def test_chained_validation_preserves_quoted_windows_paths(self) -> None:
        self.manager.save_profile(
            self.workspace,
            command='"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build && "C:\\Program Files\\CMake\\bin\\cmake.exe" --build build',
            label="Pinned CMake",
        )

        pipeline = self.manager.verification_plan(self.workspace)

        self.assertEqual(pipeline[0].command, '"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build')
        self.assertEqual(pipeline[0].source_command, '"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build && "C:\\Program Files\\CMake\\bin\\cmake.exe" --build build')
        self.assertEqual(pipeline[0].phase, "configure")
        self.assertEqual(pipeline[1].command, '"C:\\Program Files\\CMake\\bin\\cmake.exe" --build build')
        self.assertEqual(pipeline[1].phase, "build")

    def test_unsafe_or_malformed_chains_stay_as_single_steps(self) -> None:
        cases = [
            "python build.py | more && python smoke.py",
            "python build.py & python smoke.py",
            "python build.py &&",
            '"python build.py && python smoke.py',
        ]

        for command in cases:
            with self.subTest(command=command):
                self.assertEqual(self.manager._safe_and_chain_segments(command), [command])

    def test_build_runner_takes_precedence_for_native_projects(self) -> None:
        (self.workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(native_tool)\n",
            encoding="utf-8",
        )
        (self.workspace / "build.py").write_text("print('build')\n", encoding="utf-8")

        suggestions = self.manager.discover_commands(self.workspace)
        pipeline = self.manager.verification_plan(self.workspace)

        self.assertEqual(suggestions[0].command, "python build.py")
        self.assertEqual(pipeline[0].command, "python build.py")
        self.assertNotIn("cmake -S . -B build", [step.command for step in pipeline])

    def test_discovers_static_site_build_runner(self) -> None:
        (self.workspace / "index.html").write_text("<main></main>\n", encoding="utf-8")
        (self.workspace / "styles.css").write_text("@media (max-width: 600px) {}\n", encoding="utf-8")
        (self.workspace / "app.js").write_text("document.addEventListener('click', () => {});\n", encoding="utf-8")
        (self.workspace / "build.js").write_text("console.log('ok')\n", encoding="utf-8")

        suggestions = self.manager.discover_commands(self.workspace)
        pipeline = self.manager.verification_plan(self.workspace)

        self.assertEqual(suggestions[0].command, "node build.js")
        self.assertEqual(suggestions[0].category, "build")
        self.assertEqual(pipeline[0].command, "node build.js")

    def test_discovers_visual_cpp_msbuild_command(self) -> None:
        (self.workspace / "NativeTool.vcxproj").write_text("<Project></Project>", encoding="utf-8")

        suggestions = self.manager.discover_commands(self.workspace)

        self.assertEqual(suggestions[0].command, "msbuild NativeTool.vcxproj /m /p:Configuration=Debug")
        self.assertEqual(suggestions[0].category, "build")

    def test_discovers_database_validation_commands(self) -> None:
        prisma = self.workspace / "prisma" / "schema.prisma"
        prisma.parent.mkdir(parents=True, exist_ok=True)
        prisma.write_text("datasource db { provider = \"sqlite\" url = \"file:dev.db\" }\n", encoding="utf-8")
        (self.workspace / "schema.sql").write_text("select 1;\n", encoding="utf-8")

        suggestions = self.manager.discover_commands(self.workspace)
        commands = [item.command for item in suggestions]

        self.assertIn("npx prisma validate", commands)
        self.assertIn("sqlfluff lint .", commands)

    def test_verification_plan_can_include_manifest_install_step(self) -> None:
        manifest_path = self.workspace / ".aegis" / "project.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "preset_label": "FastAPI",
                    "install_command": "python -m pip install -r requirements.txt",
                    "validation_command": "python -m pytest",
                }
            ),
            encoding="utf-8",
        )

        pipeline = self.manager.verification_plan(self.workspace, include_install=True)

        self.assertEqual(pipeline[0].phase, "install")
        self.assertEqual(pipeline[0].command, "python -m pip install -r requirements.txt")
        self.assertEqual(pipeline[-1].command, "python -m pytest")

    def test_saves_and_clears_workspace_validation_profile(self) -> None:
        recipe = self.manager.save_profile(
            self.workspace,
            command="python -m pytest",
            label="Pytest suite",
            source="manual",
            notes="Use pytest for this workspace.",
        )

        loaded = self.manager.load_profile(self.workspace)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.command, recipe.command)
        self.assertEqual(loaded.source, "manual")

        self.manager.clear_profile(self.workspace)
        self.assertIsNone(self.manager.load_profile(self.workspace))

    def test_remember_success_does_not_override_manual_recipe(self) -> None:
        self.manager.save_profile(
            self.workspace,
            command="python -m pytest",
            label="Pytest suite",
            source="manual",
            notes="Pinned by the user.",
        )

        kept = self.manager.remember_success(
            self.workspace,
            recipe=self.manager.load_profile(self.workspace),
        )

        self.assertEqual(kept.source, "manual")
        self.assertEqual(kept.command, "python -m pytest")


if __name__ == "__main__":
    unittest.main()
