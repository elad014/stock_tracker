from datetime import date
from typing import Any, Optional

import asyncpg

from clients.database_client import db

ARCHIVE_TABLE = "stock_history_archive"
HISTORY_TABLE = "stock_history"


async def get_archived_stock_by_symbol(
    symbol: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT stock_id, symbol
        FROM {ARCHIVE_TABLE}
        WHERE symbol = $1
        ORDER BY date DESC
        LIMIT 1
        """,
        symbol.upper(),
        conn=conn,
    )
    if not row:
        return None
    return {
        "stock_id": str(row["stock_id"]),
        "symbol": row["symbol"],
        "name": row["symbol"],
    }


async def has_archive(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    row = await db.fetch_one(
        f"""
        SELECT 1 AS present
        FROM {ARCHIVE_TABLE}
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
        FROM {ARCHIVE_TABLE}
        WHERE stock_id = $1::uuid
        """,
        stock_id,
        conn=conn,
    )
    if not row or row.get("max_date") is None:
        return None
    return row["max_date"]


async def restore_to_history(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    await db.execute(
        f"""
        INSERT INTO {HISTORY_TABLE} (
            stock_id, symbol, date, open, high, low, close, volume
        )
        SELECT stock_id, symbol, date, open, high, low, close, volume
        FROM {ARCHIVE_TABLE}
        WHERE stock_id = $1::uuid
        ON CONFLICT (stock_id, date) DO NOTHING
        """,
        stock_id,
        conn=conn,
    )
    await db.execute(
        f"DELETE FROM {ARCHIVE_TABLE} WHERE stock_id = $1::uuid",
        stock_id,
        conn=conn,
    )


async def archive_history_for_stock(
    stock_id: str,
    symbol: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    await db.execute(
        f"""
        INSERT INTO {ARCHIVE_TABLE} (
            stock_id, symbol, date, open, high, low, close, volume
        )
        SELECT stock_id, $2, date, open, high, low, close, volume
        FROM {HISTORY_TABLE}
        WHERE stock_id = $1::uuid
        ON CONFLICT (stock_id, date) DO UPDATE SET
            symbol = EXCLUDED.symbol
        """,
        stock_id,
        symbol.upper(),
        conn=conn,
    )
    await db.execute(
        f"DELETE FROM {HISTORY_TABLE} WHERE stock_id = $1::uuid",
        stock_id,
        conn=conn,
    )
