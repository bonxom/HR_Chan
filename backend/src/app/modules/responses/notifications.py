from zoneinfo import ZoneInfo

from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditEventInput
from app.modules.audit.service import record_event
from app.modules.notifications.repository import active_hr_recipients
from app.modules.notifications.service import NotificationService

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def display_time(value):
    return value.astimezone(TZ).strftime("%d/%m/%Y %H:%M")


async def audit_response(session, context, action, changes):
    await record_event(
        session,
        AuditEventInput(
            action=action,
            outcome=AuditOutcome.SUCCESS,
            actor_id=None,
            target_type="application",
            target_id=str(context.application.id),
            metadata={"changes": {"response_link_id": context.link.id, **changes}},
        ),
    )


async def notify_hr(session, settings, context, template_code, variables):
    notifications = NotificationService(settings)
    for recipient in await active_hr_recipients(session):
        await notifications.enqueue(
            session,
            template_code=template_code,
            to=recipient.email,
            user_id=recipient.account_id,
            application_id=context.application.id,
            vars=variables,
        )


async def notify_calendar_pending(session, settings, context):
    await notify_hr(
        session,
        settings,
        context,
        "CALENDAR_SYNC_REQUIRED_HR",
        {
            "application_id": context.application.id,
            "interview_id": context.interview.id,
            "action": "Hủy lịch phỏng vấn",
        },
    )


async def notify_expired(session, settings, context):
    subject = "Lời mời phỏng vấn" if context.interview is not None else "Đề nghị đồng ý lưu hồ sơ"
    variables = {
        "job_title": context.job.title,
        "response_subject": subject,
        "response_deadline": display_time(context.link.expires_at),
    }
    await NotificationService(settings).enqueue(
        session,
        template_code="RESPONSE_EXPIRED_CANDIDATE",
        to=context.candidate.email,
        application_id=context.application.id,
        vars={"full_name": context.candidate.full_name, **variables},
    )
    await notify_hr(
        session,
        settings,
        context,
        "RESPONSE_EXPIRED_HR",
        {"application_id": context.application.id, **variables},
    )
