from typing import Any

from fastapi import APIRouter, Depends, Path, Query

import services.stocks_service as stocks_service
from deps import get_current_user
from models.stocks import StockArticle, StockDetails, StockHistoryBar

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/{stock_id}", response_model=StockDetails)
async def get_stock_details(
    stock_id: str = Path(..., description="Stock UUID"),
    user: dict[str, Any] = Depends(get_current_user),
) -> StockDetails:
    return await stocks_service.get_stock_details(stock_id, str(user["id"]))


@router.get("/{stock_id}/history", response_model=list[StockHistoryBar])
async def get_stock_history(
    stock_id: str = Path(..., description="Stock UUID"),
    range: str = Query("1Y", description="History window: 1D, 5D, 1M, 3M, 6M, 1Y, or 5Y"),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[StockHistoryBar]:
    return await stocks_service.get_stock_history(stock_id, str(user["id"]), range)


@router.get("/{stock_id}/articles", response_model=list[StockArticle])
async def list_stock_articles(
    stock_id: str = Path(..., description="Stock UUID"),
    limit: int = Query(100, ge=1, le=200, description="Max number of articles"),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[StockArticle]:
    return await stocks_service.list_stock_articles(stock_id, str(user["id"]), limit)


@router.post(
    "/{stock_id}/articles/{article_id}/summarize",
    response_model=StockArticle,
)
async def summarize_stock_article(
    stock_id: str = Path(..., description="Stock UUID"),
    article_id: str = Path(..., description="Article UUID"),
    user: dict[str, Any] = Depends(get_current_user),
) -> StockArticle:
    return await stocks_service.summarize_stock_article(
        stock_id,
        article_id,
        str(user["id"]),
    )
