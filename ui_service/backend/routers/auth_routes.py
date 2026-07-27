from typing import Any

from fastapi import APIRouter, Depends, status

import services.auth_service as auth_service
from deps import get_current_user
from models.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    Token,
    UpdateSettingsRequest,
    UpdateSettingsResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest) -> RegisterResponse:
    return await auth_service.register(req)


@router.get("/me", response_model=RegisterResponse)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> RegisterResponse:
    return await auth_service.get_me(current_user)


@router.put("/me", response_model=UpdateSettingsResponse)
async def update_me(
    req: UpdateSettingsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UpdateSettingsResponse:
    return await auth_service.update_me(req, current_user)


@router.post("/login", response_model=Token)
async def login(req: LoginRequest) -> Token:
    return await auth_service.login(req)


@router.post("/password-reset-request", response_model=MessageResponse)
async def password_reset_request(req: PasswordResetRequest) -> MessageResponse:
    return await auth_service.password_reset_request(req)


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def password_reset_confirm(req: PasswordResetConfirm) -> MessageResponse:
    return await auth_service.password_reset_confirm(req)
