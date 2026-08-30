from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest

from test_support import FakeDB, import_project_module

quotes_db = import_project_module("db_logics.quotes_db_logic", "common", "stock_manager/backend")
history_db = import_project_module("db_logics.history_db_logic", "common", "stock_manager/backend")
watchlist_db = import_project_module("db_logics.watchlist_db_logic", "common", "stock_manager/backend")
vectors_placeholder = None


class StockDbLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_quote_normalization_converts_types_and_preserves_open(self) -> None:
        row = {
            "stock_id": 123,
            "symbol": "AAPL",
            "name": "Apple",
            "close": "200.1",
            "change": "1.2",
            "percent_change": "0.6",
            "previous_close": "198.9",
            "open": "199.0",
            "high": "202",
            "low": "197",
            "volume": "123",
            "fifty_two_week_high": "250",
            "fifty_two_week_low": "150",
            "stock_summery": "summary",
            "stock_news_published_at": datetime(2026, 8, 26, tzinfo=timezone.utc),
        }
        normalized = quotes_db._normalize_quote(row)
        self.assertEqual(normalized["stock_id"], "123")
        self.assertEqual(normalized["open"], 199.0)
        self.assertEqual(normalized["volume"], 123)
        self.assertIn("2026-08-26", normalized["stock_news_published_at"])

    async def test_upsert_quote_populates_all_quote_columns_including_open(self) -> None:
        fake_db = FakeDB()
        fake_db.fetch_one_results.append({
            "stock_id": "s1",
            "symbol": "AAPL",
            "name": "Apple",
            "close": 200,
            "change": 1,
            "percent_change": 0.5,
            "previous_close": 198,
            "open": 199,
            "high": 202,
            "low": 197,
            "volume": 1000,
            "fifty_two_week_high": 250,
            "fifty_two_week_low": 150,
            "stock_summery": None,
            "stock_news_published_at": None,
        })
        quotes_db.db = fake_db

        result = await quotes_db.upsert_quote("s1", "aapl", "Apple", 200, 1, 0.5, previous_close=198, open=199, high=202, low=197, volume=1000, fifty_two_week_high=250, fifty_two_week_low=150)

        sql, params, _conn = fake_db.fetch_one_calls[0]
        self.assertIn("open", sql)
        self.assertIn("open = EXCLUDED.open", sql)
        self.assertEqual(params[7], 199)
        self.assertEqual(result["open"], 199.0)

    async def test_history_upsert_normalizes_symbol_and_rows(self) -> None:
        fake_db = FakeDB()
        history_db.db = fake_db
        bar = SimpleNamespace(date=date(2026, 8, 26), open=1, high=2, low=1, close=2, volume=10)

        await history_db.upsert_bars("s1", "aapl", [bar])

        _sql, args, _conn = fake_db.executemany_calls[0]
        self.assertEqual(args[0][1], "AAPL")
        self.assertEqual(args[0][7], 10)

    async def test_history_list_builds_date_filters_and_normalizes_rows(self) -> None:
        fake_db = FakeDB()
        fake_db.fetch_all_results.append([{"date": date(2026, 8, 26), "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}])
        history_db.db = fake_db

        rows = await history_db.list_by_stock("s1", start=date(2026, 1, 1), end=date(2026, 8, 26))

        sql, params, _conn = fake_db.fetch_all_calls[0]
        self.assertIn("date >= $2", sql)
        self.assertIn("date <= $3", sql)
        self.assertEqual(params[1], date(2026, 1, 1))
        self.assertEqual(rows[0]["close"], 2.0)

    async def test_watchlist_db_uses_conflict_safe_insert_and_delete_status(self) -> None:
        fake_db = FakeDB()
        watchlist_db.db = fake_db

        await watchlist_db.add_to_watchlist("u1", "s1")
        fake_db.execute_results.append("DELETE 1")
        result = await watchlist_db.remove_from_watchlist("u1", "s1")

        self.assertIn("ON CONFLICT", fake_db.execute_calls[0][0])
        self.assertEqual(result, "DELETE 1")


if __name__ == "__main__":
    unittest.main()
