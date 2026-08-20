from dataclasses import dataclass

from llm_guard.prompt import wrap_untrusted

__all__ = ["LLMCompletionResult", "wrap_untrusted"]


@dataclass
class LLMCompletionResult:
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
