from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from constant import NEWS_SEARCH_MAX_QUERY_CHARS


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


class StoredNewsArticle(BaseModel):
    title: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    source: Optional[str] = None
    text: Optional[str] = None
    ai_summary: Optional[str] = None
    provider_summary: Optional[str] = None


class StoredStockNewsResponse(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    count: int = Field(..., ge=0)
    articles: list[StoredNewsArticle]


class SearchAndSummarizeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["AAPL"])
    query: str = Field(
        ...,
        min_length=1,
        max_length=NEWS_SEARCH_MAX_QUERY_CHARS,
        examples=["Why did the stock drop today?"],
    )


class SearchEvidenceArticle(BaseModel):
    article_id: str
    symbol: str
    title: str
    published_at: Optional[str] = None
    url: Optional[str] = None
    matching_sentences: list[str] = Field(default_factory=list)
    text: Optional[str] = None


class SearchAndSummarizeResponse(BaseModel):
    summary: str
    articles: list[SearchEvidenceArticle] = Field(default_factory=list)
