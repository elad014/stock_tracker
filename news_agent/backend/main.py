import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI
from zoneinfo import ZoneInfo

from jobs.news_update import run_news_update
from models.jobs import HealthResponse
from routers.articles_routes import router as articles_router
from routers.jobs_routes import router as jobs_router
from routers.news_routes import router as news_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

API_DESCRIPTION = """
Internal News Agent for stock_tracker.

Orchestrates the news summary pipeline only — no direct DB or LiteLLM access.

## Auth
News and agent endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

## Swagger abilities
1. **News** — `GET /news/{symbol}`: get Finnhub news for one stock (no LLM, no DB write)
2. **Agent** — `POST /jobs/news-update`: for every stock, fetch news -> summarize via llm-service -> update DB
3. **Articles** — `POST /stocks/{stock_id}/articles/sync` to store a stock's articles, and
   `POST /articles/{article_id}/summarize` to summarize one article once for all users

News source: Finnhub (`FINNHUB_API_KEY`) via `common/news_provider_client`.
"""


def _parse_cron(expr: str, timezone: str) -> CronTrigger:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: {expr}")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=ZoneInfo(timezone),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    tz = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")
    news_cron = os.getenv("NEWS_CRON", "0 * * * *")

    scheduler.add_job(
        run_news_update,
        trigger=_parse_cron(news_cron, tz),
        id="news_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (news=%s, tz=%s)", news_cron, tz)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="News Agent API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
    openapi_tags=[
        {
            "name": "News",
            "description": "Get Finnhub news articles for a specific stock (read-only).",
        },
        {
            "name": "Agent",
            "description": (
                "Trigger the full pipeline: all stocks, one-by-one Finnhub news fetch, "
                "LLM summary, then DB update."
            ),
        },
        {
            "name": "Articles",
            "description": (
                "Store per-article news for a stock and generate one shared "
                "AI summary per article."
            ),
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(news_router)
app.include_router(articles_router)
app.include_router(jobs_router)


@app.api_route(
    "/",
    methods=["GET", "HEAD"],
    tags=["Health"],
    summary="Root health check",
    response_model=HealthResponse,
    include_in_schema=False,
)
@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
