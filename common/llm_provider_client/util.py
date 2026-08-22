from dataclasses import dataclass, field


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMCompletionResult:
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
