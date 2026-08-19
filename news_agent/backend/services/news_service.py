import asyncio
import logging
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException, status

from constant import (
    ARTICLE_RETENTION_DAYS,
    NEWS_SEARCH_MAX_CHARS,
    NEWS_SEARCH_SYSTEM_PROMPT,
)
from db_logics import articles_db_logic as articles_db
from llm_provider_client import LLMProviderClient
from models.news import NewsArticle, SearchAndSummarizeResponse, StockNewsResponse
from news_provider_client import NewsProviderClient

logger = logging.getLogger(__name__)


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMProviderClient:
    return LLMProviderClient()


async def _run_provider(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


async def get_stock_news(
    symbol: str,
    outputsize: int = 50,
    *,
    day: Optional[date] = None,
) -> StockNewsResponse:
    """Return Finnhub articles for one calendar day (default: today)."""
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")

    provider = _news_provider()
    target = day or date.today()
    # outputsize is kept as an optional cap for Swagger inspection; None path unused here.
    limit = max(1, min(int(outputsize), 200))

    try:
        items = await _run_provider(provider.get_news_for_day, normalized, target)
        items = items[:limit]
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


def _join_articles(bodies: list[str]) -> str:
    joined = "\n\n---\n\n".join(item.strip() for item in bodies if item.strip())
    if len(joined) <= NEWS_SEARCH_MAX_CHARS:
        return joined
    return joined[:NEWS_SEARCH_MAX_CHARS]


async def search_and_summarize(symbol: str, query: str) -> SearchAndSummarizeResponse:
    """Answer a question using stored article bodies from the last 7 days."""
    ticker: str = symbol.strip().upper()
    question: str = query.strip()
    if not ticker:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")
    if not question:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "query must not be empty")

    empty = SearchAndSummarizeResponse(
        summary="No recent news found for this symbol.",
    )
    try:
        bodies = await articles_db.list_recent_texts_by_symbol(
            ticker,
            days=ARTICLE_RETENTION_DAYS,
        )
    except Exception as exc:
        logger.exception("Failed to load article texts for %s", ticker)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to load recent articles",
        ) from exc

    if not bodies:
        return empty

    corpus = _join_articles(bodies)
    if not corpus:
        return empty

    user_message = (
        f"Ticker: {ticker}\n"
        f"User query: {question}\n\n"
        f"News articles:\n{corpus}"
    )
    try:
        result = await _llm_client().chat_completion(
            [
                {"role": "system", "content": NEWS_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("News search LLM failed for %s", ticker)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    summary = result.content.strip()
    if not summary:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LLM returned an empty summary")
    return SearchAndSummarizeResponse(summary=summary)
