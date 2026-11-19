# NotificationService trên PostgreSQL riêng: enqueue cùng giao dịch caller, sendNow ghi
# lượt thử bền vững trước SMTP, OTP chỉ lưu bản che, bí mật xếp hàng bị xóa sau khi xong.
"""NotificationService, template seeds and secret protection (plan task 3).

Contract (approved spec "Mẫu thư, giao dịch và dữ liệu bí mật" and plan task 3):

* ``NotificationService(settings)`` in ``app.modules.notifications.service``:

  - ``await enqueue(session, *, template_code, to, vars, application_id=None,
    user_id=None, secret_vars=frozenset()) -> int``: renders and validates first, then
    flushes one PENDING (queued) row in the caller's transaction; never commits, never
    calls SMTP.
  - ``await sendNow(session_factory, email_service, *, template_code, to, vars,
    application_id=None, user_id=None, secret_vars=frozenset(), immediate_metadata=None)
    -> DeliveryResult(outbox_id, status, attempts, error_code)``: own short
    transactions; a durable attempt is committed before each SMTP call; at most two
    attempts on temporary errors, one on a permanent error. Raises before writing
    anything for an unknown template (``TemplateNotFoundError``), a rendering error
    (``TemplateRenderError``) or an invalid recipient (``InvalidRecipientError``).

* Secrets: OTP rows only ever hold a redacted body; queued secrets are encrypted with
  ``Settings.outbox_encryption_key`` (no usable default) while PENDING and removed when
  the row becomes SENT/FAILED.
* ``seed_email_templates(session) -> int`` (``app.modules.notifications.seeds``): inserts
  the missing templates only, in the caller's transaction.
* ``TemplateCode`` (``app.modules.notifications.schemas``) names the seeded codes and
  reserves INTERVIEW_INVITATION, THANK_YOU and PROBATION_OFFER without seeding them.

Required variables chosen for the seeds (OTP_APPLY is fixed by the approved spec; the
other three are this plan's contract): see ``EXPECTED_REQUIRED_VARS``.
"""

import asyncio
import contextlib
import logging
from datetime import timedelta

import pytest
from apply_support import (
    ScriptedEmailService,
    apply_cleanup,
    build_world,
    insert_application,
    insert_otp,
    insert_template,
    now_utc,
    outbox_row,
    outbox_rows,
)
from pydantic import SecretStr
from sqlalchemy import text

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]

TEST_OUTBOX_KEY = "test-outbox-encryption-key-0123456789abcdef"
OTP = "482913"
TOKEN = "invitation-token-SECRET-value-7f3a"
TIMEOUT = 10.0

EXPECTED_REQUIRED_VARS = {
    "OTP_APPLY": {"full_name", "otp_code", "ttl_minutes", "job_title"},
    "ACCOUNT_INVITATION": {"full_name", "set_password_url", "ttl_hours"},
    "PASSWORD_RECOVERY": {"full_name", "set_password_url", "ttl_minutes"},
    "EMAIL_DELIVERY_FAILED": {"application_id", "failed_template", "error_code"},
}


def otp_vars(**overrides) -> dict:
    values = {
        "full_name": "Nguyễn Văn A",
        "otp_code": OTP,
        "ttl_minutes": "5",
        "job_title": "Lập trình viên Backend",
    }
    values.update(overrides)
    return values


def invitation_vars(**overrides) -> dict:
    values = {
        "full_name": "Trần Thị B",
        "set_password_url": f"http://localhost:5173/set-password#token={TOKEN}",
        "ttl_hours": "24",
    }
    values.update(overrides)
    return values


@pytest.fixture
def notify_settings(settings):
    return settings.model_copy(
        update={"outbox_encryption_key": SecretStr(TEST_OUTBOX_KEY), "email_outbox_batch_size": 10}
    )


@pytest.fixture
def notifications(notify_settings):
    from app.modules.notifications.service import NotificationService

    return NotificationService(notify_settings)


@pytest.fixture
async def seeded(apply_cleanup, session_factory) -> None:
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as session:
        await seed_email_templates(session)
        await session.commit()


async def send_otp(notifications, session_factory, service, **overrides):
    args = {
        "template_code": "OTP_APPLY",
        "to": "ung.vien@example.test",
        "vars": otp_vars(),
        "secret_vars": frozenset({"otp_code"}),
    }
    args.update(overrides)
    return await notifications.sendNow(session_factory, service, **args)


