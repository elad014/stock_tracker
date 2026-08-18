from fastapi import APIRouter, Depends

from deps import verify_internal_api_key
from jobs.news_update import run_news_update
from models.jobs import JobTriggerResponse

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY or FINNHUB_API_KEY not configured"},
    },
)


@router.post(
    "/jobs/news-update",
    tags=["Agent"],
    summary="Trigger agent: news -> LLM summary -> DB update (all stocks)",
    description=(
        "Runs the full news agent for **all** stocks, one stock at a time:\n\n"
        "1. List stocks from stock-manager\n"
        "2. Fetch Finnhub company news for that stock\n"
        "3. Send news text to llm-service `/summarize`\n"
        "4. Update `stock_summery` + `stock_news_published_at` via stock-manager\n\n"
        "Stocks with no news are skipped. Failures on one stock do not stop the rest."
    ),
    response_model=JobTriggerResponse,
)
async def trigger_news_update() -> JobTriggerResponse:
    await run_news_update()
    return JobTriggerResponse(
        job="news-update",
        message="News update job completed",
    )
