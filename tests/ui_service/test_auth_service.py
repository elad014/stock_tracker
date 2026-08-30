from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException
from jose import jwt

from conftest import load_backend_module


auth_service = load_backend_module("ui_service", "services.auth_service")
auth_models = load_backend_module("ui_service", "models.auth")


class _Limiter:
    def __init__(self):
        self.recorded = []
        self.reset_keys = []

    def assert_allowed(self, _key):
        return None

    def record(self, key):
        self.recorded.append(key)

    def reset(self, key):
        self.reset_keys.append(key)


class _Mailer:
    def __init__(self):
        self.password_resets = []
        self.account_changes = []

    async def send_password_reset(self, to, reset_token):
        self.password_resets.append((to, reset_token))

    async def send_account_changes(self, to, changes):
        self.account_changes.append((to, changes))


@pytest.fixture(autouse=True)
def reset_rate_limiters(monkeypatch):
    monkeypatch.setattr(auth_service, "register_by_ip", _Limiter())
    monkeypatch.setattr(auth_service, "login_by_email", _Limiter())
    monkeypatch.setattr(auth_service, "login_by_ip", _Limiter())
    monkeypatch.setattr(auth_service, "reset_by_email", _Limiter())
    monkeypatch.setattr(auth_service, "reset_by_ip", _Limiter())


def _register_request(**overrides):
    data = {
        "user_name": "alice",
        "email": "alice@example.com",
        "password": "Strong123",
        "phone_number": "+15555550100",
    }
    data.update(overrides)
    return auth_models.RegisterRequest(**data)


@pytest.mark.asyncio
async def test_register_creates_user_with_hashed_password(monkeypatch):
    created = {}

    async def no_user(_value):
        return None

    async def create_user(**kwargs):
        created.update(kwargs)
        return {
            "id": "user-1",
            "user_name": kwargs["user_name"],
            "email": kwargs["email"],
            "phone_number": kwargs["phone_number"],
            "is_admin": False,
        }

    monkeypatch.setattr(auth_service, "get_user_by_email", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_username", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_phone", no_user)
    monkeypatch.setattr(auth_service, "create_user", create_user)

    result = await auth_service.register(_register_request(), "127.0.0.1")

    assert result.id == "user-1"
    assert created["hashed_password"] != "Strong123"
    assert auth_service.verify_password("Strong123", created["hashed_password"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lookup_name", "detail"),
    [
        ("get_user_by_email", "Email already registered"),
        ("get_user_by_username", "Username already taken"),
        ("get_user_by_phone", "Phone number already registered"),
    ],
    ids=["duplicate email", "duplicate username", "duplicate phone"],
)
async def test_register_rejects_duplicate_identity(monkeypatch, lookup_name, detail):
    async def no_user(_value):
        return None

    async def existing_user(_value):
        return {"id": "other-user"}

    monkeypatch.setattr(auth_service, "get_user_by_email", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_username", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_phone", no_user)
    monkeypatch.setattr(auth_service, lookup_name, existing_user)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(_register_request(), "127.0.0.1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == detail


@pytest.mark.asyncio
async def test_login_returns_bearer_token_for_valid_credentials(monkeypatch):
    password_hash = auth_service.hash_password("Strong123")
    user = {
        "id": "user-1",
        "email": "alice@example.com",
        "password": password_hash,
        "lock": None,
    }

    async def get_user_by_email(_email):
        return user

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)

    result = await auth_service.login(
        auth_models.LoginRequest(email="alice@example.com", password="Strong123"),
        "127.0.0.1",
    )
    payload = jwt.decode(
        result.access_token,
        auth_service.JWT_SECRET_KEY,
        algorithms=[auth_service.ALGORITHM],
    )

    assert result.token_type == "bearer"
    assert payload["sub"] == "alice@example.com"
    assert payload["user_id"] == "user-1"
    assert auth_service.login_by_email.reset_keys == ["alice@example.com"]


@pytest.mark.asyncio
async def test_login_rejects_bad_password(monkeypatch):
    async def get_user_by_email(_email):
        return {
            "id": "user-1",
            "email": "alice@example.com",
            "password": auth_service.hash_password("Strong123"),
            "lock": None,
        }

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            auth_models.LoginRequest(email="alice@example.com", password="Wrong123"),
            "127.0.0.1",
        )

    assert exc_info.value.status_code == 401
    assert auth_service.login_by_email.recorded == ["alice@example.com"]


