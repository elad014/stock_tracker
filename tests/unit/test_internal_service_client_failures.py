from types import SimpleNamespace
import unittest

from test_support import FakeResponse, import_project_module


class InvalidJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("not json")


class FakeAsyncClient:
    response = FakeResponse(payload={})
    error = None
    calls: list[tuple[str, str, dict]] = []

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request("DELETE", url, **kwargs)


class InternalServiceClientFailureRegressionTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "SERVICE COMMUNICATION"

    def reset_fake_client(self, module, response=None, error=None) -> None:
        FakeAsyncClient.response = response or FakeResponse(payload={})
        FakeAsyncClient.error = error
        FakeAsyncClient.calls = []
        module.httpx.AsyncClient = FakeAsyncClient

    async def test_stock_manager_unavailable_returns_controlled_gateway_error(self) -> None:
        """Return a controlled error when stock-manager is unavailable."""
        module = import_project_module("stock_manager_client.client", "common")
        self.reset_fake_client(module, error=module.httpx.RequestError("network down"))

        with self.assertRaises(module.HTTPException) as caught:
            await module.StockManagerClient(base_url="http://stock", api_key="key").list_stocks()

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail, "Failed to reach stock manager")

    async def test_stock_manager_invalid_success_payload_returns_controlled_error(self) -> None:
        """Reject stock-manager 200 responses with the wrong JSON shape."""
        module = import_project_module("stock_manager_client.client", "common")
        self.reset_fake_client(module, response=FakeResponse(status_code=200, payload={"not": "a list"}))

        with self.assertRaises(module.HTTPException) as caught:
            await module.StockManagerClient(base_url="http://stock", api_key="key").get_stock_history("s1")

        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn("invalid response", caught.exception.detail)

    async def test_news_agent_invalid_json_returns_controlled_gateway_error(self) -> None:
        """Reject news-agent 200 responses with malformed JSON."""
        module = import_project_module("news_agent_client.client", "common")
        self.reset_fake_client(module, response=InvalidJsonResponse(status_code=200))

        with self.assertRaises(module.HTTPException) as caught:
            await module.NewsAgentClient(base_url="http://news", api_key="key").get_news("AAPL")

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail, "News agent returned invalid JSON")

    async def test_doc_agent_unavailable_returns_controlled_gateway_error(self) -> None:
        """Return a controlled error when doc-agent is unavailable."""
        module = import_project_module("doc_agent_client.client", "common")
        self.reset_fake_client(module, error=module.httpx.RequestError("network down"))

        with self.assertRaises(module.HTTPException) as caught:
            await module.DocAgentClient(base_url="http://docs", api_key="key").ask_document("u1", None, "question")

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail, "Failed to reach doc agent")

    async def test_chat_agent_malformed_success_payload_returns_controlled_error(self) -> None:
        """Reject chat-agent 200 responses with malformed JSON."""
        module = import_project_module("chat_agent_client.client", "common")
        self.reset_fake_client(module, response=InvalidJsonResponse(status_code=200))

        with self.assertRaises(module.HTTPException) as caught:
            await module.ChatAgentClient(base_url="http://chat", api_key="key").chat("u1", "hello")

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(caught.exception.detail, "Chat agent returned invalid JSON")

    async def test_internal_service_http_500_preserves_service_detail(self) -> None:
        """Preserve useful detail from internal service HTTP 500 responses."""
        module = import_project_module("news_agent_client.client", "common")
        self.reset_fake_client(module, response=FakeResponse(status_code=500, payload={"detail": "provider exploded"}))

        with self.assertRaises(module.HTTPException) as caught:
            await module.NewsAgentClient(base_url="http://news", api_key="key").get_news("AAPL")

        self.assertEqual(caught.exception.status_code, 500)
        self.assertEqual(caught.exception.detail, "provider exploded")


if __name__ == "__main__":
    unittest.main()
