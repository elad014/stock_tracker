from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArticleSummaryResponse(BaseModel):
    article_id: str
    title: str
    url: str
    status: str = Field(
        ...,
        description="ready when the summary is available, pending while another request generates it",
        examples=["ready"],
    )
    ai_summary: Optional[str] = None
    ai_summary_model: Optional[str] = None
    ai_summary_error: Optional[str] = None
    ai_summary_updated_at: Optional[datetime] = None
    extracted: bool = Field(
        False,
        description="True when full article text was extracted, false when the provider blurb was used",
    )


class ArticleRecord(BaseModel):
    article_id: str
    url: str
    title: str
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    provider: Optional[str] = None
    provider_summary: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_summary_status: str = Field(..., examples=["ready"])
    ai_summary_model: Optional[str] = None
    ai_summary_error: Optional[str] = None
    ai_summary_updated_at: Optional[datetime] = None


class ArticleSyncResponse(BaseModel):
    stock_id: str
    symbol: str
    stored: int = Field(..., ge=0, description="Number of articles stored or refreshed")


class MessageResponse(BaseModel):
    message: str
