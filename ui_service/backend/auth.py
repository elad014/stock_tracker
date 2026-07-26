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
    update_password,
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
