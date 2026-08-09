from fastapi import APIRouter, Depends

from deps import verify_internal_api_key
from jobs.news_update import run_news_update
from models.jobs import JobTriggerResponse

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY not configured on server"},
    },
)


@router.post(
    "/jobs/news-update",
    tags=["Jobs"],
    summary="Trigger news summary update",
    description=(
        "Manually runs the news cron job: list stocks from stock-manager, "
        "fetch Twelve Data news, summarize via llm-service, and update "
        "stock_summery / stock_news_published_at when news exists."
    ),
    response_model=JobTriggerResponse,
)
async def trigger_news_update() -> JobTriggerResponse:
    await run_news_update()
    return JobTriggerResponse(
        job="news-update",
        message="News update job completed",
    )
