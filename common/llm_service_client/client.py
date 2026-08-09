import os
from typing import Any, Optional

import httpx
from fastapi import HTTPException

LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8002").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _headers() -> dict[str, str]:
    return {"X-Internal-Api-Key": INTERNAL_API_KEY}


def _raise_from_response(response: httpx.Response) -> None:
    detail: Any
    try:
        payload = response.json()
        detail = payload.get("detail", payload)
    except Exception:
        detail = response.text or "LLM service request failed"
    raise HTTPException(response.status_code, detail)


async def chat(
    user_id: str,
    message: str,
    *,
    reset_session: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "user_id": user_id,
        "message": message,
        "reset_session": reset_session,
    }
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{LLM_SERVICE_URL}/chat",
            headers=_headers(),
            json=body,
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def clear_chat_session(user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{LLM_SERVICE_URL}/chat/{user_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def summarize(
    text: str,
    *,
    symbol: Optional[str] = None,
    close: Optional[float] = None,
    change: Optional[float] = None,
    percent_change: Optional[float] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"text": text}
    if symbol is not None:
        body["symbol"] = symbol
    if close is not None:
        body["close"] = close
    if change is not None:
        body["change"] = change
    if percent_change is not None:
        body["percent_change"] = percent_change
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{LLM_SERVICE_URL}/summarize",
            headers=_headers(),
            json=body,
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()
