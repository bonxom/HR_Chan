# Fake scheduler/session giúp kiểm lịch mà không chạy cron hay database thật.
# Event giữ tác vụ để kiểm shutdown có chờ công việc đang chạy kết thúc.
"""Expiry worker: one sweep per session, scheduling and orderly shutdown.

`app.worker` is imported inside each test/fixture so a missing worker module fails
these tests individually instead of breaking collection of the whole suite.

The fakes stand in for the database engine and APScheduler's `AsyncIOScheduler`; the
worker is expected to use the module-level names `create_async_engine`,
`AsyncIOScheduler`, `close_expired_once` and `purge_closed_once` (see the approved plan).

The retention purge (CLOSED postings two years after closing) is a separate task of the
same worker: it runs once at startup and then daily on a cron trigger in company time
(UTC+7), independently of the close-expired interval.
"""

import asyncio
import contextlib
import inspect
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

TIMEOUT = 5.0
DB_PASSWORD = "worker-secret-pw"
DB_URL = f"postgresql+asyncpg://worker_user:{DB_PASSWORD}@localhost:5432/worker_db"
INTERVAL_UNITS = {"weeks": 604800, "days": 86400, "hours": 3600, "minutes": 60, "seconds": 1}


def worker_settings(interval: int = 17) -> Settings:
    return Settings(_env_file=None, database_url=DB_URL, job_expiry_interval_seconds=interval)


# ---- settings -----------------------------------------------------------------------


def test_job_expiry_interval_defaults_to_60_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOB_EXPIRY_INTERVAL_SECONDS", raising=False)
    assert Settings(_env_file=None).job_expiry_interval_seconds == 60


def test_job_expiry_interval_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOB_EXPIRY_INTERVAL_SECONDS", "15")
    assert Settings(_env_file=None).job_expiry_interval_seconds == 15


@pytest.mark.parametrize("value", [0, -1, -60])
def test_job_expiry_interval_rejects_nonpositive_values(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, job_expiry_interval_seconds=value)


# ---- close_expired_once -------------------------------------------------------------


class FakeSessionFactory:
    """Async context manager factory that records how its sessions are used."""

    def __init__(self) -> None:
        self.session = object()
        self.entered = 0
        self.exited = 0

    def __call__(self):
        return self._session()

    @asynccontextmanager
    async def _session(self):
        self.entered += 1
        try:
            yield self.session
        finally:
            self.exited += 1


async def test_close_expired_once_sweeps_inside_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.recruitment.service import JobPostingService
    from app.worker import close_expired_once

    factory = FakeSessionFactory()
    calls: list[tuple[object, int, int]] = []

    async def fake_close_expired_jobs(self, now=None) -> list[int]:
        calls.append((self.session, factory.entered, factory.exited))
        return [11, 12, 13]

    monkeypatch.setattr(JobPostingService, "close_expired_jobs", fake_close_expired_jobs)

    assert await close_expired_once(factory) == 3
    assert calls == [(factory.session, 1, 0)]
    assert (factory.entered, factory.exited) == (1, 1)


async def test_close_expired_once_returns_zero_when_nothing_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.recruitment.service import JobPostingService
    from app.worker import close_expired_once

    async def nothing_expired(self, now=None) -> list[int]:
        return []

    monkeypatch.setattr(JobPostingService, "close_expired_jobs", nothing_expired)
    factory = FakeSessionFactory()

    assert await close_expired_once(factory) == 0
    assert (factory.entered, factory.exited) == (1, 1)


async def test_close_expired_once_releases_the_session_when_the_sweep_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.recruitment.service import JobPostingService
    from app.worker import close_expired_once

    async def failing(self, now=None) -> list[int]:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(JobPostingService, "close_expired_jobs", failing)
    factory = FakeSessionFactory()

    with contextlib.suppress(RuntimeError):
        await close_expired_once(factory)
    assert (factory.entered, factory.exited) == (1, 1)


# ---- purge_closed_once --------------------------------------------------------------


async def test_purge_closed_once_purges_inside_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.recruitment.service import JobPostingService
    from app.worker import purge_closed_once

    factory = FakeSessionFactory()
    calls: list[tuple[object, int, int]] = []

    async def fake_purge(self, now=None, batch_size=100) -> list[int]:
        calls.append((self.session, factory.entered, factory.exited))
        return [21, 22]

    monkeypatch.setattr(JobPostingService, "purge_closed_jobs", fake_purge)

    assert await purge_closed_once(factory) == 2
    assert calls == [(factory.session, 1, 0)]
    assert (factory.entered, factory.exited) == (1, 1)