async def run_worker_batch(session_factory, service, settings, *, after=timedelta(0)) -> int:
    from app.modules.notifications.worker import deliver_due_batch

    return await deliver_due_batch(session_factory, service, settings, now_utc() + after)


async def outbox_count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(text("SELECT count(*) FROM email_outbox"))


# ---- seeds ----------------------------------------------------------------------------


async def test_seed_creates_templates_with_the_required_variables(seeded, session_factory):
    async with session_factory() as session:
        rows = (
            await session.execute(text("SELECT code, required_vars, body FROM email_templates"))
        ).all()
    stored = {row.code: set(row.required_vars) for row in rows}
    assert stored == EXPECTED_REQUIRED_VARS
    for row in rows:
        for variable in row.required_vars:
            assert "{" + variable + "}" in row.body


def test_future_template_codes_are_reserved_but_not_seeded() -> None:
    from app.modules.notifications.schemas import TemplateCode

    assert {code.value for code in TemplateCode} >= set(EXPECTED_REQUIRED_VARS) | {
        "INTERVIEW_INVITATION",
        "THANK_YOU",
        "PROBATION_OFFER",
    }


async def test_seed_is_idempotent_and_keeps_edited_templates(seeded, session_factory) -> None:
    from app.modules.notifications.seeds import seed_email_templates

    edited_subject = "Mã OTP (đã chỉnh bởi Admin)"
    async with session_factory() as session:
        await session.execute(
            text("UPDATE email_templates SET subject = :s WHERE code = 'OTP_APPLY'"),
            {"s": edited_subject},
        )
        await session.commit()

    async with session_factory() as session:
        inserted = await seed_email_templates(session)
        await session.commit()

    assert inserted == 0
    async with session_factory() as session:
        subject = await session.scalar(
            text("SELECT subject FROM email_templates WHERE code = 'OTP_APPLY'")
        )
        count = await session.scalar(text("SELECT count(*) FROM email_templates"))
    assert subject == edited_subject
    assert count == len(EXPECTED_REQUIRED_VARS)


async def test_seed_restores_only_missing_templates(seeded, session_factory) -> None:
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as session:
        await session.execute(text("DELETE FROM email_templates WHERE code = 'PASSWORD_RECOVERY'"))
        await session.commit()
    async with session_factory() as session:
        assert await seed_email_templates(session) == 1
        await session.commit()


# ---- enqueue: caller's transaction ----------------------------------------------------


async def test_enqueue_rolls_back_with_business(seeded, session_factory, notifications) -> None:
    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session,
            template_code="ACCOUNT_INVITATION",
            to="nhan.vien@sis.hust.edu.vn",
            vars=invitation_vars(),
            secret_vars=frozenset({"set_password_url"}),
        )
        assert row_id
        await session.rollback()
    assert await outbox_row(session_factory, row_id) is None
    assert await outbox_count(session_factory) == 0


async def test_enqueue_writes_one_pending_row_and_does_not_commit(
    seeded, session_factory, notifications
) -> None:
    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session,
            template_code="ACCOUNT_INVITATION",
            to="nhan.vien@sis.hust.edu.vn",
            vars=invitation_vars(),
            secret_vars=frozenset({"set_password_url"}),
        )
        # Not visible to anyone else until the caller commits.
        assert await outbox_row(session_factory, row_id) is None
        await session.commit()

    row = await outbox_row(session_factory, row_id)
    assert row.status == "PENDING"
    assert row.attempts == 0
    assert row.template_code == "ACCOUNT_INVITATION"
    assert row.to_email == "nhan.vien@sis.hust.edu.vn"
    assert row.sent_at is None and row.last_error is None
    assert row.next_attempt_at <= now_utc()
    assert TOKEN not in row.body and TOKEN not in row.subject


async def test_enqueue_stores_application_and_account_links(
    seeded, session_factory, notifications
) -> None:
    world = await build_world(session_factory)
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        row_id = await notifications.enqueue(
            session,
            template_code="EMAIL_DELIVERY_FAILED",
            to="hr@sis.hust.edu.vn",
            vars={"application_id": str(app_id), "failed_template": "X", "error_code": "y"},
            application_id=app_id,
            user_id=world.hr_id,
        )
        await session.commit()
    row = await outbox_row(session_factory, row_id)
    assert (row.application_id, row.user_id) == (app_id, world.hr_id)


