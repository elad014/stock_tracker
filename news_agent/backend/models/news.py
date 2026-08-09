from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    title: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    summary: Optional[str] = None


class StockNewsResponse(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    count: int = Field(..., ge=0)
    articles: list[NewsArticle]
