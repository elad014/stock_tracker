from datetime import date, datetime, timezone
from typing import Any

import pytest
from conftest import load_backend_module

articles_db = load_backend_module("news_service", "db_logics.articles_db_logic")


def _row(article_id: str, day: int, hour: int = 12) -> dict[str, Any]:
    return {
        "article_id": article_id,
        "published_at": datetime(2026, 10, day, hour, tzinfo=timezone.utc),
        "created_at": datetime(2026, 10, day, hour, tzinfo=timezone.utc),
    }


def test_spread_article_ids_keeps_every_day_inside_the_limit() -> None:
    rows: list[dict[str, Any]] = []
    for day, count in ((25, 40), (24, 40), (23, 40), (22, 10), (21, 10), (20, 10), (19, 10)):
        for index in range(count):
            rows.append(_row(f"{day}-{index}", day, hour=23 - (index % 20)))

    chosen: list[str] = articles_db.spread_article_ids(rows, 100)
    days: set[int] = {int(article_id.split("-")[0]) for article_id in chosen}

    assert len(chosen) == 100
    assert days == {19, 20, 21, 22, 23, 24, 25}
    chosen_days: list[int] = [int(article_id.split("-")[0]) for article_id in chosen]
    assert chosen_days == sorted(chosen_days, reverse=True)


def test_parse_news_day_accepts_a_day_inside_the_window() -> None:
    chosen, tz_name = articles_db.parse_news_day(
        "2026-10-23",
        "Asia/Jerusalem",
        today=date(2026, 10, 25),
    )

    assert chosen == date(2026, 10, 23)
    assert tz_name == "Asia/Jerusalem"


def test_parse_news_day_rejects_a_day_outside_the_window() -> None:
    with pytest.raises(ValueError, match="7-day"):
        articles_db.parse_news_day(
            "2026-10-01",
            "Asia/Jerusalem",
            today=date(2026, 10, 25),
        )


def test_parse_news_day_blank_means_the_mixed_list() -> None:
    chosen, tz_name = articles_db.parse_news_day("", None, today=date(2026, 10, 25))

    assert chosen is None
    assert tz_name == "UTC"


def test_spread_article_ids_returns_every_row_when_under_the_limit() -> None:
    rows: list[dict[str, Any]] = [_row("25-0", 25), _row("19-0", 19)]

    chosen: list[str] = articles_db.spread_article_ids(rows, 100)

    assert chosen == ["25-0", "19-0"]
