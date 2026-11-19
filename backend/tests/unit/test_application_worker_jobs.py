# Lịch worker cho dọn CV tạm hết hạn và OTP cũ: chạy trong tiến trình worker riêng, mỗi
# job một instance, dùng chung session_factory, lỗi chỉ log tên loại, không đổi lịch cũ.
"""Cleanup schedules in ``app.worker`` (plan tasks 6–7).

Reuses the fake engine/scheduler harness of ``test_recruitment_worker``. Contract:

* module-level names ``cleanup_expired_submissions`` (from
  ``app.modules.candidates.cleanup``), ``purge_stale_codes`` (from
  ``app.core.otp.cleanup``) and ``build_cv_storage(settings)`` (returns the configured
  encrypted store; built once at startup, never at import time);
* job IDs ``CV_CLEANUP_JOB_ID`` and ``OTP_CLEANUP_JOB_ID``, interval jobs with
  ``max_instances=1`` next to the existing recruitment and outbox jobs;
* ``cleanup_expired_submissions(session_factory, storage, now)`` and
  ``purge_stale_codes(session_factory, now)`` with an aware ``now``.
"""

import logging
from datetime import datetime

import pytest
import test_recruitment_worker as worker_suite

harness = worker_suite.harness
invoke = worker_suite.invoke
start_worker = worker_suite.start_worker
stop_worker = worker_suite.stop_worker
worker_settings = worker_suite.worker_settings
DB_PASSWORD = worker_suite.DB_PASSWORD


class Calls:
    def __init__(self) -> None:
        self.cv: list[tuple] = []
        self.otp: list[tuple] = []
        self.storage = object()
        self.cv_error: Exception | None = None


@pytest.fixture
def cleanups(harness, monkeypatch) -> Calls:
    from app import worker

    calls = Calls()

    async def fake_cleanup(session_factory, storage, now) -> int:
        calls.cv.append((session_factory, storage, now))
        if calls.cv_error is not None:
            raise calls.cv_error
        return 0

    async def fake_purge(session_factory, now) -> int:
        calls.otp.append((session_factory, now))
        return 0

    async def no_outbox(*args, **kwargs) -> int:
        return 0

    monkeypatch.setattr(worker, "cleanup_expired_submissions", fake_cleanup)
    monkeypatch.setattr(worker, "purge_stale_codes", fake_purge)
    monkeypatch.setattr(worker, "build_cv_storage", lambda settings: calls.storage)
    monkeypatch.setattr(worker, "deliver_due_batch", no_outbox)
    monkeypatch.setattr(worker, "fail_abandoned_immediate", no_outbox)
    return calls


def job_by_id(scheduler, job_id: str):
    jobs = [job for job in scheduler.jobs if job.options.get("id") == job_id]
    assert len(jobs) == 1, [job.options.get("id") for job in scheduler.jobs]
    return jobs[0]


async def test_cleanup_jobs_are_scheduled_and_use_the_shared_session_factory(
    harness, cleanups
) -> None:
    from app import worker

    stop, task = await start_worker(harness, worker_settings())
    try:
        scheduler = harness.scheduler
        cv_job = job_by_id(scheduler, worker.CV_CLEANUP_JOB_ID)
        otp_job = job_by_id(scheduler, worker.OTP_CLEANUP_JOB_ID)
        for job in (cv_job, otp_job):
            assert job.options.get("max_instances", 1) == 1
        # Existing schedules are still there.
        for job_id in (worker.SWEEP_JOB_ID, worker.PURGE_JOB_ID, worker.OUTBOX_JOB_ID):
            job_by_id(scheduler, job_id)

        await invoke(cv_job)
        await invoke(otp_job)
        session_factory, storage, now = cleanups.cv[-1]
        assert session_factory is harness.sweep_factories[0]
        assert storage is cleanups.storage
        assert isinstance(now, datetime) and now.utcoffset() is not None
        otp_factory, otp_now = cleanups.otp[-1]
        assert otp_factory is harness.sweep_factories[0]
        assert otp_now.utcoffset() is not None
    finally:
        await stop_worker(stop, task)


async def test_failed_cleanup_is_logged_by_type_only(harness, cleanups, caplog) -> None:
    from app import worker

    caplog.set_level(logging.DEBUG)
    cleanups.cv_error = RuntimeError(f"cannot reach {worker_suite.DB_URL}")
    stop, task = await start_worker(harness, worker_settings())
    try:
        await invoke(job_by_id(harness.scheduler, worker.CV_CLEANUP_JOB_ID))
        assert not task.done()
    finally:
        await stop_worker(stop, task)
    assert task.exception() is None
    assert "RuntimeError" in caplog.text
    assert DB_PASSWORD not in caplog.text
