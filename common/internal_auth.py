"""FastAPI dependency: require X-Internal-Api-Key on internal agent routes."""

import hmac
import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from constant import INTERNAL_API_KEY_HEADER

internal_api_key_header = APIKeyHeader(
    name=INTERNAL_API_KEY_HEADER,
    auto_error=False,
    description="Shared internal API key required for all internal service endpoints.",
)


def expected_internal_api_key() -> str:
    expected: str = os.getenv("INTERNAL_API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_API_KEY is not configured",
        )
    return expected


def internal_api_key_matches(provided: str | None, expected: str) -> bool:
    if provided is None:
        return False
    provided_bytes: bytes = provided.encode("utf-8")
    expected_bytes: bytes = expected.encode("utf-8")
    if len(provided_bytes) != len(expected_bytes):
        return False
    return hmac.compare_digest(provided_bytes, expected_bytes)


async def verify_internal_api_key(
    x_internal_api_key: str | None = Security(internal_api_key_header),
) -> None:
    expected: str = expected_internal_api_key()
    if not internal_api_key_matches(x_internal_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal API key")
