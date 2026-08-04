import re
from typing import Optional

from pydantic import BaseModel, field_validator


class WatchlistStock(BaseModel):
    id: str
    symbol: str
    price: Optional[float] = None
    change: Optional[float] = None
    stock_summery: Optional[str] = None


class AddWatchlistRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        ticker = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{1,5}(?:[.-][A-Z])?", ticker):
            raise ValueError("Invalid ticker (e.g. AAPL, BRK.A)")
        return ticker
