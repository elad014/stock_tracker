from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from ui_utils.user_validators import (
    normalize_admin_role,
    normalize_lock_status,
    validate_password,
    validate_username,
)
from models.watchlist import WatchlistStock

_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")


class AdminUser(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    admin: Optional[str] = None
    lock: Optional[str] = None
    followed_stocks: list[WatchlistStock] = []


class AssignStockRequest(BaseModel):
    stock_id: Optional[str] = None
    symbol: Optional[str] = None


class CreateAdminStockRequest(BaseModel):
    name: str = Field(..., description="Ticker symbol, e.g. AAPL")
    user_ids: list[str] = Field(
        ...,
        min_length=1,
        description="One or more user UUIDs to receive the stock on their watchlist",
    )

    @field_validator("name")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not _TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("Invalid ticker (e.g. AAPL, BRK.A)")
        return ticker

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for user_id in value:
            normalized = str(user_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        if not cleaned:
            raise ValueError("Select at least one user")
        return cleaned


class AdminCreateUserRequest(BaseModel):
    user_name: str
    email: EmailStr
    password: str
    phone_number: str
    admin: Optional[str] = None
    lock: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return validate_password(v)

    @field_validator("user_name")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("admin", mode="before")
    @classmethod
    def normalize_admin(cls, v: object) -> object:
        return normalize_admin_role(v)

    @field_validator("lock", mode="before")
    @classmethod
    def normalize_lock(cls, v: object) -> object:
        return normalize_lock_status(v)


class AdminUpdateUserRequest(BaseModel):
    user_name: str
    email: EmailStr
    phone_number: str
    admin: Optional[str] = None
    lock: Optional[str] = None

    @field_validator("user_name")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("admin", mode="before")
    @classmethod
    def normalize_admin(cls, v: object) -> object:
        return normalize_admin_role(v)

    @field_validator("lock", mode="before")
    @classmethod
    def normalize_lock(cls, v: object) -> object:
        return normalize_lock_status(v)


class AdminSetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return validate_password(v)
