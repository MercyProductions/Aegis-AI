from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Query

from ..providers.accounts import (
    ProviderAccountError,
    ProviderAccountLinkResponse,
    ProviderAccountManager,
    ProviderAccountsResponse,
    ProviderApiKeyLinkRequest,
    ProviderCliLoginResponse,
    ProviderCliProbeRequest,
    ProviderSourceRefreshJobResponse,
    ProviderSourceRefreshJobsResponse,
    ProviderSourceRefreshRequest,
    ProviderSourceRefreshResponse,
    ProviderSourceRootOpenRequest,
    ProviderSourceRootOpenResponse,
)


def register_provider_account_routes(
    app: FastAPI,
    *,
    provider_accounts_factory: Callable[[], ProviderAccountManager],
) -> None:
    def manager() -> ProviderAccountManager:
        return provider_accounts_factory()

    def provider_error(exc: ProviderAccountError) -> HTTPException:
        return HTTPException(status_code=exc.status_code, detail=str(exc))

    @app.get("/api/provider-accounts", response_model=ProviderAccountsResponse)
    async def provider_account_snapshot() -> ProviderAccountsResponse:
        return manager().snapshot()

    @app.post("/api/provider-accounts/{provider_id}/api-key", response_model=ProviderAccountLinkResponse)
    async def link_provider_api_key(
        provider_id: str,
        request: ProviderApiKeyLinkRequest,
    ) -> ProviderAccountLinkResponse:
        try:
            return manager().link_api_key(provider_id, request)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/{provider_id}/cli-session", response_model=ProviderAccountLinkResponse)
    async def link_provider_cli_session(provider_id: str) -> ProviderAccountLinkResponse:
        try:
            return manager().link_cli_session(provider_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.delete("/api/provider-accounts/{provider_id}", response_model=ProviderAccountsResponse)
    async def unlink_provider_account(provider_id: str) -> ProviderAccountsResponse:
        try:
            return manager().unlink_provider(provider_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/cli-bridges/probe", response_model=ProviderAccountsResponse)
    async def probe_provider_cli_bridges(request: ProviderCliProbeRequest) -> ProviderAccountsResponse:
        try:
            return manager().probe_cli_bridges(request.provider_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/{provider_id}/cli-login", response_model=ProviderCliLoginResponse)
    async def start_provider_cli_login(provider_id: str) -> ProviderCliLoginResponse:
        try:
            return manager().start_cli_login(provider_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/source-root/open", response_model=ProviderSourceRootOpenResponse)
    async def open_provider_source_root(request: ProviderSourceRootOpenRequest) -> ProviderSourceRootOpenResponse:
        try:
            return manager().open_source_root(request.path)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/source-drops/refresh", response_model=ProviderSourceRefreshResponse)
    async def refresh_provider_source_drop(request: ProviderSourceRefreshRequest) -> ProviderSourceRefreshResponse:
        try:
            return manager().refresh_source_drop(request)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/source-drops/refresh-jobs", response_model=ProviderSourceRefreshJobResponse)
    async def start_provider_source_refresh_job(request: ProviderSourceRefreshRequest) -> ProviderSourceRefreshJobResponse:
        try:
            return manager().start_source_refresh_job(request)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.get("/api/provider-accounts/source-drops/refresh-jobs", response_model=ProviderSourceRefreshJobsResponse)
    async def provider_source_refresh_jobs(limit: int = Query(default=25, ge=1, le=100)) -> ProviderSourceRefreshJobsResponse:
        return manager().source_refresh_jobs_response(limit=limit)

    @app.get("/api/provider-accounts/source-drops/refresh-jobs/{job_id}", response_model=ProviderSourceRefreshJobResponse)
    async def provider_source_refresh_job(job_id: str) -> ProviderSourceRefreshJobResponse:
        try:
            return manager().source_refresh_job_response(job_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/source-drops/refresh-jobs/{job_id}/cancel", response_model=ProviderSourceRefreshJobResponse)
    async def cancel_provider_source_refresh_job(job_id: str) -> ProviderSourceRefreshJobResponse:
        try:
            return manager().cancel_source_refresh_job(job_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc

    @app.post("/api/provider-accounts/source-drops/refresh-jobs/{job_id}/retry", response_model=ProviderSourceRefreshJobResponse)
    async def retry_provider_source_refresh_job(job_id: str) -> ProviderSourceRefreshJobResponse:
        try:
            return manager().retry_source_refresh_job(job_id)
        except ProviderAccountError as exc:
            raise provider_error(exc) from exc
