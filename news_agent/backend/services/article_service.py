import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status

from article_extractor import ArticleExtractor
from article_extractor.util import is_usable_article_text
from constant import (
    ARTICLE_CANNOT_EXTRACT_MESSAGE,
    ARTICLE_EXTRACT_MIN_CHARS,
    ARTICLE_EXTRACT_RETRY_LIMIT,
)
from db_logics import articles_db_logic as articles_db
from llm_limits import article_summarize_limiter
from clients.llm_provider_client import LLMProviderClient
from models.articles import ArticleRecord, ArticleSummaryResponse, ArticleSyncResponse
from clients.news_provider_client import NewsItem, NewsProviderClient
from clients.stock_manager_client import StockManagerClient

logger = logging.getLogger(__name__)

STATUS_NONE = "none"
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


def _is_placeholder_text(article: dict[str, Any]) -> bool:
    """True when ``text`` is empty, a bot/JS wall, the title, or the Finnhub blurb."""
    text: str = str(article.get("text") or "").strip()
    if not is_usable_article_text(text, ARTICLE_EXTRACT_MIN_CHARS):
        return True
    title: str = str(article.get("title") or "").strip()
    blurb: str = str(article.get("provider_summary") or "").strip()
    if title and text == title:
        return True
    if title and blurb and text == f"{title}\n\n{blurb}":
        return True
    if blurb and text == blurb:
        return True
    return False


async def _ensure_article_body(article: dict[str, Any]) -> dict[str, Any]:
    """Visit the article URL and store the extracted body in ``text``.

    ``text`` is only the page body. Finnhub blurbs stay in ``provider_summary``.
    If extraction fails, ``text`` is left NULL so a later run can retry.
    """
    if not _is_placeholder_text(article):
        return article

    url: str = str(article.get("url") or "").strip()
    extracted: Optional[str] = (
        await _run_blocking(_extractor().extract, url) if url else None
    )
    if extracted:
        updated: Optional[dict[str, Any]] = await articles_db.set_article_text(
            article["article_id"],
            extracted,
        )
        logger.info(
            "Extracted article text for %s (%s chars)",
            article["article_id"],
            len(extracted),
        )
        return updated or article

    logger.info(
        "Could not extract article text for %s (%s)",
        article.get("article_id"),
        url or "missing-url",
    )
    current: str = str(article.get("text") or "").strip()
    if current:
        cleared: Optional[dict[str, Any]] = await articles_db.set_article_text(
            article["article_id"],
            None,
        )
        return cleared or article
    return article


async def upsert_stock_articles(
    stock_id: str,
    articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Insert/update news_articles, link them, and fill ``text`` from the URL.

    The int is how many articles were new for this stock (fresh URL row or
    first link to this ticker). Repeat Finnhub rows do not count.
    """
    pending: list[dict[str, Any]] = []
    new_count: int = 0
    for item in articles:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        article, inserted = await articles_db.upsert_article(
            url=url,
            title=title,
            source=item.get("source"),
            published_at=_parse_published_at(item.get("published_at")),
            provider=str(item.get("provider") or "finnhub"),
            provider_summary=item.get("provider_summary"),
        )
        linked: bool = await articles_db.link_article_to_stock(
            stock_id, article["article_id"]
        )
        if inserted or linked:
            new_count += 1
        pending.append(article)

    if not pending:
        return [], 0

    semaphore = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

    async def fill(article: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _ensure_article_body(article)

    filled: list[dict[str, Any]] = list(
        await asyncio.gather(*[fill(article) for article in pending])
    )
    return filled, new_count


async def retry_missing_article_bodies(
    days: int = 7,
    limit: int = ARTICLE_EXTRACT_RETRY_LIMIT,
) -> int:
    """Visit article URLs again for rows that still have no extracted ``text``."""
    pending: list[dict[str, Any]] = await articles_db.list_articles_needing_extract(
        days=days,
        limit=limit,
    )
    if not pending:
        return 0

    semaphore = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

    async def fill(article: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _ensure_article_body(article)

    filled: list[dict[str, Any]] = list(
        await asyncio.gather(*[fill(article) for article in pending])
    )
    extracted: int = 0
    for article in filled:
        if not _is_placeholder_text(article):
            extracted += 1
    return extracted


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
    stored, _new_count = (
        await upsert_stock_articles(stock_id, payload) if payload else ([], 0)
    )
    return ArticleSyncResponse(stock_id=stock_id, symbol=symbol, stored=len(stored))


def _stock_label(row: dict[str, Any]) -> str:
    symbol: str = str(row.get("symbol") or "").strip().upper()
    name: str = str(row.get("name") or "").strip()
    if symbol and name and name.upper() != symbol:
        return f"{name} ({symbol})"
    return symbol or name


def _linked_symbol_list(rows: list[dict[str, Any]]) -> Optional[str]:
    tickers: list[str] = []
    for row in rows:
        symbol: str = str(row.get("symbol") or "").strip().upper()
        if symbol and symbol not in tickers:
            tickers.append(symbol)
    if not tickers:
        return None
    return ", ".join(tickers)


async def _mark_cannot_extract(article_id: str) -> ArticleSummaryResponse:
    await articles_db.set_article_text(article_id, None)
    updated: Optional[dict[str, Any]] = await articles_db.set_summary(
        article_id,
        ai_summary=ARTICLE_CANNOT_EXTRACT_MESSAGE,
        ai_summary_status=STATUS_FAILED,
        ai_summary_error=ARTICLE_CANNOT_EXTRACT_MESSAGE,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return _article_response(updated, extracted=False)


async def summarize_article(article_id: str) -> ArticleSummaryResponse:
    """Summarize stored news_articles.text for the linked stock, once per article."""
    existing = await articles_db.get_by_id(article_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")

    claimed = await articles_db.claim_for_summary(article_id)
    if claimed is None:
        current = await articles_db.get_by_id(article_id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
        return _article_response(current)

    try:
        article_summarize_limiter.assert_allowed("article-summarize")
    except HTTPException:
        await articles_db.set_summary(
            article_id,
            ai_summary=claimed.get("ai_summary"),
            ai_summary_status=STATUS_NONE,
            ai_summary_error=None,
        )
        raise
    article_summarize_limiter.record("article-summarize")

    try:
        body: Optional[str] = None
        if not _is_placeholder_text(claimed):
            body = str(claimed.get("text") or "").strip()
        else:
            url: str = str(claimed.get("url") or "").strip()
            extracted_text: Optional[str] = (
                await _run_blocking(_extractor().extract, url) if url else None
            )
            if extracted_text:
                await articles_db.set_article_text(article_id, extracted_text)
                body = extracted_text
            else:
                await articles_db.set_article_text(article_id, None)

        if not body:
            return await _mark_cannot_extract(article_id)

        linked: list[dict[str, Any]] = await articles_db.list_linked_stocks(article_id)
        labels: list[str] = [
            label for label in (_stock_label(row) for row in linked) if label
        ]
        source: str = body
        if labels:
            source = "Related stocks: " + ", ".join(labels) + "\n\n" + body

        result = await _llm_client().summarize(
            source,
            symbol=_linked_symbol_list(linked),
        )
        content: str = result.content.strip()
        if not content:
            raise RuntimeError("LLM returned an empty summary")

        updated = await articles_db.set_summary(
            article_id,
            ai_summary=content,
            ai_summary_status=STATUS_READY,
            ai_summary_model=result.model or None,
            text=body,
        )
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
        logger.info("Summarized article %s from stored text", article_id)
        return _article_response(updated, extracted=True)
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
