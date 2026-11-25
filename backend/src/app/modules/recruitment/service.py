"""Job posting and scoring-criteria services (JobPostingControl, CriteriaControl).

Each public write method runs in one transaction it owns. Expected rule violations
are returned as ``Failure`` values; routers turn them into HTTP errors.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.exceptions import Failure, failure
from app.modules.accounts import repository as account_repository
from app.modules.accounts.models import Account
from app.modules.accounts.rules import EmployeeRole
from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event
from app.modules.departments import repository as department_repository
from app.modules.recruitment.models import CriteriaSet, Criterion, JobPosting, JobStatus
from app.modules.recruitment.repository import (
    CriteriaRepository,
    CriteriaSetRepository,
    JobInterviewerRepository,
    JobPostingRepository,
)
from app.modules.recruitment.retention import deletion_due_date
from app.modules.recruitment.schemas import (
    TOTAL_WEIGHT,
    CriteriaIn,
    JobCreateIn,
    JobFieldsIn,
    JobSort,
    SortOrder,
)
from app.modules.settings import repository as settings_repository

logger = logging.getLogger(__name__)

# Vietnam has no daylight saving time; a fixed offset avoids a tzdata dependency.
COMPANY_TZ = timezone(timedelta(hours=7))
AUDIT_TARGET = "job_posting"

JOB_FIELDS = (
    "title",
    "department_id",
    "description",
    "requirements",
    "benefits",
    "headcount",
    "work_mode",
    "location",
    "deadline",
)
REQUIRED_TO_OPEN = {
    "description": "mô tả công việc",
    "requirements": "yêu cầu ứng viên",
    "headcount": "số lượng cần tuyển",
    "deadline": "hạn nộp hồ sơ",
}

MSG_NOT_FOUND = "Không tìm thấy tin tuyển dụng"
MSG_VERSION_CONFLICT = (
    "Tin tuyển dụng đã được người khác thay đổi. Hãy tải lại tin rồi thực hiện lại."
)
MSG_CLOSED_READ_ONLY = "Tin đã đóng không được sửa. Muốn tuyển tiếp, hãy tạo tin mới."
MSG_CLOSED_NO_REOPEN = "Tin đã đóng không thể mở lại. Muốn tuyển tiếp, hãy tạo tin mới."
MSG_CLOSED_NO_CRITERIA = "Tin đã đóng không được thay đổi bộ tiêu chí."
MSG_DEADLINE_PAST = "Hạn nộp hồ sơ không được trước ngày hôm nay"
MSG_EXPIRED_READ_ONLY = (
    "Tin đã quá hạn nộp hồ sơ nên không được sửa hoặc thay đổi bộ tiêu chí."
    " Muốn tuyển tiếp, hãy tạo tin mới."
)


def company_today(now: datetime | None = None) -> date:
    return (now or clock.utcnow()).astimezone(COMPANY_TZ).date()


def is_expired(job: JobPosting, today: date) -> bool:
    """An OPEN posting whose deadline day has passed, whether or not the worker closed it."""
    return job.status is JobStatus.OPEN and job.deadline is not None and job.deadline < today


def _rule(message: str) -> Failure:
    return failure(422, "job_rule_violation", message)


def _not_found() -> Failure:
    return failure(404, "job_not_found", MSG_NOT_FOUND)


def _conflict() -> Failure:
    return failure(409, "version_conflict", MSG_VERSION_CONFLICT)


def _jsonable(value: Any) -> Any:
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _constraint_name(exc: IntegrityError) -> str | None:
    origin = getattr(exc.orig, "__cause__", None) or exc.orig
    return getattr(origin, "constraint_name", None)


def _integrity_failure(exc: IntegrityError) -> Failure:
    """Translate a database constraint violation into a safe, meaningful error."""
    name = _constraint_name(exc)
    if name == "criteria_sets_job_id_version_no_key":
        return _conflict()
    if name == "job_open_complete":
        return _rule("Tin Đang mở phải có đủ mô tả, yêu cầu, số lượng, hạn nộp và bộ tiêu chí")
    if name == "criteria_criteria_set_id_name_key":
        return _rule("Tên tiêu chí không được trùng nhau trong cùng một bộ tiêu chí")
    if name and name.endswith("_fkey"):
        return _rule("Dữ liệu tham chiếu không tồn tại (phòng ban hoặc người phỏng vấn)")
    message = str(getattr(exc.orig, "__cause__", exc.orig) or "")
    if "sum to" in message:
        return _rule("Tổng trọng số các tiêu chí phải bằng 100")
    logger.warning("Job posting write violated constraint %s", name or "unknown")
    return _rule("Dữ liệu tin tuyển dụng vi phạm ràng buộc dữ liệu")


@dataclass(frozen=True)
class CriteriaSetView:
    criteria_set: CriteriaSet
    criteria: list[Criterion]


@dataclass(frozen=True)
class JobDetailView:
    job: JobPosting
    department_name: str
    current_criteria: CriteriaSetView | None
    interviewers: list[tuple[uuid.UUID, str]]


@dataclass(frozen=True)
class JobPage:
    items: list[tuple[JobPosting, str]]
    total: int


# Bộ tiêu chí được lưu theo phiên bản: sửa tiêu chí là thêm bản mới, không ghi đè
# lịch sử. Các lệnh ghi bên dưới cùng quản lý dữ liệu nghiệp vụ và audit.
class CriteriaService:
    """CriteriaControl: validates and versions a posting's scoring criteria."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.jobs = JobPostingRepository(session)
        self.sets = CriteriaSetRepository(session)
        self.criteria = CriteriaRepository(session)
        self.interviewers = JobInterviewerRepository(session)

    async def list_interviewer_options(self) -> list[Account]:
        return await account_repository.find_by_role(self.session, EmployeeRole.INTERVIEWER.value)

    async def check_criteria(self, criteria_in: CriteriaIn) -> Failure | None:
        """Rules for a valid criteria set, then the interviewers' roles."""
        if not criteria_in.criteria:
            return _rule("Bộ tiêu chí phải có ít nhất 1 tiêu chí")
        names = [item.name.casefold() for item in criteria_in.criteria]
        for item in criteria_in.criteria:
            if message := item.floor_error():
                return _rule(message)
        if len(names) != len(set(names)):
            return _rule("Tên tiêu chí không được trùng nhau trong cùng một bộ tiêu chí")
        # Decimal tránh sai số cộng số thực khi kiểm tra tổng trọng số đúng bằng 100.
        total = sum((item.weight for item in criteria_in.criteria), Decimal("0"))
        if total != TOTAL_WEIGHT:
            shown = format(total.normalize(), "f")
            return _rule(f"Tổng trọng số các tiêu chí phải bằng 100 (hiện là {shown})")
        if not criteria_in.interviewer_ids:
            return _rule("Bộ tiêu chí phải có ít nhất 1 người phỏng vấn")
        if len(criteria_in.interviewer_ids) != len(set(criteria_in.interviewer_ids)):
            return _rule("Danh sách người phỏng vấn bị trùng")
        return await self.check_interviewers(criteria_in.interviewer_ids)

    async def check_interviewers(self, interviewer_ids: list[uuid.UUID]) -> Failure | None:
        """Every interviewer must be an employee account holding the Interviewer role.

        Account status is intentionally not checked: interviewers are assumed available.
        """
        options = {account.id for account in await self.list_interviewer_options()}
        missing = [str(uid) for uid in interviewer_ids if uid not in options]
        if missing:
            return _rule(
                "Người phỏng vấn không hợp lệ (không tồn tại hoặc không có vai trò Người phỏng"
                f" vấn): {', '.join(missing)}"
            )
        return None

    # Giá trị null từ frontend nghĩa là lấy cấu hình hệ thống, không phải ngưỡng 0.
    # Thiếu cấu hình thì báo lỗi, tránh tự chọn một ngưỡng khác với nghiệp vụ.
    async def resolve_threshold(self, criteria_in: CriteriaIn) -> Decimal | Failure:
        if criteria_in.auto_invite_threshold is not None:
            return criteria_in.auto_invite_threshold
        default = await settings_repository.get_numeric(
            self.session, settings_repository.AUTO_INVITE_THRESHOLD
        )
        if default is None:
            return failure(
                500,
                "configuration_error",
                "Chưa cấu hình ngưỡng tự động mời phỏng vấn mặc định trong cấu hình hệ thống",
            )
        return default

    # Chỉ flush để lấy ID; hàm gọi sẽ commit cả phiên bản, phân công và audit cùng lúc.
    async def insert_version(
        self, job: JobPosting, criteria_in: CriteriaIn, threshold: Decimal, actor_id: uuid.UUID
    ) -> CriteriaSet:
        """Insert a new immutable criteria-set version and make it current (no commit)."""
        criteria_set = await self.sets.add(
            CriteriaSet(
                job_id=job.id,
                version_no=await self.sets.next_version_no(job.id),
                auto_invite_threshold=threshold,
                created_by=actor_id,
            )
        )
        await self.criteria.add_all(
            [
                Criterion(
                    criteria_set_id=criteria_set.id,
                    name=item.name,
                    description=item.description,
                    is_mandatory=item.is_mandatory,
                    min_score=item.min_score,
                    weight=item.weight,
                )
                for item in criteria_in.criteria
            ]
        )
        await self.interviewers.replace(job.id, criteria_in.interviewer_ids)
        job.current_criteria_set_id = criteria_set.id
        return criteria_set

    # Khóa tin trước khi đọc version để hai người không tạo cùng một số phiên bản.
    # Tin hết hạn cũng bị chặn ngay, kể cả worker chưa kịp chuyển sang CLOSED.
    async def save_criteria(
        self,
        *,
        actor_id: uuid.UUID,
        job_id: int,
        criteria_in: CriteriaIn,
        expected_version: int,
        now: datetime | None = None,
    ) -> int | Failure:
        job = await self.jobs.get(job_id, for_update=True)
        # Read the clock only once the row lock is held: waiting may cross midnight.
        moment = now or clock.utcnow()
        if job is None:
            await self.session.rollback()
            return _not_found()
        if job.version != expected_version:
            await self.session.rollback()
            return _conflict()
        if job.status is JobStatus.CLOSED:
            await self.session.rollback()
            return _rule(MSG_CLOSED_NO_CRITERIA)
        # Checked under the row lock so a sweep that has not run yet cannot be bypassed.
        if is_expired(job, company_today(moment)):
            await self.session.rollback()
            return _rule(MSG_EXPIRED_READ_ONLY)
        problem = await self.check_criteria(criteria_in)
        if problem is not None:
            await self.session.rollback()
            return problem
        threshold = await self.resolve_threshold(criteria_in)
        if isinstance(threshold, Failure):
            await self.session.rollback()
            return threshold

        previous_set = (
            await self.sets.get(job.current_criteria_set_id)
            if job.current_criteria_set_id is not None
            else None
        )
        previous_interviewers = await self.interviewers.list_ids(job.id)
        try:
            criteria_set = await self.insert_version(job, criteria_in, threshold, actor_id)
            job.version += 1
            job.updated_at = moment
            changes: dict[str, Any] = {}
            new_interviewers = sorted(str(uid) for uid in criteria_in.interviewer_ids)
            old_interviewers = sorted(str(uid) for uid in previous_interviewers)
            if new_interviewers != old_interviewers:
                changes["interviewer_ids"] = {"before": old_interviewers, "after": new_interviewers}
            old_threshold = previous_set.auto_invite_threshold if previous_set else None
            if old_threshold != threshold:
                changes["auto_invite_threshold"] = {
                    "before": _jsonable(old_threshold),
                    "after": _jsonable(threshold),
                }
            await record_event(
                self.session,
                AuditEventInput(
                    action=AuditAction.JOB_CRITERIA_SAVED,
                    outcome=AuditOutcome.SUCCESS,
                    actor_id=actor_id,
                    target_type=AUDIT_TARGET,
                    target_id=str(job.id),
                    metadata={"version_no": criteria_set.version_no, "changes": changes},
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            return _integrity_failure(exc)
        return criteria_set.version_no

    # Gom tiêu chí của nhiều phiên bản trong một lần đọc, tránh truy vấn từng hàng.
    async def list_versions(self, job_id: int) -> list[CriteriaSetView] | Failure:
        if await self.jobs.get(job_id) is None:
            return _not_found()
        sets = await self.sets.list_for_job(job_id)
        grouped = await self.criteria.list_for_sets([item.id for item in sets])
        return [CriteriaSetView(item, grouped[item.id]) for item in sets]

    async def get_view(self, criteria_set_id: int | None) -> CriteriaSetView | None:
        if criteria_set_id is None:
            return None
        criteria_set = await self.sets.get(criteria_set_id)
        if criteria_set is None:
            return None
        grouped = await self.criteria.list_for_sets([criteria_set.id])
        return CriteriaSetView(criteria_set, grouped[criteria_set.id])


# Router chuyển request vào đây; service kiểm tra nghiệp vụ và quyết định commit/
# rollback. Repository chỉ làm việc với database, không tự kết thúc giao dịch.
class JobPostingService:
    """JobPostingControl: create, update, publish, close and list job postings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.jobs = JobPostingRepository(session)
        self.criteria_service = CriteriaService(session)

    # ---- queries -------------------------------------------------------------------

    async def list_jobs(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        status: JobStatus | None = None,
        department_id: int | None = None,
        sort: JobSort = JobSort.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
    ) -> JobPage:
        items, total = await self.jobs.search(
            q=q.strip() if q else None,
            status=status,
            department_id=department_id,
            sort=sort,
            order=order,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return JobPage(items=items, total=total)

    async def get_detail(self, job_id: int) -> JobDetailView | Failure:
        job = await self.jobs.get(job_id)
        if job is None:
            return _not_found()
        department = await department_repository.get_by_id(self.session, job.department_id)
        return JobDetailView(
            job=job,
            department_name=department.name if department else "",
            current_criteria=await self.criteria_service.get_view(job.current_criteria_set_id),
            interviewers=await self.criteria_service.interviewers.list_with_names(job.id),
        )

    # ---- rules ---------------------------------------------------------------------

    @staticmethod
    def _open_problem(job: JobPosting, today: date, *, check_deadline: bool) -> Failure | None:
        # Các trường này có thể thiếu ở DRAFT nhưng phải đủ trước khi thành OPEN.
        missing = [
            label for field, label in REQUIRED_TO_OPEN.items() if getattr(job, field) is None
        ]
        if missing:
            return _rule("Chưa đủ thông tin để đăng tin, còn thiếu: " + ", ".join(missing))
        if job.current_criteria_set_id is None:
            return _rule("Tin phải có bộ tiêu chí chấm điểm hợp lệ trước khi đăng")
        if check_deadline and job.deadline is not None and job.deadline < today:
            return _rule(MSG_DEADLINE_PAST)
        return None

    async def _check_department(self, department_id: int) -> Failure | None:
        if await department_repository.get_by_id(self.session, department_id) is None:
            return _rule("Phòng ban không tồn tại")
        return None

    # ---- commands ------------------------------------------------------------------

    # Nháp được phép chưa có criteria. Nếu đã gửi criteria, vẫn phải hợp lệ đầy đủ.
    # Tạo rồi đăng ngay cũng đi qua DRAFT trong cùng giao dịch; lỗi sẽ rollback hết.
    async def create_job(
        self, *, actor_id: uuid.UUID, payload: JobCreateIn, now: datetime | None = None
    ) -> int | Failure:
        moment = now or clock.utcnow()
        problem = await self._check_department(payload.department_id)
        if problem is None and payload.publish and payload.criteria is None:
            problem = _rule("Tin phải có bộ tiêu chí chấm điểm hợp lệ trước khi đăng")
        if problem is None and payload.criteria is not None:
            problem = await self.criteria_service.check_criteria(payload.criteria)
        threshold: Decimal | None = None
        if problem is None and payload.criteria is not None:
            resolved = await self.criteria_service.resolve_threshold(payload.criteria)
            if isinstance(resolved, Failure):
                problem = resolved
            else:
                threshold = resolved
        if problem is not None:
            await self.session.rollback()
            return problem

        job = JobPosting(
            **payload.model_dump(include=set(JOB_FIELDS)),
            status=JobStatus.DRAFT,
            created_by=actor_id,
            created_at=moment,
            updated_at=moment,
            version=1,
        )
        try:
            await self.jobs.add(job)
            version_no: int | None = None
            if payload.criteria is not None and threshold is not None:
                criteria_set = await self.criteria_service.insert_version(
                    job, payload.criteria, threshold, actor_id
                )
                version_no = criteria_set.version_no
            if payload.publish:
                problem = self._open_problem(job, company_today(moment), check_deadline=True)
                if problem is not None:
                    await self.session.rollback()
                    return problem
                job.status = JobStatus.OPEN
            await self.session.flush()
            metadata: dict[str, Any] = {"status": job.status.value}
            if version_no is not None:
                metadata["version_no"] = version_no
            await record_event(
                self.session,
                AuditEventInput(
                    action=AuditAction.JOB_CREATED,
                    outcome=AuditOutcome.SUCCESS,
                    actor_id=actor_id,
                    target_type=AUDIT_TARGET,
                    target_id=str(job.id),
                    metadata=metadata,
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            return _integrity_failure(exc)
        return job.id

    # expected_version là version người dùng đã đọc, không phải version lấy lại
    # lúc bấm lưu; khác nhau thì trả 409 để tránh ghi đè thay đổi của người khác.
    async def update_job(
        self,
        *,
        actor_id: uuid.UUID,
        job_id: int,
        payload: JobFieldsIn,
        expected_version: int,
        now: datetime | None = None,
    ) -> int | Failure:
        job = await self.jobs.get(job_id, for_update=True)
        # Read the clock only once the row lock is held: waiting may cross midnight.
        moment = now or clock.utcnow()
        if job is None:
            await self.session.rollback()
            return _not_found()
        if job.version != expected_version:
            await self.session.rollback()
            return _conflict()
        if job.status is JobStatus.CLOSED:
            await self.session.rollback()
            return _rule(MSG_CLOSED_READ_ONLY)
        # Checked under the row lock, before any field changes or the no-op return.
        if is_expired(job, company_today(moment)):
            await self.session.rollback()
            return _rule(MSG_EXPIRED_READ_ONLY)

        incoming = payload.model_dump(include=set(JOB_FIELDS))
        changes = {
            field: {"before": _jsonable(getattr(job, field)), "after": _jsonable(value)}
            for field, value in incoming.items()
            if getattr(job, field) != value
        }
        if not changes:
            await self.session.rollback()
            return job_id
        if "department_id" in changes:
            problem = await self._check_department(payload.department_id)
            if problem is not None:
                await self.session.rollback()
                return problem

        for field in changes:
            setattr(job, field, incoming[field])
        if job.status is JobStatus.OPEN:
            problem = self._open_problem(
                job, company_today(moment), check_deadline="deadline" in changes
            )
            if problem is not None:
                await self.session.rollback()
                return problem
        job.version += 1
        job.updated_at = moment
        try:
            await record_event(
                self.session,
                AuditEventInput(
                    action=AuditAction.JOB_UPDATED,
                    outcome=AuditOutcome.SUCCESS,
                    actor_id=actor_id,
                    target_type=AUDIT_TARGET,
                    target_id=str(job.id),
                    metadata={"changes": changes},
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            return _integrity_failure(exc)
        return job_id

    # Kiểm tra lại trạng thái và dữ liệu dưới khóa, không tin trạng thái trên UI.
    async def publish_job(
        self,
        *,
        actor_id: uuid.UUID,
        job_id: int,
        expected_version: int,
        now: datetime | None = None,
    ) -> int | Failure:
        job = await self.jobs.get(job_id, for_update=True)
        # Read the clock only once the row lock is held: waiting may cross midnight.
        moment = now or clock.utcnow()
        if job is None:
            await self.session.rollback()
            return _not_found()
        if job.version != expected_version:
            await self.session.rollback()
            return _conflict()
        if job.status is JobStatus.CLOSED:
            await self.session.rollback()
            return _rule(MSG_CLOSED_NO_REOPEN)
        if job.status is JobStatus.OPEN:
            await self.session.rollback()
            return _rule("Tin đã ở trạng thái Đang mở")
        problem = self._open_problem(job, company_today(moment), check_deadline=True)
        if problem is not None:
            await self.session.rollback()
            return problem

        job.status = JobStatus.OPEN
        job.version += 1
        job.updated_at = moment
        try:
            await record_event(
                self.session,
                AuditEventInput(
                    action=AuditAction.JOB_PUBLISHED,
                    outcome=AuditOutcome.SUCCESS,
                    actor_id=actor_id,
                    target_type=AUDIT_TARGET,
                    target_id=str(job.id),
                    metadata={
                        "previous_status": JobStatus.DRAFT.value,
                        "status": JobStatus.OPEN.value,
                    },
                ),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            return _integrity_failure(exc)
        return job_id

    # Đóng tin chỉ ngừng nhận hồ sơ mới; khác với xóa vĩnh viễn cả cây dữ liệu tin.
    async def close_job(
        self,
        *,
        actor_id: uuid.UUID,
        job_id: int,
        expected_version: int,
        now: datetime | None = None,
    ) -> int | Failure:
        """Stop accepting applications. Pending reviews and interviews are left untouched."""
        moment = now or clock.utcnow()
        job = await self.jobs.get(job_id, for_update=True)
        if job is None:
            await self.session.rollback()
            return _not_found()
        if job.version != expected_version:
            await self.session.rollback()
            return _conflict()
        if job.status is not JobStatus.OPEN:
            # Read the status before rollback: a rollback expires the loaded row.
            message = (
                "Tin đã ở trạng thái Đã đóng"
                if job.status is JobStatus.CLOSED
                else "Chỉ đóng được tin Đang mở"
            )
            await self.session.rollback()
            return _rule(message)

        job.status = JobStatus.CLOSED
        job.closed_at = moment
        job.version += 1
        job.updated_at = moment
        await record_event(
            self.session,
            AuditEventInput(
                action=AuditAction.JOB_CLOSED,
                outcome=AuditOutcome.SUCCESS,
                actor_id=actor_id,
                target_type=AUDIT_TARGET,
                target_id=str(job.id),
                metadata={
                    "previous_status": JobStatus.OPEN.value,
                    "status": JobStatus.CLOSED.value,
                },
            ),
        )
        await self.session.commit()
        return job.id

    # Worker đóng những tin đã qua ngày hạn nộp theo UTC+7 và ghi audit hệ thống.
    async def close_expired_jobs(self, now: datetime | None = None) -> list[int]:
        """Close OPEN postings whose deadline day has passed (company time zone).

        Run periodically by the separate worker process (`python -m app.worker`). The
        conditional bulk UPDATE waits for row locks held by concurrent edits and then
        re-checks status and deadline, so a posting is closed and audited at most once.
        """
        moment = now or clock.utcnow()
        closed = await self.jobs.close_expired(today=company_today(moment), now=moment)
        for job_id in closed:
            await record_event(
                self.session,
                AuditEventInput(
                    action=AuditAction.JOB_CLOSED,
                    outcome=AuditOutcome.SUCCESS,
                    actor_id=None,
                    target_type=AUDIT_TARGET,
                    target_id=str(job_id),
                    metadata={
                        "previous_status": JobStatus.OPEN.value,
                        "status": JobStatus.CLOSED.value,
                        "reason": "Quá hạn nộp hồ sơ",
                    },
                ),
            )
        await self.session.commit()
        return closed

    # Xóa parent để database cascade đúng các bảng con đã cho phép. Giữ ID/trạng
    # thái trước xóa để audit không cần đọc lại một bản ghi không còn tồn tại.
    # Chỉ commit sau khi audit ghi được; lỗi ở một trong hai bước sẽ rollback.
    async def _delete_and_audit(
        self, job: JobPosting, actor_id: uuid.UUID | None, reason: str
    ) -> int:
        job_id = job.id
        previous_status = job.status.value
        await self.jobs.delete(job_id)
        await record_event(
            self.session,
            AuditEventInput(
                action=AuditAction.JOB_DELETED,
                outcome=AuditOutcome.SUCCESS,
                actor_id=actor_id,
                target_type=AUDIT_TARGET,
                target_id=str(job_id),
                metadata={"previous_status": previous_status, "reason": reason},
            ),
        )
        await self.session.commit()
        return job_id

    # API xóa tay chỉ nhận DRAFT; CLOSED đủ hạn phải do luồng purge xử lý.
    # Cùng một row lock bảo vệ cả kiểm tra version, trạng thái và thao tác xóa.
    async def delete_draft_job(
        self, *, actor_id: uuid.UUID, job_id: int, expected_version: int
    ) -> int | Failure:
        job = await self.jobs.get(job_id, for_update=True)
        if job is None:
            await self.session.rollback()
            return _not_found()
        if job.version != expected_version:
            await self.session.rollback()
            return _conflict()
        if job.status is not JobStatus.DRAFT:
            await self.session.rollback()
            return _rule(
                "Chỉ được xóa bản nháp. Tin đã đóng được hệ thống tự động dọn sau hai năm."
            )
        try:
            return await self._delete_and_audit(job, actor_id, "HR xóa bản nháp")
        except IntegrityError:
            await self.session.rollback()
            return _rule("Tin đang có dữ liệu liên quan nên chưa thể xóa.")
        except Exception:
            await self.session.rollback()
            raise

    async def purge_closed_jobs(
        self, now: datetime | None = None, batch_size: int = 100
    ) -> list[int]:
        """Purge due CLOSED postings, one atomic transaction per posting.

        A keyset cursor advances even on failure. Concurrent workers skip held locks;
        a failed or skipped posting is retried on the next sweep, never busy-looped.
        """
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        purged: list[int] = []
        cursor = 0
        while True:
            # Đọc ID theo lô, không nạp toàn bộ nội dung các tin cũ vào bộ nhớ.
            candidates = await self.jobs.purge_candidates(
                today=company_today(now or clock.utcnow()), after_id=cursor, limit=batch_size
            )
            await self.session.commit()
            if not candidates:
                break
            for job_id in candidates:
                # Luôn tiến cursor, kể cả khi tin bị chặn; lần quét sau sẽ thử lại.
                cursor = job_id
                try:
                    # Bỏ qua tin worker khác đang khóa. Sau khi giữ khóa phải xét
                    # lại tuổi/trạng thái, vì dữ liệu có thể đã đổi từ lúc lấy ID.
                    job = await self.jobs.get(job_id, for_update=True, skip_locked=True)
                    moment = now or clock.utcnow()
                    due = deletion_due_date(job.closed_at) if job is not None else None
                    if (
                        job is None
                        or job.status is not JobStatus.CLOSED
                        or due is None
                        or due > company_today(moment)
                    ):
                        await self.session.rollback()
                        continue
                    purged.append(
                        await self._delete_and_audit(job, None, "Hết thời hạn lưu trữ hai năm")
                    )
                except Exception as exc:
                    await self.session.rollback()
                    logger.warning("Closed job purge failed (%s)", type(exc).__name__)
        return purged
