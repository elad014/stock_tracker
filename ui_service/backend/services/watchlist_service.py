from typing import Any

from fastapi import HTTPException, status

from db_logics import watchlist_db_logic as watchlist_db
from models.auth import MessageResponse
from models.watchlist import AddWatchlistRequest, WatchlistStock


async def list_watchlist(user: dict[str, Any]) -> list[WatchlistStock]:
    rows = await watchlist_db.get_watchlist(user["id"])
    return [WatchlistStock(**row) for row in rows]


async def add_watchlist_stock(
    req: AddWatchlistRequest,
    user: dict[str, Any],
) -> WatchlistStock:
    stock = await watchlist_db.get_stock_by_name(req.name)
    if stock is None:
        stock = await watchlist_db.create_stock(req.name)

    if await watchlist_db.is_on_watchlist(user["id"], stock["id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock already on your watchlist")

    await watchlist_db.add_to_watchlist(user["id"], stock["id"])
    return WatchlistStock(**stock)


async def remove_watchlist_stock(user: dict[str, Any], stock_id: str) -> MessageResponse:
    result = await watchlist_db.remove_from_watchlist(user["id"], stock_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found on your watchlist")
    return MessageResponse(message="Stock removed from watchlist")
