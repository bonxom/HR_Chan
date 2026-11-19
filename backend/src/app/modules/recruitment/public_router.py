"""Public job board for candidates (no account).

Only OPEN postings whose deadline is today or later in company time are visible, even
before the expiry sweep closes them. The DTOs are separate from the HR ones and carry no
criteria, thresholds, interviewers, creators, versions or embeddings. The HR job API
keeps its own protection.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core import clock
from app.core.exceptions import AppError
from app.db.session import SessionDep
from app.modules.departments.models import Department
from app.modules.recruitment.models import JobPosting, JobStatus
from app.modules.recruitment.retention import COMPANY_TZ
from app.modules.recruitment.schemas import INT64_MAX

router = APIRouter(prefix="/public", tags=["public jobs"])

PAGE_SIZE_MAX = 100
PAGE_MAX = INT64_MAX // PAGE_SIZE_MAX
JobId = Annotated[int, Path(ge=1, le=INT64_MAX)]


class PublicJobSummaryOut(BaseModel):
    id: int
    title: str
    department_id: int
    department_name: str
    headcount: int | None
    work_mode: str | None
    location: str | None
    deadline: date | None


class PublicJobDetailOut(PublicJobSummaryOut):
    description: str | None
    requirements: str | None
    benefits: str | None


class PublicJobPageOut(BaseModel):
    items: list[PublicJobSummaryOut]
    total: int
    page: int
    page_size: int


def _visible(now: datetime):
    today = now.astimezone(COMPANY_TZ).date()
    return (JobPosting.status == JobStatus.OPEN, JobPosting.deadline >= today)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _summary(job: JobPosting, department_name: str) -> PublicJobSummaryOut:
    return PublicJobSummaryOut(
        id=job.id,
        title=job.title,
        department_id=job.department_id,
        department_name=department_name,
        headcount=job.headcount,
        work_mode=job.work_mode,
        location=job.location,
        deadline=job.deadline,
    )


@router.get("/jobs", response_model=PublicJobPageOut)
async def list_public_jobs(
    session: SessionDep,
    page: Annotated[int, Query(ge=1, le=PAGE_MAX)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
    department_id: Annotated[int | None, Query(ge=1, le=INT64_MAX)] = None,
) -> PublicJobPageOut:
    conditions = list(_visible(clock.utcnow()))
    if q and q.strip():
        conditions.append(JobPosting.title.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))
    if department_id is not None:
        conditions.append(JobPosting.department_id == department_id)

    total = await session.scalar(select(func.count()).select_from(JobPosting).where(*conditions))
    rows = await session.execute(
        select(JobPosting, Department.name)
        .join(Department, Department.id == JobPosting.department_id)
        .where(*conditions)
        .order_by(JobPosting.deadline, JobPosting.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PublicJobPageOut(
        items=[_summary(job, name) for job, name in rows.all()],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/{job_id}", response_model=PublicJobDetailOut)
async def get_public_job(job_id: JobId, session: SessionDep) -> PublicJobDetailOut:
    row = (
        await session.execute(
            select(JobPosting, Department.name)
            .join(Department, Department.id == JobPosting.department_id)
            .where(JobPosting.id == job_id, *_visible(clock.utcnow()))
        )
    ).one_or_none()
    if row is None:
        raise AppError("Không tìm thấy tin tuyển dụng.", status_code=404, code="job_not_found")
    job, department_name = row
    return PublicJobDetailOut(
        **_summary(job, department_name).model_dump(),
        description=job.description,
        requirements=job.requirements,
        benefits=job.benefits,
    )
