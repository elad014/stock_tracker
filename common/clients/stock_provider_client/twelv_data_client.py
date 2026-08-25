import os
from datetime import date
from typing import Any

import requests
from dotenv import load_dotenv

from constant import TWELVE_DATA_BASE_URL
from .util import (
    OHLCVBar,
    QuoteData,
    parse_date,
    to_float,
    to_int,
)

load_dotenv()


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
        url = f"{TWELVE_DATA_BASE_URL}/{endpoint.lstrip('/')}"
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
            fifty_two_week_high = to_float(fifty_two.get("high"))
            fifty_two_week_low = to_float(fifty_two.get("low"))

        return QuoteData(
            symbol=str(data.get("symbol") or normalized).upper(),
            name=str(data.get("name") or normalized).strip(),
            close=to_float(data.get("close")),
            change=to_float(data.get("change")),
            percent_change=to_float(data.get("percent_change")),
            previous_close=to_float(data.get("previous_close")),
            high=to_float(data.get("high")),
            low=to_float(data.get("low")),
            volume=to_int(data.get("volume")),
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
            bar_date = parse_date(row.get("datetime"))
            if bar_date is None:
                continue
            bars.append(
                OHLCVBar(
                    date=bar_date,
                    open=to_float(row.get("open")),
                    high=to_float(row.get("high")),
                    low=to_float(row.get("low")),
                    close=to_float(row.get("close")),
                    volume=to_int(row.get("volume")),
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
