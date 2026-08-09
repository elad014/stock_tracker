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
        "Fetches company news from the news provider and upserts it through "
        "stock-manager. Used for stocks added between scheduled runs."
    ),
    response_model=ArticleSyncResponse,
    responses={404: {"description": "Stock not found"}},
)
async def sync_stock_articles(
    stock_id: str = Path(..., description="Stock UUID from stock_quotes.stock_id"),
    outputsize: int = Query(10, ge=1, le=50, description="Max articles to store"),
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
