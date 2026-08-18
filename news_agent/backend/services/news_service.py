import asyncio
import logging
from typing import Any

from fastapi import HTTPException, status

from models.news import NewsArticle, StockNewsResponse
from news_provider_client import NewsProviderClient

logger = logging.getLogger(__name__)


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


async def _run_provider(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


async def get_stock_news(symbol: str, outputsize: int = 5) -> StockNewsResponse:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")

    size = max(1, min(int(outputsize), 50))
    provider = _news_provider()

    try:
        items = await _run_provider(provider.get_news, normalized, size)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        logger.warning("News fetch failed for %s: %s", normalized, message)
        if "not found" in message.lower():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Symbol not found: {normalized}",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Failed to fetch news for {normalized}",
        ) from exc

    articles = [
        NewsArticle(
            title=item.title,
            url=item.url,
            published_at=item.published_at,
            source=item.source,
            summary=item.summary,
        )
        for item in items
    ]
    return StockNewsResponse(
        symbol=normalized,
        count=len(articles),
        articles=articles,
    )