async def test_purge_closed_once_releases_the_session_when_the_purge_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.recruitment.service import JobPostingService
    from app.worker import purge_closed_once

    async def failing(self, now=None, batch_size=100) -> list[int]:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(JobPostingService, "purge_closed_jobs", failing)
    factory = FakeSessionFactory()

    with contextlib.suppress(RuntimeError):
        await purge_closed_once(factory)
    assert (factory.entered, factory.exited) == (1, 1)


# ---- run_worker ---------------------------------------------------------------------


@dataclass
class ScheduledJob:
    func: Any
    trigger: Any
    args: tuple
    kwargs: dict
    options: dict


@dataclass
class Harness:
    events: list[str] = field(default_factory=list)
    engine_urls: list[str] = field(default_factory=list)
    engines: list["FakeEngine"] = field(default_factory=list)
    schedulers: list["FakeScheduler"] = field(default_factory=list)
    sweep_factories: list[object] = field(default_factory=list)
    swept: asyncio.Event = field(default_factory=asyncio.Event)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    sweep_error: Exception | None = None
    start_error: Exception | None = None
    # When set, each sweep blocks after starting until this event is set.
    hold: asyncio.Event | None = None
    background: list[asyncio.Future] = field(default_factory=list)
    # Retention purge fake (separate from the close-expired sweep).
    purge_factories: list[object] = field(default_factory=list)
    purged: asyncio.Event = field(default_factory=asyncio.Event)
    purge_error: Exception | None = None
    purge_hold: asyncio.Event | None = None

    @property
    def scheduler(self) -> "FakeScheduler":
        assert len(self.schedulers) == 1
        return self.schedulers[0]

    @property
    def engine(self) -> "FakeEngine":
        assert len(self.engines) == 1
        return self.engines[0]


class FakeEngine:
    def __init__(self, harness: Harness) -> None:
        self.harness = harness
        self.disposed = 0

    async def dispose(self, *args, **kwargs) -> None:
        self.disposed += 1
        self.harness.events.append("engine.dispose")


async def invoke(job: ScheduledJob) -> None:
    result = job.func(*job.args, **job.kwargs)
    if inspect.isawaitable(result):
        await result


class FakeScheduler:
    """Records jobs; never fires interval runs on its own.

    A job registered with ``next_run_time`` is run once when the scheduler is running,
    which is how APScheduler would honour an "immediately" request. Like APScheduler,
    job exceptions are swallowed rather than stopping the scheduler.
    """

    def __init__(self, harness: Harness, *args, **kwargs) -> None:
        self.harness = harness
        self.init_kwargs = kwargs
        self.jobs: list[ScheduledJob] = []
        self.running = False
        self.shutdown_calls: list[dict] = []

    def _fire_if_immediate(self, job: ScheduledJob) -> None:
        if self.running and job.options.get("next_run_time") is not None:

            async def run() -> None:
                with contextlib.suppress(Exception):
                    await invoke(job)

            self.harness.background.append(asyncio.ensure_future(run()))

    def add_job(self, func, trigger=None, args=None, kwargs=None, **options) -> ScheduledJob:
        job = ScheduledJob(func, trigger, tuple(args or ()), dict(kwargs or {}), options)
        self.jobs.append(job)
        self._fire_if_immediate(job)
        return job

    def start(self, *args, **kwargs) -> None:
        self.harness.events.append("scheduler.start")
        if self.harness.start_error is not None:
            raise self.harness.start_error
        self.running = True
        self.harness.started.set()
        for job in self.jobs:
            self._fire_if_immediate(job)

    def pause(self) -> None:
        # Mirrors BaseScheduler.pause(): stops processing jobs until resumed.
        self.harness.events.append("scheduler.pause")

    def shutdown(self, wait: bool = True) -> None:
        self.harness.events.append("scheduler.shutdown")
        self.shutdown_calls.append({"wait": wait})
        self.running = False
        # Like AsyncIOExecutor.shutdown: pending job futures are cancelled even with wait.
        for future in self.harness.background:
            if not future.done():
                future.cancel()


def is_interval(job: ScheduledJob) -> bool:
    return job.trigger == "interval" or hasattr(job.trigger, "interval")


def interval_seconds(job: ScheduledJob) -> float:
    if isinstance(job.trigger, str):
        return float(sum(job.options.get(unit, 0) * size for unit, size in INTERVAL_UNITS.items()))
    return job.trigger.interval.total_seconds()


