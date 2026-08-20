from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

from constant import DOC_INGEST_WEEK_DAYS
from database_client import db

INGEST_QUOTA_TABLE = "document_ingest_quota"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def first_ingest_expired(
    first_ingest: datetime,
    days: int = DOC_INGEST_WEEK_DAYS,
) -> bool:
    """True when 7 days have passed since the period's first ingest."""
    unlock_at = _as_utc(first_ingest) + timedelta(days=days)
    return datetime.now(timezone.utc) >= unlock_at


async def current_period_usage(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> tuple[int, Optional[datetime]]:
    """Ingests used in the open 7-day period, or 0 if first_ingest is 7+ days old."""
    row = await db.fetch_one(
        f"""
        SELECT count_recent_ingests, first_ingest
        FROM {INGEST_QUOTA_TABLE}
        WHERE user_id = $1
        """,
        user_id,
        conn=conn,
    )
    if row is None:
        return 0, None
    started = row["first_ingest"]
    if not isinstance(started, datetime) or first_ingest_expired(started):
        return 0, None
    return int(row["count_recent_ingests"]), started


async def record_successful_ingest(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    """Increment the user's week counter, or start a new week if first_ingest expired."""
    row = await db.fetch_one(
        f"""
        SELECT count_recent_ingests, first_ingest
        FROM {INGEST_QUOTA_TABLE}
        WHERE user_id = $1
        FOR UPDATE
        """,
        user_id,
        conn=conn,
    )
    started = row.get("first_ingest") if row else None
    if row is None or not isinstance(started, datetime) or first_ingest_expired(started):
        await db.execute(
            f"""
            INSERT INTO {INGEST_QUOTA_TABLE} (
                user_id, count_recent_ingests, first_ingest
            )
            VALUES ($1, 1, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                count_recent_ingests = 1,
                first_ingest = NOW()
            """,
            user_id,
            conn=conn,
        )
        return
    await db.execute(
        f"""
        UPDATE {INGEST_QUOTA_TABLE}
        SET count_recent_ingests = count_recent_ingests + 1
        WHERE user_id = $1
        """,
        user_id,
        conn=conn,
    )


def retry_after_seconds(
    first_ingest: Optional[datetime],
    days: int = DOC_INGEST_WEEK_DAYS,
) -> int:
    """Seconds until first_ingest is 7 days old and all 20 slots open."""
    if first_ingest is None:
        return 1
    unlock_at = _as_utc(first_ingest) + timedelta(days=days)
    remaining = (unlock_at - datetime.now(timezone.utc)).total_seconds()
    return max(1, int(remaining))
