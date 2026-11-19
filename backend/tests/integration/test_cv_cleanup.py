# Dọn CV tạm sau 24 giờ: xóa bản ghi, OTP tham chiếu và file trong kho riêng; không xóa
# CV đã thành hồ sơ; kiểm tra lại dưới khóa khi có giao dịch nộp hồ sơ đang chạy.
"""Expired submission cleanup (plan task 6).

Contract: ``app.modules.candidates.cleanup.cleanup_expired_submissions(session_factory,
storage, now, *, batch_size=100) -> int`` removes submissions with ``expires_at <= now``
that no application references (their OTP rows first, then the row, then the encrypted
file) and returns how many were removed. Each submission is re-checked under a row lock;
a submission that becomes referenced meanwhile is kept. Files outside the store's own
keys are never touched. ``app.worker`` schedules it (see test_application_worker_jobs).
"""

import asyncio
from datetime import timedelta

import pytest
from application_flow_support import (
    apply_cleanup,
    flow_cleanup,
    insert_open_job,
    make_storage,
    rows,
    scalar,
    stored_files,
)
from apply_support import (
    insert_application,
    insert_candidate,
    insert_otp,
    insert_submission,
    now_utc,
)
from pydantic import SecretStr
from sqlalchemy import text

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup", "flow_cleanup"]

TIMEOUT = 10.0


@pytest.fixture
def store(flow_cleanup):
    class _Config:
        cv_storage_dir = flow_cleanup
        cv_encryption_key = SecretStr("test-cv-storage-encryption-key-0123456789ab")

    return make_storage(_Config)


async def make_submission(session_factory, store, *, age: timedelta, email: str) -> dict:
    key = await store.put(b"%PDF-1.4 encrypted cv for " + email.encode())
    created = now_utc() - age
    async with session_factory() as session:
        candidate_id = await insert_candidate(session, email=email)
        submission_id = await insert_submission(
            session,
            candidate_id,
            cv_storage_key=key,
            created_at=created,
            expires_at=created + timedelta(hours=24),
        )
        await session.commit()
    return {"id": submission_id, "key": key, "candidate_id": candidate_id}


async def run_cleanup(session_factory, store, now=None) -> int:
    from app.modules.candidates.cleanup import cleanup_expired_submissions

    return await cleanup_expired_submissions(session_factory, store, now or now_utc())


async def exists(session_factory, submission_id: int) -> bool:
    return bool(
        await scalar(
            session_factory, "SELECT count(*) FROM cv_submissions WHERE id = :i", i=submission_id
        )
    )


async def test_expired_unused_submissions_are_removed_with_their_files_and_otps(
    session_factory, store, flow_cleanup
) -> None:
    job = await insert_open_job(session_factory)
    expired = await make_submission(
        session_factory, store, age=timedelta(hours=25), email="het.han@example.test"
    )
    fresh = await make_submission(
        session_factory, store, age=timedelta(hours=1), email="con.han@example.test"
    )
    async with session_factory() as session:
        await insert_otp(
            session,
            email="het.han@example.test",
            submission_id=expired["id"],
            job_id=job.id,
            invalidated_at=now_utc() - timedelta(hours=24),
            created_at=now_utc() - timedelta(hours=25),
            expires_at=now_utc() - timedelta(hours=24, minutes=55),
        )
        await session.commit()

    assert await run_cleanup(session_factory, store) == 1

    assert not await exists(session_factory, expired["id"])
    assert await exists(session_factory, fresh["id"])
    otp_left = await scalar(
        session_factory, "SELECT count(*) FROM otp_codes WHERE submission_id = :i", i=expired["id"]
    )
    assert otp_left == 0
    names = {path.name for path in stored_files(flow_cleanup)}
    assert not any(expired["key"] in name for name in names)
    assert any(fresh["key"] in name for name in names)

    assert await run_cleanup(session_factory, store) == 0  # idempotent


async def test_submission_used_by_an_application_is_never_removed(
    session_factory, store, flow_cleanup
) -> None:
    job = await insert_open_job(session_factory)
    used = await make_submission(
        session_factory, store, age=timedelta(days=3), email="da.nop@example.test"
    )
    async with session_factory() as session:
        await insert_application(session, used["candidate_id"], job.id, used["id"])
        await session.commit()

    assert await run_cleanup(session_factory, store, now_utc() + timedelta(days=30)) == 0
    assert await exists(session_factory, used["id"])
    assert await store.get(used["key"])


async def test_cleanup_rechecks_under_lock_while_a_submit_is_in_flight(
    session_factory, store
) -> None:
    job = await insert_open_job(session_factory)
    racing = await make_submission(
        session_factory, store, age=timedelta(hours=24, seconds=1), email="dang.nop@example.test"
    )

    async with session_factory() as submitter:
        # Giao dịch nộp hồ sơ khóa submission và tạo application nhưng chưa commit.
        await submitter.execute(
            text("SELECT id FROM cv_submissions WHERE id = :i FOR UPDATE"), {"i": racing["id"]}
        )
        await insert_application(submitter, racing["candidate_id"], job.id, racing["id"])
        cleanup = asyncio.create_task(run_cleanup(session_factory, store))
        await asyncio.sleep(0.3)  # give the cleanup time to reach the locked row
        await submitter.commit()
    removed = await asyncio.wait_for(cleanup, TIMEOUT)

    assert removed == 0
    assert await exists(session_factory, racing["id"])
    assert await store.get(racing["key"])
    assert len(await rows(session_factory, "SELECT id FROM applications")) == 1


async def test_missing_file_does_not_block_row_cleanup(session_factory, store) -> None:
    gone = await make_submission(
        session_factory, store, age=timedelta(hours=30), email="mat.file@example.test"
    )
    await store.delete(gone["key"])
    assert await run_cleanup(session_factory, store) == 1
    assert not await exists(session_factory, gone["id"])


async def test_files_not_owned_by_the_store_are_untouched(
    session_factory, store, flow_cleanup, tmp_path
) -> None:
    outsider = tmp_path / "unrelated.pdf"
    outsider.write_bytes(b"belongs to someone else")
    await make_submission(
        session_factory, store, age=timedelta(hours=30), email="ngoai.kho@example.test"
    )
    await run_cleanup(session_factory, store)
    assert outsider.read_bytes() == b"belongs to someone else"
