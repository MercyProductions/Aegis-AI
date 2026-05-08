from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent import AgentDraft, AgentEngine
from aegis_ai.llm import LocalModelStatus
from aegis_ai.schemas import (
    AgentRequest,
    CommandRun,
    CompletionQualityInfo,
    FileChange,
    WorkspaceFile,
    WorkspaceInstructionFile,
    WorkspaceDependencyProfile,
    WorkspaceInstructionStatusInfo,
    WorkspaceProjectManifest,
    WorkspaceValidationPlanInfo,
    WorkspaceValidationPlanStep,
)
from aegis_ai.settings import Settings


class AgentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = AgentEngine(
            Path(self.tempdir.name),
            Settings(_env_file=None, default_workspace="workspace"),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_explicit_context_paths_are_selected_before_heuristics(self) -> None:
        workspace = Path(self.tempdir.name) / "context-workspace"
        workspace.mkdir()
        files = [
            WorkspaceFile(path="README.md", kind="text", size=120),
            WorkspaceFile(path="package.json", kind="text", size=180),
            WorkspaceFile(path="src/target.ts", kind="text", size=240),
            WorkspaceFile(path="src/ignored.ts", kind="text", size=240),
            WorkspaceFile(path="assets/logo.png", kind="binary", size=1024),
        ]

        selected = self.engine._select_context_files(
            workspace,
            files,
            "read the readme",
            limit=3,
            context_paths=[
                "src\\target.ts",
                "src/target.ts",
                "../secret.txt",
                "assets/logo.png",
                "missing.ts",
            ],
        )

        self.assertGreaterEqual(len(selected), 1)
        self.assertEqual(selected[0].path, "src/target.ts")
        self.assertNotIn("assets/logo.png", [item.path for item in selected])

    def test_agent_request_accepts_pinned_context_paths(self) -> None:
        request = AgentRequest(message="explain this file", context_paths=["src/App.tsx"])

        self.assertEqual(request.context_paths, ["src/App.tsx"])

    def test_accepts_answer_key_for_general_questions(self) -> None:
        draft = self.engine._parse_model_payload(
            {"answer": "Yes. The app can answer normal questions now.", "changes": [], "commands": []},
            request_message="what is a vector database?",
            mode="chat",
        )

        self.assertEqual(draft.reply, "Yes. The app can answer normal questions now.")
        self.assertEqual(draft.changes, [])

    def test_code_snippet_becomes_reply_when_no_file_change_was_requested(self) -> None:
        draft = self.engine._parse_model_payload(
            {"code": "console.log('hello world');", "language": "javascript", "changes": [], "commands": []},
            request_message="write me the code to print hello world to console",
            mode="chat",
        )

        self.assertIn("```javascript", draft.reply)
        self.assertIn("console.log('hello world');", draft.reply)
        self.assertEqual(draft.changes, [])

    def test_code_snippet_becomes_file_when_file_change_was_requested(self) -> None:
        draft = self.engine._parse_model_payload(
            {"code": "console.log('hello world');", "language": "javascript", "changes": [], "commands": []},
            request_message="create a script that prints hello world",
            mode="develop",
        )

        self.assertEqual(draft.reply, "Prepared a javascript script file for review.")
        self.assertNotIn("Created", draft.reply)
        self.assertEqual(len(draft.changes), 1)
        self.assertEqual(draft.changes[0].path, "script.js")

    def test_prompt_path_request_with_apply_writes_to_prompt_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "Obfuscation" / "TypeScriptObfuscator"
            engine = AgentEngine(
                base,
                Settings(
                    _env_file=None,
                    default_workspace=str(base),
                    aegis_router_execution_enabled=False,
                ),
            )

            class FakeModel:
                label = "Fake Model"
                endpoint = "memory://fake"
                api = "fake"
                model = "fake-code"

                async def status(self) -> LocalModelStatus:
                    return LocalModelStatus(ready=True, message="ready")

                async def complete_json(self, messages):
                    return {
                        "reply": "Prepared the TypeScript obfuscator file for review.",
                        "plan": ["Create the requested obfuscator file"],
                        "changes": [
                            {
                                "action": "create",
                                "path": "obfuscate.ts",
                                "summary": "Create a small TypeScript obfuscator entry point.",
                                "content": "export function obfuscate(source: string): string { return source; }\n",
                            }
                        ],
                        "commands": [],
                    }

            engine.model = FakeModel()  # type: ignore[assignment]

            response = asyncio.run(
                engine.run(
                    AgentRequest(
                        message=f"create a TypeScript obfuscator file here {target}",
                        mode="develop",
                        apply_changes=True,
                    )
                )
            )

            self.assertEqual(Path(response.workspace_root), target.resolve())
            self.assertEqual(response.applied, ["create: obfuscate.ts"])
            self.assertTrue((target / "obfuscate.ts").exists())
            self.assertIn("export function obfuscate", (target / "obfuscate.ts").read_text(encoding="utf-8"))
            self.assertIn("Auralith Prime applied 1 file change", response.reply)

    def test_sanitize_model_change_paths_strips_workspace_folder_prefix(self) -> None:
        workspace = Path(self.tempdir.name) / "sample-app"
        draft = AgentDraft(
            reply="Created files.",
            changes=[
                FileChange(action="create", path="sample-app/src/main.py", content="print('ok')\n"),
            ],
        )

        sanitized = self.engine._sanitize_model_change_paths(draft, workspace)

        self.assertEqual([change.path for change in sanitized.changes], ["src/main.py"])
        self.assertTrue(any("Normalized model change path" in warning for warning in sanitized.warnings))

    def test_sanitize_model_change_paths_strips_absolute_workspace_prefix(self) -> None:
        workspace = Path(self.tempdir.name) / "sample-app"
        draft = AgentDraft(
            reply="Created files.",
            changes=[
                FileChange(
                    action="create",
                    path=f"{workspace.as_posix()}/src/main.py",
                    content="print('ok')\n",
                ),
            ],
        )

        sanitized = self.engine._sanitize_model_change_paths(draft, workspace)

        self.assertEqual([change.path for change in sanitized.changes], ["src/main.py"])

    def test_sanitize_model_change_paths_skips_absolute_outside_workspace(self) -> None:
        workspace = Path(self.tempdir.name) / "sample-app"
        draft = AgentDraft(
            reply="Created files.",
            changes=[
                FileChange(action="create", path="C:/Temp/outside.py", content="print('no')\n"),
            ],
        )

        sanitized = self.engine._sanitize_model_change_paths(draft, workspace)

        self.assertEqual(sanitized.changes, [])
        self.assertTrue(any("outside the workspace" in warning for warning in sanitized.warnings))

    def test_explicit_path_words_do_not_contaminate_project_type_detection(self) -> None:
        message = (
            r"At this path C:\Users\gabri\Desktop\Aegis\Website\ChatBot\workspace\sample "
            "create a Python CLI app that accepts --name, prints a greeting, includes a smoke test, and run validation."
        )
        workspace = Path(self.tempdir.name) / "sample"
        fallback = self.engine._fallback_draft(message, "build", workspace, [])

        self.assertFalse(self.engine._request_mentions_web_project(message))
        self.assertIn("build.py", [change.path for change in fallback.changes])
        self.assertFalse(self.engine._draft_is_weak_project_shape(fallback, message, "build", []))

    def test_python_cli_project_requires_package_metadata_and_validation(self) -> None:
        message = "Create a Python CLI app that accepts --name, prints a greeting, includes a smoke test, and run validation."
        thin_draft = AgentDraft(
            reply="Created a small app.",
            changes=[
                FileChange(action="create", path="main.py", content="print('hello')\n"),
                FileChange(action="create", path="build.py", content="print('ok')\n"),
                FileChange(action="create", path="tests/test_smoke.py", content="def test_smoke(): assert True\n"),
            ],
        )

        self.assertTrue(self.engine._draft_is_weak_project_shape(thin_draft, message, "build", []))

    def test_project_draft_without_source_surface_is_weak(self) -> None:
        message = "Create a full Python CLI app that accepts --name, prints a greeting, includes a smoke test, and run validation."
        metadata_only = AgentDraft(
            reply="Prepared metadata.",
            changes=[
                FileChange(action="create", path="README.md", content="# Tool\n"),
                FileChange(action="create", path="pyproject.toml", content="[project]\nname='tool'\n"),
                FileChange(action="create", path=".gitignore", content="__pycache__/\n"),
            ],
        )

        self.assertTrue(self.engine._draft_is_weak_project_shape(metadata_only, message, "build", []))

    def test_manifest_contract_blocks_accidental_web_draft_for_native_workspace(self) -> None:
        message = "continue the roadmap and add a frontend-style diagnostics dashboard without changing stacks"
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="aegis-dll",
            title="Aegis DLL",
            preset_id="cpp-cmake-dll",
            preset_label="C++ CMake DLL",
            framework="CMake",
            language="C++17",
            mission_contract={
                "preset_id": "cpp-cmake-dll",
                "stack_family": "native-cpp",
                "artifact_type": "dll",
            },
        )
        web_draft = AgentDraft(
            reply="Added the dashboard.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"next build"}}\n'),
                FileChange(action="create", path="app/page.tsx", content="export default function Page(){return <main/>}\n"),
                FileChange(action="create", path="app/globals.css", content="body{margin:0}\n"),
            ],
        )

        reasons = self.engine._draft_manifest_contract_mismatch_reasons(web_draft, message, manifest)

        self.assertTrue(any("mission contract" in reason for reason in reasons))
        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                web_draft,
                message,
                "build",
                [],
                project_manifest=manifest,
            )
        )

    def test_dll_prompt_counts_as_native_and_web_negation_suppresses_dashboard_route(self) -> None:
        message = (
            "At this path C:\\Users\\gabri\\Desktop\\Aegis Native DLL "
            "refine my existing DLL project, add a diagnostics dashboard UI, build it, and do not make a website."
        )

        self.assertTrue(self.engine._request_mentions_cpp_project(message))
        self.assertFalse(self.engine._request_mentions_web_project(message))

    def test_completion_quality_flags_web_drift_for_existing_dll_request(self) -> None:
        workspace = Path(self.tempdir.name) / "existing-dll-quality"
        workspace.mkdir()
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="include/aegis/library.h", kind="text", size=220),
            WorkspaceFile(path="library/library.cpp", kind="text", size=480),
            WorkspaceFile(path="host/main.cpp", kind="text", size=420),
        ]
        draft = AgentDraft(
            reply="Added a dashboard.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"vite build"}}\n'),
                FileChange(action="create", path="src/App.tsx", content="export function App(){return <main/>}\n"),
                FileChange(action="create", path="src/styles.css", content="body{margin:0}\n"),
            ],
        )

        quality = self.engine._completion_quality(
            request=AgentRequest(
                message=(
                    "refine my existing DLL project, add a diagnostics dashboard UI, build it, "
                    "and do not make a website"
                ),
                workspace_root=str(workspace),
                mode="build",
                run_validation=True,
            ),
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=None,
            workspace_root=workspace,
            workspace_files=files,
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertLessEqual(quality.score, 0.34)
        self.assertTrue(any("not to make a website" in reason.lower() for reason in quality.reasons))
        self.assertTrue(any("native c++" in reason.lower() for reason in quality.reasons))

    def test_desktop_prompt_rejects_static_website_draft(self) -> None:
        draft = AgentDraft(
            reply="Created a desktop app.",
            changes=[
                FileChange(action="create", path="index.html", content="<main>Desktop dashboard</main>\n"),
                FileChange(action="create", path="styles.css", content="body{margin:0}\n"),
                FileChange(action="create", path="app.js", content="console.log('ready')\n"),
            ],
        )

        reasons = self.engine._draft_stack_mismatch_reasons(
            draft,
            "Create a Windows desktop app with a settings GUI and build it.",
        )

        self.assertTrue(any("packaged desktop" in reason.lower() for reason in reasons))

    def test_desktop_prompt_allows_electron_host_surface(self) -> None:
        draft = AgentDraft(
            reply="Created an Electron desktop app.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"vite build"}}\n'),
                FileChange(action="create", path="electron.vite.config.ts", content="export default {}\n"),
                FileChange(action="create", path="src/main/index.ts", content="import { app } from 'electron';\n"),
                FileChange(action="create", path="src/preload/index.ts", content="export {}\n"),
                FileChange(action="create", path="src/renderer/src/App.tsx", content="export function App(){return <main/>}\n"),
            ],
        )

        self.assertEqual(
            self.engine._draft_stack_mismatch_reasons(
                draft,
                "Create an Electron React desktop app with TypeScript.",
            ),
            [],
        )

    def test_completion_quality_flags_static_site_for_desktop_request(self) -> None:
        workspace = Path(self.tempdir.name) / "desktop-quality"
        workspace.mkdir()
        draft = AgentDraft(
            reply="Built a desktop app.",
            changes=[
                FileChange(action="create", path="README.md", content="# App\n"),
                FileChange(action="create", path="index.html", content="<main>Tool</main>\n"),
                FileChange(action="create", path="styles.css", content="body{margin:0}\n"),
                FileChange(action="create", path="app.js", content="console.log('tool')\n"),
            ],
        )

        quality = self.engine._completion_quality(
            request=AgentRequest(
                message="Create a polished Windows desktop app with a settings GUI and build it.",
                workspace_root=str(workspace),
                mode="build",
                run_validation=True,
            ),
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=None,
            workspace_root=workspace,
            workspace_files=[],
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("packaged desktop" in reason.lower() for reason in quality.reasons))

    def test_manifest_stack_family_treats_electron_as_desktop(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="ops-desk",
            title="Ops Desk",
            preset_id="electron-react-ts",
            preset_label="Electron React TypeScript",
            framework="Electron + Vite + React",
            language="TypeScript",
            tags=["desktop", "electron", "react"],
            mission_contract={
                "schema": "aegis.mission_contract.v1",
                "preset_id": "electron-react-ts",
                "stack_family": "desktop",
                "stack_locks": ["stack-lock:desktop"],
            },
        )

        self.assertEqual(self.engine._manifest_stack_family(manifest), "desktop")

    def test_desktop_manifest_rejects_plain_static_site_drift(self) -> None:
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
        draft = AgentDraft(
            reply="Refreshed the app.",
            changes=[
                FileChange(action="create", path="index.html", content="<main>Ops Desk</main>\n"),
                FileChange(action="create", path="styles.css", content="body{margin:0}\n"),
                FileChange(action="create", path="app.js", content="console.log('ready')\n"),
            ],
        )

        reasons = self.engine._draft_manifest_contract_mismatch_reasons(
            draft,
            "continue polishing the desktop app",
            manifest,
        )

        self.assertTrue(any("desktop application" in reason.lower() for reason in reasons))

    def test_desktop_workspace_stack_family_detects_electron_host(self) -> None:
        files = [
            WorkspaceFile(path="package.json", kind="text", size=320),
            WorkspaceFile(path="electron.vite.config.ts", kind="text", size=180),
            WorkspaceFile(path="src/main/index.ts", kind="text", size=420),
            WorkspaceFile(path="src/preload/index.ts", kind="text", size=220),
            WorkspaceFile(path="src/renderer/src/App.tsx", kind="text", size=640),
        ]

        self.assertEqual(self.engine._workspace_stack_family(files), "desktop")

    def test_workspace_stack_family_ignores_generic_build_py_validator(self) -> None:
        python_files = [
            WorkspaceFile(path="pyproject.toml", kind="text", size=220),
            WorkspaceFile(path="src/aegis_app/main.py", kind="text", size=480),
            WorkspaceFile(path="tests/test_smoke.py", kind="text", size=260),
            WorkspaceFile(path="build.py", kind="text", size=340),
        ]
        dotnet_files = [
            WorkspaceFile(path="AegisTool/AegisTool.csproj", kind="text", size=320),
            WorkspaceFile(path="AegisTool/Program.cs", kind="text", size=440),
            WorkspaceFile(path="build.py", kind="text", size=340),
        ]
        native_files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=220),
            WorkspaceFile(path="src/main.cpp", kind="text", size=480),
            WorkspaceFile(path="build.py", kind="text", size=340),
        ]

        self.assertEqual(self.engine._workspace_stack_family(python_files), "python")
        self.assertEqual(self.engine._workspace_stack_family(dotnet_files), "dotnet")
        self.assertEqual(self.engine._workspace_stack_family(native_files), "native-cpp")

    def test_python_workspace_with_build_py_does_not_get_native_drift_warning(self) -> None:
        files = [
            WorkspaceFile(path="pyproject.toml", kind="text", size=220),
            WorkspaceFile(path="src/aegis_app/main.py", kind="text", size=480),
            WorkspaceFile(path="tests/test_smoke.py", kind="text", size=260),
            WorkspaceFile(path="build.py", kind="text", size=340),
        ]
        draft = AgentDraft(
            reply="Improved the Python tool.",
            changes=[
                FileChange(action="update", path="src/aegis_app/main.py", content="def main():\n    return 'ok'\n"),
                FileChange(action="update", path="tests/test_smoke.py", content="def test_main():\n    assert True\n"),
            ],
        )

        reasons = self.engine._draft_task_adherence_reasons(
            draft,
            "continue improving this Python CLI and run validation",
            files,
        )

        self.assertFalse(any("native" in reason.lower() for reason in reasons))

    def test_destructive_draft_blocks_unrequested_source_delete(self) -> None:
        message = "continue improving the native C++ app and run validation"
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="aegis-native",
            title="Aegis Native",
            preset_id="cpp-game-loop-cmake",
            preset_label="C++ Game Loop",
            framework="CMake",
            language="C++17",
            mission_contract={"stack_family": "native-cpp", "preset_id": "cpp-game-loop-cmake"},
        )
        destructive_draft = AgentDraft(
            reply="Cleaned up files.",
            changes=[
                FileChange(action="delete", path="src/main.cpp"),
                FileChange(action="update", path="CMakeLists.txt", content=""),
                FileChange(action="create", path="src/app.cpp", content="int run(){ return 0; }\n"),
            ],
        )

        reasons = self.engine._draft_destructive_change_reasons(destructive_draft, message, manifest)

        self.assertTrue(any("src/main.cpp" in reason for reason in reasons))
        self.assertTrue(any("CMakeLists.txt" in reason for reason in reasons))

    def test_destructive_draft_allows_explicit_delete_request(self) -> None:
        message = "delete the unused legacy source file src/legacy.cpp and update the build"
        draft = AgentDraft(
            reply="Removed legacy file.",
            changes=[
                FileChange(action="delete", path="src/legacy.cpp"),
                FileChange(action="update", path="CMakeLists.txt", content="cmake_minimum_required(VERSION 3.20)\n"),
            ],
        )

        self.assertEqual(self.engine._draft_destructive_change_reasons(draft, message), [])

    def test_completion_quality_flags_destructive_draft_for_autopilot(self) -> None:
        workspace = Path(self.tempdir.name) / "native-quality"
        workspace.mkdir()
        draft = AgentDraft(
            reply="Made a risky cleanup.",
            changes=[
                FileChange(action="delete", path="src/main.cpp"),
                FileChange(action="create", path="src/replacement.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        quality = self.engine._completion_quality(
            request=AgentRequest(message="continue improving this C++ project", workspace_root=str(workspace), mode="build"),
            mode="build",
            draft=draft,
            applied=[],
            validation=None,
            workspace_root=workspace,
            workspace_files=[],
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("delete" in reason.lower() for reason in quality.reasons))

    def test_existing_project_continuation_rejects_fresh_starter_scaffold(self) -> None:
        message = "continue improving this project and run validation"
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
            WorkspaceFile(path="src/app.cpp", kind="text", size=260),
        ]
        draft = AgentDraft(
            reply="Restarted the app scaffold.",
            changes=[
                FileChange(action="create", path="README.md", content="# App\n"),
                FileChange(action="create", path="CMakeLists.txt", content="cmake_minimum_required(VERSION 3.20)\n"),
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
                FileChange(action="create", path=".gitignore", content="build/\n"),
            ],
        )

        reasons = self.engine._draft_existing_project_scaffold_drift_reasons(draft, message, files)

        self.assertTrue(any("fresh starter scaffold" in reason for reason in reasons))

    def test_existing_project_allows_explicit_rebuild_from_scratch(self) -> None:
        message = "rebuild from scratch as a fresh CMake starter project"
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
        ]
        draft = AgentDraft(
            reply="Created fresh starter.",
            changes=[
                FileChange(action="create", path="README.md", content="# App\n"),
                FileChange(action="create", path="CMakeLists.txt", content="cmake_minimum_required(VERSION 3.20)\n"),
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertEqual(self.engine._draft_existing_project_scaffold_drift_reasons(draft, message, files), [])

    def test_existing_project_no_change_continuation_preserves_stack_and_proposes_validation(self) -> None:
        workspace = Path(self.tempdir.name) / "existing-native-continuation"
        workspace.mkdir()
        (workspace / "build.py").write_text("print('ok')\n", encoding="utf-8")
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
            WorkspaceFile(path="build.py", kind="text", size=80),
        ]

        draft = self.engine._existing_project_no_change_continuation_draft(
            original_draft=AgentDraft(reply="No changes."),
            fallback=AgentDraft(reply="Preserved existing project.", changes=[]),
            message="continue improving this existing project and build it",
            mode="build",
            workspace_root=workspace,
            workspace_files=files,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.changes, [])
        self.assertIn("strict existing-project continuation pass", draft.reply)
        self.assertTrue(any("native-cpp" in item for item in draft.plan))
        self.assertEqual(draft.proposed_commands[0]["command"], "python build.py")
        self.assertTrue(any("prepared a strict existing-project continuation pass" in warning for warning in draft.warnings))

    def test_existing_project_no_change_continuation_uses_manifest_validation_command(self) -> None:
        workspace = Path(self.tempdir.name) / "manifest-continuation"
        workspace.mkdir()
        files = [
            WorkspaceFile(path="ExistingNativeDll.vcxproj", kind="text", size=220),
            WorkspaceFile(path="src/dllmain.cpp", kind="text", size=320),
        ]
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="existing-native-dll",
            title="Existing Native DLL",
            preset_id="cpp-cmake-dll",
            preset_label="C++ CMake DLL",
            framework="CMake",
            language="C++17",
            validation_command="python build.py",
            mission_contract={
                "preset_id": "cpp-cmake-dll",
                "stack_family": "native-cpp",
                "artifact_type": "dll",
            },
        )

        draft = self.engine._existing_project_no_change_continuation_draft(
            original_draft=AgentDraft(reply="No changes."),
            fallback=AgentDraft(reply="Preserved existing project.", changes=[]),
            message="work on this dll and validate it",
            mode="build",
            workspace_root=workspace,
            workspace_files=files,
            project_manifest=manifest,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.proposed_commands[0]["command"], "python build.py")
        self.assertTrue(any("Existing Native DLL" in item for item in draft.plan))
        self.assertTrue(any("native-cpp" in item for item in draft.plan))

    def test_existing_project_no_change_continuation_handles_bare_continue_in_build_mode(self) -> None:
        workspace = Path(self.tempdir.name) / "bare-continue-existing-project"
        workspace.mkdir()
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
        ]

        draft = self.engine._existing_project_no_change_continuation_draft(
            original_draft=AgentDraft(reply="No changes."),
            fallback=AgentDraft(reply="Preserved existing project.", changes=[]),
            message="continue",
            mode="build",
            workspace_root=workspace,
            workspace_files=files,
        )

        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.proposed_commands[0]["command"], "cmake -S . -B build && cmake --build build --config Release")
        self.assertIn("strict existing-project continuation pass", draft.reply)

    def test_existing_project_no_change_continuation_skips_plain_chat_and_empty_workspace(self) -> None:
        workspace = Path(self.tempdir.name) / "empty-continuation"
        workspace.mkdir()

        self.assertIsNone(
            self.engine._existing_project_no_change_continuation_draft(
                original_draft=AgentDraft(reply="No changes."),
                fallback=AgentDraft(reply="No changes."),
                message="what is a vector database?",
                mode="chat",
                workspace_root=workspace,
                workspace_files=[],
            )
        )
        self.assertIsNone(
            self.engine._existing_project_no_change_continuation_draft(
                original_draft=AgentDraft(reply="No changes."),
                fallback=AgentDraft(reply="No changes."),
                message="build this project",
                mode="build",
                workspace_root=workspace,
                workspace_files=[],
            )
        )

    def test_completion_quality_flags_existing_project_starter_drift(self) -> None:
        workspace = Path(self.tempdir.name) / "existing-quality"
        workspace.mkdir()
        draft = AgentDraft(
            reply="Made a starter.",
            changes=[
                FileChange(action="create", path="README.md", content="# App\n"),
                FileChange(action="create", path="CMakeLists.txt", content="cmake_minimum_required(VERSION 3.20)\n"),
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
                FileChange(action="create", path=".gitignore", content="build/\n"),
            ],
        )
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
            WorkspaceFile(path="src/app.cpp", kind="text", size=260),
        ]

        quality = self.engine._completion_quality(
            request=AgentRequest(message="continue improving this C++ project", workspace_root=str(workspace), mode="build"),
            mode="build",
            draft=draft,
            applied=[],
            validation=None,
            workspace_root=workspace,
            workspace_files=files,
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("starter scaffold" in reason.lower() for reason in quality.reasons))

    def test_existing_file_create_action_flags_overwrite(self) -> None:
        message = "continue improving this native C++ project and run validation"
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
        ]
        draft = AgentDraft(
            reply="Updated the entry point.",
            changes=[
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        reasons = self.engine._draft_existing_file_overwrite_reasons(draft, message, files)

        self.assertTrue(any("create on existing important file" in reason for reason in reasons))

    def test_existing_file_create_action_allows_explicit_replace(self) -> None:
        message = "replace src/main.cpp with a clean rewritten entry point and run validation"
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
        ]
        draft = AgentDraft(
            reply="Replaced the entry point.",
            changes=[
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        self.assertEqual(self.engine._draft_existing_file_overwrite_reasons(draft, message, files), [])

    def test_completion_quality_flags_existing_file_overwrite(self) -> None:
        workspace = Path(self.tempdir.name) / "existing-overwrite-quality"
        workspace.mkdir()
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=120),
            WorkspaceFile(path="src/main.cpp", kind="text", size=240),
        ]
        draft = AgentDraft(
            reply="Updated the project.",
            changes=[
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        quality = self.engine._completion_quality(
            request=AgentRequest(message="continue improving this C++ project", workspace_root=str(workspace), mode="build"),
            mode="build",
            draft=draft,
            applied=[],
            validation=None,
            workspace_root=workspace,
            workspace_files=files,
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("create on existing" in reason.lower() for reason in quality.reasons))

    def test_project_manifest_context_includes_mission_contract(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="aegis-native-tool",
            title="Aegis Native Tool",
            preset_id="cpp-game-loop-cmake",
            preset_label="C++ Game Loop",
            framework="CMake",
            language="C++17",
            original_prompt="Create a native C++ game-tool project and validate it.",
            mission_contract={
                "preset_id": "cpp-game-loop-cmake",
                "stack_family": "native-cpp",
                "artifact_type": "desktop app",
            },
        )

        context = self.engine._project_manifest_context(manifest)

        self.assertIn("Mission contract:", context)
        self.assertIn("stack_family=native-cpp", context)
        self.assertIn("preserve this stack", context)
        self.assertIn("Original task:", context)

    def test_final_reply_reports_applied_validated_work(self) -> None:
        reply = self.engine._final_reply(
            "Aegis prepared a local starter for the workspace. You can preview the files and apply them when you are ready.",
            applied=["README.md", "build.py", "src/main.cpp"],
            validation=CommandRun(
                command="python build.py",
                cwd=str(Path(self.tempdir.name)),
                allowed=True,
                exit_code=0,
            ),
            completion_quality=CompletionQualityInfo(status="ready", score=1.0),
        )

        self.assertIn("Auralith Prime applied 3 file changes", reply)
        self.assertIn("validation passed", reply)
        self.assertIn("python build.py", reply)
        self.assertNotIn("preview", reply.lower())

    def test_dependency_install_recipe_detects_node_workspace_without_node_modules(self) -> None:
        workspace = Path(self.tempdir.name) / "node-app"
        workspace.mkdir()
        (workspace / "package.json").write_text(
            '{"scripts":{"build":"vite build"},"dependencies":{"@vitejs/plugin-react":"latest"}}\n',
            encoding="utf-8",
        )

        recipe = self.engine._dependency_install_recipe(workspace)

        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(recipe.command, "npm install")
        self.assertEqual(recipe.source, "install")

    def test_dependency_install_recipe_skips_node_workspace_with_node_modules(self) -> None:
        workspace = Path(self.tempdir.name) / "node-app-installed"
        workspace.mkdir()
        (workspace / "package.json").write_text('{"scripts":{"build":"vite build"}}\n', encoding="utf-8")
        (workspace / "node_modules").mkdir()

        self.assertIsNone(self.engine._dependency_install_recipe(workspace))

    def test_model_messages_include_full_build_contract_without_name_error(self) -> None:
        workspace = Path(self.tempdir.name)
        request = AgentRequest(
            message="Complete a full barber styled website for Rick Cullers",
            workspace_root=str(workspace),
            mode="build",
        )
        files: list[WorkspaceFile] = []
        dependency_profile = self.engine.workspace.inspect_dependency_profile(workspace)
        task_plan = self.engine.task_planner.build_plan(
            message=request.message,
            mode="build",
            workspace_files=files,
            context_files=[],
            project_manifest=None,
            dependency_profile=dependency_profile,
        )

        messages = self.engine._model_messages(
            request,
            "build",
            workspace,
            files,
            [],
            [],
            [],
            [],
            task_plan,
        )

        self.assertIn("Full-build contract:", messages[1]["content"])
        self.assertIn("Return concrete complete-file changes", messages[1]["content"])

    def test_model_messages_lock_explicit_dll_path_and_native_contract(self) -> None:
        workspace = Path(self.tempdir.name) / "Aegis Game Dumper"
        (workspace / ".aegis").mkdir(parents=True)
        (workspace / "library").mkdir()
        (workspace / "host").mkdir()
        (workspace / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
        (workspace / "library" / "library.cpp").write_text("int aegis_library(){return 1;}\n", encoding="utf-8")
        (workspace / "host" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="aegis-game-dumper",
            title="Aegis Game Dumper",
            preset_id="cpp-cmake-dll",
            preset_label="C++ CMake DLL",
            framework="CMake",
            language="C++17",
            validation_command="python build.py",
            mission_contract={
                "preset_id": "cpp-cmake-dll",
                "stack_family": "native-cpp",
                "artifact_type": "dll",
                "original_prompt": "Refine the existing DLL project and keep it native.",
            },
        )
        (workspace / ".aegis" / "project.json").write_text(
            manifest.model_dump_json(by_alias=True, indent=2),
            encoding="utf-8",
        )
        request = AgentRequest(
            message=f"at this path {workspace} at this path refine my existing DLL project and build it",
            workspace_root=str(workspace),
            mode="build",
        )
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=40),
            WorkspaceFile(path="library/library.cpp", kind="text", size=40),
            WorkspaceFile(path="host/main.cpp", kind="text", size=40),
        ]
        dependency_profile = self.engine.workspace.inspect_dependency_profile(workspace)
        task_plan = self.engine.task_planner.build_plan(
            message=request.message,
            mode="build",
            workspace_files=files,
            context_files=[],
            project_manifest=manifest,
            dependency_profile=dependency_profile,
        )

        messages = self.engine._model_messages(
            request,
            "build",
            workspace,
            files,
            [],
            [],
            [],
            [],
            task_plan,
        )
        content = messages[1]["content"]

        self.assertIn("Mission continuity contract:", content)
        self.assertIn(f"Workspace root: {workspace}", content)
        self.assertIn(f"Explicit path resolved from the prompt: {workspace}", content)
        self.assertIn("Words after that explicit path are instructions", content)
        self.assertIn("Native/C++ guardrail", content)
        self.assertIn("do not create package.json, index.html, styles.css, app.js", content)
        self.assertIn("DLL/shared-library guardrail", content)
        self.assertIn("Preserve the manifest validation command", content)
        self.assertNotIn(f"Workspace root: {workspace} at this path", content)

    def test_continue_with_native_manifest_keeps_file_build_contract(self) -> None:
        workspace = Path(self.tempdir.name) / "native-continuation"
        (workspace / ".aegis").mkdir(parents=True)
        (workspace / "src").mkdir()
        (workspace / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
        (workspace / "src" / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="native-continuation",
            title="Native Continuation",
            preset_id="cpp-cmake-cli",
            preset_label="C++ CMake CLI",
            framework="CMake",
            language="C++17",
            validation_command="python build.py",
            mission_contract={
                "preset_id": "cpp-cmake-cli",
                "stack_family": "native-cpp",
                "artifact_type": "console app",
                "original_prompt": "Create and keep extending a native C++ console app.",
            },
        )
        (workspace / ".aegis" / "project.json").write_text(
            manifest.model_dump_json(by_alias=True, indent=2),
            encoding="utf-8",
        )
        request = AgentRequest(message="continue", workspace_root=str(workspace), mode="build")
        files = [
            WorkspaceFile(path="CMakeLists.txt", kind="text", size=40),
            WorkspaceFile(path="src/main.cpp", kind="text", size=40),
        ]
        dependency_profile = self.engine.workspace.inspect_dependency_profile(workspace)
        task_plan = self.engine.task_planner.build_plan(
            message=request.message,
            mode="build",
            workspace_files=files,
            context_files=[],
            project_manifest=manifest,
            dependency_profile=dependency_profile,
        )

        messages = self.engine._model_messages(
            request,
            "build",
            workspace,
            files,
            [],
            [],
            [],
            [],
            task_plan,
        )
        content = messages[1]["content"]

        self.assertEqual(task_plan.intent, "implementation")
        self.assertIn("Mission continuity contract:", content)
        self.assertIn("Workspace manifest is authoritative for continuation", content)
        self.assertIn("If the user says continue, build, repair, validate, or autopilot", content)
        self.assertIn("Native/C++ guardrail", content)
        self.assertIn("Return concrete complete-file changes", content)
        self.assertNotIn("This is not a file-build turn", content)

    def test_project_status_context_surfaces_recent_build_failure(self) -> None:
        workspace = Path(self.tempdir.name) / "cpp-app"
        log_dir = workspace / ".aegis" / "build_logs"
        log_dir.mkdir(parents=True)
        (log_dir / "20260501-validation.md").write_text(
            "# Aegis Build Log\n\n## Validation\n\ncompile error: missing semicolon\n",
            encoding="utf-8",
        )
        (workspace / ".aegis" / "command_history.json").write_text(
            """{
  "schema": "aegis.command_history.v1",
  "commands": [
    {
      "kind": "validation",
      "command": "python build.py",
      "status": "failed",
      "category": "build",
      "summary": "Compilation failed.",
      "exit_code": 1,
      "build_log_path": ".aegis/build_logs/20260501-validation.md"
    }
  ]
}
""",
            encoding="utf-8",
        )
        (workspace / ".aegis" / "known_errors.json").write_text(
            """{
  "schema": "aegis.known_errors.v1",
  "errors": [
    {
      "category": "build",
      "command": "python build.py",
      "summary": "Compiler stopped on missing semicolon.",
      "exit_code": 1,
      "output_excerpt": "src/main.cpp: expected ';'",
      "build_log_path": ".aegis/build_logs/20260501-validation.md",
      "status": "open"
    }
  ]
}
""",
            encoding="utf-8",
        )

        context = self.engine._project_status_context(workspace)

        self.assertIn("Recent command history:", context)
        self.assertIn("Open known errors:", context)
        self.assertIn("python build.py", context)
        self.assertIn(".aegis/build_logs/20260501-validation.md", context)
        self.assertIn("compile error: missing semicolon", context)
        self.assertIn("Build-state rule:", context)

    def test_project_status_context_surfaces_validation_plan_steps(self) -> None:
        workspace = Path(self.tempdir.name) / "validation-plan-app"
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir(parents=True)
        (aegis_dir / "validation_plan.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.validation_plan.v1",
                    "validation_command": "cmake -S . -B build && cmake --build build",
                    "steps": [
                        {
                            "id": "validation-1",
                            "phase": "validation",
                            "command": "cmake -S . -B build",
                            "label": "Configure CMake build directory",
                            "chain_index": 1,
                            "chain_total": 2,
                        },
                        {
                            "id": "validation-2",
                            "phase": "validation",
                            "command": "cmake --build build",
                            "label": "Build CMake project",
                            "chain_index": 2,
                            "chain_total": 2,
                        },
                    ],
                    "last_run": {
                        "status": "failed",
                        "command": "cmake -S . -B build && cmake --build build",
                        "summary": "Compile failed.",
                        "failed_step": "2",
                    },
                }
            ),
            encoding="utf-8",
        )

        context = self.engine._project_status_context(workspace)

        self.assertIn("Validation plan:", context)
        self.assertIn("cmake -S . -B build", context)
        self.assertIn("cmake --build build", context)
        self.assertIn("failed_step=2", context)
        self.assertIn("failed validation-plan step", context)

    def test_instruction_status_checkpoint_surfaces_open_todo_context(self) -> None:
        workspace = Path(self.tempdir.name) / "todo-project"
        workspace.mkdir()
        (workspace / "DONE_ANY_NAME.md").write_text(
            "# Launch Plan\n\n- [x] Create starter shell\n- [ ] Add build command\n- [ ] Validate release build\n",
            encoding="utf-8",
        )
        instruction_files = self.engine.workspace.discover_instruction_files(
            workspace,
            referenced_text="continue from DONE_ANY_NAME.md",
        )

        payload = self.engine._record_instruction_status(
            workspace,
            instruction_files,
            request_message="continue from DONE_ANY_NAME.md",
            validation=None,
            completion_quality=CompletionQualityInfo(
                status="needs_work",
                score=0.42,
                reasons=["Instruction file still has open work."],
                next_actions=["Add build command"],
                should_continue=True,
            ),
            applied=["src/main.cpp"],
        )

        self.assertIsNotNone(payload)
        status = json.loads((workspace / ".aegis" / "instruction_status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["open_items"], 2)
        self.assertEqual(status["completed_items"], 1)
        self.assertIn("Add build command", status["recommendation"])
        context = self.engine._project_status_context(workspace)
        self.assertIn("Instruction file status:", context)
        self.assertIn("DONE_ANY_NAME.md", context)
        self.assertIn("Add build command", context)
        self.assertIn("Completion status: needs_work", context)
        self.assertIn("Instruction-state rule:", context)
        snapshot = self.engine.instruction_status_snapshot(workspace)
        self.assertEqual(snapshot.open_items, 2)
        self.assertEqual(snapshot.files[0].path, "DONE_ANY_NAME.md")
        self.assertTrue(snapshot.completion.get("should_continue"))

    def test_instruction_status_checkpoint_records_validation_result(self) -> None:
        workspace = Path(self.tempdir.name) / "validated-todo-project"
        workspace.mkdir()
        (workspace / "TODO.md").write_text("- [x] Compile executable\n", encoding="utf-8")
        instruction_files = self.engine.workspace.discover_instruction_files(workspace)
        validation = CommandRun(
            command="python build.py",
            cwd=str(workspace),
            allowed=True,
            exit_code=0,
            stdout="passed",
            summary="Build completed successfully.",
            category="success",
        )

        self.engine._record_instruction_status(
            workspace,
            instruction_files,
            request_message="wrap up",
            validation=validation,
            completion_quality=CompletionQualityInfo(
                status="ready",
                score=1.0,
                reasons=["Validation passed."],
                should_continue=False,
            ),
            applied=[],
        )

        context = self.engine._project_status_context(workspace)
        self.assertIn("Instruction file status: 0 open / 1 completed / 1 tracked", context)
        self.assertIn("Last validation: [passed] | python build.py", context)
        self.assertIn("All tracked instruction items are currently complete", context)

    def test_instruction_status_snapshot_accepts_utf8_bom_json(self) -> None:
        workspace = Path(self.tempdir.name) / "bom-instruction-status"
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir(parents=True)
        (aegis_dir / "instruction_status.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.instruction_status.v1",
                    "open_items": 1,
                    "completed_items": 0,
                    "total_items": 1,
                    "files": [
                        {
                            "path": "WORK.md",
                            "open_items": 1,
                            "pending_items": ["Ship the thing"],
                        }
                    ],
                    "recommendation": "Continue the next open instruction item: Ship the thing",
                }
            ),
            encoding="utf-8-sig",
        )

        snapshot = self.engine.instruction_status_snapshot(workspace)

        self.assertEqual(snapshot.open_items, 1)
        self.assertEqual(snapshot.files[0].path, "WORK.md")
        self.assertIn("Ship the thing", snapshot.recommendation)

    def test_instruction_status_snapshot_discovers_unsaved_generic_plan_file(self) -> None:
        workspace = Path(self.tempdir.name) / "unsaved-generic-plan"
        workspace.mkdir()
        (workspace / "whatever.md").write_text(
            """
# Launch Blueprint

## MVP Work Items

- CMake release build
- Console input wait
- Validation transcript
""".strip(),
            encoding="utf-8",
        )

        snapshot = self.engine.instruction_status_snapshot(workspace)

        self.assertEqual(snapshot.schema_version, "aegis.instruction_status.discovered.v1")
        self.assertEqual(snapshot.open_items, 3)
        self.assertEqual(snapshot.files[0].path, "whatever.md")
        self.assertIn("CMake release build", snapshot.files[0].pending_items)
        self.assertTrue(snapshot.completion.get("should_continue"))
        self.assertIn("CMake release build", snapshot.recommendation)
        self.assertFalse((workspace / ".aegis" / "instruction_status.json").exists())

    def test_validation_plan_snapshot_surfaces_repair_steps(self) -> None:
        workspace = Path(self.tempdir.name) / "validation-plan-profile"
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir(parents=True)
        (aegis_dir / "validation_plan.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.validation_plan.v1",
                    "validation_command": "cmake -S . -B build && cmake --build build",
                    "steps": [
                        {
                            "id": "configure",
                            "phase": "validation",
                            "command": "cmake -S . -B build",
                            "label": "Configure CMake build folder",
                            "source_command": "cmake -S . -B build && cmake --build build",
                            "chain_index": 1,
                            "chain_total": 2,
                        },
                        {
                            "id": "build",
                            "phase": "validation",
                            "command": "cmake --build build",
                            "label": "Build executable",
                            "source_command": "cmake -S . -B build && cmake --build build",
                            "chain_index": 2,
                            "chain_total": 2,
                        },
                    ],
                    "last_run": {
                        "status": "failed",
                        "command": "cmake --build build",
                        "failed_step": "build",
                        "summary": "compiler not found",
                    },
                }
            ),
            encoding="utf-8",
        )

        snapshot = self.engine.validation_plan_snapshot(workspace)
        context = self.engine._project_status_context(workspace)

        self.assertEqual(snapshot.schema_version, "aegis.validation_plan.v1")
        self.assertEqual(len(snapshot.steps), 2)
        self.assertEqual(snapshot.steps[1].command, "cmake --build build")
        self.assertEqual(snapshot.last_run["failed_step"], "build")
        self.assertIn("Validation plan:", context)
        self.assertIn("failed validation-plan step", context)

    def test_workspace_readiness_classifies_ready_and_repair_states(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema="aegis.project.v1",
            project_name="console-tool",
            validation_command="cmake --build build",
        )
        dependency_profile = WorkspaceDependencyProfile(
            config_files=["CMakeLists.txt"],
            validation_commands=["cmake --build build"],
        )
        instruction_status = WorkspaceInstructionStatusInfo(
            schema="aegis.instruction_status.v1",
            completed_items=2,
            total_items=2,
            completion={"status": "ready", "should_continue": False},
        )
        validation_plan = WorkspaceValidationPlanInfo(
            schema="aegis.validation_plan.v1",
            validation_command="cmake --build build",
            steps=[
                WorkspaceValidationPlanStep(
                    id="build",
                    phase="validation",
                    command="cmake --build build",
                    label="Build executable",
                )
            ],
            last_run={"status": "passed", "command": "cmake --build build"},
        )

        ready = self.engine.workspace_readiness_snapshot(
            manifest=manifest,
            dependency_profile=dependency_profile,
            instruction_status=instruction_status,
            validation_plan=validation_plan,
        )
        self.assertEqual(ready.status, "ready")
        self.assertGreaterEqual(ready.score, 85)
        self.assertIn("validated", ready.summary)

        validation_plan.last_run = {
            "status": "failed",
            "command": "cmake --build build",
            "failed_step": "build",
        }
        repair = self.engine.workspace_readiness_snapshot(
            manifest=manifest,
            dependency_profile=dependency_profile,
            instruction_status=instruction_status,
            validation_plan=validation_plan,
        )
        self.assertEqual(repair.status, "needs_repair")
        self.assertLessEqual(repair.score, 35)
        self.assertIn("build", repair.next_action)

    def test_workspace_readiness_uses_passed_command_history(self) -> None:
        dependency_profile = WorkspaceDependencyProfile(
            config_files=["CMakeLists.txt"],
            validation_commands=["cmake -S . -B build && cmake --build build"],
        )
        readiness = self.engine.workspace_readiness_snapshot(
            manifest=None,
            dependency_profile=dependency_profile,
            instruction_status=WorkspaceInstructionStatusInfo(),
            validation_plan=WorkspaceValidationPlanInfo(),
            command_history={
                "schema": "aegis.command_history.v1",
                "validation_command": "cmake -S . -B build && cmake --build build",
                "commands": [
                    {
                        "kind": "validation",
                        "command": "cmake -S . -B build && cmake --build build",
                        "status": "passed",
                    }
                ],
            },
        )

        self.assertEqual(readiness.status, "ready")
        self.assertGreaterEqual(readiness.score, 85)
        self.assertTrue(any("Latest validation passed" in signal for signal in readiness.signals))

    def test_workspace_readiness_uses_discovered_plan_before_unconfigured_state(self) -> None:
        workspace = Path(self.tempdir.name) / "plan-before-config"
        workspace.mkdir()
        (workspace / "anything.md").write_text(
            """
# Launch Blueprint

## MVP Work Items

- CMake release build
- Console input wait
""".strip(),
            encoding="utf-8",
        )

        readiness = self.engine.workspace_readiness_for_workspace(workspace)

        self.assertEqual(readiness.status, "needs_work")
        self.assertIn("tracked project work", readiness.summary)
        self.assertIn("CMake release build", readiness.next_action)

    def test_project_status_context_surfaces_readiness_without_metadata_todo_noise(self) -> None:
        workspace = Path(self.tempdir.name) / "readiness-context"
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir(parents=True)
        (workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(ReadinessContext LANGUAGES CXX)\n",
            encoding="utf-8",
        )
        (aegis_dir / "project.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.project.v1",
                    "project_name": "readiness-context",
                    "validation_command": "cmake --build build",
                }
            ),
            encoding="utf-8",
        )
        (aegis_dir / "ROADMAP.md").write_text(
            "# Roadmap\n\n"
            "Preset: C++ CMake CLI\n"
            "Framework: CMake\n"
            "Package manager: None\n\n"
            "- [x] Create scaffold\n"
            "- [ ] Add a smoke test\n",
            encoding="utf-8",
        )
        instruction_files = self.engine.workspace.discover_instruction_files(workspace)

        self.engine._record_instruction_status(
            workspace,
            instruction_files,
            request_message="continue",
            validation=None,
            completion_quality=CompletionQualityInfo(
                status="needs_work",
                score=0.7,
                reasons=["Roadmap still has an open item."],
                next_actions=["Add a smoke test"],
                should_continue=True,
            ),
            applied=["src/main.cpp"],
        )

        context = self.engine._project_status_context(workspace)

        self.assertIn("Workspace readiness: needs_work", context)
        self.assertIn("Readiness next action: Continue the next open instruction item: Add a smoke test", context)
        self.assertIn("Add a smoke test", context)
        self.assertNotIn("Preset: C++ CMake CLI", context)
        self.assertNotIn("Framework: CMake", context)
        self.assertIn("Instruction-state rule:", context)

    def test_model_messages_include_project_build_state_context(self) -> None:
        workspace = Path(self.tempdir.name) / "cpp-app"
        log_dir = workspace / ".aegis" / "build_logs"
        log_dir.mkdir(parents=True)
        (log_dir / "latest.md").write_text("## Validation\nlink error: unresolved external symbol\n", encoding="utf-8")
        (workspace / ".aegis" / "command_history.json").write_text(
            """{
  "schema": "aegis.command_history.v1",
  "commands": [
    {
      "kind": "validation",
      "command": "cmake --build build --config Release",
      "status": "failed",
      "category": "build",
      "summary": "Link failed.",
      "exit_code": 1,
      "build_log_path": ".aegis/build_logs/latest.md"
    }
  ]
}
""",
            encoding="utf-8",
        )
        request = AgentRequest(message="continue and fix the build", workspace_root=str(workspace), mode="build")
        files: list[WorkspaceFile] = []
        dependency_profile = self.engine.workspace.inspect_dependency_profile(workspace)
        task_plan = self.engine.task_planner.build_plan(
            message=request.message,
            mode="build",
            workspace_files=files,
            context_files=[],
            project_manifest=None,
            dependency_profile=dependency_profile,
        )

        messages = self.engine._model_messages(
            request,
            "build",
            workspace,
            files,
            [],
            [],
            [],
            [],
            task_plan,
        )

        self.assertIn("Project build and validation state:", messages[1]["content"])
        self.assertIn("cmake --build build --config Release", messages[1]["content"])
        self.assertIn("link error: unresolved external symbol", messages[1]["content"])

    def test_run_validation_persists_passed_command_history_and_build_log(self) -> None:
        workspace = Path(self.tempdir.name) / "agent-validation-pass"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "print(\'agent validation pass\')"',
            label="Agent validation pass",
            source="manual",
        )
        events: list[dict] = []

        def emit(kind: str, title: str, **kwargs) -> None:
            events.append({"kind": kind, "title": title, **kwargs})

        run = self.engine._run_validation(workspace, emit, manual=True)

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.exit_code, 0, run.stderr)
        history = json.loads((workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        latest = history["commands"][-1]
        self.assertEqual(latest["status"], "passed")
        self.assertEqual(latest["command"], run.command)
        self.assertTrue(latest["build_log_path"].startswith(".aegis/build_logs/"))
        self.assertTrue((workspace / latest["build_log_path"]).exists())
        self.assertFalse((workspace / ".aegis" / "known_errors.json").exists())
        self.assertIn("agent validation pass", self.engine._project_status_context(workspace))
        self.assertTrue(any(event.get("payload", {}).get("build_log_path") for event in events))

    def test_run_validation_persists_chained_command_steps(self) -> None:
        workspace = Path(self.tempdir.name) / "agent-validation-chain"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "print(\'configure ok\')" && python -c "print(\'build ok\')"',
            label="Agent chained validation",
            source="manual",
        )

        def emit(kind: str, title: str, **kwargs) -> None:
            pass

        run = self.engine._run_validation(workspace, emit, manual=True)

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.exit_code, 0, run.stderr)
        self.assertEqual(len(run.steps), 2)
        self.assertIn("configure ok", run.stdout)
        self.assertIn("build ok", run.stdout)
        self.assertTrue(all(step["ok"] for step in run.steps))

        history = json.loads((workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        latest = history["commands"][-1]
        self.assertEqual(len(latest["steps"]), 2)
        self.assertTrue(all(step["ok"] for step in latest["steps"]))
        build_log = (workspace / latest["build_log_path"]).read_text(encoding="utf-8")
        self.assertIn("## Command Steps", build_log)
        self.assertIn("configure ok", build_log)

    def test_failed_chained_validation_targets_failed_step(self) -> None:
        workspace = Path(self.tempdir.name) / "agent-validation-chain-fail"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "print(\'configure ok\')" && python -c "import sys; print(\'build failed\'); sys.exit(3)"',
            label="Agent failing chained validation",
            source="manual",
        )

        def emit(kind: str, title: str, **kwargs) -> None:
            pass

        run = self.engine._run_validation(workspace, emit, manual=True)

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.exit_code, 3)
        self.assertEqual(run.failed_step, "2")
        self.assertIn("sys.exit", run.failed_step_command)
        self.assertIn("failed at step 2", run.summary)

        history = json.loads((workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        latest = history["commands"][-1]
        self.assertEqual(latest["failed_step"], "2")
        self.assertIn("sys.exit", latest["failed_step_command"])
        self.assertEqual(len(latest["steps"]), 2)

        known = json.loads((workspace / ".aegis" / "known_errors.json").read_text(encoding="utf-8"))
        error = known["errors"][-1]
        self.assertEqual(error["failed_step"], "2")
        self.assertIn("sys.exit", error["failed_step_command"])

        readiness = self.engine.workspace_readiness_for_workspace(workspace)
        self.assertEqual(readiness.status, "needs_repair")
        self.assertIn("step 2", readiness.next_action)
        self.assertIn("sys.exit", readiness.next_action)
        context = self.engine._project_status_context(workspace)
        self.assertIn("failed_step=step 2", context)

    def test_run_validation_extracts_diagnostics_for_repair_context(self) -> None:
        workspace = Path(self.tempdir.name) / "agent-validation-diagnostics"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "import sys; print(\'src/main.cpp(12,34): error C2143: syntax error: missing semicolon\'); sys.exit(7)"',
            label="Agent diagnostic validation",
            source="manual",
        )
        events: list[dict] = []

        def emit(kind: str, title: str, **kwargs) -> None:
            events.append({"kind": kind, "title": title, **kwargs})

        run = self.engine._run_validation(workspace, emit, manual=True)

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.exit_code, 7)
        self.assertEqual(len(run.diagnostics), 1)
        diagnostic = run.diagnostics[0]
        self.assertEqual(diagnostic["file"], "src/main.cpp")
        self.assertEqual(diagnostic["line"], 12)
        self.assertEqual(diagnostic["column"], 34)
        self.assertEqual(diagnostic["severity"], "error")
        self.assertEqual(diagnostic["code"], "C2143")
        self.assertIn("missing semicolon", diagnostic["message"])

        history = json.loads((workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        latest = history["commands"][-1]
        self.assertEqual(latest["diagnostics"][0]["file"], "src/main.cpp")
        known = json.loads((workspace / ".aegis" / "known_errors.json").read_text(encoding="utf-8"))
        self.assertEqual(known["errors"][-1]["diagnostics"][0]["code"], "C2143")
        build_log = (workspace / latest["build_log_path"]).read_text(encoding="utf-8")
        self.assertIn("## Diagnostics", build_log)
        self.assertIn("src/main.cpp:12:34 error C2143", build_log)
        readiness = self.engine.workspace_readiness_for_workspace(workspace)
        self.assertEqual(readiness.status, "needs_repair")
        self.assertIn("src/main.cpp:12:34 error C2143", readiness.next_action)
        self.assertTrue(any("src/main.cpp:12:34 error C2143" in blocker for blocker in readiness.blockers))
        context = self.engine._project_status_context(workspace)
        self.assertIn("diagnostic=src/main.cpp:12:34 error C2143", context)
        self.assertTrue(any(event.get("payload", {}).get("diagnostics") for event in events))

        planner_message = self.engine._planner_message_with_workspace_readiness("continue", workspace, [])
        self.assertIn("Repair brief: Repair diagnostic src/main.cpp:12:34 error C2143; rerun validation", planner_message)
        task_plan = self.engine.task_planner.build_plan(
            message=planner_message,
            mode="build",
            workspace_files=self.engine.workspace.scan(workspace, 200),
            context_files=[],
            project_manifest=self.engine.workspace.load_project_manifest(workspace),
            dependency_profile=self.engine.workspace.inspect_dependency_profile(workspace),
        )
        self.assertEqual(task_plan.intent, "debug_and_repair")
        self.assertIn("Repair diagnostic src/main.cpp:12:34 error C2143", task_plan.objective)
        self.assertIn("rerun validation", task_plan.objective)

    def test_run_validation_persists_failed_known_error_and_log_context(self) -> None:
        workspace = Path(self.tempdir.name) / "agent-validation-fail"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "import sys; print(\'agent validation failure\'); sys.exit(7)"',
            label="Agent validation failure",
            source="manual",
        )
        events: list[dict] = []

        def emit(kind: str, title: str, **kwargs) -> None:
            events.append({"kind": kind, "title": title, **kwargs})

        run = self.engine._run_validation(workspace, emit, manual=True)

        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.exit_code, 7)
        history = json.loads((workspace / ".aegis" / "command_history.json").read_text(encoding="utf-8"))
        latest = history["commands"][-1]
        self.assertEqual(latest["status"], "failed")
        self.assertTrue(latest["build_log_path"].startswith(".aegis/build_logs/"))
        known = json.loads((workspace / ".aegis" / "known_errors.json").read_text(encoding="utf-8"))
        error = known["errors"][-1]
        self.assertEqual(error["status"], "open")
        self.assertEqual(error["command"], run.command)
        self.assertEqual(error["build_log_path"], latest["build_log_path"])
        context = self.engine._project_status_context(workspace)
        self.assertIn("Open known errors:", context)
        self.assertIn("agent validation failure", context)
        self.assertIn(latest["build_log_path"], context)

    def test_full_website_project_rejects_tiny_model_draft(self) -> None:
        draft = AgentDraft(
            reply="I added a starter file.",
            changes=[
                FileChange(
                    action="create",
                    path="index.html",
                    summary="Create a small placeholder page.",
                    content="<h1>Rick Cullers</h1>",
                )
            ],
        )

        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Complete a full barber styled website for Rick Cullers",
                "build",
                [],
            )
        )

    def test_browser_extension_project_rejects_thin_model_draft(self) -> None:
        message = "Create a Chrome browser extension with manifest v3 and validate it."
        thin_draft = AgentDraft(
            reply="Created extension files.",
            changes=[
                FileChange(action="create", path="README.md", content="# Extension\n"),
                FileChange(action="create", path="popup.html", content="<h1>Hello</h1>\n"),
                FileChange(action="create", path="script.js", content="console.log('hi')\n"),
                FileChange(action="create", path="style.css", content="body {}\n"),
            ],
        )
        fallback = self.engine._fallback_draft(message, "build", Path(self.tempdir.name), [])

        self.assertTrue(self.engine._request_needs_project_shape(message, "build"))
        self.assertTrue(self.engine._draft_is_weak_project_shape(thin_draft, message, "build", []))
        self.assertFalse(self.engine._draft_is_weak_project_shape(fallback, message, "build", []))
        self.assertIn("manifest.json", [change.path for change in fallback.changes])

    def test_explicit_stack_fallbacks_are_not_marked_weak(self) -> None:
        messages = [
            "Create a React Native mobile app with Expo and TypeScript.",
            "Create an Electron React desktop app with TypeScript.",
            "Create a Tauri React desktop app.",
            "Create a C++ DLL shared library with CMake.",
            "Create a Windows kernel driver with a controller app.",
            "Create a Go HTTP API.",
            "Create a Rust CLI app.",
            "Create a C# WPF desktop app.",
            "Create a FastAPI Python API.",
            "Create a Node CLI tool.",
        ]

        for message in messages:
            with self.subTest(message=message):
                fallback = self.engine._fallback_draft(message, "build", Path(self.tempdir.name), [])

                self.assertFalse(self.engine._draft_is_weak_project_shape(fallback, message, "build", []))

    def test_react_native_project_rejects_web_only_draft(self) -> None:
        message = "Create a React Native mobile app with Expo and TypeScript."
        thin_draft = AgentDraft(
            reply="Created a React app.",
            changes=[
                FileChange(action="create", path="package.json", content='{"dependencies":{"react":"latest"}}\n'),
                FileChange(action="create", path="src/main.tsx", content="export function App() { return null; }\n"),
                FileChange(action="create", path="vite.config.ts", content="export default {};\n"),
                FileChange(action="create", path="src/styles.css", content="body {}\n"),
            ],
        )

        self.assertTrue(self.engine._draft_is_weak_project_shape(thin_draft, message, "build", []))

    def test_compact_explicit_project_with_validation_can_be_ready(self) -> None:
        message = "Create a Rust CLI app that prints a greeting, includes tests, and validate it."
        fallback = self.engine._fallback_draft(message, "build", Path(self.tempdir.name), [])

        quality = self.engine._completion_quality(
            request=AgentRequest(message=message, mode="build", run_validation=True),
            mode="build",
            draft=fallback,
            applied=[change.path for change in fallback.changes],
            validation=CommandRun(
                command="cargo test",
                cwd=str(Path(self.tempdir.name)),
                allowed=True,
                exit_code=0,
            ),
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "ready")
        self.assertGreaterEqual(quality.score, 0.8)
        self.assertFalse(quality.should_continue)

    def test_single_script_request_allows_small_draft(self) -> None:
        draft = AgentDraft(
            reply="Created a script.",
            changes=[
                FileChange(
                    action="create",
                    path="hello.py",
                    summary="Create a hello script.",
                    content="print('Hello World')\n",
                )
            ],
        )

        self.assertFalse(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Create a script that prints hello world",
                "develop",
                [],
            )
        )

    def test_existing_next_workspace_rejects_static_html_draft(self) -> None:
        files = [
            WorkspaceFile(path="package.json", kind="text", size=100),
            WorkspaceFile(path="app/page.tsx", kind="text", size=100),
            WorkspaceFile(path="app/layout.tsx", kind="text", size=100),
            WorkspaceFile(path="next.config.mjs", kind="text", size=100),
        ]
        draft = AgentDraft(
            reply="Created static files.",
            changes=[
                FileChange(action="create", path="index.html", content="<main>Website</main>"),
                FileChange(action="create", path="styles.css", content="body { margin: 0; }"),
                FileChange(action="create", path="app.js", content="console.log('ready');"),
            ],
        )

        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Complete a full barber styled website",
                "build",
                files,
            )
        )

    def test_existing_next_workspace_rejects_config_only_draft(self) -> None:
        files = [
            WorkspaceFile(path="package.json", kind="text", size=100),
            WorkspaceFile(path="app/page.tsx", kind="text", size=100),
            WorkspaceFile(path="next.config.mjs", kind="text", size=100),
        ]
        draft = AgentDraft(
            reply="Updated package metadata.",
            changes=[
                FileChange(action="update", path="package.json", content="{\n" + "\"scripts\": {},\n" * 90 + "}\n"),
                FileChange(action="update", path="next.config.mjs", content="const nextConfig = {};\nexport default nextConfig;\n"),
                FileChange(action="create", path="README.md", content="# Site\n" + "Next steps.\n" * 90),
            ],
        )

        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Complete a full barber styled website",
                "build",
                files,
            )
        )

    def test_generic_website_rejects_package_dependent_framework_draft(self) -> None:
        draft = AgentDraft(
            reply="Created a Next-style starter.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"next build"},"dependencies":{"next":"latest"}}\n'),
                FileChange(action="create", path="next.config.js", content="module.exports = {};\n"),
                FileChange(action="create", path="src/pages/index.tsx", content="<main>" + "Barber website. " * 250 + "</main>"),
                FileChange(action="create", path="src/styles/globals.css", content="body { margin: 0; }\n" * 100),
            ],
        )

        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Create a complete barber styled website, use whatever language you think is best.",
                "build",
                [],
            )
        )

    def test_explicit_next_website_allows_package_dependent_framework_draft(self) -> None:
        draft = AgentDraft(
            reply="Created a Next starter.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"next build"},"dependencies":{"next":"latest"}}\n'),
                FileChange(action="create", path="next.config.js", content="module.exports = {};\n"),
                FileChange(action="create", path="src/pages/index.tsx", content="<main>" + "Next website. " * 250 + "</main>"),
                FileChange(action="create", path="src/styles/globals.css", content="body { margin: 0; }\n" * 100),
            ],
        )

        self.assertFalse(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Create a complete Next.js barber styled website.",
                "build",
                [],
            )
        )

    def test_cpp_project_requires_entry_and_build_file(self) -> None:
        draft = AgentDraft(
            reply="Added docs.",
            changes=[
                FileChange(action="create", path="README.md", content="# Hello\n"),
                FileChange(action="create", path=".gitignore", content="build/\n"),
                FileChange(action="create", path="notes.txt", content="Run the project.\n"),
            ],
        )

        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Create a C++ console app with an sln that prints hello world",
                "build",
                [],
            )
        )

    def test_cpp_request_rejects_web_heavy_mixed_stack_draft(self) -> None:
        draft = AgentDraft(
            reply="Created the app.",
            changes=[
                FileChange(action="create", path="package.json", content='{"scripts":{"build":"vite build"}}\n'),
                FileChange(action="create", path="index.html", content="<div id='root'></div>\n"),
                FileChange(action="create", path="src/main.tsx", content="export function App(){ return null; }\n"),
                FileChange(action="create", path="styles.css", content="body { margin: 0; }\n" * 60),
                FileChange(action="create", path="src/main.cpp", content="int main(){ return 0; }\n"),
            ],
        )

        reasons = self.engine._draft_stack_mismatch_reasons(
            draft,
            "Create a C++ console project with an sln that prints hello world and waits for user input.",
        )

        self.assertTrue(reasons)
        self.assertTrue(
            self.engine._draft_is_weak_project_shape(
                draft,
                "Create a C++ console project with an sln that prints hello world and waits for user input.",
                "build",
                [],
            )
        )

    def test_cpp_console_request_requires_requested_input_pause(self) -> None:
        draft = AgentDraft(
            reply="Created a C++ console app.",
            changes=[
                FileChange(action="create", path="CMakeLists.txt", content="add_executable(app src/main.cpp)\n"),
                FileChange(action="create", path="src/main.cpp", content="#include <iostream>\nint main(){ std::cout << \"hello\"; return 0; }\n"),
                FileChange(action="create", path="README.md", content="# App\n"),
            ],
        )

        quality = self.engine._completion_quality(
            request=AgentRequest(
                message="Create a C++ console app that prints hello world and requires user input to close.",
                mode="build",
                run_validation=False,
            ),
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=None,
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("user input" in reason.lower() for reason in quality.reasons))

    def test_completion_quality_continues_thin_project_pass(self) -> None:
        request = AgentRequest(
            message="Complete a full barber styled website for Rick Cullers",
            mode="build",
            run_validation=True,
        )
        draft = AgentDraft(
            reply="Built the first pass.",
            changes=[
                FileChange(action="create", path="app/page.tsx", content="<main>" + "Barber shop. " * 100 + "</main>"),
                FileChange(action="create", path="app/layout.tsx", content="export default function Layout(){ return null; }\n"),
                FileChange(action="create", path="app/globals.css", content="body { margin: 0; }\n" * 80),
            ],
        )

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=None,
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("validation" in reason.lower() for reason in quality.reasons))

    def test_completion_quality_ready_after_large_validated_project_pass(self) -> None:
        request = AgentRequest(
            message="Complete a full barber styled website for Rick Cullers",
            mode="build",
            run_validation=True,
        )
        draft = AgentDraft(
            reply="Built the site.",
            changes=[
                FileChange(action="create", path="app/page.tsx", content="<main>" + "section " * 500 + "</main>"),
                FileChange(action="create", path="app/layout.tsx", content="export default function Layout(){ return null; }\n" * 20),
                FileChange(action="create", path="app/globals.css", content="body { margin: 0; }\n" * 120),
                FileChange(action="create", path="components/hero.tsx", content="export function Hero(){ return null; }\n" * 30),
                FileChange(action="create", path="components/services.tsx", content="export function Services(){ return null; }\n" * 30),
                FileChange(action="create", path="README.md", content="# Rick Cullers\n" * 80),
            ],
        )
        validation = CommandRun(command="npm run build", cwd=str(Path(self.tempdir.name)), allowed=True, exit_code=0)

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=validation,
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "ready")
        self.assertFalse(quality.should_continue)
        self.assertGreaterEqual(quality.score, 0.8)

    def test_completion_quality_continues_when_autopilot_todo_has_open_items(self) -> None:
        workspace = Path(self.tempdir.name) / "todo-autopilot"
        workspace.mkdir()
        (workspace / "TODO.md").write_text(
            "# Project TODO\n\n"
            "- [x] Create project shell\n"
            "- [ ] Add booking form\n"
            "- [ ] Run final build validation\n",
            encoding="utf-8",
        )
        request = AgentRequest(
            message=(
                "continue\n\n"
                "Autopilot continuation context: implement and validate the open project instruction file tasks."
            ),
            mode="build",
            run_validation=True,
        )
        draft = AgentDraft(
            reply="Validated the current build.",
            changes=[
                FileChange(action="update", path="app/page.tsx", content="<main>" + "done " * 400 + "</main>"),
                FileChange(action="update", path="README.md", content="# Done\n" * 80),
            ],
        )
        validation = CommandRun(command="npm run build", cwd=str(workspace), allowed=True, exit_code=0)

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=validation,
            workspace_root=workspace,
            workspace_files=[],
        )

        self.assertEqual(quality.status, "needs_work")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("open tracked item" in reason for reason in quality.reasons))
        self.assertTrue(any("Add booking form" in action for action in quality.next_actions))

    def test_completion_quality_ignores_completed_todo_items(self) -> None:
        workspace = Path(self.tempdir.name) / "completed-todo"
        workspace.mkdir()
        (workspace / "TODO.md").write_text(
            "# Project TODO\n\n"
            "- [x] Create project shell\n"
            "- [x] Add booking form\n"
            "- [x] Run final build validation\n",
            encoding="utf-8",
        )
        request = AgentRequest(
            message=(
                "continue\n\n"
                "Autopilot continuation context: implement and validate the open project instruction file tasks."
            ),
            mode="build",
            run_validation=True,
        )
        draft = AgentDraft(
            reply="Validated the current build.",
            changes=[
                FileChange(action="update", path="app/page.tsx", content="<main>" + "done " * 400 + "</main>"),
                FileChange(action="update", path="README.md", content="# Done\n" * 80),
            ],
        )
        validation = CommandRun(command="npm run build", cwd=str(workspace), allowed=True, exit_code=0)

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=validation,
            workspace_root=workspace,
            workspace_files=[],
        )

        self.assertFalse(any("open tracked item" in reason for reason in quality.reasons))

    def test_instruction_context_tells_autopilot_to_check_off_completed_items(self) -> None:
        context = self.engine._instruction_file_context(
            [
                WorkspaceInstructionFile(
                    path="TODO.md",
                    title="Project TODO",
                    kind="todo",
                    score=0.9,
                    pending_count=1,
                    total_items=2,
                    pending_items=["Add booking form"],
                    summary="1 open / 2 tracked item(s)",
                    excerpt="- [ ] Add booking form",
                )
            ]
        )

        self.assertIn("Open items: Add booking form", context)
        self.assertIn("from [ ] to [x]", context)
        self.assertIn("never mark unchecked work complete", context)

    def test_broad_continue_planner_message_mentions_todo_checkoff(self) -> None:
        planner_message = self.engine._planner_message_with_instruction_files(
            "continue",
            [
                WorkspaceInstructionFile(
                    path="TODO.md",
                    title="Project TODO",
                    kind="todo",
                    score=0.9,
                    pending_count=1,
                    total_items=2,
                    pending_items=["Run final validation"],
                    summary="1 open / 2 tracked item(s)",
                    excerpt="- [ ] Run final validation",
                )
            ],
        )

        self.assertIn("Open tasks: Run final validation", planner_message)
        self.assertIn("update the instruction/TODO file", planner_message)
        self.assertIn("[ ] to [x]", planner_message)

    def test_broad_continue_planner_message_uses_workspace_readiness_next_action(self) -> None:
        workspace = Path(self.tempdir.name) / "readiness-continue"
        workspace.mkdir()
        (workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(ReadinessContinue LANGUAGES CXX)\n",
            encoding="utf-8",
        )
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir()
        (aegis_dir / "command_history.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.command_history.v1",
                    "validation_command": "cmake -S . -B build && cmake --build build",
                    "commands": [
                        {
                            "kind": "validation",
                            "command": "cmake -S . -B build && cmake --build build",
                            "status": "failed",
                            "summary": "Compile failed.",
                            "exit_code": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        planner_message = self.engine._planner_message_with_workspace_readiness("continue", workspace, [])

        self.assertIn("Workspace readiness continuation context", planner_message)
        self.assertIn("Readiness status: needs_repair", planner_message)
        self.assertIn("Repair cmake -S . -B build && cmake --build build", planner_message)
        self.assertIn("do not create unrelated starter files", planner_message.lower())

        task_plan = self.engine.task_planner.build_plan(
            message=planner_message,
            mode="build",
            workspace_files=self.engine.workspace.scan(workspace, 200),
            context_files=[],
            project_manifest=self.engine.workspace.load_project_manifest(workspace),
            dependency_profile=self.engine.workspace.inspect_dependency_profile(workspace),
        )
        self.assertEqual(task_plan.intent, "debug_and_repair")
        self.assertIn("Continue workspace readiness: Repair cmake", task_plan.objective)

    def test_broad_continue_with_workspace_readiness_uses_structured_path(self) -> None:
        workspace = Path(self.tempdir.name) / "readiness-route"
        workspace.mkdir()
        (workspace / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(ReadinessRoute LANGUAGES CXX)\n",
            encoding="utf-8",
        )
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir()
        (aegis_dir / "command_history.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.command_history.v1",
                    "commands": [
                        {
                            "kind": "validation",
                            "command": "cmake -S . -B build && cmake --build build",
                            "status": "failed",
                            "summary": "Build failed.",
                            "exit_code": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        request = AgentRequest(
            message="continue",
            mode="build",
            workspace_root=str(workspace),
        )

        self.assertFalse(asyncio.run(self.engine.can_stream_direct_chat(request)))

    def test_build_followup_with_workspace_readiness_uses_repair_path(self) -> None:
        workspace = Path(self.tempdir.name) / "build-followup-route"
        workspace.mkdir()
        (workspace / "package.json").write_text(
            json.dumps({"scripts": {"build": "node build.js"}}),
            encoding="utf-8",
        )
        (workspace / "build.js").write_text("process.exit(1);\n", encoding="utf-8")
        aegis_dir = workspace / ".aegis"
        aegis_dir.mkdir()
        (aegis_dir / "command_history.json").write_text(
            json.dumps(
                {
                    "schema": "aegis.command_history.v1",
                    "commands": [
                        {
                            "kind": "validation",
                            "command": "npm run build",
                            "status": "failed",
                            "summary": "Build script exited with code 1.",
                            "exit_code": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        planner_message = self.engine._planner_message_with_workspace_readiness("you didn't build it", workspace, [])

        self.assertIn("Workspace readiness continuation context", planner_message)
        self.assertIn("Readiness status: needs_repair", planner_message)
        self.assertIn("Repair npm run build", planner_message)

        task_plan = self.engine.task_planner.build_plan(
            message=planner_message,
            mode="build",
            workspace_files=self.engine.workspace.scan(workspace, 200),
            context_files=[],
            project_manifest=self.engine.workspace.load_project_manifest(workspace),
            dependency_profile=self.engine.workspace.inspect_dependency_profile(workspace),
        )
        self.assertEqual(task_plan.intent, "debug_and_repair")
        self.assertIn("Continue workspace readiness: Repair npm run build", task_plan.objective)

        request = AgentRequest(
            message="you didn't build it",
            mode="build",
            workspace_root=str(workspace),
        )
        self.assertFalse(asyncio.run(self.engine.can_stream_direct_chat(request)))

    def test_run_validation_executes_on_no_change_build_pass(self) -> None:
        workspace = Path(self.tempdir.name) / "no-change-validation"
        workspace.mkdir()
        (workspace / "build.py").write_text("print('validation ok')\n", encoding="utf-8")

        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="No file edits were needed before validation.", changes=[]), None

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="build it",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=True,
                    apply_changes=False,
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("python build.py", response.validation.command)
        self.assertIn("Auralith Prime ran validation", response.reply)
        self.assertIn("passed", response.reply)

    def test_draft_validation_command_runs_when_no_profile_is_detected(self) -> None:
        workspace = Path(self.tempdir.name) / "draft-validation-command"
        workspace.mkdir()

        async def fake_draft_response(*args, **kwargs):
            return (
                AgentDraft(
                    reply="No file edits were needed before validation.",
                    changes=[],
                    proposed_commands=[
                        {
                            "command": 'python -c "print(\'draft proposal validation ok\')"',
                            "reason": "Validate the current workspace after preserving the existing project.",
                        }
                    ],
                ),
                None,
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="build it and fix any errors",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=True,
                    apply_changes=False,
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("python -c", response.validation.command)
        self.assertIn("draft proposal validation ok", response.validation.stdout)
        self.assertTrue(
            any(event.kind == "validation" and event.title == "Draft validation command selected" for event in response.events)
        )
        learned_profile = self.engine.validation.load_profile(workspace)
        self.assertIsNotNone(learned_profile)
        self.assertEqual(learned_profile.source, "learned")
        self.assertEqual(learned_profile.command, response.validation.command)
        self.assertTrue(
            any(event.kind == "validation" and event.title == "Validation command learned" for event in response.events)
        )

    def test_saved_validation_profile_beats_draft_validation_command(self) -> None:
        workspace = Path(self.tempdir.name) / "saved-profile-before-draft"
        workspace.mkdir()
        self.engine.validation.save_profile(
            workspace,
            command='python -c "print(\'saved profile validation ok\')"',
            label="Saved profile validation",
            notes="Configured by the workspace owner.",
        )

        async def fake_draft_response(*args, **kwargs):
            return (
                AgentDraft(
                    reply="No file edits were needed before validation.",
                    changes=[],
                    proposed_commands=[
                        {
                            "command": 'python -c "print(\'draft validation should not run\')"',
                            "reason": "Validate with the model-proposed command.",
                        }
                    ],
                ),
                None,
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="build it",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=True,
                    apply_changes=False,
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertIn("saved profile validation ok", response.validation.stdout)
        self.assertNotIn("draft validation should not run", response.validation.stdout)

    def test_request_validation_override_beats_draft_validation_command(self) -> None:
        workspace = Path(self.tempdir.name) / "request-override-before-draft"
        workspace.mkdir()

        async def fake_draft_response(*args, **kwargs):
            return (
                AgentDraft(
                    reply="No file edits were needed before validation.",
                    changes=[],
                    proposed_commands=[
                        {
                            "command": 'python -c "print(\'draft validation should not run\')"',
                            "reason": "Validate with the model-proposed command.",
                        }
                    ],
                ),
                None,
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="build it",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=True,
                    apply_changes=False,
                    validation_command_override='python -c "print(\'request override validation ok\')"',
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertIn("request override validation ok", response.validation.stdout)
        self.assertNotIn("draft validation should not run", response.validation.stdout)
        self.assertIsNone(self.engine.validation.load_profile(workspace))

    def test_install_command_is_not_promoted_as_draft_validation(self) -> None:
        draft = AgentDraft(
            reply="Install dependencies before validation.",
            changes=[],
            proposed_commands=[{"command": "npm install", "reason": "Install dependencies"}],
        )

        self.assertIsNone(self.engine._draft_validation_override_recipe(draft))

    def test_failed_draft_validation_command_is_not_learned(self) -> None:
        workspace = Path(self.tempdir.name) / "failed-draft-validation-command"
        workspace.mkdir()

        async def fake_draft_response(*args, **kwargs):
            return (
                AgentDraft(
                    reply="No file edits were needed before validation.",
                    changes=[],
                    proposed_commands=[
                        {
                            "command": 'python -c "import sys; print(\'draft proposal validation failed\'); sys.exit(3)"',
                            "reason": "Validate the current workspace after preserving the existing project.",
                        }
                    ],
                ),
                None,
            )

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="build it and fix any errors",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=True,
                    apply_changes=False,
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 3)
        self.assertIsNone(self.engine.validation.load_profile(workspace))
        self.assertFalse(
            any(event.kind == "validation" and event.title == "Validation command learned" for event in response.events)
        )

    def test_prompt_validation_intent_runs_validation_without_toggle(self) -> None:
        workspace = Path(self.tempdir.name) / "prompt-validation-intent"
        workspace.mkdir()
        (workspace / "build.py").write_text("print('prompt validation ok')\n", encoding="utf-8")

        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="No file edits were needed before validation.", changes=[]), None

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        response = asyncio.run(
            self.engine.run(
                AgentRequest(
                    message="you didn't build it, build it and fix any errors",
                    mode="build",
                    workspace_root=str(workspace),
                    run_validation=False,
                    apply_changes=False,
                )
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("python build.py", response.validation.command)
        self.assertIn("passed", response.reply)

    def test_run_intent_runs_validation_without_toggle(self) -> None:
        workspace = Path(self.tempdir.name) / "prompt-run-intent"
        workspace.mkdir()
        (workspace / "build.py").write_text("print('run validation ok')\n", encoding="utf-8")

        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="No file edits were needed before running validation.", changes=[]), None

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        request = AgentRequest(
            message="run it please",
            mode="build",
            workspace_root=str(workspace),
            run_validation=False,
            apply_changes=False,
        )

        self.assertFalse(asyncio.run(self.engine.can_stream_direct_chat(request)))

        response = asyncio.run(
            self.engine.run(
                request
            )
        )

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("python build.py", response.validation.command)
        self.assertIn("passed", response.reply)

    def test_launch_intent_runs_validation_without_toggle(self) -> None:
        workspace = Path(self.tempdir.name) / "prompt-launch-intent"
        workspace.mkdir()
        (workspace / "build.py").write_text("print('launch validation ok')\n", encoding="utf-8")

        async def fake_draft_response(*args, **kwargs):
            return AgentDraft(reply="No file edits were needed before launch validation.", changes=[]), None

        self.engine._draft_response = fake_draft_response  # type: ignore[method-assign]

        request = AgentRequest(
            message="launch the app please",
            mode="build",
            workspace_root=str(workspace),
            run_validation=False,
            apply_changes=False,
        )

        self.assertFalse(asyncio.run(self.engine.can_stream_direct_chat(request)))

        response = asyncio.run(self.engine.run(request))

        self.assertIsNotNone(response.validation)
        self.assertEqual(response.validation.exit_code, 0)
        self.assertIn("python build.py", response.validation.command)
        self.assertIn("passed", response.reply)

    def test_validation_intent_detection_distinguishes_creation_from_build_request(self) -> None:
        self.assertTrue(self.engine._request_asks_for_validation("please build it and fix any errors"))
        self.assertTrue(self.engine._request_asks_for_validation("build and run it please"))
        self.assertTrue(self.engine._request_asks_for_validation("run the project"))
        self.assertTrue(self.engine._request_asks_for_validation("launch the app"))
        self.assertTrue(self.engine._request_asks_for_validation("start the project"))
        self.assertTrue(self.engine._request_asks_for_validation("execute it please"))
        self.assertTrue(self.engine._request_asks_for_validation("verify this"))
        self.assertTrue(self.engine._request_asks_for_validation("compile this and make sure there are no errors"))
        self.assertFalse(self.engine._request_asks_for_validation("build a website for a barber shop"))
        self.assertFalse(self.engine._request_asks_for_validation("explain how build systems work"))
        self.assertFalse(self.engine._request_asks_for_validation("how do I run it?"))
        self.assertFalse(self.engine._request_asks_for_validation("how do I launch it?"))

    def test_completion_quality_ready_after_validated_static_site_pass(self) -> None:
        request = AgentRequest(
            message="Complete a full barber styled website for Rick Cullers",
            mode="build",
            run_validation=True,
        )
        draft = AgentDraft(
            reply="Built and validated the static site.",
            changes=[
                FileChange(action="create", path="README.md", content="# Rick Cullers\n"),
                FileChange(action="create", path="index.html", content="<main id=\"home\"><section id=\"services\"></section><section id=\"booking\"></section></main>\n"),
                FileChange(action="create", path="styles.css", content="@media (max-width: 640px) { body { margin: 0; } }\n"),
                FileChange(action="create", path="app.js", content="document.addEventListener('click', () => {});\n"),
                FileChange(action="create", path="build.js", content="console.log('Static site validation passed.');\n"),
            ],
        )
        validation = CommandRun(
            command="node build.js",
            cwd=str(Path(self.tempdir.name)),
            allowed=True,
            exit_code=0,
            stdout="Static site validation passed.\n",
        )

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=validation,
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "ready")
        self.assertFalse(quality.should_continue)
        self.assertGreaterEqual(quality.score, 0.8)

    def test_completion_quality_blocks_on_validation_failure(self) -> None:
        request = AgentRequest(message="Create a C++ console project", mode="build", run_validation=True)
        draft = AgentDraft(
            reply="Created the project.",
            changes=[
                FileChange(action="create", path="main.cpp", content="int main(){return 0;}\n"),
                FileChange(action="create", path="CMakeLists.txt", content="cmake_minimum_required(VERSION 3.20)\n"),
            ],
        )
        validation = CommandRun(
            command="cmake --build build",
            cwd=str(Path(self.tempdir.name)),
            allowed=True,
            exit_code=1,
            stderr="compile error",
            summary="Compilation failed.",
        )

        quality = self.engine._completion_quality(
            request=request,
            mode="build",
            draft=draft,
            applied=[change.path for change in draft.changes],
            validation=validation,
            workspace_root=Path(self.tempdir.name),
            workspace_files=[],
        )

        self.assertEqual(quality.status, "blocked")
        self.assertTrue(quality.should_continue)
        self.assertTrue(any("Validation failed" in reason for reason in quality.reasons))


if __name__ == "__main__":
    unittest.main()
