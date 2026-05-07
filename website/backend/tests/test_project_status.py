from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_status import (
    display_workspace_relative_path,
    latest_project_build_log,
    read_aegis_json,
    read_text_tail,
    redact_project_status_text,
    safe_log_display_path,
    safe_project_build_log_path,
    status_text,
)


class ProjectStatusTests(unittest.TestCase):
    def test_read_aegis_json_only_returns_small_top_level_dicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            aegis_dir = workspace / ".aegis"
            aegis_dir.mkdir()
            (aegis_dir / "valid.json").write_text('{"status": "ready"}', encoding="utf-8")
            (aegis_dir / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
            (aegis_dir / "invalid.json").write_text("{broken", encoding="utf-8")

            self.assertEqual(read_aegis_json(workspace, "valid.json"), {"status": "ready"})
            self.assertEqual(read_aegis_json(workspace, "list.json"), {})
            self.assertEqual(read_aegis_json(workspace, "invalid.json"), {})
            self.assertEqual(read_aegis_json(workspace, "../valid.json"), {})

    def test_safe_project_build_log_path_confines_logs_to_build_log_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            logs_dir = workspace / ".aegis" / "build_logs"
            logs_dir.mkdir(parents=True)
            allowed = logs_dir / "run.log"
            allowed.write_text("ok", encoding="utf-8")
            rejected_extension = logs_dir / "run.json"
            rejected_extension.write_text("{}", encoding="utf-8")
            outside = workspace / ".aegis" / "secret.log"
            outside.write_text("secret", encoding="utf-8")

            self.assertEqual(safe_project_build_log_path(workspace, ".aegis/build_logs/run.log"), allowed.resolve())
            self.assertEqual(safe_project_build_log_path(workspace, str(allowed)), allowed.resolve())
            self.assertIsNone(safe_project_build_log_path(workspace, "run.log"))
            self.assertIsNone(safe_project_build_log_path(workspace, ".aegis/build_logs/../secret.log"))
            self.assertIsNone(safe_project_build_log_path(workspace, str(outside)))
            self.assertIsNone(safe_project_build_log_path(workspace, str(rejected_extension)))

    def test_safe_log_display_path_and_relative_display_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            log = workspace / ".aegis" / "build_logs" / "latest.txt"
            log.parent.mkdir(parents=True)
            log.write_text("latest", encoding="utf-8")
            outside = workspace.parent / "outside.log"

            self.assertEqual(safe_log_display_path(workspace, str(log)), ".aegis/build_logs/latest.txt")
            self.assertEqual(safe_log_display_path(workspace, "not/a/safe/log"), "not/a/safe/log")
            self.assertEqual(display_workspace_relative_path(workspace, log), ".aegis/build_logs/latest.txt")
            self.assertEqual(display_workspace_relative_path(workspace, outside), "outside.log")

    def test_latest_project_build_log_prefers_newest_safe_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            logs_dir = workspace / ".aegis" / "build_logs"
            logs_dir.mkdir(parents=True)
            older = logs_dir / "older.log"
            newer = logs_dir / "newer.md"
            ignored = logs_dir / "ignored.json"
            older.write_text("older", encoding="utf-8")
            newer.write_text("newer", encoding="utf-8")
            ignored.write_text("ignored", encoding="utf-8")
            os.utime(older, (100, 100))
            os.utime(newer, (200, 200))
            os.utime(ignored, (300, 300))

            latest = latest_project_build_log(workspace, [".aegis/build_logs/older.log"])

            self.assertIsNotNone(latest)
            display, path = latest or ("", Path())
            self.assertEqual(display, ".aegis/build_logs/newer.md")
            self.assertEqual(path.resolve(), newer.resolve())

    def test_read_text_tail_handles_missing_and_truncated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "log.txt"
            path.write_text("0123456789abcdefghijklmnopqrstuvwxyz", encoding="utf-8")

            excerpt = read_text_tail(path, max_chars=24)

            self.assertLessEqual(len(excerpt), 24)
            self.assertTrue(excerpt.startswith("[truncated to latest"))
            self.assertEqual(read_text_tail(Path(temp_dir) / "missing.log", max_chars=24), "")

    def test_status_text_compacts_defaults_and_limits(self) -> None:
        self.assertEqual(status_text(None, default="fallback"), "fallback")
        self.assertEqual(status_text("  alpha\r\n beta \t gamma  "), "alpha beta gamma")
        self.assertEqual(status_text("abcdef", limit=3), "abc")

    def test_redact_project_status_text_removes_common_secret_shapes(self) -> None:
        text = "\n".join(
            [
                "openai=sk-1234567890abcdefghij",
                "github=ghp_1234567890abcdefghij",
                "pat=github_pat_1234567890abcdefghij",
                "aws=AKIA1234567890ABCDEF",
                "slack=xoxb-1234567890abcdefghij",
                "jwt=eyJabcdefgh.abcdefghij.klmnopqrst",
                "password='super-secret'",
                "token=plain-secret",
            ]
        )

        redacted = redact_project_status_text(text)

        self.assertNotIn("sk-1234567890abcdefghij", redacted)
        self.assertNotIn("ghp_1234567890abcdefghij", redacted)
        self.assertNotIn("github_pat_1234567890abcdefghij", redacted)
        self.assertNotIn("AKIA1234567890ABCDEF", redacted)
        self.assertNotIn("xoxb-1234567890abcdefghij", redacted)
        self.assertNotIn("eyJabcdefgh.abcdefghij.klmnopqrst", redacted)
        self.assertNotIn("super-secret", redacted)
        self.assertNotIn("plain-secret", redacted)
        self.assertIn("[REDACTED_OPENAI_KEY]", redacted)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", redacted)
        self.assertIn("[REDACTED_AWS_KEY]", redacted)
        self.assertIn("[REDACTED_SLACK_TOKEN]", redacted)
        self.assertIn("[REDACTED_JWT]", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)


if __name__ == "__main__":
    unittest.main()
