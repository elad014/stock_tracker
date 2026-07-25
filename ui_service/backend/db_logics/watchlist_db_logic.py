import os
import sys
from typing import Any, Optional
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "utils"))

from database_client import db

STOCKS_TABLE = "stocks"
WATCHLIST_TABLE = "users_watchlist"


def _normalize_stock(row: dict[str, Any]) -> dict[str, Any]:
    trend_value = row.get("trend")
    if trend_value is None and "trand" in row:
        trend_value = row.get("trand")
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "price": float(row["price"]) if row.get("price") is not None else None,
        "trend": trend_value,
    }


async def get_watchlist(user_id: str) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT s.id, s.name, s.price, s.trand AS trend
        FROM {WATCHLIST_TABLE} w
        JOIN {STOCKS_TABLE} s ON s.id = w.stock_id
        WHERE w.user_id = $1
        ORDER BY s.name
        """,
        user_id,
    )
    return [_normalize_stock(row) for row in rows]


async def get_stock_by_name(name: str) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"SELECT id, name, price, trand AS trend FROM {STOCKS_TABLE} WHERE name = $1",
        name,
    )
    return _normalize_stock(row) if row else None


async def create_stock(name: str) -> dict[str, Any]:
    stock_id = str(uuid4())
    await db.execute(
        f"INSERT INTO {STOCKS_TABLE} (id, name, price, trand) VALUES ($1, $2, $3, $4)",
        stock_id,
        name,
        None,
        None,
    )
    return {"id": stock_id, "name": name, "price": None, "trend": None}


async def is_on_watchlist(user_id: str, stock_id: str) -> bool:
    row = await db.fetch_one(
        f"SELECT user_id FROM {WATCHLIST_TABLE} WHERE user_id = $1 AND stock_id = $2",
        user_id,
        stock_id,
    )
    return row is not None


async def add_to_watchlist(user_id: str, stock_id: str) -> None:
    await db.execute(
        f"INSERT INTO {WATCHLIST_TABLE} (user_id, stock_id) VALUES ($1, $2)",
        user_id,
        stock_id,
    )


async def remove_from_watchlist(user_id: str, stock_id: str) -> str:
    return await db.execute(
        f"DELETE FROM {WATCHLIST_TABLE} WHERE user_id = $1 AND stock_id = $2",
        user_id,
        stock_id,
    )