async def test_enqueue_missing_variable_writes_nothing(seeded, session_factory, notifications):
    from app.modules.notifications.rendering import TemplateRenderError

    vars_without_url = {k: v for k, v in invitation_vars().items() if k != "set_password_url"}
    async with session_factory() as session:
        with pytest.raises(TemplateRenderError):
            await notifications.enqueue(
                session,
                template_code="ACCOUNT_INVITATION",
                to="nhan.vien@sis.hust.edu.vn",
                vars=vars_without_url,
            )
        await session.commit()
    assert await outbox_count(session_factory) == 0


async def test_enqueue_unknown_template_is_rejected(seeded, session_factory, notifications):
    from app.modules.notifications.service import TemplateNotFoundError

    async with session_factory() as session:
        with pytest.raises(TemplateNotFoundError):
            await notifications.enqueue(
                session, template_code="NO_SUCH_TEMPLATE", to="a@example.test", vars={}
            )
        await session.commit()
    assert await outbox_count(session_factory) == 0


@pytest.mark.parametrize(
    "to",
    ["victim@example.test\r\nBcc: evil@example.test", "a@example.test, evil@example.test"],
)
async def test_enqueue_injected_recipient_is_rejected(seeded, session_factory, notifications, to):
    from app.modules.notifications.rendering import InvalidRecipientError

    async with session_factory() as session:
        with pytest.raises(InvalidRecipientError):
            await notifications.enqueue(
                session, template_code="ACCOUNT_INVITATION", to=to, vars=invitation_vars()
            )
        await session.commit()
    assert await outbox_count(session_factory) == 0


async def test_enqueue_subject_line_breaks_are_removed(
    apply_cleanup, session_factory, notifications
) -> None:
    async with session_factory() as session:
        await insert_template(
            session,
            "TEST_SUBJECT",
            subject="Xin chào {full_name}",
            body="Nội dung cho {full_name}.",
            required_vars=["full_name"],
        )
        row_id = await notifications.enqueue(
            session,
            template_code="TEST_SUBJECT",
            to="a@example.test",
            vars={"full_name": "A\r\nBcc: evil@example.test"},
        )
        await session.commit()
    row = await outbox_row(session_factory, row_id)
    assert "\r" not in row.subject and "\n" not in row.subject


async def test_secret_enqueue_fails_closed_without_an_encryption_key(
    seeded, session_factory, settings
) -> None:
    from app.core.exceptions import AppError
    from app.modules.notifications.service import NotificationService

    keyless = NotificationService(settings.model_copy(update={"outbox_encryption_key": None}))
    async with session_factory() as session:
        with pytest.raises(AppError):
            await keyless.enqueue(
                session,
                template_code="ACCOUNT_INVITATION",
                to="nhan.vien@sis.hust.edu.vn",
                vars=invitation_vars(),
                secret_vars=frozenset({"set_password_url"}),
            )
        await session.rollback()
    assert await outbox_count(session_factory) == 0


# ---- queued secrets: encrypted while pending, gone after a terminal state -------------


async def test_queued_secret_is_unreadable_while_pending_and_removed_after_sent(
    seeded, session_factory, notifications, notify_settings
) -> None:
    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session,
            template_code="ACCOUNT_INVITATION",
            to="nhan.vien@sis.hust.edu.vn",
            vars=invitation_vars(),
            secret_vars=frozenset({"set_password_url"}),
        )
        await session.commit()
    pending = await outbox_row(session_factory, row_id)
    assert TOKEN not in pending.body

    sender = ScriptedEmailService()
    assert await run_worker_batch(session_factory, sender, notify_settings) == 1

    [message] = sender.delivered
    assert TOKEN in message.text_body and TOKEN in message.html_body
    done = await outbox_row(session_factory, row_id)
    assert done.status == "SENT"
    assert TOKEN not in done.body
    assert done.body != pending.body  # encrypted payload no longer kept


