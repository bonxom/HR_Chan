# Smoke thật với Mailpit (và ClamAV) cục bộ, chỉ chạy khi bật rõ HR_CHAN_MAILPIT_SMOKE=1 và
# mọi địa chỉ là loopback. Không gửi ra Internet/Gmail, chỉ xóa đúng thư của test, không in
# mã OTP hay nội dung thư.
"""Real SMTP delivery through a local Mailpit (plan task 9, opt-in).

Enable with ``HR_CHAN_MAILPIT_SMOKE=1``; optional ``MAILPIT_SMTP_HOST`` (default
``127.0.0.1``), ``MAILPIT_SMTP_PORT`` (1025), ``MAILPIT_API_URL``
(``http://127.0.0.1:8025``), ``CLAMAV_SMOKE_HOST``/``CLAMAV_SMOKE_PORT`` (127.0.0.1:3311).
Hosts are checked with ``urllib.parse.urlsplit`` and must be exactly a loopback name or
address, so no message can leave the machine. Each test uses a unique ``@example.test``
recipient and deletes only its own messages through the Mailpit API.

The end-to-end API smoke uses the real encrypted store, the real ClamAV scanner and the
real SMTP adapter; CAPTCHA is a test double injected through ``create_app`` - this smoke
does NOT prove production CAPTCHA, which must be reported separately.
"""

import asyncio
import os
import re
import uuid
from urllib.parse import urlsplit

import httpx
import pytest
from application_flow_support import (
    FakeCaptcha,
    flow_settings,
    insert_open_job,
    make_storage,
    request_otp,
    submit,
    upload_ok,
)
from apply_support import apply_cleanup, outbox_rows

pytestmark = [
    pytest.mark.database,
    pytest.mark.skipif(
        os.getenv("HR_CHAN_MAILPIT_SMOKE") != "1",
        reason="Set HR_CHAN_MAILPIT_SMOKE=1 to run the local Mailpit smoke",
    ),
]

__all__ = ["apply_cleanup"]

