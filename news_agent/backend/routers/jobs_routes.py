from fastapi import APIRouter, Depends

from deps import verify_internal_api_key
from jobs.news_update import run_news_update
from llm_limits import news_update_guard
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
        "2. Fetch **all** Finnhub articles published **today** for that stock\n"
        "3. Upsert those articles locally into `news_articles` / `stock_articles`\n"
        "4. Rebuild `stock_summery` via HTTP `PUT /stocks/{stock_id}/summary`\n"
        "5. Delete articles older than 7 days (AI summaries deleted with them)\n\n"
        "Stocks with no news today are skipped. Failures on one stock do not stop the rest.\n\n"
        "The hourly scheduler is not rate-limited. This HTTP trigger is: one run at a time, "
        "and at most once per 15 minutes, so a stolen key cannot loop LLM spend."
    ),
    response_model=JobTriggerResponse,
    responses={
        409: {"description": "A news-update run is already in progress"},
        429: {"description": "HTTP trigger cooldown (scheduled job is not limited)"},
    },
)
async def trigger_news_update() -> JobTriggerResponse:
    await news_update_guard.run_from_http(run_news_update)
    return JobTriggerResponse(
        job="news-update",
        message="News update job completed",
    )
