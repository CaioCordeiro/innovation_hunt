from __future__ import annotations

import logging

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.config import settings

logger = logging.getLogger(__name__)


def validate_twilio_signature(*, url: str, form: dict[str, str], signature: str | None) -> bool:
    if not settings.twilio_validate_signature:
        return True
    if not settings.twilio_auth_token:
        logger.warning("TWILIO_VALIDATE_SIGNATURE=true but TWILIO_AUTH_TOKEN is missing")
        return False
    if not signature:
        return False
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, form, signature)


def send_whatsapp_message(*, to: str, body: str) -> None:
    """Best-effort proactive message to a WhatsApp number (e.g., whatsapp:+55...)."""
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from):
        logger.info("Twilio creds not configured; skipping proactive send")
        return

    from_number = settings.twilio_whatsapp_from
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    to_number = to
    if to_number and not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(from_=from_number, to=to_number, body=body)
