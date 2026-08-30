from datetime import date
from types import SimpleNamespace
import unittest

from test_support import import_project_module

admin_service = import_project_module("services.admin_service", "common", "ui_service/backend", model_stubs=True)
HTTPException = admin_service.HTTPException
daily_update = import_project_module("jobs.daily_update", "common", "stock_manager/backend", model_stubs=True)
cleanup_archive = import_project_module("jobs.cleanup_archive", "common", "stock_manager/backend", model_stubs=True)
news_update = import_project_module("jobs.news_update", "common", "news_agent/backend", model_stubs=True)


class AdminServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.users = {"u1": {"id": "u1", "user_name": "Alice", "email": "a@example.com", "phone_number": "050", "admin": None, "lock": None}}
        self.deleted_docs: list[str] = []
        self.purged: list[str] = []
        self.cleared: list[str] = []
        admin_service.user_db = SimpleNamespace(
            is_admin_role=lambda value: str(value).strip().lower() == "admin" if value is not None else False,
            is_user_locked=lambda value: str(value).strip().lower() == "lock" if value is not None else False,
            get_user_by_id=lambda user_id: self._async(self.users.get(user_id)),
            get_user_by_email=lambda email: self._async(None),
            get_user_by_username=lambda name: self._async(None),
            get_user_by_phone=lambda phone: self._async(None),
            update_user_fields=self.update_user_fields,
            delete_user=lambda user_id: self._async("DELETE 1"),
            create_user=self.create_user,
        )
        admin_service.admin_db = SimpleNamespace(list_users=lambda: self._async(list(self.users.values())))
        admin_service.documents_service = SimpleNamespace(delete_all_user_files=self.delete_docs)
        admin_service.doc_agent = SimpleNamespace(purge_user=self.purge_user)
        admin_service.stock_manager = SimpleNamespace(
            list_watchlist=lambda user_id: self._async([]),
            quote_to_watchlist_stock=lambda row: {"id": row.get("stock_id"), "symbol": row.get("symbol"), "price": row.get("close"), "change": row.get("change")},
            clear_user_watchlist=self.clear_watchlist,
            get_stock_by_symbol=lambda symbol: self._async(None),
            ensure_and_assign=lambda user_id, symbol: self._async({"stock_id": "s1", "symbol": symbol.upper(), "close": 10}),
            get_stock=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL"}),
            is_on_watchlist=lambda user_id, stock_id: self._async(False),
            remove_from_watchlist=lambda user_id, stock_id: self._async({}),
            unwatch_stock_everywhere=lambda stock_id: self._async({}),
        )
        admin_service.hash_password = lambda password: f"hashed:{password}"
        self.updated_fields: list[tuple[str, dict]] = []

    async def create_user(self, **kwargs):
        user = {"id": "u2", **kwargs}
        self.users["u2"] = user
        return user

    async def update_user_fields(self, user_id, **kwargs):
        self.updated_fields.append((user_id, kwargs))
        self.users[user_id].update({k: v for k, v in kwargs.items() if v is not None})

    async def delete_docs(self, user_id):
        self.deleted_docs.append(user_id)
        return 1

    async def purge_user(self, user_id):
        self.purged.append(user_id)
        return {}

    async def clear_watchlist(self, user_id):
        self.cleared.append(user_id)
        return {}

    async def test_list_users_includes_followed_stocks(self) -> None:
        result = await admin_service.list_users()
        self.assertEqual(result[0].id, "u1")

    async def test_create_user_hashes_password_and_returns_admin_user(self) -> None:
        req = SimpleNamespace(user_name="Bob", email="b@example.com", phone_number="051", password="Pass1234", admin="admin", lock=None)
        user = await admin_service.create_user(req)
        self.assertEqual(user.id, "u2")
        self.assertEqual(self.users["u2"]["hashed_password"], "hashed:Pass1234")

    async def test_update_user_rejects_missing_user(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            await admin_service.update_user("missing", SimpleNamespace(user_name="x", email="x", phone_number="x", admin=None, lock=None, model_fields_set=set()))
        self.assertEqual(caught.exception.status_code, 404)

    async def test_delete_user_cleans_documents_vectors_watchlist_then_user(self) -> None:
        response = await admin_service.delete_user("u1")
        self.assertEqual(response.message, "User deleted")
        self.assertEqual(self.deleted_docs, ["u1"])
        self.assertEqual(self.purged, ["u1"])
        self.assertEqual(self.cleared, ["u1"])

    async def test_assign_stock_requires_user_and_symbol_or_stock_id(self) -> None:
        with self.assertRaises(HTTPException):
            await admin_service.assign_stock_to_user("missing", SimpleNamespace(symbol="AAPL", stock_id=None))
        with self.assertRaises(HTTPException):
            await admin_service.assign_stock_to_user("u1", SimpleNamespace(symbol=None, stock_id=None))
        result = await admin_service.assign_stock_to_user("u1", SimpleNamespace(symbol="aapl", stock_id=None))
        self.assertEqual(result.symbol, "AAPL")

    async def _async(self, value):
        return value

    async def test_delete_user_stops_before_watchlist_and_user_delete_when_vector_purge_fails(self) -> None:
        """Stop user deletion when document vector cleanup fails partway through."""
        async def fail_purge(user_id):
            self.purged.append(user_id)
            raise RuntimeError("vector purge failed")

        admin_service.doc_agent = SimpleNamespace(purge_user=fail_purge)
        deleted_users: list[str] = []
        admin_service.user_db.delete_user = lambda user_id: self._async(deleted_users.append(user_id) or "DELETE 1")

        with self.assertRaisesRegex(RuntimeError, "vector purge failed"):
            await admin_service.delete_user("u1")

        self.assertEqual(self.deleted_docs, ["u1"])
        self.assertEqual(self.purged, ["u1"])
        self.assertEqual(self.cleared, [])
        self.assertEqual(deleted_users, [])

class FakeDb:
    def transaction(self):
        class Tx:
            async def __aenter__(self):
                return "conn"
            async def __aexit__(self, exc_type, exc, tb):
                return False
        return Tx()


class JobTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_update_skips_when_market_closed_unless_forced(self) -> None:
        calls = []
        provider = SimpleNamespace(is_market_open=lambda exchange: False)
        daily_update._provider = lambda: provider
        daily_update._run_provider = lambda func, *args: self._async(func(*args))
        daily_update.quotes_db = SimpleNamespace(list_watched_quotes=lambda: self._async(calls.append("listed") or []))

        await daily_update.run_daily_update(force=False)

        self.assertEqual(calls, [])

    async def test_daily_update_refreshes_quote_and_history_for_watched_stock(self) -> None:
        quote = SimpleNamespace(symbol="AAPL", name="Apple", close=10, change=1, percent_change=10, previous_close=9, open=9.5, high=11, low=9, volume=100, fifty_two_week_high=20, fifty_two_week_low=5)
        calls = []
        daily_update.db = FakeDb()
        daily_update._provider = lambda: SimpleNamespace(get_quote=lambda symbol: quote)
        daily_update._run_provider = lambda func, *args: self._async(func(*args))
        daily_update._fetch_history_gap_best_effort = lambda symbol, start, end: self._async([SimpleNamespace(date=date(2026, 8, 26), open=1, high=2, low=1, close=2, volume=10)])
        daily_update.quotes_db = SimpleNamespace(
            list_watched_quotes=lambda: self._async([{"stock_id": "s1", "symbol": "AAPL"}]),
            upsert_quote=lambda **kwargs: self._async(calls.append(("quote", kwargs))),
        )
        daily_update.history_db = SimpleNamespace(
            get_max_date=lambda stock_id: self._async(None),
            upsert_bars=lambda *args, **kwargs: self._async(calls.append(("history", args))),
            delete_older_than=lambda *args, **kwargs: self._async(calls.append(("delete_old", args))),
        )

        await daily_update.run_daily_update(force=True)

        self.assertEqual([call[0] for call in calls], ["quote", "history", "delete_old"])
        self.assertEqual(calls[0][1]["open"], 9.5)

    async def test_cleanup_archive_archives_unwatched_quotes(self) -> None:
        calls = []
        cleanup_archive.db = FakeDb()
        cleanup_archive.quotes_db = SimpleNamespace(
            list_unwatched_stock_ids=lambda: self._async(["s1"]),
            get_by_id=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL"}),
            delete_quote=lambda stock_id, conn=None: self._async(calls.append(("delete", stock_id, conn))),
        )
        cleanup_archive.archive_db = SimpleNamespace(archive_history_for_stock=lambda **kwargs: self._async(calls.append(("archive", kwargs))))

        await cleanup_archive.run_cleanup_archive()

        self.assertEqual(calls[0][0], "archive")
        self.assertEqual(calls[1][0], "delete")
    async def test_cleanup_archive_can_run_twice_without_reprocessing_deleted_stocks(self) -> None:
        """Make repeated cleanup archive runs idempotent."""
        calls = []
        remaining_batches = [["s1"], []]
        cleanup_archive.db = FakeDb()
        cleanup_archive.quotes_db = SimpleNamespace(
            list_unwatched_stock_ids=lambda: self._async(remaining_batches.pop(0)),
            get_by_id=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL"}),
            delete_quote=lambda stock_id, conn=None: self._async(calls.append(("delete", stock_id, conn))),
        )
        cleanup_archive.archive_db = SimpleNamespace(
            archive_history_for_stock=lambda **kwargs: self._async(calls.append(("archive", kwargs)))
        )

        await cleanup_archive.run_cleanup_archive()
        await cleanup_archive.run_cleanup_archive()

        self.assertEqual([call[0] for call in calls], ["archive", "delete"])

    async def test_news_update_skips_llm_when_no_new_articles_and_existing_summary(self) -> None:
        calls = []
        news_update.retry_missing_article_bodies = lambda *_args: self._async(0)
        news_update.purge_old_articles = lambda *_args: self._async({})
        news_update._stock_manager_client = lambda: SimpleNamespace(list_stocks=lambda: self._async([{"stock_id": "s1", "symbol": "AAPL", "stock_summery": "existing"}]), update_stock_summery=lambda *args, **kwargs: self._async(calls.append("updated")))
        news_update._news_provider = lambda: SimpleNamespace(get_news_for_day=lambda symbol, day: [news_update.NewsItem("A", "https://a", None, None, None)])
        news_update._run_provider = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))
        news_update.upsert_stock_articles = lambda stock_id, payload: self._async(([], 0))
        news_update._llm_client = lambda: SimpleNamespace(summarize=lambda *_args, **_kwargs: self._async(calls.append("llm")))

        await news_update.run_news_update()

        self.assertEqual(calls, [])

    async def test_news_update_updates_summary_for_new_articles(self) -> None:
        updates = []
        news_update.retry_missing_article_bodies = lambda *_args: self._async(0)
        news_update.purge_old_articles = lambda *_args: self._async({})
        news_update._stock_manager_client = lambda: SimpleNamespace(list_stocks=lambda: self._async([{"stock_id": "s1", "symbol": "AAPL", "close": "10", "change": "1", "percent_change": "10"}]), update_stock_summery=lambda stock_id, summary, stock_news_published_at=None: self._async(updates.append((stock_id, summary, stock_news_published_at))))
        news_update._news_provider = lambda: SimpleNamespace(get_news_for_day=lambda symbol, day: [news_update.NewsItem("A", "https://a", None, "S", "Summary")])
        news_update._run_provider = lambda func, *args, **kwargs: self._async(func(*args, **kwargs))
        news_update.upsert_stock_articles = lambda stock_id, payload: self._async(([{"article_id": "a1"}], 1))
        news_update._llm_client = lambda: SimpleNamespace(summarize=lambda *_args, **_kwargs: self._async(SimpleNamespace(content="Outlook: UP")))
        news_update._stamp_summary = lambda content: "Created: now\n\n" + content

        await news_update.run_news_update()

        self.assertEqual(updates[0][0], "s1")
        self.assertIn("Outlook: UP", updates[0][1])

    async def _async(self, value):
        return value


if __name__ == "__main__":
    unittest.main()


