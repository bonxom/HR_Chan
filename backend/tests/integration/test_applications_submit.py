# Nộp hồ sơ nguyên tử bằng OTP: đúng submission/tin/email/mục đích, capability có chữ ký và
# hạn, chặn trùng/đồng thời, tin đóng/hết hạn, liên hệ chỉ cập nhật sau OTP, rollback giữ
# OTP dùng được, không gửi thư xác nhận; dọn OTP cũ để không giữ FK tin/CV mãi.
"""``POST /api/v1/applications`` (plan task 7).

Contract:

* Body ``{submission_id, submission_token, job_id, otp_code}`` -> 201
  ``{application_id, submitted_at, message}``. In one transaction: lock the OTP,
  submission, candidate and job; verify the code (HMAC, live, not expired, purpose APPLY,
  same email/submission/job), the job is OPEN and its deadline not passed (company date),
  no application exists for candidate+job; update the candidate's verified contact; create
  the application (``SCORING``, ``ai_status=PENDING``, ``ai_total_score`` NULL,
  ``criteria_set_id`` = the job's current set); consume the OTP.
* Capability errors (forged, tampered, other submission, expired after 24 h) -> 403
  ``invalid_submission`` on both the OTP request and the submit.
* Errors: 409 ``already_applied`` (also the loser of a concurrent double submit),
  409 ``job_not_accepting``; wrong binding -> 422 on ``otp_code``.
* No confirmation email is sent.
* ``app.core.otp.cleanup.purge_stale_codes(session_factory, now) -> int`` deletes OTP rows
  whose ``expires_at`` is more than 24 h before ``now`` (beyond the hourly resend window
  and the 15-minute lock), so old codes never keep postings or CVs from being deleted.
"""

import asyncio
from datetime import datetime, timedelta

import pytest
from application_flow_support import (
    FailingTrigger,
    apply_cleanup,
    close_job,
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
    set_deadline,
    submit,
    upload_ok,
)
from apply_support import insert_account, insert_candidate, insert_otp, now_utc
from sqlalchemy import text

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup", "flow", "flow_cleanup", "flow_factory", "frozen_clock"]

EMAIL = "ung.vien@example.test"
TIMEOUT = 10.0


async def otp_for(flow_app, session_factory, *, email=EMAIL, job=None, **upload_fields):
    job = job or await insert_open_job(session_factory)
    submission = await upload_ok(flow_app.client, email=email, **upload_fields)
    response = await request_otp(flow_app.client, submission, job.id)
    assert response.status_code == 200, response.text
    return job, submission, last_otp(flow_app.email)


async def applications(session_factory) -> list:
    return await rows(
        session_factory,
        "SELECT id, candidate_id, job_id, submission_id, status::text AS status,"
        " ai_status::text AS ai_status, ai_total_score, criteria_set_id, submitted_at"
        " FROM applications ORDER BY id",
    )


# ---- success ----------------------------------------------------------------------------


async def test_valid_otp_creates_exactly_one_scoring_application(
    flow, session_factory, frozen_clock
) -> None:
    job, submission, code = await otp_for(
        flow, session_factory, full_name="Trần Thị Ứng Viên", phone="0987654321"
    )

    response = await submit(flow.client, submission, job.id, code)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) >= {"application_id", "submitted_at", "message"}
    assert "cảm ơn" in body["message"].lower()
    [application] = await applications(session_factory)
    assert application.id == body["application_id"]
    assert (application.status, application.ai_status) == ("SCORING", "PENDING")
    assert application.ai_total_score is None
    assert application.criteria_set_id == job.criteria_set_id
    assert application.submission_id == submission["submission_id"]
    assert application.submitted_at == frozen_clock.now
    datetime.fromisoformat(body["submitted_at"].replace("Z", "+00:00"))

    [candidate] = await rows(
        session_factory,
        "SELECT id, email, full_name, phone FROM candidates WHERE id = :i",
        i=application.candidate_id,
    )
    assert (candidate.email, candidate.full_name, candidate.phone) == (
        EMAIL,
        "Trần Thị Ứng Viên",
        "0987654321",
    )
    consumed = await scalar(
        session_factory, "SELECT count(*) FROM otp_codes WHERE consumed_at IS NOT NULL"
    )
    assert consumed == 1
    history = await rows(
        session_factory,
        "SELECT action FROM audit_events WHERE target_type = 'application' AND target_id = :i",
        i=str(application.id),
    )
    assert [row.action for row in history] == ["application.created"]

    # Only the OTP email exists: no submission confirmation email (context 00 §4.1).
    assert len(flow.email.attempted) == 1
    templates = await rows(session_factory, "SELECT template_code FROM email_outbox")
    assert [row.template_code for row in templates] == ["OTP_APPLY"]