@pytest.mark.asyncio
async def test_login_rejects_locked_account(monkeypatch):
    async def get_user_by_email(_email):
        return {
            "id": "user-1",
            "email": "alice@example.com",
            "password": auth_service.hash_password("Strong123"),
            "lock": "lock",
        }

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            auth_models.LoginRequest(email="alice@example.com", password="Strong123"),
            "127.0.0.1",
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_password_reset_request_does_not_reveal_unknown_email(monkeypatch):
    mailer = _Mailer()

    async def get_user_by_email(_email):
        return None

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth_service, "mailer", mailer)

    result = await auth_service.password_reset_request(
        auth_models.PasswordResetRequest(email="missing@example.com"),
        "127.0.0.1",
    )

    assert result.message == "If the email exists, a reset link has been sent"
    assert mailer.password_resets == []


@pytest.mark.asyncio
async def test_password_reset_request_sends_token_for_active_user(monkeypatch):
    mailer = _Mailer()

    async def get_user_by_email(_email):
        return {"email": "alice@example.com", "lock": None}

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth_service, "mailer", mailer)

    await auth_service.password_reset_request(
        auth_models.PasswordResetRequest(email="alice@example.com"),
        "127.0.0.1",
    )

    assert len(mailer.password_resets) == 1
    assert mailer.password_resets[0][0] == "alice@example.com"


@pytest.mark.asyncio
async def test_update_me_no_changes_does_not_write(monkeypatch):
    async def fail_update(*_args, **_kwargs):
        raise AssertionError("update should not be called")

    monkeypatch.setattr(auth_service, "update_user_fields", fail_update)
    current_user = {
        "id": "user-1",
        "user_name": "alice",
        "email": "alice@example.com",
        "phone_number": "+15555550100",
        "password": auth_service.hash_password("Strong123"),
    }

    result = await auth_service.update_me(auth_models.UpdateSettingsRequest(), current_user)

    assert result.message == "No changes to save"
    assert result.access_token is None


@pytest.mark.asyncio
async def test_update_me_rejects_duplicate_email(monkeypatch):
    async def get_user_by_email(_email):
        return {"id": "other-user"}

    monkeypatch.setattr(auth_service, "get_user_by_email", get_user_by_email)
    current_user = {
        "id": "user-1",
        "user_name": "alice",
        "email": "alice@example.com",
        "phone_number": "+15555550100",
        "password": auth_service.hash_password("Strong123"),
    }

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.update_me(
            auth_models.UpdateSettingsRequest(email="other@example.com"),
            current_user,
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_me_requires_current_password_for_password_change():
    current_user = {
        "id": "user-1",
        "user_name": "alice",
        "email": "alice@example.com",
        "phone_number": "+15555550100",
        "password": auth_service.hash_password("Strong123"),
    }

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.update_me(
            auth_models.UpdateSettingsRequest(new_password="Newpass123"),
            current_user,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_me_email_change_writes_and_returns_new_token(monkeypatch):
    mailer = _Mailer()
    updates = {}

    async def no_user(_value):
        return None

    async def update_user_fields(user_id, **kwargs):
        updates["user_id"] = user_id
        updates.update(kwargs)

    monkeypatch.setattr(auth_service, "get_user_by_email", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_username", no_user)
    monkeypatch.setattr(auth_service, "get_user_by_phone", no_user)
    monkeypatch.setattr(auth_service, "update_user_fields", update_user_fields)
    monkeypatch.setattr(auth_service, "mailer", mailer)
    current_user = {
        "id": "user-1",
        "user_name": "alice",
        "email": "alice@example.com",
        "phone_number": "+15555550100",
        "password": auth_service.hash_password("Strong123"),
    }

    result = await auth_service.update_me(
        auth_models.UpdateSettingsRequest(email="new@example.com"),
        current_user,
    )

    assert updates["user_id"] == "user-1"
    assert updates["email"] == "new@example.com"
    assert result.email == "new@example.com"
    assert result.access_token is not None
    assert {item[0] for item in mailer.account_changes} == {
        "alice@example.com",
        "new@example.com",
    }