async def test_queued_secret_is_removed_after_failed(
    seeded, session_factory, notifications, notify_settings
) -> None:
    from app.integrations.email.errors import PermanentEmailError

    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session,
            template_code="ACCOUNT_INVITATION",
            to="nhan.vien@sis.hust.edu.vn",
            vars=invitation_vars(),
            secret_vars=frozenset({"set_password_url"}),
        )
        await session.commit()
    pending = await outbox_row(session_factory, row_id)

    sender = ScriptedEmailService(PermanentEmailError("smtp_550"))
    await run_worker_batch(session_factory, sender, notify_settings)

    done = await outbox_row(session_factory, row_id)
    assert done.status == "FAILED"
    assert TOKEN not in done.body and done.body != pending.body
    assert TOKEN not in (done.last_error or "")


# ---- sendNow --------------------------------------------------------------------------


async def test_send_now_records_a_durable_attempt_before_smtp_and_masks_the_otp(
    seeded, session_factory, notifications, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    seen_during_send = []

    async def inspect(message) -> None:
        async with session_factory() as other:
            row = (
                await other.execute(
                    text(
                        "SELECT status::text AS status, attempts, body FROM email_outbox"
                        " WHERE template_code = 'OTP_APPLY'"
                    )
                )
            ).one()
        seen_during_send.append(row)

    sender = ScriptedEmailService(on_send=inspect)
    result = await send_otp(notifications, session_factory, sender)

    [during] = seen_during_send
    assert during.status == "PENDING" and during.attempts == 1  # committed before SMTP
    assert OTP not in during.body

    [message] = sender.delivered
    assert message.to == "ung.vien@example.test"
    assert OTP in message.text_body and OTP in message.html_body
    assert message.message_id

    assert (result.status, result.attempts, result.error_code) == ("SENT", 1, None)
    row = await outbox_row(session_factory, result.outbox_id)
    assert row.status == "SENT" and row.attempts == 1 and row.sent_at is not None
    assert OTP not in row.body and OTP not in row.subject
    assert OTP not in repr(result)
    assert OTP not in caplog.text


@pytest.mark.parametrize("outcomes", [(), ("permanent",)], ids=["sent", "failed"])
async def test_otp_is_masked_even_if_the_caller_omits_secret_vars(
    seeded, session_factory, notifications, outcomes
) -> None:
    # Hồi quy: OTP_APPLY luôn coi otp_code là bí mật, kể cả khi caller quên khai báo.
    from app.integrations.email.errors import PermanentEmailError

    bodies_during_send = []
    query = text("SELECT body || subject FROM email_outbox WHERE template_code = 'OTP_APPLY'")

    async def inspect(message) -> None:
        async with session_factory() as other:
            bodies_during_send.append(await other.scalar(query))

    scripted = [PermanentEmailError("smtp_550") for _ in outcomes]
    sender = ScriptedEmailService(*scripted, on_send=inspect)
    result = await send_otp(notifications, session_factory, sender, secret_vars=frozenset())

    assert OTP in sender.attempted[0].text_body  # the recipient still gets the real code
    assert bodies_during_send and all(OTP not in body for body in bodies_during_send)
    row = await outbox_row(session_factory, result.outbox_id)
    assert row.status == ("FAILED" if outcomes else "SENT")
    assert OTP not in row.body and OTP not in row.subject


async def test_queued_otp_without_secret_vars_is_still_encrypted(
    seeded, session_factory, notifications
) -> None:
    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session, template_code="OTP_APPLY", to="ung.vien@example.test", vars=otp_vars()
        )
        await session.commit()
    row = await outbox_row(session_factory, row_id)
    assert OTP not in row.body and OTP not in row.subject


async def test_send_now_escapes_the_candidate_name_in_html(seeded, session_factory, notifications):
    script = "<script>alert(1)</script>"
    sender = ScriptedEmailService()
    await send_otp(notifications, session_factory, sender, vars=otp_vars(full_name=script))
    [message] = sender.delivered
    assert "<script>" not in message.html_body and "&lt;script&gt;" in message.html_body
    assert script in message.text_body


async def test_send_now_retries_once_on_a_temporary_error(seeded, session_factory, notifications):
    from app.integrations.email.errors import TemporaryEmailError

    sender = ScriptedEmailService(TemporaryEmailError("smtp_451"))
    result = await send_otp(notifications, session_factory, sender)
    assert len(sender.attempted) == 2
    assert (result.status, result.attempts) == ("SENT", 2)
    # Both attempts belong to the same outbox row and carry the same Message-ID.
    assert sender.attempted[0].message_id == sender.attempted[1].message_id


