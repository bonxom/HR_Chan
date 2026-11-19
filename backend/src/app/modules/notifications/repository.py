"""Outbox and template queries. Callers own every transaction."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus, AccountType, EmployeeRole
from app.modules.applications.models import EMAIL_ISSUE_MAX, Application
from app.modules.notifications.models import EmailOutbox, EmailStatus, EmailTemplate
from app.modules.notifications.payloads import IMMEDIATE_PREFIX
from app.modules.notifications.schemas import HrRecipient


async def get_template(session: AsyncSession, code: str) -> EmailTemplate | None:
    return await session.get(EmailTemplate, code)


async def add_outbox(session: AsyncSession, row: EmailOutbox) -> int:
    session.add(row)
    await session.flush()
    return row.id


async def lock_row(session: AsyncSession, outbox_id: int) -> EmailOutbox | None:
    """Lock one row, waiting if needed (used by sendNow on its own row)."""
    return await session.scalar(
        select(EmailOutbox).where(EmailOutbox.id == outbox_id).with_for_update()
    )


def _immediate():
    return EmailOutbox.body.startswith(IMMEDIATE_PREFIX, autoescape=True)


async def claim_next_queued(
    session: AsyncSession, now: datetime, skip_ids: Sequence[int]
) -> EmailOutbox | None:
    """Lock the next due queued row; rows locked by another worker are skipped.

    Một dòng mỗi giao dịch: worker khác vẫn lấy được các dòng còn lại ngay, không bị
    một worker khóa cả lô N dòng trong lúc nó mới gửi dòng đầu.
    """
    query = (
        select(EmailOutbox)
        .where(
            EmailOutbox.status == EmailStatus.PENDING,
            EmailOutbox.next_attempt_at <= now,
            ~_immediate(),
        )
        .order_by(EmailOutbox.next_attempt_at, EmailOutbox.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if skip_ids:
        query = query.where(EmailOutbox.id.not_in(list(skip_ids)))
    return await session.scalar(query)


async def claim_abandoned_immediate(
    session: AsyncSession, started_before: datetime, skip_ids: Sequence[int]
) -> EmailOutbox | None:
    """Lock one immediate row whose last attempt started before ``started_before``.

    sendNow giữ khóa dòng trong lúc gửi, nên SKIP LOCKED không bao giờ lấy một dòng
    đang được gửi; chỉ dòng của tiến trình API đã chết mới bị chốt lỗi.
    """
    query = (
        select(EmailOutbox)
        .where(
            EmailOutbox.status == EmailStatus.PENDING,
            EmailOutbox.next_attempt_at <= started_before,
            _immediate(),
        )
        .order_by(EmailOutbox.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if skip_ids:
        query = query.where(EmailOutbox.id.not_in(list(skip_ids)))
    return await session.scalar(query)


async def record_attempt_start(session: AsyncSession, outbox_id: int, at: datetime) -> bool:
    """Durably count one attempt before SMTP; ``next_attempt_at`` marks when it started."""
    result = await session.execute(
        update(EmailOutbox)
        .where(EmailOutbox.id == outbox_id, EmailOutbox.status == EmailStatus.PENDING)
        .values(attempts=EmailOutbox.attempts + 1, next_attempt_at=at)
    )
    return bool(result.rowcount)


async def flag_application_email_issue(
    session: AsyncSession, application_id: int, issue: str
) -> None:
    await session.execute(
        update(Application)
        .where(Application.id == application_id)
        .values(email_issue=issue[:EMAIL_ISSUE_MAX])
    )


async def active_hr_recipients(session: AsyncSession) -> list[HrRecipient]:
    rows = await session.execute(
        select(Account.id, Account.email)
        .where(
            Account.account_type == AccountType.EMPLOYEE,
            Account.status == AccountStatus.ACTIVE,
            Account.roles.any(EmployeeRole.HR.value),
        )
        .order_by(Account.id)
    )
    return [HrRecipient(account_id=row.id, email=row.email) for row in rows]
