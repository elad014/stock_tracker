import logging

from database_client import db
from db_logics import archive_db_logic as archive_db
from db_logics import quotes_db_logic as quotes_db

logger = logging.getLogger(__name__)


async def run_cleanup_archive() -> None:
    """Archive history and remove quotes for stocks no longer on any watchlist."""
    unwatched = await quotes_db.list_unwatched_stock_ids()
    if not unwatched:
        logger.info("Cleanup: no unwatched stocks")
        return

    logger.info("Cleanup: archiving %s unwatched stocks", len(unwatched))
    for stock_id in unwatched:
        try:
            quote = await quotes_db.get_by_id(stock_id)
            if quote is None:
                continue
            async with db.transaction() as conn:
                await archive_db.archive_history_for_stock(
                    stock_id=stock_id,
                    symbol=quote["symbol"],
                    conn=conn,
                )
                await quotes_db.delete_quote(stock_id, conn=conn)
        except Exception as exc:
            logger.exception("Cleanup failed for stock_id=%s: %s", stock_id, exc)
            continue
