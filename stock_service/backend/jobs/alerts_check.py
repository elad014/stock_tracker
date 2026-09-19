import logging

from clients.ui_service_client import ui_service_client
from db_logics import alerts_db_logic as alerts_db
from models.stocks import TriggerAlertPayload

logger = logging.getLogger(__name__)


async def run_alerts_check() -> None:
    """Evaluate all PENDING price alerts against current stock_quotes data.

    Called after every quote upsert (end of daily-update and after a user adds a
    new stock).  No external API calls are made — trigger conditions are evaluated
    entirely inside a single atomic SQL statement that joins stock_alerts with
    stock_quotes and returns the rows that were just marked TRIGGERED.

    Notification delivery to ui-service is best-effort: a failure for one alert
    is logged but does not prevent the remaining alerts from being dispatched.
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
        await ui_service_client.trigger_alert(payload.model_dump())
