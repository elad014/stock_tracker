import pytest
from fastapi import HTTPException

from internal_auth import (
    expected_internal_api_key,
    internal_api_key_matches,
    verify_internal_api_key,
)


def test_internal_api_key_matches_requires_same_value_and_length():
    assert internal_api_key_matches("secret", "secret") is True
    assert internal_api_key_matches("SECRET", "secret") is False
    assert internal_api_key_matches("secret-extra", "secret") is False
    assert internal_api_key_matches(None, "secret") is False


def test_expected_internal_api_key_requires_configured_value(monkeypatch):
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        expected_internal_api_key()

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_verify_internal_api_key_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        await verify_internal_api_key("wrong")

    assert exc_info.value.status_code == 401
