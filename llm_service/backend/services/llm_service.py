import logging
import os
from typing import Optional

from fastapi import HTTPException, status

from llm_provider_client import LLMProviderClient
from models.llm import (
    ChatRequest,
    ChatResponse,
    ChatUsage,
)
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


def _system_prompt() -> Optional[str]:
    prompt = os.getenv("LLM_SYSTEM_PROMPT", "").strip()
    return prompt or None


def _provider() -> LLMProviderClient:
    return LLMProviderClient()


def _build_chat_messages(history: list[dict[str, str]], user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_prompt = _system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def _usage_from_result(result: object) -> Optional[ChatUsage]:
    prompt_tokens = getattr(result, "prompt_tokens", None)
    completion_tokens = getattr(result, "completion_tokens", None)
    total_tokens = getattr(result, "total_tokens", None)
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None
    return ChatUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


async def chat(request: ChatRequest) -> ChatResponse:
    user_id = request.user_id.strip()
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")

    message = request.message.strip()
    if not message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "message must not be empty")

    max_tokens = request.max_tokens if request.max_tokens is not None else _default_max_tokens()

    async with session_store.lock(user_id):
        if request.reset_session:
            session_store.clear(user_id)

        history = session_store.get_history(user_id)
        payload_messages = _build_chat_messages(history, message)

        try:
            result = await _provider().chat_completion(
                payload_messages,
                temperature=request.temperature,
                max_tokens=max_tokens,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
        except RuntimeError as exc:
            logger.exception("Chat completion failed for user %s", user_id)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

        session_store.set_history(
            user_id,
            [
                *history,
                {"role": "user", "content": message},
                {"role": "assistant", "content": result.content},
            ],
        )

        return ChatResponse(
            content=result.content,
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