async def test_send_now_two_temporary_errors_fail_and_the_worker_never_resends(
    seeded, session_factory, notifications, notify_settings
) -> None:
    from app.integrations.email.errors import TemporaryEmailError

    sender = ScriptedEmailService(TemporaryEmailError("smtp_451"), TemporaryEmailError("smtp_421"))
    result = await send_otp(notifications, session_factory, sender)

    assert len(sender.attempted) == 2
    assert (result.status, result.attempts, result.error_code) == ("FAILED", 2, "smtp_421")
    row = await outbox_row(session_factory, result.outbox_id)
    assert (row.status, row.attempts, row.last_error) == ("FAILED", 2, "smtp_421")
    assert OTP not in row.body

    worker_sender = ScriptedEmailService()
    for later in (timedelta(minutes=5), timedelta(hours=1)):
        await run_worker_batch(session_factory, worker_sender, notify_settings, after=later)
    assert worker_sender.attempted == []


async def test_send_now_stops_at_the_first_permanent_error(seeded, session_factory, notifications):
    from app.integrations.email.errors import PermanentEmailError

    sender = ScriptedEmailService(PermanentEmailError("invalid_recipient"))
    result = await send_otp(notifications, session_factory, sender)
    assert len(sender.attempted) == 1
    assert (result.status, result.attempts, result.error_code) == (
        "FAILED",
        1,
        "invalid_recipient",
    )


async def test_worker_ignores_an_immediate_row_while_send_now_is_in_flight(
    seeded, session_factory, notifications, notify_settings
) -> None:
    worker_sender = ScriptedEmailService()
    processed: list[int] = []

    async def worker_runs_meanwhile(message) -> None:
        processed.append(
            await run_worker_batch(
                session_factory, worker_sender, notify_settings, after=timedelta(hours=1)
            )
        )

    sender = ScriptedEmailService(on_send=worker_runs_meanwhile)
    result = await send_otp(notifications, session_factory, sender)
    assert result.status == "SENT"
    assert worker_sender.attempted == []
    assert processed == [0]


@pytest.mark.parametrize(
    ("overrides", "error_name"),
    [
        ({"template_code": "NO_SUCH_TEMPLATE"}, "TemplateNotFoundError"),
        ({"vars": {"full_name": "A", "otp_code": OTP}}, "TemplateRenderError"),
        ({"to": "ung.vien@example.test\r\nBcc: evil@example.test"}, "InvalidRecipientError"),
    ],
)
async def test_send_now_rejects_bad_input_before_writing_or_sending(
    seeded, session_factory, notifications, overrides, error_name
) -> None:
    from app.modules.notifications import rendering, service

    error = getattr(service, error_name, None) or getattr(rendering, error_name)
    sender = ScriptedEmailService()
    with pytest.raises(error):
        await send_otp(notifications, session_factory, sender, **overrides)
    assert sender.attempted == []
    assert await outbox_count(session_factory) == 0


# ---- abandoned immediate sends (API stopped mid-send) ---------------------------------


async def otp_for(session_factory, world, **overrides) -> int:
    async with session_factory() as session:
        base = {
            "email": world.candidate_email,
            "submission_id": world.submission_id,
            "job_id": world.job_id,
        }
        otp_id = await insert_otp(session, **{**base, **overrides})
        await session.commit()
    return otp_id


async def otp_invalidated_at(session_factory, otp_id: int):
    async with session_factory() as session:
        return await session.scalar(
            text("SELECT invalidated_at FROM otp_codes WHERE id = :id"), {"id": otp_id}
        )


async def abandon_send_now(notifications, session_factory, world, otp_id: int) -> int:
    """Start sendNow, stop it while SMTP is in progress (as an API crash would)."""
    entered = asyncio.Event()

    async def hang(message) -> None:
        entered.set()
        await asyncio.Event().wait()

    sender = ScriptedEmailService(on_send=hang)
    task = asyncio.create_task(
        send_otp(
            notifications,
            session_factory,
            sender,
            to=world.candidate_email,
            immediate_metadata={"otp_id": otp_id},
        )
    )
    await asyncio.wait_for(entered.wait(), TIMEOUT)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, TIMEOUT)
    [row] = await outbox_rows(session_factory, "OTP_APPLY")
    return row.id


