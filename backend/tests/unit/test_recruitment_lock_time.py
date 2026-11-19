# Giả lập việc chờ khóa qua nửa đêm để kiểm thời gian được đọc sau khi có khóa.
"""The expiry/deadline day must be taken after the job row lock is acquired.

A request that starts just before company midnight and waits for the row lock until
after midnight (version unchanged) must be judged against the new day: an OPEN posting
whose deadline was "today" has expired by then and must not be edited, extended,
given new criteria, and a DRAFT with that deadline must not be published.

These tests drive the services directly with a real ``JobPosting`` object, a fake
session, a row-lock fake that blocks until released, and a controlled
``clock.utcnow``. No database, JWT or wall-clock waits are involved.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core import clock
from app.core.exceptions import Failure
from app.modules.recruitment import service as recruitment_service
from app.modules.recruitment.models import JobPosting, JobStatus
from app.modules.recruitment.schemas import CriteriaSaveIn, JobUpdateIn
from app.modules.recruitment.service import CriteriaService, JobPostingService

TIMEOUT = 5.0
COMPANY_TZ = timezone(timedelta(hours=7))
DEADLINE = date(2026, 11, 17)
BEFORE_MIDNIGHT = datetime(2026, 11, 17, 23, 59, tzinfo=COMPANY_TZ).astimezone(UTC)
AFTER_MIDNIGHT = datetime(2026, 11, 18, 0, 1, tzinfo=COMPANY_TZ).astimezone(UTC)
JOB_ID = 7
CRITERIA_SET_ID = 11
VERSION = 3
ACTOR_ID = uuid.UUID("00000000-0000-4000-8000-0000000000aa")

JOB_FIELDS = {
    "title": "Lập trình viên Backend",
    "department_id": 1,
    "description": "Phát triển API",
    "requirements": "Python, PostgreSQL",
    "benefits": "Lương tháng 13",
    "headcount": 2,
    "work_mode": "Toàn thời gian",
    "location": "Hà Nội",
    "deadline": DEADLINE,
}


class ControlledClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeSession:
    """Records transaction calls; any other database access would raise."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def rollback(self) -> None:
        self.calls.append("rollback")

    async def commit(self) -> None:
        self.calls.append("commit")

    async def flush(self) -> None:
        self.calls.append("flush")


class RowLock:
    """Stands in for ``JobPostingRepository.get``: blocks until ``release`` is set."""

    def __init__(self, job: JobPosting) -> None:
        self.job = job
        self.requested = asyncio.Event()
        self.release = asyncio.Event()
        self.for_update: list[bool] = []

    async def get(self, job_id: int, *, for_update: bool = False) -> JobPosting:
        assert job_id == self.job.id
        self.for_update.append(for_update)
        self.requested.set()
        await asyncio.wait_for(self.release.wait(), TIMEOUT)
        return self.job


def make_job(status: JobStatus) -> JobPosting:
    return JobPosting(
        id=JOB_ID,
        **JOB_FIELDS,
        status=status,
        current_criteria_set_id=CRITERIA_SET_ID,
        created_by=ACTOR_ID,
        created_at=BEFORE_MIDNIGHT - timedelta(days=10),
        updated_at=BEFORE_MIDNIGHT - timedelta(days=10),
        version=VERSION,
    )


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> ControlledClock:
    controlled = ControlledClock(BEFORE_MIDNIGHT)
    monkeypatch.setattr(clock, "utcnow", controlled)
    return controlled


@pytest.fixture
def audit_events(monkeypatch: pytest.MonkeyPatch) -> list:
    events: list = []

    async def record_event(session, event) -> None:
        events.append(event)

    monkeypatch.setattr(recruitment_service, "record_event", record_event)
    return events


