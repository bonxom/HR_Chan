# Lịch worker outbox: chạy mỗi 30 giây, max_instances=1, phục hồi immediate bỏ dở,
# giữ hai lịch tuyển dụng cũ và chờ lượt gửi đang chạy trước khi đóng engine.
"""Outbox scheduling inside the existing worker process (plan task 4).

Reuses the fake engine/scheduler harness of ``test_recruitment_worker`` so the two
recruitment schedules are exercised by the same fakes. Contract of ``app.worker``:

* module-level names ``deliver_due_batch``, ``fail_abandoned_immediate`` (imported from
  ``app.modules.notifications.worker``) and ``build_email_service`` (from
  ``app.integrations.email.service``), so they can be replaced here;
* job IDs ``OUTBOX_JOB_ID`` and ``ABANDONED_JOB_ID`` next to ``SWEEP_JOB_ID`` and
  ``PURGE_JOB_ID``;
* settings ``email_outbox_interval_seconds`` (default 30) and
  ``email_outbox_batch_size`` (positive).

The outbox job calls ``deliver_due_batch(session_factory, email_service, settings, now)``
and the recovery job ``fail_abandoned_immediate(session_factory, now)`` with an aware
``now``. Neither replaces nor reschedules the recruitment jobs.
"""

import asyncio
import logging
from datetime import datetime

import pytest
import test_recruitment_worker as worker_suite
from pydantic import ValidationError

from app.core.config import Settings

harness = worker_suite.harness
invoke = worker_suite.invoke
interval_seconds = worker_suite.interval_seconds
let_loop_run = worker_suite.let_loop_run
start_worker = worker_suite.start_worker
stop_worker = worker_suite.stop_worker
worker_settings = worker_suite.worker_settings
DB_PASSWORD = worker_suite.DB_PASSWORD
TIMEOUT = worker_suite.TIMEOUT


class OutboxCalls:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.batches: list[tuple] = []
        self.recoveries: list[tuple] = []
        self.services: list[object] = []
        self.batch_error: Exception | None = None
        self.hold: asyncio.Event | None = None
        self.entered = asyncio.Event()


@pytest.fixture
def outbox(harness, monkeypatch) -> OutboxCalls:
    from app import worker

    calls = OutboxCalls()
    service = object()

    def fake_build_email_service(settings) -> object:
        calls.services.append(settings)
        return service

    async def fake_deliver_due_batch(session_factory, email_service, settings, now) -> int:
        calls.events.append("outbox")
        calls.batches.append((session_factory, email_service, settings, now))
        calls.entered.set()
        if calls.hold is not None:
            try:
                await calls.hold.wait()
            except asyncio.CancelledError:
                calls.events.append("outbox.cancelled")
                raise
        calls.events.append("outbox.done")
        harness.events.append("outbox.done")
        if calls.batch_error is not None:
            raise calls.batch_error
        return 0

    async def fake_fail_abandoned_immediate(session_factory, now) -> int:
        calls.recoveries.append((session_factory, now))
        return 0

    monkeypatch.setattr(worker, "build_email_service", fake_build_email_service)
    monkeypatch.setattr(worker, "deliver_due_batch", fake_deliver_due_batch)
    monkeypatch.setattr(worker, "fail_abandoned_immediate", fake_fail_abandoned_immediate)
    calls.service = service
    try:
        yield calls
    finally:
        if calls.hold is not None:
            calls.hold.set()


def job_by_id(scheduler, job_id: str):
    jobs = [job for job in scheduler.jobs if job.options.get("id") == job_id]
    assert len(jobs) == 1, [job.options.get("id") for job in scheduler.jobs]
    return jobs[0]


# ---- settings -------------------------------------------------------------------------


