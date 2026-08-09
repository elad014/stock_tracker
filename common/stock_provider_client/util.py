import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

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


def extract_news_rows(data: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(data, list):
        return data
    for key in ("data", "news", "articles", "press_releases", "values"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def strip_html(value: Any) -> str | None:
    if value is None:
        return None
    text = _HTML_TAG_RE.sub(" ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_datetime(value: Any) -> datetime | None:
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


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
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
