"""IEmailService and its two providers: a simulation and the single SMTP adapter.

``SmtpEmailService`` is the only code that talks SMTP; the legacy ``SmtpEmailClient``
delegates to it. Logs carry normalized error codes only, never bodies, recipients,
credentials or raw server replies.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr
from typing import Any, Protocol

import aiosmtplib

from app.core.config import Settings
from app.core.email_address import normalize_mailbox, strip_line_breaks
from app.integrations.email.errors import (
    EmailDeliveryError,
    PermanentEmailError,
    TemporaryEmailError,
)
from app.integrations.email.message import EmailMessage

logger = logging.getLogger(__name__)

Transport = Callable[..., Awaitable[Any]]


class IEmailService(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class FakeEmailService:
    """Simulation mode: records messages in memory; nothing leaves the process."""

    simulated = True

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
        logger.info("Email simulated (EMAIL_PROVIDER=fake); nothing was delivered")


def _status_error(code: int | None) -> EmailDeliveryError:
    if code is not None and 500 <= code <= 599:
        return PermanentEmailError(f"smtp_{code}")
    if code is not None and 400 <= code <= 499:
        return TemporaryEmailError(f"smtp_{code}")
    return TemporaryEmailError("smtp_error")


def _classify(exc: BaseException) -> EmailDeliveryError:
    # Thứ tự quan trọng: lỗi timeout của aiosmtplib cũng là SMTPException/ConnectError.
    if isinstance(exc, TimeoutError):
        return TemporaryEmailError("smtp_timeout")
    if isinstance(exc, aiosmtplib.SMTPRecipientsRefused):
        first = exc.recipients[0] if exc.recipients else None
        return _status_error(first.code if first is not None else None)
    if isinstance(exc, aiosmtplib.SMTPResponseException):
        return _status_error(exc.code)
    if isinstance(exc, aiosmtplib.SMTPNotSupported):
        return PermanentEmailError("smtp_not_supported")
    if isinstance(exc, aiosmtplib.SMTPException | OSError):
        return TemporaryEmailError("smtp_connection")
    return TemporaryEmailError("smtp_error")


class SmtpEmailService:
    simulated = False

    def __init__(self, settings: Settings, *, transport: Transport | None = None) -> None:
        if not settings.smtp_host:
            raise ValueError("SMTP is not configured")
        self._settings = settings
        self._transport: Transport = transport or aiosmtplib.send

    def _build(self, message: EmailMessage, recipient: str) -> MimeMessage:
        config = self._settings
        mime = MimeMessage()
        mime["From"] = formataddr((config.mail_from_name, config.mail_from_address))
        mime["To"] = recipient
        mime["Subject"] = strip_line_breaks(message.subject)
        if message.message_id:
            mime["Message-ID"] = strip_line_breaks(message.message_id)
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime

    async def send(self, message: EmailMessage) -> None:
        try:
            recipient = normalize_mailbox(message.to)
        except ValueError:
            raise PermanentEmailError("invalid_recipient") from None
        mime = self._build(message, recipient)
        config = self._settings
        error: EmailDeliveryError | None = None
        try:
            # Giới hạn tổng thời gian của cả lượt (kết nối, TLS, AUTH, DATA), không chỉ
            # timeout từng socket: nhiều bước chậm cộng lại vẫn bị cắt ở 10 giây.
            async with asyncio.timeout(config.smtp_timeout_seconds):
                result = await self._transport(
                    mime,
                    hostname=config.smtp_host,
                    port=config.smtp_port,
                    username=config.smtp_username,
                    password=(
                        config.smtp_password.get_secret_value() if config.smtp_password else None
                    ),
                    start_tls=bool(config.smtp_use_tls),
                    use_tls=bool(config.smtp_use_ssl),
                    validate_certs=True,
                    recipients=[recipient],
                    timeout=config.smtp_timeout_seconds,
                )
            refused = result[0] if isinstance(result, tuple) and result else None
            if refused:
                # Server accepted the session but refused the (only) recipient.
                response = next(iter(refused.values()))
                error = _status_error(getattr(response, "code", None))
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:  # classified below; raw text is dropped
            error = _classify(exc)
        if error is not None:
            # Raised outside the except block: no chained raw SMTP exception.
            logger.warning("SMTP delivery failed (%s)", error.code)
            raise error


def build_email_service(settings: Settings) -> IEmailService:
    if settings.email_provider == "smtp":
        return SmtpEmailService(settings)
    return FakeEmailService()
