# Cạnh tranh trong luồng ứng tuyển, mỗi request/giao dịch dùng session độc lập: đóng tin
# đang giữ khóa khi ứng viên nộp, gửi OTP đồng thời, nhập sai đồng thời. Không bọc chung
# một transaction, không SQLite.
"""Concurrency of the OTP/application flow (plan task 7).

Contract (in addition to test_apply_otp/test_applications_submit):

* The submit locks the posting row (FOR SHARE or FOR UPDATE) and re-checks its status
  after acquiring the lock: an HR close that commits first wins and the submit returns
  409 ``job_not_accepting`` without creating an application.
* Concurrent OTP requests for one email are serialized: one 200, the others 429; exactly
  one live code and one email.
* Concurrent wrong codes never exceed ``attempts = 5`` (CHECK) and never surface a 500.
"""

import asyncio

import pytest
from application_flow_support import (
    apply_cleanup,
    error_code,
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
from sqlalchemy import text

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup", "flow_cleanup", "flow_factory", "frozen_clock"]

EMAIL = "ung.vien@example.test"
TIMEOUT = 10.0


async def wait_for_lock_waiter(session_factory, table: str) -> None:
    """Return once another backend waits on a row lock while touching ``table``."""

    async def poll() -> None:
        while True:
            async with session_factory() as session:
                waiting = await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity"
                        " WHERE datname = current_database() AND pid <> pg_backend_pid()"
                        " AND wait_event_type = 'Lock' AND query ILIKE :pattern"
                    ),
                    {"pattern": f"%{table}%"},
                )
            if waiting:
                return
            await asyncio.sleep(0.02)

    await asyncio.wait_for(poll(), TIMEOUT)


async def test_close_holding_the_lock_wins_over_a_submit(
    flow_factory, session_factory, frozen_clock
) -> None:
    app = await flow_factory()
    job = await insert_open_job(session_factory)
    submission = await upload_ok(app.client, email=EMAIL)
    assert (await request_otp(app.client, submission, job.id)).status_code == 200
    code = last_otp(app.email)

    submit_task: asyncio.Task | None = None
    async with session_factory() as hr:
        # Giao dịch đóng tin của HR đang giữ khóa dòng tin, chưa commit.
        await hr.execute(
            text("SELECT id FROM job_postings WHERE id = :j FOR UPDATE"), {"j": job.id}
        )
        await hr.execute(
            text("UPDATE job_postings SET status = 'CLOSED', closed_at = now() WHERE id = :j"),
            {"j": job.id},
        )
        submit_task = asyncio.create_task(submit(app.client, submission, job.id, code))
        try:
            await wait_for_lock_waiter(session_factory, "job_postings")
            assert not submit_task.done()
        finally:
            await hr.commit()
    response = await asyncio.wait_for(submit_task, TIMEOUT)

    assert response.status_code == 409, response.text
    assert error_code(response) == "job_not_accepting"
    assert await scalar(session_factory, "SELECT count(*) FROM applications") == 0
    # The code was not consumed by a submit that created nothing.
    consumed = await scalar(
        session_factory, "SELECT count(*) FROM otp_codes WHERE consumed_at IS NOT NULL"
    )
    assert consumed == 0


async def test_concurrent_otp_requests_issue_a_single_code(
    flow_factory, session_factory, frozen_clock
) -> None:
    first = await flow_factory()
    second = await flow_factory()
    job = await insert_open_job(session_factory)
    submission = await upload_ok(first.client, email=EMAIL)

    responses = await asyncio.wait_for(
        asyncio.gather(
            request_otp(first.client, submission, job.id),
            request_otp(second.client, submission, job.id),
            request_otp(first.client, submission, job.id),
        ),
        TIMEOUT,
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 429, 429], [r.text for r in responses]
    live = await rows(
        session_factory,
        "SELECT id FROM otp_codes WHERE consumed_at IS NULL AND invalidated_at IS NULL",
    )
    assert len(live) == 1
    assert len(first.email.attempted) + len(second.email.attempted) == 1


async def test_resend_and_submit_lock_in_the_same_order(
    flow_factory, session_factory, frozen_clock
) -> None:
    app = await flow_factory()
    job = await insert_open_job(session_factory)
    submission = await upload_ok(app.client, email=EMAIL)
    assert (await request_otp(app.client, submission, job.id)).status_code == 200
    frozen_clock.advance(seconds=61)

    resend_task: asyncio.Task | None = None
    async with session_factory() as holder:
        # Giao dịch nộp hồ sơ: khóa submission trước, rồi mới khóa OTP.
        await holder.execute(
            text("SELECT id FROM cv_submissions WHERE id = :s FOR UPDATE"),
            {"s": submission["submission_id"]},
        )
        resend_task = asyncio.create_task(request_otp(app.client, submission, job.id))
        try:
            # Gửi lại phải đang chờ khóa; không thể chắc chắn khóa nào, nên chờ bất kỳ waiter.
            await wait_for_lock_waiter(session_factory, "")
            assert not resend_task.done()
            # Cùng thứ tự khóa => không deadlock; nếu ngược thứ tự PostgreSQL sẽ hủy một bên.
            await asyncio.wait_for(
                holder.execute(
                    text("SELECT id FROM otp_codes WHERE submission_id = :s FOR UPDATE"),
                    {"s": submission["submission_id"]},
                ),
                TIMEOUT,
            )
        finally:
            await holder.commit()
    response = await asyncio.wait_for(resend_task, TIMEOUT)

    assert response.status_code == 200, response.text
    live = await rows(
        session_factory,
        "SELECT id FROM otp_codes WHERE consumed_at IS NULL AND invalidated_at IS NULL",
    )
    assert len(live) == 1


async def test_concurrent_wrong_codes_respect_the_attempt_limit(
    flow_factory, session_factory, frozen_clock
) -> None:
    first = await flow_factory()
    second = await flow_factory()
    job = await insert_open_job(session_factory)
    submission = await upload_ok(first.client, email=EMAIL)
    await request_otp(first.client, submission, job.id)
    bad = wrong_code(last_otp(first.email))

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                submit((first if n % 2 else second).client, submission, job.id, bad)
                for n in range(8)
            )
        ),
        TIMEOUT,
    )

    assert all(r.status_code in (422, 429) for r in responses), [r.text for r in responses]
    assert sum(r.status_code == 429 for r in responses) >= 3
    attempts = await scalar(session_factory, "SELECT max(attempts) FROM otp_codes")
    assert attempts == 5
    assert await scalar(session_factory, "SELECT count(*) FROM applications") == 0
