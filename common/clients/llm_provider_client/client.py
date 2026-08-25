"""LiteLLM-based client for OpenAI, Anthropic, Gemini, and other providers.

Used by chat-agent (orchestrator) and news-agent (summaries).

Environment variables:
- ``LLM_MODELS`` — comma-separated LiteLLM model ids, tried in order until one
  succeeds (e.g. ``gemini/gemini-2.5-flash,gemini/gemini-2.5-flash-lite``)
- ``LLM_MODEL`` — optional legacy single model if ``LLM_MODELS`` is empty
- ``LLM_MAX_TOKENS`` — optional default completion cap
- ``LLM_SYSTEM_PROMPT`` — optional system message prepended to every call
- Provider keys (set the ones that match the models):
  ``GEMINI_API_KEY``, ``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from litellm import acompletion

from constant import DEFAULT_MODEL, DEPRECATED_GEMINI_MODELS, NEWS_SUMMARIZE_SYSTEM_PROMPT
from llm_guard import guarded_user_message
from .util import (
    LLMCompletionResult,
    LLMToolCall,
    is_model_unavailable,
    split_model_ids,
)

load_dotenv()

logger = logging.getLogger(__name__)


class LLMProviderClient:
    """LiteLLM vendor client used by chat-agent and news-agent."""

    def __init__(self, model: str | None = None) -> None:
        env_models: list[str] = self._models_from_env()
        if model is not None:
            preferred: str = self._normalize_model(model)
            self.models: list[str] = [preferred] + [
                item for item in env_models if item != preferred
            ]
        else:
            self.models = env_models
        self.model: str = self.models[0]

    @classmethod
    def _models_from_env(cls) -> list[str]:
        listed: list[str] = split_model_ids(os.getenv("LLM_MODELS", ""))
        if listed:
            unique: list[str] = []
            for item in listed:
                normalized: str = cls._normalize_model(item)
                if normalized not in unique:
                    unique.append(normalized)
            return unique
        configured: str = os.getenv("LLM_MODEL", "").strip()
        return [cls._normalize_model(configured or DEFAULT_MODEL)]

    @staticmethod
    def _normalize_model(model: str) -> str:
        normalized = model.strip()
        if not normalized:
            raise ValueError(
                "LLM model missing. Set LLM_MODELS or LLM_MODEL in .env or pass model=..."
            )

        if "/" not in normalized and normalized.startswith("gemini"):
            normalized = f"gemini/{normalized}"

        if normalized in DEPRECATED_GEMINI_MODELS:
            logger.warning(
                "Model %s is deprecated; still trying it because it is listed",
                normalized,
            )
        return normalized

    def _extract_content(self, response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "LLM vendor returned an unexpected response shape"
            ) from exc
        if content is None:
            return ""
        return str(content)

    def _extract_tool_calls(self, response: Any) -> list[LLMToolCall]:
        try:
            raw_calls = response.choices[0].message.tool_calls
        except (AttributeError, IndexError, KeyError, TypeError):
            return []
        if not raw_calls:
            return []
        parsed: list[LLMToolCall] = []
        for item in raw_calls:
            if isinstance(item, dict):
                function = item.get("function") or {}
                call_id = str(item.get("id") or "")
                name = str(function.get("name") or "")
                arguments = str(function.get("arguments") or "{}")
            else:
                function = getattr(item, "function", None)
                call_id = str(getattr(item, "id", "") or "")
                name = str(getattr(function, "name", "") or "") if function else ""
                arguments = (
                    str(getattr(function, "arguments", "") or "{}") if function else "{}"
                )
            if not name:
                continue
            parsed.append(LLMToolCall(id=call_id, name=name, arguments=arguments))
        return parsed

    def _extract_usage(
        self,
        response: Any,
    ) -> tuple[int | None, int | None, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None, None, None
        return (
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            getattr(usage, "total_tokens", None),
        )

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, Any]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
    ) -> LLMCompletionResult:
        if not messages:
            raise ValueError("messages must not be empty")

        if model is not None:
            preferred: str = self._normalize_model(model)
            candidates: list[str] = [preferred] + [
                item for item in self.models if item != preferred
            ]
        else:
            candidates = list(self.models)

        kwargs: dict[str, Any] = {
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        response: Any = None
        used_model: str = candidates[0]
        failures: list[str] = []
        for index, candidate in enumerate(candidates):
            try:
                kwargs["model"] = candidate
                response = await acompletion(**kwargs)
                used_model = candidate
                if failures:
                    logger.warning(
                        "LLM fallback succeeded. Order: failed [%s] then %s",
                        " -> ".join(failures),
                        candidate,
                    )
                break
            except Exception as exc:
                failures.append(f"{candidate} ({type(exc).__name__}: {exc})")
                has_next: bool = index < len(candidates) - 1
                if has_next:
                    reason: str = (
                        "unavailable" if is_model_unavailable(exc) else "failed"
                    )
                    logger.warning(
                        "LLM model %s; trying next. Order so far: %s",
                        reason,
                        " -> ".join(failures),
                    )
                    continue
                logger.error(
                    "All LLM models failed. Order tried: %s",
                    " -> ".join(failures),
                )
                raise RuntimeError(
                    "LLM vendor request failed. Order tried: "
                    + " -> ".join(failures)
                ) from exc

        prompt_tokens, completion_tokens, total_tokens = self._extract_usage(response)
        tool_calls = self._extract_tool_calls(response)
        content = self._extract_content(response)
        if not content and not tool_calls:
            raise RuntimeError("LLM vendor returned an empty response")
        return LLMCompletionResult(
            content=content,
            model=getattr(response, "model", None) or used_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _format_quote_context(
        close: Optional[float],
        change: Optional[float],
        percent_change: Optional[float],
    ) -> str:
        parts: list[str] = []
        if close is not None:
            parts.append(f"close={close}")
        if change is not None:
            parts.append(f"change={change}")
        if percent_change is not None:
            parts.append(f"percent_change={percent_change}")
        if not parts:
            return ""
        return "Current quote: " + ", ".join(parts) + ".\n"

    @staticmethod
    def _default_max_tokens() -> Optional[int]:
        raw = os.getenv("LLM_MAX_TOKENS", "").strip()
        if not raw:
            return None
        value = int(raw)
        if value <= 0:
            raise ValueError("LLM_MAX_TOKENS must be a positive integer")
        return value

    async def summarize(
        self,
        text: str,
        *,
        symbol: Optional[str] = None,
        close: Optional[float] = None,
        change: Optional[float] = None,
        percent_change: Optional[float] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMCompletionResult:
        """Summarize news text with a short outlook line."""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("text must not be empty")

        ticker = symbol.strip().upper() if symbol else None
        quote_block = self._format_quote_context(close, change, percent_change)
        subject = f" about {ticker}" if ticker else ""
        user_message = guarded_user_message(
            (
                f"Summarize the following financial news{subject}.\n"
                f"{quote_block}"
                "Respond with a 2-4 sentence summary and a final line "
                "exactly in the form: Outlook: UP|DOWN|NEUTRAL"
            ),
            ("NEWS_SOURCE_TEXT", cleaned),
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": NEWS_SUMMARIZE_SYSTEM_PROMPT},
        ]
        extra_system = os.getenv("LLM_SYSTEM_PROMPT", "").strip()
        if extra_system:
            messages.append({"role": "system", "content": extra_system})
        messages.append({"role": "user", "content": user_message})

        resolved_max = (
            max_tokens if max_tokens is not None else self._default_max_tokens()
        )
        return await self.chat_completion(
            messages,
            temperature=temperature,
            max_tokens=resolved_max,
        )
