"""NotificationService: every email goes through ``email_outbox`` (BR11).

* ``enqueue`` writes a queued row in the caller's transaction (flush only): a business
  rollback also discards the mail. It never calls SMTP.
* ``sendNow`` (OTP, test mail) records the row and delivers immediately, with at most two
  attempts on temporary errors and one on a permanent error. The worker never resends
  immediate rows; an API crash mid-send is closed by ``worker.fail_abandoned_immediate``.

Only redacted content is ever written for immediate mail; queued secrets are encrypted
and removed when the row reaches SENT/FAILED. Logs carry outbox IDs and error codes only.
"""

import logging
import uuid
from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.core.config import Settings
from app.core.otp.repository import invalidate_live_code
from app.integrations.email.errors import (
    EmailDeliveryError,
    PermanentEmailError,
    TemporaryEmailError,
)
from app.integrations.email.message import EmailMessage
from app.integrations.email.service import IEmailService
from app.modules.notifications import repository
from app.modules.notifications.models import EmailOutbox, EmailStatus
from app.modules.notifications.payloads import IMMEDIATE, QUEUED, build_envelope, check_meta
from app.modules.notifications.rendering import (
    RenderedEmail,
    RenderResult,
    normalize_recipient,
    render_template,
)
from app.modules.notifications.schemas import TEMPLATE_SECRET_VARS, DeliveryResult

logger = logging.getLogger(__name__)

IMMEDIATE_MAX_ATTEMPTS = 2  # lần đầu + thử lại ngay 1 lần (00 §4.5c)
UNKNOWN_SEND_ERROR = "send_error"


class TemplateNotFoundError(LookupError):
    """No email template with the requested code."""


def message_id_for(outbox_id: int, settings: Settings) -> str:
    """Stable Message-ID per outbox row (same value on every attempt, for reconciliation)."""
    domain = settings.mail_from_address.rpartition("@")[2] or "localhost"
    return f"<outbox.{outbox_id}@{domain}>"


def to_message(recipient: str, content: RenderedEmail, message_id: str) -> EmailMessage:
    return EmailMessage(
        to=recipient,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
        message_id=message_id,
    )


async def send_classified(
    service: IEmailService, message: EmailMessage
) -> EmailDeliveryError | None:
    """One SMTP call; any failure becomes a classified error without raw text."""
    try:
        await service.send(message)
    except EmailDeliveryError as exc:
        return exc
    except Exception as exc:
        # Lỗi không phân loại được: coi là tạm thời, chỉ log tên loại lỗi.
        logger.warning("Email service raised an unexpected %s", type(exc).__name__)
        return TemporaryEmailError(UNKNOWN_SEND_ERROR)
    return None


def mark_sent(row: EmailOutbox, redacted: RenderedEmail, at: datetime) -> None:
    row.status = EmailStatus.SENT
    row.sent_at = at
    row.last_error = None
    row.body = redacted.text_body  # bỏ envelope/payload, chỉ giữ bản đã che


def mark_failed(row: EmailOutbox, body: str, code: str) -> None:
    row.status = EmailStatus.FAILED
    # CHECK email_outbox_failed_has_error: FAILED cần attempts >= 1 và last_error.
    row.attempts = max(row.attempts, 1)
    row.last_error = code
    row.body = body


class NotificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _prepare(
        self,
        session: AsyncSession,
        template_code: str,
        to: str,
        variables: Mapping[str, Any],
        secret_vars: Collection[str],
    ) -> tuple[str, RenderResult, frozenset[str]]:
        recipient = normalize_recipient(to)
        template = await repository.get_template(session, template_code)
        if template is None:
            raise TemplateNotFoundError("Email template is not configured")
        # Hợp với biến bí mật bắt buộc của mẫu (ví dụ otp_code của OTP_APPLY) để caller
        # quên khai báo cũng không làm lộ mã trong outbox.
        secrets = frozenset(secret_vars) | TEMPLATE_SECRET_VARS.get(str(template_code), frozenset())
        rendered = render_template(
            template.subject,
            template.body,
            variables,
            required_vars=template.required_vars,
            secret_vars=secrets,
        )
        return recipient, rendered, secrets

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        template_code: str,
        to: str,
        vars: Mapping[str, Any],  # noqa: A002 - public contract name from the approved plan
        application_id: int | None = None,
        user_id: uuid.UUID | None = None,
        secret_vars: Collection[str] = frozenset(),
    ) -> int:
        recipient, rendered, secrets = await self._prepare(
            session, template_code, to, vars, secret_vars
        )
        secret = None
        key = None
        if secrets:
            # Fail closed: không có khóa thì không xếp hàng bí mật dưới dạng rõ.
            key = self._settings.require_outbox_key()
            secret = rendered.full
        now = clock.utcnow()
        row = EmailOutbox(
            template_code=template_code,
            to_email=recipient,
            subject=rendered.redacted.subject,
            body=build_envelope(QUEUED, rendered.redacted, secret=secret, key=key),
            application_id=application_id,
            user_id=user_id,
            status=EmailStatus.PENDING,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
        # Chỉ flush trong giao dịch của caller; caller commit hoặc rollback cùng nghiệp vụ.
        return await repository.add_outbox(session, row)

    async def sendNow(  # noqa: N802 - name fixed by the approved design
        self,
        session_factory: async_sessionmaker[AsyncSession],
        email_service: IEmailService,
        *,
        template_code: str,
        to: str,
        vars: Mapping[str, Any],  # noqa: A002
        application_id: int | None = None,
        user_id: uuid.UUID | None = None,
        secret_vars: Collection[str] = frozenset(),
        immediate_metadata: Mapping[str, Any] | None = None,
    ) -> DeliveryResult:
        meta = check_meta(dict(immediate_metadata or {}))
        # Giao dịch 1: ghi dòng outbox chỉ chứa bản đã che (OTP thật chỉ ở bộ nhớ).
        async with session_factory() as session:
            recipient, rendered, _secrets = await self._prepare(
                session, template_code, to, vars, secret_vars
            )
            now = clock.utcnow()
            row = EmailOutbox(
                template_code=template_code,
                to_email=recipient,
                subject=rendered.redacted.subject,
                body=build_envelope(IMMEDIATE, rendered.redacted, meta=meta),
                application_id=application_id,
                user_id=user_id,
                status=EmailStatus.PENDING,
                attempts=0,
                next_attempt_at=now,
                created_at=now,
            )
            outbox_id = await repository.add_outbox(session, row)
            await session.commit()

        message = to_message(recipient, rendered.full, message_id_for(outbox_id, self._settings))
        otp_id = meta.get("otp_id")
        attempts = 0
        last_code: str | None = None
        for attempt in range(1, IMMEDIATE_MAX_ATTEMPTS + 1):
            # Giao dịch 2: đếm lượt thử và commit TRƯỚC khi gọi SMTP. Nếu tiến trình chết
            # giữa chừng, dòng vẫn có attempts >= 1 và tác vụ phục hồi chốt FAILED,
            # không bao giờ gửi lại.
            async with session_factory() as session:
                started = await repository.record_attempt_start(session, outbox_id, clock.utcnow())
                await session.commit()
            if not started:
                break  # đã bị phục hồi chốt lỗi (không xảy ra trong ngân sách bình thường)
            attempts = attempt

            # Giao dịch 3: giữ khóa dòng suốt lượt gửi tới khi ghi kết quả, để worker
            # phục hồi (SKIP LOCKED) không thể chốt lỗi dòng đang được gửi.
            async with session_factory() as session:
                locked = await repository.lock_row(session, outbox_id)
                if locked is None or locked.status != EmailStatus.PENDING:
                    await session.rollback()
                    break
                error = await send_classified(email_service, message)
                done_at = clock.utcnow()
                if error is None:
                    mark_sent(locked, rendered.redacted, done_at)
                    await session.commit()
                    return DeliveryResult(outbox_id, EmailStatus.SENT, locked.attempts, None)
                last_code = error.code
                permanent = isinstance(error, PermanentEmailError)
                if not permanent and attempt < IMMEDIATE_MAX_ATTEMPTS:
                    locked.last_error = error.code
                    await session.commit()
                    logger.info("Immediate email %s attempt failed (%s)", outbox_id, error.code)
                    continue
                mark_failed(locked, rendered.redacted.text_body, error.code)
                if otp_id is not None:
                    # Gửi thất bại thì mã OTP tương ứng không dùng được nữa; mã mới hơn
                    # (đã gửi lại) không bị đụng tới.
                    await invalidate_live_code(session, otp_id, done_at)
                await session.commit()
                logger.warning("Immediate email %s failed (%s)", outbox_id, error.code)
                return DeliveryResult(outbox_id, EmailStatus.FAILED, locked.attempts, error.code)

        # Dòng đã được chốt bởi tiến trình khác; báo trạng thái hiện tại.
        async with session_factory() as session:
            current = await session.get(EmailOutbox, outbox_id)
            status = current.status if current is not None else EmailStatus.FAILED
            return DeliveryResult(
                outbox_id,
                status,
                current.attempts if current is not None else attempts,
                current.last_error if current is not None else last_code,
            )
