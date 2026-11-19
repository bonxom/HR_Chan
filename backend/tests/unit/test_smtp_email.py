# Adapter SMTP chung: timeout toàn lượt, TLS/SSL, MIME hai phần, phân loại 4xx/5xx,
# chặn nhiều người nhận/header injection. Transport giả, không mở kết nối mạng thật.
"""SmtpEmailService and classified delivery errors (plan task 2).

Contract:

* ``app.integrations.email.service.SmtpEmailService(settings, *, transport=None)``;
  ``transport`` defaults to ``aiosmtplib.send`` and is awaited as
  ``transport(mime_message, **kwargs)`` (``hostname``, ``port``, ``username``,
  ``password``, ``start_tls``, ``use_tls``, ``recipients`` ...). Tests inject a recorder.
* ``app.integrations.email.errors``: ``EmailDeliveryError(code)`` with subclasses
  ``TemporaryEmailError`` and ``PermanentEmailError``; ``.code`` is a normalized,
  non-sensitive string: ``smtp_timeout``, ``smtp_connection``, ``smtp_<status>`` for a
  server reply, ``invalid_recipient`` for an address that is not exactly one mailbox.
* ``EmailMessage`` keeps ``to/subject/text_body/html_body`` and gains an optional
  ``message_id`` (default ``None``) so the outbox can set a stable Message-ID.
* ``SmtpEmailClient`` (existing injection point) delegates to the same adapter.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import getaddresses

import aiosmtplib
import pytest

from app.core.config import Settings
from app.integrations.email.client import EmailMessage

PASSWORD = "smtp-password-placeholder"
RAW_SERVER_TEXT = "5.1.1 <secret.user@example.test> unknown; token=abc123SECRET"


@dataclass
class RecordingTransport:
    calls: list[tuple[MimeMessage, dict]] = field(default_factory=list)
    error: BaseException | None = None
    delay: float = 0.0
    chunks: int = 0

    async def __call__(self, message, **kwargs):
        self.calls.append((message, kwargs))
        if self.chunks:
            # Many short network steps: each one is quick, the total is not.
            for _ in range(self.chunks):
                await asyncio.sleep(self.delay)
        elif self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return ({}, "250 OK")


def make_settings(**overrides) -> Settings:
    values = {
        "email_provider": "smtp",
        "smtp_host": "smtp.example.test",
        "smtp_port": 587,
        "smtp_username": "sender@example.test",
        "smtp_password": PASSWORD,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
        "mail_from_address": "no-reply@sis.hust.edu.vn",
        "mail_from_name": "HR Chan",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def safe_message(**overrides) -> EmailMessage:
    values = {
        "to": "recipient@example.test",
        "subject": "Mã xác thực",
        "text_body": "Xin chào, đây là nội dung văn bản.",
        "html_body": "<p>Xin chào, đây là nội dung HTML.</p>",
    }
    values.update(overrides)
    return EmailMessage(**values)


def service(transport: RecordingTransport, **settings_overrides):
    from app.integrations.email.service import SmtpEmailService

    return SmtpEmailService(make_settings(**settings_overrides), transport=transport)


@pytest.fixture
def transport() -> RecordingTransport:
    return RecordingTransport()


# ---- message structure ----------------------------------------------------------------


async def test_sends_one_multipart_text_and_html_message(transport) -> None:
    await service(transport).send(safe_message())

    [(mime, kwargs)] = transport.calls
    assert mime.is_multipart()
    parts = {part.get_content_type(): part.get_content() for part in mime.iter_parts()}
    assert set(parts) == {"text/plain", "text/html"}
    assert "nội dung văn bản" in parts["text/plain"]
    assert "nội dung HTML" in parts["text/html"]
    assert mime["Subject"] == "Mã xác thực"
    assert getaddresses([mime["From"]]) == [("HR Chan", "no-reply@sis.hust.edu.vn")]
    assert getaddresses([mime["To"]]) == [("", "recipient@example.test")]
    assert mime["Cc"] is None and mime["Bcc"] is None
    assert list(kwargs["recipients"]) == ["recipient@example.test"]


async def test_message_id_is_used_when_given(transport) -> None:
    await service(transport).send(safe_message(message_id="<outbox-42@hr-chan.local>"))
    [(mime, _kwargs)] = transport.calls
    assert mime["Message-ID"] == "<outbox-42@hr-chan.local>"


def test_email_message_keeps_its_existing_constructor() -> None:
    message = EmailMessage(to="a@example.test", subject="s", text_body="t", html_body="h")
    assert message.message_id is None


# ---- TLS / SSL ------------------------------------------------------------------------


async def test_starttls_on_587(transport) -> None:
    await service(transport, smtp_port=587, smtp_use_tls=True, smtp_use_ssl=False).send(
        safe_message()
    )
    [(_mime, kwargs)] = transport.calls
    assert (kwargs["hostname"], kwargs["port"]) == ("smtp.example.test", 587)
    assert kwargs["start_tls"] is True
    assert kwargs.get("use_tls", False) is False
    assert kwargs.get("validate_certs", True) is True
    assert kwargs["username"] == "sender@example.test"
    assert kwargs["password"] == PASSWORD


async def test_implicit_ssl_on_465(transport) -> None:
    await service(transport, smtp_port=465, smtp_use_tls=False, smtp_use_ssl=True).send(
        safe_message()
    )
    [(_mime, kwargs)] = transport.calls
    assert kwargs["port"] == 465
    assert kwargs["use_tls"] is True
    assert not kwargs.get("start_tls")
    assert kwargs.get("validate_certs", True) is True


async def test_plain_local_capture_disables_opportunistic_starttls(transport) -> None:
    # Mailpit on loopback: no TLS; start_tls must be explicitly False, not "auto" (None).
    await service(
        transport,
        smtp_host="localhost",
        smtp_port=1025,
        smtp_use_tls=False,
        smtp_use_ssl=False,
        smtp_username=None,
        smtp_password=None,
    ).send(safe_message())
    [(_mime, kwargs)] = transport.calls
    assert kwargs["start_tls"] is False
    assert kwargs.get("use_tls", False) is False
    assert kwargs.get("username") is None and kwargs.get("password") is None


# ---- whole-operation timeout ----------------------------------------------------------


async def test_whole_send_is_bounded_by_the_timeout(transport) -> None:
    from app.integrations.email.errors import TemporaryEmailError

    transport.delay = 30
    bounded = service(transport, smtp_timeout_seconds=0.2)
    with pytest.raises(TemporaryEmailError) as error:
        await asyncio.wait_for(bounded.send(safe_message()), 5)
    assert error.value.code == "smtp_timeout"


async def test_timeout_covers_the_total_not_each_network_step(transport) -> None:
    from app.integrations.email.errors import TemporaryEmailError

    # Ten steps of 0.1 s: each below the 0.3 s limit, together far above it.
    transport.delay = 0.1
    transport.chunks = 10
    bounded = service(transport, smtp_timeout_seconds=0.3)
    with pytest.raises(TemporaryEmailError) as error:
        await asyncio.wait_for(bounded.send(safe_message()), 5)
    assert error.value.code == "smtp_timeout"


# ---- error classification -------------------------------------------------------------


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (aiosmtplib.SMTPConnectError("connection refused"), "smtp_connection"),
        (aiosmtplib.SMTPServerDisconnected("lost"), "smtp_connection"),
        (ConnectionResetError("reset"), "smtp_connection"),
        (aiosmtplib.SMTPReadTimeoutError("slow"), "smtp_timeout"),
        (aiosmtplib.SMTPResponseException(421, "try later"), "smtp_421"),
        (aiosmtplib.SMTPDataError(451, "local error"), "smtp_451"),
        (aiosmtplib.SMTPRecipientRefused(450, "mailbox busy", "r@example.test"), "smtp_450"),
    ],
    ids=["connect", "disconnect", "reset", "read-timeout", "421", "451", "450-rcpt"],
)
async def test_network_errors_and_4xx_are_temporary(transport, raised, code) -> None:
    from app.integrations.email.errors import PermanentEmailError, TemporaryEmailError

    transport.error = raised
    with pytest.raises(TemporaryEmailError) as error:
        await service(transport).send(safe_message())
    assert not isinstance(error.value, PermanentEmailError)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (
            aiosmtplib.SMTPRecipientsRefused(
                [aiosmtplib.SMTPRecipientRefused(550, RAW_SERVER_TEXT, "r@example.test")]
            ),
            "smtp_550",
        ),
        (aiosmtplib.SMTPRecipientRefused(553, RAW_SERVER_TEXT, "r@example.test"), "smtp_553"),
        (aiosmtplib.SMTPResponseException(554, RAW_SERVER_TEXT), "smtp_554"),
        (aiosmtplib.SMTPSenderRefused(550, RAW_SERVER_TEXT, "no-reply@x.test"), "smtp_550"),
        (aiosmtplib.SMTPAuthenticationError(535, RAW_SERVER_TEXT), "smtp_535"),
    ],
    ids=["rcpts-550", "rcpt-553", "554", "sender-550", "auth-535"],
)
async def test_5xx_rejections_are_permanent(transport, raised, code) -> None:
    from app.integrations.email.errors import PermanentEmailError, TemporaryEmailError

    transport.error = raised
    with pytest.raises(PermanentEmailError) as error:
        await service(transport).send(safe_message())
    assert not isinstance(error.value, TemporaryEmailError)
    assert error.value.code == code
    assert len(transport.calls) == 1  # never retried inside the adapter


async def test_errors_carry_no_raw_server_text_or_secrets(transport, caplog) -> None:
    from app.integrations.email.errors import EmailDeliveryError

    caplog.set_level(logging.DEBUG)
    transport.error = aiosmtplib.SMTPResponseException(554, RAW_SERVER_TEXT)
    with pytest.raises(EmailDeliveryError) as error:
        await service(transport).send(safe_message(text_body="OTP 482913", html_body="482913"))

    exc = error.value
    for leaked in ("token=abc123SECRET", "secret.user@example.test", "482913", PASSWORD):
        assert leaked not in str(exc)
        assert leaked not in repr(exc)
        assert leaked not in caplog.text
    # The raw aiosmtplib exception is not chained (a later logger.exception would print it).
    assert exc.__cause__ is None
    assert exc.__suppress_context__ or exc.__context__ is None


async def test_success_logs_no_body_recipient_or_password(transport, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    await service(transport).send(
        safe_message(to="private.person@example.test", text_body="mã 739204", html_body="739204")
    )
    for leaked in ("739204", "private.person@example.test", PASSWORD):
        assert leaked not in caplog.text


# ---- one recipient, no header injection -----------------------------------------------


@pytest.mark.parametrize(
    "to",
    [
        "victim@example.test\r\nBcc: evil@example.test",
        "victim@example.test\nCc: evil@example.test",
        "victim@example.test, evil@example.test",
        "victim@example.test; evil@example.test",
        "Victim <victim@example.test>, evil@example.test",
        "not-an-address",
        "",
    ],
    ids=["crlf-bcc", "lf-cc", "comma", "semicolon", "display-comma", "invalid", "empty"],
)
async def test_anything_but_one_mailbox_is_a_permanent_invalid_recipient(transport, to) -> None:
    from app.integrations.email.errors import PermanentEmailError

    with pytest.raises(PermanentEmailError) as error:
        await service(transport).send(safe_message(to=to))
    assert error.value.code == "invalid_recipient"
    assert transport.calls == []


async def test_subject_line_breaks_cannot_add_headers(transport) -> None:
    await service(transport).send(
        safe_message(subject="Xin chào\r\nBcc: evil@example.test\nX-Injected: 1")
    )
    [(mime, kwargs)] = transport.calls
    assert "\r" not in mime["Subject"] and "\n" not in mime["Subject"]
    assert mime["Bcc"] is None and mime["X-Injected"] is None
    assert list(kwargs["recipients"]) == ["recipient@example.test"]
    assert "evil@example.test" not in str(mime.get_all("To"))


# ---- existing injection point ---------------------------------------------------------


async def test_legacy_smtp_client_delegates_to_the_shared_adapter(monkeypatch) -> None:
    from app.integrations.email import service as service_module
    from app.integrations.email.client import SmtpEmailClient

    sent: list[EmailMessage] = []

    async def recording_send(self, message: EmailMessage) -> None:
        sent.append(message)

    monkeypatch.setattr(service_module.SmtpEmailService, "send", recording_send)
    message = safe_message()
    await SmtpEmailClient(make_settings()).send(message)
    assert sent == [message]
