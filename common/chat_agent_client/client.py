from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from constant import CHAT_AGENT_URL, INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER


class ChatAgentClient:
    """HTTP client for the internal chat-agent orchestrator."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or CHAT_AGENT_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    def _raise_from_response(self, response: httpx.Response) -> None:
        detail: Any
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except Exception:
            detail = response.text or "Chat agent request failed"
        raise HTTPException(response.status_code, detail)

    def _json_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Chat agent returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Chat agent returned an invalid response",
            )
        return payload

    async def chat(
        self,
        user_id: str,
        message: str,
        *,
        document_id: Optional[str] = None,
        reset_session: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "user_id": user_id,
            "message": message,
            "reset_session": reset_session,
        }
        if document_id is not None:
            body["document_id"] = document_id
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/chat",
                    headers=self._headers(),
                    json=body,
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach chat agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        return self._json_response(response)

    async def clear_chat_session(self, user_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self._base_url}/api/v1/chat/{user_id}",
                    headers=self._headers(),
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach chat agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        return self._json_response(response)


chat_agent_client = ChatAgentClient()
