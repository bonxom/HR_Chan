# Worker outbox trên PostgreSQL riêng: thử lại 4 lượt cách 5 phút, lỗi vĩnh viễn dừng ngay,
# giới hạn N, SKIP LOCKED giữa hai worker độc lập, báo HR khi FAILED và không lặp cảnh báo.
"""Outbox worker (plan task 4).

Contract of ``app.modules.notifications.worker``:

* ``await deliver_due_batch(session_factory, email_service, settings, now) -> int``:
  claims at most ``settings.email_outbox_batch_size`` queued PENDING rows with
  ``next_attempt_at <= now`` using ``FOR UPDATE SKIP LOCKED``, keeps each lock until the
  result is written, and returns how many rows it attempted. Immediate (sendNow) rows
  are never claimed.
* Result per attempt: success -> SENT, sent_at, attempts + 1; temporary error ->
  attempts + 1 and next_attempt_at = result time + 5 minutes; the 4th failure or a
  permanent error -> FAILED with the normalized error code in last_error.
* On FAILED with an application: ``applications.email_issue`` (<= 100 characters) and
  one EMAIL_DELIVERY_FAILED alert per ACTIVE account holding the HR role. Alerts never
  produce further alerts and never overwrite email_issue; their failure is only logged.
* Message-ID is stable per outbox row across attempts (``EmailMessage.message_id``).

All rows are created through ``NotificationService.enqueue`` and committed, then each
worker run opens its own sessions from ``session_factory`` (independent connections).
"""

import asyncio
import logging
from datetime import timedelta

import pytest
from apply_support import (
    ScriptedEmailService,
    apply_cleanup,
    build_world,
    insert_account,
    insert_application,
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
TOKEN = "queued-secret-token-9c1e"
TIMEOUT = 10.0
STEP = timedelta(minutes=6)  # comfortably past the 5-minute retry delay
TEMPLATE = "TEST_WORKER"


@pytest.fixture
def worker_settings(settings):
    return settings.model_copy(
        update={"outbox_encryption_key": SecretStr(TEST_OUTBOX_KEY), "email_outbox_batch_size": 10}
    )


@pytest.fixture
def notifications(worker_settings):
    from app.modules.notifications.service import NotificationService

    return NotificationService(worker_settings)


@pytest.fixture
async def templates(apply_cleanup, session_factory) -> None:
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as session:
        await seed_email_templates(session)
        await insert_template(
            session,
            TEMPLATE,
            subject="Thông báo cho {full_name}",
            body="Xin chào {full_name}, liên kết: {secret_link}",
            required_vars=["full_name", "secret_link"],
        )
        await session.commit()


async def queue(notifications, session_factory, *, to="nguoi.nhan@example.test", **extra) -> int:
    async with session_factory() as session:
        row_id = await notifications.enqueue(
            session,
            template_code=TEMPLATE,
            to=to,
            vars={"full_name": "Người Nhận", "secret_link": f"https://x.test/#t={TOKEN}"},
            secret_vars=frozenset({"secret_link"}),
            **extra,
        )
        await session.commit()
    return row_id


async def run(session_factory, service, settings, at) -> int:
    from app.modules.notifications.worker import deliver_due_batch

    return await deliver_due_batch(session_factory, service, settings, at)


def temporary(code: str = "smtp_451"):
    from app.integrations.email.errors import TemporaryEmailError

    return TemporaryEmailError(code)


def permanent(code: str = "smtp_550"):
    from app.integrations.email.errors import PermanentEmailError

    return PermanentEmailError(code)


# ---- retry policy ---------------------------------------------------------------------


async def test_two_temporary_failures_then_success_takes_three_attempts(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)
    sender = ScriptedEmailService(temporary(), temporary())
    t0 = now_utc()

    assert await run(session_factory, sender, worker_settings, t0) == 1
    first = await outbox_row(session_factory, row_id)
    assert (first.status, first.attempts, first.last_error) == ("PENDING", 1, "smtp_451")
    assert first.next_attempt_at >= t0 + timedelta(minutes=5)

    # Not due before the 5-minute delay has passed.
    assert await run(session_factory, sender, worker_settings, t0 + timedelta(minutes=4)) == 0
    assert len(sender.attempted) == 1

    assert await run(session_factory, sender, worker_settings, t0 + STEP) == 1
    assert await run(session_factory, sender, worker_settings, t0 + 2 * STEP) == 1

    done = await outbox_row(session_factory, row_id)
    assert (done.status, done.attempts) == ("SENT", 3)
    assert done.sent_at is not None
    assert len(sender.attempted) == 3 and len(sender.delivered) == 1
    message_ids = {message.message_id for message in sender.attempted}
    assert len(message_ids) == 1 and None not in message_ids


async def test_four_temporary_failures_end_failed_without_a_fifth_attempt(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)
    sender = ScriptedEmailService(*(temporary(f"smtp_45{n}") for n in range(5)))
    t0 = now_utc()
    for n in range(6):
        await run(session_factory, sender, worker_settings, t0 + n * STEP)

    row = await outbox_row(session_factory, row_id)
    assert (row.status, row.attempts, row.last_error) == ("FAILED", 4, "smtp_453")
    assert len(sender.attempted) == 4
    assert TOKEN not in row.body


async def test_permanent_error_fails_on_the_first_attempt(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)
    sender = ScriptedEmailService(permanent("smtp_550"))
    t0 = now_utc()
    for n in range(3):
        await run(session_factory, sender, worker_settings, t0 + n * STEP)

    row = await outbox_row(session_factory, row_id)
    assert (row.status, row.attempts, row.last_error) == ("FAILED", 1, "smtp_550")
    assert len(sender.attempted) == 1


async def test_batch_is_limited_to_n_rows(
    templates, session_factory, notifications, worker_settings
) -> None:
    for n in range(5):
        await queue(notifications, session_factory, to=f"nguoi.{n}@example.test")
    small = worker_settings.model_copy(update={"email_outbox_batch_size": 2})
    sender = ScriptedEmailService()
    at = now_utc()

    assert await run(session_factory, sender, small, at) == 2
    assert len(sender.attempted) == 2
    assert await run(session_factory, sender, small, at) == 2
    assert await run(session_factory, sender, small, at) == 1
    assert await run(session_factory, sender, small, at) == 0
    assert sorted(m.to for m in sender.delivered) == [f"nguoi.{n}@example.test" for n in range(5)]


async def test_rows_not_yet_due_are_left_alone(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE email_outbox SET next_attempt_at = now() + interval '1 hour' WHERE id = :id"
            ),
            {"id": row_id},
        )
        await session.commit()
    sender = ScriptedEmailService()
    assert await run(session_factory, sender, worker_settings, now_utc()) == 0
    assert sender.attempted == []
    later = now_utc() + timedelta(hours=2)
    assert await run(session_factory, sender, worker_settings, later) == 1


