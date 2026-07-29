from datetime import date
from typing import Any, Optional, Sequence

import asyncpg

from database_client import db
from stock_provider_client import OHLCVBar

HISTORY_TABLE = "stock_history"


async def has_history(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    row = await db.fetch_one(
        f"""
        SELECT 1 AS present
        FROM {HISTORY_TABLE}
        WHERE stock_id = $1::uuid
        LIMIT 1
        """,
        stock_id,
        conn=conn,
    )
    return row is not None


async def get_max_date(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[date]:
    row = await db.fetch_one(
        f"""
        SELECT MAX(date) AS max_date
        FROM {HISTORY_TABLE}
        WHERE stock_id = $1::uuid
        """,
        stock_id,
        conn=conn,
    )
    if not row or row.get("max_date") is None:
        return None
    return row["max_date"]


async def upsert_bars(
    stock_id: str,
    symbol: str,
    bars: Sequence[OHLCVBar],
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    if not bars:
        return
    normalized_symbol = symbol.upper()
    args: list[tuple[Any, ...]] = [
        (
            stock_id,
            normalized_symbol,
            bar.date,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
        )
        for bar in bars
    ]
    await db.executemany(
        f"""
        INSERT INTO {HISTORY_TABLE} (
            stock_id, symbol, date, open, high, low, close, volume
        )
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (stock_id, date) DO UPDATE SET
            symbol = EXCLUDED.symbol,
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """,
        args,
        conn=conn,
    )


async def delete_older_than(
    stock_id: str,
    cutoff: date,
    conn: Optional[asyncpg.Connection] = None,
) -> str:
    return await db.execute(
        f"""
        DELETE FROM {HISTORY_TABLE}
        WHERE stock_id = $1::uuid AND date < $2
        """,
        stock_id,
        cutoff,
        conn=conn,
    )