def interval_job(scheduler: "FakeScheduler") -> ScheduledJob:
    """The close-expired interval job (the worker also runs outbox interval jobs)."""
    from app.worker import SWEEP_JOB_ID

    jobs = [
        job for job in scheduler.jobs if is_interval(job) and job.options.get("id") == SWEEP_JOB_ID
    ]
    assert len(jobs) == 1, scheduler.jobs
    return jobs[0]


@pytest.fixture
async def harness(monkeypatch: pytest.MonkeyPatch):
    from app import worker

    state = Harness()

    def fake_create_async_engine(url, *args, **kwargs) -> FakeEngine:
        state.engine_urls.append(str(url))
        engine = FakeEngine(state)
        state.engines.append(engine)
        return engine

    def fake_scheduler(*args, **kwargs) -> FakeScheduler:
        scheduler = FakeScheduler(state, *args, **kwargs)
        state.schedulers.append(scheduler)
        return scheduler

    async def fake_close_expired_once(session_factory) -> int:
        state.events.append("sweep")
        state.sweep_factories.append(session_factory)
        state.swept.set()
        if state.hold is not None:
            try:
                await state.hold.wait()
            except asyncio.CancelledError:
                state.events.append("sweep.cancelled")
                raise
        state.events.append("sweep.done")
        if state.sweep_error is not None:
            raise state.sweep_error
        return 0

    async def fake_purge_closed_once(session_factory) -> int:
        state.events.append("purge")
        state.purge_factories.append(session_factory)
        state.purged.set()
        if state.purge_hold is not None:
            try:
                await state.purge_hold.wait()
            except asyncio.CancelledError:
                state.events.append("purge.cancelled")
                raise
        state.events.append("purge.done")
        if state.purge_error is not None:
            raise state.purge_error
        return 0

    monkeypatch.setattr(worker, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(worker, "AsyncIOScheduler", fake_scheduler)
    monkeypatch.setattr(worker, "close_expired_once", fake_close_expired_once)
    # raising=False: the expiry tests above keep running while the purge is not built yet;
    # the purge tests below fail until the worker calls this module-level name.
    monkeypatch.setattr(worker, "purge_closed_once", fake_purge_closed_once, raising=False)
    try:
        yield state
    finally:
        if state.hold is not None:
            state.hold.set()
        if state.purge_hold is not None:
            state.purge_hold.set()
        for task in state.background:
            task.cancel()
        await asyncio.gather(*state.background, return_exceptions=True)


async def start_worker(state: Harness, settings: Settings) -> tuple[asyncio.Event, asyncio.Task]:
    from app import worker

    stop = asyncio.Event()
    task = asyncio.create_task(worker.run_worker(settings, stop))
    ready = asyncio.ensure_future(asyncio.gather(state.started.wait(), state.swept.wait()))
    done, _pending = await asyncio.wait(
        {ready, task}, timeout=TIMEOUT, return_when=asyncio.FIRST_COMPLETED
    )
    if ready in done:
        return stop, task
    ready.cancel()
    stop.set()
    if task in done:
        task.result()  # surfaces the worker's own exception
        pytest.fail("run_worker returned before starting the scheduler and sweeping")
    task.cancel()
    await asyncio.gather(ready, task, return_exceptions=True)
    pytest.fail("run_worker did not start the scheduler and sweep within the timeout")


async def stop_worker(stop: asyncio.Event, task: asyncio.Task) -> None:
    stop.set()
    await asyncio.wait_for(task, TIMEOUT)


async def test_run_worker_sweeps_immediately_and_schedules_the_interval(
    harness: Harness,
) -> None:
    settings = worker_settings(interval=17)
    stop, task = await start_worker(harness, settings)
    try:
        assert not task.done()
        assert harness.engine_urls == [str(settings.database_url)]
        # The fake scheduler never fires interval runs, so this sweep is the startup one.
        assert harness.events.count("sweep") == 1

        scheduler = harness.scheduler
        assert scheduler.running
        job = interval_job(scheduler)
        assert interval_seconds(job) == 17
        # No overlapping sweeps: a single running instance (APScheduler's default is 1).
        assert job.options.get("max_instances", 1) == 1

        await invoke(job)
        assert harness.events.count("sweep") == 2
        assert harness.sweep_factories[1] is harness.sweep_factories[0]
    finally:
        await stop_worker(stop, task)


async def test_run_worker_shuts_down_scheduler_then_disposes_engine_on_stop(
    harness: Harness,
) -> None:
    stop, task = await start_worker(harness, worker_settings())
    await stop_worker(stop, task)

    assert task.exception() is None
    assert len(harness.scheduler.shutdown_calls) == 1
    assert not harness.scheduler.running
    assert harness.engine.disposed == 1
    assert harness.events.index("scheduler.shutdown") < harness.events.index("engine.dispose")


async def test_failed_sweep_keeps_the_worker_and_schedule_alive(harness: Harness) -> None:
    harness.sweep_error = RuntimeError("database unavailable")
    stop, task = await start_worker(harness, worker_settings(interval=30))
    try:
        assert not task.done()
        scheduler = harness.scheduler
        assert scheduler.running
        job = interval_job(scheduler)
        assert interval_seconds(job) == 30

        # APScheduler swallows job errors; the next scheduled run must still sweep.
        with contextlib.suppress(RuntimeError):
            await invoke(job)
        assert harness.events.count("sweep") == 2
        assert not task.done()
    finally:
        await stop_worker(stop, task)

    assert task.exception() is None
    assert harness.engine.disposed == 1


async def test_engine_is_disposed_when_the_scheduler_fails_to_start(harness: Harness) -> None:
    from app import worker

    harness.start_error = RuntimeError("scheduler failed to start")
    stop = asyncio.Event()

    # Whether the failure propagates is left to the implementation; the worker must not
    # hang waiting for a stop signal and must release its engine either way.
    with contextlib.suppress(RuntimeError):
        await asyncio.wait_for(worker.run_worker(worker_settings(), stop), TIMEOUT)

    assert "scheduler.start" in harness.events
    assert harness.engine.disposed == 1


async def test_worker_does_not_log_database_credentials(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    stop, task = await start_worker(harness, worker_settings())
    await stop_worker(stop, task)

    assert DB_PASSWORD not in caplog.text


# ---- shutdown while a sweep is still running ----------------------------------------


async def let_loop_run(turns: int = 50) -> None:
    """Yield to the event loop a fixed number of turns (no wall-clock wait)."""
    for _ in range(turns):
        await asyncio.sleep(0)


def last_index(events: list[str], name: str) -> int:
    return len(events) - 1 - events[::-1].index(name)


def assert_sweep_finished_before_dispose(harness: Harness) -> None:
    assert "sweep.cancelled" not in harness.events
    assert harness.engine.disposed == 1
    assert last_index(harness.events, "sweep.done") < harness.events.index("engine.dispose")
    assert all(not scheduler.running for scheduler in harness.schedulers)


async def hold_scheduled_sweep(harness: Harness) -> asyncio.Event:
    """Fire the interval job (as the scheduler would) and wait until it is mid-sweep."""
    hold = asyncio.Event()
    harness.hold = hold
    harness.swept.clear()
    harness.background.append(asyncio.ensure_future(invoke(interval_job(harness.scheduler))))
    await asyncio.wait_for(harness.swept.wait(), TIMEOUT)
    return hold


async def test_stop_lets_an_in_flight_scheduled_sweep_finish_before_dispose(
    harness: Harness,
) -> None:
    stop, task = await start_worker(harness, worker_settings())
    hold = await hold_scheduled_sweep(harness)

    stop.set()
    await let_loop_run()
    assert not task.done()
    assert harness.engine.disposed == 0
    # The held sweep is the only one that has started but not finished.
    assert harness.events.count("sweep.done") == harness.events.count("sweep") - 1

    hold.set()
    await asyncio.wait_for(task, TIMEOUT)

    assert task.exception() is None
    assert len(harness.scheduler.shutdown_calls) == 1
    assert_sweep_finished_before_dispose(harness)


async def test_cancel_lets_an_in_flight_scheduled_sweep_finish_before_dispose(
    harness: Harness,
) -> None:
    """Windows Ctrl+C cancels the main task instead of setting the stop event."""
    _stop, task = await start_worker(harness, worker_settings())
    hold = await hold_scheduled_sweep(harness)

    task.cancel()
    await let_loop_run()
    assert not task.done()
    assert harness.engine.disposed == 0

    hold.set()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, TIMEOUT)

    assert task.done()
    assert_sweep_finished_before_dispose(harness)


async def test_cancel_during_the_startup_sweep_waits_for_it_before_dispose(
    harness: Harness,
) -> None:
    from app import worker

    hold = asyncio.Event()
    harness.hold = hold
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run_worker(worker_settings(), stop))
    await asyncio.wait_for(harness.swept.wait(), TIMEOUT)

    task.cancel()
    await let_loop_run()
    assert not task.done()
    assert harness.engine.disposed == 0

    hold.set()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, TIMEOUT)

    assert task.done()
    assert_sweep_finished_before_dispose(harness)


