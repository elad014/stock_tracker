import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from database_client import db
from internal_docs import disabled_docs_kwargs, mount_protected_docs
from jobs.cleanup_archive import run_scheduled_cleanup_archive
from jobs.daily_update import run_scheduled_daily_update
from routers.stocks_routes import router as stocks_router
from utils import make_scheduler, mount_health, parse_cron

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = make_scheduler()

API_DESCRIPTION = """
Internal Stock Manager service for stock_tracker.

## Auth
All write endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

`/docs`, `/redoc`, and `/openapi.json` require the same key (header, HTTP Basic
password, or `?api_key=`). They are not public.

Use the **Authorize** button in Swagger and paste the same key configured in `.env`.

## Responsibilities
- Validate symbols via Twelve Data
- Maintain `stock_quotes`, `stock_history`, `watchlist`
- Persist rollup `stock_summery` on `stock_quotes` (written by news-agent over HTTP)
- Restore from `stock_history_archive` when possible
- Background jobs: daily quote/history update + unwatched cleanup/archive
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    tz = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")
    daily_cron = os.getenv("DAILY_CRON", "35 9 * * mon-fri")
    cleanup_cron = os.getenv("CLEANUP_CRON", "0 * * * *")

    scheduler.add_job(
        run_scheduled_daily_update,
        trigger=parse_cron(daily_cron, tz),
        id="daily_update",
        replace_existing=True,
    )
    scheduler.add_job(
        run_scheduled_cleanup_archive,
        trigger=parse_cron(cleanup_cron, tz),
        id="cleanup_archive",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (daily=%s, cleanup=%s, tz=%s)", daily_cron, cleanup_cron, tz)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


app = FastAPI(
    title="Stock Manager API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    **disabled_docs_kwargs(),
    openapi_tags=[
        {
            "name": "Watchlist",
            "description": "Add/remove stocks on a user's watchlist and sync market data.",
        },
        {
            "name": "Admin",
            "description": "Admin helpers for assigning stocks and bulk unwatch.",
        },
        {
            "name": "Jobs",
            "description": "Manually trigger scheduled daily-update and cleanup/archive jobs.",
        },
        {
            "name": "News",
            "description": "Read/update AI news summaries stored on stock_quotes.stock_summery.",
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(stocks_router)
mount_protected_docs(app)
mount_health(app)
