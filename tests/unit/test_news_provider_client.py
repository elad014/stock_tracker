from datetime import date, datetime, timezone
import unittest

from test_support import FakeResponse, import_project_module

news_provider_module = import_project_module("news_provider_client.client", "common")
NewsProviderClient = news_provider_module.NewsProviderClient
NewsItem = news_provider_module.NewsItem
util = import_project_module("news_provider_client.util", "common")


class StubNewsProvider(NewsProviderClient):
    def __init__(self, payload):
        self.api_key = "key"
        self.payload = payload
        self.calls = []

    def request(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class NewsProviderClientTests(unittest.TestCase):
    def test_constructor_requires_api_key(self) -> None:
        with self.assertRaises(ValueError):
            NewsProviderClient(api_key="")

    def test_parse_unix_datetime_and_optional_str(self) -> None:
        self.assertEqual(util.parse_unix_datetime(1787702400), datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc))
        self.assertIsNone(util.parse_unix_datetime("bad"))
        self.assertEqual(util.to_optional_str(" source "), "source")
        self.assertIsNone(util.to_optional_str("  "))

    def test_get_news_validates_symbol_and_date_range(self) -> None:
        client = StubNewsProvider([])
        with self.assertRaises(ValueError):
            client.get_news("  ", start=date(2026, 8, 26), end=date(2026, 8, 26))
        with self.assertRaises(ValueError):
            client.get_news("AAPL", start=date(2026, 8, 27), end=date(2026, 8, 26))

    def test_get_news_parses_list_payload_and_skips_bad_rows(self) -> None:
        client = StubNewsProvider([
            {"headline": "Apple news", "url": "https://x", "datetime": 1787702400, "source": "Finnhub", "summary": "short"},
            {"headline": ""},
            "bad",
        ])

        items = client.get_news(" aapl ", start=date(2026, 8, 26), end=date(2026, 8, 26), limit=10)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Apple news")
        self.assertEqual(client.calls[0][1]["symbol"], "AAPL")

    def test_parse_items_raises_symbol_not_found_from_error_payload(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Symbol not found"):
            StubNewsProvider({})._parse_items({"error": "symbol not found"}, symbol="BAD")

    def test_request_maps_http_status_errors(self) -> None:
        client = NewsProviderClient(api_key="key")
        news_provider_module.requests.get = lambda *_args, **_kwargs: FakeResponse(status_code=429, payload={})

        with self.assertRaisesRegex(RuntimeError, "rate limit"):
            client.request("company-news", {"symbol": "AAPL"})


if __name__ == "__main__":
    unittest.main()

