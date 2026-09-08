import asyncio
import os
from typing import Literal

ChatRole = Literal["user", "assistant"]


class SessionStore:
    """In-memory per-user chat history with per-user locks for safe concurrency."""

    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def get_history(self, user_id: str) -> list[dict[str, str]]:
        return list(self._histories.get(user_id, []))

    def set_history(self, user_id: str, messages: list[dict[str, str]]) -> None:
        self._histories[user_id] = self._trim(messages)

    def clear(self, user_id: str) -> None:
        self._histories.pop(user_id, None)

    def lock(self, user_id: str) -> asyncio.Lock:
        return self._lock_for(user_id)

    def _trim(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        if len(messages) <= self._max_messages:
            return messages
        return messages[-self._max_messages :]


def _max_session_messages() -> int:
    raw = os.getenv("LLM_SESSION_MAX_MESSAGES", "20").strip()
    try:
        value = int(raw)
    except ValueError:
        return 20
    return max(value, 2)


session_store = SessionStore(max_messages=_max_session_messages())
