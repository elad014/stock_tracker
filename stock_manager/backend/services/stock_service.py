import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from database_client import db
from db_logics import archive_db_logic as archive_db
from db_logics import history_db_logic as history_db
from db_logics import quotes_db_logic as quotes_db
from db_logics import watchlist_db_logic as watchlist_db
from models.stocks import MessageResponse, StockQuoteResponse
from stock_provider_client import OHLCVBar, QuoteData, TwelveDataClient

logger = logging.getLogger(__name__)


# =============================================================================
# Shared helpers
# =============================================================================


def _retention_years() -> int:
    return int(os.getenv("HISTORY_RETENTION_YEARS", "5"))


def _provider() -> TwelveDataClient:
    return TwelveDataClient()


def _retention_cutoff(today: date | None = None) -> date:
    base = today or date.today()
    years = _retention_years()
    try:
        return date(base.year - years, base.month, base.day)
    except ValueError:
        return date(base.year - years, base.month, 28)


async def _run_provider(func: Any, *args: Any) -> Any:
    return await asyncio.to_thread(func, *args)


# =============================================================================
# Table: stock_quotes
# =============================================================================


def _quote_to_response(row: dict[str, Any]) -> StockQuoteResponse:
    return StockQuoteResponse(
        stock_id=row["stock_id"],
        symbol=row["symbol"],
        name=row["name"],
        close=row.get("close"),
        change=row.get("change"),
        percent_change=row.get("percent_change"),
        previous_close=row.get("previous_close"),
        high=row.get("high"),
        low=row.get("low"),
        volume=row.get("volume"),
        fifty_two_week_high=row.get("fifty_two_week_high"),
        fifty_two_week_low=row.get("fifty_two_week_low"),
    )


async def _upsert_quote_from_provider(
    stock_id: str,
    quote: QuoteData,
    *,
    name: str | None = None,
    conn: Any = None,
) -> dict[str, Any]:
    return await quotes_db.upsert_quote(
        stock_id=stock_id,
        symbol=quote.symbol,
        name=name or quote.name,
        close=quote.close,
        change=quote.change,
        percent_change=quote.percent_change,
        previous_close=quote.previous_close,
        high=quote.high,
        low=quote.low,
        volume=quote.volume,
        fifty_two_week_high=quote.fifty_two_week_high,
        fifty_two_week_low=quote.fifty_two_week_low,
        conn=conn,
    )


async def _refresh_existing_and_watch(
    user_id: str,
    existing: dict[str, Any],
    quote: QuoteData,
) -> StockQuoteResponse:
    stock_id = existing["stock_id"]
    has_hist = await history_db.has_history(stock_id)
    today = date.today()
    bars: list[OHLCVBar] = []

    if not has_hist:
        archived_max = await archive_db.get_max_date(stock_id)
        if archived_max is not None or await archive_db.has_archive(stock_id):
            start = (
                archived_max + timedelta(days=1)
                if archived_max is not None
                else _retention_cutoff(today)
            )
            bars = await _fetch_history_gap_best_effort(quote.symbol, start, today)
        else:
            try:
                bars = await _fetch_history(quote.symbol, _retention_cutoff(today), today)
            except Exception as exc:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    f"Failed to fetch history: {exc}",
                ) from exc

    async with db.transaction() as conn:
        if not has_hist and await archive_db.has_archive(stock_id):
            # Quote already exists; restore any leftover archive rows into history.
            await archive_db.restore_to_history(stock_id, conn=conn)
        row = await _upsert_quote_from_provider(stock_id, quote, conn=conn)
        if bars:
            await history_db.upsert_bars(stock_id, quote.symbol, bars, conn=conn)
            await history_db.delete_older_than(stock_id, _retention_cutoff(today), conn=conn)
        await watchlist_db.add_to_watchlist(user_id, stock_id, conn=conn)

    return _quote_to_response(row)


async def _create_new_and_watch(user_id: str, quote: QuoteData) -> StockQuoteResponse:
    stock_id = str(uuid4())
    today = date.today()
    try:
        bars = await _fetch_history(quote.symbol, _retention_cutoff(today), today)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Failed to fetch history: {exc}",
        ) from exc

    async with db.transaction() as conn:
        row = await _upsert_quote_from_provider(stock_id, quote, conn=conn)
        await history_db.upsert_bars(stock_id, quote.symbol, bars, conn=conn)
        await watchlist_db.add_to_watchlist(user_id, stock_id, conn=conn)

    return _quote_to_response(row)


