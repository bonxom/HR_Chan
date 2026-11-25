from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.core import clock
from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus, AccountType
from app.modules.applications.models import Application, ApplicationStatus
from app.modules.notifications.models import EmailOutbox
from app.modules.notifications.repository import active_hr_recipients
from app.modules.notifications.service import NotificationService
from app.modules.settings.models import Holiday, SystemSetting

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


async def remind_overdue_reviews(session_factory, settings, now=None):
    now = now or clock.utcnow()
    local = now.astimezone(TZ)
    sent = 0
    async with session_factory() as session:
        hours = await session.get(SystemSetting, "working_hours")
        if hours is None or not hours.value_json:
            return 0
        opening = time.fromisoformat(hours.value_json["start"])
        if local.weekday() >= 5 or local.time().replace(tzinfo=None) < opening:
            return 0
        if await session.get(Holiday, local.date()):
            return 0
        recipients = await active_hr_recipients(session)
    day_start = datetime.combine(local.date(), time.min, TZ)
    day_end = day_start + timedelta(days=1)
    for recipient in recipients:
        async with session_factory.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": f"review-digest:{recipient.account_id}:{local.date()}"},
            )
            existing = await session.scalar(
                select(EmailOutbox.id)
                .where(
                    EmailOutbox.template_code == "REVIEW_OVERDUE_DIGEST",
                    EmailOutbox.user_id == recipient.account_id,
                    EmailOutbox.created_at >= day_start,
                    EmailOutbox.created_at < day_end,
                )
                .limit(1)
            )
            if existing:
                continue
            applications = (
                await session.scalars(
                    select(Application)
                    .where(
                        Application.status == ApplicationStatus.PENDING_HR_REVIEW,
                        Application.review_due_at < now,
                    )
                    .order_by(Application.review_due_at, Application.id)
                )
            ).all()
            if not applications:
                continue
            account = await session.get(Account, recipient.account_id)
            if (
                account is None
                or account.status != AccountStatus.ACTIVE
                or account.account_type != AccountType.EMPLOYEE
                or "HR" not in account.roles
            ):
                continue
            outbox_id = await NotificationService(settings).enqueue(
                session,
                template_code="REVIEW_OVERDUE_DIGEST",
                to=recipient.email,
                user_id=recipient.account_id,
                vars=dict(
                    full_name=account.full_name,
                    overdue_count=len(applications),
                    overdue_list="\n".join(f"Hồ sơ #{app.id}" for app in applications),
                ),
            )
            # Associate the digest with the local day of this worker tick.
            outbox = await session.get(EmailOutbox, outbox_id)
            outbox.created_at = now
            sent += 1
    return sent
