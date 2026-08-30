from datetime import datetime, timedelta, timezone
import unittest

from test_support import FakeDB, import_project_module

vectors_db = import_project_module("db_logics.vectors_db_logic", "common", "doc_agent/backend")
ingest_db = import_project_module("db_logics.ingest_events_db_logic", "common", "doc_agent/backend")


class DocDbLogicTests(unittest.IsolatedAsyncioTestCase):
    def test_embedding_literal_formats_pgvector_value(self) -> None:
        self.assertEqual(vectors_db.embedding_literal([0.1, 2]), "[0.1,2.0]")

    async def test_insert_chunks_serializes_vectors_for_executemany(self) -> None:
        fake_db = FakeDB()
        vectors_db.db = fake_db

        await vectors_db.insert_chunks("u1", "a.pdf", [(0, "text", [0.1, 0.2])])

        self.assertEqual(fake_db.executemany_calls[0][1][0], ("u1", "a.pdf", 0, "text", "[0.1,0.2]"))

    async def test_search_similar_scopes_to_user_and_optional_document(self) -> None:
        fake_db = FakeDB()
        fake_db.fetch_all_results.append([{"document_id": "a.pdf", "content": "Text", "similarity": "0.9"}])
        vectors_db.db = fake_db

        rows = await vectors_db.search_similar([0.1], "u1", "a.pdf", limit=5)

        sql, params, _conn = fake_db.fetch_all_calls[0]
        self.assertIn("document_id = $3", sql)
        self.assertEqual(params, ("[0.1]", "u1", "a.pdf", 5))
        self.assertEqual(rows[0]["similarity"], 0.9)

    async def test_delete_status_counts_rows(self) -> None:
        fake_db = FakeDB()
        fake_db.execute_results.append("DELETE 7")
        vectors_db.db = fake_db
        self.assertEqual(await vectors_db.delete_user_vectors("u1"), 7)

    def test_ingest_period_expiration_and_retry_after(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=8)
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertTrue(ingest_db.first_ingest_expired(old))
        self.assertFalse(ingest_db.first_ingest_expired(recent))
        self.assertGreater(ingest_db.retry_after_seconds(recent), 1)

    async def test_current_period_usage_resets_expired_period(self) -> None:
        fake_db = FakeDB()
        fake_db.fetch_one_results.append({"count_recent_ingests": 5, "first_ingest": datetime.now(timezone.utc) - timedelta(days=8)})
        ingest_db.db = fake_db
        self.assertEqual(await ingest_db.current_period_usage("u1"), (0, None))

    async def test_record_successful_ingest_inserts_or_increments(self) -> None:
        fake_db = FakeDB()
        fake_db.fetch_one_results.append(None)
        fake_db.fetch_one_results.append({"count_recent_ingests": 1, "first_ingest": datetime.now(timezone.utc)})
        ingest_db.db = fake_db

        await ingest_db.record_successful_ingest("u1")
        await ingest_db.record_successful_ingest("u1")

        self.assertIn("INSERT INTO", fake_db.execute_calls[0][0])
        self.assertIn("count_recent_ingests = count_recent_ingests + 1", fake_db.execute_calls[1][0])


if __name__ == "__main__":
    unittest.main()
