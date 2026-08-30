from types import SimpleNamespace
import unittest

from test_support import import_project_module

watchlist_service = import_project_module("services.watchlist_service", "common", "ui_service/backend", model_stubs=True)
HTTPException = watchlist_service.HTTPException
stocks_service = import_project_module("services.stocks_service", "common", "ui_service/backend", model_stubs=True)
chat_service = import_project_module("services.chat_service", "common", "ui_service/backend", model_stubs=True)


class FakeStockManager:
    def __init__(self) -> None:
        self.watchlist = []
        self.existing_by_symbol = {}
        self.on_watchlist = False
        self.added: list[tuple[str, str]] = []
        self.removed: list[tuple[str, str]] = []
        self.history = []

    async def list_watchlist(self, user_id):
        return self.watchlist

    async def get_stock_by_symbol(self, symbol):
        return self.existing_by_symbol.get(symbol)

    async def is_on_watchlist(self, user_id, stock_id):
        return self.on_watchlist

    async def add_to_watchlist(self, user_id, symbol):
        self.added.append((user_id, symbol))
        return {"stock_id": "s1", "symbol": symbol.upper(), "close": 10, "change": 1}

    async def remove_from_watchlist(self, user_id, stock_id):
        self.removed.append((user_id, stock_id))
        return {"message": "ok"}

    async def get_stock(self, stock_id):
        return {"stock_id": stock_id, "symbol": "AAPL", "name": "Apple", "close": 200, "open": 198, "stock_summery": "summary"}

    async def get_stock_history(self, stock_id, range_key):
        return self.history

    def quote_to_watchlist_stock(self, row):
        return {"id": row.get("stock_id"), "symbol": row.get("symbol"), "price": row.get("close"), "change": row.get("change"), "stock_summery": row.get("stock_summery"), "stock_news_published_at": row.get("stock_news_published_at")}


class UiServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_watchlist_list_maps_stock_manager_quotes(self) -> None:
        fake = FakeStockManager()
        fake.watchlist = [{"stock_id": "s1", "symbol": "AAPL", "close": 200, "change": 3}]
        watchlist_service.stock_manager = fake

        result = await watchlist_service.list_watchlist({"id": "u1"})

        self.assertEqual(result[0].id, "s1")
        self.assertEqual(result[0].price, 200)

    async def test_watchlist_add_rejects_existing_stock_for_user(self) -> None:
        fake = FakeStockManager()
        fake.existing_by_symbol["AAPL"] = {"stock_id": "s1"}
        fake.on_watchlist = True
        watchlist_service.stock_manager = fake

        with self.assertRaises(HTTPException) as caught:
            await watchlist_service.add_watchlist_stock(SimpleNamespace(name="AAPL"), {"id": "u1"})

        self.assertEqual(caught.exception.status_code, 409)

    async def test_watchlist_add_assigns_new_stock(self) -> None:
        fake = FakeStockManager()
        watchlist_service.stock_manager = fake

        result = await watchlist_service.add_watchlist_stock(SimpleNamespace(name="msft"), {"id": "u1"})

        self.assertEqual(result.symbol, "MSFT")
        self.assertEqual(fake.added, [("u1", "msft")])

    async def test_stock_details_requires_watchlist_membership(self) -> None:
        fake = FakeStockManager()
        fake.on_watchlist = False
        stocks_service.stock_manager = fake

        with self.assertRaises(HTTPException) as caught:
            await stocks_service.get_stock_details("s1", "u1")

        self.assertEqual(caught.exception.status_code, 403)

    async def test_stock_details_maps_quote_payload(self) -> None:
        fake = FakeStockManager()
        fake.on_watchlist = True
        stocks_service.stock_manager = fake

        result = await stocks_service.get_stock_details("s1", "u1")

        self.assertEqual(result.id, "s1")
        self.assertEqual(result.open, 198)
        self.assertEqual(result.stock_summery, "summary")

    async def test_stock_history_maps_rows_after_authorization(self) -> None:
        fake = FakeStockManager()
        fake.on_watchlist = True
        fake.history = [{"date": "2026-08-26", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}]
        stocks_service.stock_manager = fake

        result = await stocks_service.get_stock_history("s1", "u1", "5D")

        self.assertEqual(result[0].date, "2026-08-26")

    async def test_stock_articles_and_summary_use_news_agent(self) -> None:
        fake = FakeStockManager()
        fake.on_watchlist = True
        stocks_service.stock_manager = fake
        stocks_service.news_agent = SimpleNamespace(
            list_stock_articles=lambda stock_id, limit: self._async([{"article_id": "a1", "url": "https://x", "title": "Title", "ai_summary_status": "ready"}]),
            summarize_article=lambda article_id: self._async({"article_id": article_id, "url": "https://x", "title": "Title", "status": "ready", "ai_summary": "ok"}),
        )

        articles = await stocks_service.list_stock_articles("s1", "u1")
        summary = await stocks_service.summarize_stock_article("s1", "a1", "u1")

        self.assertEqual(articles[0].article_id, "a1")
        self.assertEqual(summary.ai_summary, "ok")

    async def test_chat_service_rejects_invalid_or_empty_agent_payloads(self) -> None:
        async def bad_chat(*_args, **_kwargs):
            return {"content": "   "}
        chat_service.chat_agent = SimpleNamespace(chat=bad_chat)

        with self.assertRaises(HTTPException) as caught:
            await chat_service.send_chat({"id": "u1"}, SimpleNamespace(message="hi", document_id=None, reset_session=False))

        self.assertEqual(caught.exception.status_code, 502)

    async def test_chat_service_returns_trimmed_content(self) -> None:
        async def good_chat(*_args, **_kwargs):
            return {"content": "  hello  ", "model": "fake"}
        chat_service.chat_agent = SimpleNamespace(chat=good_chat)

        response = await chat_service.send_chat({"id": "u1"}, SimpleNamespace(message="hi", document_id=None, reset_session=True))

        self.assertEqual(response.content, "hello")
        self.assertEqual(response.model, "fake")

    async def _async(self, value):
        return value


if __name__ == "__main__":
    unittest.main()
