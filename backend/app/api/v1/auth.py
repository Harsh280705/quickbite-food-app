"""Authentication endpoints: POST /auth/login, GET /me."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, RegisterRequest
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange email/password for a signed access token",
)
async def login(session: DbSession, payload: LoginRequest) -> LoginResponse:
    user, token, expires_in = await auth_service.authenticate(
        session, email=payload.email, password=payload.password
    )
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=MeResponse.model_validate(user).model_dump(),  # type: ignore[arg-type]
    )


@router.post(
    "/auth/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer account and issue an access token",
)
async def register(session: DbSession, payload: RegisterRequest) -> LoginResponse:
    user, token, expires_in = await auth_service.register(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=MeResponse.model_validate(user).model_dump(),  # type: ignore[arg-type]
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current authenticated user",
)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(user)  # type: ignore[arg-type]
