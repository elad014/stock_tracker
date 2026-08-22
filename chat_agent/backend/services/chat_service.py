import logging
import os
from typing import Any, Optional

from fastapi import HTTPException, status

from constant import CHAT_MAX_TOOL_ROUNDS, CHAT_ORCHESTRATOR_SYSTEM_PROMPT
from llm_guard import guarded_user_message
from llm_limits import chat_limiter
from llm_provider_client import LLMCompletionResult, LLMProviderClient
from models.chat import ChatRequest, ChatResponse, ChatUsage
from services.chat_tools import CHAT_TOOLS, ChatTools
from services.session_store import session_store

logger = logging.getLogger(__name__)


def _default_max_tokens() -> Optional[int]:
    raw = os.getenv("LLM_MAX_TOKENS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "LLM_MAX_TOKENS must be a positive integer",
        ) from exc
    if value <= 0:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "LLM_MAX_TOKENS must be a positive integer",
        )
    return value


def _provider() -> LLMProviderClient:
    return LLMProviderClient()


def _system_prompt(document_id: Optional[str]) -> str:
    extra = os.getenv("LLM_SYSTEM_PROMPT", "").strip()
    parts: list[str] = [CHAT_ORCHESTRATOR_SYSTEM_PROMPT]
    if extra:
        parts.append(extra)
    viewing = (document_id or "").strip()
    if viewing:
        parts.append(f"The user is currently viewing document: {viewing}.")
    return " ".join(parts)


def _build_chat_messages(
    history: list[dict[str, str]],
    user_message: str,
    document_id: Optional[str],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(document_id)},
    ]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": guarded_user_message(
                "Answer the user's message using tools when needed. "
                "Search their documents even if they did not name a file.",
                ("USER_MESSAGE", user_message),
            ),
        }
    )
    return messages


def _usage_from_result(result: LLMCompletionResult) -> Optional[ChatUsage]:
    if (
        result.prompt_tokens is None
        and result.completion_tokens is None
        and result.total_tokens is None
    ):
        return None
    return ChatUsage(
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )


def _assistant_tool_message(result: LLMCompletionResult) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": result.content or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
            }
            for call in result.tool_calls
        ],
    }


async def _complete(
    messages: list[dict[str, Any]],
    *,
    temperature: Optional[float],
    max_tokens: Optional[int],
    with_tools: bool,
) -> LLMCompletionResult:
    try:
        return await _provider().chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=CHAT_TOOLS if with_tools else None,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Chat completion failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


async def _run_tool_loop(
    messages: list[dict[str, Any]],
    tools: ChatTools,
    *,
    temperature: Optional[float],
    max_tokens: Optional[int],
) -> LLMCompletionResult:
    result = await _complete(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        with_tools=True,
    )
    rounds = 0
    while result.tool_calls and rounds < CHAT_MAX_TOOL_ROUNDS:
        messages.append(_assistant_tool_message(result))
        for call in result.tool_calls:
            output = await tools.execute(call.name, call.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": output,
                }
            )
        rounds += 1
        result = await _complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            with_tools=rounds < CHAT_MAX_TOOL_ROUNDS,
        )
    return result


async def chat(request: ChatRequest) -> ChatResponse:
    user_id = request.user_id.strip()
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")

    message = request.message.strip()
    if not message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "message must not be empty")

    document_id = (request.document_id or "").strip() or None
    max_tokens = request.max_tokens if request.max_tokens is not None else _default_max_tokens()
    chat_limiter.consume(user_id)

    async with session_store.lock(user_id):
        if request.reset_session:
            session_store.clear(user_id)

        history = session_store.get_history(user_id)
        payload_messages = _build_chat_messages(history, message, document_id)
        result = await _run_tool_loop(
            payload_messages,
            ChatTools(user_id),
            temperature=request.temperature,
            max_tokens=max_tokens,
        )
        answer = result.content.strip()
        if not answer:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "LLM returned an empty answer",
            )

        session_store.set_history(
            user_id,
            [
                *history,
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ],
        )
        return ChatResponse(
            content=answer,
            model=result.model,
            user_id=user_id,
            usage=_usage_from_result(result),
        )


async def clear_session(user_id: str) -> None:
    normalized = user_id.strip()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")
    async with session_store.lock(normalized):
        session_store.clear(normalized)
