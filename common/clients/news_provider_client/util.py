from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class NewsItem:
    title: str
    url: str | None
    published_at: datetime | None
    source: str | None
    summary: str | None


def to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_unix_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
