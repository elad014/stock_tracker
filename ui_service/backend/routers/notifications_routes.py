from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status

from clients.database_client import db
from db_logics import notifications_db_logic as notifications_db
from deps import get_current_user
from models.notifications import NotificationResponse

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    responses={401: {"description": "Not authenticated"}},
)


@router.get(
    "",
    summary="List unread in-app notifications",
    response_model=list[NotificationResponse],
)
async def list_notifications(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[NotificationResponse]:
    """Return all unread in-app notifications for the authenticated user, newest first."""
    user_id: str = str(user["id"])
    rows = await notifications_db.list_unread(user_id)
    return [NotificationResponse(**row) for row in rows]


@router.put(
    "/{notification_id}/read",
    summary="Mark a notification as read",
    response_model=NotificationResponse,
    responses={404: {"description": "Notification not found or not owned by this user"}},
)
async def mark_notification_read(
    notification_id: str = Path(..., description="UUID of the notification to mark read"),
    user: dict[str, Any] = Depends(get_current_user),
) -> NotificationResponse:
    """Flip is_read to TRUE for the given notification.

    Returns 404 if the notification does not exist or belongs to a different user.
    """
    user_id: str = str(user["id"])

    # Attempt update (idempotent — works even if already read)
    row = await db.fetch_one(
        """
        UPDATE in_app_notifications
        SET is_read = TRUE
        WHERE id = $1::uuid AND user_id = $2::uuid
        RETURNING *
        """,
        notification_id,
        user_id,
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationResponse(
        id=str(row["id"]),
        message=row["message"],
        is_read=row["is_read"],
        created_at=row["created_at"],
    )
