from types import SimpleNamespace
import unittest

from test_support import import_project_module

llm_client_module = import_project_module("llm_provider_client.client", "common")
llm_util = import_project_module("llm_provider_client.util", "common")
embedding_module = import_project_module("embedding_client.client", "common")


class LlmClientTests(unittest.IsolatedAsyncioTestCase):
    def test_split_model_ids_and_unavailable_detection(self) -> None:
        self.assertEqual(llm_util.split_model_ids(" a, b; c ,,"), ["a", "b", "c"])
        self.assertTrue(llm_util.is_model_unavailable(RuntimeError("429 rate limit")))
        self.assertFalse(llm_util.is_model_unavailable(ValueError("bad prompt")))

    def test_normalize_model_adds_gemini_provider_prefix(self) -> None:
        self.assertEqual(llm_client_module.LLMProviderClient._normalize_model("gemini-2.5-flash"), "gemini/gemini-2.5-flash")

    async def test_chat_completion_falls_back_between_models_and_extracts_usage_and_tools(self) -> None:
        responses = []
        async def fake_completion(**kwargs):
            responses.append(kwargs["model"])
            if kwargs["model"] == "bad-model":
                raise RuntimeError("503 unavailable")
            message = SimpleNamespace(content="answer", tool_calls=[SimpleNamespace(id="t1", function=SimpleNamespace(name="tool", arguments="{}"))])
            usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model=kwargs["model"])
        llm_client_module.acompletion = fake_completion
        client = llm_client_module.LLMProviderClient(model="bad-model")
        client.models = ["bad-model", "good-model"]

        result = await client.chat_completion([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])

        self.assertEqual(responses, ["bad-model", "good-model"])
        self.assertEqual(result.content, "answer")
        self.assertEqual(result.tool_calls[0].name, "tool")
        self.assertEqual(result.total_tokens, 3)

    async def test_chat_completion_rejects_empty_messages_and_empty_vendor_response(self) -> None:
        client = llm_client_module.LLMProviderClient(model="fake")
        with self.assertRaises(ValueError):
            await client.chat_completion([])
        async def fake_completion(**_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[]))], usage=None, model="fake")
        llm_client_module.acompletion = fake_completion
        with self.assertRaises(RuntimeError):
            await client.chat_completion([{"role": "user", "content": "hi"}])

    async def test_summarize_wraps_untrusted_text_and_quote_context(self) -> None:
        captured = {}
        async def fake_chat(messages, **kwargs):
            captured["messages"] = messages
            return llm_util.LLMCompletionResult(content="summary", model="fake")
        client = llm_client_module.LLMProviderClient(model="fake")
        client.chat_completion = fake_chat

        await client.summarize("news text", symbol="aapl", close=10, change=1, percent_change=2)

        user_content = captured["messages"][-1]["content"]
        self.assertIn("Current quote: close=10", user_content)
        self.assertIn("<<<UNTRUSTED_DATA>>>", user_content)


class EmbeddingClientTests(unittest.IsolatedAsyncioTestCase):
    def test_constructor_validates_dimensions_and_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            embedding_module.EmbeddingClient(model="fake", dimensions=0)
        with self.assertRaises(ValueError):
            embedding_module.EmbeddingClient(model="fake", dimensions=2, batch_size=0)

    def test_extract_vectors_orders_by_index_and_validates_dimensions(self) -> None:
        client = embedding_module.EmbeddingClient(model="fake", dimensions=2)
        response = {"data": [{"index": 1, "embedding": [3, 4]}, {"index": 0, "embedding": [1, 2]}]}
        self.assertEqual(client._extract_vectors(response, expected=2), [[1.0, 2.0], [3.0, 4.0]])
        with self.assertRaises(RuntimeError):
            client._extract_vectors({"data": [{"index": 0, "embedding": [1]}]}, expected=1)

    async def test_embed_texts_batches_vendor_calls_without_real_api(self) -> None:
        calls = []
        async def fake_embedding(**kwargs):
            calls.append(kwargs["input"])
            return {"data": [{"index": index, "embedding": [float(index), 1.0]} for index, _ in enumerate(kwargs["input"])]}
        embedding_module.aembedding = fake_embedding
        client = embedding_module.EmbeddingClient(model="fake", dimensions=2, batch_size=2)

        vectors = await client.embed_texts(["a", "b", "c"])

        self.assertEqual(len(vectors), 3)
        self.assertEqual(calls, [["a", "b"], ["c"]])

    async def test_embed_query_rejects_blank_text(self) -> None:
        client = embedding_module.EmbeddingClient(model="fake", dimensions=2)
        with self.assertRaises(ValueError):
            await client.embed_query("  ")


if __name__ == "__main__":
    unittest.main()
