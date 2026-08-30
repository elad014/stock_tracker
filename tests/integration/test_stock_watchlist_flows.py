import asyncio
from datetime import date
from types import SimpleNamespace
import unittest

from test_support import import_project_module


EXPECTED_QUOTE_COLUMNS = {
    "stock_id",
    "symbol",
    "name",
    "close",
    "change",
    "percent_change",
    "previous_close",
    "open",
    "high",
    "low",
    "volume",
    "fifty_two_week_high",
    "fifty_two_week_low",
    "stock_summery",
    "stock_news_published_at",
}


class FakeTransactionDb:
    def transaction(self):
        class Tx:
            async def __aenter__(self):
                return "test-conn"
            async def __aexit__(self, exc_type, exc, tb):
                return False
        return Tx()


class InMemoryStockStore:
    def __init__(self) -> None:
        self.quotes_by_id: dict[str, dict] = {}
        self.quotes_by_symbol: dict[str, dict] = {}
        self.history: dict[str, list[dict]] = {}
        self.watchlist: set[tuple[str, str]] = set()
        self.archived: dict[str, dict] = {}
        self.next_id = 1

    def next_stock_id(self) -> str:
        value = f"stock-{self.next_id}"
        self.next_id += 1
        return value

    async def get_by_symbol(self, symbol, conn=None):
        return self.quotes_by_symbol.get(symbol.upper())

    async def get_by_id(self, stock_id, conn=None):
        return self.quotes_by_id.get(stock_id)

    async def upsert_quote(self, **kwargs):
        symbol = kwargs["symbol"].upper()
        stock_id = self.quotes_by_symbol.get(symbol, {}).get("stock_id", kwargs["stock_id"])
        row = {
            "stock_id": stock_id,
            "symbol": symbol,
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
            "stock_summery": self.quotes_by_id.get(stock_id, {}).get("stock_summery"),
            "stock_news_published_at": self.quotes_by_id.get(stock_id, {}).get("stock_news_published_at"),
        }
        self.quotes_by_id[stock_id] = row
        self.quotes_by_symbol[row["symbol"]] = row
        return row

    async def list_all_quotes(self, conn=None):
        return sorted(self.quotes_by_id.values(), key=lambda row: row["symbol"])

    async def list_watched_quotes(self, conn=None):
        watched_ids = {stock_id for _user_id, stock_id in self.watchlist}
        return [self.quotes_by_id[stock_id] for stock_id in watched_ids if stock_id in self.quotes_by_id]

    async def update_stock_summery(self, stock_id, stock_summery, stock_news_published_at=None, conn=None):
        row = self.quotes_by_id.get(stock_id)
        if not row:
            return None
        row["stock_summery"] = stock_summery
        row["stock_news_published_at"] = stock_news_published_at
        return row

    async def has_history(self, stock_id, conn=None):
        return bool(self.history.get(stock_id))

    async def upsert_bars(self, stock_id, symbol, bars, conn=None):
        rows = self.history.setdefault(stock_id, [])
        by_date = {row["date"]: row for row in rows}
        for bar in bars:
            key = bar.date.isoformat() if hasattr(bar.date, "isoformat") else str(bar.date)
            by_date[key] = {
                "date": key,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
        self.history[stock_id] = [by_date[key] for key in sorted(by_date)]

    async def list_by_stock(self, stock_id, start=None, end=None, conn=None):
        rows = list(self.history.get(stock_id, []))
        if start is not None:
            rows = [row for row in rows if row["date"] >= start.isoformat()]
        if end is not None:
            rows = [row for row in rows if row["date"] <= end.isoformat()]
        return rows

    async def get_latest_bar(self, stock_id, conn=None):
        rows = self.history.get(stock_id, [])
        return rows[-1] if rows else None

    async def get_max_date(self, stock_id, conn=None):
        rows = self.history.get(stock_id, [])
        return date.fromisoformat(rows[-1]["date"]) if rows else None

    async def delete_older_than(self, stock_id, cutoff, conn=None):
        self.history[stock_id] = [row for row in self.history.get(stock_id, []) if row["date"] >= cutoff.isoformat()]
        return "DELETE 0"

    async def list_user_watchlist(self, user_id, conn=None):
        ids = [stock_id for uid, stock_id in self.watchlist if uid == user_id]
        return [self.quotes_by_id[stock_id] for stock_id in ids]

    async def is_on_watchlist(self, user_id, stock_id, conn=None):
        return (user_id, stock_id) in self.watchlist

    async def add_to_watchlist(self, user_id, stock_id, conn=None):
        self.watchlist.add((user_id, stock_id))

    async def remove_from_watchlist(self, user_id, stock_id, conn=None):
        if (user_id, stock_id) not in self.watchlist:
            return "DELETE 0"
        self.watchlist.remove((user_id, stock_id))
        return "DELETE 1"

    async def delete_watchlist_for_user(self, user_id, conn=None):
        self.watchlist = {item for item in self.watchlist if item[0] != user_id}

    async def delete_watchlist_for_stock(self, stock_id, conn=None):
        self.watchlist = {item for item in self.watchlist if item[1] != stock_id}

    async def get_archived_stock_by_symbol(self, symbol, conn=None):
        return self.archived.get(symbol.upper())

    async def has_archive(self, stock_id, conn=None):
        return False

    async def restore_to_history(self, stock_id, conn=None):
        pass

    async def get_archive_max_date(self, stock_id, conn=None):
        return None


class FakeTwelveProvider:
    def __init__(self, stock_module):
        self.stock_module = stock_module
        self.fail_symbols: set[str] = set()
        self.quote_calls: list[str] = []

    def get_quote(self, symbol):
        symbol = symbol.upper()
        self.quote_calls.append(symbol)
        if symbol in self.fail_symbols:
            raise RuntimeError("symbol not found")
        return self.stock_module.QuoteData(
            symbol=symbol,
            name=f"{symbol} Inc.",
            close=200.5,
            change=1.5,
            percent_change=0.75,
            previous_close=199.0,
            open=199.5,
            high=202.0,
            low=198.0,
            volume=123456,
            fifty_two_week_high=250.0,
            fifty_two_week_low=150.0,
        )

    def get_daily_time_series(self, symbol, start, end):
        return [
            self.stock_module.OHLCVBar(date=date(2026, 8, 25), open=190, high=195, low=188, close=194, volume=1000),
            self.stock_module.OHLCVBar(date=date(2026, 8, 26), open=195, high=202, low=194, close=200.5, volume=2000),
        ]

    def is_market_open(self, exchange="NASDAQ"):
        return True


class StockManagerRouteIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "STOCKS / WATCHLIST"

    async def asyncSetUp(self) -> None:
        self.routes = import_project_module("routers.stocks_routes", "common", "stock_manager/backend", model_stubs=True)
        self.stock_service = self.routes.stock_service
        self.store = InMemoryStockStore()
        self.provider = FakeTwelveProvider(self.stock_service)
        self.stock_service.db = FakeTransactionDb()
        self.stock_service.quotes_db = SimpleNamespace(
            get_by_symbol=self.store.get_by_symbol,
            get_by_id=self.store.get_by_id,
            upsert_quote=self.store.upsert_quote,
            list_all_quotes=self.store.list_all_quotes,
            update_stock_summery=self.store.update_stock_summery,
        )
        self.stock_service.history_db = SimpleNamespace(
            has_history=self.store.has_history,
            upsert_bars=self.store.upsert_bars,
            list_by_stock=self.store.list_by_stock,
            get_latest_bar=self.store.get_latest_bar,
            get_max_date=self.store.get_max_date,
            delete_older_than=self.store.delete_older_than,
        )
        self.stock_service.watchlist_db = SimpleNamespace(
            list_user_watchlist=self.store.list_user_watchlist,
            is_on_watchlist=self.store.is_on_watchlist,
            add_to_watchlist=self.store.add_to_watchlist,
            remove_from_watchlist=self.store.remove_from_watchlist,
            delete_watchlist_for_user=self.store.delete_watchlist_for_user,
            delete_watchlist_for_stock=self.store.delete_watchlist_for_stock,
        )
        self.stock_service.archive_db = SimpleNamespace(
            get_archived_stock_by_symbol=self.store.get_archived_stock_by_symbol,
            has_archive=self.store.has_archive,
            get_max_date=self.store.get_archive_max_date,
            restore_to_history=self.store.restore_to_history,
        )
        self.stock_service._provider = lambda: self.provider
        self.stock_service._run_provider = lambda func, *args: self._async(func(*args))
        self.stock_service.uuid4 = self.store.next_stock_id

    async def _async(self, value):
        return value

    async def add_aapl(self):
        return await self.routes.add_watchlist(SimpleNamespace(user_id="u1", symbol="AAPL"))

    async def test_watchlist_add_stock_not_yet_stored_persists_quote_history_and_watchlist(self) -> None:
        response = await self.add_aapl()
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(len(self.store.quotes_by_id), 1)
        self.assertEqual(len(self.store.history[response.stock_id]), 2)
        self.assertTrue(await self.store.is_on_watchlist("u1", response.stock_id))

    async def test_stock_quote_all_expected_database_columns_populated(self) -> None:
        response = await self.add_aapl()
        row = self.store.quotes_by_id[response.stock_id]
        self.assertEqual(set(row), EXPECTED_QUOTE_COLUMNS)
        for column in EXPECTED_QUOTE_COLUMNS - {"stock_summery", "stock_news_published_at"}:
            self.assertIsNotNone(row[column], column)
        self.assertEqual(row["open"], 199.5)

    async def test_stock_quote_retrieval_reads_persisted_quote(self) -> None:
        created = await self.add_aapl()
        quote = await self.routes.get_stock(created.stock_id)
        self.assertEqual(quote.stock_id, created.stock_id)
        self.assertEqual(quote.open, 195)
        self.assertEqual(quote.close, 200.5)

    async def test_stock_history_retrieval_reads_saved_database_rows(self) -> None:
        created = await self.add_aapl()
        history = await self.routes.get_stock_history(created.stock_id, range="5Y")
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0].date, "2026-08-25")

    async def test_stock_history_invalid_range_rejected(self) -> None:
        created = await self.add_aapl()
        with self.assertRaises(self.stock_service.HTTPException) as caught:
            await self.routes.get_stock_history(created.stock_id, range="BAD")
        self.assertEqual(caught.exception.status_code, 400)

    async def test_watchlist_list_returns_user_stocks(self) -> None:
        created = await self.add_aapl()
        rows = await self.routes.list_watchlist("u1")
        self.assertEqual(rows[0].stock_id, created.stock_id)

    async def test_watchlist_remove_deletes_membership(self) -> None:
        created = await self.add_aapl()
        response = await self.routes.remove_watchlist(SimpleNamespace(user_id="u1", stock_id=created.stock_id))
        self.assertEqual(response.message, "Stock removed from watchlist")
        self.assertFalse(await self.store.is_on_watchlist("u1", created.stock_id))

    async def test_watchlist_remove_missing_membership_returns_404(self) -> None:
        with self.assertRaises(self.stock_service.HTTPException) as caught:
            await self.routes.remove_watchlist(SimpleNamespace(user_id="u1", stock_id="missing"))
        self.assertEqual(caught.exception.status_code, 404)

    async def test_provider_unknown_symbol_maps_to_404(self) -> None:
        self.provider.fail_symbols.add("BAD")
        with self.assertRaises(self.stock_service.HTTPException) as caught:
            await self.routes.add_watchlist(SimpleNamespace(user_id="u1", symbol="BAD"))
        self.assertEqual(caught.exception.status_code, 404)
    async def test_concurrent_same_symbol_adds_create_one_stock_and_watchlist_row(self) -> None:
        """Collapse concurrent same-symbol watchlist adds into one stock row."""
        results = await asyncio.gather(self.add_aapl(), self.add_aapl())

        self.assertEqual({item.stock_id for item in results}, {results[0].stock_id})
        self.assertEqual(len(self.store.quotes_by_id), 1)
        self.assertEqual(len(self.store.watchlist), 1)

    async def test_reimporting_same_history_updates_existing_candles_without_duplicates(self) -> None:
        """Keep one history row per stock/date when importing history twice."""
        created = await self.add_aapl()
        await self.store.upsert_bars(
            created.stock_id,
            "AAPL",
            [self.stock_service.OHLCVBar(date=date(2026, 8, 26), open=300, high=301, low=299, close=300.5, volume=999)],
        )

        rows = self.store.history[created.stock_id]

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["date"], "2026-08-26")
        self.assertEqual(rows[-1]["close"], 300.5)
        self.assertEqual(rows[-1]["volume"], 999)

    async def test_stock_summary_update_persists_summary_columns(self) -> None:
        created = await self.add_aapl()
        response = await self.routes.update_stock_summery(SimpleNamespace(stock_summery="Created summary", stock_news_published_at="2026-08-26T00:00:00Z"), created.stock_id)
        self.assertEqual(response.stock_summery, "Created summary")
        self.assertEqual(self.store.quotes_by_id[created.stock_id]["stock_news_published_at"], "2026-08-26T00:00:00Z")


class UiToStockManagerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "SERVICE COMMUNICATION"

    async def asyncSetUp(self) -> None:
        self.stock_tests = StockManagerRouteIntegrationTests()
        await self.stock_tests.asyncSetUp()
        self.ui_watchlist = import_project_module("routers.watchlist_routes", "common", "ui_service/backend", model_stubs=True)

        class BridgeStockManager:
            async def list_watchlist(_, user_id):
                return [item.model_dump() for item in await self.stock_tests.routes.list_watchlist(user_id)]
            async def get_stock_by_symbol(_, symbol):
                try:
                    return (await self.stock_tests.routes.get_stock_by_symbol(symbol)).model_dump()
                except Exception:
                    return None
            async def is_on_watchlist(_, user_id, stock_id):
                return (await self.stock_tests.routes.check_watchlist_membership(user_id, stock_id))["on_watchlist"]
            async def add_to_watchlist(_, user_id, symbol):
                return (await self.stock_tests.routes.add_watchlist(SimpleNamespace(user_id=user_id, symbol=symbol))).model_dump()
            async def remove_from_watchlist(_, user_id, stock_id):
                return (await self.stock_tests.routes.remove_watchlist(SimpleNamespace(user_id=user_id, stock_id=stock_id))).model_dump()
            def quote_to_watchlist_stock(_, payload):
                return {"id": payload.get("stock_id"), "symbol": payload.get("symbol"), "price": payload.get("close"), "change": payload.get("change"), "stock_summery": payload.get("stock_summery")}
        self.ui_watchlist.watchlist_service.stock_manager = BridgeStockManager()

    async def test_ui_service_adds_stock_via_stock_manager_route_bridge(self) -> None:
        response = await self.ui_watchlist.add_watchlist_stock(SimpleNamespace(name="AAPL"), {"id": "u1"})
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.price, 200.5)

    async def test_ui_service_prevents_duplicate_watchlist_entry(self) -> None:
        created = await self.ui_watchlist.add_watchlist_stock(SimpleNamespace(name="AAPL"), {"id": "u1"})
        with self.assertRaises(self.ui_watchlist.watchlist_service.HTTPException) as caught:
            await self.ui_watchlist.add_watchlist_stock(SimpleNamespace(name="AAPL"), {"id": "u1"})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(created.symbol, "AAPL")

    async def test_ui_service_lists_and_removes_watchlist_entry_via_bridge(self) -> None:
        created = await self.ui_watchlist.add_watchlist_stock(SimpleNamespace(name="AAPL"), {"id": "u1"})
        listed = await self.ui_watchlist.list_watchlist({"id": "u1"})
        removed = await self.ui_watchlist.remove_watchlist_stock(created.id, {"id": "u1"})
        self.assertEqual(listed[0].id, created.id)
        self.assertEqual(removed.message, "Stock removed from watchlist")


if __name__ == "__main__":
    unittest.main()


