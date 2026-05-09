from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent import AgentDraft, AgentEngine
from aegis_ai.context_budget import ContextBudgetManager
from aegis_ai.routing import ModelRouter
from aegis_ai.schemas import (
    AgentRequest,
    FileChange,
    ModelBenchmarkProviderScore,
    ModelRegistryProviderUpsertRequest,
    RoutePreviewRequest,
    WorkspaceDependencyProfile,
    WorkspaceFile,
    WorkspaceProjectManifest,
)
from aegis_ai.settings import Settings
from aegis_ai.task_planner import TaskPlanner


class PromptRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(_env_file=None)
        self.router = ModelRouter(self.settings)
        self.planner = TaskPlanner(self.router)

    def test_build_mode_still_routes_plain_question_to_chat(self) -> None:
        decision = self.router.recommend(
            "count to 10 starting from 11",
            "build",
            has_workspace_context=True,
        )

        self.assertEqual(decision.task_role, "chat")
        self.assertFalse(decision.requires_tools)

    def test_build_mode_routes_file_creation_to_code(self) -> None:
        decision = self.router.recommend(
            "create a python script file that prints hello world",
            "build",
            has_workspace_context=True,
        )

        self.assertEqual(decision.task_role, "code")
        self.assertTrue(decision.requires_workspace)

    def test_logo_generation_routes_to_creative_not_code(self) -> None:
        decision = self.router.recommend(
            "generate a random logo for a company called Aspire in computer science",
            "build",
            has_workspace_context=False,
        )

        self.assertEqual(decision.task_role, "creative")
        self.assertFalse(decision.requires_workspace)

    def test_task_planner_keeps_logo_generation_out_of_workspace_profiles(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema_version="aegis.project.v1",
            project_name="existing-web-app",
            title="Existing Web App",
            preset_label="Vite React TypeScript",
            framework="Vite + React",
            language="TypeScript",
            package_manager="npm",
            install_command="npm install",
            validation_command="npm run build",
            tags=["web", "vite", "react"],
        )
        plan = self.planner.build_plan(
            message="generate a random logo for a company called Aspire in computer science",
            mode="build",
            workspace_files=[WorkspaceFile(path="package.json", size=100, kind="text")],
            context_files=[],
            project_manifest=manifest,
        )

        self.assertEqual(plan.intent, "conversation")
        self.assertEqual(plan.route_profile, {})
        self.assertIsNotNone(plan.routing)
        self.assertEqual(plan.routing.task_role, "creative")

    def test_chat_run_creates_creative_job_for_logo_prompt_even_with_apply_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            engine = AgentEngine(
                workspace,
                Settings(_env_file=None, aegis_model_api="none", aegis_database_path="data/test.sqlite3"),
            )

            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="generate a random logo for a company called Aspire in computer science",
                        workspace_root=str(workspace),
                        mode="build",
                    )
                )
            )
            response = asyncio.run(
                engine.run(
                    AgentRequest(
                        message="generate a random logo for a company called Aspire in computer science",
                        workspace_root=str(workspace),
                        mode="build",
                        apply_changes=True,
                        run_validation=True,
                    )
                )
            )

        self.assertFalse(direct_stream)
        self.assertEqual(response.engine, "Auralith Creative Studio")
        self.assertEqual(response.changes, [])
        self.assertEqual(response.applied, [])
        self.assertIsNone(response.validation)
        self.assertIn("Creative Studio", response.reply)
        self.assertIn("Apply changes was ignored", " ".join(response.warnings))
        self.assertIsNotNone(response.media_job)
        self.assertEqual(response.media_job.kind if response.media_job else "", "logo")
        self.assertTrue(any(asset.format == "png" for asset in (response.media_job.assets if response.media_job else [])))
        self.assertTrue(any(event.kind == "creative.intent" for event in response.events))
        self.assertFalse((workspace / "go.mod").exists())

    def test_chat_run_routes_informal_logo_smoke_test_to_creative_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            engine = AgentEngine(
                workspace,
                Settings(_env_file=None, aegis_model_api="none", aegis_database_path="data/test.sqlite3"),
            )

            response = asyncio.run(
                engine.run(
                    AgentRequest(
                        message="generate a random logo idc what it is but i want to make sure this is working",
                        workspace_root=str(workspace),
                        mode="build",
                        apply_changes=True,
                    )
                )
            )

        self.assertEqual(response.engine, "Auralith Creative Studio")
        self.assertEqual(response.task_plan.routing.task_role if response.task_plan and response.task_plan.routing else "", "creative")
        self.assertIsNotNone(response.media_job)
        self.assertEqual(response.media_job.kind if response.media_job else "", "logo")

    def test_task_planner_is_prompt_first_not_mode_first(self) -> None:
        plan = self.planner.build_plan(
            message="count to 10 starting from 11",
            mode="build",
            workspace_files=[],
            context_files=[],
        )

        self.assertEqual(plan.intent, "conversation")
        self.assertIsNotNone(plan.routing)
        self.assertEqual(plan.routing.task_role, "chat")

    def test_project_manifest_continuation_routes_to_code(self) -> None:
        manifest = WorkspaceProjectManifest(
            schema_version="aegis.project.v1",
            project_name="preview-control-deck",
            title="Preview Control Deck",
            preset_label="Tauri React TypeScript",
            framework="Tauri + Vite + React",
            language="TypeScript + Rust",
            package_manager="npm/cargo",
            install_command="npm install",
            validation_command="npm run build",
            tags=["desktop", "tauri"],
        )
        plan = self.planner.build_plan(
            message="go ahead and continue with your suggestions",
            mode="develop",
            workspace_files=[WorkspaceFile(path="package.json", size=100, kind="text")],
            context_files=[],
            project_manifest=manifest,
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "desktop-app")
        self.assertIn("route profile metadata", plan.context_requirements)
        self.assertIsNotNone(plan.routing)
        self.assertEqual(plan.routing.task_role, "code")
        self.assertIn("Aegis project manifest", plan.context_requirements)
        self.assertIn("manifest validation command", plan.tool_requirements)

    def test_driver_prompt_gets_high_risk_route_profile_without_manifest(self) -> None:
        plan = self.planner.build_plan(
            message="create a Windows KMDF kernel driver skeleton with an IOCTL interface",
            mode="build",
            workspace_files=[WorkspaceFile(path="driver/main.c", size=100, kind="text")],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "kernel-driver")
        self.assertIn("driver safety and signing checklist", plan.tool_requirements)
        self.assertIn("high-risk", " ".join(plan.risks).lower())

    def test_reverse_engineering_prompt_gets_authorized_analysis_profile(self) -> None:
        plan = self.planner.build_plan(
            message="analyze this PE file with reverse engineering tactics to understand imports and crashes",
            mode="review",
            workspace_files=[WorkspaceFile(path="analysis/report.md", size=100, kind="text")],
            context_files=[],
        )

        self.assertEqual(plan.route_profile["id"], "reverse-engineering")
        self.assertIn("authorized static-analysis checklist", plan.tool_requirements)
        self.assertIn("authorized binaries", " ".join(plan.risks))

    def test_database_prompt_gets_migration_profile(self) -> None:
        plan = self.planner.build_plan(
            message="add a postgres schema migration for user accounts",
            mode="develop",
            workspace_files=[WorkspaceFile(path="migrations/001_init.sql", size=100, kind="text")],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "database")
        self.assertIn("migration and rollback review", plan.tool_requirements)

    def test_complete_full_website_routes_as_implementation(self) -> None:
        plan = self.planner.build_plan(
            message="Complete a full barber styled website for Rick Cullers",
            mode="build",
            workspace_files=[],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "web-app")
        self.assertIn("Full-build requests include enough files", " ".join(plan.completion_criteria))

    def test_large_full_app_prompt_expands_planning_and_context_budget(self) -> None:
        dependency_profile = WorkspaceDependencyProfile(
            languages=["TypeScript", "Python"],
            frameworks=["React", "FastAPI"],
            package_managers=["npm", "pip"],
            build_systems=["vite", "pytest"],
            config_files=["package.json", "pyproject.toml", "vite.config.ts", "src/api/main.py"],
            validation_commands=["npm run build", "pytest"],
        )
        plan = self.planner.build_plan(
            message=(
                "Build a full blown production-grade app from scratch in one prompt with "
                "frontend, backend, auth, database, tests, deployment notes, and validation."
            ),
            mode="build",
            workspace_files=[WorkspaceFile(path=f"src/module_{index}.ts", size=1800, kind="text") for index in range(85)],
            context_files=[],
            dependency_profile=dependency_profile,
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "full-stack-app")
        self.assertIn(plan.complexity, {"large", "epic"})
        self.assertGreaterEqual(plan.estimated_slices, 5)
        self.assertGreaterEqual(plan.pass_budget_hint, 22)
        self.assertIn("Keep the requested target path", "\n".join(plan.large_task_protocol))
        self.assertIn("Large-task protocol", plan.to_prompt_context())

        budget = ContextBudgetManager(self.settings).profile_for(plan, provider_context_window=64_000)

        self.assertGreaterEqual(budget.max_context_files, 26)
        self.assertGreaterEqual(budget.max_file_chars, 6200)
        self.assertIn("expanded", " ".join(budget.notes).lower())

    def test_huge_single_file_workspace_enables_chunked_large_file_protocol(self) -> None:
        plan = self.planner.build_plan(
            message="Refactor this 500,000 line single file project without losing behavior.",
            mode="develop",
            workspace_files=[
                WorkspaceFile(
                    path="src/legacy_monolith.cpp",
                    size=36_000_000,
                    kind="text",
                    is_large=True,
                    estimated_lines=500_000,
                    large_file_strategy="huge-file sampled indexing; read targeted line slices before patching",
                )
            ],
            context_files=[],
        )

        self.assertIn(plan.complexity, {"large", "epic"})
        protocol = "\n".join(plan.large_task_protocol)
        self.assertIn("chunked assets", protocol)
        self.assertIn("targeted line slices", protocol)
        self.assertIn("Avoid rewriting giant files wholesale", protocol)

    def test_explicit_website_request_beats_stale_desktop_workspace_signal(self) -> None:
        plan = self.planner.build_plan(
            message="Complete a full barber styled website for Rick Cullers",
            mode="build",
            workspace_files=[
                WorkspaceFile(path="CMakeLists.txt", size=100, kind="text"),
                WorkspaceFile(path="src/main.cpp", size=100, kind="text"),
            ],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile["id"], "web-app")

    def test_do_not_make_website_keeps_native_workspace_route(self) -> None:
        plan = self.planner.build_plan(
            message="add a diagnostics UI and build it, but do not make a website.",
            mode="build",
            workspace_files=[
                WorkspaceFile(path="CMakeLists.txt", size=100, kind="text"),
                WorkspaceFile(path="src/main.cpp", size=100, kind="text"),
            ],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertIn(plan.route_profile["id"], {"desktop-app", "systems-cli", "native-binary"})
        self.assertNotEqual(plan.route_profile["id"], "web-app")
        self.assertNotEqual(plan.route_profile["category"], "web")

    def test_route_preview_uses_registry_role_primary_without_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            engine.model_registry.upsert_provider(
                ModelRegistryProviderUpsertRequest(
                    id="ollama:codegemma",
                    label="CodeGemma",
                    api="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model_name="codegemma:2b",
                    local=True,
                    enabled=True,
                    configured=True,
                    capabilities=["chat", "structured_json"],
                    roles=["chat", "fallback"],
                )
            )
            engine.model_registry.apply_benchmark_winners(
                [
                    ModelBenchmarkProviderScore(
                        provider_id="ollama:codegemma",
                        provider_label="CodeGemma",
                        api="ollama",
                        model_name="codegemma:2b",
                        local=True,
                        enabled=True,
                        configured=True,
                        overall_score=0.91,
                        chat_score=0.93,
                        code_score=0.62,
                        reasoning_score=0.60,
                        avg_latency_ms=950,
                        run_count=3,
                    )
                ]
            )

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="count to 10 starting from 11",
                        workspace_root=temp_dir,
                        mode="build",
                    )
                )
            )

        self.assertEqual(preview.task_plan.routing.task_role, "chat")
        self.assertIsNotNone(preview.primary_attempt)
        self.assertEqual(preview.primary_attempt.model, "codegemma:2b")
        self.assertEqual(preview.primary_attempt.metadata["registry_role_primary_model"], "codegemma:2b")
        self.assertIn("should not require file changes", " ".join(preview.recommendations))

    def test_route_preview_uses_manifest_for_broad_continuation_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            manifest_path = workspace / ".aegis" / "project.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "aegis.project.v1",
                        "project_name": "route-preview-smoke",
                        "title": "Route Preview Smoke",
                        "preset_label": "Tauri React TypeScript",
                        "framework": "Tauri + Vite + React",
                        "language": "TypeScript + Rust",
                        "package_manager": "npm/cargo",
                        "install_command": "npm install",
                        "validation_command": "npm run build",
                        "tags": ["desktop", "tauri"],
                    }
                ),
                encoding="utf-8",
            )
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"build": "vite build"}}),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="and continue with your suggestions",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertEqual(preview.task_plan.route_profile["id"], "desktop-app")
        self.assertEqual(preview.task_plan.routing.task_role, "code")
        self.assertIn("Workspace manifest detected", " ".join(preview.recommendations))
        self.assertIn("Route profile active", " ".join(preview.recommendations))
        self.assertIn("npm run build", " ".join(preview.recommendations))
        self.assertIsNotNone(preview.primary_attempt)
        self.assertEqual(preview.primary_attempt.metadata["route_profile_id"], "desktop-app")

    def test_chat_run_uses_explicit_prompt_path_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Roblox" / "TestOne"
            engine = AgentEngine(
                base_workspace,
                Settings(_env_file=None, aegis_model_api="none", aegis_database_path="data/test.sqlite3"),
            )

            response = asyncio.run(
                engine.run(
                    AgentRequest(
                        message=(
                            f"at this path {target_workspace} create a C++ console project with an sln "
                            "that prints hello world, waits for enter, and also build it"
                        ),
                        workspace_root=str(base_workspace),
                        mode="build",
                        apply_changes=True,
                        run_validation=False,
                        max_repair_attempts=0,
                    )
                )
            )

            self.assertEqual(Path(response.workspace_root), target_workspace.resolve())
            self.assertTrue((target_workspace / "src" / "main.cpp").exists())
            self.assertTrue(any(path.suffix == ".sln" for path in target_workspace.glob("*.sln")))
            self.assertFalse((base_workspace / "src" / "main.cpp").exists())

    def test_chat_run_keeps_existing_dll_request_native_at_prompt_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Aegis DLL Build Tools"
            (target_workspace / "src").mkdir(parents=True)
            (target_workspace / "CMakeLists.txt").write_text(
                "\n".join(
                    [
                        "cmake_minimum_required(VERSION 3.20)",
                        "project(AegisDll LANGUAGES CXX)",
                        "add_library(AegisDll SHARED src/main.cpp)",
                    ]
                ),
                encoding="utf-8",
            )
            (target_workspace / "src" / "main.cpp").write_text(
                'extern "C" __declspec(dllexport) int aegis_version(){ return 1; }\n',
                encoding="utf-8",
            )
            engine = AgentEngine(
                base_workspace,
                Settings(_env_file=None, aegis_model_api="none", aegis_database_path="data/test.sqlite3"),
            )

            response = asyncio.run(
                engine.run(
                    AgentRequest(
                        message=(
                            f"at this path {target_workspace} work on my existing DLL project, "
                            "refine it, keep it native C++, and do not turn it into a website"
                        ),
                        workspace_root=str(base_workspace),
                        mode="develop",
                        apply_changes=True,
                        run_validation=False,
                        max_repair_attempts=0,
                    )
                )
            )

            generated_files = {
                path.relative_to(target_workspace).as_posix()
                for path in target_workspace.rglob("*")
                if path.is_file()
            }
            self.assertEqual(Path(response.workspace_root), target_workspace.resolve())
            self.assertIn("CMakeLists.txt", generated_files)
            self.assertIn("build.py", generated_files)
            self.assertNotIn("package.json", generated_files)
            self.assertFalse(any(path.endswith((".tsx", ".jsx", ".html")) for path in generated_files))

    def test_route_preview_trims_path_marker_without_creating_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Aegis Game Dumper"
            engine = AgentEngine(base_workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message=(
                            f"{target_workspace} at this path refine the existing DLL project and build it"
                        ),
                        workspace_root=str(base_workspace),
                        mode="develop",
                    )
                )
            )

            self.assertEqual(Path(preview.workspace_root), target_workspace.resolve())
            self.assertFalse((base_workspace / "Aegis Game Dumper at this path").exists())
            self.assertFalse(target_workspace.exists())

    def test_route_preview_keeps_action_words_inside_prompt_workspace_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Aegis Build Tools New"
            engine = AgentEngine(base_workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message=(
                            f"at this path {target_workspace} create a C++ console project "
                            "with an sln and build it"
                        ),
                        workspace_root=str(base_workspace),
                        mode="build",
                    )
                )
            )

            self.assertEqual(Path(preview.workspace_root), target_workspace.resolve())
            self.assertFalse((base_workspace / "Aegis").exists())
            self.assertFalse(target_workspace.exists())

    def test_mission_anchor_routes_vague_continue_to_original_native_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Existing Dll Tool"
            (target_workspace / "src").mkdir(parents=True)
            (target_workspace / "CMakeLists.txt").write_text(
                "\n".join(
                    [
                        "cmake_minimum_required(VERSION 3.20)",
                        "project(ExistingDllTool LANGUAGES CXX)",
                        "add_library(ExistingDllTool SHARED src/main.cpp)",
                    ]
                ),
                encoding="utf-8",
            )
            (target_workspace / "src" / "main.cpp").write_text(
                'extern "C" __declspec(dllexport) int aegis_version(){ return 1; }\n',
                encoding="utf-8",
            )
            original = f"at this path {target_workspace} refine my existing DLL project and build it"
            history = [
                {
                    "role": "system",
                    "content": "\n".join(
                        [
                            "Aegis mission anchor:",
                            f"- Original user mission: {original}",
                            f"- Active workspace root: {target_workspace}",
                            "- Continuity rule: Preserve the original path, stack, artifact type, and validation intent.",
                        ]
                    ),
                }
            ]
            engine = AgentEngine(base_workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue",
                        history=history,
                        workspace_root=str(base_workspace),
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue",
                        history=history,
                        workspace_root=str(base_workspace),
                        mode="develop",
                    )
                )
            )

        self.assertEqual(Path(preview.workspace_root), target_workspace.resolve())
        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertNotEqual(preview.task_plan.route_profile["id"], "web-app")
        self.assertEqual(preview.task_plan.routing.task_role, "code")
        self.assertFalse(direct_stream)

    def test_source_code_followups_stay_native_not_research(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Native Source Project"
            (target_workspace / "src").mkdir(parents=True)
            (target_workspace / "CMakeLists.txt").write_text(
                "\n".join(
                    [
                        "cmake_minimum_required(VERSION 3.20)",
                        "project(NativeSourceProject LANGUAGES CXX)",
                        "add_executable(NativeSourceProject src/main.cpp)",
                    ]
                ),
                encoding="utf-8",
            )
            (target_workspace / "src" / "main.cpp").write_text(
                '#include <iostream>\nint main(){ std::cout << "hello"; return 0; }\n',
                encoding="utf-8",
            )
            original = f"at this path {target_workspace} refine the existing native C++ source code and build it"
            history = [
                {
                    "role": "system",
                    "content": "\n".join(
                        [
                            "Aegis mission anchor:",
                            f"- Original user mission: {original}",
                            f"- Active workspace root: {target_workspace}",
                            "- Continuity rule: Preserve the original path, stack, artifact type, and validation intent.",
                        ]
                    ),
                }
            ]
            engine = AgentEngine(base_workspace, self.settings)

            cases = (
                ("continue", {"implementation"}),
                ("yes", {"implementation"}),
                ("yes im aware go ahead", {"implementation"}),
                ("build it", {"implementation"}),
                ("continue working on the source files", {"implementation"}),
                ("use the latest source layout and build it", {"implementation"}),
                ("fix the source code and build it", {"debug_and_repair"}),
            )
            for message, expected_intents in cases:
                with self.subTest(message=message):
                    preview = asyncio.run(
                        engine.preview_route(
                            RoutePreviewRequest(
                                message=message,
                                history=history,
                                workspace_root=str(base_workspace),
                                mode="develop",
                            )
                        )
                    )

                    self.assertEqual(Path(preview.workspace_root), target_workspace.resolve())
                    self.assertIn(preview.task_plan.intent, expected_intents)
                    self.assertEqual(preview.task_plan.route_profile.get("id"), "native-binary")
                    self.assertIn("*.slnx", preview.task_plan.route_profile.get("focus_paths", []))
                    self.assertIn(preview.task_plan.routing.task_role, {"code", "debug"})
                    self.assertEqual(preview.task_plan.routing.privacy_mode, "local-first")

    def test_external_research_does_not_inherit_native_route_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "src").mkdir()
            (workspace / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(NativeResearchBoundary LANGUAGES CXX)\n"
                "add_executable(NativeResearchBoundary src/main.cpp)\n",
                encoding="utf-8",
            )
            (workspace / "src" / "main.cpp").write_text("int main(){ return 0; }\n", encoding="utf-8")
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="look up latest AI news",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertEqual(preview.task_plan.intent, "research_and_synthesize")
        self.assertEqual(preview.task_plan.routing.task_role, "research")
        self.assertEqual(preview.task_plan.route_profile, {})

    def test_stream_meta_workspace_root_uses_mission_anchor_for_continue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Native Mission"
            original = f"at this path {target_workspace} create a native C++ console app and build it"
            engine = AgentEngine(base_workspace, self.settings)
            request = AgentRequest(
                message="build it",
                history=[
                    {
                        "role": "system",
                        "content": "\n".join(
                            [
                                "Aegis mission anchor:",
                                f"- Original user mission: {original}",
                                f"- Active workspace root: {target_workspace}",
                                "- Continuity rule: Continue the saved mission without changing stacks.",
                            ]
                        ),
                    }
                ],
                workspace_root=str(base_workspace),
                mode="build",
            )

            workspace_root = engine.stream_meta_workspace_root(request)

        self.assertEqual(Path(workspace_root), target_workspace.resolve())
        self.assertFalse(target_workspace.exists())

    def test_non_coding_mission_anchor_can_still_stream_as_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            history = [
                {
                    "role": "system",
                    "content": "\n".join(
                        [
                            "Aegis mission anchor:",
                            "- Original user mission: count to 10 starting from 11",
                            f"- Active workspace root: {temp_dir}",
                            "- Continuity rule: Preserve normal conversation context.",
                        ]
                    ),
                }
            ]

            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue",
                        history=history,
                        workspace_root=temp_dir,
                        mode="build",
                    )
                )
            )

        self.assertTrue(direct_stream)

    def test_route_preview_surfaces_arbitrary_instruction_file_for_continue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "finish-this.md").write_text(
                """
# Finish This Project

- [ ] Build the C++ console entry point.
- [ ] Add the Visual Studio solution file.
- [ ] Run validation and capture the output.
""".strip(),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        recommendation_text = " ".join(preview.recommendations)
        self.assertIn("Project instruction files detected", recommendation_text)
        self.assertIn("finish-this.md", recommendation_text)
        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertEqual(preview.task_plan.routing.task_role, "code")
        self.assertFalse(direct_stream)

    def test_continue_does_not_autopilot_completed_todo_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "TODO.md").write_text(
                """
# TODO

- [x] Build the C++ console entry point.
- [x] Add the Visual Studio solution file.
- [x] Run validation and capture the output.
""".strip(),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertEqual(preview.task_plan.intent, "conversation")
        self.assertIn("tracked checklist items are complete", " ".join(preview.recommendations))
        self.assertTrue(direct_stream)

    def test_continue_can_follow_guidance_file_without_checkboxes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "AGENTS.md").write_text(
                """
# Agent Handoff

Project instructions: continue improving the desktop coding assistant.
Remaining work includes better build output cards and a stronger route dashboard.
""".strip(),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertIn("AGENTS.md", " ".join(preview.recommendations))
        self.assertFalse(direct_stream)

    def test_long_autopilot_continue_prompt_follows_instruction_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "PROJECT_TODO.md").write_text(
                """
# Project TODO

- [ ] Build the ImGui project dashboard.
- [ ] Add CMake and MSVC validation coverage.
- [ ] Capture build output in the activity panel.
""".strip(),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            message = (
                "please continue bug hunting, and if no more bugs are found continue with your suggestions "
                "while stress testing to ensure everything remains functional and intact"
            )
            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message=message,
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message=message,
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertIn(preview.task_plan.routing.task_role, {"code", "debug"})
        self.assertIn("PROJECT_TODO.md", " ".join(preview.recommendations))
        self.assertNotEqual(preview.task_plan.route_profile.get("id"), "reverse-engineering")
        self.assertFalse(direct_stream)

    def test_validation_word_does_not_trigger_ida_reverse_engineering_profile(self) -> None:
        plan = self.planner.build_plan(
            message="continue bug hunting and add native validation coverage",
            mode="develop",
            workspace_files=[WorkspaceFile(path="PROJECT_TODO.md", size=100, kind="text")],
            context_files=[],
        )

        self.assertNotEqual(plan.route_profile.get("id"), "reverse-engineering")

    def test_explicit_ida_prompt_keeps_reverse_engineering_profile(self) -> None:
        plan = self.planner.build_plan(
            message="Use IDA to inspect the import table for this authorized plugin binary.",
            mode="review",
            workspace_files=[WorkspaceFile(path="analysis/notes.md", size=100, kind="text")],
            context_files=[],
        )

        self.assertEqual(plan.route_profile["id"], "reverse-engineering")

    def test_continue_from_referenced_extensionless_instruction_file_uses_structured_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "northstar").write_text(
                """
Project completion list

- Build the ImGui diagnostics panel.
- Add native validation coverage.
""".strip(),
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue from northstar",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )
            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(
                        message="continue from northstar",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertIn(preview.task_plan.intent, {"debug_and_repair", "implementation"})
        self.assertIn("northstar", " ".join(preview.recommendations))
        self.assertFalse(direct_stream)

    def test_specific_new_request_does_not_get_swallowed_by_continue_file_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "PROJECT_TODO.md").write_text(
                "- [ ] Refactor the existing dashboard.\n",
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="continue, but create a Python CLI smoke test project called Tiny Tool",
                        workspace_root=temp_dir,
                        mode="build",
                    )
                )
            )

        objective = preview.task_plan.objective.lower()
        self.assertIn("python", objective)
        self.assertIn("cli", objective)
        self.assertNotIn("open project instruction file tasks", objective)

    def test_native_cpp_draft_gets_python_build_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            draft = AgentDraft(
                reply="Created a C++ CMake project.",
                changes=[
                    FileChange(
                        action="create",
                        path="CMakeLists.txt",
                        summary="Add CMake build.",
                        content="cmake_minimum_required(VERSION 3.20)\nadd_executable(App src/main.cpp)\n",
                    ),
                    FileChange(
                        action="create",
                        path="src/main.cpp",
                        summary="Add entry.",
                        content="#include <iostream>\nint main(){ std::cout << \"hello\"; }\n",
                    ),
                    FileChange(
                        action="create",
                        path="scripts/build.sh",
                        summary="Add shell build.",
                        content="cmake -S . -B build && cmake --build build\n",
                    ),
                ],
                proposed_commands=[
                    {"command": "bash scripts/build.sh", "reason": "Build the project."},
                    {"command": "cmake -S . -B build && cmake --build build --config Release", "reason": "Build with CMake."},
                ],
            )

            hardened = engine._harden_native_cpp_draft(
                draft,
                "continue\nCreate a C++ console entry point and add a CMake build file.",
                Path(temp_dir),
            )

        paths = [change.path for change in hardened.changes]
        commands = [command["command"] for command in hardened.proposed_commands]
        self.assertIn("build.py", paths)
        self.assertNotIn("scripts/build.sh", paths)
        self.assertIn("python build.py", commands)
        self.assertNotIn("bash scripts/build.sh", commands)
        self.assertNotIn("cmake -S . -B build && cmake --build build --config Release", commands)
        build_py = next(change.content for change in hardened.changes if change.path == "build.py")
        self.assertIn("smoke_run_executable", build_py)
        self.assertIn('"--aegis-validate"', build_py)
        self.assertIn('input="\\n"', build_py)

    def test_direct_numeric_fallback_beats_thin_model_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            fallback = engine._fallback_draft(
                "count to 10 starting from 11",
                "chat",
                Path(temp_dir),
                [],
            )

        self.assertEqual(fallback.reply, "11, 12, 13, 14, 15, 16, 17, 18, 19, 20")
        self.assertTrue(
            engine._direct_answer_fallback_is_more_specific(
                "Starting the counting sequence.",
                fallback.reply,
            )
        )

    def test_non_file_chat_ignores_invalid_change_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            draft = engine._parse_model_payload(
                {
                    "reply": "11, 12, 13",
                    "changes": [11, 12, 13],
                    "commands": [],
                },
                request_message="count to 3 starting from 11",
                mode="build",
            )

        self.assertEqual(draft.reply, "11, 12, 13")
        self.assertEqual(draft.warnings, [])

    def test_project_manifest_context_includes_stack_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = AgentEngine(Path(temp_dir), self.settings)
            context = engine._project_manifest_context(
                WorkspaceProjectManifest(
                    schema_version="aegis.project.v1",
                    project_name="control-deck",
                    title="Control Deck",
                    preset_label="Tauri React TypeScript",
                    framework="Tauri + Vite + React",
                    language="TypeScript + Rust",
                    package_manager="npm/cargo",
                    install_command="npm install",
                    validation_command="npm run build",
                    tags=["desktop", "tauri"],
                    agent_handoff={
                        "primary_goal": "Turn the scaffold into a working product.",
                        "first_pass": ["Install dependencies.", "Run validation."],
                    },
                )
            )

        self.assertIn("Control Deck", context)
        self.assertIn("Tauri + Vite + React / TypeScript + Rust", context)
        self.assertIn("npm run build", context)
        self.assertIn("Turn the scaffold into a working product.", context)

    def test_natural_existing_native_prompts_use_structured_agent(self) -> None:
        prompts = (
            "refine my existing DLL project",
            "work on my existing DLL project",
            "optimize this native project",
            "clean up this C++ project",
            "improve this C++ project",
            "polish this native tool",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "src").mkdir()
            (workspace / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(NativeDll LANGUAGES CXX)\n"
                "add_library(NativeDll SHARED src/dllmain.cpp)\n",
                encoding="utf-8",
            )
            (workspace / "src" / "dllmain.cpp").write_text(
                "#include <windows.h>\n"
                "BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) { return TRUE; }\n",
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            for prompt in prompts:
                with self.subTest(prompt=prompt):
                    plan = self.planner.build_plan(
                        message=prompt,
                        mode="develop",
                        workspace_files=[
                            WorkspaceFile(path="CMakeLists.txt", size=120, kind="text"),
                            WorkspaceFile(path="src/dllmain.cpp", size=120, kind="text"),
                        ],
                        context_files=[],
                    )
                    direct_stream = asyncio.run(
                        engine.can_stream_direct_chat(
                            AgentRequest(message=prompt, workspace_root=temp_dir, mode="develop")
                        )
                    )

                    self.assertEqual(plan.intent, "implementation")
                    self.assertNotEqual(plan.route_profile.get("id"), "web-app")
                    self.assertFalse(direct_stream)

    def test_plain_native_question_can_still_stream_as_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\nproject(NativeDll LANGUAGES CXX)\n",
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            direct_stream = asyncio.run(
                engine.can_stream_direct_chat(
                    AgentRequest(message="what is a DLL?", workspace_root=temp_dir, mode="develop")
                )
            )
            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(message="what is a DLL?", workspace_root=temp_dir, mode="develop")
                )
            )

        self.assertTrue(direct_stream)
        self.assertEqual(preview.task_plan.intent, "conversation")
        self.assertEqual(preview.task_plan.route_profile, {})

    def test_negated_website_phrase_does_not_poison_native_route_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "src").mkdir()
            (workspace / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(ExistingDll LANGUAGES CXX)\n"
                "add_library(ExistingDll SHARED src/dllmain.cpp)\n",
                encoding="utf-8",
            )
            (workspace / "src" / "dllmain.cpp").write_text(
                "#include <windows.h>\n"
                "BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) { return TRUE; }\n",
                encoding="utf-8",
            )
            engine = AgentEngine(workspace, self.settings)

            preview = asyncio.run(
                engine.preview_route(
                    RoutePreviewRequest(
                        message="work on my existing DLL project and refine it without turning it into a website",
                        workspace_root=temp_dir,
                        mode="develop",
                    )
                )
            )

        self.assertEqual(preview.task_plan.intent, "implementation")
        self.assertEqual(preview.task_plan.route_profile.get("id"), "native-binary")

    def test_negated_website_conversion_does_not_poison_desktop_route_profile(self) -> None:
        plan = self.planner.build_plan(
            message="modernize this WPF desktop app without converting it to a website",
            mode="develop",
            workspace_files=[WorkspaceFile(path="LegacyDesktop.csproj", size=100, kind="text")],
            context_files=[],
        )

        self.assertEqual(plan.intent, "implementation")
        self.assertEqual(plan.route_profile.get("id"), "desktop-app")

    def test_design_plus_build_prompts_stay_implementation_not_planning_only(self) -> None:
        cases = (
            ("design and build a C++ DLL project", "native-binary"),
            ("create and design a barber website", "web-app"),
            ("create a design system for a React app", "web-app"),
        )
        for prompt, expected_route in cases:
            with self.subTest(prompt=prompt):
                plan = self.planner.build_plan(
                    message=prompt,
                    mode="build",
                    workspace_files=[],
                    context_files=[],
                )

                self.assertEqual(plan.intent, "implementation")
                self.assertEqual(plan.route_profile.get("id"), expected_route)

    def test_explicit_architecture_prompt_still_routes_to_planning(self) -> None:
        plan = self.planner.build_plan(
            message="plan the architecture for a C++ project",
            mode="build",
            workspace_files=[],
            context_files=[],
        )

        self.assertEqual(plan.intent, "architecture_planning")
        self.assertEqual(plan.route_profile.get("id"), "native-binary")

    def test_stream_meta_workspace_root_uses_explicit_prompt_path_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_workspace = Path(temp_dir)
            target_workspace = base_workspace / "Prompt Selected Native Project"
            engine = AgentEngine(base_workspace, self.settings)

            workspace_root = engine.stream_meta_workspace_root(
                AgentRequest(
                    message=(
                        f"at this path {target_workspace} create a C++ console app "
                        "that prints hello world and build it"
                    ),
                    workspace_root=str(base_workspace),
                    mode="build",
                )
            )

            self.assertEqual(Path(workspace_root), target_workspace.resolve())
            self.assertFalse(target_workspace.exists())


if __name__ == "__main__":
    unittest.main()
