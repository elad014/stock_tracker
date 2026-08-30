from datetime import date, timedelta
from types import SimpleNamespace
import unittest

from test_support import import_project_module

stock_service = import_project_module("services.stock_service", "common", "stock_manager/backend", model_stubs=True)
HTTPException = stock_service.HTTPException
QuoteData = stock_service.QuoteData
OHLCVBar = stock_service.OHLCVBar


class FakeTxDB:
    def __init__(self) -> None:
        self.conn = "conn"
        self.transaction_count = 0

    def transaction(self):
        outer = self
        class Tx:
            async def __aenter__(self):
                outer.transaction_count += 1
                return outer.conn
            async def __aexit__(self, exc_type, exc, tb):
                return False
        return Tx()


class StockManagerServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.quote = QuoteData(
            symbol="AAPL",
            name="Apple",
            close=200.0,
            change=1.5,
            percent_change=0.75,
            previous_close=198.5,
            open=199.0,
            high=202.0,
            low=197.0,
            volume=123456,
            fifty_two_week_high=250.0,
            fifty_two_week_low=150.0,
        )

    def test_history_start_validates_supported_ranges(self) -> None:
        today = date(2026, 8, 26)
        self.assertEqual(stock_service._history_start_for_range("5D", today), today - timedelta(days=5))
        with self.assertRaises(HTTPException) as caught:
            stock_service._history_start_for_range("2Y", today)
        self.assertEqual(caught.exception.status_code, 400)

    def test_retention_cutoff_handles_leap_day(self) -> None:
        cutoff = stock_service._retention_cutoff(date(2024, 2, 29))
        self.assertEqual(cutoff.month, 2)
        self.assertEqual(cutoff.day, 28)

    def test_quote_to_response_preserves_quote_columns_including_open(self) -> None:
        row = {"stock_id": "s1", "symbol": "AAPL", "name": "Apple", "close": 200, "open": 199, "high": 202, "low": 197, "volume": 10}
        response = stock_service._quote_to_response(row)
        self.assertEqual(response.open, 199)
        self.assertEqual(response.high, 202)

    def test_with_today_close_adds_or_replaces_latest_point(self) -> None:
        quote = {"close": 200, "open": 198, "high": 201, "low": 197, "volume": 100}
        result = stock_service._with_today_close([], quote, None)
        self.assertEqual(result[0].close, 200.0)
        self.assertEqual(result[0].open, 198)

    async def test_get_stock_uses_latest_history_open(self) -> None:
        stock_service.quotes_db = SimpleNamespace(get_by_id=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL", "name": "Apple", "close": 200, "open": 1}))
        stock_service.history_db = SimpleNamespace(get_latest_bar=lambda stock_id: self._async({"open": 199}))

        response = await stock_service.get_stock("s1")

        self.assertEqual(response.open, 199)

    async def test_add_to_watchlist_maps_provider_not_found_to_404(self) -> None:
        class Provider:
            def get_quote(self, symbol):
                raise RuntimeError("symbol not found")
        stock_service._provider = lambda: Provider()
        stock_service._run_provider = lambda func, *args: self._async_error(func(*args))

        with self.assertRaises(HTTPException) as caught:
            await stock_service.add_to_watchlist("u1", "bad")

        self.assertEqual(caught.exception.status_code, 404)

    async def test_create_new_and_watch_persists_quote_history_and_watchlist(self) -> None:
        calls: list[tuple[str, tuple]] = []
        stock_service.db = FakeTxDB()
        stock_service._fetch_history = lambda symbol, start, end: self._async([OHLCVBar(date=date(2026, 8, 26), open=1, high=2, low=1, close=2, volume=100)])
        stock_service.quotes_db = SimpleNamespace(
            upsert_quote=lambda **kwargs: self._async_record(calls, "upsert", kwargs, {"stock_id": kwargs["stock_id"], "symbol": kwargs["symbol"], "name": kwargs["name"], "close": kwargs["close"], "open": kwargs["open"], "high": kwargs["high"], "low": kwargs["low"], "volume": kwargs["volume"]})
        )
        stock_service.history_db = SimpleNamespace(upsert_bars=lambda *args, **kwargs: self._async_record(calls, "history", args, None))
        stock_service.watchlist_db = SimpleNamespace(add_to_watchlist=lambda *args, **kwargs: self._async_record(calls, "watch", args, None))

        response = await stock_service._create_new_and_watch("u1", self.quote)

        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.open, 199.0)
        self.assertEqual([call[0] for call in calls], ["upsert", "history", "watch"])

    async def test_remove_from_watchlist_turns_delete_zero_into_404(self) -> None:
        stock_service.watchlist_db = SimpleNamespace(remove_from_watchlist=lambda *_args: self._async("DELETE 0"))
        with self.assertRaises(HTTPException) as caught:
            await stock_service.remove_from_watchlist("u1", "s1")
        self.assertEqual(caught.exception.status_code, 404)

    async def test_update_stock_summery_trims_blank_to_none(self) -> None:
        seen: list[tuple] = []
        async def update(stock_id, summary, stock_news_published_at=None):
            seen.append((stock_id, summary, stock_news_published_at))
            return {"stock_id": stock_id, "symbol": "AAPL", "stock_summery": summary, "stock_news_published_at": stock_news_published_at}
        stock_service.quotes_db = SimpleNamespace(update_stock_summery=update)

        response = await stock_service.update_stock_summery("s1", "   ")

        self.assertIsNone(response.stock_summery)
        self.assertEqual(seen[0][1], None)

    async def _async(self, value):
        return value

    async def _async_error(self, value):
        return value

    async def _async_record(self, calls, name, payload, result):
        calls.append((name, payload))
        return result


if __name__ == "__main__":
    unittest.main()
