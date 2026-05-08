from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.schemas import (
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
    WorkspaceDependencyProfile,
    WorkspaceInstructionStatusFile,
    WorkspaceInstructionStatusInfo,
    WorkspaceProjectManifest,
    WorkspaceReadinessInfo,
    WorkspaceValidationPlanInfo,
)


class FakeAutopilotWorkspaceManager:
    def __init__(
        self,
        root: Path,
        *,
        manifest: WorkspaceProjectManifest | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ):
        self.root = root
        self.manifest = manifest
        self.dependency_profile = dependency_profile or WorkspaceDependencyProfile()

    def resolve_workspace(self, workspace_root: str | None) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def load_project_manifest(self, root: Path) -> WorkspaceProjectManifest | None:
        return self.manifest

    def inspect_dependency_profile(self, root: Path) -> WorkspaceDependencyProfile:
        return self.dependency_profile


class CountingAutopilotWorkspaceManager(FakeAutopilotWorkspaceManager):
    def __init__(
        self,
        root: Path,
        *,
        manifest: WorkspaceProjectManifest | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ):
        super().__init__(root, manifest=manifest, dependency_profile=dependency_profile)
        self.manifest_calls = 0
        self.dependency_profile_calls = 0

    def load_project_manifest(self, root: Path) -> WorkspaceProjectManifest | None:
        self.manifest_calls += 1
        return super().load_project_manifest(root)

    def inspect_dependency_profile(self, root: Path) -> WorkspaceDependencyProfile:
        self.dependency_profile_calls += 1
        return super().inspect_dependency_profile(root)


class FakeAutopilotAgent:
    def __init__(
        self,
        *,
        readiness: WorkspaceReadinessInfo,
        instruction_status: WorkspaceInstructionStatusInfo | None = None,
        validation_plan: WorkspaceValidationPlanInfo | None = None,
        command_history: dict[str, object] | None = None,
    ):
        self.readiness = readiness
        self.instruction_status = instruction_status or WorkspaceInstructionStatusInfo()
        self.validation_plan = validation_plan or WorkspaceValidationPlanInfo()
        self.command_history = command_history or {}

    def instruction_status_snapshot(self, root: Path) -> WorkspaceInstructionStatusInfo:
        return self.instruction_status

    def validation_plan_snapshot(self, root: Path) -> WorkspaceValidationPlanInfo:
        return self.validation_plan

    def command_history_snapshot(self, root: Path) -> dict[str, object]:
        return self.command_history

    def workspace_readiness_snapshot(self, **kwargs: object) -> WorkspaceReadinessInfo:
        return self.readiness


class CountingAutopilotAgent(FakeAutopilotAgent):
    def __init__(
        self,
        *,
        readiness: WorkspaceReadinessInfo,
        instruction_status: WorkspaceInstructionStatusInfo | None = None,
        validation_plan: WorkspaceValidationPlanInfo | None = None,
        command_history: dict[str, object] | None = None,
    ):
        super().__init__(
            readiness=readiness,
            instruction_status=instruction_status,
            validation_plan=validation_plan,
            command_history=command_history,
        )
        self.instruction_status_calls = 0
        self.validation_plan_calls = 0
        self.command_history_calls = 0
        self.readiness_calls = 0

    def instruction_status_snapshot(self, root: Path) -> WorkspaceInstructionStatusInfo:
        self.instruction_status_calls += 1
        return super().instruction_status_snapshot(root)

    def validation_plan_snapshot(self, root: Path) -> WorkspaceValidationPlanInfo:
        self.validation_plan_calls += 1
        return super().validation_plan_snapshot(root)

    def command_history_snapshot(self, root: Path) -> dict[str, object]:
        self.command_history_calls += 1
        return super().command_history_snapshot(root)

    def workspace_readiness_snapshot(self, **kwargs: object) -> WorkspaceReadinessInfo:
        self.readiness_calls += 1
        return super().workspace_readiness_snapshot(**kwargs)


