from contextlib import asynccontextmanager
from datetime import date, datetime
from io import BytesIO
import os
from types import SimpleNamespace
import unittest

from test_support import AsyncTransaction, SimpleModel, import_project_module


class FakeLimiter:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def consume(self, key: str) -> None:
        self.keys.append(key)

    def assert_allowed(self, key: str) -> None:
        self.keys.append(f"assert:{key}")

    def record(self, key: str) -> None:
        self.keys.append(f"record:{key}")


class FakeLlm:
    def __init__(self, content: str = "Mock Gemini analysis", model: str = "gemini-test") -> None:
        self.content = content
        self.model = model
        self.messages: list[list[dict]] = []
        self.sources: list[str] = []

    def _default_max_tokens(self) -> int:
        return 128

    async def chat_completion(self, messages, **_kwargs):
        self.messages.append(messages)
        return SimpleNamespace(content=self.content, model=self.model)

    async def summarize(self, source: str, **_kwargs):
        self.sources.append(source)
        return SimpleNamespace(content=self.content, model=self.model)


class NewsRoutesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "NEWS"

    async def asyncSetUp(self) -> None:
        self.routes = import_project_module("routers.news_routes", "common", "news_agent/backend", model_stubs=True)
        self.service = self.routes.news_service
        self.llm = FakeLlm("AAPL news answer from mocked Gemini")

        class Provider:
            def get_news_for_day(_, symbol, day=None):
                if symbol == "MISSING":
                    raise RuntimeError("symbol not found")
                return [
                    SimpleNamespace(
                        title="Apple expands services",
                        url="https://example.test/aapl-services",
                        published_at=datetime(2026, 8, 26, 12, 0, 0),
                        source="Example Wire",
                        summary="Provider summary",
                    ),
                    SimpleNamespace(
                        title="Apple options activity rises",
                        url="https://example.test/aapl-options",
                        published_at=datetime(2026, 8, 26, 13, 0, 0),
                        source="Market Wire",
                        summary="Options summary",
                    ),
                ]

        class ArticlesDb:
            async def list_recent_articles_by_symbol(_, symbol, days=7, limit=8):
                return [
                    {
                        "article_id": "article-1",
                        "symbol": symbol,
                        "title": "Apple options activity rises",
                        "url": "https://example.test/aapl-options",
                        "published_at": datetime(2026, 8, 26, 13, 0, 0),
                        "source": "Market Wire",
                        "text": "AAPL options activity increased. AAPL call volume rose sharply.",
                        "ai_summary": "Existing AI summary",
                        "provider_summary": "Provider options summary",
                    }
                ]

        async def run_provider(func, *args, **kwargs):
            return func(*args, **kwargs)

        self.service._news_provider = lambda: Provider()
        self.service._llm_client = lambda: self.llm
        self.service._run_provider = run_provider
        self.service.articles_db = ArticlesDb()

    async def test_news_route_fetches_finnhub_articles_with_provider_mock(self) -> None:
        response = await self.routes.get_news_for_stock(" aapl ", day=date(2026, 8, 26), outputsize=1)
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.count, 1)
        self.assertEqual(response.articles[0].title, "Apple expands services")

    async def test_news_route_maps_provider_not_found_to_404(self) -> None:
        with self.assertRaises(self.service.HTTPException) as caught:
            await self.routes.get_news_for_stock("MISSING", day=date(2026, 8, 26))
        self.assertEqual(caught.exception.status_code, 404)

    async def test_stored_news_route_reads_database_rows_without_provider_call(self) -> None:
        response = await self.routes.get_stored_news_for_stock("aapl", limit=5)
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.count, 1)
        self.assertEqual(response.articles[0].ai_summary, "Existing AI summary")
        self.assertIn("call volume", response.articles[0].text)

    async def test_search_and_summarize_uses_stored_articles_and_mocked_gemini(self) -> None:
        req = SimpleModel(symbol="aapl", query="What happened with options activity?")
        response = await self.routes.search_and_summarize(req)
        self.assertEqual(response.summary, "AAPL news answer from mocked Gemini")
        self.assertEqual(response.articles[0].article_id, "article-1")
        self.assertIn("options activity", response.articles[0].matching_sentences[0].lower())
        self.assertTrue(self.llm.messages)


class ArticleRoutesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "NEWS"

    async def asyncSetUp(self) -> None:
        self.routes = import_project_module("routers.articles_routes", "common", "news_agent/backend", model_stubs=True)
        self.service = self.routes.article_service
        self.stored_payloads: list[dict] = []
        self.llm = FakeLlm("Article summary from mocked Gemini")

        class StockManager:
            async def get_stock(_, stock_id):
                return {"stock_id": stock_id, "symbol": "AAPL", "name": "Apple Inc"}

        class Provider:
            def get_news_for_day(_, symbol, *_args, **_kwargs):
                return [
                    SimpleNamespace(
                        title="Apple supplier news",
                        url="https://example.test/apple-supplier",
                        source="Example Wire",
                        published_at=datetime(2026, 8, 26, 9, 0, 0),
                        summary="Supplier summary",
                    )
                ]

        async def run_blocking(func, *args, **kwargs):
            return func(*args, **kwargs)

        async def upsert(stock_id, payload):
            self.stored_payloads.extend(payload)
            return ([{"article_id": "article-1", **item} for item in payload], len(payload))

        self.service._stock_manager_client = lambda: StockManager()
        self.service._news_provider = lambda: Provider()
        self.service._run_blocking = run_blocking
        self.service.upsert_stock_articles = upsert
        self.service._llm_client = lambda: self.llm
        self.service.article_summarize_limiter = FakeLimiter()

    async def test_article_sync_route_maps_finnhub_response_and_persists_articles(self) -> None:
        response = await self.routes.sync_stock_articles("stock-1", outputsize=100)
        self.assertEqual(response.stock_id, "stock-1")
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.stored, 1)
        self.assertEqual(self.stored_payloads[0]["provider"], "finnhub")
        self.assertEqual(self.stored_payloads[0]["provider_summary"], "Supplier summary")

    async def test_article_summarize_route_claims_article_and_uses_mocked_gemini(self) -> None:
        article = {
            "article_id": "article-1",
            "url": "https://example.test/apple-supplier",
            "title": "Apple supplier news",
            "text": "Apple reported supplier improvements and better margins. " * 4,
            "ai_summary_status": "none",
        }

        class ArticlesDb:
            async def get_by_id(_, article_id):
                return dict(article) if article_id == "article-1" else None

            async def claim_for_summary(_, article_id):
                return dict(article) if article_id == "article-1" else None

            async def list_linked_stocks(_, article_id):
                return [{"symbol": "AAPL", "name": "Apple Inc"}]

            async def set_article_text(_, article_id, text):
                article["text"] = text
                return dict(article)

            async def set_summary(_, article_id, **kwargs):
                article.update(kwargs)
                article["ai_summary_updated_at"] = datetime(2026, 8, 26, 14, 0, 0)
                return dict(article)

        self.service.articles_db = ArticlesDb()
        response = await self.routes.summarize_article("article-1")
        self.assertEqual(response.status, "ready")
        self.assertEqual(response.ai_summary, "Article summary from mocked Gemini")
        self.assertTrue(self.llm.sources[0].startswith("Related stocks: Apple Inc (AAPL)"))


class FakeDocumentStorage:
    def __init__(self) -> None:
        self.objects = {"u1/reports/Q2.pdf": b"%PDF-1.4 fake deterministic test pdf"}
        self.created_folders: set[str] = set()
        self.deleted: list[str] = []

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list_objects(self, prefix: str, include_placeholders: bool = False):
        return [
            SimpleNamespace(key=key, size=len(value), last_modified=datetime(2026, 8, 26, 10, 0, 0))
            for key, value in self.objects.items()
            if key.startswith(prefix)
        ]

    async def download_bytes(self, key: str) -> bytes:
        return self.objects[key]

    async def folder_exists(self, key: str) -> bool:
        return key in self.created_folders or key == "u1" or key == "u1/reports"

    async def create_folder(self, key: str) -> None:
        self.created_folders.add(key)

    async def upload_fileobj(self, key: str, fileobj, content_type: str = "application/pdf"):
        data = fileobj.read()
        fileobj.seek(0)
        self.objects[key] = data
        return SimpleNamespace(key=key, size=len(data), last_modified=datetime(2026, 8, 26, 11, 0, 0))

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


class FakeVectorsDb:
    def __init__(self) -> None:
        self.inserted: list[tuple[str, str, list[tuple[int, str, list[float]]]]] = []
        self.deleted_docs: list[tuple[str, str]] = []

    async def delete_document_vectors(self, user_id, document_id, conn=None):
        self.deleted_docs.append((user_id, document_id))
        return 2

    async def insert_chunks(self, user_id, document_id, rows, conn=None):
        self.inserted.append((user_id, document_id, rows))

    async def search_similar(self, query_vector, user_id, document_id, limit):
        return [
            {
                "document_id": document_id or "reports/Q2.pdf",
                "content": "Revenue increased and cash flow improved.",
                "distance": 0.1,
            }
        ]

    async def delete_user_vectors(self, user_id, conn=None):
        return 5


