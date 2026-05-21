from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from ..auth import AccountStore, AuthSession
from ..schemas import (
    AuthForgotPasswordRequest,
    AuthLoginRequest,
    AuthMessageResponse,
    AuthRegisterRequest,
    AuthSessionResponse,
)


AccountStoreFactory = Callable[[], AccountStore]


def register_auth_routes(app: FastAPI, *, account_store_factory: AccountStoreFactory) -> None:
    def store() -> AccountStore:
        return account_store_factory()

    def auth_response(session: AuthSession) -> AuthSessionResponse:
        return AuthSessionResponse(token=session.token, user=session.user, expires_at=session.expires_at)

    def extract_bearer_token(authorization: str | None) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authentication required.")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="Authentication required.")
        return token.strip()

    def session_from_authorization(authorization: str | None) -> tuple[Any, str]:
        token = extract_bearer_token(authorization)
        session = store().user_for_token(token)
        if session is None:
            raise HTTPException(status_code=401, detail="Session expired or invalid.")
        return session

    @app.post("/api/auth/register", response_model=AuthSessionResponse)
    async def register_account(request: AuthRegisterRequest) -> AuthSessionResponse:
        if request.password != request.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match.")

        try:
            user = store().create_account(name=request.name, email=request.email, password=request.password)
            session = store().create_session(user, remember_me=True)
            return auth_response(session)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/auth/login", response_model=AuthSessionResponse)
    async def login_account(request: AuthLoginRequest) -> AuthSessionResponse:
        try:
            session = store().authenticate(
                email=request.email,
                password=request.password,
                remember_me=request.remember_me,
            )
            return auth_response(session)
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/api/auth/me", response_model=AuthSessionResponse)
    async def current_account(authorization: str | None = Header(default=None)) -> AuthSessionResponse:
        user, expires_at = session_from_authorization(authorization)
        return AuthSessionResponse(token="", user=user, expires_at=expires_at)

    @app.post("/api/auth/logout", response_model=AuthMessageResponse)
    async def logout_account(authorization: str | None = Header(default=None)) -> AuthMessageResponse:
        token = extract_bearer_token(authorization)
        store().delete_session(token)
        return AuthMessageResponse(message="Signed out.")

    @app.post("/api/auth/forgot-password", response_model=AuthMessageResponse)
    async def forgot_password(request: AuthForgotPasswordRequest) -> AuthMessageResponse:
        # The local-first runtime has no outbound email channel yet, so this endpoint
        # intentionally avoids revealing whether an account exists.
        _ = request.email
        return AuthMessageResponse(message="If an account exists, password recovery instructions will be sent when email is configured.")
