"""LiteLLM-based client for OpenAI, Anthropic, Gemini, and other providers.

Used by llm-service (chat) and news-agent (summaries).

Environment variables:
- ``LLM_MODEL`` — default LiteLLM model id
  (e.g. ``gemini/gemini-2.5-flash``, ``openai/gpt-4o-mini``,
  ``anthropic/claude-3-5-sonnet-latest``)
- ``LLM_MAX_TOKENS`` — optional default completion cap
- ``LLM_SYSTEM_PROMPT`` — optional system message prepended to every call
- Provider keys (set the ones that match ``LLM_MODEL``):
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
from llm_provider_client.util import LLMCompletionResult

load_dotenv()

logger = logging.getLogger(__name__)


class LLMProviderClient:
    """LiteLLM vendor client used by llm-service and news-agent."""

    def __init__(self, model: str | None = None) -> None:
        configured = (model or os.getenv("LLM_MODEL", "")).strip()
        self.model: str = self._normalize_model(configured or DEFAULT_MODEL)

    @staticmethod
    def _normalize_model(model: str) -> str:
        normalized = model.strip()
        if not normalized:
            raise ValueError(
                "LLM model missing. Set LLM_MODEL in .env or pass model=..."
            )

        if normalized in DEPRECATED_GEMINI_MODELS:
            logger.warning(
                "Model %s is deprecated; using %s instead",
                normalized,
                DEFAULT_MODEL,
            )
            return DEFAULT_MODEL

        if "/" in normalized:
            return normalized

        if normalized.startswith("gemini"):
            candidate = f"gemini/{normalized}"
            if candidate in DEPRECATED_GEMINI_MODELS:
                logger.warning(
                    "Model %s is deprecated; using %s instead",
                    candidate,
                    DEFAULT_MODEL,
                )
                return DEFAULT_MODEL
            return candidate

        return normalized

    def _extract_content(self, response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "LLM vendor returned an unexpected response shape"
            ) from exc
        if content is None:
            raise RuntimeError("LLM vendor returned an empty response")
        return str(content)

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
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> LLMCompletionResult:
        if not messages:
            raise ValueError("messages must not be empty")

        resolved_model = (
            self._normalize_model(model) if model is not None else self.model
        )
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format

        try:
            response = await acompletion(**kwargs)
        except Exception as exc:
            logger.exception("LiteLLM chat completion failed")
            raise RuntimeError(f"LLM vendor request failed: {exc}") from exc

        prompt_tokens, completion_tokens, total_tokens = self._extract_usage(response)
        return LLMCompletionResult(
            content=self._extract_content(response),
            model=getattr(response, "model", None) or resolved_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
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
