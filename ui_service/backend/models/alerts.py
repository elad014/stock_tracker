from typing import Literal

from pydantic import BaseModel


class CreateAlertRequest(BaseModel):
    """Body for POST /stocks/{stock_id}/alerts (public, Bearer-protected)."""

    alert_type: Literal["PERCENT", "ABSOLUTE"]
    target_value: float
    direction: Literal["ABOVE", "BELOW"]


class AlertResponse(BaseModel):
    """Mirrors the response from stock-service's POST /internal/alerts."""

    id: str
    stock_id: str
    alert_type: str
    target_value: float
    direction: str
    status: str


class InternalAlertTriggerRequest(BaseModel):
    """Body posted by stock-service to POST /api/v1/internal/alerts/trigger."""

    user_id: str
    stock_id: str
    symbol: str
    alert_type: str
    direction: str
    target_value: float
    current_value: float