# =============================================================================
# Table: stock_history
# =============================================================================


async def _fetch_history(symbol: str, start: date, end: date) -> list[OHLCVBar]:
    if start > end:
        return []
    provider = _provider()
    return await _run_provider(provider.get_daily_time_series, symbol, start, end)


async def _fetch_history_gap_best_effort(
    symbol: str,
    start: date,
    end: date,
) -> list[OHLCVBar]:
    """Fetch missing history days. On provider errors (e.g. same-day 400), return []."""
    if start > end:
        return []
    try:
        return await _fetch_history(symbol, start, end)
    except Exception as exc:
        # Twelve Data often 400s for same-day / incomplete trading-day ranges.
        # Archive restore should still succeed; daily job can fill later.
        logger.warning(
            "Gap history fetch skipped for %s (%s → %s): %s",
            symbol,
            start,
            end,
            exc,
        )
        return []


# =============================================================================
# Table: stock_history_archive
# =============================================================================


async def _restore_archived_and_watch(
    user_id: str,
    archived: dict[str, Any],
    quote: QuoteData,
) -> StockQuoteResponse:
    stock_id = archived["stock_id"]
    today = date.today()
    archived_max = await archive_db.get_max_date(stock_id)
    start = (
        archived_max + timedelta(days=1)
        if archived_max is not None
        else _retention_cutoff(today)
    )

    bars = await _fetch_history_gap_best_effort(quote.symbol, start, today)

    # Quote must exist before history insert (FK). Order: quote -> restore -> gap bars -> watchlist
    async with db.transaction() as conn:
        row = await _upsert_quote_from_provider(
            stock_id,
            quote,
            name=quote.name or archived["name"],
            conn=conn,
        )
        await archive_db.restore_to_history(stock_id, conn=conn)
        if bars:
            await history_db.upsert_bars(stock_id, quote.symbol, bars, conn=conn)
        await history_db.delete_older_than(stock_id, _retention_cutoff(today), conn=conn)
        await watchlist_db.add_to_watchlist(user_id, stock_id, conn=conn)

    return _quote_to_response(row)


# =============================================================================
# Table: watchlist
# =============================================================================


async def list_user_watchlist(user_id: str) -> list[StockQuoteResponse]:
    rows = await watchlist_db.list_user_watchlist(user_id)
    return [_quote_to_response(row) for row in rows]


async def list_all_stocks() -> list[StockQuoteResponse]:
    rows = await quotes_db.list_all_quotes()
    return [_quote_to_response(row) for row in rows]


async def get_stock(stock_id: str) -> StockQuoteResponse:
    existing = await quotes_db.get_by_id(stock_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return _quote_to_response(existing)


async def get_stock_by_symbol(symbol: str) -> StockQuoteResponse:
    existing = await quotes_db.get_by_symbol(symbol.strip().upper())
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return _quote_to_response(existing)


async def is_stock_on_watchlist(user_id: str, stock_id: str) -> bool:
    return await watchlist_db.is_on_watchlist(user_id, stock_id)


async def add_to_watchlist(user_id: str, symbol: str) -> StockQuoteResponse:
    symbol = symbol.strip().upper()
    provider = _provider()

    try:
        quote: QuoteData = await _run_provider(provider.get_quote, symbol)
    except RuntimeError as exc:
        message = str(exc).lower()
        if "not found" in message or "invalid" in message or "404" in message:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown symbol: {symbol}") from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Market data provider error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Market data provider error: {exc}",
        ) from exc

    existing = await quotes_db.get_by_symbol(symbol)
    if existing is not None:
        return await _refresh_existing_and_watch(user_id, existing, quote)

    archived = await archive_db.get_archived_stock_by_symbol(symbol)
    if archived is not None:
        return await _restore_archived_and_watch(user_id, archived, quote)

    return await _create_new_and_watch(user_id, quote)


async def remove_from_watchlist(user_id: str, stock_id: str) -> MessageResponse:
    result = await watchlist_db.remove_from_watchlist(user_id, stock_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not on watchlist")
    return MessageResponse(message="Stock removed from watchlist")


async def clear_user_watchlist(user_id: str) -> MessageResponse:
    await watchlist_db.delete_watchlist_for_user(user_id)
    return MessageResponse(message="User watchlist cleared")


async def unwatch_stock_everywhere(stock_id: str) -> MessageResponse:
    existing = await quotes_db.get_by_id(stock_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    await watchlist_db.delete_watchlist_for_stock(stock_id)
    return MessageResponse(message="Stock removed from all watchlists")