class CountingProjectPlanScaffolder:
    def __init__(self) -> None:
        self.calls = 0

    def plan_from_prompt(self, request: ProjectScaffoldPlanRequest) -> ProjectScaffoldPlanResponse:
        self.calls += 1
        preset = ProjectScaffoldPreset(
            id="cpp-msvc-console-sln",
            label="C++ Console Solution",
            framework="MSVC",
            language="C++",
            validation_command="cmake --build build",
        )
        scaffold_request = ProjectScaffoldRequest(
            target_path=request.preferred_target_path or "C:/aegis-cache-test",
            preset_id=preset.id,
            project_name=f"cached-plan-{self.calls}",
            prompt=request.prompt,
            validation_command=preset.validation_command,
            run_validation=True,
        )
        return ProjectScaffoldPlanResponse(
            ok=True,
            message="planned",
            prompt=request.prompt,
            confidence=0.9,
            preset=preset,
            project_name=scaffold_request.project_name,
            target_path=scaffold_request.target_path,
            validation_command=scaffold_request.validation_command,
            scaffold_request=scaffold_request,
        )


class WorkspaceAutopilotStatusTests(unittest.TestCase):
    def tearDown(self) -> None:
        main._clear_workspace_status_cache()
        main._clear_project_plan_cache()

    def test_repeated_project_plan_requests_use_short_lived_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "plan-cache-workspace"
            target = workspace / "console-app"
            request = ProjectScaffoldPlanRequest(
                prompt="Create a C++ console app that prints hello world and build it.",
                workspace_root=str(workspace),
                preferred_target_path=str(target),
            )
            fake_scaffolder = CountingProjectPlanScaffolder()

            with patch.object(main, "project_scaffolder", lambda: fake_scaffolder):
                first = main._cached_project_plan(request)
                second = main._cached_project_plan(request)
                second.project_name = "mutated-client-copy"
                third = main._cached_project_plan(request)

                self.assertEqual(fake_scaffolder.calls, 1)
                self.assertEqual(first.project_name, "cached-plan-1")
                self.assertEqual(third.project_name, "cached-plan-1")

                main._clear_project_plan_cache()
                refreshed = main._cached_project_plan(request)

                self.assertEqual(fake_scaffolder.calls, 2)
                self.assertEqual(refreshed.project_name, "cached-plan-2")

    def test_profile_and_autopilot_status_share_short_lived_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "cached-workspace"
            readiness = WorkspaceReadinessInfo(
                status="ready",
                score=91,
                summary="Workspace is ready.",
                next_action="Summarize the finished state.",
                signals=["Validation passed."],
            )
            manager = CountingAutopilotWorkspaceManager(workspace)
            agent = CountingAutopilotAgent(readiness=readiness)

            with (
                patch.object(main, "workspace_manager", manager),
                patch.object(main, "agent", agent),
            ):
                profile = asyncio.run(main.workspace_profile(str(workspace)))
                status = asyncio.run(main.workspace_autopilot_status(str(workspace)))

                self.assertEqual(profile.readiness.status, "ready")
                self.assertEqual(status.phase, "ready")
                self.assertEqual(manager.manifest_calls, 1)
                self.assertEqual(manager.dependency_profile_calls, 1)
                self.assertEqual(agent.instruction_status_calls, 1)
                self.assertEqual(agent.validation_plan_calls, 1)
                self.assertEqual(agent.command_history_calls, 1)
                self.assertEqual(agent.readiness_calls, 1)

                main._clear_workspace_status_cache(workspace)
                asyncio.run(main.workspace_autopilot_status(str(workspace)))

                self.assertEqual(manager.manifest_calls, 2)
                self.assertEqual(manager.dependency_profile_calls, 2)
                self.assertEqual(agent.instruction_status_calls, 2)
                self.assertEqual(agent.validation_plan_calls, 2)
                self.assertEqual(agent.command_history_calls, 2)
                self.assertEqual(agent.readiness_calls, 2)

    def test_routes_repair_state_with_validation_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "repair-workspace"
            manifest = WorkspaceProjectManifest(
                schema="aegis.project.v1",
                project_name="repair",
                validation_command="python build.py",
            )
            readiness = WorkspaceReadinessInfo(
                status="needs_repair",
                score=25,
                summary="Validation failed.",
                next_action="Repair python build.py, inspect captured build output, and rerun validation.",
                blockers=["Validation failed at build."],
                signals=["Manifest found."],
            )
            validation_plan = WorkspaceValidationPlanInfo(
                schema="aegis.validation_plan.v1",
                validation_command="python build.py",
                last_run={
                    "status": "failed",
                    "command": "python build.py",
                    "failed_step": "validation-1",
                },
            )
            command_history = {
                "validation_command": "python build.py",
                "commands": [
                    {
                        "kind": "validation",
                        "status": "failed",
                        "command": "python build.py",
                        "failed_step": "2",
                        "failed_step_command": "python build.py --smoke",
                        "diagnostics": [
                            {
                                "file": "src/main.cpp",
                                "line": 17,
                                "column": 5,
                                "severity": "error",
                                "code": "C2143",
                                "message": "syntax error: missing semicolon",
                            }
                        ],
                    }
                ],
            }

            with (
                patch.object(main, "workspace_manager", FakeAutopilotWorkspaceManager(workspace, manifest=manifest)),
                patch.object(
                    main,
                    "agent",
                    FakeAutopilotAgent(
                        readiness=readiness,
                        validation_plan=validation_plan,
                        command_history=command_history,
                    ),
                ),
            ):
                status = asyncio.run(main.workspace_autopilot_status(str(workspace)))

        self.assertEqual(status.phase, "repair")
        self.assertTrue(status.should_continue)
        self.assertEqual(status.recommended_mode, "develop")
        self.assertTrue(status.run_validation)
        self.assertEqual(status.max_repair_attempts, 3)
        self.assertEqual(status.pass_budget, 6)
        self.assertEqual(status.validation_command, "python build.py")
        self.assertEqual(status.latest_validation_status, "failed")
        self.assertEqual(status.failed_step, "2")
        self.assertEqual(status.failed_step_command, "python build.py --smoke")
        self.assertEqual(status.first_diagnostic, "src/main.cpp:17:5 error C2143")
        self.assertIn("Repair step 2: python build.py --smoke", status.repair_brief)
        self.assertIn("diagnostic src/main.cpp:17:5 error C2143", status.repair_brief)
        self.assertIn("Repair brief:", status.suggested_prompt)
        self.assertIn("Objective:", status.suggested_prompt)
        self.assertIn("python build.py --smoke", "\n".join(status.recommendations))

    def test_routes_work_state_with_instruction_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "work-workspace"
            manifest = WorkspaceProjectManifest(
                schema="aegis.project.v1",
                project_name="dashboard",
                validation_command="npm run build",
            )
            dependency_profile = WorkspaceDependencyProfile(validation_commands=["npm run build"])
            instruction_status = WorkspaceInstructionStatusInfo(
                schema="aegis.instruction_status.v1",
                open_items=7,
                completed_items=2,
                total_items=9,
                files=[
                    WorkspaceInstructionStatusFile(
                        path="whatever.md",
                        title="Custom Launch Plan",
                        kind="instruction",
                        open_items=3,
                        completed_items=1,
                        total_items=4,
                        pending_items=[
                            "Build the dashboard.",
                            "Wire booking requests.",
                            "Run the CMake release build.",
                        ],
                    )
                ],
                recommendation="Build the dashboard.",
            )
            readiness = WorkspaceReadinessInfo(
                status="needs_work",
                score=52,
                summary="Open roadmap items remain.",
                next_action="Continue the next open instruction item: Build the dashboard.",
                signals=["Instruction checkpoint found."],
            )

            with (
                patch.object(
                    main,
                    "workspace_manager",
                    FakeAutopilotWorkspaceManager(
                        workspace,
                        manifest=manifest,
                        dependency_profile=dependency_profile,
                    ),
                ),
                patch.object(
                    main,
                    "agent",
                    FakeAutopilotAgent(
                        readiness=readiness,
                        instruction_status=instruction_status,
                    ),
                ),
            ):
                status = asyncio.run(main.workspace_autopilot_status(str(workspace)))

        self.assertEqual(status.phase, "work")
        self.assertTrue(status.should_continue)
        self.assertEqual(status.recommended_mode, "build")
        self.assertTrue(status.run_validation)
        self.assertEqual(status.max_repair_attempts, 2)
        self.assertEqual(status.pass_budget, 11)
        self.assertEqual(status.open_items, 7)
        self.assertEqual(status.completed_items, 2)
        self.assertEqual(status.total_items, 9)
        self.assertEqual(status.validation_command, "npm run build")
        self.assertIn("Build the dashboard", status.suggested_prompt)
        self.assertEqual(status.instruction_source, "aegis.instruction_status.v1")
        self.assertEqual(len(status.instruction_files), 1)
        self.assertEqual(status.instruction_files[0].path, "whatever.md")
        self.assertEqual(status.next_open_items[:2], ["Build the dashboard.", "Wire booking requests."])
        self.assertIn("Next open instruction items", status.suggested_prompt)

    def test_large_work_state_gets_longer_autopilot_budget_and_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "large-workspace"
            manifest = WorkspaceProjectManifest(
                schema="aegis.project.v1",
                project_name="full-product",
                framework="React + FastAPI",
                language="TypeScript + Python",
                package_manager="npm + pip",
                validation_command="npm run build",
                tags=["web", "api", "database", "tests"],
            )
            dependency_profile = WorkspaceDependencyProfile(
                languages=["TypeScript", "Python"],
                frameworks=["React", "FastAPI"],
                package_managers=["npm", "pip"],
                build_systems=["vite", "pytest"],
                config_files=["package.json", "pyproject.toml", "vite.config.ts"],
                validation_commands=["npm run build", "pytest"],
                database_tools=["sqlite"],
            )
            instruction_status = WorkspaceInstructionStatusInfo(
                schema="aegis.instruction_status.v1",
                open_items=18,
                completed_items=4,
                total_items=24,
                files=[
                    WorkspaceInstructionStatusFile(
                        path="BUILD_PLAN.md",
                        title="Full Product Plan",
                        kind="instruction",
                        open_items=18,
                        completed_items=4,
                        total_items=24,
                        pending_items=[f"Complete vertical slice {index}." for index in range(1, 14)],
                    )
                ],
            )
            readiness = WorkspaceReadinessInfo(
                status="needs_work",
                score=41,
                summary="Large product build still has open vertical slices.",
                next_action="Continue the next open product slice and validate it.",
                signals=["Instruction checkpoint found.", "Validation command detected."],
            )

            with (
                patch.object(
                    main,
                    "workspace_manager",
                    FakeAutopilotWorkspaceManager(
                        workspace,
                        manifest=manifest,
                        dependency_profile=dependency_profile,
                    ),
                ),
                patch.object(
                    main,
                    "agent",
                    FakeAutopilotAgent(
                        readiness=readiness,
                        instruction_status=instruction_status,
                    ),
                ),
            ):
                status = asyncio.run(main.workspace_autopilot_status(str(workspace)))

        self.assertEqual(status.phase, "work")
        self.assertTrue(status.large_task_mode)
        self.assertIn(status.complexity, {"large", "epic"})
        self.assertGreaterEqual(status.pass_budget, 26)
        self.assertEqual(status.estimated_passes_remaining, status.pass_budget)
        self.assertIn("frontend", status.execution_lanes)
        self.assertIn("backend", status.execution_lanes)
        self.assertIn("database", status.execution_lanes)
        self.assertIn("Large-task protocol", status.suggested_prompt)
        self.assertIn("vertical slices", "\n".join(status.recommendations))

    def test_routes_ready_state_to_clean_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "ready-workspace"
            readiness = WorkspaceReadinessInfo(
                status="ready",
                score=92,
                summary="Workspace is ready.",
                next_action="Summarize the finished state.",
                signals=["Validation passed."],
            )

            with (
                patch.object(main, "workspace_manager", FakeAutopilotWorkspaceManager(workspace)),
                patch.object(main, "agent", FakeAutopilotAgent(readiness=readiness)),
            ):
                status = asyncio.run(main.workspace_autopilot_status(str(workspace)))

        self.assertEqual(status.phase, "ready")
        self.assertFalse(status.should_continue)
        self.assertEqual(status.pass_budget, 0)
        self.assertFalse(status.run_validation)
        self.assertIn("ready", status.stop_reason.lower())


if __name__ == "__main__":
    unittest.main()
