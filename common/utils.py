"""Shared FastAPI health routes, HealthResponse, and APScheduler helpers."""

from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


def mount_health(app: FastAPI) -> None:
    """Register GET / and GET /health. No API key required."""

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


def make_scheduler() -> AsyncIOScheduler:
    """AsyncIOScheduler with defaults that survive late Docker Desktop wakes.

    Default misfire_grace_time is 1s. A busy event loop routinely wakes a few
    seconds late, and APScheduler then skips the job.
    """
    return AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )


def parse_cron(expr: str, timezone: str) -> CronTrigger:
    parts: list[str] = expr.split()
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
