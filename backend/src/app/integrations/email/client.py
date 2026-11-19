"""Legacy email injection point used by account flows.

``EmailMessage``/``EmailClient`` stay importable from here so account services and
tests keep injecting a client. ``SmtpEmailClient`` is a thin adapter over the single
SMTP implementation in ``service.SmtpEmailService``. Nothing here logs tokens or bodies.
"""

import logging
from typing import Protocol

from app.core.config import Settings
from app.integrations.email.message import EmailMessage
from app.integrations.email.service import SmtpEmailService

__all__ = ["EmailClient", "EmailMessage", "SmtpEmailClient", "build_email_client", "deliver"]

logger = logging.getLogger(__name__)


class EmailClient(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpEmailClient:
    def __init__(self, settings: Settings):
        if settings.smtp_host is None:
            raise ValueError("SMTP is not configured")
        self._service = SmtpEmailService(settings)

    async def send(self, message: EmailMessage) -> None:
        await self._service.send(message)


def build_email_client(settings: Settings) -> EmailClient | None:
    # Giữ hành vi cũ cho email tài khoản (chưa chuyển sang outbox ở bước này):
    # không có SMTP thật thì không gửi; chế độ fake cũng không gửi ra ngoài.
    if settings.email_provider != "smtp" or settings.smtp_host is None:
        return None
    return SmtpEmailClient(settings)


async def deliver(client: EmailClient | None, message: EmailMessage) -> bool:
    """Attempt one bounded delivery; failure never rolls back committed state."""
    if client is None:
        logger.warning("Email delivery is not configured")
        return False
    try:
        await client.send(message)
    except Exception:
        # Never include the link token or message body in logs.
        logger.warning("Email delivery failed")
        return False
    return True
