import hashlib
from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import asyncpg

from constant import ARTICLE_EXTRACT_MIN_CHARS, ARTICLE_RETENTION_DAYS
from clients.database_client import db

ARTICLES_TABLE = "news_articles"
STOCK_ARTICLES_TABLE = "stock_articles"
# Owned by stock_service. news_db_user holds USAGE on stock_schema and SELECT
# on this one table, and stock_schema is kept off its search_path, so every
# reference has to be schema-qualified.
QUOTES_TABLE = "stock_schema.stock_quotes"

SUMMARY_STATUS_NONE = "none"
SUMMARY_STATUS_PENDING = "pending"
SUMMARY_STATUS_READY = "ready"
SUMMARY_STATUS_FAILED = "failed"

# A claim older than this is treated as abandoned (crashed worker / redeploy).
_STALE_CLAIM_MINUTES = 3

_ARTICLE_COLUMNS = (
    "article_id, url_hash, url, title, source, published_at, "
    "provider, provider_summary, text, "
    "ai_summary, ai_summary_status, ai_summary_model, ai_summary_error, "
    "ai_summary_started_at, ai_summary_updated_at, created_at"
)
_ARTICLE_COLUMNS_A = ", ".join(
    f"a.{column.strip()}" for column in _ARTICLE_COLUMNS.split(",")
)


