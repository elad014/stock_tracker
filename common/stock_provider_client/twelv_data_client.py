import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.twelvedata.com"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class QuoteData:
    symbol: str
    name: str
    close: float | None
    change: float | None
    percent_change: float | None
    previous_close: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    exchange: str | None = None


@dataclass
class OHLCVBar:
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


@dataclass
class NewsItem:
    title: str
    url: str | None
    published_at: datetime | None
    source: str | None
    summary: str | None


class TwelveDataClient:
    """Twelve Data REST client used by stock_manager."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key: str = api_key or os.getenv("TWELVEDATA_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "API key missing. Set TWELVEDATA_API_KEY in .env or pass api_key=..."
            )

    def request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        query_params: dict[str, Any] = dict(params or {})
        query_params["apikey"] = self.api_key

        if method.upper() == "GET":
            response = requests.get(url, params=query_params, timeout=60)
        elif method.upper() == "POST":
            response = requests.post(url, json=query_params, timeout=60)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            symbol = str(query_params.get("symbol") or "")
            if status_code == 404:
                raise RuntimeError(f"Symbol not found: {symbol}") from None
            raise RuntimeError(f"Twelve Data HTTP {status_code}") from None

        data: dict[str, Any] = response.json()

        if data.get("status") == "error":
            code = data.get("code")
            message = str(data.get("message") or "Unknown error")
            message_lower = message.lower()
            if code == 404 or "not found" in message_lower or "invalid symbol" in message_lower:
                symbol = str(query_params.get("symbol") or "")
                raise RuntimeError(f"Symbol not found: {symbol}") from None
            raise RuntimeError(f"Twelve Data API error {code}: {message}") from None

        return data

    def get_quote(self, symbol: str) -> QuoteData:
        normalized = symbol.strip().upper()
        try:
            data = self.request("quote", {"symbol": normalized})
        except RuntimeError:
            # Twelve Data uses class shares with a dot (BRK.A), not a hyphen (BRK-A).
            if "-" in normalized:
                data = self.request("quote", {"symbol": normalized.replace("-", ".")})
            else:
                raise

        fifty_two = data.get("fifty_two_week")
        fifty_two_week_high: float | None = None
        fifty_two_week_low: float | None = None
        if isinstance(fifty_two, dict):
            fifty_two_week_high = _to_float(fifty_two.get("high"))
            fifty_two_week_low = _to_float(fifty_two.get("low"))

        return QuoteData(
            symbol=str(data.get("symbol") or normalized).upper(),
            name=str(data.get("name") or normalized).strip(),
            close=_to_float(data.get("close")),
            change=_to_float(data.get("change")),
            percent_change=_to_float(data.get("percent_change")),
            previous_close=_to_float(data.get("previous_close")),
            high=_to_float(data.get("high")),
            low=_to_float(data.get("low")),
            volume=_to_int(data.get("volume")),
            fifty_two_week_high=fifty_two_week_high,
            fifty_two_week_low=fifty_two_week_low,
            exchange=str(data["exchange"]) if data.get("exchange") else None,
        )

    def get_daily_time_series(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> list[OHLCVBar]:
        data = self.request(
            "time_series",
            {
                "symbol": symbol.upper(),
                "interval": "1day",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "order": "ASC",
            },
        )
        values = data.get("values") or []
        bars: list[OHLCVBar] = []
        for row in values:
            bar_date = _parse_date(row.get("datetime"))
            if bar_date is None:
                continue
            bars.append(
                OHLCVBar(
                    date=bar_date,
                    open=_to_float(row.get("open")),
                    high=_to_float(row.get("high")),
                    low=_to_float(row.get("low")),
                    close=_to_float(row.get("close")),
                    volume=_to_int(row.get("volume")),
                )
            )
        return bars

    def is_market_open(self, exchange: str = "NASDAQ") -> bool:
        data = self.request("market_state", {"exchange": exchange})
        if isinstance(data, list):
            for item in data:
                if str(item.get("exchange", "")).upper() == exchange.upper():
                    return bool(item.get("is_market_open"))
            return bool(data[0].get("is_market_open")) if data else False
        return bool(data.get("is_market_open"))

    def get_news(self, symbol: str, outputsize: int = 5) -> list[NewsItem]:
        """Fetch recent news/articles for a symbol.

        Prefers GET /news; falls back to /press_releases when /news is unavailable.
        """
        normalized = symbol.strip().upper()
        size = max(1, int(outputsize))
        params: dict[str, Any] = {"symbol": normalized, "outputsize": size}

        data: dict[str, Any] | list[Any]
        try:
            data = self.request("news", params)
        except RuntimeError as exc:
            message = str(exc).lower()
            if "404" not in message and "not found" not in message:
                raise
            data = self.request("press_releases", params)

        raw_items = _extract_news_rows(data)
        items: list[NewsItem] = []
        for row in raw_items[:size]:
            if not isinstance(row, dict):
                continue
            title = str(
                row.get("title")
                or row.get("headline")
                or row.get("name")
                or ""
            ).strip()
            if not title:
                continue
            summary_raw = (
                row.get("summary")
                or row.get("description")
                or row.get("content")
                or row.get("body")
                or row.get("snippet")
            )
            summary = _strip_html(summary_raw)
            items.append(
                NewsItem(
                    title=title,
                    url=_to_optional_str(row.get("url") or row.get("link")),
                    published_at=_parse_datetime(
                        row.get("published_at")
                        or row.get("published")
                        or row.get("datetime")
                        or row.get("date")
                    ),
                    source=_to_optional_str(
                        row.get("source") or row.get("publisher") or row.get("author")
                    ),
                    summary=summary,
                )
            )
        return items


def _extract_news_rows(data: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(data, list):
        return data
    for key in ("data", "news", "articles", "press_releases", "values"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _strip_html(value: Any) -> str | None:
    if value is None:
        return None
    text = _HTML_TAG_RE.sub(" ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if " " in text else text[:10], fmt)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None
