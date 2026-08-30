from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest

from test_support import FakeDB, FakeResponse, import_project_module


class TransactionRollbackRegressionTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "STOCKS / WATCHLIST"

    async def asyncSetUp(self) -> None:
        self.stock_service = import_project_module(
            "services.stock_service",
            "common",
            "stock_manager/backend",
            model_stubs=True,
        )
        self.quote = self.stock_service.QuoteData(
            symbol="AAPL",
            name="Apple",
            close=200,
            change=1,
            percent_change=0.5,
            previous_close=199,
            open=199.5,
            high=202,
            low=198,
            volume=1000,
            fifty_two_week_high=250,
            fifty_two_week_low=150,
        )
        self.tx_exits: list[type | None] = []

        class RecordingTxDb:
            def transaction(inner):
                outer = self

                class Tx:
                    async def __aenter__(self):
                        return "tx-conn"

                    async def __aexit__(self, exc_type, exc, tb):
                        outer.tx_exits.append(exc_type)
                        return False

                return Tx()

        self.stock_service.db = RecordingTxDb()
        self.stock_service._fetch_history = lambda *_args: self._async([
            self.stock_service.OHLCVBar(
                date=date(2026, 8, 26),
                open=1,
                high=2,
                low=1,
                close=2,
                volume=10,
            )
        ])

    async def test_quote_saved_but_history_failure_aborts_watchlist_add(self) -> None:
        """Abort watchlist add when history persistence fails after quote upsert."""
        calls: list[str] = []

        async def upsert_quote(**kwargs):
            calls.append("quote")
            return {
                "stock_id": kwargs["stock_id"],
                "symbol": kwargs["symbol"],
                "name": kwargs["name"],
                "close": kwargs["close"],
                "change": kwargs["change"],
                "percent_change": kwargs["percent_change"],
                "previous_close": kwargs.get("previous_close"),
                "open": kwargs.get("open"),
                "high": kwargs.get("high"),
                "low": kwargs.get("low"),
                "volume": kwargs.get("volume"),
                "fifty_two_week_high": kwargs.get("fifty_two_week_high"),
                "fifty_two_week_low": kwargs.get("fifty_two_week_low"),
                "stock_summery": None,
                "stock_news_published_at": None,
            }

        async def fail_history(*_args, **_kwargs):
            calls.append("history")
            raise RuntimeError("history insert failed")

        async def add_watchlist(*_args, **_kwargs):
            calls.append("watchlist")

        self.stock_service.quotes_db = SimpleNamespace(upsert_quote=upsert_quote)
        self.stock_service.history_db = SimpleNamespace(upsert_bars=fail_history)
        self.stock_service.watchlist_db = SimpleNamespace(add_to_watchlist=add_watchlist)

        with self.assertRaisesRegex(RuntimeError, "history insert failed"):
            await self.stock_service._create_new_and_watch("u1", self.quote)

        self.assertEqual(calls, ["quote", "history"])
        self.assertIs(self.tx_exits[0], RuntimeError)

    async def test_watchlist_failure_rolls_back_created_quote_and_history_transaction(self) -> None:
        """Propagate watchlist failure so quote/history inserts are transactionally rolled back."""
        calls: list[str] = []

        async def upsert_quote(**kwargs):
            calls.append("quote")
            return {
                "stock_id": kwargs["stock_id"],
                "symbol": kwargs["symbol"],
                "name": kwargs["name"],
                "close": kwargs["close"],
                "change": kwargs["change"],
                "percent_change": kwargs["percent_change"],
                "previous_close": kwargs.get("previous_close"),
                "open": kwargs.get("open"),
                "high": kwargs.get("high"),
                "low": kwargs.get("low"),
                "volume": kwargs.get("volume"),
                "fifty_two_week_high": kwargs.get("fifty_two_week_high"),
                "fifty_two_week_low": kwargs.get("fifty_two_week_low"),
                "stock_summery": None,
                "stock_news_published_at": None,
            }

        async def upsert_history(*_args, **_kwargs):
            calls.append("history")

        async def fail_watchlist(*_args, **_kwargs):
            calls.append("watchlist")
            raise RuntimeError("watchlist insert failed")

        self.stock_service.quotes_db = SimpleNamespace(upsert_quote=upsert_quote)
        self.stock_service.history_db = SimpleNamespace(upsert_bars=upsert_history)
        self.stock_service.watchlist_db = SimpleNamespace(add_to_watchlist=fail_watchlist)

        with self.assertRaisesRegex(RuntimeError, "watchlist insert failed"):
            await self.stock_service._create_new_and_watch("u1", self.quote)

        self.assertEqual(calls, ["quote", "history", "watchlist"])
        self.assertIs(self.tx_exits[0], RuntimeError)

    async def _async(self, value):
        return value


class StockDatabaseIdempotencyRegressionTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "STOCKS / TWELVE DATA"

    async def test_quote_upsert_conflicts_on_symbol_to_prevent_duplicate_stock_rows(self) -> None:
        """Use symbol uniqueness for idempotent stock creation races."""
        quotes_db = import_project_module(
            "db_logics.quotes_db_logic",
            "common",
            "stock_manager/backend",
        )
        fake_db = FakeDB()
        fake_db.fetch_one_results.append({
            "stock_id": "existing-stock-id",
            "symbol": "AAPL",
            "name": "Apple",
            "close": 200,
            "change": 1,
            "percent_change": 0.5,
            "previous_close": 199,
            "open": 199.5,
            "high": 202,
            "low": 198,
            "volume": 1000,
            "fifty_two_week_high": 250,
            "fifty_two_week_low": 150,
            "stock_summery": None,
            "stock_news_published_at": None,
        })
        quotes_db.db = fake_db

        result = await quotes_db.upsert_quote("new-generated-id", "aapl", "Apple", 200, 1, 0.5)

        sql, _params, _conn = fake_db.fetch_one_calls[0]
        self.assertIn("ON CONFLICT (symbol)", sql)
        self.assertEqual(result["stock_id"], "existing-stock-id")

    async def test_history_upsert_uses_stock_and_date_conflict_for_repeated_imports(self) -> None:
        """Make repeated history imports idempotent for the same stock/date."""
        history_db = import_project_module(
            "db_logics.history_db_logic",
            "common",
            "stock_manager/backend",
        )
        fake_db = FakeDB()
        history_db.db = fake_db
        bars = [
            SimpleNamespace(date=date(2026, 8, 26), open=1, high=2, low=1, close=2, volume=10),
            SimpleNamespace(date=date(2026, 8, 26), open=3, high=4, low=2, close=4, volume=20),
        ]

        await history_db.upsert_bars("s1", "aapl", bars)

        sql, args, _conn = fake_db.executemany_calls[0]
        self.assertIn("ON CONFLICT (stock_id, date) DO UPDATE", sql)
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0][2], args[1][2])

    async def test_empty_history_import_is_a_noop(self) -> None:
        """Skip database writes for an empty history provider response."""
        history_db = import_project_module(
            "db_logics.history_db_logic",
            "common",
            "stock_manager/backend",
        )
        fake_db = FakeDB()
        history_db.db = fake_db

        await history_db.upsert_bars("s1", "AAPL", [])

        self.assertEqual(fake_db.executemany_calls, [])

    async def test_history_listing_orders_rows_by_date_ascending(self) -> None:
        """Read history back in ascending timestamp order."""
        history_db = import_project_module(
            "db_logics.history_db_logic",
            "common",
            "stock_manager/backend",
        )
        fake_db = FakeDB()
        history_db.db = fake_db

        await history_db.list_by_stock("s1")

        sql, _params, _conn = fake_db.fetch_all_calls[0]
        self.assertIn("ORDER BY date ASC", sql)


