import asyncio
import logging
import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from constant import ARTICLE_EXTRACT_RETRY_LIMIT, ARTICLE_RETENTION_DAYS
from llm_limits import news_update_guard
from clients.llm_provider_client import LLMProviderClient
from clients.news_provider_client import NewsItem, NewsProviderClient
from services.article_service import (
    purge_old_articles,
    retry_missing_article_bodies,
    to_article_payload,
    upsert_stock_articles,
)
from clients.stock_manager_client import StockManagerClient

logger = logging.getLogger(__name__)


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMProviderClient:
    return LLMProviderClient()


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
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stamp_summary(content: str) -> str:
    """Prefix the rollup with the local time this summary was written."""
    tz_name: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Jerusalem")
    created_at: datetime = datetime.now(ZoneInfo(tz_name))
    stamp: str = created_at.strftime("%Y-%m-%d %H:%M")
    return f"Created: {stamp}\n\n{content}"


async def run_news_update() -> None:
    """Fetch today's Finnhub articles per stock, store them, update rollup summary.

    Each run:
    1. List stocks from stock-manager (`stock_quotes`)
    2. Ask Finnhub for every article published today
    3. Upsert + link those articles in `news_articles` / `stock_articles`
    4. LLM + HTTP `stock_summery` only when this stock got new articles
    5. Delete articles older than ARTICLE_RETENTION_DAYS (summaries go with them)
    """
    stock_manager = _stock_manager_client()
    stocks = await stock_manager.list_stocks()
    today = date.today()
    logger.info(
        "News update for %s stocks (today=%s, retention=%s days)",
        len(stocks),
        today.isoformat(),
        ARTICLE_RETENTION_DAYS,
    )
    news_provider = _news_provider()
    llm_client = _llm_client()

    try:
        retried: int = await retry_missing_article_bodies(
            ARTICLE_RETENTION_DAYS,
            ARTICLE_EXTRACT_RETRY_LIMIT,
        )
        if retried:
            logger.info("Filled extracted article text for %s stored rows", retried)
    except Exception:
        logger.exception("Failed to retry article text extraction")

    for stock in stocks:
        stock_id = str(stock.get("stock_id") or "")
        symbol = str(stock.get("symbol") or "").strip().upper()
        if not stock_id or not symbol:
            logger.warning("Skipping stock with missing id/symbol: %s", stock)
            continue

        try:
            news_items: list[NewsItem] = await _run_provider(
                news_provider.get_news_for_day,
                symbol,
                today,
            )
            if not news_items:
                logger.info("No news for %s on %s; skipping summary update", symbol, today)
                continue

            payload = to_article_payload(news_items)
            new_count: int = 0
            if payload:
                _stored, new_count = await upsert_stock_articles(stock_id, payload)

            existing_summary = str(stock.get("stock_summery") or "").strip()
            if new_count == 0 and existing_summary:
                logger.info(
                    "No new articles for %s on %s; skipping LLM",
                    symbol,
                    today,
                )
                continue
            if new_count == 0 and not existing_summary:
                logger.info(
                    "No new articles for %s but stock_summery empty; summarizing",
                    symbol,
                )

            news_text = _build_news_text(news_items)
            summary_result = await llm_client.summarize(
                news_text,
                symbol=symbol,
                close=_to_float(stock.get("close")),
                change=_to_float(stock.get("change")),
                percent_change=_to_float(stock.get("percent_change")),
            )
            raw_summary: str = summary_result.content.strip()
            if not raw_summary:
                logger.warning("Empty LLM summary for %s; skipping update", symbol)
                continue

            content: str = _stamp_summary(raw_summary)

            newest = _newest_published_at(news_items)
            published_iso = newest.isoformat() if newest is not None else None
            await stock_manager.update_stock_summery(
                stock_id,
                content,
                stock_news_published_at=published_iso,
            )
            logger.info(
                "Updated summary for %s (today_articles=%s, new=%s, published_at=%s)",
                symbol,
                len(news_items),
                new_count,
                published_iso,
            )
        except Exception:
            logger.exception("News update failed for %s", symbol)
            continue

    try:
        await purge_old_articles(ARTICLE_RETENTION_DAYS)
    except Exception:
        logger.exception("Failed to purge articles older than %s days", ARTICLE_RETENTION_DAYS)


async def run_scheduled_news_update() -> None:
    """Cron entry: never cooldown-limited; skipped only if a run is already in progress."""
    await news_update_guard.run_from_schedule(run_news_update)
