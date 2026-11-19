# OTP nộp hồ sơ thật: 6 số, chỉ lưu băm, hạn 5 phút, sai 5 lần khóa 15 phút ngay ở lần 5,
# gửi lại sau 60 giây, tối đa 3 lần gửi lại/giờ, bền qua hai instance API, lỗi gửi vô hiệu
# đúng mã. Thời gian điều khiển bằng frozen_clock; email lấy từ dịch vụ email inject.
"""``POST /api/v1/applications/otp`` and OTP verification rules (plan task 7).

Contract:

* Request ``{submission_id, submission_token, job_id}`` -> 200
  ``{expires_at, resend_available_at}`` (server times; never the code). The code is
  delivered with ``NotificationService.sendNow`` (template OTP_APPLY) and stored only as
  an HMAC hash (``Settings.otp_secret``) bound to email, purpose APPLY, submission, job.
* ``POST /api/v1/applications`` with a wrong/expired/invalidated code -> 422 on
  ``otp_code`` (Vietnamese message). The 5th wrong entry locks for 15 minutes: that
  response and later ones are 429 ``otp_locked`` with ``Retry-After``; a resend does not
  lift the lock.
* Resend: same endpoint; before 60 s -> 429 ``rate_limited`` + ``Retry-After``; at most 3
  resends per hour per email (4th -> 429); a resend invalidates the previous code.
* Email failure -> 503 ``email_unavailable``; that code is invalidated (never newer ones).
* Limits live in PostgreSQL, so two API instances share them.
"""

import hashlib
from datetime import datetime, timedelta

import pytest
from application_flow_support import (
    apply_cleanup,
    error_code,
    field_errors,
    flow,
    flow_cleanup,
    flow_factory,
    frozen_clock,
    insert_open_job,
    last_otp,
    request_otp,
    rows,
    scalar,
    submit,
    upload_ok,
    wrong_code,
)

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup", "flow", "flow_cleanup", "flow_factory", "frozen_clock"]

EMAIL = "ung.vien@example.test"


@pytest.fixture
async def ready(flow, session_factory, frozen_clock):
    job = await insert_open_job(session_factory)
    submission = await upload_ok(flow.client, email=EMAIL)
    return job, submission


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def otp_rows(session_factory) -> list:
    return await rows(
        session_factory,
        "SELECT id, email, purpose::text AS purpose, code_hash, submission_id, job_id, attempts,"
        " expires_at, consumed_at, invalidated_at FROM otp_codes ORDER BY id",
    )


async def application_count(session_factory) -> int:
    return await scalar(session_factory, "SELECT count(*) FROM applications")


# ---- issuing ----------------------------------------------------------------------------


async def test_otp_is_sent_hashed_bound_and_timed_by_the_server(
    flow, ready, session_factory, frozen_clock
) -> None:
    job, submission = ready
    response = await request_otp(flow.client, submission, job.id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"expires_at", "resend_available_at"}
    assert parse(body["expires_at"]) == frozen_clock.now + timedelta(minutes=5)
    assert parse(body["resend_available_at"]) == frozen_clock.now + timedelta(seconds=60)

    code = last_otp(flow.email)
    assert len(code) == 6 and code.isdigit()
    assert code not in response.text
    [message] = flow.email.attempted
    assert message.to == EMAIL and job.title in message.text_body

    [otp] = await otp_rows(session_factory)
    assert (otp.email, otp.purpose) == (EMAIL, "APPLY")
    assert (otp.submission_id, otp.job_id) == (submission["submission_id"], job.id)
    assert code not in otp.code_hash
    assert otp.code_hash != hashlib.sha256(code.encode()).hexdigest()  # keyed HMAC, not bare
    assert otp.expires_at == frozen_clock.now + timedelta(minutes=5)

    outbox = await rows(
        session_factory,
        "SELECT status::text AS status, body, subject FROM email_outbox"
        " WHERE template_code = 'OTP_APPLY'",
    )
    assert [row.status for row in outbox] == ["SENT"]
    assert code not in outbox[0].body and code not in outbox[0].subject


async def test_codes_are_random(flow_factory, session_factory, frozen_clock) -> None:
    job = await insert_open_job(session_factory)
    codes = set()
    for n in range(6):
        app = await flow_factory(client_ip=f"198.51.100.{n + 1}")
        submission = await upload_ok(app.client, email=f"ngau.nhien.{n}@example.test")
        assert (await request_otp(app.client, submission, job.id)).status_code == 200
        codes.add(last_otp(app.email))
    assert len(codes) >= 5


# ---- wrong, expired, lock ---------------------------------------------------------------


