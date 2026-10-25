import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from clients.database_client import db
from clients.stock_provider_client import OHLCVBar
from db_logics import history_db_logic as history_db
from db_logics import quotes_db_logic as quotes_db
from job_limits import daily_update_guard
from jobs.alerts_check import run_alerts_check
from services.stock_service import (
    _provider,
    _retention_cutoff,
    _run_provider,
)

logger = logging.getLogger(__name__)

# Re-fetch this many calendar days every run so mid-range holes near "today"
# (e.g. deleted yesterday while today already exists) still get filled.
_RECENT_LOOKBACK_DAYS = 14

# Twelve Data's free tier allows 8 requests per minute. Each stock needs a
# quote call and a history call, so a burst rate-limits the symbols later in
# the list and their daily bars never get stored.
_REQUEST_SPACING_SECONDS = 8.0
_RATE_LIMIT_RETRIES = 5


def _is_rate_limited(exc: BaseException) -> bool:
    return "429" in str(exc)


async def _provider_call(func: Any, *args: Any) -> Any:
    wait_seconds: float = _REQUEST_SPACING_SECONDS
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            result: Any = await _run_provider(func, *args)
        except Exception as exc:
            if not _is_rate_limited(exc) or attempt == _RATE_LIMIT_RETRIES:
                raise
            logger.warning(
                "Twelve Data rate limit (attempt %s/%s); waiting %ss",
                attempt,
                _RATE_LIMIT_RETRIES,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60.0)
            continue
        await asyncio.sleep(_REQUEST_SPACING_SECONDS)
        return result
    raise RuntimeError("Twelve Data request failed")


async def run_daily_update(*, force: bool = False) -> None:
    """Refresh quotes and fill history gaps through today for all watched stocks."""
    provider = _provider()
    today = date.today()
    cutoff = _retention_cutoff(today)

    if not force and today.weekday() >= 5:
        logger.info("Skipping daily update: weekend")
        return

    if not force:
        try:
            market_open = await _run_provider(provider.is_market_open, "NASDAQ")
        except Exception as exc:
            logger.warning("Could not read market state (%s); continuing with update", exc)
            market_open = True

        if not market_open:
            logger.info("Skipping daily update: market closed")
            return

    watched = await quotes_db.list_watched_quotes()
    logger.info("Daily update for %s watched stocks (force=%s)", len(watched), force)

    for stock in watched:
        stock_id = stock["stock_id"]
        symbol = stock["symbol"]
        try:
            quote = await _provider_call(provider.get_quote, symbol)
            max_date = await history_db.get_max_date(stock_id)
            if max_date is None:
                start = cutoff
            else:
                # Fill trailing gaps from last bar, and always re-sync a recent
                # window so holes before max_date (deleted mid-range days) return.
                forward_start = max_date + timedelta(days=1)
                recent_start = today - timedelta(days=_RECENT_LOOKBACK_DAYS)
                start = max(min(forward_start, recent_start), cutoff)

            bars: list[OHLCVBar] = []
            if start <= today:
                try:
                    bars = await _provider_call(
                        provider.get_daily_time_series,
                        symbol,
                        start,
                        today,
                    )
                except Exception as exc:
                    if _is_rate_limited(exc):
                        raise
                    # Same-day ranges often 400 while the session is still open.
                    logger.warning(
                        "Gap history fetch skipped for %s (%s → %s): %s",
                        symbol,
                        start,
                        today,
                        exc,
                    )
            logger.info(
                "Daily update %s: gap %s → %s (%s bars, max_date=%s)",
                symbol,
                start,
                today,
                len(bars),
                max_date,
            )

            async with db.transaction() as conn:
                await quotes_db.upsert_quote(
                    stock_id=stock_id,
                    symbol=quote.symbol,
                    name=quote.name,
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
                if bars:
                    await history_db.upsert_bars(
                        stock_id,
                        quote.symbol,
                        bars,
                        conn=conn,
                    )
                await history_db.delete_older_than(stock_id, cutoff, conn=conn)
        except Exception as exc:
            logger.exception("Daily update failed for %s: %s", symbol, exc)
            continue

    # Event-driven alert evaluation: run immediately after all quotes are fresh.
    # Errors are isolated so a notification failure never breaks the daily update.
    try:
        await run_alerts_check()
    except Exception as exc:
        logger.exception("Alert check failed after daily update: %s", exc)


async def run_scheduled_daily_update() -> None:
    """Cron entry: never cooldown-limited; skipped only if a run is already in progress."""
    await daily_update_guard.run_from_schedule(run_daily_update)
