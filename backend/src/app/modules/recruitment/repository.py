"""Data access for job postings, criteria sets, criteria and interviewers.

Repositories only query and flush; services own transactions.
"""

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import Date, Select, cast, delete, func, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.departments.models import Department
from app.modules.recruitment.models import (
    CriteriaSet,
    Criterion,
    JobInterviewer,
    JobPosting,
    JobStatus,
)
from app.modules.recruitment.schemas import JobSort, SortOrder


# Các hàm ở đây truy vấn/flush dữ liệu; service giữ quyền commit hoặc rollback.
class JobPostingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: JobPosting) -> JobPosting:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(
        self, job_id: int, *, for_update: bool = False, skip_locked: bool = False
    ) -> JobPosting | None:
        # for_update dùng cho lệnh ghi; skip_locked chỉ dùng khi worker có thể
        # xử lý tin khác trước thay vì chờ một tin đang được khóa.
        statement = select(JobPosting).where(JobPosting.id == job_id)
        if for_update:
            statement = statement.with_for_update(skip_locked=skip_locked)
        return await self.session.scalar(statement)

    async def delete(self, job_id: int) -> None:
        # Chỉ xóa parent; FK/trigger trong migration0004 quản lý các dòng con.
        await self.session.execute(delete(JobPosting).where(JobPosting.id == job_id))

    async def purge_candidates(self, *, today: date, after_id: int, limit: int) -> list[int]:
        # PostgreSQL interval arithmetic matches the calendar anniversary, including
        # 29 February -> 28 February. Subtracting two years from today misses that case.
        closed_day = cast(func.timezone("Asia/Ho_Chi_Minh", JobPosting.closed_at), Date)
        due = closed_day + literal_column("INTERVAL '2 years'")
        statement = (
            select(JobPosting.id)
            .where(
                JobPosting.id > after_id,
                JobPosting.status == JobStatus.CLOSED,
                JobPosting.closed_at.is_not(None),
                due <= today,
            )
            .order_by(JobPosting.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    def _filtered(
        self,
        statement: Select,
        *,
        q: str | None,
        status: JobStatus | None,
        department_id: int | None,
    ) -> Select:
        if q:
            # Người dùng đang tìm chữ thường; % và _ không được tự thành wildcard.
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(JobPosting.title.ilike(f"%{escaped}%", escape="\\"))
        if status is not None:
            statement = statement.where(JobPosting.status == status)
        if department_id is not None:
            statement = statement.where(JobPosting.department_id == department_id)
        return statement

    async def search(
        self,
        *,
        q: str | None,
        status: JobStatus | None,
        department_id: int | None,
        sort: JobSort,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[JobPosting, str]], int]:
        # Dùng cùng bộ lọc cho tổng số và dữ liệu trang để phân trang không bị lệch.
        filters = {"q": q, "status": status, "department_id": department_id}
        total = await self.session.scalar(
            self._filtered(select(func.count()).select_from(JobPosting), **filters)
        )
        sort_column = JobPosting.deadline if sort is JobSort.DEADLINE else JobPosting.created_at
        ordering = sort_column.asc() if order is SortOrder.ASC else sort_column.desc()
        statement = self._filtered(
            select(JobPosting, Department.name).join(
                Department, Department.id == JobPosting.department_id
            ),
            **filters,
        ).order_by(ordering.nulls_last(), JobPosting.id.desc())
        rows = (await self.session.execute(statement.offset(offset).limit(limit))).all()
        return [(row[0], row[1]) for row in rows], int(total or 0)

    async def close_expired(self, *, today: date, now: datetime) -> list[int]:
        # UPDATE có điều kiện và RETURNING: chỉ audit những tin thực sự vừa đóng.
        # PostgreSQL kiểm tra lại điều kiện nếu phải chờ một transaction khác.
        result = await self.session.execute(
            update(JobPosting)
            .where(JobPosting.status == JobStatus.OPEN, JobPosting.deadline < today)
            .values(
                status=JobStatus.CLOSED,
                closed_at=now,
                updated_at=now,
                version=JobPosting.version + 1,
            )
            .returning(JobPosting.id)
        )
        return list(result.scalars().all())


class CriteriaSetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, criteria_set: CriteriaSet) -> CriteriaSet:
        self.session.add(criteria_set)
        await self.session.flush()
        return criteria_set

    async def get(self, criteria_set_id: int) -> CriteriaSet | None:
        return await self.session.get(CriteriaSet, criteria_set_id)

    async def next_version_no(self, job_id: int) -> int:
        # Service phải giữ khóa tin khi gọi để hai lệnh lưu không dùng cùng số mới.
        current = await self.session.scalar(
            select(func.max(CriteriaSet.version_no)).where(CriteriaSet.job_id == job_id)
        )
        return int(current or 0) + 1

    async def list_for_job(self, job_id: int) -> list[CriteriaSet]:
        statement = (
            select(CriteriaSet)
            .where(CriteriaSet.job_id == job_id)
            .order_by(CriteriaSet.version_no.desc())
        )
        return list((await self.session.scalars(statement)).all())


class CriteriaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_all(self, criteria: Sequence[Criterion]) -> None:
        self.session.add_all(criteria)
        await self.session.flush()

    async def list_for_sets(self, set_ids: Sequence[int]) -> dict[int, list[Criterion]]:
        # Trả map theo set ID để service ghép lịch sử mà không bị lỗi N+1 truy vấn.
        grouped: dict[int, list[Criterion]] = {set_id: [] for set_id in set_ids}
        if not set_ids:
            return grouped
        statement = (
            select(Criterion)
            .where(Criterion.criteria_set_id.in_(set_ids))
            .order_by(Criterion.criteria_set_id, Criterion.id)
        )
        for criterion in (await self.session.scalars(statement)).all():
            grouped[criterion.criteria_set_id].append(criterion)
        return grouped


class JobInterviewerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_ids(self, job_id: int) -> list[uuid.UUID]:
        statement = (
            select(JobInterviewer.user_id)
            .where(JobInterviewer.job_id == job_id)
            .order_by(JobInterviewer.user_id)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_with_names(self, job_id: int) -> list[tuple[uuid.UUID, str]]:
        statement = (
            select(Account.id, Account.full_name)
            .join(JobInterviewer, JobInterviewer.user_id == Account.id)
            .where(JobInterviewer.job_id == job_id)
            .order_by(Account.full_name, Account.id)
        )
        return [(row[0], row[1]) for row in (await self.session.execute(statement)).all()]

    async def replace(self, job_id: int, user_ids: Sequence[uuid.UUID]) -> None:
        # Thay phân công của tin hiện tại, không xóa tài khoản người phỏng vấn.
        await self.session.execute(delete(JobInterviewer).where(JobInterviewer.job_id == job_id))
        self.session.add_all(JobInterviewer(job_id=job_id, user_id=uid) for uid in user_ids)
        await self.session.flush()