def test_outbox_interval_defaults_to_30_seconds(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_OUTBOX_INTERVAL_SECONDS", raising=False)
    assert Settings(_env_file=None).email_outbox_interval_seconds == 30


def test_outbox_settings_read_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_OUTBOX_INTERVAL_SECONDS", "45")
    monkeypatch.setenv("EMAIL_OUTBOX_BATCH_SIZE", "7")
    settings = Settings(_env_file=None)
    assert settings.email_outbox_interval_seconds == 45
    assert settings.email_outbox_batch_size == 7


def test_default_batch_size_is_positive(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_OUTBOX_BATCH_SIZE", raising=False)
    assert Settings(_env_file=None).email_outbox_batch_size > 0


@pytest.mark.parametrize("field", ["email_outbox_interval_seconds", "email_outbox_batch_size"])
@pytest.mark.parametrize("value", [0, -1])
def test_outbox_settings_reject_non_positive_values(field, value) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


# ---- scheduling -----------------------------------------------------------------------


async def test_worker_schedules_the_outbox_every_30_seconds_with_one_instance(
    harness, outbox
) -> None:
    from app import worker

    settings = worker_settings(interval=17).model_copy(update={"email_outbox_interval_seconds": 30})
    stop, task = await start_worker(harness, settings)
    try:
        scheduler = harness.scheduler
        job = job_by_id(scheduler, worker.OUTBOX_JOB_ID)
        assert interval_seconds(job) == 30
        assert job.options.get("max_instances", 1) == 1
        assert job.options.get("coalesce") is True

        before = len(outbox.batches)
        await invoke(job)
        assert len(outbox.batches) == before + 1
        session_factory, email_service, passed_settings, now = outbox.batches[-1]
        assert session_factory is harness.sweep_factories[0]  # same engine/sessionmaker
        assert email_service is outbox.service
        assert passed_settings is settings
        assert isinstance(now, datetime) and now.utcoffset() is not None
        assert outbox.services == [settings]  # the email service is built once
    finally:
        await stop_worker(stop, task)


async def test_worker_schedules_recovery_of_abandoned_immediate_mail(harness, outbox) -> None:
    from app import worker

    stop, task = await start_worker(harness, worker_settings())
    try:
        job = job_by_id(harness.scheduler, worker.ABANDONED_JOB_ID)
        assert job.options.get("max_instances", 1) == 1
        before = len(outbox.recoveries)
        await invoke(job)
        assert len(outbox.recoveries) == before + 1
        session_factory, now = outbox.recoveries[-1]
        assert session_factory is harness.sweep_factories[0]
        assert isinstance(now, datetime) and now.utcoffset() is not None
    finally:
        await stop_worker(stop, task)


async def test_recruitment_schedules_are_unchanged(harness, outbox) -> None:
    from app import worker

    stop, task = await start_worker(harness, worker_settings(interval=17))
    try:
        scheduler = harness.scheduler
        sweep = job_by_id(scheduler, worker.SWEEP_JOB_ID)
        assert interval_seconds(sweep) == 17
        purge = job_by_id(scheduler, worker.PURGE_JOB_ID)
        assert worker_suite.is_cron(purge)
        ids = {job.options.get("id") for job in scheduler.jobs}
        assert {
            worker.SWEEP_JOB_ID,
            worker.PURGE_JOB_ID,
            worker.OUTBOX_JOB_ID,
            worker.ABANDONED_JOB_ID,
        } <= ids

        sweeps = harness.events.count("sweep")
        await invoke(job_by_id(scheduler, worker.OUTBOX_JOB_ID))
        assert harness.events.count("sweep") == sweeps  # outbox run does not sweep jobs
    finally:
        await stop_worker(stop, task)


async def test_failed_outbox_batch_is_logged_by_type_and_keeps_the_schedule(
    harness, outbox, caplog
) -> None:
    from app import worker

    caplog.set_level(logging.DEBUG)
    outbox.batch_error = RuntimeError(f"connect failed for {worker_suite.DB_URL}")
    stop, task = await start_worker(harness, worker_settings())
    try:
        job = job_by_id(harness.scheduler, worker.OUTBOX_JOB_ID)
        await invoke(job)
        await invoke(job)
        assert outbox.events.count("outbox") >= 2
        assert not task.done()
    finally:
        await stop_worker(stop, task)

    assert task.exception() is None
    assert "RuntimeError" in caplog.text
    assert DB_PASSWORD not in caplog.text


async def test_stop_waits_for_an_in_flight_outbox_batch_before_dispose(harness, outbox) -> None:
    from app import worker

    stop, task = await start_worker(harness, worker_settings())
    outbox.hold = asyncio.Event()
    outbox.entered.clear()
    harness.background.append(
        asyncio.ensure_future(invoke(job_by_id(harness.scheduler, worker.OUTBOX_JOB_ID)))
    )
    await asyncio.wait_for(outbox.entered.wait(), TIMEOUT)

    stop.set()
    await let_loop_run()
    assert not task.done()
    assert harness.engine.disposed == 0

    outbox.hold.set()
    await asyncio.wait_for(task, TIMEOUT)

    assert task.exception() is None
    assert "outbox.cancelled" not in outbox.events
    last_done = worker_suite.last_index(harness.events, "outbox.done")
    assert last_done < harness.events.index("engine.dispose")
