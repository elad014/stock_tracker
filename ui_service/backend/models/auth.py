from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from ui_utils.user_validators import validate_password, validate_username


class RegisterRequest(BaseModel):
    user_name: str
    email: EmailStr
    password: str
    phone_number: str

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return validate_password(v)

    @field_validator("user_name")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)


class RegisterResponse(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    is_admin: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginPublicKey(BaseModel):
    kty: str
    n: str
    e: str


class EncryptedPayload(BaseModel):
    wrapped_key: str
    iv: str
    ciphertext: str

    @field_validator("wrapped_key", "iv", "ciphertext")
    @classmethod
    def require_ciphertext_fields(cls, v: str) -> str:
        stripped: str = v.strip()
        if not stripped or len(stripped) > 8192:
            raise ValueError("Invalid encrypted payload")
        return stripped


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
    def validate_password_field(cls, v: str) -> str:
        return validate_password(v)


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
    def validate_username_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_username(v)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_password(v)


class UpdateSettingsResponse(BaseModel):
    id: str
    user_name: str
    email: str
    phone_number: str
    message: str
    access_token: Optional[str] = None
