from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "e35c6172-bf33-407d-834e-fa80cc43da9c",
                    "message": "What is a stock option?",
                    "temperature": 0.2,
                }
            ]
        }
    )

    user_id: str = Field(..., description="User UUID for isolated chat history", min_length=1)
    message: str = Field(..., description="New user message", min_length=1)
    reset_session: bool = Field(
        False,
        description="Clear stored conversation history for this user before processing",
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)


class ChatUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatResponse(BaseModel):
    content: str
    model: str
    user_id: str
    usage: Optional[ChatUsage] = None


class SummarizeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "Apple reported record iPhone sales this quarter...",
                    "symbol": "AAPL",
                    "close": 198.5,
                    "change": 2.1,
                    "percent_change": 1.07,
                }
            ]
        }
    )

    text: str = Field(..., description="News article or text to summarize", min_length=1)
    symbol: Optional[str] = Field(
        None,
        description="Optional ticker symbol for context in the summary prompt",
    )
    close: Optional[float] = Field(
        None,
        description="Latest close price for quote-aware outlook",
    )
    change: Optional[float] = Field(
        None,
        description="Absolute price change for quote-aware outlook",
    )
    percent_change: Optional[float] = Field(
        None,
        description="Percent price change for quote-aware outlook",
    )
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)


class SummarizeResponse(BaseModel):
    content: str
    model: str
    symbol: Optional[str] = None
    usage: Optional[ChatUsage] = None


class SessionClearResponse(BaseModel):
    user_id: str
    message: str


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
