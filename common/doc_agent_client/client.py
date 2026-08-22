from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from constant import DOC_AGENT_URL, INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER


class DocAgentClient:
    """HTTP client for the internal doc-agent service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or DOC_AGENT_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    def _raise_from_response(self, response: httpx.Response) -> None:
        detail: Any
        try:
            payload = response.json()
            detail = payload.get("detail", payload)
        except Exception:
            detail = response.text or "Doc agent request failed"
        retry_after: Optional[str] = response.headers.get("Retry-After")
        raise HTTPException(
            response.status_code,
            detail,
            headers={"Retry-After": retry_after} if retry_after else None,
        )

    async def ingest_document(
        self,
        user_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """Download a stored PDF, embed its chunks, and replace vectors."""
        uid: str = user_id.strip()
        relative: str = document_id.strip()
        if not uid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")
        if not relative:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "document_id must not be empty",
            )
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/docs/upload",
                    headers=self._headers(),
                    json={"user_id": uid, "document_id": relative},
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach doc agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload

    async def purge_user(self, user_id: str) -> dict[str, Any]:
        """Delete all document vectors and ingest quota for one user."""
        uid: str = user_id.strip()
        if not uid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.delete(
                    f"{self._base_url}/api/v1/docs/users/{uid}",
                    headers=self._headers(),
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach doc agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload

    async def delete_document_vectors(
        self,
        user_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """Delete stored vectors for one document after the PDF is removed."""
        uid: str = user_id.strip()
        relative: str = document_id.strip()
        if not uid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")
        if not relative:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "document_id must not be empty",
            )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self._base_url}/api/v1/docs/vectors",
                    headers=self._headers(),
                    params={"user_id": uid, "document_id": relative},
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach doc agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload


doc_agent_client = DocAgentClient()
