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


UNAVAILABLE_MARKERS: tuple[str, ...] = (
    "503",
    "unavailable",
    "high demand",
    "overloaded",
    "try again later",
    "429",
    "rate limit",
    "resource exhausted",
    "temporarily",
    "capacity",
)
UNAVAILABLE_EXC_NAMES: frozenset[str] = frozenset(
    {
        "ServiceUnavailableError",
        "RateLimitError",
        "APIConnectionError",
        "Timeout",
        "InternalServerError",
        "APITimeoutError",
    }
)


def split_model_ids(raw: str) -> list[str]:
    parts: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        item: str = chunk.strip()
        if item:
            parts.append(item)
    return parts


def is_model_unavailable(exc: BaseException) -> bool:
    if type(exc).__name__ in UNAVAILABLE_EXC_NAMES:
        return True
    text: str = str(exc).lower()
    return any(marker in text for marker in UNAVAILABLE_MARKERS)
