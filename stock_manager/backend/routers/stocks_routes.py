from fastapi import APIRouter, Depends, Path, Query, status

from deps import verify_internal_api_key
from jobs.cleanup_archive import run_cleanup_archive
from jobs.daily_update import run_daily_update
import services.stock_service as stock_service
from models.stocks import (
    AddWatchlistRequest,
    JobTriggerResponse,
    MessageResponse,
    RemoveWatchlistRequest,
    StockHistoryBar,
    StockQuoteResponse,
    StockSummeryResponse,
    UpdateStockSummeryRequest,
)

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY not configured on server"},
    },
)


@router.get(
    "/watchlist/{user_id}",
    tags=["Watchlist"],
    summary="List stocks on a user watchlist",
    response_model=list[StockQuoteResponse],
)
async def list_watchlist(
    user_id: str = Path(..., description="User UUID whose watchlist to return"),
) -> list[StockQuoteResponse]:
    return await stock_service.list_user_watchlist(user_id)


@router.get(
    "/stocks",
    tags=["Admin"],
    summary="List all stock quotes",
    response_model=list[StockQuoteResponse],
)
async def list_stocks() -> list[StockQuoteResponse]:
    return await stock_service.list_all_stocks()


@router.get(
    "/stocks/symbol/{symbol}",
    tags=["Admin"],
    summary="Get stock quote by symbol",
    response_model=StockQuoteResponse,
    responses={404: {"description": "Stock not found"}},
)
async def get_stock_by_symbol(
    symbol: str = Path(..., description="Ticker symbol, e.g. AAPL"),
) -> StockQuoteResponse:
    return await stock_service.get_stock_by_symbol(symbol)


@router.get(
    "/stocks/{stock_id}",
    tags=["Admin"],
    summary="Get stock quote by id",
    response_model=StockQuoteResponse,
    responses={404: {"description": "Stock not found"}},
)
async def get_stock(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
) -> StockQuoteResponse:
    return await stock_service.get_stock(stock_id)


@router.get(
    "/stocks/{stock_id}/history",
    tags=["Stocks"],
    summary="Get daily OHLCV history for a stock",
    response_model=list[StockHistoryBar],
    responses={
        400: {"description": "Invalid range"},
        404: {"description": "Stock not found"},
    },
)
async def get_stock_history(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
    range: str = Query(
        "1Y",
        description="History window: 1D, 5D, 1M, 3M, 6M, 1Y, or 5Y",
    ),
) -> list[StockHistoryBar]:
    return await stock_service.get_stock_history(stock_id, range)


@router.get(
    "/stocks/{stock_id}/summary",
    tags=["News"],
    summary="Get stock news summary",
    response_model=StockSummeryResponse,
    responses={404: {"description": "Stock not found"}},
)
async def get_stock_summery(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
) -> StockSummeryResponse:
    return await stock_service.get_stock_summery(stock_id)


@router.put(
    "/stocks/{stock_id}/summary",
    tags=["News"],
    summary="Update stock news summary",
    description=(
        "Used by news-agent to persist AI news summaries on "
        "stock_quotes.stock_summery and stock_news_published_at."
    ),
    response_model=StockSummeryResponse,
    responses={404: {"description": "Stock not found"}},
)
async def update_stock_summery(
    req: UpdateStockSummeryRequest,
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
) -> StockSummeryResponse:
    return await stock_service.update_stock_summery(
        stock_id,
        req.stock_summery,
        stock_news_published_at=req.stock_news_published_at,
    )


@router.get(
    "/watchlist/{user_id}/{stock_id}",
    tags=["Watchlist"],
    summary="Check whether a stock is on a user watchlist",
    response_model=dict[str, bool],
)
async def check_watchlist_membership(
    user_id: str = Path(..., description="User UUID"),
    stock_id: str = Path(..., description="Stock UUID"),
) -> dict[str, bool]:
    on_list = await stock_service.is_stock_on_watchlist(user_id, stock_id)
    return {"on_watchlist": on_list}


@router.post(
    "/watchlist",
    tags=["Watchlist"],
    summary="Add stock to user watchlist",
    description=(
        "Validates the symbol with Twelve Data, creates or refreshes quote/history "
        "(including archive restore when possible), then adds the stock to the user's watchlist."
    ),
    response_model=StockQuoteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Unknown symbol"},
        502: {"description": "Market data provider failure"},
    },
)
async def add_watchlist(req: AddWatchlistRequest) -> StockQuoteResponse:
    return await stock_service.add_to_watchlist(req.user_id, req.symbol)


@router.delete(
    "/watchlist",
    tags=["Watchlist"],
    summary="Remove stock from user watchlist",
    description=(
        "Removes only the watchlist row. Quote/history cleanup is handled by the "
        "scheduled archive job when no users watch the stock."
    ),
    response_model=MessageResponse,
    responses={404: {"description": "Stock not on watchlist"}},
)
async def remove_watchlist(req: RemoveWatchlistRequest) -> MessageResponse:
    return await stock_service.remove_from_watchlist(req.user_id, req.stock_id)


@router.post(
    "/admin/ensure-and-assign",
    tags=["Admin"],
    summary="Ensure stock data and assign to user",
    description="Admin helper that runs the same full add-to-watchlist flow for a user/symbol.",
    response_model=StockQuoteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Unknown symbol"},
        502: {"description": "Market data provider failure"},
    },
)
async def ensure_and_assign(req: AddWatchlistRequest) -> StockQuoteResponse:
    return await stock_service.add_to_watchlist(req.user_id, req.symbol)


@router.delete(
    "/watchlist/user/{user_id}",
    tags=["Watchlist"],
    summary="Clear all watchlist entries for a user",
    response_model=MessageResponse,
)
async def clear_user_watchlist(
    user_id: str = Path(..., description="User UUID whose watchlist should be cleared"),
) -> MessageResponse:
    return await stock_service.clear_user_watchlist(user_id)


@router.delete(
    "/stocks/{stock_id}",
    tags=["Admin"],
    summary="Remove stock from all watchlists",
    description=(
        "Deletes every watchlist row for this stock. The cleanup job will later "
        "archive history and remove the quote when no watchers remain."
    ),
    response_model=MessageResponse,
    responses={404: {"description": "Stock not found"}},
)
async def unwatch_stock_everywhere(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
) -> MessageResponse:
    return await stock_service.unwatch_stock_everywhere(stock_id)


@router.post(
    "/jobs/daily-update",
    tags=["Jobs"],
    summary="Trigger daily quote/history update",
    description=(
        "Manually runs the same job as the daily cron: refresh quotes and "
        "fill any missing history from the last stored day through today. "
        "By default it still skips weekends / closed market; "
        "set force=true to run anyway (useful for testing)."
    ),
    response_model=JobTriggerResponse,
)
async def trigger_daily_update(
    force: bool = Query(
        False,
        description="If true, ignore weekend and market-closed checks",
    ),
) -> JobTriggerResponse:
    await run_daily_update(force=force)
    return JobTriggerResponse(
        job="daily-update",
        message="Daily update job completed" + (" (forced)" if force else ""),
    )


@router.post(
    "/jobs/cleanup-archive",
    tags=["Jobs"],
    summary="Trigger cleanup and archive",
    description=(
        "Manually runs the cleanup job: for stocks with no watchlist entries, "
        "moves history to stock_history_archive and deletes the quote."
    ),
    response_model=JobTriggerResponse,
)
async def trigger_cleanup_archive() -> JobTriggerResponse:
    await run_cleanup_archive()
    return JobTriggerResponse(
        job="cleanup-archive",
        message="Cleanup/archive job completed",
    )