async def run_while_locked(operation, lock: RowLock, fake_clock: ControlledClock, *, cross: bool):
    """Start ``operation``, wait until it requests the row lock, optionally move the
    clock past company midnight, then grant the lock and return the result."""
    task = asyncio.ensure_future(operation)
    try:
        await asyncio.wait_for(lock.requested.wait(), TIMEOUT)
        if cross:
            fake_clock.now = AFTER_MIDNIGHT
        lock.release.set()
        return await asyncio.wait_for(task, TIMEOUT)
    finally:
        lock.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def assert_rule_violation(result: object) -> None:
    assert isinstance(result, Failure), result
    assert result.status_code == 422
    assert result.code == "job_rule_violation"


def job_service(session: FakeSession, lock: RowLock, monkeypatch) -> JobPostingService:
    service = JobPostingService(session)
    monkeypatch.setattr(service.jobs, "get", lock.get)
    return service


# ---- update_job -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Sửa sau nửa đêm"},
        {"deadline": DEADLINE + timedelta(days=30)},
    ],
    ids=["edit", "extend-deadline"],
)
async def test_update_waiting_for_lock_past_midnight_is_rejected(
    fake_clock, audit_events, monkeypatch, changes
) -> None:
    job = make_job(JobStatus.OPEN)
    session = FakeSession()
    lock = RowLock(job)
    service = job_service(session, lock, monkeypatch)
    payload = JobUpdateIn(**{**JOB_FIELDS, **changes}, version=VERSION)

    result = await run_while_locked(
        service.update_job(
            actor_id=ACTOR_ID, job_id=JOB_ID, payload=payload, expected_version=VERSION
        ),
        lock,
        fake_clock,
        cross=True,
    )

    assert_rule_violation(result)
    assert lock.for_update == [True]
    assert job.version == VERSION
    assert job.title == JOB_FIELDS["title"]
    assert job.deadline == DEADLINE
    assert job.status is JobStatus.OPEN
    assert audit_events == []
    assert "commit" not in session.calls
    assert "rollback" in session.calls


async def test_update_holding_lock_before_midnight_still_succeeds(
    fake_clock, audit_events, monkeypatch
) -> None:
    job = make_job(JobStatus.OPEN)
    session = FakeSession()
    lock = RowLock(job)
    service = job_service(session, lock, monkeypatch)
    payload = JobUpdateIn(**{**JOB_FIELDS, "title": "Sửa trong hạn"}, version=VERSION)

    result = await run_while_locked(
        service.update_job(
            actor_id=ACTOR_ID, job_id=JOB_ID, payload=payload, expected_version=VERSION
        ),
        lock,
        fake_clock,
        cross=False,
    )

    assert result == JOB_ID
    assert job.title == "Sửa trong hạn"
    assert job.version == VERSION + 1
    assert [event.action.value for event in audit_events] == ["job.updated"]
    assert session.calls[-1] == "commit"


async def test_update_with_explicit_now_ignores_the_clock(
    fake_clock, audit_events, monkeypatch
) -> None:
    """An explicit ``now`` keeps deterministic semantics regardless of the clock."""
    job = make_job(JobStatus.OPEN)
    session = FakeSession()
    lock = RowLock(job)
    service = job_service(session, lock, monkeypatch)
    payload = JobUpdateIn(**{**JOB_FIELDS, "title": "Sửa với thời điểm cố định"}, version=VERSION)

    result = await run_while_locked(
        service.update_job(
            actor_id=ACTOR_ID,
            job_id=JOB_ID,
            payload=payload,
            expected_version=VERSION,
            now=BEFORE_MIDNIGHT,
        ),
        lock,
        fake_clock,
        cross=True,
    )

    assert result == JOB_ID
    assert job.version == VERSION + 1
    assert job.updated_at == BEFORE_MIDNIGHT


# ---- save_criteria --------------------------------------------------------------------


def criteria_service(session: FakeSession, lock: RowLock, monkeypatch, mutations: list):
    service = CriteriaService(session)
    monkeypatch.setattr(service.jobs, "get", lock.get)

    async def check_criteria(criteria_in) -> None:
        mutations.append("check_criteria")
        return None

    async def previous_set(criteria_set_id):
        return None

    async def previous_interviewers(job_id) -> list:
        return []

    async def insert_version(job, criteria_in, threshold, actor_id):
        mutations.append("insert_version")
        job.current_criteria_set_id = CRITERIA_SET_ID + 1
        return SimpleNamespace(version_no=2)

    monkeypatch.setattr(service, "check_criteria", check_criteria)
    monkeypatch.setattr(service.sets, "get", previous_set)
    monkeypatch.setattr(service.interviewers, "list_ids", previous_interviewers)
    monkeypatch.setattr(service, "insert_version", insert_version)
    return service


