import logging
from typing import Any, Optional

import httpx

from constant import INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER, UI_SERVICE_URL

logger = logging.getLogger(__name__)


class UiServiceClient:
    """HTTP client used by stock-service to call ui-service internal endpoints.

    All failures are logged and swallowed so that a transient ui-service outage
    does not abort the alerts cron job.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url: str = (base_url or UI_SERVICE_URL).rstrip("/")
        self._api_key: str = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    async def trigger_alert(self, payload: dict[str, Any]) -> bool:
        """POST /api/v1/internal/alerts/trigger.

        Returns True when ui-service accepted the notification. Logs errors
        but does not raise so that one failed notification does not prevent
        the remaining triggered alerts from being dispatched.
        """
        url = f"{self._base_url}/api/v1/internal/alerts/trigger"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                )
            if response.status_code >= 400:
                logger.error(
                    "trigger_alert: ui-service returned %s — %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
            return True
        except httpx.RequestError as exc:
            logger.error("trigger_alert: request to ui-service failed: %s", exc)
            return False
        except Exception as exc:
            logger.exception("trigger_alert: unexpected error: %s", exc)
            return False


ui_service_client = UiServiceClient()
