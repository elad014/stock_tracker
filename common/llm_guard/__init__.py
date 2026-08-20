"""Shared LLM safety for every agent: prompt fencing and usage limits.

Not for login/register. Auth throttling stays in ui-service.
Each agent sets its own numbers and task text; this package stays generic.
"""

from llm_guard.job_guard import JobRunGuard
from llm_guard.limiter import LlmRateLimiter
from llm_guard.prompt import (
    UNTRUSTED_BEGIN,
    UNTRUSTED_DATA_RULES,
    UNTRUSTED_END,
    compose_system_prompt,
    guarded_user_message,
    wrap_untrusted,
)

__all__ = [
    "JobRunGuard",
    "LlmRateLimiter",
    "UNTRUSTED_BEGIN",
    "UNTRUSTED_DATA_RULES",
    "UNTRUSTED_END",
    "compose_system_prompt",
    "guarded_user_message",
    "wrap_untrusted",
]
