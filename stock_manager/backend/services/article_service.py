import logging
from typing import Any, Optional

from fastapi import HTTPException, status

from db_logics import articles_db_logic as articles_db
from db_logics import quotes_db_logic as quotes_db
from models.stocks import (
    ArticleInput,
    ArticleResponse,
    ClaimSummaryResponse,
)

logger = logging.getLogger(__name__)


def _to_response(article: dict[str, Any]) -> ArticleResponse:
    return ArticleResponse(**article)


async def _require_stock(stock_id: str) -> dict[str, Any]:
    existing = await quotes_db.get_by_id(stock_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return existing


async def _require_article(article_id: str) -> dict[str, Any]:
    article = await articles_db.get_by_id(article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return article


async def list_stock_articles(stock_id: str, limit: int = 10) -> list[ArticleResponse]:
    await _require_stock(stock_id)
    rows = await articles_db.list_by_stock(stock_id, limit=limit)
    return [_to_response(row) for row in rows]


async def upsert_stock_articles(
    stock_id: str,
    articles: list[ArticleInput],
) -> list[ArticleResponse]:
    await _require_stock(stock_id)

    stored: list[ArticleResponse] = []
    for item in articles:
        url = item.url.strip()
        title = item.title.strip()
        if not url or not title:
            continue
        article = await articles_db.upsert_article(
            url=url,
            title=title,
            source=item.source,
            published_at=item.published_at,
            provider=item.provider,
            provider_article_id=item.provider_article_id,
            provider_summary=item.provider_summary,
        )
        await articles_db.link_article_to_stock(stock_id, article["article_id"])
        stored.append(_to_response(article))
    return stored


async def get_article(article_id: str) -> ArticleResponse:
    return _to_response(await _require_article(article_id))


async def claim_article_summary(article_id: str) -> ClaimSummaryResponse:
    await _require_article(article_id)
    claimed = await articles_db.claim_for_summary(article_id)
    if claimed is not None:
        return ClaimSummaryResponse(claimed=True, article=_to_response(claimed))

    # Someone else owns the work (or it is already cached): report current state.
    current = await _require_article(article_id)
    return ClaimSummaryResponse(claimed=False, article=_to_response(current))


async def update_article_summary(
    article_id: str,
    ai_summary: Optional[str],
    ai_summary_status: str,
    ai_summary_model: Optional[str] = None,
    ai_summary_error: Optional[str] = None,
) -> ArticleResponse:
    normalized = ai_summary.strip() if ai_summary is not None else None
    if normalized == "":
        normalized = None
    updated = await articles_db.set_summary(
        article_id,
        ai_summary=normalized,
        ai_summary_status=ai_summary_status,
        ai_summary_model=ai_summary_model,
        ai_summary_error=ai_summary_error,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return _to_response(updated)


async def purge_old_articles(days: int = 7) -> dict[str, str]:
    result = await articles_db.delete_older_than(days)
    logger.info("Purged articles older than %s days (%s)", days, result)
    return {"message": f"Purged articles older than {days} days", "result": result}
