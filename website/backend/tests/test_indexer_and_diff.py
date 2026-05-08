from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.diff_engine import DiffEngine
from aegis_ai.project_indexer import ProjectIndexer
from aegis_ai.schemas import WorkspaceFile


class IndexerAndDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_project_indexer_uses_content_keywords(self) -> None:
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        target = self.root / "src" / "payments.py"
        target.write_text(
            "class BillingLedger:\n    def reconcile_invoice(self):\n        return 'ok'\n",
            encoding="utf-8",
        )
        files = [
            WorkspaceFile(path="src/payments.py", size=target.stat().st_size, kind="text"),
            WorkspaceFile(path="README.md", size=0, kind="text"),
        ]

        indexer = ProjectIndexer()
        indexer.build_from_workspace(self.root, files)
        results = indexer.find_relevant_files("reconcile invoice bug", max_results=3)

        self.assertTrue(results)
        self.assertEqual(results[0].path, "src/payments.py")

    def test_project_indexer_samples_large_files_instead_of_skipping_them(self) -> None:
        (self.root / "src").mkdir(parents=True, exist_ok=True)
        target = self.root / "src" / "giant_module.cpp"
        target.write_text(
            "class ImportantSubsystem {};\n"
            + "".join(f"int filler_{index} = {index};\n" for index in range(45_000))
            + "void TailOnlyRepairTarget() {}\n",
            encoding="utf-8",
        )
        files = [
            WorkspaceFile(
                path="src/giant_module.cpp",
                size=target.stat().st_size,
                kind="text",
                is_large=True,
                estimated_lines=45_002,
                large_file_strategy="large-file summarized context; read targeted line slices before patching",
            )
        ]

        indexer = ProjectIndexer()
        indexer.build_from_workspace(self.root, files)
        results = indexer.find_relevant_files("repair TailOnlyRepairTarget in huge file", max_results=3)

        self.assertTrue(results)
        self.assertEqual(results[0].path, "src/giant_module.cpp")
        self.assertTrue(results[0].is_large)
        self.assertGreaterEqual(results[0].estimated_lines, 45_000)

    def test_diff_engine_generates_unified_patch_and_applies_it(self) -> None:
        old_content = "alpha\nbeta\ngamma\n"
        new_content = "alpha\nbeta changed\ngamma\ndelta\n"

        diff = DiffEngine.compare_files(old_content, new_content, "example.txt", "update")
        patch = diff.get_patch()

        self.assertIn("--- a/example.txt", patch)
        self.assertIn("+++ b/example.txt", patch)
        self.assertGreaterEqual(diff.added_lines, 1)
        self.assertGreaterEqual(diff.removed_lines, 1)
        self.assertEqual(DiffEngine.apply_patch(old_content, patch), new_content.rstrip("\n"))

    def test_diff_summary_names_append_changes(self) -> None:
        diff = DiffEngine.compare_files("alpha\n", "alpha\nbeta\n", "huge.txt", "append")

        self.assertEqual(DiffEngine.summarize_diff(diff), "Append to huge.txt (+1 lines)")


if __name__ == "__main__":
    unittest.main()
