from sqlalchemy import func, or_, select

from app.modules.applications.models import Application, ApplicationScore, ApplicationStatus
from app.modules.audit.models import AuditEvent
from app.modules.candidates.models import Candidate, CvSubmission
from app.modules.recruitment.models import Criterion, JobPosting


async def joined_application(session, application_id, *, lock=False):
    query = (
        select(Application, Candidate, CvSubmission, JobPosting)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(CvSubmission, CvSubmission.id == Application.submission_id)
        .join(JobPosting, JobPosting.id == Application.job_id)
        .where(Application.id == application_id)
    )
    if lock:
        query = query.with_for_update(of=Application)
    return (await session.execute(query)).one_or_none()


def overdue_condition(now):
    return (
        (Application.status == ApplicationStatus.PENDING_HR_REVIEW)
        & Application.review_due_at.is_not(None)
        & (Application.review_due_at < now)
    )


async def count_by_status(session, now):
    # Một câu lệnh để mọi con số cùng một snapshot.
    rows = await session.execute(
        select(
            Application.status,
            func.count(),
            func.count().filter(overdue_condition(now)),
        ).group_by(Application.status)
    )
    return [(status, total, overdue) for status, total, overdue in rows]


async def list_applications(session, filters, now):
    query = (
        select(Application, Candidate, JobPosting)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(JobPosting, JobPosting.id == Application.job_id)
    )
    conditions = []
    for value, condition in (
        (filters.job_id, Application.job_id == filters.job_id),
        (filters.status, Application.status == filters.status),
    ):
        if value is not None:
            conditions.append(condition)
    if filters.submitted_from is not None:
        conditions.append(Application.submitted_at >= filters.submitted_from)
    if filters.submitted_to is not None:
        conditions.append(Application.submitted_at <= filters.submitted_to)
    if filters.score_min is not None:
        conditions.append(Application.ai_total_score >= filters.score_min)
    if filters.score_max is not None:
        conditions.append(Application.ai_total_score <= filters.score_max)
    if filters.overdue is not None:
        overdue = overdue_condition(now)
        conditions.append(overdue if filters.overdue else ~overdue)
    if filters.email_issue is not None:
        conditions.append(
            Application.email_issue.is_not(None)
            if filters.email_issue
            else Application.email_issue.is_(None)
        )
    if filters.q and filters.q.strip():
        term = filters.q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            or_(
                Candidate.full_name.ilike(f"%{term}%", escape="\\"),
                Candidate.email.ilike(f"%{term}%", escape="\\"),
            )
        )
    query = query.where(*conditions)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    column = getattr(Application, filters.sort)
    ordering = column.asc() if filters.order == "asc" else column.desc()
    rows = (
        await session.execute(
            query.order_by(ordering.nulls_last(), Application.id)
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
    ).all()
    return rows, total


async def score_explanations(session, application_id):
    return (
        await session.execute(
            select(ApplicationScore, Criterion)
            .join(Criterion, Criterion.id == ApplicationScore.criterion_id)
            .where(ApplicationScore.application_id == application_id)
            .order_by(Criterion.id)
        )
    ).all()


async def status_history(session, application_id):
    return (
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.target_type == "application",
                AuditEvent.target_id == str(application_id),
                AuditEvent.action.in_(["application.created", "application.status_changed"]),
            )
            .order_by(AuditEvent.timestamp, AuditEvent.id)
        )
    ).all()