class FakeIngestEventsDb:
    async def current_period_usage(self, user_id):
        return 0, None

    def retry_after_seconds(self, first_ingest):
        return 60

    async def record_successful_ingest(self, user_id, conn=None):
        self.recorded_user_id = user_id

    async def delete_user_quota(self, user_id, conn=None):
        return True


class FakeEmbeddingClient:
    async def embed_texts(self, chunks):
        return [[float(index), 0.5] for index, _chunk in enumerate(chunks)]

    async def embed_query(self, query):
        return [0.25, 0.75]


class DocumentRoutesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "DOCUMENTS"

    async def asyncSetUp(self) -> None:
        self.routes = import_project_module("routers.docs_routes", "common", "doc_agent/backend", model_stubs=True)
        self.service = self.routes.doc_service
        self.storage = FakeDocumentStorage()
        self.vectors = FakeVectorsDb()
        self.events = FakeIngestEventsDb()
        self.llm = FakeLlm("Document answer from mocked Gemini")
        self.service.storage = self.storage
        self.service.vectors_db = self.vectors
        self.service.ingest_events_db = self.events
        self.service.db = SimpleNamespace(transaction=lambda: AsyncTransaction("doc-test-conn"))
        self.service.ingest_limiter = FakeLimiter()
        self.service.ask_limiter = FakeLimiter()
        self.service._embedding_client = lambda: FakeEmbeddingClient()
        self.service._llm_client = lambda: self.llm
        self.service.extract_pdf_blocks = lambda _pdf: [
            SimpleNamespace(kind="prose", section="Overview", text="Revenue increased. Cash flow improved."),
            SimpleNamespace(kind="table", section="Metrics", text="| Metric | Value |\n| --- | --- |\n| Revenue | Up |"),
        ]

    async def test_doc_agent_upload_route_processes_chunks_and_persists_vectors(self) -> None:
        response = await self.routes.upload_document(SimpleModel(user_id="u1", document_id="reports/Q2.pdf"))
        self.assertEqual(response.user_id, "u1")
        self.assertEqual(response.document_id, "reports/Q2.pdf")
        self.assertEqual(response.chunk_count, 2)
        self.assertEqual(self.vectors.inserted[0][0], "u1")
        self.assertIn("Document: Q2.pdf", self.vectors.inserted[0][2][0][1])

    async def test_doc_agent_ask_route_retrieves_vectors_and_uses_mocked_gemini(self) -> None:
        response = await self.routes.ask_document(SimpleModel(user_id="u1", document_id="reports/Q2.pdf", query="What improved?"))
        self.assertEqual(response.answer, "Document answer from mocked Gemini")
        self.assertIn("Revenue increased", response.excerpts[0])
        self.assertTrue(self.llm.messages)

    async def test_doc_agent_delete_vectors_and_purge_user_routes_clean_index_data(self) -> None:
        deleted = await self.routes.delete_document_vectors(user_id="u1", document_id="reports/Q2.pdf")
        purged = await self.routes.purge_user_documents("u1")
        self.assertEqual(deleted.deleted_chunks, 2)
        self.assertEqual(purged.deleted_chunks, 5)
        self.assertTrue(purged.quota_deleted)

    async def test_ui_document_upload_route_stores_pdf_and_calls_doc_agent(self) -> None:
        ui_routes = import_project_module("routers.documents_routes", "common", "ui_service/backend", model_stubs=True)
        ui_service = ui_routes.documents_service
        storage = FakeDocumentStorage()
        storage.objects = {}
        ingests: list[tuple[str, str]] = []

        class DocAgent:
            async def ingest_document(_, user_id, document_id):
                ingests.append((user_id, document_id))
                return {"user_id": user_id, "document_id": document_id, "chunk_count": 1}

        ui_service.storage = storage
        ui_service.doc_agent = DocAgent()
        upload = SimpleNamespace(
            filename="Q3.pdf",
            content_type="application/pdf",
            file=BytesIO(b"%PDF-1.4 uploaded deterministic pdf"),
        )
        response = await ui_routes.upload_file(upload, folder="reports", user={"id": "u1"})
        self.assertEqual(response.path, "reports/Q3.pdf")
        self.assertEqual(ingests, [("u1", "reports/Q3.pdf")])
        self.assertIn("u1/reports/Q3.pdf", storage.objects)


class ChatRoutesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "CHAT / LLM"

    async def asyncSetUp(self) -> None:
        self.routes = import_project_module("routers.chat_routes", "common", "chat_agent/backend", model_stubs=True)
        self.service = self.routes.chat_service
        self.completions = 0
        self.tool_calls: list[tuple[str, str]] = []

        class FakeSessionStore:
            def __init__(_) -> None:
                _.history: dict[str, list[dict[str, str]]] = {}

            @asynccontextmanager
            async def lock(_, user_id):
                yield

            def get_history(_, user_id):
                return list(_.history.get(user_id, []))

            def set_history(_, user_id, history):
                _.history[user_id] = list(history)

            def clear(_, user_id):
                _.history[user_id] = []

        class FakeTools:
            def __init__(_, user_id):
                _.user_id = user_id

            async def execute(_, name, arguments):
                self.tool_calls.append((name, arguments))
                return "AAPL quote is 200.50"

        async def complete(messages, *, temperature, max_tokens, with_tools):
            self.completions += 1
            if with_tools and self.completions == 1:
                return self.service.LLMCompletionResult(
                    content="",
                    model="gemini-test",
                    tool_calls=[SimpleNamespace(id="call-1", name="get_stock_price", arguments='{"symbol":"AAPL"}')],
                )
            return self.service.LLMCompletionResult(
                content="AAPL is trading at 200.50 based on the stock tool.",
                model="gemini-test",
                prompt_tokens=10,
                completion_tokens=8,
                total_tokens=18,
            )

        self.session_store = FakeSessionStore()
        self.service.session_store = self.session_store
        self.service.chat_limiter = FakeLimiter()
        self.service.ChatTools = FakeTools
        self.service._complete = complete

    async def test_chat_agent_route_runs_tool_loop_with_mocked_gemini(self) -> None:
        req = SimpleModel(
            user_id=" u1 ",
            message="What is AAPL doing?",
            document_id="reports/Q2.pdf",
            reset_session=True,
            temperature=0.0,
            max_tokens=64,
        )
        response = await self.routes.create_chat(req)
        self.assertEqual(response.user_id, "u1")
        self.assertEqual(response.model, "gemini-test")
        self.assertEqual(response.usage.total_tokens, 18)
        self.assertEqual(self.tool_calls[0][0], "get_stock_price")
        self.assertEqual(self.session_store.history["u1"][-1]["content"], response.content)

    async def test_chat_agent_rejects_empty_message(self) -> None:
        req = SimpleModel(user_id="u1", message="  ", document_id=None, reset_session=False, temperature=None, max_tokens=None)
        with self.assertRaises(self.service.HTTPException) as caught:
            await self.routes.create_chat(req)
        self.assertEqual(caught.exception.status_code, 400)

    async def test_chat_agent_clear_session_route_removes_history(self) -> None:
        self.session_store.history["u1"] = [{"role": "user", "content": "hello"}]
        response = await self.routes.clear_user_chat("u1")
        self.assertEqual(response.user_id, "u1")
        self.assertEqual(self.session_store.history["u1"], [])

    async def test_ui_chat_route_sends_request_to_chat_agent_client(self) -> None:
        ui_routes = import_project_module("routers.chat_routes", "common", "ui_service/backend", model_stubs=True)
        ui_service = ui_routes.chat_service
        calls: list[dict] = []

        class ChatAgent:
            async def chat(_, user_id, message, document_id=None, reset_session=False):
                calls.append({"user_id": user_id, "message": message, "document_id": document_id, "reset_session": reset_session})
                return {"content": "UI bridge answer", "model": "gemini-test"}

        ui_service.chat_agent = ChatAgent()
        req = SimpleModel(message="Explain my document", document_id="reports/Q2.pdf", reset_session=True)
        response = await ui_routes.create_chat(req, {"id": "u1"})
        self.assertEqual(response.content, "UI bridge answer")
        self.assertEqual(response.model, "gemini-test")
        self.assertEqual(calls[0]["document_id"], "reports/Q2.pdf")


class InternalServiceAuthIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "SERVICE COMMUNICATION"

    async def asyncSetUp(self) -> None:
        self.old_key = os.environ.get("INTERNAL_API_KEY")
        os.environ["INTERNAL_API_KEY"] = "integration-secret"

    async def asyncTearDown(self) -> None:
        if self.old_key is None:
            os.environ.pop("INTERNAL_API_KEY", None)
        else:
            os.environ["INTERNAL_API_KEY"] = self.old_key

    async def test_internal_api_key_auth_accepts_shared_key(self) -> None:
        deps = import_project_module("deps", "chat_agent/backend", model_stubs=True)
        self.assertIsNone(await deps.verify_internal_api_key("integration-secret"))

    async def test_internal_api_key_auth_rejects_invalid_key(self) -> None:
        deps = import_project_module("deps", "news_agent/backend", model_stubs=True)
        with self.assertRaises(deps.HTTPException) as caught:
            await deps.verify_internal_api_key("wrong-key")
        self.assertEqual(caught.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

