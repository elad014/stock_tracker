from datetime import date

from stock_provider_client.util import parse_date, to_float, to_int


def test_to_float_converts_numeric_values():
    assert to_float("12.34") == 12.34
    assert to_float(5) == 5.0
    assert to_float("") is None
    assert to_float(None) is None
    assert to_float("not-a-number") is None


def test_to_int_converts_numeric_values():
    assert to_int("12") == 12
    assert to_int("12.9") == 12
    assert to_int(7.2) == 7
    assert to_int("") is None
    assert to_int(None) is None
    assert to_int("not-a-number") is None


def test_parse_date_accepts_iso_date_and_datetime():
    assert parse_date("2026-08-30") == date(2026, 8, 30)
    assert parse_date("2026-08-30T10:15:00Z") == date(2026, 8, 30)
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("bad-date") is None