# ---- retention purge: startup catch-up and daily schedule ---------------------------

COMPANY_OFFSET = timedelta(hours=7)
CRON_FIELDS = (
    "year",
    "month",
    "day",
    "week",
    "day_of_week",
    "hour",
    "minute",
    "second",
    "start_date",
    "end_date",
    "timezone",
    "jitter",
)


def is_cron(job: ScheduledJob) -> bool:
    return job.trigger == "cron" or type(job.trigger).__name__ == "CronTrigger"


def purge_job(scheduler: "FakeScheduler") -> ScheduledJob:
    jobs = [job for job in scheduler.jobs if is_cron(job)]
    assert len(jobs) == 1, scheduler.jobs
    return jobs[0]


def daily_fire_times(scheduler: "FakeScheduler", job: ScheduledJob) -> tuple[datetime, datetime]:
    """Two consecutive fire times of the purge trigger, as APScheduler would compute them."""
    from apscheduler.triggers.cron import CronTrigger

    if isinstance(job.trigger, str):
        zone = job.options.get("timezone") or scheduler.init_kwargs.get("timezone")
        # A server-local default would make the schedule depend on the host's time zone.
        assert zone is not None, "the daily purge needs an explicit company time zone"
        fields = {key: value for key, value in job.options.items() if key in CRON_FIELDS}
        fields["timezone"] = zone
        trigger = CronTrigger(**fields)
    else:
        trigger = job.trigger
    start = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    first = trigger.get_next_fire_time(None, start)
    second = trigger.get_next_fire_time(first, first + timedelta(seconds=1))
    return first, second


