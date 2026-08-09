from dataclasses import dataclass


@dataclass
class LLMCompletionResult:
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
