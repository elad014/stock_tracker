import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status

from article_extractor import ArticleExtractor
from db_logics import articles_db_logic as articles_db
from llm_provider_client import LLMProviderClient
from models.articles import ArticleRecord, ArticleSummaryResponse, ArticleSyncResponse
from news_provider_client import NewsItem, NewsProviderClient
from stock_manager_client import StockManagerClient

logger = logging.getLogger(__name__)

STATUS_READY = "ready"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
_EXTRACT_CONCURRENCY = 5


def _stock_manager_client() -> StockManagerClient:
    return StockManagerClient()


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMProviderClient:
    return LLMProviderClient()


def _extractor() -> ArticleExtractor:
    return ArticleExtractor()


async def _run_blocking(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


def _parse_published_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def to_article_payload(items: list[NewsItem]) -> list[dict[str, Any]]:
    """Convert provider news items into the local upsert payload."""
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


def _to_record(article: dict[str, Any]) -> ArticleRecord:
    return ArticleRecord(
        article_id=article["article_id"],
        url=article["url"],
        title=article["title"],
        source=article.get("source"),
        published_at=article.get("published_at"),
        provider=article.get("provider"),
        provider_summary=article.get("provider_summary"),
        ai_summary=article.get("ai_summary"),
        ai_summary_status=article.get("ai_summary_status") or "none",
        ai_summary_model=article.get("ai_summary_model"),
        ai_summary_error=article.get("ai_summary_error"),
        ai_summary_updated_at=article.get("ai_summary_updated_at"),
    )


def _placeholder_body(article: dict[str, Any]) -> Optional[str]:
    """Return Finnhub blurb, or None. Never use the headline as article body."""
    blurb = str(article.get("provider_summary") or "").strip()
    return blurb or None


def _is_placeholder_text(article: dict[str, Any]) -> bool:
    """True when ``text`` is empty, the title, or title+blurb — not a full article."""
    text = str(article.get("text") or "").strip()
    if not text:
        return True
    title = str(article.get("title") or "").strip()
    blurb = str(article.get("provider_summary") or "").strip()
    if title and text == title:
        return True
    if title and blurb and text == f"{title}\n\n{blurb}":
        return True
    if blurb and text == blurb:
        return True
    return False


async def _ensure_article_body(article: dict[str, Any]) -> dict[str, Any]:
    """Download the page and store readable body in ``text`` when missing."""
    if not _is_placeholder_text(article):
        return article

    url = str(article.get("url") or "").strip()
    extracted = await _run_blocking(_extractor().extract, url) if url else None
    if extracted:
        updated = await articles_db.set_article_text(article["article_id"], extracted)
        return updated or article

    current = str(article.get("text") or "").strip()
    title = str(article.get("title") or "").strip()
    blurb = str(article.get("provider_summary") or "").strip()
    if (not current) or (title and current == title) or (
        title and blurb and current == f"{title}\n\n{blurb}"
    ):
        repaired = await articles_db.set_article_text(
            article["article_id"],
            _placeholder_body(article),
        )
        return repaired or article
    return article


async def upsert_stock_articles(
    stock_id: str,
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Insert/update news_articles, link them, and fill ``text`` from the URL."""
    pending: list[dict[str, Any]] = []
    for item in articles:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        article = await articles_db.upsert_article(
            url=url,
            title=title,
            source=item.get("source"),
            published_at=_parse_published_at(item.get("published_at")),
            provider=str(item.get("provider") or "finnhub"),
            provider_summary=item.get("provider_summary"),
        )
        await articles_db.link_article_to_stock(stock_id, article["article_id"])
        pending.append(article)

    if not pending:
        return []

    semaphore = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

    async def fill(article: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _ensure_article_body(article)

    return list(await asyncio.gather(*[fill(article) for article in pending]))


async def list_stock_articles(stock_id: str, limit: int = 100) -> list[ArticleRecord]:
    rows = await articles_db.list_by_stock(stock_id, limit=limit)
    return [_to_record(row) for row in rows]


async def purge_old_articles(days: int = 7) -> dict[str, str]:
    result = await articles_db.delete_older_than(days)
    orphans = await articles_db.delete_orphans_older_than(days)
    logger.info("Purged articles older than %s days (%s, orphans=%s)", days, result, orphans)
    return {
        "message": f"Purged articles older than {days} days",
        "result": result,
        "orphans": orphans,
    }


async def sync_stock_articles(
    stock_id: str,
    outputsize: int = 10,
) -> ArticleSyncResponse:
    """Fetch today's Finnhub articles for one stock and store them (Swagger / ops only)."""
    _ = outputsize
    stock = await _stock_manager_client().get_stock(stock_id)
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
    stored = await upsert_stock_articles(stock_id, payload) if payload else []
    return ArticleSyncResponse(stock_id=stock_id, symbol=symbol, stored=len(stored))


def _summary_source(article: dict[str, Any], extracted_text: Optional[str]) -> str:
    """LLM input only. Does not decide what is stored in ``text``."""
    if extracted_text:
        return extracted_text
    existing = str(article.get("text") or "").strip()
    title = str(article.get("title") or "").strip()
    if existing and existing != title:
        return existing
    provider_summary = str(article.get("provider_summary") or "").strip()
    if provider_summary:
        return f"{title}\n\n{provider_summary}" if title else provider_summary
    return title


async def summarize_article(article_id: str) -> ArticleSummaryResponse:
    """Summarize one article exactly once, no matter how many users ask."""
    existing = await articles_db.get_by_id(article_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")

    claimed = await articles_db.claim_for_summary(article_id)
    if claimed is None:
        current = await articles_db.get_by_id(article_id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
        return _article_response(current)

    extracted_text: Optional[str] = None
    try:
        extractor = _extractor()
        extracted_text = await _run_blocking(extractor.extract, claimed["url"])
        if extracted_text:
            await articles_db.set_article_text(article_id, extracted_text)
        elif _is_placeholder_text(claimed):
            await articles_db.set_article_text(
                article_id,
                _placeholder_body(claimed),
            )

        text = _summary_source(claimed, extracted_text)
        if not text.strip():
            raise RuntimeError("No article text available to summarize")

        result = await _llm_client().summarize(text, symbol=None)
        content = result.content.strip()
        if not content:
            raise RuntimeError("LLM returned an empty summary")

        updated = await articles_db.set_summary(
            article_id,
            ai_summary=content,
            ai_summary_status=STATUS_READY,
            ai_summary_model=result.model or None,
            text=extracted_text,
        )
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
        logger.info(
            "Summarized article %s (extracted=%s)",
            article_id,
            bool(extracted_text),
        )
        return _article_response(updated, extracted=bool(extracted_text))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Article summarize failed for %s", article_id)
        failed = await articles_db.set_summary(
            article_id,
            ai_summary=None,
            ai_summary_status=STATUS_FAILED,
            ai_summary_error=str(exc)[:500],
        )
        if failed is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found") from exc
        return _article_response(failed)
