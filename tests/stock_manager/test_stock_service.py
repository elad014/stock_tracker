from datetime import date as real_date

import pytest
from fastapi import HTTPException

from conftest import load_backend_module
from stock_provider_client import QuoteData


stock_service = load_backend_module("stock_manager", "services.stock_service")
stock_models = load_backend_module("stock_manager", "models.stocks")


class FrozenDate(real_date):
    @classmethod
    def today(cls):
        return cls(2026, 8, 30)


def _quote_row(**overrides):
    row = {
        "stock_id": "stock-1",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "close": 200.0,
        "change": 1.5,
        "percent_change": 0.75,
        "previous_close": 198.5,
        "open": 199.0,
        "high": 201.0,
        "low": 197.0,
        "volume": 12345,
        "fifty_two_week_high": 250.0,
        "fifty_two_week_low": 150.0,
        "stock_summery": "Summary",
        "stock_news_published_at": None,
    }
    row.update(overrides)
    return row


def _quote_data(symbol="AAPL"):
    return QuoteData(
        symbol=symbol,
        name="Apple Inc.",
        close=200.0,
        change=1.5,
        percent_change=0.75,
    )


def test_history_start_for_range_accepts_supported_ranges(monkeypatch):
    monkeypatch.setenv("HISTORY_RETENTION_YEARS", "5")
    today = real_date(2026, 8, 30)

    assert stock_service._history_start_for_range("1D", today) == real_date(2026, 8, 29)
    assert stock_service._history_start_for_range("5D", today) == real_date(2026, 8, 25)
    assert stock_service._history_start_for_range("1M", today) == real_date(2026, 7, 31)
    assert stock_service._history_start_for_range("3M", today) == real_date(2026, 6, 1)
    assert stock_service._history_start_for_range("6M", today) == real_date(2026, 3, 3)
    assert stock_service._history_start_for_range("1Y", today) == real_date(2025, 8, 30)
    assert stock_service._history_start_for_range("5Y", today) == real_date(2021, 8, 30)


def test_history_start_for_range_rejects_invalid_range():
    with pytest.raises(HTTPException) as exc_info:
        stock_service._history_start_for_range("2Y", real_date(2026, 8, 30))

    assert exc_info.value.status_code == 400


def test_quote_to_response_maps_row_fields():
    result = stock_service._quote_to_response(_quote_row(), open_price=201.5)

    assert result.stock_id == "stock-1"
    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.close == 200.0
    assert result.open == 201.5
    assert result.stock_summery == "Summary"


def test_with_today_close_appends_latest_quote(monkeypatch):
    monkeypatch.setattr(stock_service, "date", FrozenDate)
    bars = [
        stock_models.StockHistoryBar(
            date="2026-08-29",
            open=190.0,
            high=195.0,
            low=189.0,
            close=194.0,
            volume=1000,
        )
    ]

    result = stock_service._with_today_close(bars, _quote_row(close=200.0), None)

    assert [bar.date for bar in result] == ["2026-08-29", "2026-08-30"]
    assert result[-1].close == 200.0


def test_with_today_close_replaces_existing_today_bar(monkeypatch):
    monkeypatch.setattr(stock_service, "date", FrozenDate)
    bars = [
        stock_models.StockHistoryBar(
            date="2026-08-30",
            open=None,
            high=198.0,
            low=190.0,
            close=195.0,
            volume=None,
        )
    ]

    result = stock_service._with_today_close(
        bars,
        _quote_row(open=196.0, high=202.0, low=191.0, close=201.0, volume=5000),
        None,
    )

    assert len(result) == 1
    assert result[0].open == 196.0
    assert result[0].high == 202.0
    assert result[0].low == 191.0
    assert result[0].close == 201.0
    assert result[0].volume == 5000