async def test_verified_contact_replaces_existing_candidate_data_only_after_otp(
    flow, session_factory
) -> None:
    async with session_factory() as session:
        await insert_candidate(session, email=EMAIL, full_name="Tên cũ", phone="0900000000")
        await session.commit()

    job, submission, code = await otp_for(
        flow, session_factory, full_name="Tên mới", phone="0911111111"
    )
    before = await rows(session_factory, "SELECT full_name, phone FROM candidates")
    assert [(r.full_name, r.phone) for r in before] == [("Tên cũ", "0900000000")]

    assert (await submit(flow.client, submission, job.id, code)).status_code == 201
    after = await rows(session_factory, "SELECT full_name, phone FROM candidates")
    assert [(r.full_name, r.phone) for r in after] == [("Tên mới", "0911111111")]


# ---- binding ----------------------------------------------------------------------------


async def test_code_is_bound_to_its_job(flow, session_factory) -> None:
    job, submission, code = await otp_for(flow, session_factory)
    other_job = await insert_open_job(session_factory, title="Tin khác")

    errors = field_errors(await submit(flow.client, submission, other_job.id, code))
    assert "otp_code" in errors
    assert await applications(session_factory) == []


async def test_code_is_bound_to_its_submission_and_email(flow_factory, session_factory) -> None:
    victim = await flow_factory()
    attacker = await flow_factory(client_ip="198.51.100.9")
    job, _victim_submission, victim_code = await otp_for(victim, session_factory)
    attacker_submission = await upload_ok(attacker.client, email="ke.gian@example.test")

    errors = field_errors(await submit(attacker.client, attacker_submission, job.id, victim_code))
    assert "otp_code" in errors
    assert await applications(session_factory) == []


async def test_reset_password_code_cannot_submit_an_application(flow, session_factory) -> None:
    job = await insert_open_job(session_factory)
    submission = await upload_ok(flow.client, email=EMAIL)
    # A RESET_PASSWORD row for the same email (purpose binding); its hash is irrelevant.
    async with session_factory() as session:
        account = await insert_account(session, email=EMAIL)
        await insert_otp(session, email=EMAIL, purpose="RESET_PASSWORD", user_id=account)
        await session.commit()
    errors = field_errors(await submit(flow.client, submission, job.id, "123456"))
    assert "otp_code" in errors


# ---- capability -------------------------------------------------------------------------


async def test_forged_or_foreign_capability_is_refused(flow_factory, session_factory) -> None:
    owner = await flow_factory()
    other = await flow_factory(client_ip="198.51.100.10")
    job = await insert_open_job(session_factory)
    mine = await upload_ok(owner.client, email=EMAIL)
    theirs = await upload_ok(other.client, email="nguoi.khac@example.test")

    token = mine["submission_token"]
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    cases = [
        {**mine, "submission_token": "forged-token-value-0123456789abcdef"},
        {**mine, "submission_token": tampered},
        {**mine, "submission_id": theirs["submission_id"]},
        {**theirs, "submission_token": token},
    ]
    for submission in cases:
        response = await request_otp(owner.client, submission, job.id)
        assert response.status_code == 403, response.text
        assert error_code(response) == "invalid_submission"
        attempt = await submit(owner.client, submission, job.id, "123456")
        assert attempt.status_code == 403
    assert owner.email.attempted == []


async def test_capability_expires_after_24_hours(flow, session_factory, frozen_clock) -> None:
    job = await insert_open_job(session_factory)
    submission = await upload_ok(flow.client, email=EMAIL)
    frozen_clock.advance(hours=24, seconds=1)
    response = await request_otp(flow.client, submission, job.id)
    assert response.status_code == 403
    assert error_code(response) == "invalid_submission"


# ---- duplicates and concurrency ---------------------------------------------------------


