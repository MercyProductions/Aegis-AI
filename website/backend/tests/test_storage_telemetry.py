from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import RouteQualityResponse
from aegis_ai.storage_telemetry import (
    bounded_snapshot_limits,
    model_json,
    parse_snapshot_timestamp,
    snapshot_updated_before,
    telemetry_snapshot_from_row,
    telemetry_snapshot_key,
)


class StorageTelemetryTests(unittest.TestCase):
    def test_bounded_snapshot_limits_and_key_are_stable(self) -> None:
        self.assertEqual(bounded_snapshot_limits(0, 999, 1200), (1, 100, 500))
        self.assertEqual(bounded_snapshot_limits(200, 20, 75), (200, 20, 75))
        self.assertEqual(telemetry_snapshot_key(200, 20, 75), "route:200|fallback:20|feedback:75")

    def test_snapshot_timestamp_parsing_and_cutoff_comparison(self) -> None:
        parsed = parse_snapshot_timestamp("2026-01-01T12:00:00Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)

        naive = parse_snapshot_timestamp("2026-01-01T12:00:00")
        self.assertIsNotNone(naive)
        self.assertEqual(naive.tzinfo, timezone.utc)

        cutoff = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.assertTrue(snapshot_updated_before("2026-01-01T12:00:00Z", cutoff))
        self.assertFalse(snapshot_updated_before("not-a-date", cutoff))

    def test_telemetry_snapshot_from_row_rehydrates_payloads_and_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            project_root = Path(tempdir)
            updated_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            try:
                conn.execute(
                    """
                    create table snapshots (
                        id text,
                        snapshot_key text,
                        created_at text,
                        updated_at text,
                        route_quality_limit integer,
                        fallback_limit integer,
                        feedback_limit integer,
                        stale_after_seconds integer,
                        route_quality_json text,
                        fallback_inspector_json text,
                        feedback_json text
                    )
                    """
                )
                conn.execute(
                    """
                    insert into snapshots values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "snapshot-1",
                        telemetry_snapshot_key(50, 10, 25),
                        "2026-01-01T00:00:00+00:00",
                        updated_at,
                        50,
                        10,
                        25,
                        90,
                        json.dumps(
                            {
                                "workspace_root": "/workspace",
                                "limit": 50,
                                "overview": {"model_attempt_count": 3},
                            }
                        ),
                        json.dumps({"workspace_root": "/workspace", "limit": 10, "task_count": 2}),
                        json.dumps(
                            {
                                "workspace_root": "/workspace",
                                "limit": 25,
                                "summary": {"feedback_count": 4, "positive_rate": 0.5},
                            }
                        ),
                    ),
                )
                row = conn.execute("select * from snapshots").fetchone()
                snapshot = telemetry_snapshot_from_row(row, project_root, stale_after_seconds=60)

                self.assertEqual(snapshot.id, "snapshot-1")
                self.assertEqual(snapshot.workspace_root, str(project_root.resolve()))
                self.assertEqual(snapshot.route_quality.overview.model_attempt_count, 3)
                self.assertEqual(snapshot.fallback_inspector.task_count, 2)
                self.assertEqual(snapshot.feedback.summary.feedback_count, 4)
                self.assertTrue(snapshot.is_stale)
            finally:
                conn.close()

    def test_model_json_sorts_pydantic_payloads(self) -> None:
        payload = model_json(RouteQualityResponse(workspace_root="/workspace", limit=2))

        self.assertLess(payload.index('"limit"'), payload.index('"overview"'))
        self.assertIn('"workspace_root": "/workspace"', payload)
