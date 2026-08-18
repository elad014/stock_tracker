from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StockDetails(BaseModel):
    id: str
    symbol: str
    name: str
    close: Optional[float] = None
    change: Optional[float] = None
    percent_change: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    stock_summery: Optional[str] = None


class StockHistoryBar(BaseModel):
    date: str = Field(..., description="Trading date (YYYY-MM-DD)")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class StockArticle(BaseModel):
    article_id: str
    url: str
    title: str
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    provider_summary: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_summary_status: str = Field(..., description="none | pending | ready | failed")
    ai_summary_error: Optional[str] = None