class TwelveDataFailureRegressionTests(unittest.TestCase):
    COMPONENT = "STOCKS / TWELVE DATA"

    def setUp(self) -> None:
        self.twelve_module = import_project_module(
            "stock_provider_client.twelv_data_client",
            "common",
        )
        self.client = self.twelve_module.TwelveDataClient(api_key="test-key")

    def test_rate_limit_response_becomes_provider_error(self) -> None:
        """Map Twelve Data HTTP 429 into a provider error."""
        self.twelve_module.requests.get = lambda *_args, **_kwargs: FakeResponse(status_code=429)

        with self.assertRaisesRegex(RuntimeError, "Twelve Data HTTP 429"):
            self.client.request("quote", {"symbol": "AAPL"})

    def test_timeout_response_becomes_provider_error(self) -> None:
        """Map Twelve Data timeout into a provider error."""
        self.twelve_module.requests.get = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            self.twelve_module.requests.RequestException("timeout")
        )

        with self.assertRaisesRegex(RuntimeError, "Twelve Data request failed"):
            self.client.request("quote", {"symbol": "AAPL"})

    def test_provider_500_response_becomes_provider_error(self) -> None:
        """Map Twelve Data HTTP 500 into a provider error."""
        self.twelve_module.requests.get = lambda *_args, **_kwargs: FakeResponse(status_code=500)

        with self.assertRaisesRegex(RuntimeError, "Twelve Data HTTP 500"):
            self.client.request("quote", {"symbol": "AAPL"})

    def test_invalid_json_response_becomes_provider_error(self) -> None:
        """Reject malformed JSON from Twelve Data."""
        class InvalidJsonResponse(FakeResponse):
            def json(self):
                raise ValueError("not json")

        self.twelve_module.requests.get = lambda *_args, **_kwargs: InvalidJsonResponse(status_code=200)

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            self.client.request("quote", {"symbol": "AAPL"})

    def test_quote_missing_nullable_fields_does_not_invent_values(self) -> None:
        """Map missing quote fields to None without corrupting numeric values."""
        class Stub(self.twelve_module.TwelveDataClient):
            def __init__(inner):
                inner.api_key = "test-key"

            def request(inner, *_args, **_kwargs):
                return {"symbol": "AAPL", "name": "Apple", "close": "200.5", "change": None, "percent_change": "bad"}

        quote = Stub().get_quote("AAPL")

        self.assertEqual(quote.close, 200.5)
        self.assertIsNone(quote.open)
        self.assertIsNone(quote.volume)
        self.assertIsNone(quote.previous_close)
        self.assertIsNone(quote.percent_change)

    def test_history_response_is_sorted_and_skips_bad_timestamps(self) -> None:
        """Normalize out-of-order history and skip rows with invalid timestamps."""
        class Stub(self.twelve_module.TwelveDataClient):
            def __init__(inner):
                inner.api_key = "test-key"

            def request(inner, *_args, **_kwargs):
                return {
                    "values": [
                        {"datetime": "2026-08-27T00:30:00+03:00", "open": "2", "high": "3", "low": "1", "close": "2.5", "volume": "20"},
                        {"datetime": "bad", "open": "9", "high": "9", "low": "9", "close": "9", "volume": "9"},
                        {"datetime": "2026-08-26T23:30:00Z", "open": "1", "high": "2", "low": "1", "close": "1.5", "volume": "10"},
                    ]
                }

        bars = Stub().get_daily_time_series("AAPL", date(2026, 8, 1), date(2026, 8, 27))

        self.assertEqual([bar.date for bar in bars], [date(2026, 8, 26), date(2026, 8, 27)])


class JwtEdgeCaseRegressionTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "AUTHENTICATION"

    async def asyncSetUp(self) -> None:
        self.ui_deps = import_project_module("deps", "common", "ui_service/backend")
        self.ui_deps.get_user_auth_by_id = lambda user_id: self._async(None)
        self.ui_deps.get_user_by_email = lambda email: self._async(None)

    async def test_expired_jwt_is_rejected(self) -> None:
        """Reject an expired JWT."""
        self.ui_deps.jwt.decode = lambda *_args, **_kwargs: (_ for _ in ()).throw(self.ui_deps.JWTError("expired"))

        with self.assertRaises(self.ui_deps.HTTPException) as caught:
            await self.ui_deps.get_current_user(SimpleNamespace(scheme="Bearer", credentials="expired-token"))

        self.assertEqual(caught.exception.status_code, 401)

    async def test_invalid_jwt_signature_is_rejected(self) -> None:
        """Reject a JWT with an invalid signature."""
        self.ui_deps.jwt.decode = lambda *_args, **_kwargs: (_ for _ in ()).throw(self.ui_deps.JWTError("bad signature"))

        with self.assertRaises(self.ui_deps.HTTPException) as caught:
            await self.ui_deps.get_current_user(SimpleNamespace(scheme="Bearer", credentials="bad-token"))

        self.assertEqual(caught.exception.status_code, 401)

    async def test_token_for_deleted_user_is_rejected(self) -> None:
        """Reject a valid token when the user no longer exists."""
        self.ui_deps.jwt.decode = lambda *_args, **_kwargs: {"user_id": "deleted-user", "sub": "gone@example.com"}

        with self.assertRaises(self.ui_deps.HTTPException) as caught:
            await self.ui_deps.get_current_user(SimpleNamespace(scheme="Bearer", credentials="valid-but-deleted"))

        self.assertEqual(caught.exception.status_code, 401)

    async def _async(self, value):
        return value


if __name__ == "__main__":
    unittest.main()
