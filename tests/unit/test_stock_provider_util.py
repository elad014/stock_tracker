from datetime import date
import unittest

from test_support import load_module

stock_util = load_module("stock_provider_util_under_test", "common/stock_provider_client/util.py")

parse_date = stock_util.parse_date
to_float = stock_util.to_float
to_int = stock_util.to_int


class StockProviderUtilTests(unittest.TestCase):
    def test_to_float_converts_numeric_values(self) -> None:
        self.assertEqual(to_float("123.45"), 123.45)
        self.assertEqual(to_float(10), 10.0)
        self.assertIsNone(to_float(""))
        self.assertIsNone(to_float(None))
        self.assertIsNone(to_float("not-a-number"))

    def test_to_int_converts_numeric_values(self) -> None:
        self.assertEqual(to_int("123.9"), 123)
        self.assertEqual(to_int(10), 10)
        self.assertIsNone(to_int(""))
        self.assertIsNone(to_int(None))
        self.assertIsNone(to_int("not-a-number"))

    def test_parse_date_accepts_iso_date_and_datetime(self) -> None:
        self.assertEqual(parse_date("2026-08-26"), date(2026, 8, 26))
        self.assertEqual(parse_date("2026-08-26T12:30:00Z"), date(2026, 8, 26))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date("26/08/2026"))

    def test_parse_date_preserves_provider_calendar_date_at_timezone_boundaries(self) -> None:
        """Preserve daily candle calendar dates around midnight and DST offsets."""
        self.assertEqual(stock_util.parse_date("2026-03-27T00:30:00+03:00"), date(2026, 3, 27))
        self.assertEqual(stock_util.parse_date("2026-10-25T23:30:00+02:00"), date(2026, 10, 25))
        self.assertEqual(stock_util.parse_date("2026-08-26T21:30:00Z"), date(2026, 8, 26))

if __name__ == "__main__":
    unittest.main()