async def test_one_application_per_email_and_job(flow, session_factory, frozen_clock) -> None:
    job, submission, code = await otp_for(flow, session_factory)
    assert (await submit(flow.client, submission, job.id, code)).status_code == 201

    replay = await submit(flow.client, submission, job.id, code)
    assert replay.status_code in (409, 422)

    frozen_clock.advance(minutes=2)
    again = await upload_ok(flow.client, email=EMAIL.upper())
    blocked = await request_otp(flow.client, again, job.id)
    assert blocked.status_code == 409
    assert error_code(blocked) == "already_applied"
    assert len(await applications(session_factory)) == 1


async def test_concurrent_double_submit_creates_only_one_application(
    flow_factory, session_factory
) -> None:
    first = await flow_factory()
    second = await flow_factory()
    job, submission, code = await otp_for(first, session_factory)

    responses = await asyncio.wait_for(
        asyncio.gather(
            submit(first.client, submission, job.id, code),
            submit(second.client, submission, job.id, code),
        ),
        TIMEOUT,
    )

    assert sorted(r.status_code for r in responses) == [201, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert error_code(loser) == "already_applied"
    assert "IntegrityError" not in loser.text and "duplicate key" not in loser.text
    assert len(await applications(session_factory)) == 1
    consumed = await scalar(
        session_factory, "SELECT count(*) FROM otp_codes WHERE consumed_at IS NOT NULL"
    )
    assert consumed == 1


# ---- posting state ----------------------------------------------------------------------


async def test_closed_posting_refuses_the_submit(flow, session_factory) -> None:
    job, submission, code = await otp_for(flow, session_factory)
    await close_job(session_factory, job.id)

    response = await submit(flow.client, submission, job.id, code)
    assert response.status_code == 409
    assert error_code(response) == "job_not_accepting"
    assert await applications(session_factory) == []


async def test_posting_past_its_deadline_refuses_even_before_the_sweep(
    flow, session_factory, frozen_clock
) -> None:
    from app.modules.recruitment.service import company_today

    job, submission, code = await otp_for(flow, session_factory)
    await set_deadline(session_factory, job.id, company_today(frozen_clock.now) - timedelta(days=1))

    response = await submit(flow.client, submission, job.id, code)
    assert response.status_code == 409
    assert error_code(response) == "job_not_accepting"


# ---- rollback keeps the code usable -----------------------------------------------------


async def test_failed_application_insert_keeps_the_otp_usable(flow, session_factory) -> None:
    job, submission, code = await otp_for(flow, session_factory)

    async with FailingTrigger(session_factory, "applications"):
        failed = await submit(flow.client, submission, job.id, code)
    assert failed.status_code >= 500
    assert "injected test failure" not in failed.text
    assert await applications(session_factory) == []
    unused = await scalar(
        session_factory, "SELECT count(*) FROM otp_codes WHERE consumed_at IS NULL"
    )
    assert unused == 1

    retried = await submit(flow.client, submission, job.id, code)
    assert retried.status_code == 201, retried.text


# ---- stale OTP cleanup ------------------------------------------------------------------


async def test_stale_codes_are_purged_so_they_never_block_deletion(flow, session_factory) -> None:
    from app.core.otp.cleanup import purge_stale_codes

    job, submission, _code = await otp_for(flow, session_factory)
    now = now_utc()
    recent_id = await scalar(session_factory, "SELECT max(id) FROM otp_codes")
    async with session_factory() as session:
        old_id = await insert_otp(
            session,
            email="cu@example.test",
            submission_id=submission["submission_id"],
            job_id=job.id,
            created_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=2) + timedelta(minutes=5),
            consumed_at=now - timedelta(days=2),
        )
        await session.commit()

    assert await purge_stale_codes(session_factory, now) == 1
    remaining = {row.id for row in await rows(session_factory, "SELECT id FROM otp_codes")}
    assert remaining == {recent_id}
    assert old_id not in remaining

    # Once every code of a posting is stale, nothing keeps the posting from being deleted.
    assert await purge_stale_codes(session_factory, now + timedelta(days=2)) == 1
    await close_job(session_factory, job.id)
    async with session_factory() as session:
        await session.execute(text("DELETE FROM cv_submissions"))
        await session.execute(text("DELETE FROM job_postings WHERE id = :j"), {"j": job.id})
        await session.commit()
