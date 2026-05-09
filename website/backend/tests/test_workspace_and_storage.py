from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.schemas import (
    ContextBudgetInfo,
    ContextBudgetItemInfo,
    FileChange,
    ModelAdapterHealthInfo,
    ModelAttemptInfo,
    RepairAttempt,
)
from aegis_ai.settings import Settings
from aegis_ai.storage import EventStore
from aegis_ai.memory_manager import MemoryManager
from aegis_ai.workspace import WorkspaceManager


class WorkspaceAndStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_database_path="data/test.sqlite3",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_restore_checkpoint_restores_updated_and_created_files(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        original_file = workspace / "app.py"
        original_file.write_text("print('before')\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="update", path="app.py", summary="update", content="print('after')\n"),
                FileChange(action="create", path="new.py", summary="create", content="print('new')\n"),
            ],
        )

        self.assertIsNotNone(result.checkpoint)
        manager.restore_checkpoint(workspace, result.checkpoint or "")

        self.assertEqual(original_file.read_text(encoding="utf-8"), "print('before')\n")
        self.assertFalse((workspace / "new.py").exists())

    def test_restore_checkpoint_rejects_path_traversal_checkpoint_id(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        with self.assertRaisesRegex(ValueError, "checkpoint folder name"):
            manager.restore_checkpoint(workspace, "../outside")

    def test_restore_checkpoint_rejects_non_file_manifest(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        checkpoint_root = workspace / ".aegis" / "checkpoints" / "bad-manifest"
        (checkpoint_root / "manifest.json").mkdir(parents=True)

        with self.assertRaisesRegex(ValueError, "not a regular file"):
            manager.restore_checkpoint(workspace, "bad-manifest")

    def test_restore_checkpoint_rejects_backup_paths_outside_files_folder(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        checkpoint_root = workspace / ".aegis" / "checkpoints" / "bad-backup-path"
        checkpoint_root.mkdir(parents=True)
        (checkpoint_root / "manifest.json").write_text(
            json.dumps({"id": "bad-backup-path", "files": [{"path": "../workspace/app.py", "state": "present"}]}),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "outside the checkpoint files folder"):
            manager.restore_checkpoint(workspace, "bad-backup-path")

    def test_restore_checkpoint_preflights_missing_backup_before_restoring(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        tracked = workspace / "app.py"
        tracked.write_text("after\n", encoding="utf-8")
        checkpoint_root = workspace / ".aegis" / "checkpoints" / "missing-backup"
        backup = checkpoint_root / "files" / "app.py"
        backup.parent.mkdir(parents=True)
        backup.write_text("before\n", encoding="utf-8")
        (checkpoint_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "missing-backup",
                    "files": [
                        {"path": "app.py", "state": "present"},
                        {"path": "missing.py", "state": "present"},
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "checkpoint backup file is missing"):
            manager.restore_checkpoint(workspace, "missing-backup")

        self.assertEqual(tracked.read_text(encoding="utf-8"), "after\n")

    def test_apply_changes_does_not_write_when_checkpoint_cannot_be_created(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / ".aegis").write_text("not a directory", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="app.py", summary="create", content="print('new')\n"),
            ],
        )

        self.assertEqual(result.applied, [])
        self.assertIsNone(result.checkpoint)
        self.assertFalse((workspace / "app.py").exists())
        self.assertTrue(any("checkpoint could not be created" in warning for warning in result.warnings))

    def test_apply_changes_can_append_large_generated_file_chunks(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="generated/monolith.cpp", summary="seed", content="int first = 1;\n"),
                FileChange(action="append", path="generated/monolith.cpp", summary="chunk", content="int second = 2;\n"),
            ],
        )

        self.assertEqual(
            (workspace / "generated" / "monolith.cpp").read_text(encoding="utf-8"),
            "int first = 1;\nint second = 2;\n",
        )
        self.assertIn("append: generated/monolith.cpp", result.applied)

    def test_apply_changes_does_not_append_to_missing_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="append", path="generated/missing.cpp", summary="chunk", content="int second = 2;\n"),
            ],
        )

        self.assertFalse((workspace / "generated" / "missing.cpp").exists())
        self.assertNotIn("append: generated/missing.cpp", result.applied)
        self.assertTrue(any("skipped append" in warning and "use create before append" in warning for warning in result.warnings))

    def test_apply_changes_does_not_append_after_skipped_create(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "generated" / "monolith.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int original = 42;\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="generated/monolith.cpp", summary="seed", content="int first = 1;\n"),
                FileChange(action="append", path="generated/monolith.cpp", summary="chunk", content="int second = 2;\n"),
            ],
        )

        self.assertEqual(existing.read_text(encoding="utf-8"), "int original = 42;\n")
        self.assertNotIn("create: generated/monolith.cpp", result.applied)
        self.assertNotIn("append: generated/monolith.cpp", result.applied)
        self.assertTrue(any("already exists" in warning and "use update" in warning for warning in result.warnings))
        self.assertTrue(any("seed create" in warning and "did not apply" in warning for warning in result.warnings))

    def test_apply_changes_does_not_append_after_skipped_create_with_mixed_slashes(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "generated" / "monolith.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int original = 42;\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path=r"generated\monolith.cpp", summary="seed", content="int first = 1;\n"),
                FileChange(action="append", path="generated/monolith.cpp", summary="chunk", content="int second = 2;\n"),
            ],
        )

        self.assertEqual(existing.read_text(encoding="utf-8"), "int original = 42;\n")
        self.assertNotIn("append: generated/monolith.cpp", result.applied)
        self.assertTrue(any("seed create" in warning and "did not apply" in warning for warning in result.warnings))

    def test_apply_changes_does_not_append_after_skipped_create_with_mixed_case(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="Generated/Monolith.cpp", summary="seed", content=None),
                FileChange(action="append", path="generated/monolith.cpp", summary="chunk", content="int second = 2;\n"),
            ],
        )

        self.assertFalse((workspace / "generated" / "monolith.cpp").exists())
        self.assertNotIn("append: generated/monolith.cpp", result.applied)
        self.assertTrue(any("missing file content" in warning for warning in result.warnings))
        self.assertTrue(any("seed create" in warning and "did not apply" in warning for warning in result.warnings))

    def test_apply_changes_does_not_delete_after_skipped_create(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "generated" / "monolith.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int original = 42;\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path=r"generated\monolith.cpp", summary="seed", content="int first = 1;\n"),
                FileChange(action="delete", path="generated/monolith.cpp", summary="delete"),
            ],
        )

        self.assertTrue(existing.exists())
        self.assertEqual(existing.read_text(encoding="utf-8"), "int original = 42;\n")
        self.assertNotIn("delete: generated/monolith.cpp", result.applied)
        self.assertTrue(any("already exists" in warning and "use update" in warning for warning in result.warnings))
        self.assertTrue(any("skipped delete" in warning and "seed create" in warning for warning in result.warnings))

    def test_apply_changes_delete_still_removes_existing_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "generated" / "remove-me.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int old = 1;\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="delete", path="generated/remove-me.cpp", summary="delete"),
            ],
        )

        self.assertFalse(existing.exists())
        self.assertIn("delete: generated/remove-me.cpp", result.applied)
        self.assertEqual(result.warnings, [])

    def test_apply_changes_does_not_create_over_existing_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "src" / "main.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int main(){ return 42; }\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="src/main.cpp", summary="replace", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertEqual(existing.read_text(encoding="utf-8"), "int main(){ return 42; }\n")
        self.assertNotIn("create: src/main.cpp", result.applied)
        self.assertTrue(any("already exists" in warning and "use update" in warning for warning in result.warnings))

    def test_apply_changes_update_still_modifies_existing_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        existing = workspace / "src" / "main.cpp"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("int main(){ return 42; }\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="update", path="src/main.cpp", summary="update", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertEqual(existing.read_text(encoding="utf-8"), "int main(){ return 0; }\n")
        self.assertIn("update: src/main.cpp", result.applied)
        self.assertEqual(result.warnings, [])

    def test_apply_changes_does_not_update_missing_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="update", path="src/missing.cpp", summary="update", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertFalse((workspace / "src" / "missing.cpp").exists())
        self.assertNotIn("update: src/missing.cpp", result.applied)
        self.assertTrue(any("does not exist" in warning and "use create" in warning for warning in result.warnings))

    def test_apply_changes_create_then_update_same_file_in_batch(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="create", path="src/new.cpp", summary="create", content="int main(){ return 1; }\n"),
                FileChange(action="update", path="src/new.cpp", summary="update", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertEqual((workspace / "src" / "new.cpp").read_text(encoding="utf-8"), "int main(){ return 0; }\n")
        self.assertIn("create: src/new.cpp", result.applied)
        self.assertIn("update: src/new.cpp", result.applied)
        self.assertEqual(result.warnings, [])

    def test_list_checkpoints_returns_file_counts_and_entries(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "app.py").write_text("print('before')\n", encoding="utf-8")

        result = manager.apply_changes(
            workspace,
            [
                FileChange(action="update", path="app.py", summary="update", content="print('after')\n"),
                FileChange(action="create", path="new.py", summary="create", content="print('new')\n"),
            ],
        )

        checkpoints = manager.list_checkpoints(workspace, limit=10)

        self.assertGreaterEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0].id, result.checkpoint)
        self.assertEqual(checkpoints[0].file_count, 2)
        self.assertEqual(checkpoints[0].present_count, 1)
        self.assertEqual(checkpoints[0].missing_count, 1)
        self.assertEqual([entry.path for entry in checkpoints[0].files], ["app.py", "new.py"])

    def test_resolve_workspace_copies_legacy_backend_workspace_when_new_workspace_is_empty(self) -> None:
        legacy_workspace = self.project_root / "backend" / "workspace"
        legacy_workspace.mkdir(parents=True, exist_ok=True)
        (legacy_workspace / "legacy.txt").write_text("from legacy\n", encoding="utf-8")

        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        self.assertTrue((workspace / "legacy.txt").exists())
        self.assertEqual((workspace / "legacy.txt").read_text(encoding="utf-8"), "from legacy\n")

    def test_resolve_workspace_does_not_seed_explicit_project_path_from_legacy_workspace(self) -> None:
        legacy_workspace = self.project_root / "backend" / "workspace"
        legacy_workspace.mkdir(parents=True, exist_ok=True)
        (legacy_workspace / "legacy.txt").write_text("from legacy\n", encoding="utf-8")

        manager = WorkspaceManager(self.project_root, self.settings)
        requested = self.project_root / "workspace" / "fresh-project"
        workspace = manager.resolve_workspace(str(requested))

        self.assertEqual(workspace, requested.resolve())
        self.assertTrue(workspace.exists())
        self.assertFalse((workspace / "legacy.txt").exists())

    def test_resolve_workspace_allows_configured_aegis_workspace_root(self) -> None:
        aegis_root = self.project_root / "Aegis"
        backend_project = aegis_root / "Website" / "ChatBot"
        backend_project.mkdir(parents=True, exist_ok=True)
        requested = aegis_root / "Tools" / "04 Runtime & Engine Tools" / "DeleteLater"
        settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_workspace_root=str(aegis_root),
            aegis_database_path="data/test.sqlite3",
        )

        manager = WorkspaceManager(backend_project, settings)
        workspace = manager.resolve_workspace(str(requested))

        self.assertEqual(workspace, requested.resolve())
        self.assertTrue(workspace.exists())

    def test_resolve_workspace_rejects_paths_outside_allowed_roots(self) -> None:
        outside = self.project_root.parent / "outside-aegis-workspace"
        settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_workspace_root=str(self.project_root),
            aegis_allow_explicit_workspace_paths=False,
            aegis_database_path="data/test.sqlite3",
        )
        manager = WorkspaceManager(self.project_root, settings)

        with self.assertRaises(ValueError):
            manager.resolve_workspace(str(outside))

    def test_resolve_workspace_reports_create_failures_as_value_errors(self) -> None:
        blocker = self.project_root / "not-a-directory"
        blocker.write_text("blocks child workspace creation", encoding="utf-8")
        manager = WorkspaceManager(self.project_root, self.settings)

        with self.assertRaisesRegex(ValueError, "workspace root could not be created"):
            manager.resolve_workspace("not-a-directory/workspace")

    def test_resolve_workspace_allows_safe_explicit_absolute_project_paths(self) -> None:
        outside = self.project_root.parent / "outside-aegis-workspace"
        settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_workspace_root=str(self.project_root),
            aegis_allow_explicit_workspace_paths=True,
            aegis_database_path="data/test.sqlite3",
        )
        manager = WorkspaceManager(self.project_root, settings)

        workspace = manager.resolve_workspace(str(outside))

        self.assertEqual(workspace, outside.resolve())
        self.assertTrue(workspace.exists())

    def test_scan_treats_native_and_windows_project_files_as_text(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")

        files = {
            "CMakeLists.txt": "cmake_minimum_required(VERSION 3.20)\nproject(AegisNative)\n",
            "Makefile": "all:\n\t@echo build\n",
            "AegisNative.sln": "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            "AegisNative.vcxproj": "<Project></Project>\n",
            "AegisNative.vcxproj.filters": "<Project></Project>\n",
            "include/aegis/native.hpp": "#pragma once\nvoid run();\n",
            "src/main.cpp": "#include <iostream>\nint main(){ std::cout << \"hi\"; }\n",
            "src/win32.rc": "IDI_ICON1 ICON \"app.ico\"\n",
            "scripts/build.ps1": "cmake -S . -B build\n",
            "shaders/debug.hlsl": "float4 main() : SV_Target { return 1; }\n",
            ".editorconfig": "root = true\n",
        }
        for relative, content in files.items():
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        scanned = {item.path: item.kind for item in manager.scan(workspace, max_files=40)}

        for relative in files:
            self.assertEqual(scanned.get(relative.replace("\\", "/")), "text", relative)

    def test_large_file_scan_context_and_line_slice_support(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        source_dir = workspace / "src"
        source_dir.mkdir(parents=True, exist_ok=True)
        source = source_dir / "monolith.cpp"
        source.write_text(
            "".join(f"int generated_symbol_{index}() {{ return {index}; }}\n" for index in range(30_000)),
            encoding="utf-8",
        )

        files = manager.scan(workspace, max_files=20)
        monolith = next(item for item in files if item.path == "src/monolith.cpp")

        self.assertTrue(monolith.is_large)
        self.assertGreaterEqual(monolith.estimated_lines, 30_000)
        self.assertIn("line slices", monolith.large_file_strategy)

        context = manager.context_for_model(workspace, [monolith], max_chars=6_000, max_file_chars=2_400)
        self.assertIn("[large file summary]", context)
        self.assertIn("generated_symbol_0", context)
        self.assertIn("generated_symbol_29999", context)
        self.assertIn("do not rewrite this file wholesale", context)

        with self.assertRaisesRegex(ValueError, "line slice"):
            manager.read_file(workspace, "src/monolith.cpp")

        slice_payload = manager.read_file_slice(workspace, "src/monolith.cpp", start_line=200, max_lines=3)
        self.assertEqual(slice_payload["start_line"], 200)
        self.assertEqual(slice_payload["lines_returned"], 3)
        self.assertIn("generated_symbol_199", slice_payload["content"])

        inventory = manager.large_file_inventory(workspace, files)
        self.assertEqual(inventory[0]["path"], "src/monolith.cpp")
        self.assertGreaterEqual(inventory[0]["estimated_lines"], 30_000)

    def test_resolve_workspace_rejects_drive_or_filesystem_root_even_when_explicit_paths_are_enabled(self) -> None:
        settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_workspace_root=str(self.project_root),
            aegis_allow_explicit_workspace_paths=True,
            aegis_database_path="data/test.sqlite3",
        )
        manager = WorkspaceManager(self.project_root, settings)
        root_path = Path(self.project_root.anchor or "/").resolve()

        with self.assertRaises(ValueError):
            manager.resolve_workspace(str(root_path))

    def test_resolve_workspace_allows_additional_configured_roots_when_explicit_paths_are_locked_down(self) -> None:
        projects_root = self.project_root.parent / "configured-projects"
        requested = projects_root / "tooling-app"
        settings = Settings(
            _env_file=None,
            default_workspace="workspace",
            aegis_workspace_root=str(self.project_root),
            aegis_additional_workspace_roots=str(projects_root),
            aegis_allow_explicit_workspace_paths=False,
            aegis_database_path="data/test.sqlite3",
        )
        manager = WorkspaceManager(self.project_root, settings)

        workspace = manager.resolve_workspace(str(requested))

        self.assertEqual(workspace, requested.resolve())
        self.assertTrue(workspace.exists())

    def test_load_project_manifest_reads_aegis_project_metadata(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        manifest_path = workspace / ".aegis" / "project.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "demo-app",
                    "title": "Demo App",
                    "preset_id": "vite-react-ts",
                    "preset_label": "Vite React TypeScript",
                    "framework": "Vite + React",
                    "language": "TypeScript",
                    "package_manager": "npm",
                    "install_command": "npm install",
                    "validation_command": "npm run build",
                    "tags": ["web", "react"],
                    "agent_handoff": {"primary_goal": "Build a polished app."},
                }
            ),
            encoding="utf-8",
        )

        manifest = manager.load_project_manifest(workspace)

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.schema_version, "aegis.project.v1")
        self.assertEqual(manifest.title, "Demo App")
        self.assertEqual(manifest.validation_command, "npm run build")
        self.assertEqual(manifest.tags, ["web", "react"])

    def test_discover_instruction_files_uses_content_not_only_filename(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "northstar.md").write_text(
            """
# Project Completion List

- [ ] Build the dashboard shell with responsive layout.
- [ ] Add validation coverage for the CLI workflow.
- [x] Create the initial scaffold.
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertEqual(instructions[0].path, "northstar.md")
        self.assertEqual(instructions[0].pending_count, 2)
        self.assertIn("Build the dashboard shell", instructions[0].pending_items[0])

    def test_discover_instruction_files_supports_agent_handoff_and_numbered_checkboxes(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "AGENTS.md").write_text(
            """
# Agent Handoff

1. [ ] Build the ImGui diagnostics panel.
2. [x] Create the first smoke test.
3. [ ] Validate the native build loop.
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertEqual(instructions[0].path, "AGENTS.md")
        self.assertEqual(instructions[0].pending_count, 2)
        self.assertEqual(instructions[0].completed_count, 1)
        self.assertEqual(instructions[0].pending_items[0], "Build the ImGui diagnostics panel.")

    def test_discover_instruction_files_supports_extensionless_todo_files(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "TODO").write_text(
            """
Project instructions

- Build a full validation report view.
- Add tests for command capture.
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertEqual(instructions[0].path, "TODO")
        self.assertEqual(instructions[0].pending_count, 2)

    def test_discover_instruction_files_includes_prompt_referenced_neutral_filename(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "alpha-notes.md").write_text(
            """
# Alpha Notes

- Conversation persistence
- CMake verification logs
- Build output viewer
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(
            workspace,
            referenced_text="Continue the project from alpha-notes.md.",
        )

        self.assertEqual(instructions[0].path, "alpha-notes.md")
        self.assertGreaterEqual(instructions[0].score, 0.64)
        self.assertIn("referenced by prompt", instructions[0].summary)
        self.assertIn("Conversation persistence", instructions[0].pending_items)

    def test_discover_instruction_files_supports_generic_filename_with_plan_headings(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "whatever.md").write_text(
            """
# Barber Launch Blueprint

## Phase 1

- Hero booking CTA
- Pricing cards
- Gallery carousel

## Acceptance Criteria

- Mobile layout passes
- Release build succeeds
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertEqual(instructions[0].path, "whatever.md")
        self.assertEqual(instructions[0].pending_count, 5)
        self.assertIn("Hero booking CTA", instructions[0].pending_items)
        self.assertIn("Mobile layout passes", instructions[0].pending_items)
        self.assertIn("instruction heading", instructions[0].summary)

    def test_discover_instruction_files_ignores_plain_notes_without_project_work(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "meeting-notes.md").write_text(
            """
# Meeting Notes

- Coffee preference
- Parking details
- Lunch options
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertEqual(instructions, [])

    def test_discover_instruction_files_prioritizes_prompt_referenced_plan(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "TODO.md").write_text(
            """
# TODO

- [ ] Low priority cleanup
""".strip(),
            encoding="utf-8",
        )
        (workspace / "release-plan.md").write_text(
            """
# Release Plan

- Package desktop build
- Capture final validation logs
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(
            workspace,
            referenced_text="Use release-plan.md for this autopilot pass.",
        )

        self.assertEqual(instructions[0].path, "release-plan.md")
        self.assertIn("Package desktop build", instructions[0].pending_items)

    def test_discover_instruction_files_supports_prompt_referenced_extensionless_file(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "northstar").write_text(
            """
Project completion list

- Build the native diagnostics panel.
- Add validation coverage for the release workflow.
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(
            workspace,
            referenced_text="Continue from northstar until the project is complete.",
        )

        self.assertEqual(instructions[0].path, "northstar")
        self.assertGreaterEqual(instructions[0].score, 0.64)
        self.assertIn("referenced by prompt", instructions[0].summary)
        self.assertIn("Build the native diagnostics panel.", instructions[0].pending_items)

    def test_discover_instruction_files_includes_aegis_roadmap(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        roadmap = workspace / ".aegis" / "ROADMAP.md"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        roadmap.write_text(
            """
# Roadmap

## Next Steps
- [ ] Implement the repair loop dashboard.
- [ ] Run the project validation command after edits.
""".strip(),
            encoding="utf-8",
        )

        instructions = manager.discover_instruction_files(workspace)

        self.assertIn(".aegis/ROADMAP.md", [item.path for item in instructions])
        self.assertTrue(any("repair loop dashboard" in " ".join(item.pending_items) for item in instructions))

    def test_inspect_dependency_profile_detects_node_stack(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
        (workspace / "prisma").mkdir(parents=True, exist_ok=True)
        (workspace / "prisma" / "schema.prisma").write_text("datasource db { provider = \"sqlite\" }\n", encoding="utf-8")
        (workspace / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "pnpm@9.0.0",
                    "scripts": {
                        "build": "vite build",
                        "typecheck": "tsc --noEmit",
                        "test": "vitest run",
                    },
                    "dependencies": {
                        "react": "^19.0.0",
                        "prisma": "^6.0.0",
                    },
                    "devDependencies": {
                        "typescript": "^5.0.0",
                        "vite": "^6.0.0",
                        "vitest": "^3.0.0",
                    },
                }
            ),
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("TypeScript", profile.languages)
        self.assertIn("React", profile.frameworks)
        self.assertIn("Vite", profile.frameworks)
        self.assertIn("pnpm", profile.package_managers)
        self.assertIn("pnpm install", profile.install_commands)
        self.assertIn("pnpm build", profile.validation_commands)
        self.assertIn("pnpm typecheck", profile.validation_commands)
        self.assertIn("Prisma", profile.database_tools)
        self.assertEqual(profile.scripts[0].source, "package.json")
        self.assertTrue(any(item.name == "react" for item in profile.dependencies))
        self.assertTrue(any(item.name == "typescript" for item in profile.dev_dependencies))

    def test_inspect_dependency_profile_detects_bun_node_stack(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "bun.lock").write_text("", encoding="utf-8")
        (workspace / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "bun@1.1.0",
                    "scripts": {
                        "build": "vite build",
                        "test": "bun test",
                        "typecheck": "tsc --noEmit",
                    },
                    "dependencies": {
                        "react": "^19.0.0",
                    },
                    "devDependencies": {
                        "typescript": "^5.0.0",
                        "vite": "^6.0.0",
                    },
                }
            ),
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("bun", profile.package_managers)
        self.assertIn("bun install", profile.install_commands)
        self.assertIn("bun run build", profile.validation_commands)
        self.assertIn("bun run typecheck", profile.validation_commands)
        self.assertIn("React", profile.frameworks)
        self.assertIn("Vite", profile.frameworks)

    def test_inspect_dependency_profile_accepts_bom_prefixed_package_json(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "package.json").write_text(
            "\ufeff" + json.dumps({"scripts": {"test": "node smoke.js"}}),
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("package.json", profile.config_files)
        self.assertIn("npm", profile.package_managers)
        self.assertIn("npm run test", profile.validation_commands)

    def test_inspect_dependency_profile_ignores_damaged_marker_directories(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        marker_dirs = (
            "package.json",
            "tsconfig.json",
            "requirements.txt",
            "go.mod",
            "Cargo.toml",
            "CMakeLists.txt",
            "build.py",
            "Demo.csproj",
            "Demo.fsproj",
            "Demo.vbproj",
            "Demo.vcxproj",
            "Demo.sln",
            "Demo.slnx",
            "Demo.vcxproj.filters",
            "pom.xml",
            "build.gradle",
            "schema.sql",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lock",
            "prisma/schema.prisma",
            "src/main.tsx",
        )
        for relative in marker_dirs:
            (workspace / relative).mkdir(parents=True)

        profile = manager.inspect_dependency_profile(workspace)

        self.assertEqual(profile.config_files, [])
        self.assertEqual(profile.validation_commands, [])
        self.assertEqual(profile.entry_points, [])
        self.assertIn("No dependency or build manifest was detected.", profile.warnings)

        (workspace / "package.json").rmdir()
        (workspace / "package.json").write_text(
            json.dumps({"scripts": {"build": "vite build"}}),
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("package.json", profile.config_files)
        self.assertIn("npm", profile.package_managers)
        self.assertNotIn("pnpm", profile.package_managers)
        self.assertNotIn("tsconfig.json", profile.config_files)
        self.assertIn("npm run build", profile.validation_commands)

        python_workspace = manager.resolve_workspace("python-workspace")
        (python_workspace / "pyproject.toml").write_text("[project]\nname = \"demo\"\n", encoding="utf-8")
        (python_workspace / "uv.lock").mkdir()
        (python_workspace / "poetry.lock").mkdir()

        profile = manager.inspect_dependency_profile(python_workspace)

        self.assertIn("pip", profile.package_managers)
        self.assertNotIn("uv", profile.package_managers)
        self.assertNotIn("poetry", profile.package_managers)

    def test_inspect_dependency_profile_detects_supported_dotnet_projects(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "src" / "FSharpApp").mkdir(parents=True, exist_ok=True)
        (workspace / "src" / "VbTool").mkdir(parents=True, exist_ok=True)
        (workspace / "src" / "FSharpApp" / "FSharpApp.fsproj").write_text(
            '<Project><ItemGroup><PackageReference Include="FsToolkit.ErrorHandling" Version="4.18.0" /></ItemGroup></Project>\n',
            encoding="utf-8",
        )
        (workspace / "src" / "VbTool" / "VbTool.vbproj").write_text("<Project></Project>\n", encoding="utf-8")

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("src/FSharpApp/FSharpApp.fsproj", profile.config_files)
        self.assertIn("src/VbTool/VbTool.vbproj", profile.config_files)
        self.assertIn("F#", profile.languages)
        self.assertIn("Visual Basic", profile.languages)
        self.assertIn("dotnet", profile.package_managers)
        self.assertIn("dotnet restore", profile.install_commands)
        self.assertIn("dotnet build", profile.validation_commands)
        self.assertIn("dotnet test", profile.validation_commands)
        self.assertTrue(any(item.name == "FsToolkit.ErrorHandling" for item in profile.dependencies))

    def test_inspect_dependency_profile_detects_slnx_solution(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "Modern.slnx").write_text("<Solution></Solution>\n", encoding="utf-8")

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("Modern.slnx", profile.config_files)
        self.assertIn("msbuild Modern.slnx /m /p:Configuration=Release", profile.validation_commands)
        self.assertIn("Visual Studio / MSBuild", profile.build_systems)

    def test_inspect_dependency_profile_detects_python_stack(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "pyproject.toml").write_text(
            """
[project]
dependencies = ["fastapi>=0.100", "sqlalchemy"]

[project.optional-dependencies]
dev = ["pytest", "ruff"]
""".strip(),
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertIn("Python", profile.languages)
        self.assertIn("pip", profile.package_managers)
        self.assertIn("FastAPI", profile.frameworks)
        self.assertIn("SQLAlchemy", profile.frameworks)
        self.assertIn("SQLAlchemy", profile.database_tools)
        self.assertIn("python -m pytest", profile.validation_commands)
        self.assertIn("python -m ruff check .", profile.validation_commands)

    def test_inspect_dependency_profile_detects_native_game_and_windows_tooling(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "src").mkdir(parents=True, exist_ok=True)
        (workspace / "include").mkdir(parents=True, exist_ok=True)
        (workspace / "shaders").mkdir(parents=True, exist_ok=True)
        (workspace / "CMakeLists.txt").write_text(
            """
cmake_minimum_required(VERSION 3.20)
project(NativeInspector LANGUAGES CXX)
find_package(Vulkan)
""".strip(),
            encoding="utf-8",
        )
        (workspace / "build.py").write_text("print('build')\n", encoding="utf-8")
        (workspace / "src" / "main.cpp").write_text(
            """
#include <windows.h>
#include <d3d11.h>
#include <MinHook.h>
#include <capstone/capstone.h>
#include "imgui.h"
int main() {
    MH_Initialize();
    ImGui::CreateContext();
    return 0;
}
""".strip(),
            encoding="utf-8",
        )
        (workspace / "include" / "pe.hpp").write_text(
            "#pragma once\nstruct IMAGE_NT_HEADERS;\nstruct IMAGE_DOS_HEADER;\n",
            encoding="utf-8",
        )
        (workspace / "shaders" / "overlay.hlsl").write_text(
            "float4 main() : SV_Target { return 1; }\n",
            encoding="utf-8",
        )

        profile = manager.inspect_dependency_profile(workspace)

        self.assertEqual(profile.project_type, "native-app")
        self.assertIn("C++", profile.languages)
        self.assertIn("HLSL", profile.languages)
        self.assertIn("CMake", profile.build_systems)
        self.assertIn("python build.py", profile.validation_commands)
        self.assertNotIn("cmake --build build", profile.validation_commands)
        self.assertNotIn("ctest --test-dir build", profile.validation_commands)
        self.assertIn("Dear ImGui", profile.frameworks)
        self.assertIn("Win32 API", profile.frameworks)
        self.assertIn("DirectX", profile.frameworks)
        self.assertIn("MinHook", profile.frameworks)
        self.assertIn("Capstone", profile.frameworks)
        self.assertIn("PE/COFF analysis", profile.frameworks)
        self.assertTrue(any(item.name == "MinHook" for item in profile.dependencies))

    def test_inspect_dependency_profile_prefers_root_powershell_build_runner_for_native_validation(self) -> None:
        manager = WorkspaceManager(self.project_root, self.settings)
        workspace = manager.resolve_workspace("workspace")
        (workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(NativeInspector LANGUAGES CXX)\n",
            encoding="utf-8",
        )
        (workspace / "NativeInspector.sln").write_text(
            "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            encoding="utf-8",
        )
        (workspace / "NativeInspector.vcxproj").write_text("<Project></Project>", encoding="utf-8")
        (workspace / "build.ps1").write_text("Write-Host 'build'\n", encoding="utf-8")

        profile = manager.inspect_dependency_profile(workspace)

        expected = "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1"
        self.assertEqual(profile.validation_commands[0], expected)
        self.assertIn("build.ps1", profile.config_files)
        self.assertIn("CMake", profile.build_systems)
        self.assertIn("Visual Studio / MSBuild", profile.build_systems)
        self.assertNotIn("cmake --build build", profile.validation_commands)
        self.assertNotIn("ctest --test-dir build", profile.validation_commands)
        self.assertNotIn(
            "msbuild NativeInspector.sln /m /p:Configuration=Release",
            profile.validation_commands,
        )
        self.assertNotIn(
            "msbuild NativeInspector.vcxproj /m /p:Configuration=Release",
            profile.validation_commands,
        )

    def test_fix_history_retrieval_preserves_category(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        store.remember_fix(
            project_root=workspace,
            error_signature="ModuleNotFoundError: No module named requests",
            fix_summary="Install requests in the active environment before rerunning validation.",
            evidence="python -m pytest exited with 0 after dependency install",
            confidence=0.92,
            category="dependency",
        )

        hits = store.relevant_fix_history(
            project_root=workspace,
            query="tests fail with ModuleNotFoundError for requests",
            limit=3,
        )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].category, "dependency")

    def test_project_memory_upserts_and_retrieves_notes(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        store.remember_project_note(
            project_root=workspace,
            category="constraint",
            title="Constraint",
            detail="Must stay Windows-first and avoid PowerShell for generated scripts.",
            source="user_request",
            confidence=0.75,
        )
        store.remember_project_note(
            project_root=workspace,
            category="constraint",
            title="Constraint",
            detail="Must stay Windows-first and avoid PowerShell for generated scripts.",
            source="user_request",
            confidence=0.9,
        )

        notes = store.project_memory(project_root=workspace, limit=5)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].category, "constraint")
        self.assertGreaterEqual(notes[0].confidence, 0.9)

        hits = store.relevant_project_memory(
            project_root=workspace,
            query="keep this Windows-first and avoid PowerShell",
            limit=3,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].title, "Constraint")

    def test_memory_manager_updates_and_deletes_notes(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        manager = MemoryManager(workspace)

        note = manager.create_note(
            title="Theme preference",
            content="Use green sparingly and keep dashboards readable.",
            category="preference",
            tags=["ui", "desktop"],
            related_files=["PROJECT_TODO.md"],
        )
        updated = manager.update_note(note.id, pinned=True, confidence=0.95)

        self.assertIsNotNone(updated)
        self.assertTrue(updated.pinned)
        self.assertGreaterEqual(updated.confidence, 0.95)
        self.assertEqual(len(manager.search_notes("green")), 1)
        self.assertTrue(manager.delete_note(note.id))
        self.assertEqual(manager.search_notes("green"), [])

    def test_memory_manager_confines_user_controlled_category_to_memory_dir(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        manager = MemoryManager(workspace)

        note = manager.create_note(
            title="Scoped note",
            content="Keep memory files inside the memory directory.",
            category="../.aegis/project memory",
            tags="safety",
            related_files="PROJECT_TODO.md",
        )

        self.assertNotIn("/", note.id)
        self.assertNotIn("\\", note.id)
        self.assertNotIn("..", note.id)
        self.assertEqual(note.category, "../.aegis/project memory")
        self.assertEqual(note.tags, ["safety"])
        self.assertEqual(note.related_files, ["PROJECT_TODO.md"])
        self.assertTrue((workspace / "memory" / f"{note.id}.json").is_file())
        self.assertFalse((workspace / ".aegis").exists())

    def test_memory_manager_generates_unique_ids_for_same_millisecond(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        manager = MemoryManager(workspace)
        fixed_now = datetime(2026, 5, 8, 12, 0, 0, 123000, tzinfo=timezone.utc)

        with patch("aegis_ai.memory_manager.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fixed_now
            first = manager.create_note("First", "One", "insight")
            second = manager.create_note("Second", "Two", "insight")

        self.assertNotEqual(first.id, second.id)
        self.assertTrue((workspace / "memory" / f"{first.id}.json").is_file())
        self.assertTrue((workspace / "memory" / f"{second.id}.json").is_file())

    def test_memory_manager_ignores_update_attempts_to_mutate_note_identity(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        manager = MemoryManager(workspace)
        note = manager.create_note("Stable", "Keep the id stable.", "insight")

        updated = manager.update_note(note.id, id="../escaped", created_at="changed", confidence=9)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.id, note.id)
        self.assertEqual(updated.created_at, note.created_at)
        self.assertEqual(updated.confidence, 1.0)
        self.assertTrue((workspace / "memory" / f"{note.id}.json").is_file())
        self.assertFalse((workspace / "escaped.json").exists())

    def test_memory_api_coerces_bad_confidence_without_escaping_memory_dir(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        workspace_manager = WorkspaceManager(self.project_root, self.settings)

        with (
            patch.object(main, "workspace_manager", workspace_manager),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/memory",
                params={"workspace_root": str(workspace)},
                json={
                    "title": "API note",
                    "content": "Invalid confidence should not break the endpoint.",
                    "category": "../.aegis/api note",
                    "confidence": "not-a-number",
                    "tags": "api",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["confidence"], 0.8)
        self.assertEqual(payload["tags"], ["api"])
        self.assertTrue((workspace / "memory" / f"{payload['id']}.json").is_file())
        self.assertFalse((workspace / ".aegis").exists())

    def test_memory_manager_degrades_when_memory_storage_path_is_file(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        memory_path = workspace / "memory"
        memory_path.write_text("damaged memory path", encoding="utf-8")

        manager = MemoryManager(workspace)

        self.assertEqual(manager.notes, {})
        self.assertIn("not a directory", manager.storage_warning)
        with self.assertRaisesRegex(OSError, "Could not initialize memory storage"):
            manager.create_note("Blocked", "Cannot write through a file path.", "insight")
        self.assertEqual(memory_path.read_text(encoding="utf-8"), "damaged memory path")

    def test_memory_api_reports_damaged_memory_storage_path(self) -> None:
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").write_text("damaged memory path", encoding="utf-8")
        workspace_manager = WorkspaceManager(self.project_root, self.settings)

        with (
            patch.object(main, "workspace_manager", workspace_manager),
            TestClient(main.app) as client,
        ):
            get_response = client.get("/api/memory", params={"workspace_root": str(workspace)})
            create_response = client.post(
                "/api/memory",
                params={"workspace_root": str(workspace)},
                json={"title": "Blocked", "content": "Cannot write.", "category": "insight"},
            )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["notes"], [])
        self.assertIn("not a directory", "\n".join(get_response.json()["warnings"]))
        self.assertEqual(create_response.status_code, 503)
        self.assertIn("Could not update memory notes", create_response.json()["detail"])
        self.assertIn("not a directory", create_response.json()["detail"])

    def test_repair_attempts_round_trip(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        task_id = store.create_task(mode="develop", workspace_root=workspace, message="Fix failing test")
        store.record_repair_attempt(
            task_id,
            RepairAttempt(
                attempt=1,
                category="test",
                before_signature="AssertionError: expected 1 got 0",
                after_signature="",
                outcome="rolled_back",
                checkpoint="cp-1",
                summary="Repair attempt did not improve validation.",
                created_at="2026-04-21T00:00:00+00:00",
            ),
        )

        attempts = store.repair_attempts(task_id)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].outcome, "rolled_back")
        self.assertEqual(attempts[0].category, "test")

    def test_route_health_signals_cool_down_failing_provider(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="chat", workspace_root=workspace, message="Count to 10")
        store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="ollama:codegemma",
                    provider_label="CodeGemma",
                    provider_api="ollama",
                    model="codegemma:2b",
                    status="failed",
                    error="invalid json",
                ),
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="ollama:codegemma",
                    provider_label="CodeGemma",
                    provider_api="ollama",
                    model="codegemma:2b",
                    status="failed",
                    error="invalid json",
                ),
            ],
        )

        signals = store.route_health_signals(project_root=workspace, limit=20)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].provider_id, "ollama:codegemma")
        self.assertTrue(signals[0].cooldown)
        self.assertGreaterEqual(signals[0].penalty, 6000.0)

    def test_route_quality_includes_context_drilldowns(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="develop", workspace_root=workspace, message="Refactor the app")
        store.record_context_budget(
            task_id=task_id,
            workspace_root=workspace,
            context_budget=ContextBudgetInfo(
                intent="implementation",
                route_role="code",
                strategy="focused code context",
                max_context_tokens=4000,
                estimated_context_tokens=2800,
                estimated_file_tokens=2300,
                reserve_response_tokens=900,
                selected_file_count=2,
                omitted_file_count=1,
                selected_memory_count=1,
                omitted_memory_count=1,
                selected_project_memory_count=1,
                omitted_project_memory_count=0,
                notes=["Large file was clipped."],
                items=[
                    ContextBudgetItemInfo(
                        kind="file",
                        ref="src/App.tsx",
                        estimated_tokens=1500,
                        included=True,
                        reason="route match",
                    ),
                    ContextBudgetItemInfo(
                        kind="file",
                        ref="src/legacy.ts",
                        estimated_tokens=900,
                        included=False,
                        reason="budget limit",
                    ),
                    ContextBudgetItemInfo(
                        kind="memory",
                        ref="architecture-note",
                        estimated_tokens=300,
                        included=True,
                        reason="pinned",
                    ),
                ],
            ),
        )

        quality = store.route_quality(project_root=workspace, limit=20)

        self.assertEqual(len(quality.context_drilldowns), 1)
        drilldown = quality.context_drilldowns[0]
        self.assertEqual(drilldown.task_id, task_id)
        self.assertEqual(drilldown.route_role, "code")
        self.assertGreater(drilldown.utilization or 0.0, 0.9)
        self.assertEqual(drilldown.omitted_file_count, 1)
        self.assertTrue(any("src/App.tsx" in item for item in drilldown.largest_refs))
        self.assertTrue(any("omitted" in item for item in drilldown.recommendations))

    def test_route_quality_includes_token_calibration_rollups(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="chat", workspace_root=workspace, message="Explain the code")
        store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    input_tokens=3200,
                    output_tokens=128,
                    metadata={
                        "token_estimator_family": "qwen_coder",
                        "token_estimate_source": "provider_profile",
                        "estimated_input_tokens": 3200,
                        "estimated_output_tokens": 128,
                        "reported_input_tokens": 3000,
                        "reported_output_tokens": 120,
                        "reported_token_source": "ollama:chat",
                    },
                )
            ],
        )

        quality = store.route_quality(project_root=workspace, limit=20)

        self.assertEqual(len(quality.token_calibration), 1)
        calibration = quality.token_calibration[0]
        self.assertEqual(calibration.provider_id, "ollama:qwen")
        self.assertEqual(calibration.calibration_status, "stable")
        self.assertEqual(calibration.calibrated_attempts, 1)
        self.assertIn("qwen_coder:provider_profile", calibration.token_estimator_sources)
        self.assertIn("ollama:chat", calibration.reported_token_sources)
        self.assertAlmostEqual(calibration.average_input_token_error or 0.0, 0.0667)
        self.assertEqual(calibration.reported_input_tokens, 3000)

    def test_route_quality_includes_structured_preview_rollups(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="build", workspace_root=workspace, message="Create a CLI")
        store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    metadata={
                        "structured_preview_delta_count": 3,
                        "structured_preview_char_count": 42,
                        "structured_preview_reset_count": 0,
                        "structured_preview_emitted": True,
                        "structured_preview_retired": False,
                        "structured_preview_final_winner": True,
                    },
                ),
                ModelAttemptInfo(
                    attempt=2,
                    role="code",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="failed",
                    error="invalid structured JSON",
                    metadata={
                        "structured_preview_delta_count": 1,
                        "structured_preview_char_count": 12,
                        "structured_preview_reset_count": 1,
                        "structured_preview_emitted": True,
                        "structured_preview_retired": True,
                        "structured_preview_final_winner": False,
                        "structured_preview_retired_reason": "invalid_structured_json",
                    },
                ),
            ],
        )

        quality = store.route_quality(project_root=workspace, limit=20)

        self.assertEqual(quality.overview.structured_preview_attempts, 2)
        self.assertEqual(quality.overview.structured_preview_retired_attempts, 1)
        self.assertEqual(quality.overview.structured_preview_reset_count, 1)
        self.assertEqual(len(quality.structured_preview), 1)
        preview = quality.structured_preview[0]
        self.assertEqual(preview.provider_id, "ollama:qwen")
        self.assertEqual(preview.previewed_attempts, 2)
        self.assertEqual(preview.final_winning_attempts, 1)
        self.assertEqual(preview.retired_attempts, 1)
        self.assertEqual(preview.reset_count, 1)
        self.assertEqual(preview.delta_count, 4)
        self.assertEqual(preview.char_count, 54)
        self.assertEqual(preview.preview_status, "unstable")
        self.assertIn("invalid_structured_json", preview.retired_reasons)
        self.assertTrue(any("Structured preview" in item for item in quality.recommendations))

    def test_route_health_penalizes_structured_preview_resets(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="build", workspace_root=workspace, message="Create a desktop app")
        store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    metadata={
                        "structured_preview_delta_count": 1,
                        "structured_preview_char_count": 8,
                        "structured_preview_reset_count": 1,
                        "structured_preview_emitted": True,
                        "structured_preview_retired": True,
                        "structured_preview_final_winner": False,
                    },
                ),
                ModelAttemptInfo(
                    attempt=1,
                    role="code",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    metadata={
                        "structured_preview_delta_count": 1,
                        "structured_preview_char_count": 7,
                        "structured_preview_reset_count": 1,
                        "structured_preview_emitted": True,
                        "structured_preview_retired": True,
                        "structured_preview_final_winner": False,
                    },
                ),
            ],
        )

        signals = store.route_health_signals(project_root=workspace, limit=20)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].structured_preview_attempts, 2)
        self.assertEqual(signals[0].structured_preview_retired_attempts, 2)
        self.assertEqual(signals[0].structured_preview_reset_count, 2)
        self.assertGreater(signals[0].penalty, 0.0)
        self.assertIn("Structured preview", signals[0].recommendation)

    def test_route_quality_includes_token_calibration_trends(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        old_task_id = store.create_task(mode="chat", workspace_root=workspace, message="Explain yesterday")
        store.record_model_attempts(
            task_id=old_task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    metadata={
                        "estimated_input_tokens": 1000,
                        "estimated_output_tokens": 100,
                        "reported_input_tokens": 1000,
                        "reported_output_tokens": 100,
                        "reported_token_source": "ollama:chat",
                    },
                )
            ],
        )
        new_task_id = store.create_task(mode="chat", workspace_root=workspace, message="Explain today")
        store.record_model_attempts(
            task_id=new_task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="ollama:qwen",
                    provider_label="Qwen Local",
                    provider_api="ollama",
                    model="qwen2.5-coder:7b",
                    status="succeeded",
                    metadata={
                        "estimated_input_tokens": 1500,
                        "estimated_output_tokens": 180,
                        "reported_input_tokens": 1000,
                        "reported_output_tokens": 100,
                        "reported_token_source": "ollama:chat",
                    },
                )
            ],
        )
        with store._session() as conn:
            conn.execute(
                "update model_attempt_telemetry set created_at = ? where task_id = ?",
                ("2026-04-28T12:00:00+00:00", old_task_id),
            )
            conn.execute(
                "update model_attempt_telemetry set created_at = ? where task_id = ?",
                ("2026-04-29T12:00:00+00:00", new_task_id),
            )

        quality = store.route_quality(project_root=workspace, limit=20)

        trends = [
            bucket
            for bucket in quality.token_calibration_trends
            if bucket.provider_id == "ollama:qwen" and bucket.model == "qwen2.5-coder:7b"
        ]
        self.assertEqual([bucket.period_start for bucket in trends], ["2026-04-29", "2026-04-28"])
        self.assertEqual(trends[0].calibration_status, "drift")
        self.assertEqual(trends[0].trend_direction, "worsening")
        self.assertEqual(trends[1].calibration_status, "stable")
        self.assertEqual(trends[1].trend_direction, "baseline")

    def test_prune_telemetry_snapshots_keeps_recent_windows(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        snapshots = [
            store.refresh_telemetry_snapshot(project_root=workspace, route_quality_limit=200 + index)
            for index in range(3)
        ]
        now = datetime.now(timezone.utc)
        with store._session() as conn:
            conn.execute(
                "update telemetry_snapshots set updated_at = ? where id = ?",
                ((now - timedelta(days=40)).isoformat(), snapshots[0].id),
            )
            conn.execute(
                "update telemetry_snapshots set updated_at = ? where id = ?",
                ((now - timedelta(days=10)).isoformat(), snapshots[1].id),
            )
            conn.execute(
                "update telemetry_snapshots set updated_at = ? where id = ?",
                (now.isoformat(), snapshots[2].id),
            )

        prune = store.prune_telemetry_snapshots(project_root=workspace, max_snapshots=2, retention_days=30)

        self.assertEqual(prune.deleted_count, 1)
        self.assertEqual(prune.retained_count, 2)
        self.assertEqual(prune.retention_max_snapshots, 2)
        self.assertEqual(prune.retention_days, 30)
        self.assertIn("retained 2", prune.recommendation)
        with store._session() as conn:
            count = conn.execute("select count(*) from telemetry_snapshots").fetchone()[0]
        self.assertEqual(count, 2)

    def test_fallback_inspector_attaches_adapter_health_to_candidates(self) -> None:
        store = EventStore(self.project_root, self.settings)
        workspace = (self.project_root / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        task_id = store.create_task(mode="chat", workspace_root=workspace, message="Use the cloud route")
        store.record_event(
            task_id,
            kind="planner",
            title="Task plan prepared",
            status="ok",
            detail="Task plan prepared.",
            payload={
                "intent": "conversation",
                "objective": "Use the cloud route",
                "workflow": "answer",
                "routing": {
                    "task_role": "chat",
                    "privacy_mode": "cloud-allowed",
                    "fallback_roles": ["fallback"],
                    "candidates": [
                        {
                            "candidate_id": "primary:chat",
                            "role": "chat",
                            "provider_hint": "OpenAI Primary",
                            "required_capabilities": ["chat"],
                            "privacy_mode": "cloud-allowed",
                            "reason": "Use the primary cloud model.",
                            "confidence": 0.9,
                        }
                    ],
                },
            },
        )
        store.record_model_attempts(
            task_id=task_id,
            workspace_root=workspace,
            attempts=[
                ModelAttemptInfo(
                    attempt=1,
                    role="chat",
                    provider_id="openai:primary",
                    provider_label="OpenAI Primary",
                    provider_api="openai",
                    model="gpt-test",
                    status="skipped",
                    error="OPENAI_API_KEY is not set.",
                    metadata={"candidate_id": "primary:chat", "registry_resolved": True},
                )
            ],
        )

        inspector = store.fallback_inspector(
            project_root=workspace,
            limit=5,
            adapter_health=[
                ModelAdapterHealthInfo(
                    provider_id="openai:primary",
                    provider_label="OpenAI Primary",
                    api="openai",
                    model="gpt-test",
                    status="missing_secret",
                    message="Provider is missing OPENAI_API_KEY.",
                    secret_env="OPENAI_API_KEY",
                    recommendation="Set OPENAI_API_KEY before using this provider.",
                    preflight_skips=1,
                )
            ],
        )

        candidate = inspector.tasks[0].candidates[0]
        self.assertEqual(candidate.adapter_status, "missing_secret")
        self.assertEqual(candidate.adapter_secret_env, "OPENAI_API_KEY")
        self.assertEqual(candidate.adapter_preflight_skips, 1)
        self.assertTrue(any("missing its required secret" in item for item in inspector.tasks[0].recommendations))
        self.assertTrue(any("missing provider secrets" in item for item in inspector.recommendations))


if __name__ == "__main__":
    unittest.main()
