"""Finnhub-backed news provider client.

Environment variables:
- ``FINNHUB_API_KEY`` — Finnhub API token
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from constant import FINNHUB_BASE_URL
from news_provider_client.util import NewsItem, parse_unix_datetime, to_optional_str

load_dotenv()


class NewsProviderClient:
    """Finnhub company-news client used by news_agent."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key: str = api_key or os.getenv("FINNHUB_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "API key missing. Set FINNHUB_API_KEY in .env or pass api_key=..."
            )

    def request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{FINNHUB_BASE_URL}/{endpoint.lstrip('/')}"
        query_params: dict[str, Any] = dict(params or {})
        query_params["token"] = self.api_key

        response = requests.get(url, params=query_params, timeout=60)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            symbol = str(query_params.get("symbol") or "")
            if status_code == 404:
                raise RuntimeError(f"Symbol not found: {symbol}") from None
            if status_code == 401:
                raise RuntimeError("Finnhub authentication failed") from None
            if status_code == 429:
                raise RuntimeError("Finnhub rate limit exceeded") from None
            raise RuntimeError(f"Finnhub HTTP {status_code}") from None

        return response.json()

    def _parse_items(
        self,
        data: Any,
        *,
        symbol: str,
        limit: Optional[int] = None,
    ) -> list[NewsItem]:
        if not isinstance(data, list):
            message = ""
            if isinstance(data, dict):
                message = str(data.get("error") or data.get("message") or "")
            if "not found" in message.lower():
                raise RuntimeError(f"Symbol not found: {symbol}") from None
            raise RuntimeError(
                f"Finnhub returned unexpected company-news payload for {symbol}"
            )

        items: list[NewsItem] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            title = str(row.get("headline") or row.get("title") or "").strip()
            if not title:
                continue
            items.append(
                NewsItem(
                    title=title,
                    url=to_optional_str(row.get("url")),
                    published_at=parse_unix_datetime(row.get("datetime")),
                    source=to_optional_str(row.get("source")),
                    summary=to_optional_str(row.get("summary")),
                )
            )
            if limit is not None and len(items) >= limit:
                break
        return items

    def get_news(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
        limit: Optional[int] = None,
    ) -> list[NewsItem]:
        """Fetch company news for ``symbol`` between ``start`` and ``end`` (inclusive).

        Pass ``limit=None`` to keep every article Finnhub returns for that window.
        """
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        if end < start:
            raise ValueError("end date must be on or after start date")

        data = self.request(
            "company-news",
            {
                "symbol": normalized,
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
        )
        return self._parse_items(data, symbol=normalized, limit=limit)

    def get_news_for_day(
        self,
        symbol: str,
        day: Optional[date] = None,
    ) -> list[NewsItem]:
        """Fetch every Finnhub article published on one calendar day."""
        target = day or date.today()
        return self.get_news(symbol, start=target, end=target, limit=None)
