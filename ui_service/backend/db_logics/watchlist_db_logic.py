from typing import Any, Optional

from database_client import db

QUOTES_TABLE = "stock_quotes"
WATCHLIST_TABLE = "watchlist"


def _normalize_stock(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["stock_id"]),
        "name": row.get("symbol") or row.get("name"),
        "price": float(row["close"]) if row.get("close") is not None else None,
        "trend": (
            float(row["percent_change"])
            if row.get("percent_change") is not None
            else None
        ),
    }


async def get_watchlist(user_id: str) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT q.stock_id, q.symbol, q.name, q.close, q.percent_change
        FROM {WATCHLIST_TABLE} w
        JOIN {QUOTES_TABLE} q ON q.stock_id = w.stock_id
        WHERE w.user_id = $1::uuid
        ORDER BY q.symbol
        """,
        user_id,
    )
    return [_normalize_stock(row) for row in rows]


async def list_stocks() -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT stock_id, symbol, name, close, percent_change
        FROM {QUOTES_TABLE}
        ORDER BY symbol
        """
    )
    return [_normalize_stock(row) for row in rows]


async def get_stock_by_id(stock_id: str) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT stock_id, symbol, name, close, percent_change
        FROM {QUOTES_TABLE}
        WHERE stock_id = $1::uuid
        """,
        stock_id,
    )
    return _normalize_stock(row) if row else None


async def get_stock_by_name(name: str) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT stock_id, symbol, name, close, percent_change
        FROM {QUOTES_TABLE}
        WHERE symbol = $1
        """,
        name.strip().upper(),
    )
    return _normalize_stock(row) if row else None


async def is_on_watchlist(user_id: str, stock_id: str) -> bool:
    row = await db.fetch_one(
        f"""
        SELECT 1 AS present
        FROM {WATCHLIST_TABLE}
        WHERE user_id = $1::uuid AND stock_id = $2::uuid
        """,
        user_id,
        stock_id,
    )
    return row is not None