async def recover(session_factory, *, after: timedelta) -> int:
    from app.modules.notifications.worker import fail_abandoned_immediate

    return await fail_abandoned_immediate(session_factory, now_utc() + after)


async def test_abandoned_immediate_is_failed_after_the_safety_window_and_never_resent(
    seeded, session_factory, notifications, notify_settings
) -> None:
    world = await build_world(session_factory)
    otp_id = await otp_for(session_factory, world)
    row_id = await abandon_send_now(notifications, session_factory, world, otp_id)

    stuck = await outbox_row(session_factory, row_id)
    assert (stuck.status, stuck.attempts) == ("PENDING", 1)
    assert OTP not in stuck.body

    worker_sender = ScriptedEmailService()
    hour = timedelta(hours=1)
    await run_worker_batch(session_factory, worker_sender, notify_settings, after=hour)
    assert worker_sender.attempted == []

    # Still inside the sendNow budget: left alone.
    assert await recover(session_factory, after=timedelta(seconds=5)) == 0
    assert (await outbox_row(session_factory, row_id)).status == "PENDING"
    assert await otp_invalidated_at(session_factory, otp_id) is None

    assert await recover(session_factory, after=timedelta(minutes=2)) == 1
    failed = await outbox_row(session_factory, row_id)
    assert failed.status == "FAILED" and failed.attempts >= 1 and failed.last_error
    assert OTP not in failed.body
    assert await otp_invalidated_at(session_factory, otp_id) is not None

    assert await recover(session_factory, after=timedelta(minutes=3)) == 0
    await run_worker_batch(session_factory, worker_sender, notify_settings, after=2 * hour)
    assert worker_sender.attempted == []


async def test_abandoned_immediate_without_a_recorded_attempt_is_also_closed(
    seeded, session_factory, notifications
) -> None:
    world = await build_world(session_factory)
    otp_id = await otp_for(session_factory, world)
    row_id = await abandon_send_now(notifications, session_factory, world, otp_id)
    # Crash before the attempt was recorded: the row exists with attempts = 0.
    async with session_factory() as session:
        await session.execute(
            text("UPDATE email_outbox SET attempts = 0 WHERE id = :id"), {"id": row_id}
        )
        await session.commit()

    assert await recover(session_factory, after=timedelta(minutes=2)) == 1
    failed = await outbox_row(session_factory, row_id)
    # FAILED needs attempts >= 1 and last_error (email_outbox_failed_has_error).
    assert failed.status == "FAILED" and failed.attempts >= 1 and failed.last_error


async def test_recovery_invalidates_only_the_otp_of_the_abandoned_mail(
    seeded, session_factory, notifications
) -> None:
    world = await build_world(session_factory)
    old_otp = await otp_for(session_factory, world)
    row_id = await abandon_send_now(notifications, session_factory, world, old_otp)

    # The candidate asked for a new code meanwhile: old one invalidated, new one live.
    async with session_factory() as session:
        await session.execute(
            text("UPDATE otp_codes SET invalidated_at = now() WHERE id = :id"), {"id": old_otp}
        )
        await session.commit()
    old_invalidated = await otp_invalidated_at(session_factory, old_otp)
    new_otp = await otp_for(session_factory, world)

    assert await recover(session_factory, after=timedelta(minutes=2)) == 1
    assert (await outbox_row(session_factory, row_id)).status == "FAILED"
    assert await otp_invalidated_at(session_factory, new_otp) is None
    assert await otp_invalidated_at(session_factory, old_otp) == old_invalidated


async def test_recovery_leaves_queued_and_finished_rows_alone(
    seeded, session_factory, notifications
) -> None:
    async with session_factory() as session:
        queued = await notifications.enqueue(
            session,
            template_code="ACCOUNT_INVITATION",
            to="nhan.vien@sis.hust.edu.vn",
            vars=invitation_vars(),
            secret_vars=frozenset({"set_password_url"}),
        )
        await session.commit()
    sent = (await send_otp(notifications, session_factory, ScriptedEmailService())).outbox_id

    assert await recover(session_factory, after=timedelta(days=1)) == 0
    assert (await outbox_row(session_factory, queued)).status == "PENDING"
    assert (await outbox_row(session_factory, sent)).status == "SENT"
