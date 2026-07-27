from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from ui_utils.user_validators import (
    normalize_admin_role,
    normalize_lock_status,
    validate_password,
    validate_username,
)
from models.watchlist import WatchlistStock


class AdminUser(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    admin: Optional[str] = None
    lock: Optional[str] = None
    followed_stocks: list[WatchlistStock] = []


class AssignStockRequest(BaseModel):
    stock_id: str


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