async def test_wrong_code_is_an_otp_field_error(flow, ready, session_factory) -> None:
    job, submission = ready
    await request_otp(flow.client, submission, job.id)
    code = last_otp(flow.email)

    errors = field_errors(await submit(flow.client, submission, job.id, wrong_code(code)))
    assert "otp_code" in errors and errors["otp_code"]
    [otp] = await otp_rows(session_factory)
    assert otp.attempts == 1 and otp.consumed_at is None
    assert await application_count(session_factory) == 0


async def test_expired_code_is_rejected(flow, ready, session_factory, frozen_clock) -> None:
    job, submission = ready
    await request_otp(flow.client, submission, job.id)
    code = last_otp(flow.email)
    frozen_clock.advance(minutes=5, seconds=1)

    errors = field_errors(await submit(flow.client, submission, job.id, code))
    assert "otp_code" in errors
    assert await application_count(session_factory) == 0


async def test_fifth_wrong_code_locks_for_fifteen_minutes(
    flow, ready, session_factory, frozen_clock
) -> None:
    job, submission = ready
    await request_otp(flow.client, submission, job.id)
    code = last_otp(flow.email)
    bad = wrong_code(code)

    for _ in range(4):
        field_errors(await submit(flow.client, submission, job.id, bad))
    fifth = await submit(flow.client, submission, job.id, bad)
    assert fifth.status_code == 429, fifth.text
    assert error_code(fifth) == "otp_locked"
    assert 840 < int(fifth.headers["Retry-After"]) <= 900
    [otp] = await otp_rows(session_factory)
    assert otp.attempts == 5

    # Even the right code is refused while locked.
    locked = await submit(flow.client, submission, job.id, code)
    assert locked.status_code == 429
    assert await application_count(session_factory) == 0

    # A resend does not lift the lock.
    frozen_clock.advance(minutes=2)
    resend = await request_otp(flow.client, submission, job.id)
    assert resend.status_code in (200, 429)
    if resend.status_code == 200:
        still = await submit(flow.client, submission, job.id, last_otp(flow.email))
        assert still.status_code == 429

    frozen_clock.advance(minutes=14)
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    # Khóa đã hết hạn: mã mới có ngân sách nhập sai mới, một lần sai chỉ là 422 chứ không phải 429.
    assert (await otp_rows(session_factory))[-1].attempts == 0
    new_code = last_otp(flow.email)
    field_errors(await submit(flow.client, submission, job.id, wrong_code(new_code)))
    accepted = await submit(flow.client, submission, job.id, new_code)
    assert accepted.status_code == 201, accepted.text


async def test_wrong_code_budget_survives_resends(
    flow, ready, session_factory, frozen_clock
) -> None:
    job, submission = ready
    await request_otp(flow.client, submission, job.id)
    for _ in range(4):
        field_errors(
            await submit(flow.client, submission, job.id, wrong_code(last_otp(flow.email)))
        )

    # Mã mới sau cooldown không được đặt lại ngân sách nhập sai: lần sai thứ 5 vẫn khóa 15 phút.
    frozen_clock.advance(seconds=61)
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    fifth = await submit(flow.client, submission, job.id, wrong_code(last_otp(flow.email)))
    assert fifth.status_code == 429, fifth.text
    assert error_code(fifth) == "otp_locked"
    assert 840 < int(fifth.headers["Retry-After"]) <= 900
    # Mã đúng của lần gửi lại cũng bị từ chối khi đang khóa.
    locked = await submit(flow.client, submission, job.id, last_otp(flow.email))
    assert locked.status_code == 429
    assert await application_count(session_factory) == 0


async def test_lock_is_shared_by_two_api_instances(
    flow_factory, session_factory, frozen_clock
) -> None:
    job = await insert_open_job(session_factory)
    first = await flow_factory()
    second = await flow_factory()
    submission = await upload_ok(first.client, email=EMAIL)
    await request_otp(first.client, submission, job.id)
    code = last_otp(first.email)

    for n in range(4):
        app = first if n % 2 else second
        field_errors(await submit(app.client, submission, job.id, wrong_code(code)))
    assert (await submit(second.client, submission, job.id, wrong_code(code))).status_code == 429
    assert (await submit(first.client, submission, job.id, code)).status_code == 429


# ---- resend -----------------------------------------------------------------------------


