from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddWatchlistRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "e35c6172-bf33-407d-834e-fa80cc43da9c",
                    "symbol": "AAPL",
                }
            ]
        }
    )

    user_id: str = Field(..., description="Target user UUID from user_auth_data.id")
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL", min_length=1)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        return symbol


class RemoveWatchlistRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "e35c6172-bf33-407d-834e-fa80cc43da9c",
                    "stock_id": "5400d8f9-2946-475f-9279-5650ff385aa1",
                }
            ]
        }
    )

    user_id: str = Field(..., description="Target user UUID")
    stock_id: str = Field(..., description="Stock UUID from stock_quotes.stock_id")


class StockQuoteResponse(BaseModel):
    stock_id: str = Field(..., description="Internal stock UUID")
    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Company name from market data provider")
    close: Optional[float] = Field(None, description="Latest close / last price")
    change: Optional[float] = Field(None, description="Absolute price change")
    percent_change: Optional[float] = Field(None, description="Percent price change")


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class JobTriggerResponse(BaseModel):
    message: str
    job: str
