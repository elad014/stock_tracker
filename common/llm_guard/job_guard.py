"""Single-flight job runner: HTTP has a cooldown, the scheduler does not."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class JobRunGuard:
    """One in-process run at a time. Cron is never cooldown-limited."""

    def __init__(
        self,
        http_cooldown_seconds: int,
        *,
        busy_detail: str,
        cooldown_detail: str,
        skip_log: str,
    ) -> None:
        self._http_cooldown_seconds: int = http_cooldown_seconds
        self._busy_detail: str = busy_detail
        self._cooldown_detail: str = cooldown_detail
        self._skip_log: str = skip_log
        self._lock: asyncio.Lock = asyncio.Lock()
        self._running: bool = False
        self._last_http_started_at: Optional[float] = None

    async def _begin(self, *, http_trigger: bool) -> Optional[str]:
        async with self._lock:
            if self._running:
                return "running"
            if http_trigger and self._last_http_started_at is not None:
                elapsed: float = time.monotonic() - self._last_http_started_at
                if elapsed < self._http_cooldown_seconds:
                    retry_after: int = max(
                        1,
                        int(self._http_cooldown_seconds - elapsed),
                    )
                    raise HTTPException(
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        self._cooldown_detail,
                        headers={"Retry-After": str(retry_after)},
                    )
            self._running = True
            if http_trigger:
                self._last_http_started_at = time.monotonic()
            return None

    async def _end(self) -> None:
        async with self._lock:
            self._running = False

    async def run_from_http(self, job: Callable[[], Awaitable[None]]) -> None:
        blocked: Optional[str] = await self._begin(http_trigger=True)
        if blocked == "running":
            raise HTTPException(status.HTTP_409_CONFLICT, self._busy_detail)
        try:
            await job()
        finally:
            await self._end()

    async def run_from_schedule(self, job: Callable[[], Awaitable[None]]) -> None:
        blocked: Optional[str] = await self._begin(http_trigger=False)
        if blocked == "running":
            logger.warning(self._skip_log)
            return
        try:
            await job()
        finally:
            await self._end()
