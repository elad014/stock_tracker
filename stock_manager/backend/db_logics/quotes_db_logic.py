from datetime import datetime
from typing import Any, Optional

import asyncpg

from database_client import db

QUOTES_TABLE = "stock_quotes"

_QUOTE_COLUMNS = (
    "stock_id, symbol, name, close, change, percent_change, "
    "previous_close, high, low, volume, fifty_two_week_high, fifty_two_week_low"
)
_QUOTE_COLUMNS_Q = (
    "q.stock_id, q.symbol, q.name, q.close, q.change, q.percent_change, "
    "q.previous_close, q.high, q.low, q.volume, q.fifty_two_week_high, q.fifty_two_week_low"
)


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
        "previous_close": (
            float(row["previous_close"]) if row.get("previous_close") is not None else None
        ),
        "high": float(row["high"]) if row.get("high") is not None else None,
        "low": float(row["low"]) if row.get("low") is not None else None,
        "volume": int(row["volume"]) if row.get("volume") is not None else None,
        "fifty_two_week_high": (
            float(row["fifty_two_week_high"])
            if row.get("fifty_two_week_high") is not None
            else None
        ),
        "fifty_two_week_low": (
            float(row["fifty_two_week_low"])
            if row.get("fifty_two_week_low") is not None
            else None
        ),
    }


async def get_by_symbol(
    symbol: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT {_QUOTE_COLUMNS}
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
        SELECT {_QUOTE_COLUMNS}
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
    previous_close: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: int | None = None,
    fifty_two_week_high: float | None = None,
    fifty_two_week_low: float | None = None,
    conn: Optional[asyncpg.Connection] = None,
) -> dict[str, Any]:
    row = await db.fetch_one(
        f"""
        INSERT INTO {QUOTES_TABLE} (
            stock_id, symbol, name, close, change, percent_change,
            previous_close, high, low, volume,
            fifty_two_week_high, fifty_two_week_low, updated_at
        )
        VALUES (
            $1::uuid, $2, $3, $4, $5, $6,
            $7, $8, $9, $10,
            $11, $12, $13
        )
        ON CONFLICT (stock_id) DO UPDATE SET
            symbol = EXCLUDED.symbol,
            name = EXCLUDED.name,
            close = EXCLUDED.close,
            change = EXCLUDED.change,
            percent_change = EXCLUDED.percent_change,
            previous_close = EXCLUDED.previous_close,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            volume = EXCLUDED.volume,
            fifty_two_week_high = EXCLUDED.fifty_two_week_high,
            fifty_two_week_low = EXCLUDED.fifty_two_week_low,
            updated_at = EXCLUDED.updated_at
        RETURNING {_QUOTE_COLUMNS}
        """,
        stock_id,
        symbol.upper(),
        name,
        close,
        change,
        percent_change,
        previous_close,
        high,
        low,
        volume,
        fifty_two_week_high,
        fifty_two_week_low,
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
        SELECT {_QUOTE_COLUMNS}
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
        SELECT DISTINCT {_QUOTE_COLUMNS_Q}
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