@pytest.mark.asyncio
async def test_add_to_watchlist_maps_invalid_symbol_to_404(monkeypatch):
    class Provider:
        def get_quote(self, _symbol):
            raise RuntimeError("invalid symbol")

    async def run_provider(func, *args):
        return func(*args)

    monkeypatch.setattr(stock_service, "_provider", lambda: Provider())
    monkeypatch.setattr(stock_service, "_run_provider", run_provider)

    with pytest.raises(HTTPException) as exc_info:
        await stock_service.add_to_watchlist("user-1", "bad")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_to_watchlist_maps_provider_error_to_502(monkeypatch):
    class Provider:
        def get_quote(self, _symbol):
            raise RuntimeError("timeout")

    async def run_provider(func, *args):
        return func(*args)

    monkeypatch.setattr(stock_service, "_provider", lambda: Provider())
    monkeypatch.setattr(stock_service, "_run_provider", run_provider)

    with pytest.raises(HTTPException) as exc_info:
        await stock_service.add_to_watchlist("user-1", "AAPL")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_add_to_watchlist_refreshes_existing_stock(monkeypatch):
    calls = {}

    class Provider:
        def get_quote(self, symbol):
            return _quote_data(symbol)

    async def run_provider(func, *args):
        return func(*args)

    async def get_by_symbol(symbol):
        calls["symbol"] = symbol
        return _quote_row()

    async def refresh(user_id, existing, quote):
        calls["refresh"] = (user_id, existing["stock_id"], quote.symbol)
        return stock_service._quote_to_response(existing)

    monkeypatch.setattr(stock_service, "_provider", lambda: Provider())
    monkeypatch.setattr(stock_service, "_run_provider", run_provider)
    monkeypatch.setattr(stock_service.quotes_db, "get_by_symbol", get_by_symbol)
    monkeypatch.setattr(stock_service, "_refresh_existing_and_watch", refresh)

    result = await stock_service.add_to_watchlist("user-1", " aapl ")

    assert result.symbol == "AAPL"
    assert calls["symbol"] == "AAPL"
    assert calls["refresh"] == ("user-1", "stock-1", "AAPL")


@pytest.mark.asyncio
async def test_add_to_watchlist_restores_archived_stock(monkeypatch):
    calls = {}

    class Provider:
        def get_quote(self, symbol):
            return _quote_data(symbol)

    async def run_provider(func, *args):
        return func(*args)

    async def get_by_symbol(_symbol):
        return None

    async def get_archived_stock_by_symbol(symbol):
        calls["archived_symbol"] = symbol
        return {"stock_id": "archived-1", "name": "Archived Apple"}

    async def restore(user_id, archived, quote):
        calls["restore"] = (user_id, archived["stock_id"], quote.symbol)
        return stock_service._quote_to_response(_quote_row(stock_id=archived["stock_id"]))

    monkeypatch.setattr(stock_service, "_provider", lambda: Provider())
    monkeypatch.setattr(stock_service, "_run_provider", run_provider)
    monkeypatch.setattr(stock_service.quotes_db, "get_by_symbol", get_by_symbol)
    monkeypatch.setattr(
        stock_service.archive_db,
        "get_archived_stock_by_symbol",
        get_archived_stock_by_symbol,
    )
    monkeypatch.setattr(stock_service, "_restore_archived_and_watch", restore)

    result = await stock_service.add_to_watchlist("user-1", "AAPL")

    assert result.stock_id == "archived-1"
    assert calls["archived_symbol"] == "AAPL"
    assert calls["restore"] == ("user-1", "archived-1", "AAPL")


@pytest.mark.asyncio
async def test_add_to_watchlist_creates_new_stock(monkeypatch):
    calls = {}

    class Provider:
        def get_quote(self, symbol):
            return _quote_data(symbol)

    async def run_provider(func, *args):
        return func(*args)

    async def get_by_symbol(_symbol):
        return None

    async def get_archived_stock_by_symbol(_symbol):
        return None

    async def create_new(user_id, quote):
        calls["create"] = (user_id, quote.symbol)
        return stock_service._quote_to_response(_quote_row())

    monkeypatch.setattr(stock_service, "_provider", lambda: Provider())
    monkeypatch.setattr(stock_service, "_run_provider", run_provider)
    monkeypatch.setattr(stock_service.quotes_db, "get_by_symbol", get_by_symbol)
    monkeypatch.setattr(
        stock_service.archive_db,
        "get_archived_stock_by_symbol",
        get_archived_stock_by_symbol,
    )
    monkeypatch.setattr(stock_service, "_create_new_and_watch", create_new)

    result = await stock_service.add_to_watchlist("user-1", "AAPL")

    assert result.symbol == "AAPL"
    assert calls["create"] == ("user-1", "AAPL")
