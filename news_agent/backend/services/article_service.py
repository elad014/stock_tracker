import asyncio
import logging
from typing import Any, Optional

from fastapi import HTTPException, status

from article_extractor_client import ArticleExtractorClient
from llm_service_client import LLMServiceClient
from models.articles import ArticleSummaryResponse, ArticleSyncResponse
from news_provider_client import NewsItem, NewsProviderClient
from stock_manager_client import StockManagerClient

logger = logging.getLogger(__name__)

STATUS_READY = "ready"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"


def _stock_manager_client() -> StockManagerClient:
    return StockManagerClient()


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMServiceClient:
    return LLMServiceClient()


def _extractor() -> ArticleExtractorClient:
    return ArticleExtractorClient()


async def _run_blocking(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


def to_article_payload(items: list[NewsItem]) -> list[dict[str, Any]]:
    """Convert provider news items into the stock-manager upsert payload."""
    payload: list[dict[str, Any]] = []
    for item in items:
        if not item.url:
            continue
        payload.append(
            {
                "url": item.url,
                "title": item.title,
                "source": item.source,
                "published_at": (
                    item.published_at.isoformat() if item.published_at else None
                ),
                "provider": "finnhub",
                "provider_summary": item.summary,
            }
        )
    return payload


def _article_response(
    article: dict[str, Any],
    *,
    extracted: bool = False,
) -> ArticleSummaryResponse:
    return ArticleSummaryResponse(
        article_id=article["article_id"],
        title=article["title"],
        url=article["url"],
        status=article.get("ai_summary_status") or "none",
        ai_summary=article.get("ai_summary"),
        ai_summary_model=article.get("ai_summary_model"),
        ai_summary_error=article.get("ai_summary_error"),
        ai_summary_updated_at=article.get("ai_summary_updated_at"),
        extracted=extracted,
    )


async def sync_stock_articles(
    stock_id: str,
    outputsize: int = 10,
) -> ArticleSyncResponse:
    """Fetch today's Finnhub articles for one stock and store them (Swagger / ops only)."""
    _ = outputsize
    stock_manager = _stock_manager_client()
    stock = await stock_manager.get_stock(stock_id)
    symbol = str(stock.get("symbol") or "").strip().upper()
    if not symbol:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock has no symbol")

    provider = _news_provider()
    try:
        items = await _run_blocking(provider.get_news_for_day, symbol)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("News fetch failed for %s: %s", symbol, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Failed to fetch news for {symbol}",
        ) from exc

    payload = to_article_payload(items)
    if payload:
        await stock_manager.upsert_stock_articles(stock_id, payload)

    return ArticleSyncResponse(stock_id=stock_id, symbol=symbol, stored=len(payload))


def _summary_source(article: dict[str, Any], extracted_text: Optional[str]) -> str:
    if extracted_text:
        return extracted_text
    provider_summary = str(article.get("provider_summary") or "").strip()
    title = str(article.get("title") or "").strip()
    if provider_summary:
        return f"{title}\n\n{provider_summary}" if title else provider_summary
    return title


async def summarize_article(article_id: str) -> ArticleSummaryResponse:
    """Summarize one article exactly once, no matter how many users ask."""
    stock_manager = _stock_manager_client()
    claim = await stock_manager.claim_article_summary(article_id)
    article: dict[str, Any] = claim["article"]

    if not claim.get("claimed"):
        # Another request owns the work, or the summary is already cached.
        return _article_response(article)

    extracted_text: Optional[str] = None
    try:
        extractor = _extractor()
        extracted_text = await _run_blocking(extractor.extract, article["url"])

        text = _summary_source(article, extracted_text)
        if not text.strip():
            raise RuntimeError("No article text available to summarize")

        result = await _llm_client().summarize(text, symbol=None)
        content = str(result.get("content") or "").strip()
        if not content:
            raise RuntimeError("LLM returned an empty summary")

        updated = await stock_manager.update_article_summary(
            article_id,
            ai_summary=content,
            ai_summary_status=STATUS_READY,
            ai_summary_model=str(result.get("model") or "") or None,
        )
        logger.info(
            "Summarized article %s (extracted=%s)",
            article_id,
            bool(extracted_text),
        )
        return _article_response(updated, extracted=bool(extracted_text))
    except Exception as exc:
        logger.exception("Article summarize failed for %s", article_id)
        failed = await stock_manager.update_article_summary(
            article_id,
            ai_summary=None,
            ai_summary_status=STATUS_FAILED,
            ai_summary_error=str(exc)[:500],
        )
        return _article_response(failed)
