import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status

from clients.database_client import db
from clients.email_client import mailer
from clients.stock_service_client import stock_service_client as stock_service
from db_logics import user_db_logic as user_db
from db_logics import notifications_db_logic as notifications_db
from deps import get_current_user
from internal_auth import verify_internal_api_key
from models.alerts import AlertResponse, CreateAlertRequest, InternalAlertTriggerRequest
from services.stocks_service import _require_on_watchlist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router — two tag groups share the same prefix hierarchy
# ---------------------------------------------------------------------------

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal endpoint: called by stock-service when an alert fires
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/internal/alerts/trigger",
    tags=["Internal"],
    summary="Receive a triggered alert from stock-service",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        404: {"description": "User not found"},
    },
)
async def trigger_alert(req: InternalAlertTriggerRequest) -> dict[str, bool]:
    """Called by stock-service when a price alert condition is met.

    1. Look up the user's email address.
    2. Insert an in-app notification inside a transaction.
    3. Send an email (failure is logged, not re-raised).
    """
    user = await user_db.get_user_auth_by_id(req.user_id)
    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"User {req.user_id!r} not found",
        )

    # Build a human-readable banner message
    direction_label = "above" if req.direction == "ABOVE" else "below"
    if req.alert_type == "PERCENT":
        message = (
            f"{req.symbol} PERCENT alert triggered: "
            f"daily change {req.current_value:+.2f}% is "
            f"{direction_label} target {req.target_value:+.2f}%"
        )
    else:
        message = (
            f"{req.symbol} ABSOLUTE alert triggered: "
            f"price ${req.current_value:.2f} is "
            f"{direction_label} target ${req.target_value:.2f}"
        )

    async with db.transaction() as conn:
        await notifications_db.create_notification(
            user_id=req.user_id,
            message=message,
            conn=conn,
        )

    # Email is best-effort — a failure must not roll back the notification
    try:
        await mailer.send_alert_triggered(
            to=str(user["email"]),
            symbol=req.symbol,
            alert_type=req.alert_type,
            direction=req.direction,
            target_value=req.target_value,
            current_value=req.current_value,
        )
    except Exception as exc:
        logger.error(
            "trigger_alert: failed to send email for user %s / alert %s: %s",
            req.user_id,
            req.symbol,
            exc,
        )

    return {"ok": True}


# ---------------------------------------------------------------------------
# Public endpoint: browser creates a new alert for a watchlist stock
# ---------------------------------------------------------------------------


@router.post(
    "/stocks/{stock_id}/alerts",
    tags=["Alerts"],
    summary="Create a price alert for a watchlist stock",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Stock is not on your watchlist"},
    },
)
async def create_stock_alert(
    req: CreateAlertRequest,
    stock_id: str = Path(..., description="Stock UUID"),
    user: dict[str, Any] = Depends(get_current_user),
) -> AlertResponse:
    """Create a new PENDING price alert for a stock that is already on the user's watchlist."""
    user_id: str = str(user["id"])
    await _require_on_watchlist(user_id, stock_id)

    alert = await stock_service.create_alert(
        user_id=user_id,
        stock_id=stock_id,
        alert_type=req.alert_type,
        target_value=req.target_value,
        direction=req.direction,
    )
    return AlertResponse(**alert)
