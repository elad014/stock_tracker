"""In-process sliding-window limiter for LLM HTTP calls.

Shared by all agents. Pass agent-specific max_attempts, window, and error text
when constructing. Do not use this for login or password reset.
"""

import time
from threading import Lock

from fastapi import HTTPException, status


class LlmRateLimiter:
    """Cap how often a key may consume an LLM call."""

    def __init__(self, max_attempts: int, window_seconds: int, detail: str) -> None:
        self._max_attempts: int = max_attempts
        self._window_seconds: int = window_seconds
        self._detail: str = detail
        self._hits: dict[str, list[float]] = {}
        self._lock: Lock = Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff: float = now - self._window_seconds
        stamps: list[float] = [stamp for stamp in self._hits.get(key, []) if stamp > cutoff]
        if stamps:
            self._hits[key] = stamps
        else:
            self._hits.pop(key, None)
        return stamps

    def assert_allowed(self, key: str) -> None:
        now: float = time.monotonic()
        with self._lock:
            stamps: list[float] = self._prune(key, now)
            if len(stamps) >= self._max_attempts:
                retry_after: int = max(1, int(self._window_seconds - (now - stamps[0])))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    self._detail,
                    headers={"Retry-After": str(retry_after)},
                )

    def record(self, key: str) -> None:
        now: float = time.monotonic()
        with self._lock:
            stamps: list[float] = self._prune(key, now)
            stamps.append(now)
            self._hits[key] = stamps

    def consume(self, key: str) -> None:
        """Reject if over quota, otherwise count this call."""
        self.assert_allowed(key)
        self.record(key)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
