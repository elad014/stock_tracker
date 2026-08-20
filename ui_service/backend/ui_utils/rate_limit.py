import time
from threading import Lock

from fastapi import HTTPException, Request, status

_TOO_MANY: str = "Too many attempts, please try again later"


class RateLimiter:
    """In-process sliding-window limiter. One process (the ui-service container)."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts: int = max_attempts
        self._window_seconds: int = window_seconds
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
                    _TOO_MANY,
                    headers={"Retry-After": str(retry_after)},
                )

    def record(self, key: str) -> None:
        now: float = time.monotonic()
        with self._lock:
            stamps: list[float] = self._prune(key, now)
            stamps.append(now)
            self._hits[key] = stamps

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


def client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


login_by_email = RateLimiter(max_attempts=5, window_seconds=15 * 60)
login_by_ip = RateLimiter(max_attempts=20, window_seconds=15 * 60)
register_by_ip = RateLimiter(max_attempts=5, window_seconds=60 * 60)
reset_by_email = RateLimiter(max_attempts=5, window_seconds=15 * 60)
reset_by_ip = RateLimiter(max_attempts=10, window_seconds=15 * 60)
