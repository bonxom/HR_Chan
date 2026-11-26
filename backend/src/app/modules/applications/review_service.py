from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.core import clock
from app.core.exceptions import AppError
from app.integrations.storage.client import StorageError
from app.modules.applications import review_repository as repository
from app.modules.applications.models import ApplicationStatus
from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event
from app.modules.candidates.envelope import EnvelopeFormatError, unpack
from app.modules.interviews.models import Interview
from app.modules.notifications.service import NotificationService


async def audit_access(session, actor_id, action, application_id=None):
    await record_event(
        session,
        AuditEventInput(
            action=action,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="application",
            target_id=str(application_id) if application_id else None,
        ),
    )


def summary(application, candidate, job):
    return dict(
        id=application.id,
        job_id=job.id,
        job_title=job.title,
        full_name=candidate.full_name,
        email=candidate.email,
        submitted_at=application.submitted_at,
        status=application.status,
        ai_status=application.ai_status,
        ai_total_score=application.ai_total_score,
        review_due_at=application.review_due_at,
        email_issue=application.email_issue,
        version=application.version,
    )


class ApplicationReviewService:
    def __init__(self, session):
        self.session = session

    async def _load(self, application_id, *, lock=False):
        row = await repository.joined_application(self.session, application_id, lock=lock)
        if row is None:
            raise AppError("Không tìm thấy hồ sơ", 404, "application_not_found")
        return row

    async def list(self, actor_id, filters):
        rows, total = await repository.list_applications(self.session, filters, clock.utcnow())
        result = dict(
            items=[summary(*row) for row in rows],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )
        await audit_access(self.session, actor_id, AuditAction.APPLICATION_LISTED)
        await self.session.commit()
        return result

    async def detail(self, actor_id, application_id):
        application, candidate, cv, job = await self._load(application_id)
        result = summary(application, candidate, job)
        explanations = []
        for score, criterion in await repository.score_explanations(self.session, application_id):
            item = dict(
                criterion_id=criterion.id,
                name=criterion.name,
                is_mandatory=criterion.is_mandatory,
                score=score.score,
                weight_snapshot=score.weight_snapshot,
                ai_comment=score.ai_comment,
            )
            if criterion.is_mandatory:
                item.update(min_score=criterion.min_score, meets_mandatory=score.meets_mandatory)
            explanations.append(item)
        history = []
        for event in await repository.status_history(self.session, application_id):
            change = event.event_metadata.get("changes", {}).get("status", {})
            history.append(dict(at=event.timestamp, actor_id=event.actor_id, **change))
        result.update(
            candidate=dict(
                id=candidate.id,
                full_name=candidate.full_name,
                email=candidate.email,
                phone=candidate.phone,
            ),
            parsed_data=cv.parsed_data,
            criteria_set_id=application.criteria_set_id,
            ai_failure_reason=application.ai_failure_reason,
            hr_note=application.hr_note,
            scores=explanations,
            status_history=history,
        )
        interview = await self.session.scalar(
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(Interview.id.desc())
            .limit(1)
        )
        result["interview"] = (
            {
                "id": interview.id,
                "status": interview.status,
                "needs_manual_calendar_fix": interview.needs_manual_calendar_fix,
            }
            if interview is not None
            else None
        )
        await audit_access(self.session, actor_id, AuditAction.APPLICATION_VIEWED, application_id)
        await self.session.commit()
        return result

    async def download_cv(self, actor_id, application_id, storage):
        _, _, cv, _ = await self._load(application_id)
        if storage is None:
            raise AppError("Kho CV chưa sẵn sàng", 503, "cv_unavailable")
        try:
            blob = await storage.get(cv.cv_storage_key)
            content, _ = unpack(blob)
        except (StorageError, OSError, EnvelopeFormatError):
            raise AppError("Không đọc được CV", 503, "cv_unavailable") from None
        filename = cv.cv_original_name.replace("\\", "/").split("/")[-1]
        headers = {
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename),
            "Cache-Control": "private, no-store",
        }
        await audit_access(
            self.session, actor_id, AuditAction.APPLICATION_CV_DOWNLOADED, application_id
        )
        await self.session.commit()
        return content, cv.cv_mime_type, headers

    async def reject(self, actor_id, application_id, payload, settings):
        from app.core.response_links import ResponseLinkService

        try:
            application, candidate, _, job = await self._load(application_id, lock=True)
            if application.version != payload.version:
                raise AppError("Hồ sơ đã thay đổi, vui lòng tải lại", 409, "version_conflict")
            if application.status != ApplicationStatus.PENDING_HR_REVIEW:
                raise AppError("Hồ sơ không còn chờ xét duyệt", 409, "invalid_application_state")
            now = clock.utcnow()
            deadline = await self.session.scalar(
                text(
                    "SELECT working_deadline(:at,value::integer) FROM system_settings"
                    " WHERE key='response_deadline_days'"
                ),
                {"at": now},
            )
            if deadline is None:
                raise AppError("Thiếu cấu hình hạn phản hồi", 503, "configuration_error")
            link = await ResponseLinkService(self.session, settings.public_base_url).issue(
                purpose="TALENT_POOL_CONSENT",
                application_id=application_id,
                expires_at=deadline,
                now=now,
            )
            await NotificationService(settings).enqueue(
                self.session,
                template_code="REJECT_THANK_YOU",
                to=candidate.email,
                vars=dict(
                    full_name=candidate.full_name,
                    job_title=job.title,
                    consent_url=link.url,
                    response_deadline=deadline.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).strftime(
                        "%d/%m/%Y %H:%M"
                    ),
                ),
                secret_vars={"consent_url"},
                application_id=application_id,
            )
            await self.session.execute(
                text("SELECT set_config('app.actor_id', :actor, true)"), {"actor": str(actor_id)}
            )
            application.status = ApplicationStatus.REJECTED
            application.decided_by = actor_id
            application.decided_at = application.updated_at = now
            application.reject_reason_code = payload.reason_code.value
            application.reject_reason_text = payload.reason_text
            application.version += 1
            await audit_access(
                self.session, actor_id, AuditAction.APPLICATION_REJECTED, application_id
            )
            result = dict(
                application_id=application_id,
                status=application.status,
                version=application.version,
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise
