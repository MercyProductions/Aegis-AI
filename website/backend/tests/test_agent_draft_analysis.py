from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent_runtime import AgentDraft
from aegis_ai.agent_runtime.draft_analysis import (
    draft_change_paths,
    draft_change_payload_size,
    draft_has_concrete_source_surface,
    draft_has_desktop_host_surface,
    draft_stack_families,
    important_project_path,
    looks_like_next_workspace,
    manifest_contract_value,
    manifest_stack_family,
    stack_family_label,
    workspace_stack_family,
)
from aegis_ai.schemas import FileChange, WorkspaceFile, WorkspaceProjectManifest


class AgentDraftAnalysisTests(unittest.TestCase):
    def test_normalizes_change_paths_and_counts_material_payload(self) -> None:
        draft = AgentDraft(
            reply="Prepared changes.",
            changes=[
                FileChange(action="create", path="Src\\App.tsx", content="abc"),
                FileChange(action="update", path="/README.md", content="hello"),
                FileChange(action="delete", path="old.txt"),
            ],
        )

        self.assertEqual(draft_change_paths(draft), {"src/app.tsx", "readme.md", "old.txt"})
        self.assertEqual(draft_change_payload_size(draft), 8)

    def test_detects_concrete_source_surface_without_counting_metadata(self) -> None:
        metadata_only = AgentDraft(
            reply="Prepared metadata.",
            changes=[
                FileChange(action="create", path="README.md", content="# Project\n"),
                FileChange(action="create", path="pyproject.toml", content="[project]\n"),
            ],
        )
        source_draft = AgentDraft(
            reply="Prepared source.",
            changes=[FileChange(action="create", path="src/tool/main.py", content="print('ok')\n")],
        )

        self.assertFalse(draft_has_concrete_source_surface(metadata_only))
        self.assertTrue(draft_has_concrete_source_surface(source_draft))

    def test_manifest_stack_family_honors_mission_contract_and_preset(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="ops-desk",
            title="Ops Desk",
            preset_id="electron-react-ts",
            preset_label="Electron React TypeScript",
            framework="Electron + Vite + React",
            language="TypeScript",
            tags=["desktop", "electron", "react"],
            mission_contract={"stack_family": "desktop", "preset_id": "electron-react-ts"},
        )
        native_manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="native-tool",
            title="Native Tool",
            preset_id="cpp-cmake-dll",
            preset_label="C++ CMake DLL",
            framework="CMake",
            language="C++17",
            mission_contract={"stack_family": "native-cpp"},
        )

        self.assertEqual(manifest_contract_value(manifest, "stack_family"), "desktop")
        self.assertEqual(manifest_stack_family(manifest), "desktop")
        self.assertEqual(manifest_stack_family(native_manifest), "native-cpp")
        self.assertEqual(manifest_stack_family(None), "")

    def test_draft_stack_families_detects_language_and_desktop_host_surface(self) -> None:
        draft = AgentDraft(
            reply="Prepared Electron app.",
            changes=[
                FileChange(action="create", path="package.json", content="{}"),
                FileChange(action="create", path="electron.vite.config.ts", content="export default {}\n"),
                FileChange(action="create", path="src/main/index.ts", content="import { app } from 'electron';\n"),
                FileChange(action="create", path="src/renderer/src/App.tsx", content="export function App(){return null}\n"),
            ],
        )

        self.assertEqual(draft_stack_families(draft), {"web", "desktop"})
        self.assertTrue(draft_has_desktop_host_surface(draft))

    def test_workspace_stack_family_prioritizes_real_project_markers(self) -> None:
        self.assertEqual(
            workspace_stack_family(
                [
                    WorkspaceFile(path="pyproject.toml", kind="text", size=220),
                    WorkspaceFile(path="src/aegis_app/main.py", kind="text", size=480),
                    WorkspaceFile(path="build.py", kind="text", size=340),
                ]
            ),
            "python",
        )
        self.assertEqual(
            workspace_stack_family(
                [
                    WorkspaceFile(path="CMakeLists.txt", kind="text", size=220),
                    WorkspaceFile(path="src/main.cpp", kind="text", size=480),
                    WorkspaceFile(path="build.py", kind="text", size=340),
                ]
            ),
            "native-cpp",
        )
        self.assertEqual(
            workspace_stack_family(
                [
                    WorkspaceFile(path="package.json", kind="text", size=320),
                    WorkspaceFile(path="electron.vite.config.ts", kind="text", size=180),
                    WorkspaceFile(path="src/main/index.ts", kind="text", size=420),
                    WorkspaceFile(path="src/preload/index.ts", kind="text", size=220),
                ]
            ),
            "desktop",
        )

    def test_important_project_path_and_next_workspace_detection_are_stable(self) -> None:
        self.assertTrue(important_project_path(".aegis/project.json"))
        self.assertTrue(important_project_path("src/main.cpp"))
        self.assertTrue(important_project_path("package.json"))
        self.assertFalse(important_project_path("notes/sketch.txt"))
        self.assertTrue(
            looks_like_next_workspace(
                [
                    WorkspaceFile(path="package.json", kind="text", size=320),
                    WorkspaceFile(path="next.config.ts", kind="text", size=180),
                    WorkspaceFile(path="app/page.tsx", kind="text", size=640),
                ]
            )
        )

    def test_stack_family_label_keeps_user_facing_guardrail_terms(self) -> None:
        self.assertEqual(stack_family_label("native-cpp"), "native C++/CMake/Visual Studio")
        self.assertEqual(stack_family_label("desktop"), "desktop application")
        self.assertEqual(stack_family_label("unknown-family"), "unknown-family")


if __name__ == "__main__":
    unittest.main()
