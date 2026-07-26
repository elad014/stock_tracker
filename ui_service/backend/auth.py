import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "utils"))

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
import bcrypt
import httpx

logger = logging.getLogger(__name__)

from db_logics.user_db_logic import (
    create_user,
    get_user_by_email,
    get_user_by_phone,
    get_user_by_username,
    is_admin_role,
    update_password,
    update_user_fields,
)
from deps import get_current_user
from email_client import mailer
from models import (
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

load_dotenv()

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
RESET_TOKEN_EXPIRE_MINUTES = 15

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(data: dict, expires_minutes: int) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest) -> RegisterResponse:
    if await get_user_by_email(req.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    if await get_user_by_username(req.user_name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    if await get_user_by_phone(req.phone_number):
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already registered")

    user = await create_user(
        user_name=req.user_name,
        hashed_password=_hash_password(req.password),
        email=req.email,
        phone_number=req.phone_number,
    )
    return RegisterResponse(**user)


@router.get("/me", response_model=RegisterResponse)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> RegisterResponse:
    return RegisterResponse(
        id=str(current_user["id"]),
        user_name=current_user["user_name"],
        email=current_user["email"],
        phone_number=current_user["phone_number"],
        is_admin=is_admin_role(current_user.get("admin")),
    )


@router.put("/me", response_model=UpdateSettingsResponse)
async def update_me(
    req: UpdateSettingsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UpdateSettingsResponse:
    user_id: str = str(current_user["id"])
    old_email: str = current_user["email"]
    changes: list[dict[str, str]] = []
    new_user_name: Optional[str] = None
    new_email: Optional[str] = None
    new_phone: Optional[str] = None
    new_hashed_password: Optional[str] = None

    if req.user_name is not None and req.user_name != current_user["user_name"]:
        owner = await get_user_by_username(req.user_name)
        if owner and str(owner["id"]) != user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
        changes.append(
            {
                "field": "Username",
                "old": current_user["user_name"],
                "new": req.user_name,
            }
        )
        new_user_name = req.user_name

    if req.email is not None and req.email != current_user["email"]:
        owner = await get_user_by_email(req.email)
        if owner and str(owner["id"]) != user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        changes.append(
            {
                "field": "Email",
                "old": current_user["email"],
                "new": req.email,
            }
        )
        new_email = req.email

    if req.phone_number is not None and req.phone_number != current_user["phone_number"]:
        owner = await get_user_by_phone(req.phone_number)
        if owner and str(owner["id"]) != user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already registered")
        changes.append(
            {
                "field": "Phone",
                "old": current_user["phone_number"],
                "new": req.phone_number,
            }
        )
        new_phone = req.phone_number

    if req.new_password is not None:
        if not req.old_password:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Current password is required to set a new password",
            )
        if not _verify_password(req.old_password, current_user["password"]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
        new_hashed_password = _hash_password(req.new_password)
        changes.append({"field": "Password"})

    if not changes:
        return UpdateSettingsResponse(
            id=user_id,
            user_name=current_user["user_name"],
            email=current_user["email"],
            phone_number=current_user["phone_number"],
            message="No changes to save",
        )

    await update_user_fields(
        user_id,
        user_name=new_user_name,
        email=new_email,
        phone_number=new_phone,
        hashed_password=new_hashed_password,
    )

    updated_user_name: str = new_user_name or current_user["user_name"]
    updated_email: str = new_email or current_user["email"]
    updated_phone: str = new_phone or current_user["phone_number"]

    recipients: set[str] = {old_email, updated_email}
    try:
        for recipient in recipients:
            await mailer.send_account_changes(to=recipient, changes=changes)
    except (httpx.HTTPStatusError, httpx.RequestError):
        logger.error("Failed to send account change email for user %s", user_id)

    access_token: Optional[str] = None
    if new_email is not None:
        access_token = _create_token(
            {"sub": updated_email, "user_id": user_id},
            ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    return UpdateSettingsResponse(
        id=user_id,
        user_name=updated_user_name,
        email=updated_email,
        phone_number=updated_phone,
        message="Settings updated successfully",
        access_token=access_token,
    )


@router.post("/login", response_model=Token)
async def login(req: LoginRequest) -> Token:
    user = await get_user_by_email(req.email)
    if not user or not _verify_password(req.password, user["password"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = _create_token(
        {"sub": user["email"], "user_id": str(user["id"])},
        ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/password-reset-request", response_model=MessageResponse)
async def password_reset_request(req: PasswordResetRequest) -> MessageResponse:
    """Always returns success to avoid leaking whether email exists."""
    user = await get_user_by_email(req.email)
    if user:
        token = _create_token({"sub": user["email"], "type": "reset"}, RESET_TOKEN_EXPIRE_MINUTES)
        try:
            await mailer.send_password_reset(to=user["email"], reset_token=token)
        except (httpx.HTTPStatusError, httpx.RequestError):
            logger.error("Failed to send password reset email to %s", req.email)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Email service is not available right now, please try again later",
            )
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def password_reset_confirm(req: PasswordResetConfirm) -> MessageResponse:
    try:
        payload = jwt.decode(req.token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "reset":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid reset token")
        email: Optional[str] = payload.get("sub")
    except JWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    if not email or not await get_user_by_email(email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid reset token")

    await update_password(email, _hash_password(req.new_password))
    return MessageResponse(message="Password has been reset successfully")
