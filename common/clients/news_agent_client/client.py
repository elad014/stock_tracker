from typing import Any, Optional

import httpx
from fastapi import HTTPException

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
            detail = payload.get("detail", payload)
        except Exception:
            detail = response.text or "News agent request failed"
        retry_after: Optional[str] = response.headers.get("Retry-After")
        raise HTTPException(
            response.status_code,
            detail,
            headers={"Retry-After": retry_after} if retry_after else None,
        )

    async def get_news(self, symbol: str, outputsize: int = 5) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self._base_url}/news/{symbol}",
                headers=self._headers(),
                params={"outputsize": outputsize},
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def get_stored_news(
        self,
        symbol: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/news/{symbol}/stored",
                headers=self._headers(),
                params={"limit": limit},
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def sync_stock_articles(
        self,
        stock_id: str,
        outputsize: int = 10,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/stocks/{stock_id}/articles/sync",
                headers=self._headers(),
                params={"outputsize": outputsize},
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def summarize_article(self, article_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self._base_url}/articles/{article_id}/summarize",
                headers=self._headers(),
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        return response.json()

    async def list_stock_articles(
        self,
        stock_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/stocks/{stock_id}/articles",
                headers=self._headers(),
                params={"limit": limit},
            )
        if response.status_code >= 400:
            self._raise_from_response(response)
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return payload

    async def search_and_summarize(self, symbol: str, query: str) -> dict[str, Any]:
        ticker: str = symbol.strip().upper()
        question: str = query.strip()
        if not ticker:
            raise HTTPException(400, "symbol must not be empty")
        if not question:
            raise HTTPException(400, "query must not be empty")

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self._base_url}/api/v1/news/search-and-summarize",
                headers=self._headers(),
                json={"symbol": ticker, "query": question},
            )
        if response.status_code != 200:
            self._raise_from_response(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(502, "News agent returned an invalid response")
        summary = str(payload.get("summary") or "").strip()
        articles = payload.get("articles")
        has_articles = isinstance(articles, list) and bool(articles)
        if not summary and not has_articles:
            raise HTTPException(502, "News agent returned an empty response")
        return payload


news_agent_client = NewsAgentClient()
