from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import (
    ProjectScaffoldPlanRequest,
    ProjectScaffoldPlanResponse,
    ProjectScaffoldPreset,
    ProjectScaffoldRequest,
)
from aegis_ai.workspace_cache import (
    ProjectPlanCache,
    WorkspaceStatusSnapshot,
    WorkspaceStatusSnapshotCache,
    cache_paths_are_related,
    normalized_cache_path,
    project_plan_cache_key,
)


class WorkspaceCacheTests(unittest.TestCase):
    def test_related_cache_paths_match_parent_and_child_paths(self) -> None:
        root = normalized_cache_path(Path("C:/work/app"))
        child = normalized_cache_path(Path("C:/work/app/src"))
        sibling = normalized_cache_path(Path("C:/work/application"))

        self.assertTrue(cache_paths_are_related(root, child))
        self.assertTrue(cache_paths_are_related(child, root))
        self.assertFalse(cache_paths_are_related(root, sibling))

    def test_workspace_status_cache_clears_related_paths(self) -> None:
        cache = WorkspaceStatusSnapshotCache(ttl_seconds=5, max_size=10)
        root = Path("C:/work/app")
        child = root / "src"
        other = Path("C:/work/other")
        snapshot = WorkspaceStatusSnapshot(
            created_at=10.0,
            manifest=None,
            dependency_profile=None,
            instruction_status=None,
            validation_plan=None,
            command_history={},
            readiness=None,
        )

        cache.set(root, snapshot)
        cache.set(other, snapshot)
        self.assertIs(cache.get(root, now=12.0), snapshot)

        cache.clear(child)

        self.assertIsNone(cache.get(root, now=12.0))
        self.assertIs(cache.get(other, now=12.0), snapshot)

    def test_project_plan_cache_returns_deep_copies_and_expires_entries(self) -> None:
        request = ProjectScaffoldPlanRequest(prompt="Build a focused CLI.")
        response = _plan_response("cached-plan")
        cache = ProjectPlanCache(ttl_seconds=5, max_size=10)

        cache.set(request, response, now=10.0)
        first = cache.get(request, now=12.0)
        assert first is not None
        first.project_name = "mutated"
        second = cache.get(request, now=12.0)

        self.assertIsNotNone(second)
        assert second is not None
        self.assertEqual(second.project_name, "cached-plan")
        self.assertIsNone(cache.get(request, now=16.1))

    def test_project_plan_cache_key_is_order_stable(self) -> None:
        first = ProjectScaffoldPlanRequest(prompt="Build a CLI.", preferred_target_path="C:/work/app")
        second = ProjectScaffoldPlanRequest(preferred_target_path="C:/work/app", prompt="Build a CLI.")

        self.assertEqual(project_plan_cache_key(first), project_plan_cache_key(second))


def _plan_response(project_name: str) -> ProjectScaffoldPlanResponse:
    preset = ProjectScaffoldPreset(
        id="python-cli",
        label="Python CLI",
        language="Python",
        framework="stdlib",
        validation_command="python -m pytest",
    )
    scaffold_request = ProjectScaffoldRequest(
        target_path=f"C:/work/{project_name}",
        preset_id=preset.id,
        project_name=project_name,
        prompt="Build a focused CLI.",
        validation_command=preset.validation_command,
    )
    return ProjectScaffoldPlanResponse(
        ok=True,
        message="planned",
        prompt="Build a focused CLI.",
        confidence=0.9,
        preset=preset,
        project_name=project_name,
        target_path=scaffold_request.target_path,
        validation_command=scaffold_request.validation_command,
        scaffold_request=scaffold_request,
    )


if __name__ == "__main__":
    unittest.main()
