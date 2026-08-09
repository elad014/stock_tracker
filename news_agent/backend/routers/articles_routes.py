from fastapi import APIRouter, Depends, Path, Query

from deps import verify_internal_api_key
from models.articles import ArticleSummaryResponse, ArticleSyncResponse
import services.article_service as article_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY or FINNHUB_API_KEY not configured"},
        502: {"description": "Upstream provider or LLM request failed"},
    },
)


@router.post(
    "/stocks/{stock_id}/articles/sync",
    tags=["Articles"],
    summary="Fetch provider news for one stock and store it",
    description=(
        "Fetches **today's** Finnhub articles for one stock and upserts them "
        "through stock-manager. For Swagger / ops only — the UI never calls this. "
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
        "Claims the article through stock-manager. The winning caller extracts the "
        "article text from its URL (falling back to the provider blurb), sends it to "
        "llm-service, and stores the result. Concurrent callers get status=pending "
        "and should poll until status=ready. A cached summary returns immediately."
    ),
    response_model=ArticleSummaryResponse,
    responses={404: {"description": "Article not found"}},
)
async def summarize_article(
    article_id: str = Path(..., description="Article UUID"),
) -> ArticleSummaryResponse:
    return await article_service.summarize_article(article_id)
