from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


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
