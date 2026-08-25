from typing import Optional

from pydantic import BaseModel, field_validator

from constant import TICKER_PATTERN


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
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("Invalid ticker (e.g. AAPL, BRK.A)")
        return ticker
