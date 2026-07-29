from typing import Any

from models.stocks import StockDetails, StockHistoryBar
import stock_manager_client as stock_manager


def _quote_to_stock_details(payload: dict[str, Any]) -> StockDetails:
    return StockDetails(
        id=str(payload.get("stock_id") or payload.get("id")),
        symbol=str(payload.get("symbol") or ""),
        name=str(payload.get("name") or payload.get("symbol") or ""),
        close=payload.get("close"),
        change=payload.get("change"),
        percent_change=payload.get("percent_change"),
        previous_close=payload.get("previous_close"),
        open=payload.get("open"),
        high=payload.get("high"),
        low=payload.get("low"),
        volume=payload.get("volume"),
        fifty_two_week_high=payload.get("fifty_two_week_high"),
        fifty_two_week_low=payload.get("fifty_two_week_low"),
    )


async def get_stock_details(stock_id: str) -> StockDetails:
    payload = await stock_manager.get_stock(stock_id)
    return _quote_to_stock_details(payload)


async def get_stock_history(
    stock_id: str,
    range_key: str = "1Y",
) -> list[StockHistoryBar]:
    rows = await stock_manager.get_stock_history(stock_id, range_key)
    return [StockHistoryBar(**row) for row in rows]
