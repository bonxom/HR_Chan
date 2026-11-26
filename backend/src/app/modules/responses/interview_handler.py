from sqlalchemy import func, select, text

from app.core.exceptions import AppError
from app.core.response_handler import ResponseHandler
from app.core.response_links import LinkOutcome, invalid_link
from app.modules.applications.models import ApplicationStatus
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditAction
from app.modules.interviews.models import InterviewStatus
from app.modules.responses.notifications import (
    audit_response,
    display_time,
    notify_calendar_pending,
    notify_hr,
)
from app.modules.settings.models import SystemSetting


class InterviewResponseHandler(ResponseHandler):
    def validate(self, context):
        application, interview, link = context.application, context.interview, context.link
        if (
            interview is None
            or application.status != ApplicationStatus.INTERVIEW_INVITED
            or interview.status != InterviewStatus.SCHEDULED
            or interview.application_id != application.id
            or link.interview_id != interview.id
        ):
            raise invalid_link()

    async def _request_count(self, context):
        return await self.session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.target_type == "application",
                AuditEvent.target_id == str(context.application.id),
                AuditEvent.action == AuditAction.INTERVIEW_RESCHEDULE_REQUESTED.value,
            )
        )

    async def _limit(self):
        value = await self.session.get(SystemSetting, "max_reschedule_requests")
        if value is None or value.value is None:
            raise AppError("Thiếu cấu hình phản hồi", 503, "configuration_error")
        return int(value.value)

    async def view(self, context):
        self.validate(context)
        available = await self._request_count(context) < await self._limit()
        actions = ["ACCEPTED", "DECLINED"]
        if available:
            actions.append("RESCHEDULE_REQUESTED")
        return {
            "start_at": context.interview.start_at,
            "meet_link": context.interview.meet_link,
            "allowed_actions": actions,
            "can_reschedule": available,
        }

    async def apply(self, context, payload):
        self.validate(context)
        action = LinkOutcome(payload.action)
        note = (payload.note or "").strip()
        due = None
        interview, application = context.interview, context.application
        if action in (LinkOutcome.DECLINED, LinkOutcome.RESCHEDULE_REQUESTED):
            if not note or len(note) > 500:
                raise AppError("Vui lòng nhập ghi chú từ 1 đến 500 ký tự", 422, "invalid_note")
        if action == LinkOutcome.ACCEPTED:
            interview.status = InterviewStatus.CONFIRMED
            application.status = ApplicationStatus.INTERVIEW_CONFIRMED
            audit = AuditAction.INTERVIEW_CONFIRMED
            message = "Bạn đã xác nhận lịch phỏng vấn."
        elif action == LinkOutcome.RESCHEDULE_REQUESTED:
            if await self._request_count(context) >= await self._limit():
                raise AppError("Đã đạt giới hạn yêu cầu đổi lịch", 422, "reschedule_limit")
            due = await self.session.scalar(
                text(
                    "SELECT working_deadline(:at,value::integer) FROM system_settings"
                    " WHERE key='reschedule_handle_days'"
                ),
                {"at": context.now},
            )
            if due is None:
                raise AppError("Thiếu cấu hình hạn xử lý", 503, "configuration_error")
            interview.status = InterviewStatus.RESCHEDULE_REQUESTED
            interview.reschedule_note = note
            audit = AuditAction.INTERVIEW_RESCHEDULE_REQUESTED
            message = "Yêu cầu đổi lịch đã được gửi đến bộ phận tuyển dụng."
        elif action == LinkOutcome.DECLINED:
            self._cancel(context, note)
            audit = AuditAction.INTERVIEW_DECLINED
            message = "Đã ghi nhận từ chối phỏng vấn. Hủy sự kiện lịch đang chờ đồng bộ."
            await notify_calendar_pending(self.session, self.settings, context)
        else:
            raise AppError("Phản hồi không hợp lệ", 422, "invalid_action")
        application.version += 1
        application.updated_at = context.now
        changes = {"outcome": action.value, "note": note}
        if due is not None:
            changes["handle_due_at"] = due.isoformat()
        await audit_response(self.session, context, audit, changes)
        await notify_hr(
            self.session,
            self.settings,
            context,
            "INTERVIEW_RESPONSE_HR",
            {
                "application_id": application.id,
                "job_title": context.job.title,
                "response": action.value,
                "response_time": display_time(context.now),
                "note": note or "—",
                "handle_due_at": display_time(due) if due else "—",
            },
        )
        return {
            "outcome": action.value,
            "application_status": application.status,
            "interview_status": interview.status,
            "message": message,
        }

    def _cancel(self, context, reason):
        context.interview.status = InterviewStatus.CANCELLED
        context.interview.decline_reason = reason
        context.interview.needs_manual_calendar_fix = True
        context.application.status = ApplicationStatus.INTERVIEW_DECLINED

    async def expire(self, context):
        self.validate(context)
        self._cancel(context, "Không phản hồi trong thời hạn")
        context.application.version += 1
        context.application.updated_at = context.now
        await notify_calendar_pending(self.session, self.settings, context)
