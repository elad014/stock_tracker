import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

internal_api_key_header = APIKeyHeader(
    name="X-Internal-Api-Key",
    auto_error=False,
    description="Shared internal API key required for news-agent job triggers.",
)


async def verify_internal_api_key(
    x_internal_api_key: str | None = Security(internal_api_key_header),
) -> None:
    expected = os.getenv("INTERNAL_API_KEY", "")
    if not expected:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_API_KEY is not configured",
        )
    if not x_internal_api_key or x_internal_api_key != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal API key")
