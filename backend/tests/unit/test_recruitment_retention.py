# Dùng thời điểm cố định để kiểm mốc hai năm, đổi ngày UTC+7 và năm nhuận.
# Các ca này không cần chờ đồng hồ thật hoặc ghi database.
"""Retention: a CLOSED posting is due for deletion two calendar years after it closed.

The anniversary is counted on the company calendar (UTC+7), not on UTC dates and not
as a fixed 730 days. A 29 February closing day falls due on 28 February when the target
year is not a leap year. A posting without ``closed_at`` has no due date.

``app.modules.recruitment.retention`` is imported inside each test so a missing module
fails these tests individually instead of breaking collection of the whole suite.
"""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

COMPANY_TZ = timezone(timedelta(hours=7))


def due(closed_at: datetime | None) -> date | None:
    from app.modules.recruitment.retention import deletion_due_date

    return deletion_due_date(closed_at)


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


# ---- calendar rule ------------------------------------------------------------------


def test_missing_closed_at_has_no_due_date() -> None:
    assert due(None) is None


def test_due_date_is_two_calendar_years_after_the_company_closing_day() -> None:
    # 10:00 UTC is 17:00 in Vietnam on the same day.
    assert due(utc(2026, 11, 17, 10, 0)) == date(2028, 11, 17)


def test_due_date_is_not_a_fixed_730_days() -> None:
    # 730 days after 1 March 2026 is 29 February 2028 (2028 is a leap year).
    closed = datetime(2026, 3, 1, 9, 0, tzinfo=COMPANY_TZ)
    assert due(closed) == date(2028, 3, 1)
    assert due(closed) != (closed.date() + timedelta(days=730))


@pytest.mark.parametrize(
    ("closed_at", "expected"),
    [
        # 23:59:59 on 31/12/2026 in Vietnam: still the 2026 closing day.
        (utc(2026, 12, 31, 16, 59, 59), date(2028, 12, 31)),
        # 00:00 on 01/01/2027 in Vietnam, although the UTC date is still 31/12/2026.
        (utc(2026, 12, 31, 17, 0, 0), date(2029, 1, 1)),
        # Early-morning Vietnam time whose UTC date is the previous day.
        (utc(2026, 11, 16, 18, 30), date(2028, 11, 17)),
    ],
    ids=["last-second-of-day", "company-midnight", "utc-previous-day"],
)
def test_closing_day_is_taken_in_company_time(closed_at: datetime, expected: date) -> None:
    assert due(closed_at) == expected


def test_same_instant_in_any_offset_gives_the_same_due_date() -> None:
    instant = utc(2026, 12, 31, 17, 30)
    assert due(instant) == due(instant.astimezone(COMPANY_TZ)) == date(2029, 1, 1)
    assert due(instant.astimezone(timezone(timedelta(hours=-5)))) == date(2029, 1, 1)


@pytest.mark.parametrize(
    ("closed_at", "expected"),
    [
        # 29/02/2028 (Vietnam) -> 2030 is not a leap year -> 28/02/2030.
        (datetime(2028, 2, 29, 10, 0, tzinfo=COMPANY_TZ), date(2030, 2, 28)),
        # 17:30 UTC on 28/02/2028 is already 29/02/2028 in Vietnam.
        (utc(2028, 2, 28, 17, 30), date(2030, 2, 28)),
        # 29/02/2024 -> 28/02/2026.
        (utc(2024, 2, 29, 3, 0), date(2026, 2, 28)),
        # 28/02/2026 -> 28/02/2028, never moved to the leap day.
        (datetime(2026, 2, 28, 12, 0, tzinfo=COMPANY_TZ), date(2028, 2, 28)),
        # 01/03/2027 -> 01/03/2029.
        (datetime(2027, 3, 1, 0, 0, tzinfo=COMPANY_TZ), date(2029, 3, 1)),
    ],
    ids=["leap-day", "leap-day-by-offset", "leap-day-2024", "feb-28", "march-1"],
)
def test_leap_day_anniversary(closed_at: datetime, expected: date) -> None:
    assert due(closed_at) == expected


# ---- before / exactly on / after the due day ----------------------------------------


@pytest.mark.parametrize(
    ("now", "eligible"),
    [
        (datetime(2028, 11, 16, 23, 59, 59, tzinfo=COMPANY_TZ), False),
        (datetime(2028, 11, 17, 0, 0, 0, tzinfo=COMPANY_TZ), True),
        (datetime(2028, 11, 18, 9, 0, 0, tzinfo=COMPANY_TZ), True),
        # 16:59 UTC on 16/11/2028 is still 23:59 on 16/11 in Vietnam.
        (utc(2028, 11, 16, 16, 59), False),
        # 17:00 UTC on 16/11/2028 is midnight 17/11 in Vietnam.
        (utc(2028, 11, 16, 17, 0), True),
    ],
    ids=["day-before", "exact-day", "day-after", "utc-before-boundary", "utc-at-boundary"],
)
def test_due_date_against_company_today(now: datetime, eligible: bool) -> None:
    from app.modules.recruitment.service import company_today

    due_date = due(datetime(2026, 11, 17, 15, 0, tzinfo=COMPANY_TZ))
    assert due_date == date(2028, 11, 17)
    assert (due_date <= company_today(now)) is eligible


# ---- response mapping ---------------------------------------------------------------


def make_job(**overrides):
    from app.modules.recruitment.models import JobPosting, JobStatus

    values = {
        "id": 7,
        "title": "Lập trình viên Backend",
        "department_id": 1,
        "status": JobStatus.CLOSED,
        "headcount": 2,
        "work_mode": None,
        "location": None,
        "deadline": date(2026, 12, 31),
        "created_at": utc(2026, 1, 5, 3, 0),
        "updated_at": utc(2026, 12, 31, 17, 0),
        "closed_at": utc(2026, 12, 31, 17, 0),
        "version": 4,
    }
    values.update(overrides)
    return JobPosting(**values)


def test_closed_summary_and_detail_carry_the_backend_due_date() -> None:
    import uuid

    from app.modules.recruitment.router import _detail, _summary
    from app.modules.recruitment.service import JobDetailView

    job = make_job(
        description="Mô tả",
        requirements="Yêu cầu",
        benefits=None,
        created_by=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    )
    summary = _summary(job, "Phòng Kỹ thuật")
    assert summary.deletion_due_date == date(2029, 1, 1)
    assert summary.model_dump(mode="json")["deletion_due_date"] == "2029-01-01"

    detail = _detail(
        JobDetailView(
            job=job, department_name="Phòng Kỹ thuật", current_criteria=None, interviewers=[]
        )
    )
    assert detail.deletion_due_date == date(2029, 1, 1)


@pytest.mark.parametrize("status", ["DRAFT", "OPEN"])
def test_drafts_and_open_postings_have_no_due_date(status: str) -> None:
    from app.modules.recruitment.models import JobStatus
    from app.modules.recruitment.router import _summary

    summary = _summary(make_job(status=JobStatus(status), closed_at=None), "Phòng Kỹ thuật")
    assert summary.deletion_due_date is None
    assert summary.model_dump(mode="json")["deletion_due_date"] is None


def test_due_date_field_is_declared_nullable_on_the_contract() -> None:
    from app.modules.recruitment.schemas import JobDetailOut, JobSummaryOut

    for model in (JobSummaryOut, JobDetailOut):
        assert model.model_fields["deletion_due_date"].annotation == date | None
