from types import SimpleNamespace
import unittest

from test_support import import_project_module

doc_service = import_project_module("services.doc_service", "common", "doc_agent/backend", model_stubs=True)
HTTPException = doc_service.HTTPException


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_download = False

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list_objects(self, prefix: str):
        return [SimpleNamespace(key=key) for key in self.objects if key.startswith(prefix)]

    async def download_bytes(self, key: str) -> bytes:
        if self.fail_download:
            raise doc_service.ObjectStorageError("download failed")
        return self.objects[key]


class FakeVectorsDb:
    def __init__(self) -> None:
        self.deleted: list[tuple] = []
        self.inserted: list[tuple] = []
        self.matches: list[dict] = []

    async def delete_document_vectors(self, user_id, document_id, conn=None):
        self.deleted.append((user_id, document_id, conn))
        return 2

    async def insert_chunks(self, user_id, document_id, rows, conn=None):
        self.inserted.append((user_id, document_id, rows, conn))

    async def search_similar(self, vector, user_id, document_id, limit):
        self.search_args = (vector, user_id, document_id, limit)
        return self.matches

    async def delete_user_vectors(self, user_id, conn=None):
        return 3


class FakeIngestEventsDb:
    def __init__(self) -> None:
        self.usage = (0, None)
        self.recorded: list[str] = []

    async def current_period_usage(self, user_id):
        return self.usage

    def retry_after_seconds(self, first_ingest):
        return 99

    async def record_successful_ingest(self, user_id, conn=None):
        self.recorded.append(user_id)

    async def delete_user_quota(self, user_id, conn=None):
        return True


class FakeDb:
    def transaction(self):
        class Tx:
            async def __aenter__(self):
                return "conn"
            async def __aexit__(self, exc_type, exc, tb):
                return False
        return Tx()


class DocAgentServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage()
        self.vectors = FakeVectorsDb()
        self.ingest_events = FakeIngestEventsDb()
        doc_service.storage = self.storage
        doc_service.vectors_db = self.vectors
        doc_service.ingest_events_db = self.ingest_events
        doc_service.db = FakeDb()
        doc_service.ingest_limiter = SimpleNamespace(consume=lambda key: None)
        doc_service.ask_limiter = SimpleNamespace(consume=lambda key: None)
        doc_service.DOC_MAX_INDEXED_FILES = 10
        doc_service.DOC_MAX_INGESTS_PER_WEEK = 20

    def test_document_storage_key_scopes_to_user_and_rejects_traversal(self) -> None:
        key, stored_id = doc_service.document_storage_key("u1", "Folder/report.pdf")
        self.assertEqual(key, "u1/Folder/report.pdf")
        self.assertEqual(stored_id, "Folder/report.pdf")
        with self.assertRaises(HTTPException):
            doc_service.document_storage_key("u1", "../secret.pdf")
        with self.assertRaises(HTTPException):
            doc_service.document_storage_key("bad/user", "a.pdf")

    async def test_resolve_document_key_matches_case_insensitively(self) -> None:
        self.storage.objects["u1/Reports/Annual.PDF"] = b"data"

        key, stored_id = await doc_service.resolve_document_key("u1", "reports/annual.pdf", require_object=True)

        self.assertEqual(key, "u1/Reports/Annual.PDF")
        self.assertEqual(stored_id, "Reports/Annual.PDF")

    async def test_assert_ingest_quotas_rejects_too_many_files_and_weekly_limit(self) -> None:
        for index in range(11):
            self.storage.objects[f"u1/{index}.pdf"] = b"x"
        with self.assertRaises(HTTPException) as too_many_files:
            await doc_service._assert_ingest_quotas("u1")
        self.assertEqual(too_many_files.exception.status_code, 409)

        self.storage.objects = {"u1/a.pdf": b"x"}
        self.ingest_events.usage = (20, None)
        with self.assertRaises(HTTPException) as weekly:
            await doc_service._assert_ingest_quotas("u1")
        self.assertEqual(weekly.exception.status_code, 429)
        self.assertEqual(weekly.exception.headers["Retry-After"], "99")

    async def test_ingest_document_downloads_pdf_embeds_chunks_and_replaces_vectors(self) -> None:
        self.storage.objects["u1/a.pdf"] = b"%PDF-fake"
        doc_service.extract_pdf_blocks = lambda data: [SimpleNamespace(kind="prose", section="Intro", text="Alpha. Beta.")]
        class Embeddings:
            async def embed_texts(self, chunks):
                self.chunks = chunks
                return [[0.1, 0.2] for _ in chunks]
        doc_service._embedding_client = lambda: Embeddings()

        result = await doc_service.ingest_document("u1", "a.pdf")

        self.assertEqual(result.document_id, "a.pdf")
        self.assertGreater(result.chunk_count, 0)
        self.assertEqual(self.vectors.deleted[0][:2], ("u1", "a.pdf"))
        self.assertEqual(self.ingest_events.recorded, ["u1"])

    async def test_ingest_document_maps_pdf_errors(self) -> None:
        self.storage.objects["u1/a.pdf"] = b"%PDF-fake"
        doc_service.extract_pdf_blocks = lambda data: (_ for _ in ()).throw(doc_service.PdfExtractError("PDF contains no extractable text"))

        with self.assertRaises(HTTPException) as caught:
            await doc_service.ingest_document("u1", "a.pdf")

        self.assertEqual(caught.exception.status_code, 404)

    async def test_ask_document_returns_not_found_when_no_matching_chunks(self) -> None:
        class Embeddings:
            async def embed_query(self, text):
                return [0.1]
        doc_service._embedding_client = lambda: Embeddings()
        self.vectors.matches = []

        result = await doc_service.ask_document("What?", "u1")

        self.assertEqual(result.answer, doc_service.DOC_NOT_FOUND_ANSWER)
        self.assertEqual(result.excerpts, [])

    async def test_ask_document_calls_llm_with_guarded_excerpts(self) -> None:
        class Embeddings:
            async def embed_query(self, text):
                return [0.1]
        captured = {}
        class LLM:
            def _default_max_tokens(self):
                return None
            async def chat_completion(self, messages, max_tokens=None):
                captured["messages"] = messages
                return SimpleNamespace(content="Answer")
        doc_service._embedding_client = lambda: Embeddings()
        doc_service._llm_client = lambda: LLM()
        self.vectors.matches = [{"document_id": "a.pdf", "content": "Document content", "similarity": 0.9}]

        result = await doc_service.ask_document("What happened?", "u1")

        self.assertEqual(result.answer, "Answer")
        self.assertIn("<<<UNTRUSTED_DATA>>>", captured["messages"][1]["content"])
        self.assertIn("Source document: a.pdf", result.excerpts[0])

    async def test_delete_document_vectors_and_purge_user_wrap_db_actions(self) -> None:
        self.storage.objects["u1/a.pdf"] = b"x"
        deleted = await doc_service.delete_document_vectors("u1", "a.pdf")
        purged = await doc_service.purge_user("u1")
        self.assertEqual(deleted.deleted_chunks, 2)
        self.assertEqual(purged.deleted_chunks, 3)
        self.assertTrue(purged.quota_deleted)


if __name__ == "__main__":
    unittest.main()


