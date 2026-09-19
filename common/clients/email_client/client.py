import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from constant import RESEND_API_URL

logger = logging.getLogger(__name__)

load_dotenv()


class EmailClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        from_address: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self._from_address = from_address or os.getenv("EMAIL_FROM", "noreply@yourdomain.com")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> dict:
        payload: dict = {
            "from": self._from_address,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    RESEND_API_URL,
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Email send failed: %s %s", exc.response.status_code, exc.response.text)
            raise
        except httpx.RequestError as exc:
            logger.error("Email service unreachable: %s", exc)
            raise

    async def send_password_reset(self, to: str, reset_token: str) -> dict:
        subject = "Stock Tracker - Password Reset"
        html = (
            "<h2>Password Reset Request</h2>"
            "<p>You requested a password reset. Use the token below to reset your password:</p>"
            f"<p style='font-size:18px;font-weight:bold;background:#f0f2f5;padding:12px;border-radius:8px;'>{reset_token}</p>"
            "<p>This token expires in 15 minutes.</p>"
            "<p>If you did not request this, ignore this email.</p>"
        )
        return await self.send(to=to, subject=subject, html=html)

    async def send_account_changes(
        self,
        to: str,
        changes: list[dict[str, str]],
    ) -> dict:
        rows: list[str] = []
        for change in changes:
            field = change["field"]
            if field == "Password":
                rows.append("<li><strong>Password</strong> was changed</li>")
                continue
            old_value = change.get("old", "")
            new_value = change.get("new", "")
            rows.append(
                f"<li><strong>{field}</strong> changed from "
                f"<code>{old_value}</code> to <code>{new_value}</code></li>"
            )

        subject = "Stock Tracker - Account details updated"
        html = (
            "<h2>Account details updated</h2>"
            "<p>The following changes were made to your Stock Tracker account:</p>"
            f"<ul>{''.join(rows)}</ul>"
            "<p>If you did not make these changes, reset your password immediately.</p>"
        )
        return await self.send(to=to, subject=subject, html=html)


    async def send_alert_triggered(
        self,
        to: str,
        symbol: str,
        alert_type: str,
        direction: str,
        target_value: float,
        current_value: float,
    ) -> dict:
        """Send a stock-alert triggered notification email."""
        subject = f"Stock Alert Triggered: {symbol}"
        direction_label = "above" if direction == "ABOVE" else "below"
        if alert_type == "PERCENT":
            trigger_line = (
                f"<strong>{symbol}</strong> has moved {current_value:+.2f}% today, "
                f"{'surpassing' if direction == 'ABOVE' else 'falling below'} "
                f"your {target_value:+.2f}% target."
            )
        else:
            trigger_line = (
                f"<strong>{symbol}</strong> is currently trading at "
                f"<strong>${current_value:.2f}</strong>, which is {direction_label} "
                f"your target of <strong>${target_value:.2f}</strong>."
            )
        html = (
            "<h2>Stock Alert Triggered</h2>"
            f"<p>{trigger_line}</p>"
            "<p>Log in to Stock Tracker to review your portfolio.</p>"
            "<p style='color:#888;font-size:12px;'>You are receiving this email because "
            "you set a price alert on Stock Tracker.</p>"
        )
        return await self.send(to=to, subject=subject, html=html)


mailer = EmailClient()
