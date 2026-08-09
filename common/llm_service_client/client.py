from typing import Any, Optional

import httpx
from fastapi import HTTPException

from constant import INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER, LLM_SERVICE_URL


class LLMServiceClient:
    """HTTP client for the internal llm-service gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or LLM_SERVICE_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    def _raise_from_response(self, response: httpx.Response) -> None:
        detail: Any
        try:
            payload = response.json()
            detail = payload.get("detail", payload)
        except Exception:
            detail = response.text or "LLM service request failed"
        raise HTTPException(response.status_code, detail)

    async def chat(
        self,
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
                f"{self._base_url}/chat",
                headers=self._headers(),
                json=body,
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def clear_chat_session(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self._base_url}/chat/{user_id}",
                headers=self._headers(),
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def summarize(
        self,
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
                f"{self._base_url}/summarize",
                headers=self._headers(),
                json=body,
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()


llm_service_client = LLMServiceClient()
