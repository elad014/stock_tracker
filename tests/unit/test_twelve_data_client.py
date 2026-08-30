from datetime import date
import unittest

from test_support import FakeResponse, import_project_module

twelve_module = import_project_module("stock_provider_client.twelv_data_client", "common")
TwelveDataClient = twelve_module.TwelveDataClient


class StubTwelveClient(TwelveDataClient):
    def __init__(self, responses):
        self.api_key = "key"
        self.responses = list(responses)
        self.calls = []

    def request(self, endpoint, params=None, method="GET"):
        self.calls.append((endpoint, params, method))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TwelveDataClientTests(unittest.TestCase):
    def test_constructor_requires_api_key(self) -> None:
        with self.assertRaises(ValueError):
            TwelveDataClient(api_key="")

    def test_get_quote_maps_api_payload_to_quote_data_including_open(self) -> None:
        client = StubTwelveClient([{
            "symbol": "aapl",
            "name": "Apple Inc.",
            "close": "200.5",
            "change": "1.2",
            "percent_change": "0.60",
            "previous_close": "199.3",
            "open": "199.8",
            "high": "202",
            "low": "198",
            "volume": "12345",
            "fifty_two_week": {"high": "250", "low": "150"},
            "exchange": "NASDAQ",
        }])

        quote = client.get_quote(" aapl ")

        self.assertEqual(quote.symbol, "AAPL")
        self.assertEqual(quote.open, 199.8)
        self.assertEqual(quote.volume, 12345)

    def test_get_quote_retries_hyphen_symbol_as_dot_symbol(self) -> None:
        client = StubTwelveClient([RuntimeError("Symbol not found: BRK-A"), {"symbol": "BRK.A", "name": "Berkshire", "close": "1"}])

        quote = client.get_quote("BRK-A")

        self.assertEqual(quote.symbol, "BRK.A")
        self.assertEqual(client.calls[1][1]["symbol"], "BRK.A")

    def test_get_daily_time_series_skips_invalid_dates(self) -> None:
        client = StubTwelveClient([{"values": [{"datetime": "2026-08-26", "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}, {"datetime": "bad"}]}])

        bars = client.get_daily_time_series("aapl", date(2026, 8, 1), date(2026, 8, 26))

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].date, date(2026, 8, 26))

    def test_request_maps_twelve_data_error_payloads(self) -> None:
        client = TwelveDataClient(api_key="key")
        twelve_module.requests.get = lambda *_args, **_kwargs: FakeResponse(payload={"status": "error", "code": 404, "message": "symbol not found"})

        with self.assertRaisesRegex(RuntimeError, "Symbol not found"):
            client.request("quote", {"symbol": "BAD"})

    def test_request_rejects_unsupported_method(self) -> None:
        with self.assertRaises(ValueError):
            TwelveDataClient(api_key="key").request("quote", method="PATCH")

    def test_is_market_open_handles_list_and_dict_payloads(self) -> None:
        self.assertTrue(StubTwelveClient([[{"exchange": "NASDAQ", "is_market_open": True}]]).is_market_open("NASDAQ"))
        self.assertFalse(StubTwelveClient([{"is_market_open": False}]).is_market_open("NASDAQ"))


if __name__ == "__main__":
    unittest.main()
