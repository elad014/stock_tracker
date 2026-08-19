from typing import Any, Optional

from models.stocks import StockArticle, StockDetails, StockHistoryBar
from news_agent_client import news_agent_client as news_agent
from stock_manager_client import stock_manager_client as stock_manager


def _quote_to_stock_details(
    payload: dict[str, Any],
    *,
    stock_summery: Optional[str] = None,
) -> StockDetails:
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
        stock_summery=stock_summery,
    )


async def get_stock_details(stock_id: str, user_id: str) -> StockDetails:
    payload = await stock_manager.get_stock(stock_id)
    on_watchlist = await stock_manager.is_on_watchlist(user_id, stock_id)
    summary = payload.get("stock_summery") if on_watchlist else None
    return _quote_to_stock_details(payload, stock_summery=summary)


async def get_stock_history(
    stock_id: str,
    range_key: str = "1Y",
) -> list[StockHistoryBar]:
    rows = await stock_manager.get_stock_history(stock_id, range_key)
    return [StockHistoryBar(**row) for row in rows]


def _to_article(payload: dict[str, Any]) -> StockArticle:
    return StockArticle(
        article_id=str(payload.get("article_id")),
        url=str(payload.get("url") or ""),
        title=str(payload.get("title") or ""),
        source=payload.get("source"),
        published_at=payload.get("published_at"),
        provider_summary=payload.get("provider_summary"),
        ai_summary=payload.get("ai_summary"),
        ai_summary_status=str(payload.get("ai_summary_status") or "none"),
        ai_summary_error=payload.get("ai_summary_error"),
    )


async def list_stock_articles(stock_id: str, limit: int = 100) -> list[StockArticle]:
    """Read-only: articles are filled by news-agent cron / Swagger, never by the user."""
    rows = await news_agent.list_stock_articles(stock_id, limit)
    return [_to_article(row) for row in rows]


async def summarize_stock_article(stock_id: str, article_id: str) -> StockArticle:
    _ = stock_id
    result = await news_agent.summarize_article(article_id)
    return StockArticle(
        article_id=str(result.get("article_id")),
        url=str(result.get("url") or ""),
        title=str(result.get("title") or ""),
        source=None,
        published_at=None,
        provider_summary=None,
        ai_summary=result.get("ai_summary"),
        ai_summary_status=str(result.get("status") or "none"),
        ai_summary_error=result.get("ai_summary_error"),
    )
