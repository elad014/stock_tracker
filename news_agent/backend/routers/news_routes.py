from fastapi import APIRouter, Depends, Path, Query

from deps import verify_internal_api_key
from models.news import StockNewsResponse
import services.news_service as news_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY or FINNHUB_API_KEY not configured"},
        502: {"description": "Upstream news provider request failed"},
    },
)


@router.get(
    "/news/{symbol}",
    tags=["News"],
    summary="Get news for a specific stock",
    description=(
        "Fetches recent company news for one stock from Finnhub "
        "(`/company-news`). Read-only: does not call llm-service or update the DB."
    ),
    response_model=StockNewsResponse,
    responses={
        400: {"description": "Empty or invalid symbol"},
        404: {"description": "Symbol not found"},
    },
)
async def get_news_for_stock(
    symbol: str = Path(..., description="Stock ticker symbol", examples=["AAPL"]),
    outputsize: int = Query(
        5,
        ge=1,
        le=50,
        description="Max number of articles to return",
    ),
) -> StockNewsResponse:
    return await news_service.get_stock_news(symbol, outputsize)