def normalize_url(url: str) -> str:
    """Drop the fragment and trailing slash so the same article hashes once."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def hash_url(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def _normalize_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalize_article(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": str(row["article_id"]),
        "url": row["url"],
        "title": row["title"],
        "source": row.get("source"),
        "published_at": _normalize_datetime(row.get("published_at")),
        "provider": row.get("provider"),
        "provider_summary": row.get("provider_summary"),
        "text": row.get("text"),
        "ai_summary": row.get("ai_summary"),
        "ai_summary_status": row.get("ai_summary_status") or SUMMARY_STATUS_NONE,
        "ai_summary_model": row.get("ai_summary_model"),
        "ai_summary_error": row.get("ai_summary_error"),
        "ai_summary_updated_at": _normalize_datetime(row.get("ai_summary_updated_at")),
    }


async def upsert_article(
    url: str,
    title: str,
    source: Optional[str] = None,
    published_at: Optional[datetime] = None,
    provider: str = "finnhub",
    provider_summary: Optional[str] = None,
    text: Optional[str] = None,
    conn: Optional[asyncpg.Connection] = None,
) -> tuple[dict[str, Any], bool]:
    """Insert or refresh an article by URL. Never overwrites a stored full text body.

    The bool is True only on a real INSERT (xmax = 0). ON CONFLICT updates
    return False so callers can skip repeat LLM work.
    """
    row = await db.fetch_one(
        f"""
        INSERT INTO {ARTICLES_TABLE} (
            article_id, url_hash, url, title, source, published_at,
            provider, provider_summary, text
        )
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (url_hash) DO UPDATE SET
            title = EXCLUDED.title,
            source = COALESCE(EXCLUDED.source, {ARTICLES_TABLE}.source),
            published_at = COALESCE(
                EXCLUDED.published_at, {ARTICLES_TABLE}.published_at
            ),
            provider_summary = COALESCE(
                EXCLUDED.provider_summary, {ARTICLES_TABLE}.provider_summary
            ),
            text = COALESCE({ARTICLES_TABLE}.text, EXCLUDED.text)
        RETURNING {_ARTICLE_COLUMNS}, (xmax = 0) AS inserted
        """,
        str(uuid4()),
        hash_url(url),
        url,
        title,
        source,
        published_at,
        provider,
        provider_summary,
        text,
        conn=conn,
    )
    assert row is not None
    return _normalize_article(row), bool(row["inserted"])


async def link_article_to_stock(
    stock_id: str,
    article_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    """True when this stock was not already linked to the article."""
    row = await db.fetch_one(
        f"""
        INSERT INTO {STOCK_ARTICLES_TABLE} (stock_id, article_id)
        VALUES ($1::uuid, $2::uuid)
        ON CONFLICT (stock_id, article_id) DO NOTHING
        RETURNING article_id
        """,
        stock_id,
        article_id,
        conn=conn,
    )
    return row is not None


def _row_day(row: dict[str, Any]) -> date:
    value: Any = row.get("published_at") or row.get("created_at")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_news_day(
    day: str | None,
    timezone_name: str | None,
    *,
    today: date | None = None,
) -> tuple[date | None, str]:
    """Validate a chosen news day in the viewer's timezone.

    An empty day means the mixed 7-day list. A specific day must fall inside
    the retention window for that timezone.
    """
    tz_name: str = (timezone_name or "UTC").strip() or "UTC"
    try:
        zone: ZoneInfo = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError("Invalid timezone") from exc
    if day is None or not str(day).strip():
        return None, tz_name
    try:
        chosen: date = date.fromisoformat(str(day).strip())
    except ValueError as exc:
        raise ValueError("Invalid day") from exc
    current: date = today if today is not None else datetime.now(zone).date()
    oldest: date = current - timedelta(days=ARTICLE_RETENTION_DAYS - 1)
    if chosen < oldest or chosen > current:
        raise ValueError("Day is outside the 7-day news window")
    return chosen, tz_name


def spread_article_ids(rows: list[dict[str, Any]], limit: int) -> list[str]:
    """Pick up to ``limit`` ids so every day in ``rows`` stays on the page.

    ``rows`` must be newest first. Each day gets an equal share of the limit.
    Days with fewer articles give their unused slots to newer leftovers.
    """
    capped: int = max(0, int(limit))
    if capped == 0 or not rows:
        return []

    by_day: dict[date, list[dict[str, Any]]] = {}
    day_order: list[date] = []
    for row in rows:
        day: date = _row_day(row)
        if day not in by_day:
            by_day[day] = []
            day_order.append(day)
        by_day[day].append(row)

    per_day: int = max(1, capped // len(by_day))
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()
    for day in day_order:
        if len(chosen) >= capped:
            break
        for row in by_day[day][:per_day]:
            if len(chosen) >= capped:
                break
            article_id: str = str(row["article_id"])
            chosen.append(row)
            chosen_ids.add(article_id)

    if len(chosen) < capped:
        for row in rows:
            article_id = str(row["article_id"])
            if article_id in chosen_ids:
                continue
            chosen.append(row)
            chosen_ids.add(article_id)
            if len(chosen) >= capped:
                break

    chosen.sort(
        key=lambda row: str(row.get("published_at") or row.get("created_at") or ""),
        reverse=True,
    )
    return [str(row["article_id"]) for row in chosen]


async def _articles_in_order(
    article_ids: list[str],
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    if not article_ids:
        return []
    rows = await db.fetch_all(
        f"""
        SELECT {_ARTICLE_COLUMNS}
        FROM {ARTICLES_TABLE}
        WHERE article_id = ANY($1::uuid[])
        """,
        article_ids,
        conn=conn,
    )
    by_id: dict[str, Any] = {str(row["article_id"]): row for row in rows}
    ordered = [by_id[article_id] for article_id in article_ids if article_id in by_id]
    return [_normalize_article(row) for row in ordered]


async def list_by_stock(
    stock_id: str,
    limit: int = 10,
    day: date | None = None,
    timezone_name: str = "UTC",
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Articles from the retention window.

    With no day, the result is spread across the window so one busy day cannot
    hide the rest of the week. With a day, every returned article is from that
    calendar day in ``timezone_name``.
    """
    capped: int = max(1, int(limit))
    if day is not None:
        index_rows = await db.fetch_all(
            f"""
            SELECT a.article_id
            FROM {ARTICLES_TABLE} a
            INNER JOIN {STOCK_ARTICLES_TABLE} sa ON sa.article_id = a.article_id
            WHERE sa.stock_id = $1::uuid
              AND (COALESCE(a.published_at, a.created_at) AT TIME ZONE $2)::date = $3::date
            ORDER BY a.published_at DESC NULLS LAST, a.created_at DESC
            LIMIT $4
            """,
            stock_id,
            timezone_name,
            day,
            capped,
            conn=conn,
        )
        return await _articles_in_order(
            [str(row["article_id"]) for row in index_rows],
            conn=conn,
        )

    index_rows = await db.fetch_all(
        f"""
        SELECT a.article_id, a.published_at, a.created_at
        FROM {ARTICLES_TABLE} a
        INNER JOIN {STOCK_ARTICLES_TABLE} sa ON sa.article_id = a.article_id
        WHERE sa.stock_id = $1::uuid
          AND COALESCE(a.published_at, a.created_at)::date
              >= (CURRENT_DATE - ($2::int - 1))
        ORDER BY a.published_at DESC NULLS LAST, a.created_at DESC
        """,
        stock_id,
        max(1, ARTICLE_RETENTION_DAYS),
        conn=conn,
    )
    return await _articles_in_order(spread_article_ids(index_rows, capped), conn=conn)


