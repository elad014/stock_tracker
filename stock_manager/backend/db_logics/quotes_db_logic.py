from datetime import datetime
from typing import Any, Optional

import asyncpg

from database_client import db

QUOTES_TABLE = "stock_quotes"


def _normalize_quote(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_id": str(row["stock_id"]),
        "symbol": row["symbol"],
        "name": row["name"],
        "close": float(row["close"]) if row.get("close") is not None else None,
        "change": float(row["change"]) if row.get("change") is not None else None,
        "percent_change": (
            float(row["percent_change"]) if row.get("percent_change") is not None else None
        ),
    }


async def get_by_symbol(
    symbol: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT stock_id, symbol, name, close, change, percent_change
        FROM {QUOTES_TABLE}
        WHERE symbol = $1
        """,
        symbol.upper(),
        conn=conn,
    )
    return _normalize_quote(row) if row else None


async def get_by_id(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT stock_id, symbol, name, close, change, percent_change
        FROM {QUOTES_TABLE}
        WHERE stock_id = $1::uuid
        """,
        stock_id,
        conn=conn,
    )
    return _normalize_quote(row) if row else None


async def upsert_quote(
    stock_id: str,
    symbol: str,
    name: str,
    close: float | None,
    change: float | None,
    percent_change: float | None,
    conn: Optional[asyncpg.Connection] = None,
) -> dict[str, Any]:
    row = await db.fetch_one(
        f"""
        INSERT INTO {QUOTES_TABLE} (
            stock_id, symbol, name, close, change, percent_change, updated_at
        )
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (stock_id) DO UPDATE SET
            symbol = EXCLUDED.symbol,
            name = EXCLUDED.name,
            close = EXCLUDED.close,
            change = EXCLUDED.change,
            percent_change = EXCLUDED.percent_change,
            updated_at = EXCLUDED.updated_at
        RETURNING stock_id, symbol, name, close, change, percent_change
        """,
        stock_id,
        symbol.upper(),
        name,
        close,
        change,
        percent_change,
        datetime.utcnow(),
        conn=conn,
    )
    assert row is not None
    return _normalize_quote(row)


async def list_all_quotes(
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT stock_id, symbol, name, close, change, percent_change
        FROM {QUOTES_TABLE}
        ORDER BY symbol
        """,
        conn=conn,
    )
    return [_normalize_quote(row) for row in rows]


async def list_watched_quotes(
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT DISTINCT q.stock_id, q.symbol, q.name, q.close, q.change, q.percent_change
        FROM {QUOTES_TABLE} q
        INNER JOIN watchlist w ON w.stock_id = q.stock_id
        ORDER BY q.symbol
        """,
        conn=conn,
    )
    return [_normalize_quote(row) for row in rows]


async def list_unwatched_stock_ids(
    conn: Optional[asyncpg.Connection] = None,
) -> list[str]:
    rows = await db.fetch_all(
        f"""
        SELECT q.stock_id
        FROM {QUOTES_TABLE} q
        LEFT JOIN watchlist w ON w.stock_id = q.stock_id
        WHERE w.stock_id IS NULL
        """,
        conn=conn,
    )
    return [str(row["stock_id"]) for row in rows]


async def delete_quote(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> str:
    return await db.execute(
        f"DELETE FROM {QUOTES_TABLE} WHERE stock_id = $1::uuid",
        stock_id,
        conn=conn,
    )
