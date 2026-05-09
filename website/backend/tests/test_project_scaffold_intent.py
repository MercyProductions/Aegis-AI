from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_intent import (
    continuity_preset_id,
    existing_project_validation_command,
    prompt_is_existing_project_validation_intent,
    prompt_requests_validation,
    prompt_should_reuse_existing_project,
    should_update_existing_scaffold,
    should_validate_existing_project_only,
)
from aegis_ai.schemas import WorkspaceDependencyProfile, WorkspaceProjectManifest


KNOWN_PRESETS = {
    "cpp-cmake-cli",
    "cpp-cmake-dll",
    "cpp-imgui-win32-dx11",
    "cpp-msvc-console-sln",
    "electron-react-ts",
    "fastapi-python-api",
    "nextjs-ts-tailwind",
    "node-fullstack-js",
    "python-cli",
    "static-html-site",
    "vite-react-ts",
}


class ProjectScaffoldIntentTests(unittest.TestCase):
    def test_existing_project_validation_intent_filters_create_requests(self) -> None:
        self.assertTrue(prompt_is_existing_project_validation_intent("continue"))
        self.assertTrue(prompt_is_existing_project_validation_intent("repair and make sure there are no errors"))
        self.assertFalse(prompt_is_existing_project_validation_intent("create a new project and build it"))
        self.assertFalse(prompt_is_existing_project_validation_intent("why does this build fail?"))

    def test_should_validate_existing_project_requires_existing_project_signals(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            profile = WorkspaceDependencyProfile()

            self.assertFalse(
                should_validate_existing_project_only(
                    "continue",
                    target,
                    run_validation=True,
                    profile=profile,
                )
            )

            (target / ".aegis").mkdir()
            (target / ".aegis" / "project.json").write_text("{}", encoding="utf-8")
            self.assertTrue(
                should_validate_existing_project_only(
                    "continue",
                    target,
                    run_validation=True,
                    profile=profile,
                )
            )
            self.assertFalse(
                should_validate_existing_project_only(
                    "continue",
                    target,
                    run_validation=False,
                    profile=profile,
                )
            )

    def test_should_validate_existing_project_accepts_build_profiles_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            profile = WorkspaceDependencyProfile(config_files=["CMakeLists.txt"])

            self.assertTrue(
                should_validate_existing_project_only(
                    "build it and fix any errors",
                    target,
                    run_validation=True,
                    profile=profile,
                )
            )

    def test_existing_project_validation_command_prefers_real_build_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)

            self.assertEqual(
                existing_project_validation_command(
                    target,
                    WorkspaceDependencyProfile(validation_commands=["npm run build"]),
                    "python build.py",
                ),
                "npm run build",
            )

            (target / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n",
                encoding="utf-8",
            )
            self.assertEqual(
                existing_project_validation_command(
                    target,
                    WorkspaceDependencyProfile(),
                    "cmake --build build --config Release",
                ),
                "cmake -S . -B build && cmake --build build --config Release",
            )

            (target / "build").mkdir()
            self.assertEqual(
                existing_project_validation_command(target, WorkspaceDependencyProfile(), ""),
                "cmake --build build --config Release",
            )

    def test_existing_project_validation_command_accepts_slnx_solution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "Modern.slnx").write_text("<Solution></Solution>\n", encoding="utf-8")

            self.assertEqual(
                existing_project_validation_command(target, WorkspaceDependencyProfile(), ""),
                "msbuild Modern.slnx /m /p:Configuration=Release",
            )

    def test_continuity_preset_uses_manifest_contract_and_profile_signals(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)

            manifest = WorkspaceProjectManifest(preset_id="vite-react-ts")
            self.assertEqual(
                continuity_preset_id(
                    prompt="continue building",
                    target=target,
                    manifest=manifest,
                    profile=WorkspaceDependencyProfile(),
                    known_preset_ids=KNOWN_PRESETS,
                ),
                "vite-react-ts",
            )

            contract_manifest = WorkspaceProjectManifest(mission_contract={"preset_id": "cpp-cmake-dll"})
            self.assertEqual(
                continuity_preset_id(
                    prompt="continue",
                    target=target,
                    manifest=contract_manifest,
                    profile=WorkspaceDependencyProfile(),
                    known_preset_ids=KNOWN_PRESETS,
                ),
                "cpp-cmake-dll",
            )

            self.assertEqual(
                continuity_preset_id(
                    prompt="continue",
                    target=target,
                    manifest=None,
                    profile=WorkspaceDependencyProfile(config_files=["CMakeLists.txt"], build_systems=["cmake"]),
                    known_preset_ids=KNOWN_PRESETS,
                ),
                "cpp-cmake-cli",
            )

            self.assertEqual(
                continuity_preset_id(
                    prompt="continue",
                    target=target,
                    manifest=None,
                    profile=WorkspaceDependencyProfile(config_files=["Modern.slnx"]),
                    known_preset_ids=KNOWN_PRESETS,
                ),
                "cpp-msvc-console-sln",
            )

            self.assertEqual(
                continuity_preset_id(
                    prompt="create a brand new project from scratch",
                    target=target,
                    manifest=manifest,
                    profile=WorkspaceDependencyProfile(),
                    known_preset_ids=KNOWN_PRESETS,
                ),
                "",
            )

    def test_prompt_reuse_validation_and_update_flags_remain_conservative(self) -> None:
        self.assertTrue(prompt_should_reuse_existing_project("build it"))
        self.assertFalse(prompt_should_reuse_existing_project("start a brand new separate app"))
        self.assertTrue(prompt_requests_validation("launch the app"))
        self.assertFalse(prompt_requests_validation("show me how to launch it"))

        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self.assertFalse(should_update_existing_scaffold("improve the copy", target))

            (target / "README.md").write_text("Generated by Aegis\n", encoding="utf-8")
            self.assertTrue(should_update_existing_scaffold("continue and build it", target))

            slnx_target = Path(raw) / "slnx"
            slnx_target.mkdir()
            (slnx_target / "Modern.slnx").write_text("<Solution></Solution>\n", encoding="utf-8")
            self.assertTrue(should_update_existing_scaffold("continue and build it", slnx_target))


if __name__ == "__main__":
    unittest.main()
