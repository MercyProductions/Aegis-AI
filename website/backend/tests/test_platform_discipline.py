from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.continuity import AegisContinuityEngine
from aegis_ai.platform_discipline import PlatformDisciplineEngine
from aegis_ai.schemas import UnifiedContextSnapshot
from aegis_ai.settings import Settings
from aegis_ai.unified_runtime import RuntimeSignalCounts, UnifiedRuntimeEngine
from aegis_ai.workspace import WorkspaceManager


def _runtime_snapshot(root: Path):
    return UnifiedRuntimeEngine().snapshot(
        workspace_root=root,
        counts=RuntimeSignalCounts(
            task_count=3,
            active_task_count=1,
            project_memory_count=2,
            fix_memory_count=1,
            creative_job_count=1,
            creative_asset_count=1,
            worker_count=1,
            queue_job_count=0,
            objective_count=0,
            pending_approval_count=1,
            recommendation_count=2,
            project_intelligence_ready=True,
        ),
    )


def _continuity_snapshot(root: Path):
    context = UnifiedContextSnapshot(
        workspace_root=str(root),
        generated_at="2026-05-07T00:00:00+00:00",
        records=[],
        relationships=[],
    )
    return AegisContinuityEngine().snapshot(workspace_root=root, context=context)


class PlatformDisciplineTests(unittest.TestCase):
    def test_engine_selects_domains_tiers_budgets_and_deprecated_paths(self) -> None:
        root = Path("C:/workspace")
        snapshot = PlatformDisciplineEngine().snapshot(
            workspace_root=root,
            runtime=_runtime_snapshot(root),
            continuity=_continuity_snapshot(root),
        )

        self.assertEqual(snapshot.api_version, "2026.05.07")
        self.assertEqual(snapshot.stewardship.id, "platform_stewardship")
        self.assertIn("trust", snapshot.stewardship.preserve)
        self.assertIn("friction", snapshot.stewardship.reduce)
        self.assertIn("responsiveness", snapshot.stewardship.improve)
        self.assertEqual(snapshot.feature_admission.default_decision, "reject_when_unclear")
        self.assertEqual(len(snapshot.feature_admission.criteria), 10)
        self.assertTrue(any("unclear value" in item for item in snapshot.feature_admission.hard_no_rules))
        self.assertEqual([item.id for item in snapshot.primary_domains], ["coding_workspace", "orchestration_runtime", "memory_knowledge_os"])
        self.assertTrue(any(item.id == "desktop_operating_layer" for item in snapshot.experimental_domains))
        self.assertTrue(any(item.id == "stable_runtime" for item in snapshot.stability_tiers))
        self.assertTrue(any(item.status == "deprecated" for item in snapshot.roadmap))
        self.assertTrue(any(item.id == "frontend_bundle" and item.status == "watch" for item in snapshot.performance_budgets))
        self.assertTrue(any(item.id == "rollback" and item.status == "ready" for item in snapshot.security_foundations))
        self.assertTrue(any("coding workspace" in item.lower() for item in snapshot.recommendations))

    def test_platform_discipline_api_returns_contract_for_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            settings = Settings(
                _env_file=None,
                default_workspace="workspace",
                aegis_database_path="data/test.sqlite3",
                approval_tier="guided",
                sandbox_profile="standard",
            )
            workspace_manager = WorkspaceManager(project_root, settings)
            workspace = workspace_manager.resolve_workspace("workspace")

            with (
                patch.object(main, "settings", settings),
                patch.object(main, "workspace_manager", workspace_manager),
                patch.object(main, "_unified_runtime_snapshot", side_effect=lambda root: _runtime_snapshot(root)),
                patch.object(main, "_continuity_snapshot", side_effect=lambda root: _continuity_snapshot(root)),
                patch.object(main, "platform_discipline", PlatformDisciplineEngine()),
                TestClient(main.app) as client,
            ):
                response = client.get("/api/platform-discipline", params={"workspace_root": str(workspace)})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("local-first", payload["core_identity"])
        self.assertEqual(payload["stewardship"]["id"], "platform_stewardship")
        self.assertIn("powerful without feeling chaotic", payload["stewardship"]["product_feel"])
        self.assertEqual(payload["feature_admission"]["default_decision"], "reject_when_unclear")
        self.assertTrue(any("dashboard sprawl" in item for item in payload["feature_admission"]["hard_no_rules"]))
        self.assertEqual(len(payload["primary_domains"]), 3)
        self.assertTrue(any(item["id"] == "uncontrolled_autonomy" for item in payload["roadmap"]))
        self.assertTrue(any(item["id"] == "stable_runtime" for item in payload["stability_tiers"]))
        self.assertGreaterEqual(payload["deprecated_count"], 1)


if __name__ == "__main__":
    unittest.main()
