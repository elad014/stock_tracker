from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from conftest import load_backend_module
from llm_provider_client.util import LLMCompletionResult, LLMToolCall


chat_service = load_backend_module("chat_agent", "services.chat_service")
chat_models = load_backend_module("chat_agent", "models.chat")


class _SessionStore:
    def __init__(self):
        self.histories = {}
        self.cleared = []

    @asynccontextmanager
    async def lock(self, _user_id):
        yield

    def clear(self, user_id):
        self.cleared.append(user_id)
        self.histories.pop(user_id, None)

    def get_history(self, user_id):
        return list(self.histories.get(user_id, []))

    def set_history(self, user_id, messages):
        self.histories[user_id] = list(messages)


class _Limiter:
    def __init__(self):
        self.users = []

    def consume(self, user_id):
        self.users.append(user_id)


def test_system_prompt_includes_document_context(monkeypatch):
    monkeypatch.setenv("LLM_SYSTEM_PROMPT", "Extra instruction.")

    prompt = chat_service._system_prompt("reports/aapl.pdf")

    assert "Extra instruction." in prompt
    assert "The user is currently viewing document: reports/aapl.pdf." in prompt


def test_build_chat_messages_adds_system_history_and_guarded_user_message():
    history = [{"role": "assistant", "content": "previous answer"}]

    messages = chat_service._build_chat_messages(history, "What is AAPL?", "doc.pdf")

    assert messages[0]["role"] == "system"
    assert messages[1] == history[0]
    assert messages[-1]["role"] == "user"
    assert "What is AAPL?" in messages[-1]["content"]


def test_default_max_tokens_accepts_empty_or_positive_value(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert chat_service._default_max_tokens() is None

    monkeypatch.setenv("LLM_MAX_TOKENS", "123")
    assert chat_service._default_max_tokens() == 123


@pytest.mark.parametrize(
    "raw",
    ["0", "-1", "abc"],
    ids=["zero", "negative", "not a number"],
)
def test_default_max_tokens_rejects_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("LLM_MAX_TOKENS", raw)

    with pytest.raises(HTTPException) as exc_info:
        chat_service._default_max_tokens()

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_complete_maps_provider_runtime_error_to_502(monkeypatch):
    class Provider:
        async def chat_completion(self, *_args, **_kwargs):
            raise RuntimeError("vendor failed")

    monkeypatch.setattr(chat_service, "_provider", lambda: Provider())

    with pytest.raises(HTTPException) as exc_info:
        await chat_service._complete(
            [{"role": "user", "content": "hello"}],
            temperature=None,
            max_tokens=None,
            with_tools=False,
        )

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_run_tool_loop_executes_tool_call_then_finishes(monkeypatch):
    calls = []
    results = [
        LLMCompletionResult(
            content="",
            model="test-model",
            tool_calls=[
                LLMToolCall(
                    id="call-1",
                    name="get_stock_price",
                    arguments='{"symbol": "AAPL"}',
                )
            ],
        ),
        LLMCompletionResult(content="final answer", model="test-model"),
    ]

    async def complete(messages, *, temperature, max_tokens, with_tools):
        calls.append((list(messages), with_tools))
        return results.pop(0)

    class Tools:
        async def execute(self, name, arguments):
            assert name == "get_stock_price"
            assert arguments == '{"symbol": "AAPL"}'
            return "Price: 200"

    monkeypatch.setattr(chat_service, "_complete", complete)

    messages = [{"role": "user", "content": "price?"}]
    result = await chat_service._run_tool_loop(
        messages,
        Tools(),
        temperature=None,
        max_tokens=None,
    )

    assert result.content == "final answer"
    assert calls[0][1] is True
    assert calls[1][1] is True
    assert messages[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "Price: 200",
    }


@pytest.mark.asyncio
async def test_chat_rejects_blank_user_id():
    with pytest.raises(HTTPException) as exc_info:
        await chat_service.chat(
            chat_models.ChatRequest(user_id=" ", message="hello"),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_chat_rejects_blank_message():
    with pytest.raises(HTTPException) as exc_info:
        await chat_service.chat(
            chat_models.ChatRequest(user_id="user-1", message=" "),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_chat_stores_history_and_usage(monkeypatch):
    session_store = _SessionStore()
    limiter = _Limiter()

    async def run_tool_loop(_messages, _tools, *, temperature, max_tokens):
        assert temperature == 0.2
        assert max_tokens is None
        return LLMCompletionResult(
            content=" answer ",
            model="test-model",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )

    monkeypatch.setattr(chat_service, "session_store", session_store)
    monkeypatch.setattr(chat_service, "chat_limiter", limiter)
    monkeypatch.setattr(chat_service, "_run_tool_loop", run_tool_loop)

    result = await chat_service.chat(
        chat_models.ChatRequest(
            user_id=" user-1 ",
            message=" hello ",
            temperature=0.2,
        ),
    )

    assert result.content == "answer"
    assert result.model == "test-model"
    assert result.user_id == "user-1"
    assert result.usage.total_tokens == 3
    assert limiter.users == ["user-1"]
    assert session_store.histories["user-1"][-2:] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "answer"},
    ]


@pytest.mark.asyncio
async def test_chat_rejects_empty_llm_answer(monkeypatch):
    async def run_tool_loop(*_args, **_kwargs):
        return LLMCompletionResult(content=" ", model="test-model")

    monkeypatch.setattr(chat_service, "session_store", _SessionStore())
    monkeypatch.setattr(chat_service, "chat_limiter", _Limiter())
    monkeypatch.setattr(chat_service, "_run_tool_loop", run_tool_loop)

    with pytest.raises(HTTPException) as exc_info:
        await chat_service.chat(chat_models.ChatRequest(user_id="user-1", message="hello"))

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_clear_session_normalizes_and_clears(monkeypatch):
    session_store = _SessionStore()
    session_store.histories["user-1"] = [{"role": "user", "content": "hello"}]
    monkeypatch.setattr(chat_service, "session_store", session_store)

    await chat_service.clear_session(" user-1 ")

    assert session_store.cleared == ["user-1"]
    assert "user-1" not in session_store.histories
