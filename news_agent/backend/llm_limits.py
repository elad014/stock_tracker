"""News-agent instances of the shared LLM limiter / job guard."""

from constant import (
    ARTICLE_SUMMARIZE_MAX_ATTEMPTS,
    ARTICLE_SUMMARIZE_WINDOW_SECONDS,
    NEWS_UPDATE_HTTP_COOLDOWN_SECONDS,
)
from llm_guard import JobRunGuard, LlmRateLimiter

article_summarize_limiter = LlmRateLimiter(
    max_attempts=ARTICLE_SUMMARIZE_MAX_ATTEMPTS,
    window_seconds=ARTICLE_SUMMARIZE_WINDOW_SECONDS,
    detail="Too many article summaries, please try again later",
)
news_update_guard = JobRunGuard(
    NEWS_UPDATE_HTTP_COOLDOWN_SECONDS,
    busy_detail="News update already running",
    cooldown_detail=(
        "News update was triggered too recently; try again later. "
        "The scheduled job is not affected."
    ),
    skip_log="Skipping scheduled news-update; a run is already in progress",
)