async def test_sent_and_failed_rows_are_never_picked_again(
    templates, session_factory, notifications, worker_settings
) -> None:
    sent = await queue(notifications, session_factory, to="a@example.test")
    failed = await queue(notifications, session_factory, to="b@example.test")
    sender = ScriptedEmailService()
    # One row is delivered, the other fails permanently.
    first = ScriptedEmailService(None, permanent())
    await run(session_factory, first, worker_settings, now_utc())
    statuses = {(await outbox_row(session_factory, i)).status for i in (sent, failed)}
    assert statuses == {"SENT", "FAILED"}

    assert await run(session_factory, sender, worker_settings, now_utc() + timedelta(days=1)) == 0
    assert sender.attempted == []


async def test_corrupted_body_is_never_sent(
    templates, session_factory, notifications, worker_settings, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    row_id = await queue(notifications, session_factory)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE email_outbox SET body = 'không phải envelope hợp lệ' WHERE id = :id"),
            {"id": row_id},
        )
        await session.commit()
    sender = ScriptedEmailService()
    await run(session_factory, sender, worker_settings, now_utc())

    assert sender.attempted == []
    row = await outbox_row(session_factory, row_id)
    assert row.status == "FAILED" and row.last_error
    assert "không phải envelope" not in caplog.text


async def test_tampered_ciphertext_is_never_sent(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)
    async with session_factory() as session:
        body = await session.scalar(
            text("SELECT body FROM email_outbox WHERE id = :id"), {"id": row_id}
        )
        # Flip one character near the end (inside the encrypted payload of the envelope).
        index = len(body) - 10
        flipped = body[:index] + ("A" if body[index] != "A" else "B") + body[index + 1 :]
        await session.execute(
            text("UPDATE email_outbox SET body = :b WHERE id = :id"), {"b": flipped, "id": row_id}
        )
        await session.commit()
    sender = ScriptedEmailService()
    await run(session_factory, sender, worker_settings, now_utc())
    assert sender.attempted == []
    assert (await outbox_row(session_factory, row_id)).status != "SENT"