async def wait_for_startup_purge(harness: Harness) -> None:
    await asyncio.wait_for(harness.purged.wait(), TIMEOUT)
    await let_loop_run()


async def test_run_worker_purges_at_startup_and_schedules_a_daily_company_time_purge(
    harness: Harness,
) -> None:
    settings = worker_settings(interval=17)
    stop, task = await start_worker(harness, settings)
    try:
        # Catch-up scan at startup: postings that became due while the worker was down.
        await wait_for_startup_purge(harness)
        assert harness.events.count("purge") == 1
        assert not task.done()

        scheduler = harness.scheduler
        job = purge_job(scheduler)
        assert job.options.get("max_instances", 1) == 1
        assert job.options.get("coalesce") is True
        first, second = daily_fire_times(scheduler, job)
        assert first.utcoffset() == COMPANY_OFFSET
        assert second - first == timedelta(days=1)

        # The close-expired interval is unchanged and independent of the purge.
        assert interval_seconds(interval_job(scheduler)) == 17
        sweeps = harness.events.count("sweep")
        await invoke(job)
        assert harness.events.count("purge") == 2
        assert harness.events.count("sweep") == sweeps
        assert harness.purge_factories[1] is harness.purge_factories[0]

        await invoke(interval_job(scheduler))
        assert harness.events.count("sweep") == sweeps + 1
        assert harness.events.count("purge") == 2
    finally:
        await stop_worker(stop, task)

    assert harness.engine.disposed == 1


async def test_failed_purge_is_logged_safely_and_keeps_both_schedules(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness.purge_error = RuntimeError(f"could not connect to {DB_URL}")
    stop, task = await start_worker(harness, worker_settings(interval=30))
    try:
        await wait_for_startup_purge(harness)
        assert not task.done()

        scheduler = harness.scheduler
        with contextlib.suppress(RuntimeError):
            await invoke(purge_job(scheduler))
        assert harness.events.count("purge") == 2

        sweeps = harness.events.count("sweep")
        await invoke(interval_job(scheduler))
        assert harness.events.count("sweep") == sweeps + 1
        assert not task.done()
    finally:
        await stop_worker(stop, task)

    assert task.exception() is None
    assert harness.engine.disposed == 1
    # Reported by exception type only, never with the message (it may hold credentials).
    assert "RuntimeError" in caplog.text
    assert DB_PASSWORD not in caplog.text


async def test_stop_lets_an_in_flight_purge_finish_before_dispose(harness: Harness) -> None:
    stop, task = await start_worker(harness, worker_settings())
    await wait_for_startup_purge(harness)

    hold = asyncio.Event()
    harness.purge_hold = hold
    harness.purged.clear()
    harness.background.append(asyncio.ensure_future(invoke(purge_job(harness.scheduler))))
    await asyncio.wait_for(harness.purged.wait(), TIMEOUT)

    stop.set()
    await let_loop_run()
    assert not task.done()
    assert harness.engine.disposed == 0

    hold.set()
    await asyncio.wait_for(task, TIMEOUT)

    assert task.exception() is None
    assert "purge.cancelled" not in harness.events
    assert last_index(harness.events, "purge.done") < harness.events.index("engine.dispose")
    assert all(not scheduler.running for scheduler in harness.schedulers)
