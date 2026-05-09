from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.model_manager import ModelManager
from aegis_ai.schemas import ModelOperationInfo, ModelRegistryResponse
from aegis_ai.settings import Settings


class EmptyRegistry:
    def snapshot(self) -> ModelRegistryResponse:
        return ModelRegistryResponse(active_provider_id="", active_model="", providers=[])


class ModelManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(_env_file=None)
        self.manager = ModelManager(self.project_root, self.settings, EmptyRegistry())  # type: ignore[arg-type]

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_snapshot_ignores_damaged_operations_path(self) -> None:
        self.manager.operations_path.mkdir(parents=True)

        snapshot = self.manager.snapshot(minimum_free_gb=0)

        self.assertEqual(snapshot.operations, [])
        self.assertTrue(self.manager.operations_path.is_dir())

    def test_load_operations_skips_invalid_records(self) -> None:
        self.manager.operations_path.parent.mkdir(parents=True)
        self.manager.operations_path.write_text(
            json.dumps(
                [
                    {"id": "valid", "model_name": "qwen-test:7b", "action": "pull", "status": "running"},
                    {"id": "invalid", "pid": "not-an-int"},
                    "not an operation",
                ]
            ),
            encoding="utf-8",
        )

        operations = self.manager._load_operations()

        self.assertEqual([operation.id for operation in operations], ["valid"])

    def test_save_operations_writes_atomically_and_cleans_temp_name(self) -> None:
        self.manager._save_operations([ModelOperationInfo(id="op-1", model_name="qwen-test:7b")])

        payload = json.loads(self.manager.operations_path.read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["id"], "op-1")
        self.assertFalse((self.manager.operations_path.parent / ".operations.json.tmp").exists())

    def test_snapshot_skips_damaged_pull_log_summary(self) -> None:
        (self.project_root / "logs" / "model-pulls" / "summary.json").mkdir(parents=True)

        snapshot = self.manager.snapshot(minimum_free_gb=0)

        self.assertEqual(snapshot.pull_logs, [])


if __name__ == "__main__":
    unittest.main()
