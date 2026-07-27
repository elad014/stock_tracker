from typing import Any

from fastapi import APIRouter, Depends, status

import services.watchlist_service as watchlist_service
from deps import get_current_user
from models.auth import MessageResponse
from models.watchlist import AddWatchlistRequest, WatchlistStock

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


@router.get("", response_model=list[WatchlistStock])
async def list_watchlist(user: dict[str, Any] = Depends(get_current_user)) -> list[WatchlistStock]:
    return await watchlist_service.list_watchlist(user)


@router.post("", response_model=WatchlistStock, status_code=status.HTTP_201_CREATED)
async def add_watchlist_stock(
    req: AddWatchlistRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> WatchlistStock:
    return await watchlist_service.add_watchlist_stock(req, user)


@router.delete("/{stock_id}", response_model=MessageResponse)
async def remove_watchlist_stock(
    stock_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> MessageResponse:
    return await watchlist_service.remove_watchlist_stock(user, stock_id)
