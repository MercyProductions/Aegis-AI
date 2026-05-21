from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    ValidateRequest,
    ValidateResponse,
    ValidationProfileResponse,
    ValidationProfileUpdateRequest,
    VerificationRequest,
    VerificationResponse,
)


def register_validation_routes(
    app: FastAPI,
    *,
    validate_workspace: Callable[[ValidateRequest], Awaitable[ValidateResponse]],
    verify_workspace: Callable[[VerificationRequest], Awaitable[VerificationResponse]],
    validation_profile: Callable[[str | None], Awaitable[ValidationProfileResponse]],
    update_validation_profile: Callable[
        [ValidationProfileUpdateRequest, str | None],
        Awaitable[ValidationProfileResponse],
    ],
) -> None:
    @app.post("/api/validate", response_model=ValidateResponse)
    async def post_validate_workspace(request: ValidateRequest) -> ValidateResponse:
        return await validate_workspace(request)

    @app.post("/api/verify", response_model=VerificationResponse)
    async def post_verify_workspace(request: VerificationRequest) -> VerificationResponse:
        return await verify_workspace(request)

    @app.get("/api/validation/profile", response_model=ValidationProfileResponse)
    async def get_validation_profile(
        workspace_root: str | None = Query(default=None),
    ) -> ValidationProfileResponse:
        return await validation_profile(workspace_root)

    @app.put("/api/validation/profile", response_model=ValidationProfileResponse)
    async def put_validation_profile(
        request: ValidationProfileUpdateRequest,
        workspace_root: str | None = Query(default=None),
    ) -> ValidationProfileResponse:
        return await update_validation_profile(request, workspace_root)
