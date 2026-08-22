"""Doc-agent instances of the shared LLM limiter."""

from constant import (
    DOC_ASK_MAX_ATTEMPTS,
    DOC_ASK_WINDOW_SECONDS,
    DOC_INGEST_MAX_ATTEMPTS,
    DOC_INGEST_WINDOW_SECONDS,
)
from llm_guard import LlmRateLimiter

ingest_limiter = LlmRateLimiter(
    max_attempts=DOC_INGEST_MAX_ATTEMPTS,
    window_seconds=DOC_INGEST_WINDOW_SECONDS,
    detail="Too many document ingestions, please try again later",
)
ask_limiter = LlmRateLimiter(
    max_attempts=DOC_ASK_MAX_ATTEMPTS,
    window_seconds=DOC_ASK_WINDOW_SECONDS,
    detail="Too many document questions, please try again later",
)