async def list_linked_stocks(
    article_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Symbols and names linked to this article via stock_articles."""
    rows = await db.fetch_all(
        f"""
        SELECT sq.symbol, sq.name
        FROM {STOCK_ARTICLES_TABLE} sa
        JOIN {QUOTES_TABLE} sq ON sa.stock_id = sq.stock_id
        WHERE sa.article_id = $1::uuid
        ORDER BY sq.symbol
        """,
        article_id,
        conn=conn,
    )
    linked: list[dict[str, Any]] = []
    for row in rows:
        linked.append(
            {
                "symbol": str(row.get("symbol") or "").strip().upper(),
                "name": str(row.get("name") or "").strip(),
            }
        )
    return linked


async def get_by_id(
    article_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        SELECT {_ARTICLE_COLUMNS}
        FROM {ARTICLES_TABLE}
        WHERE article_id = $1::uuid
        """,
        article_id,
        conn=conn,
    )
    return _normalize_article(row) if row else None


async def list_articles_needing_extract(
    days: int = 7,
    limit: int = 30,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Recent rows whose ``text`` is empty or still the provider blurb."""
    rows = await db.fetch_all(
        f"""
        SELECT {_ARTICLE_COLUMNS}
        FROM {ARTICLES_TABLE}
        WHERE COALESCE(published_at, created_at)
              >= NOW() - make_interval(days => $1::int)
          AND url IS NOT NULL
          AND BTRIM(url) <> ''
          AND (
            text IS NULL
            OR BTRIM(text) = ''
            OR char_length(BTRIM(text)) < {ARTICLE_EXTRACT_MIN_CHARS}
            OR text ILIKE '%enable javascript%'
            OR text = title
            OR (provider_summary IS NOT NULL AND text = provider_summary)
            OR (
              title IS NOT NULL
              AND provider_summary IS NOT NULL
              AND text = title || E'\n\n' || provider_summary
            )
          )
        ORDER BY published_at DESC NULLS LAST, created_at DESC
        LIMIT $2
        """,
        max(1, int(days)),
        max(1, int(limit)),
        conn=conn,
    )
    return [_normalize_article(row) for row in rows]


async def claim_for_summary(
    article_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    """Atomically take ownership of summarizing this article.

    Exactly one concurrent caller gets a row back; everyone else gets None and
    should read the current state instead of doing duplicate LLM work.
    """
    row = await db.fetch_one(
        f"""
        UPDATE {ARTICLES_TABLE}
        SET ai_summary_status = '{SUMMARY_STATUS_PENDING}',
            ai_summary_started_at = NOW()
        WHERE article_id = $1::uuid
          AND (
            ai_summary_status IN ('{SUMMARY_STATUS_NONE}', '{SUMMARY_STATUS_FAILED}')
            OR (
                ai_summary_status = '{SUMMARY_STATUS_PENDING}'
                AND ai_summary_started_at
                    < NOW() - INTERVAL '{_STALE_CLAIM_MINUTES} minutes'
            )
            OR (
                ai_summary_status = '{SUMMARY_STATUS_READY}'
                AND (
                    text IS NULL
                    OR BTRIM(text) = ''
                    OR char_length(BTRIM(text)) < {ARTICLE_EXTRACT_MIN_CHARS}
                    OR text ILIKE '%enable javascript%'
                )
            )
          )
        RETURNING {_ARTICLE_COLUMNS}
        """,
        article_id,
        conn=conn,
    )
    return _normalize_article(row) if row else None


async def set_article_text(
    article_id: str,
    text: Optional[str],
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    """Overwrite ``text`` only. Pass None to clear a placeholder (e.g. title)."""
    row = await db.fetch_one(
        f"""
        UPDATE {ARTICLES_TABLE}
        SET text = $2
        WHERE article_id = $1::uuid
        RETURNING {_ARTICLE_COLUMNS}
        """,
        article_id,
        text,
        conn=conn,
    )
    return _normalize_article(row) if row else None


async def set_summary(
    article_id: str,
    ai_summary: Optional[str],
    ai_summary_status: str,
    ai_summary_model: Optional[str] = None,
    ai_summary_error: Optional[str] = None,
    text: Optional[str] = None,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"""
        UPDATE {ARTICLES_TABLE}
        SET ai_summary = $2,
            ai_summary_status = $3,
            ai_summary_model = $4,
            ai_summary_error = $5,
            text = COALESCE($6, {ARTICLES_TABLE}.text),
            ai_summary_updated_at = NOW()
        WHERE article_id = $1::uuid
        RETURNING {_ARTICLE_COLUMNS}
        """,
        article_id,
        ai_summary,
        ai_summary_status,
        ai_summary_model,
        ai_summary_error,
        text,
        conn=conn,
    )
    return _normalize_article(row) if row else None


async def list_recent_articles_by_symbol(
    symbol: str,
    days: int = 7,
    limit: int = 10,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Stored news_articles rows for one ticker, including the text body."""
    rows = await db.fetch_all(
        f"""
        SELECT na.article_id, sq.symbol, na.title, na.source, na.published_at, na.url,
               na.text, na.ai_summary, na.provider_summary
        FROM {ARTICLES_TABLE} na
        JOIN {STOCK_ARTICLES_TABLE} sa ON na.article_id = sa.article_id
        JOIN {QUOTES_TABLE} sq ON sa.stock_id = sq.stock_id
        WHERE UPPER(sq.symbol) = UPPER($1)
          AND na.published_at >= NOW() - make_interval(days => $2::int)
        ORDER BY na.published_at DESC NULLS LAST
        LIMIT $3
        """,
        symbol,
        max(1, int(days)),
        max(1, int(limit)),
        conn=conn,
    )
    articles: list[dict[str, Any]] = []
    for row in rows:
        articles.append(
            {
                "article_id": str(row.get("article_id") or ""),
                "symbol": str(row.get("symbol") or symbol).strip().upper(),
                "title": str(row.get("title") or "").strip() or "Untitled",
                "source": row.get("source"),
                "published_at": _normalize_datetime(row.get("published_at")),
                "url": row.get("url"),
                "text": row.get("text"),
                "ai_summary": row.get("ai_summary"),
                "provider_summary": row.get("provider_summary"),
            }
        )
    return articles


async def list_recent_texts_by_symbol(
    symbol: str,
    days: int = 7,
    conn: Optional[asyncpg.Connection] = None,
) -> list[str]:
    """Read article bodies for one ticker. Joins quotes read-only to filter by symbol."""
    articles: list[dict[str, Any]] = await list_recent_articles_by_symbol(
        symbol,
        days=days,
        limit=200,
        conn=conn,
    )
    texts: list[str] = []
    for article in articles:
        body: str = str(article.get("text") or "").strip()
        if body:
            texts.append(body)
    return texts


async def delete_older_than(
    days: int = 7,
    conn: Optional[asyncpg.Connection] = None,
) -> str:
    """Delete articles outside the retention window (AI summaries go with the row).

    Keeps the last ``days`` calendar days inclusive. Example with days=7 on Aug 9:
    keeps Aug 3..Aug 9 and deletes anything older. ``stock_articles`` links cascade.
    """
    window = max(1, int(days))
    return await db.execute(
        f"""
        DELETE FROM {ARTICLES_TABLE}
        WHERE COALESCE(published_at, created_at)::date
              < (CURRENT_DATE - ($1::int - 1))
        """,
        window,
        conn=conn,
    )


async def delete_orphans_older_than(
    days: int = 7,
    conn: Optional[asyncpg.Connection] = None,
) -> str:
    """Remove articles no stock links to anymore."""
    return await db.execute(
        f"""
        DELETE FROM {ARTICLES_TABLE} a
        WHERE NOT EXISTS (
            SELECT 1 FROM {STOCK_ARTICLES_TABLE} sa WHERE sa.article_id = a.article_id
        )
        AND a.created_at < NOW() - ($1::int * INTERVAL '1 day')
        """,
        days,
        conn=conn,
    )
