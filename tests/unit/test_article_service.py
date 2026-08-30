from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from test_support import import_project_module

article_service = import_project_module("services.article_service", "common", "news_agent/backend", model_stubs=True)
HTTPException = article_service.HTTPException
NewsItem = article_service.NewsItem
ORIGINAL_UPSERT_STOCK_ARTICLES = article_service.upsert_stock_articles


class FakeArticlesDb:
    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.links: list[tuple[str, str]] = []
        self.text_updates: list[tuple[str, str | None]] = []
        self.summary_updates: list[tuple[str, dict]] = []
        self.articles: dict[str, dict] = {}
        self.claimed: dict | None = None
        self.linked_stocks = []

    async def upsert_article(self, **kwargs):
        self.upserts.append(kwargs)
        article = {"article_id": f"a{len(self.upserts)}", "title": kwargs["title"], "url": kwargs["url"], "text": kwargs.get("text"), "provider_summary": kwargs.get("provider_summary"), "ai_summary_status": "none"}
        return article, True

    async def link_article_to_stock(self, stock_id, article_id):
        self.links.append((stock_id, article_id))
        return True

    async def set_article_text(self, article_id, text):
        self.text_updates.append((article_id, text))
        article = dict(self.articles.get(article_id, {"article_id": article_id, "title": "Title", "url": "https://x"}))
        article["text"] = text
        self.articles[article_id] = article
        return article

    async def get_by_id(self, article_id):
        return self.articles.get(article_id)

    async def claim_for_summary(self, article_id):
        return self.claimed

    async def list_linked_stocks(self, article_id):
        return self.linked_stocks

    async def set_summary(self, article_id, **kwargs):
        self.summary_updates.append((article_id, kwargs))
        article = dict(self.articles.get(article_id, self.claimed or {"article_id": article_id, "title": "Title", "url": "https://x"}))
        article.update(kwargs)
        article["ai_summary_status"] = kwargs["ai_summary_status"]
        self.articles[article_id] = article
        return article

    async def list_articles_needing_extract(self, **_kwargs):
        return list(self.articles.values())

    async def list_by_stock(self, stock_id, limit=100):
        return list(self.articles.values())[:limit]

    async def delete_older_than(self, days):
        return "DELETE 2"

    async def delete_orphans_older_than(self, days):
        return "DELETE 1"


class ArticleServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = FakeArticlesDb()
        article_service.articles_db = self.db
        article_service.upsert_stock_articles = ORIGINAL_UPSERT_STOCK_ARTICLES
        article_service.article_summarize_limiter = SimpleNamespace(assert_allowed=lambda key: None, record=lambda key: None)

    def test_to_article_payload_skips_items_without_url(self) -> None:
        items = [
            NewsItem(title="A", url="https://a", published_at=datetime(2026, 8, 26, tzinfo=timezone.utc), source="S", summary="sum"),
            NewsItem(title="B", url=None, published_at=None, source=None, summary=None),
        ]
        payload = article_service.to_article_payload(items)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["provider"], "finnhub")
        self.assertIn("2026-08-26", payload[0]["published_at"])

    def test_placeholder_detection_flags_empty_blocked_title_and_blurb(self) -> None:
        self.assertTrue(article_service._is_placeholder_text({"text": ""}))
        self.assertTrue(article_service._is_placeholder_text({"title": "T", "text": "T"}))
        self.assertTrue(article_service._is_placeholder_text({"provider_summary": "short", "text": "short"}))
        self.assertFalse(article_service._is_placeholder_text({"text": "Real article body " * 20}))

    async def test_upsert_stock_articles_inserts_links_and_extracts_text(self) -> None:
        article_service._extractor = lambda: SimpleNamespace(extract=lambda url: "Extracted body " * 20)
        article_service._run_blocking = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))

        stored, new_count = await article_service.upsert_stock_articles("s1", [{"url": "https://a", "title": "A", "published_at": "2026-08-26T00:00:00Z"}])

        self.assertEqual(new_count, 1)
        self.assertEqual(self.db.links, [("s1", "a1")])
        self.assertTrue(stored[0]["text"].startswith("Extracted body"))

    async def test_retry_missing_article_bodies_counts_successful_extractions(self) -> None:
        self.db.articles["a1"] = {"article_id": "a1", "title": "T", "url": "https://a", "text": None}
        article_service._extractor = lambda: SimpleNamespace(extract=lambda url: "Extracted body " * 20)
        article_service._run_blocking = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))

        count = await article_service.retry_missing_article_bodies()

        self.assertEqual(count, 1)

    async def test_summarize_article_returns_existing_when_claim_is_busy(self) -> None:
        self.db.articles["a1"] = {"article_id": "a1", "title": "T", "url": "https://a", "ai_summary_status": "pending", "ai_summary": "old"}
        self.db.claimed = None

        result = await article_service.summarize_article("a1")

        self.assertEqual(result.status, "pending")
        self.assertEqual(result.ai_summary, "old")

    async def test_summarize_article_marks_cannot_extract_when_body_missing(self) -> None:
        self.db.articles["a1"] = {"article_id": "a1", "title": "T", "url": "https://a", "text": None, "ai_summary_status": "none"}
        self.db.claimed = dict(self.db.articles["a1"])
        article_service._extractor = lambda: SimpleNamespace(extract=lambda url: None)
        article_service._run_blocking = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))

        result = await article_service.summarize_article("a1")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.ai_summary, article_service.ARTICLE_CANNOT_EXTRACT_MESSAGE)

    async def test_summarize_article_calls_llm_and_stores_ready_summary(self) -> None:
        self.db.articles["a1"] = {"article_id": "a1", "title": "T", "url": "https://a", "text": "Real article body " * 20, "ai_summary_status": "none"}
        self.db.claimed = dict(self.db.articles["a1"])
        self.db.linked_stocks = [{"symbol": "AAPL", "name": "Apple"}]
        class LLM:
            async def summarize(self, source, symbol=None):
                self.source = source
                return SimpleNamespace(content="Summary", model="fake-model")
        article_service._llm_client = lambda: LLM()

        result = await article_service.summarize_article("a1")

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.ai_summary, "Summary")
        self.assertEqual(self.db.summary_updates[-1][1]["ai_summary_model"], "fake-model")

    async def test_summarize_article_records_failed_status_when_llm_errors(self) -> None:
        self.db.articles["a1"] = {"article_id": "a1", "title": "T", "url": "https://a", "text": "Real article body " * 20, "ai_summary_status": "none"}
        self.db.claimed = dict(self.db.articles["a1"])
        class LLM:
            async def summarize(self, *_args, **_kwargs):
                raise RuntimeError("Gemini down")
        article_service._llm_client = lambda: LLM()

        result = await article_service.summarize_article("a1")

        self.assertEqual(result.status, "failed")
        self.assertIn("Gemini down", result.ai_summary_error)

    async def test_sync_stock_articles_fetches_symbol_and_stores_payload(self) -> None:
        article_service._stock_manager_client = lambda: SimpleNamespace(get_stock=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL"}))
        article_service._news_provider = lambda: SimpleNamespace(get_news_for_day=lambda symbol: [NewsItem("A", "https://a", None, None, None)])
        article_service._run_blocking = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))
        article_service.upsert_stock_articles = lambda stock_id, payload: self._async(([{"article_id": "a1"}], 1))

        result = await article_service.sync_stock_articles("s1")

        self.assertEqual(result.symbol, "AAPL")
        self.assertEqual(result.stored, 1)
    async def test_repeated_news_sync_reuses_article_and_stock_link(self) -> None:
        """Do not count duplicate Finnhub articles as new on repeated sync."""
        seen_urls: dict[str, dict] = {}
        linked_pairs: set[tuple[str, str]] = set()

        async def upsert_article(**kwargs):
            inserted = kwargs["url"] not in seen_urls
            article = seen_urls.setdefault(
                kwargs["url"],
                {
                    "article_id": "article-1",
                    "title": kwargs["title"],
                    "url": kwargs["url"],
                    "text": "Existing article body " * 20,
                    "provider_summary": kwargs.get("provider_summary"),
                    "ai_summary_status": "none",
                },
            )
            return article, inserted

        async def link_article_to_stock(stock_id, article_id):
            pair = (stock_id, article_id)
            linked = pair not in linked_pairs
            linked_pairs.add(pair)
            return linked

        article_service.articles_db = SimpleNamespace(
            upsert_article=upsert_article,
            link_article_to_stock=link_article_to_stock,
        )

        payload = [{"url": "https://example.com/aapl", "title": "AAPL news", "provider": "finnhub"}]
        first, first_count = await article_service.upsert_stock_articles("s1", payload)
        second, second_count = await article_service.upsert_stock_articles("s1", payload)

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(first[0]["article_id"], second[0]["article_id"])
        self.assertEqual(len(seen_urls), 1)
        self.assertEqual(len(linked_pairs), 1)

    async def _async(self, value):
        return value


if __name__ == "__main__":
    unittest.main()


