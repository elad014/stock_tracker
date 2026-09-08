from typing import Any

from fastapi import HTTPException, status

from models.auth import MessageResponse
from models.watchlist import AddWatchlistRequest, WatchlistStock
from clients.stock_service_client import stock_service_client as stock_service


async def list_watchlist(user: dict[str, Any]) -> list[WatchlistStock]:
    rows = await stock_service.list_watchlist(user["id"])
    return [WatchlistStock(**stock_service.quote_to_watchlist_stock(row)) for row in rows]


async def add_watchlist_stock(
    req: AddWatchlistRequest,
    user: dict[str, Any],
) -> WatchlistStock:
    existing = await stock_service.get_stock_by_symbol(req.name)
    if existing and await stock_service.is_on_watchlist(user["id"], existing["stock_id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock already on your watchlist")

    payload = await stock_service.add_to_watchlist(user["id"], req.name)
    return WatchlistStock(**stock_service.quote_to_watchlist_stock(payload))


async def remove_watchlist_stock(user: dict[str, Any], stock_id: str) -> MessageResponse:
    await stock_service.remove_from_watchlist(user["id"], stock_id)
    return MessageResponse(message="Stock removed from watchlist")
