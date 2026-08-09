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
from routers.jobs_routes import router as jobs_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

API_DESCRIPTION = """
Internal News Agent for stock_tracker.

Orchestrates the news summary pipeline only — no direct DB or LiteLLM access.

## Auth
Manual job triggers require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

## Flow
1. List stocks via stock-manager
2. Fetch Twelve Data news per symbol
3. Skip when no news
4. Summarize via llm-service (UP/DOWN/NEUTRAL outlook)
5. Persist summary + newest article time via stock-manager
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
            "name": "Jobs",
            "description": "Manually trigger the news summary cron job.",
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
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
