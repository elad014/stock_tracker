import logging

from clients.ui_service_client import ui_service_client
from db_logics import alerts_db_logic as alerts_db
from models.stocks import TriggerAlertPayload

logger = logging.getLogger(__name__)


async def run_alerts_check() -> None:
    """Evaluate all PENDING price alerts against current stock_quotes data.

    Called after every quote upsert (end of daily-update and after a user adds a
    new stock). Trigger conditions are evaluated inside a single atomic SQL
    statement that joins stock_alerts with stock_quotes and claims matching
    rows as TRIGGERED so a second run cannot fire the same alert twice.

    After ui-service accepts the notification, the alert row is deleted.
    If delivery fails, the row is returned to PENDING so the next check can
    try again. A failure for one alert does not stop the remaining alerts.
    """
    triggered = await alerts_db.check_and_trigger_alerts()

    if not triggered:
        logger.debug("alerts_check: no alerts triggered")
        return

    logger.info("alerts_check: %s alert(s) triggered", len(triggered))

    for alert in triggered:
        payload = TriggerAlertPayload(
            user_id=alert["user_id"],
            stock_id=alert["stock_id"],
            symbol=alert["symbol"],
            alert_type=alert["alert_type"],
            direction=alert["direction"],
            target_value=alert["target_value"],
            current_value=alert["current_value"],
        )
        delivered = await ui_service_client.trigger_alert(payload.model_dump())
        alert_id = str(alert["id"])
        if delivered:
            await alerts_db.delete_alert(alert_id)
            logger.info("alerts_check: deleted alert %s after notification", alert_id)
        else:
            await alerts_db.reopen_alert(alert_id)
            logger.warning(
                "alerts_check: notification failed for alert %s; left PENDING",
                alert_id,
            )
