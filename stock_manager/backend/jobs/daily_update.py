import logging
from datetime import date, timedelta

from database_client import db
from db_logics import history_db_logic as history_db
from db_logics import quotes_db_logic as quotes_db
from services.stock_service import _fetch_history, _provider, _retention_cutoff, _run_provider

logger = logging.getLogger(__name__)


async def run_daily_update(*, force: bool = False) -> None:
    """Refresh quotes and append today's bar for all watched stocks."""
    provider = _provider()
    today = date.today()

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
            bars = await _fetch_history(symbol, today - timedelta(days=5), today)
            today_bars = [bar for bar in bars if bar.date == today]
            if not today_bars and bars:
                # Holiday / closed day — still refresh quote, skip history insert
                today_bars = []

            async with db.transaction() as conn:
                await quotes_db.upsert_quote(
                    stock_id=stock_id,
                    symbol=quote.symbol,
                    name=quote.name,
                    close=quote.close,
                    change=quote.change,
                    percent_change=quote.percent_change,
                    conn=conn,
                )
                if today_bars:
                    await history_db.upsert_bars(
                        stock_id,
                        quote.symbol,
                        today_bars,
                        conn=conn,
                    )
                await history_db.delete_older_than(
                    stock_id,
                    _retention_cutoff(today),
                    conn=conn,
                )
        except Exception as exc:
            logger.exception("Daily update failed for %s: %s", symbol, exc)
            continue