async def test_pending_row_without_attempts_left_fails_before_smtp(
    templates, session_factory, notifications, worker_settings
) -> None:
    # Hồi quy: dòng PENDING attempts=4 từng bị gửi SMTP lần 5 rồi commit lỗi CHECK.
    world = await build_world(session_factory)
    app_id = await application_for(session_factory, world)
    row_id = await queue(
        notifications, session_factory, to=world.candidate_email, application_id=app_id
    )
    async with session_factory() as session:
        await session.execute(
            text("UPDATE email_outbox SET attempts = 4, last_error = 'smtp_451' WHERE id = :id"),
            {"id": row_id},
        )
        await session.commit()

    sender = ScriptedEmailService()
    assert await run(session_factory, sender, worker_settings, now_utc()) == 1

    assert sender.attempted == []
    row = await outbox_row(session_factory, row_id)
    assert (row.status, row.attempts) == ("FAILED", 4)
    assert row.last_error and TOKEN not in row.last_error
    assert TOKEN not in row.body
    assert await email_issue(session_factory, app_id)
    alerts = await outbox_rows(session_factory, "EMAIL_DELIVERY_FAILED")
    assert [alert.user_id for alert in alerts] == [world.hr_id]
    # Not picked again.
    assert await run(session_factory, sender, worker_settings, now_utc() + STEP) == 1  # alert
    assert all(m.to != world.candidate_email for m in sender.attempted)


# ---- concurrency: two independent workers ---------------------------------------------


async def test_two_workers_never_send_the_same_row(
    templates, session_factory, notifications, worker_settings
) -> None:
    ids = [
        await queue(notifications, session_factory, to=f"song.song.{n}@example.test")
        for n in range(3)
    ]
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold_first_send(message) -> None:
        # Gate: worker A keeps its claimed rows locked until the test releases it.
        if not entered.is_set():
            entered.set()
            await asyncio.wait_for(release.wait(), TIMEOUT)

    sender_a = ScriptedEmailService(on_send=hold_first_send)
    sender_b = ScriptedEmailService()
    at = now_utc()
    worker_a = asyncio.create_task(run(session_factory, sender_a, worker_settings, at))
    try:
        await asyncio.wait_for(entered.wait(), TIMEOUT)
        # Worker B runs while A holds its locks: it must skip, not wait and not resend.
        processed_b = await asyncio.wait_for(
            run(session_factory, sender_b, worker_settings, at), TIMEOUT
        )
    finally:
        release.set()
        processed_a = await asyncio.wait_for(worker_a, TIMEOUT)

    delivered = [m.to for m in sender_a.delivered + sender_b.delivered]
    assert sorted(delivered) == sorted(set(delivered))  # no address delivered twice
    assert processed_a + processed_b == 3
    assert len(delivered) == 3
    for row_id in ids:
        row = await outbox_row(session_factory, row_id)
        assert (row.status, row.attempts) == ("SENT", 1)


async def test_concurrent_batches_with_a_small_limit_split_the_rows(
    templates, session_factory, notifications, worker_settings
) -> None:
    for n in range(4):
        await queue(notifications, session_factory, to=f"chia.{n}@example.test")
    small = worker_settings.model_copy(update={"email_outbox_batch_size": 2})
    barrier = asyncio.Barrier(2)

    def meet_once():
        # Both workers must be inside a send (holding their claimed locks) at the same
        # time; a worker that waited for the other's locks would never reach the barrier.
        reached = False

        async def meet(message) -> None:
            nonlocal reached
            if not reached:
                reached = True
                await asyncio.wait_for(barrier.wait(), TIMEOUT)

        return meet

    sender_a = ScriptedEmailService(on_send=meet_once())
    sender_b = ScriptedEmailService(on_send=meet_once())
    at = now_utc()
    results = await asyncio.wait_for(
        asyncio.gather(
            run(session_factory, sender_a, small, at), run(session_factory, sender_b, small, at)
        ),
        TIMEOUT * 2,
    )
    assert results == [2, 2]
    a = {m.to for m in sender_a.delivered}
    b = {m.to for m in sender_b.delivered}
    assert a.isdisjoint(b) and len(a | b) == 4


# ---- crash between SMTP acceptance and commit -----------------------------------------


class SimulatedCrash(BaseException):
    """Process death after SMTP accepted the message, before the result was committed."""


async def test_crash_after_smtp_accept_may_resend_with_the_same_message_id(
    templates, session_factory, notifications, worker_settings
) -> None:
    row_id = await queue(notifications, session_factory)

    async def crash_after_accept(message) -> None:
        crashing.delivered.append(message)  # SMTP accepted it
        raise SimulatedCrash

    crashing = ScriptedEmailService(on_send=crash_after_accept)
    with pytest.raises(SimulatedCrash):
        await run(session_factory, crashing, worker_settings, now_utc())

    # Nothing was committed: the row is still PENDING and is delivered again next run.
    assert (await outbox_row(session_factory, row_id)).status == "PENDING"
    retry = ScriptedEmailService()
    assert await run(session_factory, retry, worker_settings, now_utc() + STEP) == 1
    assert (await outbox_row(session_factory, row_id)).status == "SENT"
    # At-least-once, not exactly-once: the receiver can de-duplicate by Message-ID.
    assert retry.delivered[0].message_id == crashing.delivered[0].message_id


# ---- FAILED -> email_issue and HR alerts ----------------------------------------------


