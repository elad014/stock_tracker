import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def _validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


def _validate_username(user_name: str) -> str:
    if len(user_name) < 3:
        raise ValueError("Username must be at least 3 characters")
    return user_name


class RegisterRequest(BaseModel):
    user_name: str
    email: EmailStr
    password: str
    phone_number: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("user_name")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username(v)


class RegisterResponse(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    is_admin: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class MessageResponse(BaseModel):
    message: str


class UpdateSettingsRequest(BaseModel):
    user_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator(
        "user_name",
        "email",
        "phone_number",
        "old_password",
        "new_password",
        mode="before",
    )
    @classmethod
    def blank_as_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("user_name")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validate_username(v)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validate_password(v)


class UpdateSettingsResponse(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    message: str
    access_token: Optional[str] = None


class WatchlistStock(BaseModel):
    id: str
    name: str
    price: Optional[float] = None
    trend: Optional[float | str] = None


class AddWatchlistRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        ticker = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{1,5}", ticker):
            raise ValueError("Stock name must be 1–5 letters (e.g. AAPL)")
        return ticker


class AdminUser(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    followed_stocks: list[WatchlistStock] = []


class AssignStockRequest(BaseModel):
    stock_id: str


class AdminCreateUserRequest(BaseModel):
    user_name: str
    email: EmailStr
    password: str
    phone_number: str
    admin: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("user_name")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username(v)

    @field_validator("admin", mode="before")
    @classmethod
    def normalize_admin(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            value = v.strip().lower()
            if not value:
                return None
            if value == "admin":
                return "admin"
            raise ValueError("Admin field must be empty or 'admin'")
        return v


class AdminUpdateUserRequest(BaseModel):
    user_name: str
    email: EmailStr
    phone_number: str

    @field_validator("user_name")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username(v)


class AdminSetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)