def criteria_payload() -> CriteriaSaveIn:
    return CriteriaSaveIn(
        criteria=[{"name": "Kỹ năng", "description": "Mô tả", "weight": 100}],
        interviewer_ids=[uuid.UUID("00000000-0000-4000-8000-0000000000bb")],
        auto_invite_threshold=Decimal("80"),
        version=VERSION,
    )


async def test_save_criteria_waiting_for_lock_past_midnight_is_rejected(
    fake_clock, audit_events, monkeypatch
) -> None:
    job = make_job(JobStatus.OPEN)
    session = FakeSession()
    lock = RowLock(job)
    mutations: list[str] = []
    service = criteria_service(session, lock, monkeypatch, mutations)

    result = await run_while_locked(
        service.save_criteria(
            actor_id=ACTOR_ID,
            job_id=JOB_ID,
            criteria_in=criteria_payload(),
            expected_version=VERSION,
        ),
        lock,
        fake_clock,
        cross=True,
    )

    assert_rule_violation(result)
    assert lock.for_update == [True]
    assert "insert_version" not in mutations
    assert job.current_criteria_set_id == CRITERIA_SET_ID
    assert job.version == VERSION
    assert audit_events == []
    assert "commit" not in session.calls
    assert "rollback" in session.calls


async def test_save_criteria_holding_lock_before_midnight_still_succeeds(
    fake_clock, audit_events, monkeypatch
) -> None:
    job = make_job(JobStatus.OPEN)
    session = FakeSession()
    lock = RowLock(job)
    mutations: list[str] = []
    service = criteria_service(session, lock, monkeypatch, mutations)

    result = await run_while_locked(
        service.save_criteria(
            actor_id=ACTOR_ID,
            job_id=JOB_ID,
            criteria_in=criteria_payload(),
            expected_version=VERSION,
        ),
        lock,
        fake_clock,
        cross=False,
    )

    assert result == 2
    assert mutations == ["check_criteria", "insert_version"]
    assert job.version == VERSION + 1
    assert [event.action.value for event in audit_events] == ["job.criteria_saved"]
    assert session.calls[-1] == "commit"


# ---- publish_job ----------------------------------------------------------------------


async def test_publish_waiting_for_lock_past_midnight_is_rejected(
    fake_clock, audit_events, monkeypatch
) -> None:
    job = make_job(JobStatus.DRAFT)
    session = FakeSession()
    lock = RowLock(job)
    service = job_service(session, lock, monkeypatch)

    result = await run_while_locked(
        service.publish_job(actor_id=ACTOR_ID, job_id=JOB_ID, expected_version=VERSION),
        lock,
        fake_clock,
        cross=True,
    )

    assert_rule_violation(result)
    assert lock.for_update == [True]
    assert job.status is JobStatus.DRAFT
    assert job.version == VERSION
    assert audit_events == []
    assert "commit" not in session.calls
    assert "rollback" in session.calls


async def test_publish_holding_lock_before_midnight_still_succeeds(
    fake_clock, audit_events, monkeypatch
) -> None:
    job = make_job(JobStatus.DRAFT)
    session = FakeSession()
    lock = RowLock(job)
    service = job_service(session, lock, monkeypatch)

    result = await run_while_locked(
        service.publish_job(actor_id=ACTOR_ID, job_id=JOB_ID, expected_version=VERSION),
        lock,
        fake_clock,
        cross=False,
    )

    assert result == JOB_ID
    assert job.status is JobStatus.OPEN
    assert job.version == VERSION + 1
    assert [event.action.value for event in audit_events] == ["job.published"]
    assert session.calls[-1] == "commit"
