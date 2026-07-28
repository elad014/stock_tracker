from typing import Any, Optional

import asyncpg

from database_client import db

WATCHLIST_TABLE = "watchlist"


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
