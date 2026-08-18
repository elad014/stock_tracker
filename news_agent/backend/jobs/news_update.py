import asyncio
import logging
from datetime import datetime
from typing import Any

from llm_service_client import LLMServiceClient
from news_provider_client import NewsItem, NewsProviderClient
from stock_manager_client import StockManagerClient

logger = logging.getLogger(__name__)


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMServiceClient:
    return LLMServiceClient()


def _stock_manager_client() -> StockManagerClient:
    return StockManagerClient()


async def _run_provider(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


def _build_news_text(items: list[NewsItem]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(items, start=1):
        lines = [f"{index}. {item.title}"]
        if item.source:
            lines.append(f"Source: {item.source}")
        if item.published_at is not None:
            lines.append(f"Published: {item.published_at.isoformat()}")
        if item.url:
            lines.append(f"URL: {item.url}")
        if item.summary:
            lines.append(item.summary)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _newest_published_at(items: list[NewsItem]) -> datetime | None:
    published = [item.published_at for item in items if item.published_at is not None]
    if not published:
        return None
    return max(published)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def run_news_update() -> None:
    """Fetch news per stock via Finnhub, summarize via llm-service, persist via stock-manager."""
    stock_manager = _stock_manager_client()
    stocks = await stock_manager.list_stocks()
    logger.info("News update for %s stocks", len(stocks))
    news_provider = _news_provider()
    llm_client = _llm_client()

    for stock in stocks:
        stock_id = str(stock.get("stock_id") or "")
        symbol = str(stock.get("symbol") or "").strip().upper()
        if not stock_id or not symbol:
            logger.warning("Skipping stock with missing id/symbol: %s", stock)
            continue

        try:
            news_items: list[NewsItem] = await _run_provider(
                news_provider.get_news,
                symbol,
                5,
            )
            if not news_items:
                logger.info("No news for %s; skipping summary update", symbol)
                continue

            news_text = _build_news_text(news_items)
            summary_result = await llm_client.summarize(
                news_text,
                symbol=symbol,
                close=_to_float(stock.get("close")),
                change=_to_float(stock.get("change")),
                percent_change=_to_float(stock.get("percent_change")),
            )
            content = str(summary_result.get("content") or "").strip()
            if not content:
                logger.warning("Empty LLM summary for %s; skipping update", symbol)
                continue

            newest = _newest_published_at(news_items)
            published_iso = newest.isoformat() if newest is not None else None
            await stock_manager.update_stock_summery(
                stock_id,
                content,
                stock_news_published_at=published_iso,
            )
            logger.info(
                "Updated summary for %s (articles=%s, published_at=%s)",
                symbol,
                len(news_items),
                published_iso,
            )
        except Exception:
            logger.exception("News update failed for %s", symbol)
            continue