SMTP_HOST = os.getenv("MAILPIT_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.getenv("MAILPIT_SMTP_PORT", "1025"))
API_URL = os.getenv("MAILPIT_API_URL", "http://127.0.0.1:8025").rstrip("/")
CLAMAV_HOST = os.getenv("CLAMAV_SMOKE_HOST", "127.0.0.1")
CLAMAV_PORT = int(os.getenv("CLAMAV_SMOKE_PORT", "3311"))
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
OUTBOX_KEY = "test-outbox-encryption-key-0123456789abcdef"
OTP_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _is_loopback_url(url: str) -> bool:
    parts = urlsplit(url)
    # Không chấp nhận userinfo (http://localhost@evil) hay tên giả (localhost.evil).
    return (
        parts.scheme in ("http", "https")
        and parts.username is None
        and parts.password is None
        and parts.hostname in LOOPBACK
    )


@pytest.fixture(scope="module", autouse=True)
def only_loopback() -> None:
    if SMTP_HOST not in LOOPBACK or CLAMAV_HOST not in LOOPBACK or not _is_loopback_url(API_URL):
        pytest.skip("Mailpit smoke only talks to loopback SMTP/API/ClamAV")


def test_loopback_guard_rejects_lookalike_hosts() -> None:
    assert _is_loopback_url("http://127.0.0.1:8025")
    assert _is_loopback_url("http://[::1]:8025")
    for url in (
        "http://localhost.evil.example:8025",
        "http://localhost@evil.example:8025",
        "http://user:pw@127.0.0.1:8025",
        "http://127.0.0.1.nip.io:8025",
        "file:///etc/passwd",
    ):
        assert not _is_loopback_url(url), url


@pytest.fixture
def mailpit_settings(settings):
    from pydantic import SecretStr

    return settings.model_copy(
        update={
            "email_provider": "smtp",
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT,
            "smtp_use_tls": False,
            "smtp_use_ssl": False,
            "smtp_username": None,
            "smtp_password": None,
            "outbox_encryption_key": SecretStr(OUTBOX_KEY),
        }
    )


@pytest.fixture
async def mailbox():
    """Find messages for one recipient and delete exactly those at teardown."""
    created: list[str] = []

    async with httpx.AsyncClient(base_url=API_URL, timeout=5) as api:

        async def search(recipient: str) -> list[dict]:
            found = await api.get("/api/v1/search", params={"query": f'to:"{recipient}"'})
            found.raise_for_status()
            messages = found.json().get("messages") or []
            created.extend(m["ID"] for m in messages if m["ID"] not in created)
            return messages

        async def find(recipient: str) -> dict:
            for _ in range(50):
                messages = await search(recipient)
                if messages:
                    detail = await api.get(f"/api/v1/message/{messages[0]['ID']}")
                    detail.raise_for_status()
                    return detail.json()
                await asyncio.sleep(0.2)
            pytest.fail("Message did not arrive in Mailpit within 10 seconds")

        find.search = search  # type: ignore[attr-defined]
        try:
            yield find
        finally:
            if created:
                await api.request("DELETE", "/api/v1/messages", json={"IDs": created})


def unique_recipient() -> str:
    return f"smoke-{uuid.uuid4().hex[:12]}@example.test"


async def test_smtp_adapter_delivers_multipart_mail_to_mailpit(mailpit_settings, mailbox) -> None:
    from app.integrations.email.message import EmailMessage
    from app.integrations.email.service import SmtpEmailService

    recipient = unique_recipient()
    marker = uuid.uuid4().hex
    await SmtpEmailService(mailpit_settings).send(
        EmailMessage(
            to=recipient,
            subject=f"Smoke {marker}",
            text_body=f"Text part {marker}",
            html_body=f"<p>HTML part {marker}</p>",
            message_id=f"<smoke.{marker}@sis.hust.edu.vn>",
        )
    )

    message = await mailbox(recipient)
    assert message["Subject"] == f"Smoke {marker}"
    assert [to["Address"] for to in message["To"]] == [recipient]
    assert not message.get("Cc") and not message.get("Bcc")
    assert marker in message["Text"] and marker in message["HTML"]
    assert message["MessageID"].strip("<>") == f"smoke.{marker}@sis.hust.edu.vn"


async def test_otp_through_send_now_reaches_mailpit_and_the_outbox_stays_masked(
    apply_cleanup, session_factory, mailpit_settings, mailbox
) -> None:
    from app.integrations.email.service import SmtpEmailService
    from app.modules.notifications.service import NotificationService

    recipient = unique_recipient()
    result = await NotificationService(mailpit_settings).sendNow(
        session_factory,
        SmtpEmailService(mailpit_settings),
        template_code="OTP_APPLY",
        to=recipient,
        vars={
            "full_name": "Smoke Test",
            "otp_code": f"{uuid.uuid4().int % 1_000_000:06d}",
            "ttl_minutes": "5",
            "job_title": "Smoke",
        },
    )

    assert result.status == "SENT"
    message = await mailbox(recipient)
    code = OTP_PATTERN.search(message["Text"]).group(1)
    [row] = await outbox_rows(session_factory, "OTP_APPLY")
    assert row.status == "SENT"
    assert code not in row.body and code not in row.subject


async def test_full_api_flow_with_real_store_clamav_and_mailpit(
    apply_cleanup, session_factory, mailpit_settings, mailbox, tmp_path
) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.integrations.antivirus.client import ClamAVScanner
    from app.integrations.email.service import SmtpEmailService
    from app.main import create_app

    cv_dir = tmp_path / "smoke-cv-store"
    cv_dir.mkdir()
    config = flow_settings(mailpit_settings, cv_dir)
    app = create_app(
        config,
        email_service=SmtpEmailService(config),
        storage=make_storage(config),
        scanner=ClamAVScanner(CLAMAV_HOST, CLAMAV_PORT, timeout=10),
        captcha=FakeCaptcha(),  # CAPTCHA thật KHÔNG được kiểm ở smoke này
    )
    job = await insert_open_job(session_factory, title="Smoke Backend")
    recipient = unique_recipient()

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Origin": "http://localhost:5173"},
        ) as client:
            submission = await upload_ok(client, email=recipient, full_name="Smoke Ứng Viên")
            issued = await request_otp(client, submission, job.id)
            assert issued.status_code == 200, issued.text
            message = await mailbox(recipient)
            code = OTP_PATTERN.search(message["Text"]).group(1)
            created = await submit(client, submission, job.id, code)

    assert created.status_code == 201, created.text
    async with session_factory() as session:
        from sqlalchemy import text

        count = await session.scalar(text("SELECT count(*) FROM applications"))
    assert count == 1
    [row] = await outbox_rows(session_factory, "OTP_APPLY")
    assert row.status == "SENT" and code not in row.body
    assert len(await outbox_rows(session_factory)) == 1  # no confirmation email queued
    await asyncio.sleep(1)
    assert len(await mailbox.search(recipient)) == 1  # only the OTP reached the mailbox
