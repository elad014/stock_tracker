import uuid
from typing import Any, Optional

import asyncpg

from clients.database_client import db

ALERTS_TABLE = "stock_alerts"
QUOTES_TABLE = "stock_quotes"


def _normalize_alert(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record row from stock_alerts into a plain dict."""
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "stock_id": str(row["stock_id"]),
        "alert_type": row["alert_type"],
        "target_value": float(row["target_value"]),
        "direction": row["direction"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


async def create_alert(
    user_id: str,
    stock_id: str,
    alert_type: str,
    target_value: float,
    direction: str,
    conn: Optional[asyncpg.Connection] = None,
) -> dict[str, Any]:
    """Insert a new PENDING alert and return it as a dict."""
    alert_id = uuid.uuid4()
    row = await db.fetch_one(
        f"""
        INSERT INTO {ALERTS_TABLE}
            (id, user_id, stock_id, alert_type, target_value, direction, status)
        VALUES ($1, $2, $3::uuid, $4, $5, $6, 'PENDING')
        RETURNING *
        """,
        str(alert_id),
        user_id,
        stock_id,
        alert_type,
        target_value,
        direction,
        conn=conn,
    )
    return _normalize_alert(row)


async def check_and_trigger_alerts() -> list[dict[str, Any]]:
    """Atomically find all PENDING alerts whose conditions are met based on
    the current data in stock_quotes, claim them as TRIGGERED, and return the
    claimed rows enriched with symbol and current_value.

    TRIGGERED is only a claim so a second check cannot fire the same alert.
    The caller deletes the row after the notification is delivered.

    Trigger conditions (evaluated entirely in SQL — no external API calls):
      ABSOLUTE ABOVE  →  stock_quotes.close          >  target_value
      ABSOLUTE BELOW  →  stock_quotes.close          <  target_value
      PERCENT  ABOVE  →  stock_quotes.percent_change >  target_value
      PERCENT  BELOW  →  stock_quotes.percent_change <  -ABS(target_value)

    The entire find-and-update is one atomic statement inside a transaction,
    so there are no race conditions between alert evaluation and status update.
    """
    async with db.transaction() as conn:
        rows = await db.fetch_all(
            f"""
            UPDATE {ALERTS_TABLE} AS sa
            SET status = 'TRIGGERED'
            FROM {QUOTES_TABLE} AS sq
            WHERE sa.stock_id = sq.stock_id
              AND sa.status = 'PENDING'
              AND sq.close IS NOT NULL
              AND (
                (sa.alert_type = 'ABSOLUTE' AND sa.direction = 'ABOVE'
                    AND sq.close > sa.target_value)
                OR
                (sa.alert_type = 'ABSOLUTE' AND sa.direction = 'BELOW'
                    AND sq.close < sa.target_value)
                OR
                (sa.alert_type = 'PERCENT' AND sa.direction = 'ABOVE'
                    AND sq.percent_change IS NOT NULL
                    AND sq.percent_change > sa.target_value)
                OR
                (sa.alert_type = 'PERCENT' AND sa.direction = 'BELOW'
                    AND sq.percent_change IS NOT NULL
                    AND sq.percent_change < -ABS(sa.target_value))
              )
            RETURNING
                sa.id::text          AS id,
                sa.user_id           AS user_id,
                sa.stock_id::text    AS stock_id,
                sa.alert_type        AS alert_type,
                sa.target_value::float AS target_value,
                sa.direction         AS direction,
                sq.symbol            AS symbol,
                CASE sa.alert_type
                    WHEN 'PERCENT' THEN sq.percent_change
                    ELSE sq.close
                END::float           AS current_value
            """,
            conn=conn,
        )
    return rows


async def delete_alert(
    alert_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    """Remove an alert after its notification has been delivered."""
    result = await db.execute(
        f"""
        DELETE FROM {ALERTS_TABLE}
        WHERE id = $1::uuid
        """,
        alert_id,
        conn=conn,
    )
    return _rows_affected(result) > 0


async def reopen_alert(
    alert_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> bool:
    """Return a claimed alert to PENDING when notification delivery failed."""
    result = await db.execute(
        f"""
        UPDATE {ALERTS_TABLE}
        SET status = 'PENDING'
        WHERE id = $1::uuid AND status = 'TRIGGERED'
        """,
        alert_id,
        conn=conn,
    )
    return _rows_affected(result) > 0


def _rows_affected(result: str) -> int:
    """Parse asyncpg's 'DELETE N' / 'UPDATE N' command tag into a row count."""
    try:
        return int(result.split()[-1])
    except (AttributeError, ValueError, IndexError):
        return 0


async def cancel_alert(
    alert_id: str,
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> Optional[dict[str, Any]]:
    """Set status to CANCELLED.  Returns None if the alert does not exist or
    does not belong to the given user."""
    row = await db.fetch_one(
        f"""
        UPDATE {ALERTS_TABLE}
        SET status = 'CANCELLED'
        WHERE id = $1::uuid AND user_id = $2 AND status = 'PENDING'
        RETURNING *
        """,
        alert_id,
        user_id,
        conn=conn,
    )
    return _normalize_alert(row) if row else None
