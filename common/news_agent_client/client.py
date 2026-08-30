from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from constant import INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER, NEWS_AGENT_URL


class NewsAgentClient:
    """HTTP client for the internal news-agent service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or NEWS_AGENT_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    def _raise_from_response(self, response: httpx.Response) -> None:
        detail: Any
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except Exception:
            detail = response.text or "News agent request failed"
        retry_after: Optional[str] = response.headers.get("Retry-After")
        raise HTTPException(
            response.status_code,
            detail,
            headers={"Retry-After": retry_after} if retry_after else None,
        )

    def _json_response(self, response: httpx.Response, expected_type: type) -> Any:
        try:
            payload = response.json()
        except Exception as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "News agent returned invalid JSON",
            ) from exc
        if not isinstance(payload, expected_type):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "News agent returned an invalid response",
            )
        return payload

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        expected_type: type,
        **kwargs: Any,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._headers(),
                    **kwargs,
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach news agent",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        return self._json_response(response, expected_type)

    async def get_news(self, symbol: str, outputsize: int = 5) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/news/{symbol}",
            timeout=60.0,
            expected_type=dict,
            params={"outputsize": outputsize},
        )

    async def get_stored_news(
        self,
        symbol: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/news/{symbol}/stored",
            timeout=30.0,
            expected_type=dict,
            params={"limit": limit},
        )

    async def sync_stock_articles(
        self,
        stock_id: str,
        outputsize: int = 10,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/stocks/{stock_id}/articles/sync",
            timeout=120.0,
            expected_type=dict,
            params={"outputsize": outputsize},
        )

    async def summarize_article(self, article_id: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/articles/{article_id}/summarize",
            timeout=180.0,
            expected_type=dict,
        )

    async def list_stock_articles(
        self,
        stock_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            f"/stocks/{stock_id}/articles",
            timeout=30.0,
            expected_type=list,
            params={"limit": limit},
        )

    async def search_and_summarize(self, symbol: str, query: str) -> dict[str, Any]:
        ticker: str = symbol.strip().upper()
        question: str = query.strip()
        if not ticker:
            raise HTTPException(400, "symbol must not be empty")
        if not question:
            raise HTTPException(400, "query must not be empty")

        payload = await self._request_json(
            "POST",
            "/api/v1/news/search-and-summarize",
            timeout=180.0,
            expected_type=dict,
            json={"symbol": ticker, "query": question},
        )
        summary = str(payload.get("summary") or "").strip()
        articles = payload.get("articles")
        has_articles = isinstance(articles, list) and bool(articles)
        if not summary and not has_articles:
            raise HTTPException(502, "News agent returned an empty response")
        return payload


news_agent_client = NewsAgentClient()