async def test_resend_waits_sixty_seconds_and_invalidates_the_old_code(
    flow, ready, session_factory, frozen_clock
) -> None:
    job, submission = ready
    await request_otp(flow.client, submission, job.id)
    old = last_otp(flow.email)

    frozen_clock.advance(seconds=30)
    early = await request_otp(flow.client, submission, job.id)
    assert early.status_code == 429
    assert error_code(early) == "rate_limited"
    assert 1 <= int(early.headers["Retry-After"]) <= 30
    assert len(flow.email.attempted) == 1

    frozen_clock.advance(seconds=31)
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    new = last_otp(flow.email)

    live = [row for row in await otp_rows(session_factory) if row.invalidated_at is None]
    assert len(live) == 1
    if new != old:
        assert "otp_code" in field_errors(await submit(flow.client, submission, job.id, old))
    assert (await submit(flow.client, submission, job.id, new)).status_code == 201


async def test_at_most_three_resends_per_hour_across_instances(
    flow_factory, session_factory, frozen_clock
) -> None:
    job = await insert_open_job(session_factory)
    first = await flow_factory()
    second = await flow_factory()
    submission = await upload_ok(first.client, email=EMAIL)

    assert (await request_otp(first.client, submission, job.id)).status_code == 200
    for n in range(3):
        frozen_clock.advance(seconds=61)
        app = second if n % 2 == 0 else first
        assert (await request_otp(app.client, submission, job.id)).status_code == 200
    frozen_clock.advance(seconds=61)
    fourth = await request_otp(first.client, submission, job.id)
    assert fourth.status_code == 429
    assert int(fourth.headers["Retry-After"]) > 0

    frozen_clock.advance(hours=1)
    assert (await request_otp(second.client, submission, job.id)).status_code == 200


# ---- delivery failure -------------------------------------------------------------------


async def test_failed_delivery_invalidates_exactly_that_code(
    flow, ready, session_factory, frozen_clock
) -> None:
    from app.integrations.email.errors import TemporaryEmailError

    job, submission = ready
    flow.email.outcomes = [TemporaryEmailError("smtp_451"), TemporaryEmailError("smtp_451")]
    failed = await request_otp(flow.client, submission, job.id)
    assert failed.status_code == 503
    assert error_code(failed) == "email_unavailable"
    [otp] = await otp_rows(session_factory)
    assert otp.invalidated_at is not None
    for leaked in ("smtp", "451", last_otp(flow.email)):
        assert leaked not in failed.text

    # The next request (after the cooldown) gets a working code; the old row stays dead.
    frozen_clock.advance(seconds=61)
    flow.email.outcomes = []
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    first, second = await otp_rows(session_factory)
    assert first.invalidated_at is not None and second.invalidated_at is None
    accepted = await submit(flow.client, submission, job.id, last_otp(flow.email))
    assert accepted.status_code == 201, accepted.text


async def test_permanent_delivery_failure_is_reported_once(flow, ready, session_factory) -> None:
    from app.integrations.email.errors import PermanentEmailError

    job, submission = ready
    flow.email.outcomes = [PermanentEmailError("invalid_recipient")]
    failed = await request_otp(flow.client, submission, job.id)
    assert failed.status_code == 503
    assert len(flow.email.attempted) == 1  # no retry on a permanent error
    [otp] = await otp_rows(session_factory)
    assert otp.invalidated_at is not None


async def test_otp_cannot_be_requested_for_a_job_that_is_not_open(
    flow, ready, session_factory
) -> None:
    from application_flow_support import close_job

    job, submission = ready
    await close_job(session_factory, job.id)
    response = await request_otp(flow.client, submission, job.id)
    assert response.status_code == 409
    assert error_code(response) == "job_not_accepting"
    assert flow.email.attempted == []
    assert await otp_rows(session_factory) == []


async def test_unknown_job_is_404(flow, ready) -> None:
    _job, submission = ready
    response = await request_otp(flow.client, submission, 9_000_000_000)
    assert response.status_code == 404
    assert error_code(response) == "job_not_found"


async def test_failed_resend_preserves_wrong_code_budget(flow, ready, frozen_clock) -> None:
    """SMTP hỏng không được xóa số lần sai đã tích lũy của email."""
    from app.integrations.email.errors import PermanentEmailError

    job, submission = ready
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    for _ in range(4):
        field_errors(
            await submit(flow.client, submission, job.id, wrong_code(last_otp(flow.email)))
        )

    frozen_clock.advance(seconds=61)
    flow.email.outcomes = [PermanentEmailError("invalid_recipient")]
    failed = await request_otp(flow.client, submission, job.id)
    assert failed.status_code == 503
    assert error_code(failed) == "email_unavailable"

    frozen_clock.advance(seconds=61)
    flow.email.outcomes = []
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    fifth = await submit(flow.client, submission, job.id, wrong_code(last_otp(flow.email)))
    assert fifth.status_code == 429
    assert error_code(fifth) == "otp_locked"
