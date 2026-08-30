import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from database_client import db
from db_logics import archive_db_logic as archive_db
from db_logics import history_db_logic as history_db
from db_logics import quotes_db_logic as quotes_db
from db_logics import watchlist_db_logic as watchlist_db
from models.stocks import (
    MessageResponse,
    StockHistoryBar,
    StockQuoteResponse,
    StockSummeryResponse,
)
from stock_provider_client import OHLCVBar, QuoteData, TwelveDataClient

_HISTORY_RANGE_DAYS: dict[str, int | None] = {
    "1D": 1,
    "5D": 5,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "5Y": None,
}

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


def _quote_to_response(
    row: dict[str, Any],
    *,
    open_price: float | None = None,
) -> StockQuoteResponse:
    return StockQuoteResponse(
        stock_id=row["stock_id"],
        symbol=row["symbol"],
        name=row["name"] or row["symbol"],
        close=row.get("close"),
        change=row.get("change"),
        percent_change=row.get("percent_change"),
        previous_close=row.get("previous_close"),
        open=open_price if open_price is not None else row.get("open"),
        high=row.get("high"),
        low=row.get("low"),
        volume=row.get("volume"),
        fifty_two_week_high=row.get("fifty_two_week_high"),
        fifty_two_week_low=row.get("fifty_two_week_low"),
        stock_summery=row.get("stock_summery"),
        stock_news_published_at=row.get("stock_news_published_at"),
    )


def _history_start_for_range(range_key: str, today: date | None = None) -> date | None:
    base = today or date.today()
    normalized = range_key.strip().upper()
    if normalized not in _HISTORY_RANGE_DAYS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid range. Use one of: 1D, 5D, 1M, 3M, 6M, 1Y, 5Y",
        )
    days = _HISTORY_RANGE_DAYS[normalized]
    if days is None:
        return _retention_cutoff(base)
    return base - timedelta(days=days)


def _with_today_close(
    bars: list[StockHistoryBar],
    quote: dict[str, Any],
    start: date | None,
) -> list[StockHistoryBar]:
    """Ensure the latest quote close appears as today's point on the chart."""
    close = quote.get("close")
    if close is None:
        return bars

    today = date.today()
    if start is not None and today < start:
        return bars

    today_str = today.isoformat()
    today_bar = StockHistoryBar(
        date=today_str,
        open=quote.get("open"),
        high=quote.get("high"),
        low=quote.get("low"),
        close=float(close),
        volume=quote.get("volume"),
    )

    if not bars:
        return [today_bar]

    last = bars[-1]
    if last.date == today_str:
        bars[-1] = StockHistoryBar(
            date=today_str,
            open=last.open if last.open is not None else today_bar.open,
            high=today_bar.high if today_bar.high is not None else last.high,
            low=today_bar.low if today_bar.low is not None else last.low,
            close=float(close),
            volume=(
                today_bar.volume if today_bar.volume is not None else last.volume
            ),
        )
        return bars

    if last.date < today_str:
        return [*bars, today_bar]

    return bars


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
        open=quote.open,
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
    latest = await history_db.get_latest_bar(stock_id)
    open_price = latest.get("open") if latest else None
    return _quote_to_response(existing, open_price=open_price)


async def get_stock_by_symbol(symbol: str) -> StockQuoteResponse:
    existing = await quotes_db.get_by_symbol(symbol.strip().upper())
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    latest = await history_db.get_latest_bar(existing["stock_id"])
    open_price = latest.get("open") if latest else None
    return _quote_to_response(existing, open_price=open_price)


async def get_stock_summery(stock_id: str) -> StockSummeryResponse:
    existing = await quotes_db.get_by_id(stock_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return StockSummeryResponse(
        stock_id=existing["stock_id"],
        symbol=existing["symbol"],
        stock_summery=existing.get("stock_summery"),
        stock_news_published_at=existing.get("stock_news_published_at"),
    )


async def update_stock_summery(
    stock_id: str,
    stock_summery: str | None,
    stock_news_published_at: datetime | None = None,
) -> StockSummeryResponse:
    normalized = stock_summery.strip() if stock_summery is not None else None
    if normalized == "":
        normalized = None
    updated = await quotes_db.update_stock_summery(
        stock_id,
        normalized,
        stock_news_published_at=stock_news_published_at,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return StockSummeryResponse(
        stock_id=updated["stock_id"],
        symbol=updated["symbol"],
        stock_summery=updated.get("stock_summery"),
        stock_news_published_at=updated.get("stock_news_published_at"),
    )


async def get_stock_history(
    stock_id: str,
    range_key: str = "1Y",
) -> list[StockHistoryBar]:
    existing = await quotes_db.get_by_id(stock_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    start = _history_start_for_range(range_key)
    rows = await history_db.list_by_stock(stock_id, start=start)
    latest = await history_db.get_latest_bar(stock_id)
    quote_with_open = {
        **existing,
        "open": latest.get("open") if latest else existing.get("open"),
    }
    bars = [StockHistoryBar(**row) for row in rows]
    return _with_today_close(bars, quote_with_open, start)


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
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Stock {symbol} not found",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Market data provider error",
        ) from exc
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "invalid symbol" in message or "404" in message:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Stock {symbol} not found",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Market data provider error",
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

