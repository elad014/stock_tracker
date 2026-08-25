import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI

from clients.database_client import db
from internal_docs import disabled_docs_kwargs, mount_protected_docs
from jobs.news_update import run_scheduled_news_update
from routers.articles_routes import router as articles_router
from routers.jobs_routes import router as jobs_router
from routers.news_routes import router as news_router
from utils import make_scheduler, mount_health, parse_cron

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = make_scheduler()

API_DESCRIPTION = """
Internal News Agent for stock_tracker.

Owns `news_articles` and `stock_articles` on the shared Neon database.
Reads `stock_quotes` only to join/filter by ticker. Rollup `stock_summery`
is written through stock-manager HTTP (news-agent does not write quotes).
Summaries go through ``llm_provider_client`` (LiteLLM), not chat-agent.

## Auth
News and agent endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

`/docs`, `/redoc`, and `/openapi.json` require the same key (header, HTTP Basic
password, or `?api_key=`). They are not public.

## Swagger abilities
1. **News** — `GET /news/{symbol}`: get Finnhub news for one stock (no LLM, no DB write)
2. **Search** — `POST /api/v1/news/search-and-summarize`: rank stored article
   text for one ticker (last 7 days) and return matching sentences plus optional
   LLM analysis
3. **Agent** — `POST /jobs/news-update`: for every stock, fetch news -> summarize via LiteLLM -> HTTP update `stock_summery`
4. **Articles** — `GET /stocks/{stock_id}/articles`, `POST /stocks/{stock_id}/articles/sync`,
   `POST /articles/{article_id}/summarize`

News source: Finnhub (`FINNHUB_API_KEY`) via `common/news_provider_client`.
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    tz = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")
    news_cron = os.getenv("NEWS_CRON", "0 * * * *")

    scheduler.add_job(
        run_scheduled_news_update,
        trigger=parse_cron(news_cron, tz),
        id="news_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (news=%s, tz=%s)", news_cron, tz)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


app = FastAPI(
    title="News Agent API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    **disabled_docs_kwargs(),
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
mount_protected_docs(app)
mount_health(app)
