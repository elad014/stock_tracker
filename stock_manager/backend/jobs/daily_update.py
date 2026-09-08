import logging
from datetime import date, timedelta

from clients.database_client import db
from db_logics import history_db_logic as history_db
from db_logics import quotes_db_logic as quotes_db
from job_limits import daily_update_guard
from services.stock_service import (
    _fetch_history_gap_best_effort,
    _provider,
    _retention_cutoff,
    _run_provider,
)

logger = logging.getLogger(__name__)

# Re-fetch this many calendar days every run so mid-range holes near "today"
# (e.g. deleted yesterday while today already exists) still get filled.
_RECENT_LOOKBACK_DAYS = 14


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
            quote = await _run_provider(provider.get_quote, symbol)
            max_date = await history_db.get_max_date(stock_id)
            if max_date is None:
                start = cutoff
            else:
                # Fill trailing gaps from last bar, and always re-sync a recent
                # window so holes before max_date (deleted mid-range days) return.
                forward_start = max_date + timedelta(days=1)
                recent_start = today - timedelta(days=_RECENT_LOOKBACK_DAYS)
                start = max(min(forward_start, recent_start), cutoff)

            bars = await _fetch_history_gap_best_effort(symbol, start, today)
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


async def run_scheduled_daily_update() -> None:
    """Cron entry: never cooldown-limited; skipped only if a run is already in progress."""
    await daily_update_guard.run_from_schedule(run_daily_update)
