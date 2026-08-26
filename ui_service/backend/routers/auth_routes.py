from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

import services.auth_service as auth_service
from deps import get_current_user
from models.auth import (
    EncryptedPayload,
    LoginPublicKey,
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
from ui_utils.payload_crypto import decrypt_json, public_jwk
from ui_utils.rate_limit import client_ip, login_by_ip

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, request: Request) -> RegisterResponse:
    return await auth_service.register(req, client_ip(request))


@router.get("/me", response_model=RegisterResponse)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> RegisterResponse:
    return await auth_service.get_me(current_user)


@router.put("/me", response_model=UpdateSettingsResponse)
async def update_me(
    req: UpdateSettingsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UpdateSettingsResponse:
    return await auth_service.update_me(req, current_user)


@router.get("/public-key", response_model=LoginPublicKey)
async def get_login_public_key() -> LoginPublicKey:
    return LoginPublicKey.model_validate(public_jwk())


@router.post("/login", response_model=Token)
async def login(req: EncryptedPayload, request: Request) -> Token:
    ip: str = client_ip(request)
    login_by_ip.assert_allowed(ip)
    try:
        plain: dict[str, Any] = decrypt_json(req.wrapped_key, req.iv, req.ciphertext)
        login_req: LoginRequest = LoginRequest.model_validate(plain)
    except (ValueError, ValidationError) as exc:
        login_by_ip.record(ip)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid login payload") from exc
    return await auth_service.login(login_req, ip)


@router.post("/password-reset-request", response_model=MessageResponse)
async def password_reset_request(req: PasswordResetRequest, request: Request) -> MessageResponse:
    return await auth_service.password_reset_request(req, client_ip(request))


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def password_reset_confirm(req: PasswordResetConfirm) -> MessageResponse:
    return await auth_service.password_reset_confirm(req)
