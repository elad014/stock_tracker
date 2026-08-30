from types import SimpleNamespace
import unittest

from test_support import import_project_module

news_service = import_project_module("services.news_service", "common", "news_agent/backend", model_stubs=True)
HTTPException = news_service.HTTPException


class NewsServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_query_terms_remove_stop_words_add_variants_and_fixes(self) -> None:
        terms = news_service._query_terms("What did Invidia companies report?", "NVDA")
        self.assertIn("nvidia", terms)
        self.assertIn("company", terms)
        self.assertIn("nvda", terms)
        self.assertNotIn("what", terms)

    def test_matching_sentences_ranks_ticker_specific_sentence_first(self) -> None:
        text = "AMD announced results. NVDA reported record revenue. For NVDA, options sweeps increased."
        terms = ["reported", "options", "nvda"]

        matches = news_service._matching_sentences(text, terms, ticker="NVDA")

        self.assertTrue(matches[0].startswith("NVDA reported"))
        self.assertIn("options sweeps", matches[0])

    async def test_get_stock_news_normalizes_symbol_and_limits_items(self) -> None:
        item = SimpleNamespace(title="Title", url="https://x", published_at=None, source="Source", summary="Summary")
        provider = SimpleNamespace(get_news_for_day=lambda symbol, day: [item, item])
        news_service._news_provider = lambda: provider
        news_service._run_provider = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))

        result = await news_service.get_stock_news(" aapl ", outputsize=1)

        self.assertEqual(result.symbol, "AAPL")
        self.assertEqual(result.count, 1)

    async def test_get_stock_news_maps_provider_not_found_to_404(self) -> None:
        def fail(*_args):
            raise RuntimeError("symbol not found")
        news_service._news_provider = lambda: SimpleNamespace(get_news_for_day=fail)
        news_service._run_provider = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))

        with self.assertRaises(HTTPException) as caught:
            await news_service.get_stock_news("BAD")

        self.assertEqual(caught.exception.status_code, 404)

    async def test_search_and_summarize_returns_empty_when_no_articles(self) -> None:
        news_service.articles_db = SimpleNamespace(list_recent_articles_by_symbol=lambda *_args, **_kwargs: self._async([]))

        result = await news_service.search_and_summarize("AAPL", "earnings")

        self.assertEqual(result.summary, "No recent news found for this symbol.")
        self.assertEqual(result.articles, [])

    async def test_search_and_summarize_ranks_articles_and_calls_llm_with_guarded_blocks(self) -> None:
        rows = [
            {"article_id": "a1", "symbol": "AAPL", "title": "Weak", "text": "AAPL mentioned briefly.", "url": "u1"},
            {"article_id": "a2", "symbol": "AAPL", "title": "Strong", "text": "AAPL earnings beat expectations. The stock rose after earnings.", "url": "u2"},
        ]
        news_service.articles_db = SimpleNamespace(list_recent_articles_by_symbol=lambda *_args, **_kwargs: self._async(rows))
        captured = {}
        class LLM:
            def _default_max_tokens(self):
                return 123
            async def chat_completion(self, messages, max_tokens=None):
                captured["messages"] = messages
                captured["max_tokens"] = max_tokens
                return SimpleNamespace(content="LLM analysis")
        news_service._llm_client = lambda: LLM()

        result = await news_service.search_and_summarize("AAPL", "earnings beat")

        self.assertEqual(result.summary, "LLM analysis")
        self.assertEqual(result.articles[0].article_id, "a2")
        self.assertIn("<<<UNTRUSTED_DATA>>>", captured["messages"][1]["content"])

    async def test_search_and_summarize_falls_back_when_llm_fails(self) -> None:
        rows = [{"article_id": "a1", "symbol": "AAPL", "title": "News", "text": "AAPL revenue increased.", "url": "u"}]
        news_service.articles_db = SimpleNamespace(list_recent_articles_by_symbol=lambda *_args, **_kwargs: self._async(rows))
        class LLM:
            def _default_max_tokens(self):
                return None
            async def chat_completion(self, *_args, **_kwargs):
                raise RuntimeError("vendor down")
        news_service._llm_client = lambda: LLM()

        result = await news_service.search_and_summarize("AAPL", "revenue")

        self.assertIn("unavailable", result.summary)
        self.assertEqual(len(result.articles), 1)

    async def _async(self, value):
        return value


if __name__ == "__main__":
    unittest.main()
