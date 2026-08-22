"""Chat-agent instances of the shared LLM limiter."""

from constant import CHAT_MAX_ATTEMPTS, CHAT_WINDOW_SECONDS
from llm_guard import LlmRateLimiter

chat_limiter = LlmRateLimiter(
    max_attempts=CHAT_MAX_ATTEMPTS,
    window_seconds=CHAT_WINDOW_SECONDS,
    detail="Too many chat messages, please try again later",
)
