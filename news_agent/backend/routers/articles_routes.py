from fastapi import APIRouter, Depends, Path, Query

from deps import verify_internal_api_key
from models.articles import ArticleRecord, ArticleSummaryResponse, ArticleSyncResponse, MessageResponse
import services.article_service as article_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY or FINNHUB_API_KEY not configured"},
        502: {"description": "Upstream provider or LLM request failed"},
    },
)


@router.get(
    "/stocks/{stock_id}/articles",
    tags=["Articles"],
    summary="List news articles linked to a stock",
    response_model=list[ArticleRecord],
)
async def list_stock_articles(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
    limit: int = Query(100, ge=1, le=200, description="Max number of articles"),
) -> list[ArticleRecord]:
    return await article_service.list_stock_articles(stock_id, limit)


@router.post(
    "/stocks/{stock_id}/articles/sync",
    tags=["Articles"],
    summary="Fetch provider news for one stock and store it",
    description=(
        "Fetches **today's** Finnhub articles for one stock and upserts them "
        "directly into `news_articles` / `stock_articles`. For Swagger / ops only. "
        "Daily population is done by the cron job (`POST /jobs/news-update`)."
    ),
    response_model=ArticleSyncResponse,
    responses={404: {"description": "Stock not found"}},
)
async def sync_stock_articles(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
    outputsize: int = Query(
        100,
        ge=1,
        le=200,
        description="Ignored; kept for compatibility. Sync stores all of today's articles.",
    ),
) -> ArticleSyncResponse:
    return await article_service.sync_stock_articles(stock_id, outputsize)


@router.post(
    "/articles/{article_id}/summarize",
    tags=["Articles"],
    summary="Summarize one article (computed once, shared by all users)",
    description=(
        "Atomically claims the article in `news_articles`. The winning caller extracts "
        "text from the URL (falling back to the provider blurb), sends it to LiteLLM, "
        "and stores `ai_summary` plus `text`. Concurrent callers get status=pending."
    ),
    response_model=ArticleSummaryResponse,
    responses={404: {"description": "Article not found"}},
)
async def summarize_article(
    article_id: str = Path(..., description="Article UUID"),
) -> ArticleSummaryResponse:
    return await article_service.summarize_article(article_id)


@router.post(
    "/articles/cleanup",
    tags=["Articles"],
    summary="Delete articles older than the retention window",
    response_model=MessageResponse,
)
async def cleanup_old_articles(
    days: int = Query(7, ge=1, le=90, description="Retention window in calendar days"),
) -> MessageResponse:
    result = await article_service.purge_old_articles(days)
    return MessageResponse(message=result["message"])
