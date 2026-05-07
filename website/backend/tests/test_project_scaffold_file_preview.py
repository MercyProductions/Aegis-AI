from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_file_preview import (
    diff_preview_stage,
    diff_summary,
    scaffold_file_change_preview,
)
from aegis_ai.schemas import ProjectScaffoldFile, ProjectScaffoldPreset


class ProjectScaffoldFilePreviewTests(unittest.TestCase):
    def test_scaffold_file_change_preview_detects_create_and_update(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir)
            (target / "README.md").write_text("old\n", encoding="utf-8")

            changes, file_infos = scaffold_file_change_preview(
                target,
                preset(),
                {
                    "README.md": "updated\n",
                    "src/app.py": "print('hello')\n",
                },
            )

        self.assertEqual([change.path for change in changes], ["README.md", "src/app.py"])
        self.assertEqual([change.action for change in changes], ["update", "create"])
        self.assertEqual(changes[0].summary, "Update README.md for the Test Preset preset.")
        self.assertEqual([info.action for info in file_infos], ["update", "create"])
        self.assertEqual(file_infos[1].size, len("print('hello')\n".encode("utf-8")))

    def test_diff_summary_orders_create_update_delete_counts(self) -> None:
        summary = diff_summary(
            [
                ProjectScaffoldFile(path="new.py", action="create"),
                ProjectScaffoldFile(path="old.py", action="update"),
                ProjectScaffoldFile(path="gone.py", action="delete"),
            ]
        )

        self.assertEqual(summary, ["+ 1 create", "~ 1 update", "- 1 delete"])

    def test_diff_preview_stage_uses_summary_or_empty_message(self) -> None:
        populated = diff_preview_stage(
            [
                ProjectScaffoldFile(path="a.py", action="create"),
                ProjectScaffoldFile(path="b.py", action="create"),
            ]
        )
        empty = diff_preview_stage([])

        self.assertEqual(populated.id, "diff")
        self.assertEqual(populated.status, "succeeded")
        self.assertEqual(populated.detail, "+ 2 create")
        self.assertEqual(empty.detail, "No file changes are planned.")


def preset() -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id="test",
        label="Test Preset",
        framework="test",
        language="test",
    )


if __name__ == "__main__":
    unittest.main()
