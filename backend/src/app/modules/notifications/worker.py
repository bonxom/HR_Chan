"""Outbox delivery and recovery tasks, run by the separate worker process.

``deliver_due_batch`` delivers queued PENDING rows that are due, at most
``settings.email_outbox_batch_size`` per run. Each row is claimed with
``FOR UPDATE SKIP LOCKED`` in its own transaction, kept locked through the SMTP call and
committed with its result before the next row is claimed.

SMTP and the database share no transaction: if the process dies after the server
accepted a message but before the commit, the row is delivered again on a later run with
the same Message-ID (at-least-once, not exactly-once).

``fail_abandoned_immediate`` closes immediate (sendNow) rows whose API process stopped
mid-send: they become FAILED and are never resent.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.otp.repository import invalidate_live_code
from app.integrations.email.errors import PermanentEmailError
from app.integrations.email.service import IEmailService
from app.modules.notifications import repository
from app.modules.notifications.models import MAX_ATTEMPTS, EmailOutbox
from app.modules.notifications.payloads import (
    QUEUED,
    UNREADABLE_BODY,
    Envelope,
    EnvelopeError,
    decrypt_payload,
    parse_envelope,
)
from app.modules.notifications.schemas import TemplateCode
from app.modules.notifications.service import (
    NotificationService,
    mark_failed,
    mark_sent,
    message_id_for,
    send_classified,
    to_message,
)

logger = logging.getLogger(__name__)

RETRY_DELAY = timedelta(minutes=5)
# Lâu hơn toàn bộ ngân sách sendNow (2 lượt x 10 giây + ghi DB) để không chốt lỗi
# một lượt gửi còn đang chạy.
ABANDONED_AFTER = timedelta(seconds=60)
INVALID_PAYLOAD = "invalid_payload"
ATTEMPTS_EXHAUSTED = "attempts_exhausted"
ABANDONED = "abandoned"


def _email_issue(template_code: str, code: str) -> str:
    return f"Gửi email {template_code} thất bại ({code})"


async def _handle_failure(
    session: AsyncSession, row: EmailOutbox, code: str, settings: Settings
) -> None:
    """Within the row's transaction: flag the application and queue HR alerts.

    Thư báo lỗi (EMAIL_DELIVERY_FAILED) không bao giờ sinh thêm thư báo lỗi và không
    ghi đè email_issue; lỗi của nó chỉ được log.
    """
    if row.template_code == TemplateCode.EMAIL_DELIVERY_FAILED:
        logger.warning("Delivery-failure alert %s failed (%s)", row.id, code)
        return
    if row.application_id is None:
        return
    await repository.flag_application_email_issue(
        session, row.application_id, _email_issue(row.template_code, code)
    )
    notifications = NotificationService(settings)
    try:
        # Savepoint: cảnh báo cùng giao dịch với FAILED + email_issue. Nếu không tạo
        # được cảnh báo (ví dụ mẫu bị thiếu), vẫn chốt FAILED để không gửi lại vô hạn.
        async with session.begin_nested():
            for hr in await repository.active_hr_recipients(session):
                await notifications.enqueue(
                    session,
                    template_code=TemplateCode.EMAIL_DELIVERY_FAILED,
                    to=hr.email,
                    vars={
                        "application_id": str(row.application_id),
                        "failed_template": row.template_code,
                        "error_code": code,
                    },
                    application_id=row.application_id,
                    user_id=hr.account_id,
                )
    except Exception as exc:
        logger.error("Could not queue delivery-failure alerts (%s)", type(exc).__name__)


async def _deliver_one(
    session: AsyncSession,
    row: EmailOutbox,
    email_service: IEmailService,
    settings: Settings,
    now: datetime,
) -> bool:
    """Process one claimed row. Returns False when it was skipped without an attempt."""
    try:
        envelope: Envelope = parse_envelope(row.body)
        if envelope.mode != QUEUED:
            raise EnvelopeError("Not a queued envelope")
    except EnvelopeError:
        # Không thử giải mã/gửi nội dung rác: chốt lỗi ngay, không giữ thân hỏng.
        row.attempts = min(row.attempts + 1, MAX_ATTEMPTS)
        mark_failed(row, UNREADABLE_BODY, INVALID_PAYLOAD)
        # (attempts giới hạn ở 4 để không vi phạm CHECK khi dòng đã hết lượt.)
        await _handle_failure(session, row, INVALID_PAYLOAD, settings)
        logger.warning("Outbox email %s has an unreadable body", row.id)
        return True

    if row.attempts >= MAX_ATTEMPTS:
        # Dòng PENDING đã dùng hết 4 lượt (ví dụ dữ liệu cũ/sửa tay): không được gọi
        # SMTP lần 5 (vi phạm CHECK attempts <= 4). Chốt FAILED ngay, gắn cờ và báo HR,
        # thay vì bỏ qua khiến dòng PENDING mãi.
        mark_failed(row, envelope.redacted.text_body, ATTEMPTS_EXHAUSTED)
        await _handle_failure(session, row, ATTEMPTS_EXHAUSTED, settings)
        logger.warning("Outbox email %s had no attempts left; marked FAILED", row.id)
        return True

    content = envelope.redacted
    if envelope.payload is not None:
        try:
            key = settings.require_outbox_key()
        except AppError:
            # Thiếu khóa là lỗi cấu hình: không tính lượt, để nguyên chờ cấu hình.
            logger.error("Outbox email %s skipped: OUTBOX_ENCRYPTION_KEY missing", row.id)
            return False
        try:
            content = decrypt_payload(envelope, key)
        except EnvelopeError:
            row.attempts = min(row.attempts + 1, MAX_ATTEMPTS)
            mark_failed(row, envelope.redacted.text_body, INVALID_PAYLOAD)
            await _handle_failure(session, row, INVALID_PAYLOAD, settings)
            logger.warning("Outbox email %s payload failed authentication", row.id)
            return True

    message = to_message(row.to_email, content, message_id_for(row.id, settings))
    error = await send_classified(email_service, message)
    result_at = max(now, clock.utcnow())
    row.attempts += 1
    if error is None:
        mark_sent(row, envelope.redacted, clock.utcnow())
        return True
    if isinstance(error, PermanentEmailError) or row.attempts >= MAX_ATTEMPTS:
        mark_failed(row, envelope.redacted.text_body, error.code)
        await _handle_failure(session, row, error.code, settings)
        logger.warning("Outbox email %s failed (%s)", row.id, error.code)
        return True
    row.last_error = error.code
    row.next_attempt_at = result_at + RETRY_DELAY
    logger.info("Outbox email %s will be retried (%s)", row.id, error.code)
    return True


async def deliver_due_batch(
    session_factory: async_sessionmaker[AsyncSession],
    email_service: IEmailService,
    settings: Settings,
    now: datetime,
) -> int:
    """Deliver up to N due queued rows; return how many rows were attempted."""
    processed = 0
    seen: list[int] = []
    while len(seen) < settings.email_outbox_batch_size:
        async with session_factory() as session:
            row = await repository.claim_next_queued(session, now, seen)
            if row is None:
                await session.rollback()
                break
            seen.append(row.id)
            # Khóa dòng được giữ trong suốt lượt gửi và chỉ nhả khi commit kết quả.
            attempted = await _deliver_one(session, row, email_service, settings, now)
            if attempted:
                await session.commit()
                processed += 1
            else:
                await session.rollback()
    return processed


async def fail_abandoned_immediate(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> int:
    """Close immediate rows whose last attempt started more than 60 s before ``now``."""
    closed = 0
    seen: list[int] = []
    cutoff = now - ABANDONED_AFTER
    while True:
        async with session_factory() as session:
            row = await repository.claim_abandoned_immediate(session, cutoff, seen)
            if row is None:
                await session.rollback()
                break
            seen.append(row.id)
            otp_id = None
            body = UNREADABLE_BODY
            try:
                envelope = parse_envelope(row.body)
                body = envelope.redacted.text_body
                otp_id = envelope.otp_id
            except EnvelopeError:
                pass
            # Không gửi lại: chốt FAILED (attempts >= 1 theo CHECK) và vô hiệu đúng mã
            # OTP của thư này; mã mới hơn do gửi lại không bị ảnh hưởng.
            mark_failed(row, body, ABANDONED)
            if otp_id is not None:
                await invalidate_live_code(session, otp_id, clock.utcnow())
            await session.commit()
            closed += 1
            logger.warning("Immediate email %s was abandoned; marked FAILED", row.id)
    return closed
