"""Job posting endpoints. Every endpoint requires an employee account with the HR role."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from app.core.exceptions import Failure
from app.core.security import HrPrincipal
from app.db.session import SessionDep
from app.modules.departments import repository as department_repository
from app.modules.recruitment.models import JobPosting, JobStatus
from app.modules.recruitment.retention import deletion_due_date
from app.modules.recruitment.schemas import (
    INT64_MAX,
    CriteriaSaveIn,
    CriteriaSetOut,
    CriterionOut,
    DepartmentOut,
    InterviewerOut,
    JobCreateIn,
    JobDetailOut,
    JobPageOut,
    JobSort,
    JobSummaryOut,
    JobUpdateIn,
    SortOrder,
    VersionIn,
)
from app.modules.recruitment.service import (
    CriteriaService,
    CriteriaSetView,
    JobDetailView,
    JobPostingService,
)

# Luồng request: HrPrincipal kiểm quyền -> schema kiểm kiểu -> service xử lý
# nghiệp vụ/giao dịch -> các hàm mapping bên dưới trả JSON cho frontend.
router = APIRouter(tags=["recruitment"])

PAGE_SIZE_MAX = 100
# Largest page whose OFFSET, (page - 1) * page_size, still fits a BIGINT for any page size.
PAGE_MAX = INT64_MAX // PAGE_SIZE_MAX

JobId = Annotated[int, Path(ge=1, le=INT64_MAX)]


def _summary(job: JobPosting, department_name: str) -> JobSummaryOut:
    return JobSummaryOut(
        id=job.id,
        title=job.title,
        department_id=job.department_id,
        department_name=department_name,
        status=job.status,
        headcount=job.headcount,
        work_mode=job.work_mode,
        location=job.location,
        deadline=job.deadline,
        created_at=job.created_at,
        updated_at=job.updated_at,
        closed_at=job.closed_at,
        deletion_due_date=deletion_due_date(job.closed_at)
        if job.status is JobStatus.CLOSED
        else None,
        version=job.version,
    )


def _criteria_out(view: CriteriaSetView) -> CriteriaSetOut:
    item = view.criteria_set
    return CriteriaSetOut(
        id=item.id,
        version_no=item.version_no,
        auto_invite_threshold=item.auto_invite_threshold,
        created_by=item.created_by,
        created_at=item.created_at,
        criteria=[
            CriterionOut(
                id=criterion.id,
                name=criterion.name,
                description=criterion.description,
                is_mandatory=criterion.is_mandatory,
                min_score=criterion.min_score,
                weight=criterion.weight,
            )
            for criterion in view.criteria
        ],
    )


def _detail(view: JobDetailView) -> JobDetailOut:
    job = view.job
    return JobDetailOut(
        **_summary(job, view.department_name).model_dump(),
        description=job.description,
        requirements=job.requirements,
        benefits=job.benefits,
        created_by=job.created_by,
        current_criteria=_criteria_out(view.current_criteria) if view.current_criteria else None,
        interviewers=[InterviewerOut(id=uid, full_name=name) for uid, name in view.interviewers],
    )


async def _detail_response(service: JobPostingService, result: int | Failure) -> JobDetailOut:
    if isinstance(result, Failure):
        result.raise_error()
    # Sau commit, đọc lại dữ liệu thay vì trả object ORM có thể còn trạng thái cũ.
    service.session.expire_all()
    view = await service.get_detail(result)
    if isinstance(view, Failure):
        view.raise_error()
    return _detail(view)


@router.get("/jobs", response_model=JobPageOut)
async def list_jobs(
    principal: HrPrincipal,
    session: SessionDep,
    page: Annotated[int, Query(ge=1, le=PAGE_MAX)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: JobStatus | None = None,
    department_id: Annotated[int | None, Query(ge=1, le=INT64_MAX)] = None,
    sort: JobSort = JobSort.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> JobPageOut:
    result = await JobPostingService(session).list_jobs(
        page=page,
        page_size=page_size,
        q=q,
        status=status,
        department_id=department_id,
        sort=sort,
        order=order,
    )
    return JobPageOut(
        items=[_summary(job, name) for job, name in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post("/jobs", status_code=201, response_model=JobDetailOut)
async def create_job(
    payload: JobCreateIn, principal: HrPrincipal, session: SessionDep
) -> JobDetailOut:
    service = JobPostingService(session)
    result = await service.create_job(actor_id=principal.account_id, payload=payload)
    return await _detail_response(service, result)


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: JobId, principal: HrPrincipal, session: SessionDep) -> JobDetailOut:
    view = await JobPostingService(session).get_detail(job_id)
    if isinstance(view, Failure):
        view.raise_error()
    return _detail(view)


@router.put("/jobs/{job_id}", response_model=JobDetailOut)
async def update_job(
    job_id: JobId,
    payload: JobUpdateIn,
    principal: HrPrincipal,
    session: SessionDep,
) -> JobDetailOut:
    service = JobPostingService(session)
    result = await service.update_job(
        actor_id=principal.account_id,
        job_id=job_id,
        payload=payload,
        expected_version=payload.version,
    )
    return await _detail_response(service, result)


@router.post("/jobs/{job_id}/publish", response_model=JobDetailOut)
async def publish_job(
    job_id: JobId,
    payload: VersionIn,
    principal: HrPrincipal,
    session: SessionDep,
) -> JobDetailOut:
    service = JobPostingService(session)
    result = await service.publish_job(
        actor_id=principal.account_id, job_id=job_id, expected_version=payload.version
    )
    return await _detail_response(service, result)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_draft_job(
    job_id: JobId, payload: VersionIn, principal: HrPrincipal, session: SessionDep
) -> Response:
    # Xóa tay chỉ dành cho nháp; trả204 không có body để shared client xử lý đúng.
    result = await JobPostingService(session).delete_draft_job(
        actor_id=principal.account_id, job_id=job_id, expected_version=payload.version
    )
    if isinstance(result, Failure):
        result.raise_error()
    return Response(status_code=204)


@router.post("/jobs/{job_id}/close", response_model=JobDetailOut)
async def close_job(
    job_id: JobId, payload: VersionIn, principal: HrPrincipal, session: SessionDep
) -> JobDetailOut:
    service = JobPostingService(session)
    result = await service.close_job(
        actor_id=principal.account_id, job_id=job_id, expected_version=payload.version
    )
    return await _detail_response(service, result)


@router.put("/jobs/{job_id}/criteria", response_model=JobDetailOut)
async def save_criteria(
    job_id: JobId, payload: CriteriaSaveIn, principal: HrPrincipal, session: SessionDep
) -> JobDetailOut:
    result = await CriteriaService(session).save_criteria(
        actor_id=principal.account_id,
        job_id=job_id,
        criteria_in=payload,
        expected_version=payload.version,
    )
    if isinstance(result, Failure):
        result.raise_error()
    return await _detail_response(JobPostingService(session), job_id)


@router.get("/jobs/{job_id}/criteria/versions", response_model=list[CriteriaSetOut])
async def list_criteria_versions(
    job_id: JobId, principal: HrPrincipal, session: SessionDep
) -> list[CriteriaSetOut]:
    result = await CriteriaService(session).list_versions(job_id)
    if isinstance(result, Failure):
        result.raise_error()
    return [_criteria_out(view) for view in result]


@router.get("/interviewers", response_model=list[InterviewerOut])
async def list_interviewers(principal: HrPrincipal, session: SessionDep) -> list[InterviewerOut]:
    accounts = await CriteriaService(session).list_interviewer_options()
    return [InterviewerOut(id=account.id, full_name=account.full_name) for account in accounts]


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(principal: HrPrincipal, session: SessionDep) -> list[DepartmentOut]:
    departments = await department_repository.list_departments(session)
    return [
        DepartmentOut(id=item.id, name=item.name, is_active=item.is_active) for item in departments
    ]
