from typing import Any

from fastapi import APIRouter, Depends, Path, Query

import services.stocks_service as stocks_service
from deps import get_current_user
from models.stocks import StockDetails, StockHistoryBar

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/{stock_id}", response_model=StockDetails)
async def get_stock_details(
    stock_id: str = Path(..., description="Stock UUID"),
    user: dict[str, Any] = Depends(get_current_user),
) -> StockDetails:
    _ = user
    return await stocks_service.get_stock_details(stock_id)


@router.get("/{stock_id}/history", response_model=list[StockHistoryBar])
async def get_stock_history(
    stock_id: str = Path(..., description="Stock UUID"),
    range: str = Query("1Y", description="History window: 1D, 5D, 1M, 3M, 6M, 1Y, or 5Y"),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[StockHistoryBar]:
    _ = user
    return await stocks_service.get_stock_history(stock_id, range)
