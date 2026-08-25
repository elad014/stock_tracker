from typing import Any, Optional

import asyncpg

from clients.database_client import db
from db_logics.quotes_db_logic import _QUOTE_COLUMNS_Q, _normalize_quote

WATCHLIST_TABLE = "watchlist"
QUOTES_TABLE = "stock_quotes"


async def list_user_watchlist(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT {_QUOTE_COLUMNS_Q}
        FROM {WATCHLIST_TABLE} w
        JOIN {QUOTES_TABLE} q ON q.stock_id = w.stock_id
        WHERE w.user_id = $1::uuid
        ORDER BY q.symbol
        """,
        user_id,
        conn=conn,
    )
    return [_normalize_quote(row) for row in rows]


async def is_on_watchlist(
    user_id: str,
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    row = await db.fetch_one(
        f"""
        SELECT 1 AS present
        FROM {WATCHLIST_TABLE}
        WHERE user_id = $1::uuid AND stock_id = $2::uuid
        """,
        user_id,
        stock_id,
        conn=conn,
    )
    return row is not None


async def add_to_watchlist(
    user_id: str,
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    await db.execute(
        f"""
        INSERT INTO {WATCHLIST_TABLE} (user_id, stock_id)
        VALUES ($1::uuid, $2::uuid)
        ON CONFLICT (user_id, stock_id) DO NOTHING
        """,
        user_id,
        stock_id,
        conn=conn,
    )


async def remove_from_watchlist(
    user_id: str,
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> str:
    return await db.execute(
        f"""
        DELETE FROM {WATCHLIST_TABLE}
        WHERE user_id = $1::uuid AND stock_id = $2::uuid
        """,
        user_id,
        stock_id,
        conn=conn,
    )


async def delete_watchlist_for_user(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    await db.execute(
        f"DELETE FROM {WATCHLIST_TABLE} WHERE user_id = $1::uuid",
        user_id,
        conn=conn,
    )


async def delete_watchlist_for_stock(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    await db.execute(
        f"DELETE FROM {WATCHLIST_TABLE} WHERE stock_id = $1::uuid",
        stock_id,
        conn=conn,
    )
