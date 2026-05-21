from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from ..creative_media import CreativeMediaEngine
from ..schemas import (
    MediaAssetLibraryResponse,
    MediaCapabilitiesResponse,
    MediaCreativeRequest,
    MediaExportRequest,
    MediaExportResponse,
    MediaJobResponse,
    MediaPromptPreset,
    MediaProviderInfo,
)


def register_media_routes(
    app: FastAPI,
    *,
    creative_media_factory: Callable[[], CreativeMediaEngine],
) -> None:
    def creative_media() -> CreativeMediaEngine:
        return creative_media_factory()

    @app.get("/api/media/capabilities", response_model=MediaCapabilitiesResponse)
    async def media_capabilities() -> MediaCapabilitiesResponse:
        return creative_media().capabilities()

    @app.get("/api/creative-studio", response_model=MediaCapabilitiesResponse)
    async def creative_studio_capabilities() -> MediaCapabilitiesResponse:
        return creative_media().capabilities()

    @app.get("/api/media/providers", response_model=list[MediaProviderInfo])
    async def media_providers() -> list[MediaProviderInfo]:
        return creative_media().providers()

    @app.get("/api/creative-studio/providers", response_model=list[MediaProviderInfo])
    async def creative_studio_providers() -> list[MediaProviderInfo]:
        return creative_media().providers()

    @app.get("/api/media/prompt-presets", response_model=list[MediaPromptPreset])
    async def media_prompt_presets() -> list[MediaPromptPreset]:
        return creative_media().prompt_presets()

    @app.get("/api/creative-studio/prompt-presets", response_model=list[MediaPromptPreset])
    async def creative_studio_prompt_presets() -> list[MediaPromptPreset]:
        return creative_media().prompt_presets()

    @app.get("/api/media/jobs", response_model=list[MediaJobResponse])
    async def list_media_jobs(
        limit: int = Query(default=50, ge=1, le=200),
        kind: str = Query(default=""),
    ) -> list[MediaJobResponse]:
        return creative_media().list_jobs(limit=limit, kind=kind)

    @app.get("/api/creative-studio/jobs", response_model=list[MediaJobResponse])
    async def list_creative_studio_jobs(
        limit: int = Query(default=50, ge=1, le=200),
        kind: str = Query(default=""),
    ) -> list[MediaJobResponse]:
        return creative_media().list_jobs(limit=limit, kind=kind)

    @app.get("/api/media/jobs/{job_id}", response_model=MediaJobResponse)
    async def get_media_job(job_id: str) -> MediaJobResponse:
        try:
            return creative_media().get_job(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc

    @app.get("/api/creative-studio/jobs/{job_id}", response_model=MediaJobResponse)
    async def get_creative_studio_job(job_id: str) -> MediaJobResponse:
        return await get_media_job(job_id)

    @app.post("/api/media/jobs", response_model=MediaJobResponse)
    async def create_media_job(request: MediaCreativeRequest) -> MediaJobResponse:
        try:
            return creative_media().create_job(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/creative-studio/jobs", response_model=MediaJobResponse)
    async def create_creative_studio_job(request: MediaCreativeRequest) -> MediaJobResponse:
        return await create_media_job(request)

    @app.post("/api/media/jobs/{job_id}/cancel", response_model=MediaJobResponse)
    async def cancel_media_job(job_id: str) -> MediaJobResponse:
        try:
            return creative_media().cancel_job(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc

    @app.post("/api/creative-studio/jobs/{job_id}/cancel", response_model=MediaJobResponse)
    async def cancel_creative_studio_job(job_id: str) -> MediaJobResponse:
        return await cancel_media_job(job_id)

    @app.get("/api/media/assets", response_model=MediaAssetLibraryResponse)
    async def media_asset_library(
        limit: int = Query(default=100, ge=1, le=500),
        kind: str = Query(default=""),
        format: str = Query(default=""),
    ) -> MediaAssetLibraryResponse:
        return creative_media().asset_library(limit=limit, kind=kind, fmt=format)

    @app.get("/api/creative-studio/assets", response_model=MediaAssetLibraryResponse)
    async def creative_studio_asset_library(
        limit: int = Query(default=100, ge=1, le=500),
        kind: str = Query(default=""),
        format: str = Query(default=""),
    ) -> MediaAssetLibraryResponse:
        return creative_media().asset_library(limit=limit, kind=kind, fmt=format)

    @app.get("/api/creative-studio/assets/file")
    async def creative_studio_asset_file(path: str = Query(min_length=1)) -> FileResponse:
        requested = Path(path).resolve()
        base = creative_media().base_dir.resolve()
        try:
            requested.relative_to(base)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="asset path is outside the creative library") from exc
        if not requested.exists() or not requested.is_file():
            raise HTTPException(status_code=404, detail="asset not found")
        return FileResponse(requested)

    @app.post("/api/media/jobs/{job_id}/export", response_model=MediaExportResponse)
    async def export_media_job(job_id: str, request: MediaExportRequest) -> MediaExportResponse:
        try:
            return creative_media().export_job(job_id, request)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc

    @app.post("/api/creative-studio/jobs/{job_id}/export", response_model=MediaExportResponse)
    async def export_creative_studio_job(job_id: str, request: MediaExportRequest) -> MediaExportResponse:
        return await export_media_job(job_id, request)