async def hr_accounts(session_factory, world) -> dict[str, object]:
    async with session_factory() as session:
        accounts = {
            "hr_active": world.hr_id,
            "hr_multi_role": await insert_account(session, roles=["INTERVIEWER", "HR"]),
            "hr_locked": await insert_account(session, roles=["HR"], status="LOCKED"),
            "hr_disabled": await insert_account(session, roles=["HR"], status="DISABLED"),
            "hr_pending": await insert_account(session, roles=["HR"], status="PENDING_SETUP"),
            "interviewer": await insert_account(session, roles=["INTERVIEWER"]),
            "admin": await insert_account(session, roles=[], account_type="ADMIN"),
        }
        await session.commit()
    return accounts


async def application_for(session_factory, world) -> int:
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.commit()
    return app_id


async def email_issue(session_factory, app_id: int):
    async with session_factory() as session:
        return await session.scalar(
            text("SELECT email_issue FROM applications WHERE id = :id"), {"id": app_id}
        )


async def test_failed_mail_flags_the_application_and_alerts_active_hr_only(
    templates, session_factory, notifications, worker_settings
) -> None:
    world = await build_world(session_factory)
    accounts = await hr_accounts(session_factory, world)
    app_id = await application_for(session_factory, world)
    row_id = await queue(
        notifications, session_factory, to=world.candidate_email, application_id=app_id
    )

    refusing = ScriptedEmailService(permanent("smtp_550"))
    await run(session_factory, refusing, worker_settings, now_utc())

    assert (await outbox_row(session_factory, row_id)).status == "FAILED"
    issue = await email_issue(session_factory, app_id)
    assert issue and len(issue) <= 100
    assert "smtp_550" in issue
    assert TOKEN not in issue

    alerts = await outbox_rows(session_factory, "EMAIL_DELIVERY_FAILED")
    assert {row.user_id for row in alerts} == {accounts["hr_active"], accounts["hr_multi_role"]}
    assert all(row.status == "PENDING" for row in alerts)
    for row in alerts:
        assert TOKEN not in row.body and world.candidate_email not in row.subject


async def test_alerts_are_delivered_by_the_next_run(
    templates, session_factory, notifications, worker_settings
) -> None:
    world = await build_world(session_factory)
    app_id = await application_for(session_factory, world)
    await queue(notifications, session_factory, to=world.candidate_email, application_id=app_id)
    await run(session_factory, ScriptedEmailService(permanent()), worker_settings, now_utc())

    sender = ScriptedEmailService()
    assert await run(session_factory, sender, worker_settings, now_utc()) == 1
    [alert] = sender.delivered
    assert str(app_id) in alert.text_body
    assert TOKEN not in alert.text_body and TOKEN not in alert.html_body


async def test_failed_alert_creates_no_further_alert_and_keeps_the_original_issue(
    templates, session_factory, notifications, worker_settings, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    world = await build_world(session_factory)
    app_id = await application_for(session_factory, world)
    await queue(notifications, session_factory, to=world.candidate_email, application_id=app_id)
    refusing = ScriptedEmailService(permanent("smtp_550"))
    await run(session_factory, refusing, worker_settings, now_utc())
    original_issue = await email_issue(session_factory, app_id)
    alerts_before = await outbox_rows(session_factory, "EMAIL_DELIVERY_FAILED")
    assert len(alerts_before) == 1

    # Every alert keeps failing until it is FAILED.
    failing = ScriptedEmailService(*(temporary("smtp_421") for _ in range(10)))
    t0 = now_utc()
    for n in range(6):
        await run(session_factory, failing, worker_settings, t0 + n * STEP)

    alerts_after = await outbox_rows(session_factory, "EMAIL_DELIVERY_FAILED")
    assert [row.id for row in alerts_after] == [row.id for row in alerts_before]
    assert alerts_after[0].status == "FAILED"
    assert await email_issue(session_factory, app_id) == original_issue
    assert "smtp_421" in caplog.text  # the alert failure is logged (code only)


async def test_failure_without_an_application_raises_no_alert(
    templates, session_factory, notifications, worker_settings
) -> None:
    await build_world(session_factory)  # an active HR account exists
    await queue(notifications, session_factory)
    await run(session_factory, ScriptedEmailService(permanent()), worker_settings, now_utc())
    assert await outbox_rows(session_factory, "EMAIL_DELIVERY_FAILED") == []


async def test_worker_logs_no_secret_body_or_recipient(
    templates, session_factory, notifications, worker_settings, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    await queue(notifications, session_factory, to="rieng.tu@example.test")
    await queue(notifications, session_factory, to="rieng.tu.2@example.test")
    sender = ScriptedEmailService(None, permanent("smtp_550"))
    await run(session_factory, sender, worker_settings, now_utc())
    for leaked in (TOKEN, "rieng.tu@example.test", "rieng.tu.2@example.test", "Người Nhận"):
        assert leaked not in caplog.text
