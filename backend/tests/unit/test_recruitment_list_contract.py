# Giữ hợp đồng dữ liệu danh sách/chi tiết mà frontend HR đang sử dụng.
"""The job list response carries work mode and location (no database needed)."""

import uuid
from datetime import UTC, date, datetime

from app.modules.recruitment.models import JobPosting, JobStatus
from app.modules.recruitment.router import _detail, _summary
from app.modules.recruitment.schemas import JobPageOut, JobSummaryOut
from app.modules.recruitment.service import JobDetailView


def make_job(**overrides) -> JobPosting:
    values = {
        "id": 7,
        "title": "Lập trình viên Backend",
        "department_id": 1,
        "status": JobStatus.OPEN,
        "headcount": 2,
        "work_mode": "Toàn thời gian – Hybrid",
        "location": "Hà Nội",
        "deadline": date(2026, 12, 31),
        "created_at": datetime(2026, 11, 17, 3, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 11, 17, 3, 0, tzinfo=UTC),
        "closed_at": None,
        "version": 3,
    }
    values.update(overrides)
    return JobPosting(**values)


def test_summary_includes_work_mode_and_location() -> None:
    summary = _summary(make_job(), "Phòng Kỹ thuật")

    assert summary.work_mode == "Toàn thời gian – Hybrid"
    assert summary.location == "Hà Nội"


def test_summary_keeps_missing_work_mode_and_location_as_null() -> None:
    payload = JobPageOut(
        items=[_summary(make_job(work_mode=None, location=None), "Phòng Kỹ thuật")],
        total=1,
        page=1,
        page_size=20,
    ).model_dump(mode="json")

    item = payload["items"][0]
    assert item["work_mode"] is None
    assert item["location"] is None


def test_detail_still_builds_with_work_mode_and_location() -> None:
    job = make_job(
        description="Phát triển API",
        requirements="Python",
        benefits=None,
        created_by=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    )
    detail = _detail(
        JobDetailView(
            job=job, department_name="Phòng Kỹ thuật", current_criteria=None, interviewers=[]
        )
    )

    assert (detail.work_mode, detail.location) == ("Toàn thời gian – Hybrid", "Hà Nội")
    assert detail.description == "Phát triển API"


def test_list_contract_only_adds_fields() -> None:
    assert {"work_mode", "location"} <= set(JobSummaryOut.model_fields)
    # Existing fields stay unchanged for current clients.
    assert {
        "id",
        "title",
        "department_id",
        "department_name",
        "status",
        "headcount",
        "deadline",
        "created_at",
        "updated_at",
        "closed_at",
        "version",
    } <= set(JobSummaryOut.model_fields)
