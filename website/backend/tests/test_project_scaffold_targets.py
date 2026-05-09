from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_targets import (
    command_for_project,
    conflicting_paths,
    has_non_metadata_entries,
    is_metadata_only_refresh,
    is_same_scaffold_project,
    next_available_child_target,
    should_install_before_validation,
    title_from_name,
    visible_entries,
)
from aegis_ai.schemas import ProjectScaffoldPreset, ProjectScaffoldRequest


class ProjectScaffoldTargetTests(unittest.TestCase):
    def test_visible_entries_conflicts_and_metadata_detection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / ".aegis").mkdir()
            (target / ".gitignore").write_text("dist\n", encoding="utf-8")
            (target / "src").mkdir()
            (target / "src" / "app.ts").write_text("", encoding="utf-8")

            self.assertCountEqual([entry.name for entry in visible_entries(target)], [".gitignore", "src"])
            self.assertEqual(conflicting_paths(target, {"src/app.ts": "", "README.md": ""}), ["src/app.ts"])
            self.assertTrue(has_non_metadata_entries(target, safe_metadata_paths={".gitignore"}))

    def test_metadata_only_refresh_requires_manifest_and_safe_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            manifest = target / ".aegis" / "project.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"preset_id": "vite-react-ts", "project_name": "aegis-app"}), encoding="utf-8")

            safe = {".aegis/project.json", ".gitignore"}

            self.assertTrue(is_metadata_only_refresh(target, [".aegis\\project.json", ".gitignore"], safe_metadata_paths=safe))
            self.assertFalse(is_metadata_only_refresh(target, ["src/app.ts"], safe_metadata_paths=safe))
            self.assertTrue(is_same_scaffold_project(target, "vite-react-ts", "aegis-app"))
            self.assertFalse(is_same_scaffold_project(target, "nextjs-ts-tailwind", "aegis-app"))

    def test_next_available_child_target_reuses_manifest_child_then_increments(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            existing = target / "my-app"
            (existing / ".aegis").mkdir(parents=True)
            (existing / ".aegis" / "project.json").write_text("{}", encoding="utf-8")

            self.assertEqual(next_available_child_target(target, "My App"), existing)

            (existing / ".aegis" / "project.json").unlink()
            existing.mkdir(exist_ok=True)
            self.assertEqual(next_available_child_target(target, "My App"), target / "my-app-2")

    def test_project_title_and_command_placeholders(self) -> None:
        self.assertEqual(title_from_name("native_diagnostics-tool"), "Native Diagnostics Tool")
        self.assertEqual(
            command_for_project("echo {project_name} && echo {project_title}", "native_diagnostics-tool"),
            "echo native_diagnostics-tool && echo Native Diagnostics Tool",
        )

    def test_should_install_before_validation_for_missing_dependency_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "package.json").write_text("{}", encoding="utf-8")
            request = scaffold_request(target, run_validation=True)
            preset = scaffold_preset("vite-react-ts", package_manager="npm")

            self.assertTrue(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="npm install",
                    validation_command="npm run build",
                    request=request,
                )
            )

            (target / "node_modules").mkdir()
            self.assertFalse(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="npm install",
                    validation_command="npm run build",
                    request=request,
                )
            )

    def test_should_install_before_validation_honors_request_flags_and_python_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            (target / "pyproject.toml").write_text("[project]\nname='tool'\n", encoding="utf-8")
            preset = scaffold_preset("python-cli", package_manager="pip")

            self.assertFalse(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="python -m pip install -e .",
                    validation_command="python -m pytest",
                    request=scaffold_request(target, run_validation=False),
                )
            )
            self.assertTrue(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="python -m pip install -e .",
                    validation_command="python -m pytest",
                    request=scaffold_request(target, run_validation=True),
                )
            )

            (target / ".venv").mkdir()
            self.assertFalse(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="python -m pip install -e .",
                    validation_command="python -m pytest",
                    request=scaffold_request(target, run_validation=True),
                )
            )

    def test_should_install_before_validation_detects_supported_dotnet_manifests(self) -> None:
        for manifest_name in ("App.csproj", "App.fsproj", "App.vbproj", "App.sln", "App.slnx"):
            with self.subTest(manifest_name=manifest_name), tempfile.TemporaryDirectory() as raw:
                target = Path(raw)
                (target / "src" / "App").mkdir(parents=True)
                manifest_parent = target if manifest_name.endswith((".sln", ".slnx")) else target / "src" / "App"
                manifest_parent.mkdir(parents=True, exist_ok=True)
                (manifest_parent / manifest_name).write_text("<Project></Project>\n", encoding="utf-8")
                preset = scaffold_preset("dotnet-console-csharp", package_manager="dotnet")

                self.assertTrue(
                    should_install_before_validation(
                        preset,
                        target,
                        install_command="dotnet restore",
                        validation_command="dotnet build",
                        request=scaffold_request(target, run_validation=True),
                    )
                )

                (target / "obj").mkdir(exist_ok=True)
                (target / "obj" / "project.assets.json").write_text("{}", encoding="utf-8")
                self.assertFalse(
                    should_install_before_validation(
                        preset,
                        target,
                        install_command="dotnet restore",
                        validation_command="dotnet build",
                        request=scaffold_request(target, run_validation=True),
                    )
                )

    def test_should_install_before_validation_skips_dotnet_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            preset = scaffold_preset("dotnet-console-csharp", package_manager="dotnet")

            self.assertFalse(
                should_install_before_validation(
                    preset,
                    target,
                    install_command="dotnet restore",
                    validation_command="dotnet build",
                    request=scaffold_request(target, run_validation=True),
                )
            )


def scaffold_preset(preset_id: str, *, package_manager: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id=preset_id,
        label="Test Preset",
        framework="test",
        language="test",
        package_manager=package_manager,
    )


def scaffold_request(target: Path, *, run_validation: bool) -> ProjectScaffoldRequest:
    return ProjectScaffoldRequest(
        target_path=str(target),
        run_validation=run_validation,
        run_install=False,
    )


if __name__ == "__main__":
    unittest.main()
