import logging

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core import clock
from app.core.exceptions import AppError
from app.core.interview_scheduler import COMPANY_TZ, InterviewScheduler
from app.core.response_links import ResponseLinkService
from app.integrations.google_workspace.client import GoogleWorkspaceError
from app.modules.accounts.models import Account
from app.modules.applications.models import Application, ApplicationStatus
from app.modules.candidates.models import Candidate
from app.modules.interviews.models import Interview
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.models import JobInterviewer, JobPosting

logger = logging.getLogger(__name__)


class InterviewInvitationService:
    def __init__(self, session, settings, google, session_factory):
        self.session = session
        self.settings = settings
        self.google = google
        self.session_factory = session_factory
        self.scheduler = InterviewScheduler(session, google, settings.interview_duration_minutes)

    async def _application(self, application_id, version=None):
        application = await self.session.scalar(
            select(Application).where(Application.id == application_id).with_for_update()
        )
        if application is None:
            raise AppError("Không tìm thấy hồ sơ", 404, "application_not_found")
        if application.status != ApplicationStatus.PENDING_HR_REVIEW:
            raise AppError("Hồ sơ phải ở trạng thái chờ HR duyệt", 409, "invalid_state")
        if version is not None and application.version != version:
            raise AppError("Hồ sơ đã thay đổi", 409, "version_conflict")
        return application

    async def _interviewer(self, application, interviewer_id):
        ids = list(
            await self.session.scalars(
                select(JobInterviewer.user_id).where(JobInterviewer.job_id == application.job_id)
            )
        )
        if interviewer_id is None:
            if len(ids) != 1:
                raise AppError("Cần chọn người phỏng vấn", 422, "interviewer_required")
            interviewer_id = ids[0]
        if interviewer_id not in ids:
            raise AppError("Người phỏng vấn không thuộc tin", 422, "invalid_interviewer")
        return await self.session.get(Account, interviewer_id)

    async def slots(self, application_id, interviewer_id, date_from, date_to):
        if date_from > date_to:
            raise AppError("Khoảng ngày không hợp lệ", 422, "invalid_date_range")
        application = await self._application(application_id)
        interviewer = await self._interviewer(application, interviewer_id)
        try:
            return await self.scheduler.suggest(interviewer, date_from, date_to, clock.utcnow())
        except GoogleWorkspaceError:
            raise AppError(
                "Không truy cập được lịch phỏng vấn", 503, "calendar_unavailable"
            ) from None

    async def _compensate(self, event_id):
        try:
            await self.google.cancel_event(event_id)
        except Exception:
            logger.error("Calendar cancellation failed for google_event_id=%s", event_id)

    async def _reconcile(self, event_id):
        try:
            async with self.session_factory() as session:
                committed = await session.scalar(
                    select(Interview.id).where(Interview.google_event_id == event_id)
                )
        except Exception:
            logger.error("Calendar commit unresolved for google_event_id=%s", event_id)
            return
        if committed is None:
            await self._compensate(event_id)

    async def invite(self, application_id, actor_id, start_at, version, interviewer_id=None):
        event = None
        committing = False
        now = clock.utcnow()
        try:
            application = await self._application(application_id, version)
            interviewer = await self._interviewer(application, interviewer_id)
            end_at = await self.scheduler.validate(interviewer, start_at, now)
            expires_at = await self.scheduler.deadline(now)
            job = await self.session.get(JobPosting, application.job_id)
            candidate = await self.session.get(Candidate, application.candidate_id)
            event = await self.google.create_event(interviewer.email, start_at, end_at, job.title)
            interview = await self.scheduler.reserve(
                application_id=application.id,
                interviewer_id=interviewer.id,
                start_at=start_at,
                end_at=end_at,
                status="SCHEDULED",
                auto_scheduled=False,
                created_by=actor_id,
                google_event_id=event.event_id,
                meet_link=event.meet_link,
            )
            link = await ResponseLinkService(self.session, self.settings.public_base_url).issue(
                purpose="CONFIRM_INTERVIEW",
                application_id=application.id,
                interview_id=interview.id,
                expires_at=expires_at,
                now=now,
            )
            await NotificationService(self.settings).enqueue(
                self.session,
                template_code="INTERVIEW_INVITE",
                to=candidate.email,
                application_id=application.id,
                vars={
                    "full_name": candidate.full_name,
                    "job_title": job.title,
                    "interview_time": start_at.astimezone(COMPANY_TZ).strftime("%d/%m/%Y %H:%M"),
                    "meet_link": event.meet_link,
                    "confirm_url": link.url,
                    "response_deadline": expires_at.astimezone(COMPANY_TZ).strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                },
                secret_vars={"confirm_url"},
            )
            await self.session.execute(
                text("SELECT set_config('app.actor_id',:actor,true)"), {"actor": str(actor_id)}
            )
            application.status = ApplicationStatus.INTERVIEW_INVITED
            application.version += 1
            application.decided_by = actor_id
            application.decided_at = now
            application.updated_at = now
            result = {
                "application_id": application.id,
                "status": "INTERVIEW_INVITED",
                "version": application.version,
                "interview_id": interview.id,
            }
            await self.session.flush()
            committing = True
            await self.session.commit()
            return result
        except Exception as exc:
            try:
                await self.session.rollback()
            except Exception:
                logger.error("Invitation rollback failed")
            if event is not None:
                if committing:
                    await self._reconcile(event.event_id)
                else:
                    await self._compensate(event.event_id)
            if isinstance(exc, DBAPIError):
                name = getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
                sqlstate = getattr(exc.orig, "sqlstate", None)
                if name in {"interviews_no_overlap", "interviews_one_active"} or (
                    event is not None and sqlstate == "40P01"
                ):
                    raise AppError("Khung giờ vừa có người đặt", 409, "slot_conflict") from None
            if isinstance(exc, GoogleWorkspaceError):
                raise AppError(
                    "Không tạo được lịch phỏng vấn", 503, "calendar_unavailable"
                ) from None
            raise
