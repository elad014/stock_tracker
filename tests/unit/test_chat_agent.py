from types import SimpleNamespace
import unittest

from test_support import import_project_module

chat_tools = import_project_module("services.chat_tools", "common", "chat_agent/backend", model_stubs=True)
HTTPException = chat_tools.HTTPException
chat_service = import_project_module("services.chat_service", "common", "chat_agent/backend", model_stubs=True)
session_store_module = import_project_module("services.session_store", "chat_agent/backend")
llm_util = import_project_module("llm_provider_client.util", "common")


class ChatToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_format_quote_includes_major_quote_fields_and_summary(self) -> None:
        text = chat_tools._format_quote({"symbol": "aapl", "name": "Apple", "close": 200, "open": 199, "volume": 100, "stock_summery": "News summary"})
        self.assertIn("Apple (AAPL)", text)
        self.assertIn("Open: 199", text)
        self.assertIn("Summary: News summary", text)

    async def test_format_history_computes_window_change_and_skips_bad_bars(self) -> None:
        text = chat_tools._format_history("AAPL", "5D", [{"date": "2026-08-25", "close": 100}, {"date": "2026-08-26", "close": "110"}, {"date": "bad"}])
        self.assertIn("Window change: 10.00%", text)
        self.assertIn("Recent daily closes", text)

    async def test_news_evidence_preserves_matching_sentence_when_clipping(self) -> None:
        body = "start " + ("filler " * 500) + "AAPL reported record revenue. " + ("tail " * 500)
        payload = {"summary": "analysis", "articles": [{"title": "Title", "text": body, "matching_sentences": ["AAPL reported record revenue."], "article_id": "a1"}]}
        text = chat_tools._format_news_evidence(payload, "AAPL")
        self.assertIn("NEWS AGENT ANSWER", text)
        self.assertIn("AAPL reported record revenue", text)
        self.assertIn("[truncated]", text)

    async def test_execute_rejects_invalid_json_and_unknown_tools(self) -> None:
        tools = chat_tools.ChatTools("u1")
        self.assertEqual(await tools.execute("get_stock_price", "{"), "Invalid tool arguments.")
        self.assertEqual(await tools.execute("missing", "{}"), "Unknown tool: missing")

    async def test_get_stock_price_handles_not_found_and_formats_payload(self) -> None:
        async def by_symbol(symbol):
            return {"symbol": symbol, "name": "Apple", "close": 200}
        chat_tools.stock_manager = SimpleNamespace(get_stock_by_symbol=by_symbol)

        text = await chat_tools.ChatTools("u1").get_stock_price(" aapl ")

        self.assertIn("Apple (AAPL)", text)
        self.assertIn("Price: 200", text)

    async def test_get_stock_history_normalizes_bad_range(self) -> None:
        async def by_symbol(symbol):
            return {"stock_id": "s1", "symbol": symbol}
        async def history(stock_id, window):
            self.assertEqual(window, "1M")
            return [{"date": "2026-08-26", "close": 10}]
        chat_tools.stock_manager = SimpleNamespace(get_stock_by_symbol=by_symbol, get_stock_history=history)

        text = await chat_tools.ChatTools("u1").get_stock_history("aapl", "bad")

        self.assertIn("History for AAPL (1M)", text)

    async def test_tool_methods_return_tool_error_instead_of_raising(self) -> None:
        async def fail(*_args, **_kwargs):
            raise HTTPException(403, "forbidden")
        chat_tools.news_agent = SimpleNamespace(search_and_summarize=fail)

        text = await chat_tools.ChatTools("u1").get_stock_news_summary("AAPL", "why")

        self.assertEqual(text, "Tool error (403): forbidden")


class SessionStoreTests(unittest.TestCase):
    def test_session_store_trims_history_and_returns_copies(self) -> None:
        store = session_store_module.SessionStore(max_messages=2)
        store.set_history("u1", [{"role": "user", "content": "1"}, {"role": "assistant", "content": "2"}, {"role": "user", "content": "3"}])
        history = store.get_history("u1")
        history.append({"role": "assistant", "content": "mutated"})
        self.assertEqual([item["content"] for item in store.get_history("u1")], ["2", "3"])


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        chat_service.chat_limiter = SimpleNamespace(consumed=[], consume=lambda key: chat_service.chat_limiter.consumed.append(key))
        chat_service.session_store = session_store_module.SessionStore(max_messages=20)

    async def test_chat_rejects_empty_user_and_message(self) -> None:
        with self.assertRaises(chat_service.HTTPException):
            await chat_service.chat(SimpleNamespace(user_id=" ", message="hi", document_id=None, max_tokens=None, temperature=None, reset_session=False))
        with self.assertRaises(chat_service.HTTPException):
            await chat_service.chat(SimpleNamespace(user_id="u1", message=" ", document_id=None, max_tokens=None, temperature=None, reset_session=False))

    async def test_chat_runs_tool_loop_and_stores_history(self) -> None:
        calls = [
            llm_util.LLMCompletionResult(content="", model="m1", tool_calls=[llm_util.LLMToolCall(id="c1", name="get_stock_price", arguments='{"symbol":"AAPL"}')]),
            llm_util.LLMCompletionResult(content="Final answer", model="m2", prompt_tokens=1, completion_tokens=2, total_tokens=3),
        ]
        async def complete(messages, temperature=None, max_tokens=None, with_tools=True):
            return calls.pop(0)
        chat_service._complete = complete
        class Tools:
            def __init__(self, user_id):
                self.user_id = user_id
            async def execute(self, name, arguments):
                return "Price: 200"
        chat_service.ChatTools = Tools

        response = await chat_service.chat(SimpleNamespace(user_id=" u1 ", message=" hi ", document_id=None, max_tokens=None, temperature=None, reset_session=False))

        self.assertEqual(response.content, "Final answer")
        self.assertEqual(response.usage.total_tokens, 3)
        self.assertEqual(chat_service.session_store.get_history("u1")[-1]["content"], "Final answer")

    async def test_chat_rejects_empty_llm_answer(self) -> None:
        async def complete(*_args, **_kwargs):
            return llm_util.LLMCompletionResult(content="  ", model="m")
        chat_service._complete = complete
        chat_service.ChatTools = lambda user_id: SimpleNamespace(execute=lambda *_args: None)

        with self.assertRaises(chat_service.HTTPException) as caught:
            await chat_service.chat(SimpleNamespace(user_id="u1", message="hi", document_id=None, max_tokens=None, temperature=None, reset_session=False))
        self.assertEqual(caught.exception.status_code, 502)
    async def test_repeated_tool_calls_stop_after_configured_round_limit(self) -> None:
        """Stop repeated LLM tool-call loops at the configured round limit."""
        original_limit = chat_service.CHAT_MAX_TOOL_ROUNDS
        chat_service.CHAT_MAX_TOOL_ROUNDS = 2
        calls: list[bool] = []

        async def complete(messages, temperature=None, max_tokens=None, with_tools=True):
            calls.append(with_tools)
            if with_tools:
                return llm_util.LLMCompletionResult(
                    content="",
                    model="m-tool",
                    tool_calls=[llm_util.LLMToolCall(id=f"c{len(calls)}", name="get_stock_price", arguments='{"symbol":"AAPL"}')],
                )
            return llm_util.LLMCompletionResult(content="Final answer", model="m-final")

        class Tools:
            def __init__(self, user_id):
                self.user_id = user_id

            async def execute(self, name, arguments):
                return "Price: 200"

        chat_service._complete = complete
        chat_service.ChatTools = Tools
        try:
            response = await chat_service.chat(
                SimpleNamespace(user_id="u1", message="price", document_id=None, max_tokens=None, temperature=None, reset_session=False)
            )
        finally:
            chat_service.CHAT_MAX_TOOL_ROUNDS = original_limit

        self.assertEqual(response.content, "Final answer")
        self.assertEqual(calls, [True, True, False])

    async def test_clear_session_validates_and_removes_history(self) -> None:
        chat_service.session_store.set_history("u1", [{"role": "user", "content": "hi"}])
        await chat_service.clear_session("u1")
        self.assertEqual(chat_service.session_store.get_history("u1"), [])


if __name__ == "__main__":
    unittest.main()

