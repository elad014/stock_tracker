from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from deps import verify_internal_api_key
from models.news import SearchAndSummarizeRequest, SearchAndSummarizeResponse, StockNewsResponse
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
    summary="Get news for a specific stock on one calendar day",
    description=(
        "Fetches Finnhub `/company-news` for one stock and one day "
        "(default: today). Read-only: does not call the LLM or update the DB."
    ),
    response_model=StockNewsResponse,
    responses={
        400: {"description": "Empty or invalid symbol"},
        404: {"description": "Symbol not found"},
    },
)
async def get_news_for_stock(
    symbol: str = Path(..., description="Stock ticker symbol", examples=["AAPL"]),
    day: Optional[date] = Query(
        None,
        description="Calendar day to fetch (YYYY-MM-DD). Defaults to today.",
    ),
    outputsize: int = Query(
        50,
        ge=1,
        le=200,
        description="Optional cap on how many articles to return",
    ),
) -> StockNewsResponse:
    return await news_service.get_stock_news(symbol, outputsize, day=day)


@router.post(
    "/api/v1/news/search-and-summarize",
    tags=["News"],
    summary="Answer a question from recent stored article text",
    description=(
        "Reads `news_articles.text` for the ticker from the last 7 days "
        "(JOIN stock_articles + stock_quotes) and asks LiteLLM to answer `query` "
        "from that corpus only."
    ),
    response_model=SearchAndSummarizeResponse,
)
async def search_and_summarize(
    req: SearchAndSummarizeRequest,
) -> SearchAndSummarizeResponse:
    return await news_service.search_and_summarize(req.symbol, req.query)
