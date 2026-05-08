from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aegis_ai.creative_media import CreativeMediaEngine, infer_theme_color
from aegis_ai.schemas import MediaCreativeRequest
from aegis_ai.settings import Settings


class CreativeMediaTests(unittest.TestCase):
    def test_infers_theme_color_and_honors_override(self) -> None:
        self.assertEqual(infer_theme_color("luxury premium launch"), "#d7a84f")
        self.assertEqual(infer_theme_color("anything", "#123abc"), "#123abc")
        self.assertEqual(infer_theme_color("anything", "teal"), "#14b8a6")

    def test_creates_editable_media_package(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = CreativeMediaEngine(Path(tmp), Settings(_env_file=None))
            response = engine.create_job(
                MediaCreativeRequest(
                    prompt="Create a premium AI product launch visual",
                    kind="psd_template",
                    theme_color="gold",
                )
            )

            formats = {asset.format for asset in response.assets}
            self.assertEqual(response.theme_color, "#d7a84f")
            self.assertIn("svg", formats)
            self.assertIn("jsx", formats)
            self.assertIn("json", formats)
            self.assertTrue((Path(response.job_dir) / "manifest.json").exists())
            self.assertTrue((Path(response.job_dir) / "layer_manifest.json").exists())

    def test_revision_keeps_previous_job_link(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = CreativeMediaEngine(Path(tmp), Settings(_env_file=None))
            first = engine.create_job(MediaCreativeRequest(prompt="A green finance dashboard image", kind="image"))
            revision = engine.create_job(
                MediaCreativeRequest(
                    prompt="Make it cleaner and add more depth",
                    kind="image",
                    previous_job_id=first.id,
                    feedback="Make it cleaner and add more depth",
                )
            )

            self.assertEqual(revision.previous_job_id, first.id)
            self.assertIn("Preserve useful composition", (Path(revision.job_dir) / "creative_brief.md").read_text(encoding="utf-8"))

    def test_lists_and_loads_media_jobs(self) -> None:
        with TemporaryDirectory() as tmp:
            engine = CreativeMediaEngine(Path(tmp), Settings(_env_file=None))
            beat = engine.create_job(MediaCreativeRequest(prompt="Create a dark trap beat", kind="music_beat"))
            image = engine.create_job(MediaCreativeRequest(prompt="Create a launch image", kind="image"))

            jobs = engine.list_jobs(limit=10)
            image_jobs = engine.list_jobs(limit=10, kind="image")
            loaded = engine.get_job(beat.id)

            self.assertGreaterEqual(len(jobs), 2)
            self.assertEqual(image_jobs[0].id, image.id)
            self.assertEqual(loaded.id, beat.id)
            self.assertIn("wav", {asset.format for asset in loaded.assets})


if __name__ == "__main__":
    unittest.main()
