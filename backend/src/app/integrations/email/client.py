"""Email delivery boundary.

Development captures messages in a local SMTP mailbox; production requires
explicit SMTP configuration. Callers pass message content built by templates, so
this module never logs tokens or message bodies.
"""

import logging
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr
from typing import Protocol

import aiosmtplib

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str


class EmailClient(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpEmailClient:
    def __init__(self, settings: Settings):
        if settings.smtp_host is None:
            raise ValueError("SMTP is not configured")
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        config = self._settings
        mime = MimeMessage()
        mime["From"] = formataddr((config.smtp_from_name, config.smtp_from_email))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        await aiosmtplib.send(
            mime,
            hostname=config.smtp_host,
            port=config.smtp_port,
            start_tls=config.smtp_starttls,
            username=config.smtp_username,
            password=(config.smtp_password.get_secret_value() if config.smtp_password else None),
            timeout=config.smtp_timeout_seconds,
        )


def build_email_client(settings: Settings) -> EmailClient | None:
    if settings.smtp_host is None:
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
