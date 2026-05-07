from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.creative_media import CreativeMediaEngine
from aegis_ai.schemas import MediaCreativeRequest, MediaExportRequest
from aegis_ai.settings import Settings


class CreativeStudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.settings = Settings(_env_file=None, default_workspace="workspace", aegis_database_path="data/test.sqlite3")
        self.engine = CreativeMediaEngine(self.project_root, self.settings)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_image_job_asset_library_and_zip_export(self) -> None:
        job = self.engine.create_job(
            MediaCreativeRequest(
                kind="logo",
                studio="image",
                prompt="Create a premium logo for Auralith Creative Studio",
                output_formats=["png", "svg", "zip"],
            )
        )
        library = self.engine.asset_library()
        export = self.engine.export_job(job.id, MediaExportRequest(format="zip"))

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.provider_id, "local_creative_renderer")
        self.assertTrue(any(asset.format == "svg" for asset in job.assets))
        self.assertTrue(job.timeline)
        self.assertGreaterEqual(library.total_assets, len(job.assets))
        self.assertTrue(Path(export.path).exists())
        with zipfile.ZipFile(export.path) as archive:
            self.assertIn("manifest.json", archive.namelist())

    def test_audio_jobs_generate_beat_midi_and_voice_assets(self) -> None:
        beat = self.engine.create_job(
            MediaCreativeRequest(
                kind="music_beat",
                studio="beat",
                prompt="Generate a clean tech beat with crisp drums",
                bpm=104,
                key="C minor",
                duration_seconds=3,
            )
        )
        voice = self.engine.create_job(
            MediaCreativeRequest(
                kind="voiceover",
                studio="voice",
                prompt="Create a calm narration for a product launch",
                voice="calm narrator",
                duration_seconds=2,
            )
        )

        self.assertTrue(any(asset.format == "wav" for asset in beat.assets))
        self.assertTrue(any(asset.format == "midi" for asset in beat.assets))
        self.assertTrue(any("stems" in asset.role for asset in beat.assets))
        self.assertTrue(any(asset.format == "wav" for asset in voice.assets))

    def test_safety_approval_gates_paid_providers_sensitive_styles_and_voice_clone(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.create_job(
                MediaCreativeRequest(
                    kind="image",
                    prompt="Create a product image",
                    provider_id="cloud_image_api",
                )
            )
        with self.assertRaises(ValueError):
            self.engine.create_job(
                MediaCreativeRequest(
                    kind="image",
                    prompt="Create an icon in the style of a famous living artist",
                )
            )
        with self.assertRaises(ValueError):
            self.engine.create_job(
                MediaCreativeRequest(
                    kind="voiceover",
                    prompt="Read this line",
                    operation="clone",
                    voice="clone sample",
                )
            )

    def test_creative_studio_api_lifecycle(self) -> None:
        with (
            patch.object(main, "creative_media", self.engine),
            TestClient(main.app) as client,
        ):
            capabilities = client.get("/api/creative-studio")
            created = client.post(
                "/api/creative-studio/jobs",
                json={
                    "kind": "ui_mockup",
                    "studio": "image",
                    "prompt": "Create a calm project dashboard mockup",
                    "output_formats": ["png", "svg"],
                },
            )
            job_id = created.json()["id"]
            jobs = client.get("/api/creative-studio/jobs")
            assets = client.get("/api/creative-studio/assets")
            export = client.post(f"/api/creative-studio/jobs/{job_id}/export", json={"format": "zip"})
            blocked = client.post(
                "/api/creative-studio/jobs",
                json={
                    "kind": "text_to_video",
                    "provider_id": "cloud_video_api",
                    "prompt": "Create a paid promo video",
                    "duration_seconds": 12,
                },
            )

        self.assertEqual(capabilities.status_code, 200, capabilities.text)
        self.assertTrue(capabilities.json()["providers"])
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["status"], "completed")
        self.assertEqual(jobs.status_code, 200, jobs.text)
        self.assertTrue(jobs.json())
        self.assertEqual(assets.status_code, 200, assets.text)
        self.assertGreater(assets.json()["total_assets"], 0)
        self.assertEqual(export.status_code, 200, export.text)
        self.assertTrue(Path(export.json()["path"]).exists())
        self.assertEqual(blocked.status_code, 400)


if __name__ == "__main__":
    unittest.main()
