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


def _normalize_bar(row: dict[str, Any]) -> dict[str, Any]:
    bar_date = row["date"]
    if hasattr(bar_date, "isoformat"):
        bar_date = bar_date.isoformat()
    return {
        "date": str(bar_date),
        "open": float(row["open"]) if row.get("open") is not None else None,
        "high": float(row["high"]) if row.get("high") is not None else None,
        "low": float(row["low"]) if row.get("low") is not None else None,
        "close": float(row["close"]) if row.get("close") is not None else None,
        "volume": int(row["volume"]) if row.get("volume") is not None else None,
    }


async def get_latest_bar(
    stock_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT date, open, high, low, close, volume
        FROM {HISTORY_TABLE}
        WHERE stock_id = $1::uuid
        ORDER BY date DESC
        LIMIT 1
        """,
        stock_id,
        conn=conn,
    )
    return _normalize_bar(row) if row else None


async def list_by_stock(
    stock_id: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = ["stock_id = $1::uuid"]
    args: list[Any] = [stock_id]
    if start is not None:
        args.append(start)
        clauses.append(f"date >= ${len(args)}")
    if end is not None:
        args.append(end)
        clauses.append(f"date <= ${len(args)}")
    where = " AND ".join(clauses)
    rows = await db.fetch_all(
        f"""
        SELECT date, open, high, low, close, volume
        FROM {HISTORY_TABLE}
        WHERE {where}
        ORDER BY date ASC
        """,
        *args,
        conn=conn,
    )
    return [_normalize_bar(row) for row in rows]
