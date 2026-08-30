import pytest

from conftest import load_backend_module


validators = load_backend_module("ui_service", "ui_utils.user_validators")


def test_validate_password_accepts_strong_password():
    assert validators.validate_password("Strong123") == "Strong123"


@pytest.mark.parametrize(
    "password",
    ["Short1", "lowercase1", "UPPERCASE1", "NoDigits"],
    ids=[
        "too short",
        "missing uppercase",
        "missing lowercase",
        "missing digit",
    ],
)
def test_validate_password_rejects_weak_passwords(password):
    with pytest.raises(ValueError):
        validators.validate_password(password)


def test_validate_username_requires_minimum_length():
    assert validators.validate_username("abc") == "abc"
    with pytest.raises(ValueError):
        validators.validate_username("ab")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), (" admin ", "admin"), (123, None)],
    ids=["none stays empty", "blank string becomes empty", "admin is normalized", "non string becomes empty"],
)
def test_normalize_admin_role_accepts_empty_or_admin(raw, expected):
    assert validators.normalize_admin_role(raw) == expected


def test_normalize_admin_role_rejects_other_strings():
    with pytest.raises(ValueError):
        validators.normalize_admin_role("owner")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), ("", None), (" lock ", "lock"), (False, None)],
    ids=["none stays empty", "blank string becomes empty", "lock is normalized", "non string becomes empty"],
)
def test_normalize_lock_status_accepts_empty_or_lock(raw, expected):
    assert validators.normalize_lock_status(raw) == expected


def test_normalize_lock_status_rejects_other_strings():
    with pytest.raises(ValueError):
        validators.normalize_lock_status("locked")
