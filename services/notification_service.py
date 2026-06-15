"""
Notification service.
Sends alerts via WhatsApp (Twilio) or Email (SendGrid).
Both are no-ops when credentials are not configured — the alert is still saved to the DB.
"""
from __future__ import annotations

import logging

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_whatsapp(to: str, message: str) -> bool:
    """
    Send a WhatsApp message via Twilio.
    `to` must be in format 'whatsapp:+91XXXXXXXXXX'.
    Returns True on success.
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        logger.info("[WhatsApp stub] would send to %s: %s", to, message[:80])
        return False

    try:
        from twilio.rest import Client  # lazy import

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=message,
            from_=settings.twilio_whatsapp_from,
            to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
        )
        logger.info("WhatsApp sent to %s", to)
        return True
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        return False


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Send an email alert via SendGrid. Returns True on success."""
    if not settings.sendgrid_api_key:
        logger.info("[Email stub] would send to %s: %s", to, subject)
        return False

    try:
        from sendgrid import SendGridAPIClient  # lazy import
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.alert_from_email,
            to_emails=to,
            subject=subject,
            html_content=body_html,
        )
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        sg.send(message)
        logger.info("Email sent to %s", to)
        return True
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False


def build_alert_message(order_id: int, alert_type: str, details: str) -> str:
    return (
        f"🚨 Eluno OMS Alert\n"
        f"Order #{order_id} | {alert_type.replace('_', ' ').title()}\n"
        f"{details}\n"
        f"Login to dashboard to take action."
    )