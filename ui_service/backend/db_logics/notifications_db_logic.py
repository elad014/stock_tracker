import uuid
from typing import Any, Optional

import asyncpg

from clients.database_client import db

NOTIFICATIONS_TABLE = "in_app_notifications"


def _normalize_notification(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record from in_app_notifications into a plain dict."""
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "message": row["message"],
        "is_read": row["is_read"],
        "created_at": row["created_at"],
    }


async def create_notification(
    user_id: str,
    message: str,
    *,
    conn: asyncpg.Connection,
) -> dict[str, Any]:
    """Insert a new notification row and return it.

    Must be called inside an active db.transaction() context.
    """
    notification_id = uuid.uuid4()
    row = await db.fetch_one(
        f"""
        INSERT INTO {NOTIFICATIONS_TABLE} (id, user_id, message)
        VALUES ($1::uuid, $2::uuid, $3)
        RETURNING *
        """,
        str(notification_id),
        user_id,
        message,
        conn=conn,
    )
    return _normalize_notification(row)


async def list_unread(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Return all unread notifications for the user, newest first."""
    rows = await db.fetch_all(
        f"""
        SELECT *
        FROM {NOTIFICATIONS_TABLE}
        WHERE user_id = $1::uuid AND is_read = FALSE
        ORDER BY created_at DESC
        """,
        user_id,
        conn=conn,
    )
    return [_normalize_notification(row) for row in rows]


async def mark_read(
    notification_id: str,
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    """Flip is_read to TRUE.  Returns False when the row does not exist or
    the caller is not the owner."""
    result = await db.execute(
        f"""
        UPDATE {NOTIFICATIONS_TABLE}
        SET is_read = TRUE
        WHERE id = $1::uuid AND user_id = $2::uuid AND is_read = FALSE
        """,
        notification_id,
        user_id,
        conn=conn,
    )
    # asyncpg returns "UPDATE N" — parse the row count
    try:
        rows_affected = int(result.split()[-1])
    except (AttributeError, ValueError, IndexError):
        rows_affected = 0
    return rows_affected > 0
