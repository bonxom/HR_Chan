"""Notification contracts shared with callers."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.modules.notifications.models import EmailStatus


class TemplateCode(StrEnum):
    # Đã seed ở bước này.
    OTP_APPLY = "OTP_APPLY"
    ACCOUNT_INVITATION = "ACCOUNT_INVITATION"
    PASSWORD_RECOVERY = "PASSWORD_RECOVERY"
    EMAIL_DELIVERY_FAILED = "EMAIL_DELIVERY_FAILED"
    INTERVIEW_INVITE = "INTERVIEW_INVITE"
    REJECT_THANK_YOU = "REJECT_THANK_YOU"
    REVIEW_OVERDUE_DIGEST = "REVIEW_OVERDUE_DIGEST"
    INTERVIEW_RESPONSE_HR = "INTERVIEW_RESPONSE_HR"
    RESPONSE_EXPIRED_CANDIDATE = "RESPONSE_EXPIRED_CANDIDATE"
    RESPONSE_EXPIRED_HR = "RESPONSE_EXPIRED_HR"
    CALENDAR_SYNC_REQUIRED_HR = "CALENDAR_SYNC_REQUIRED_HR"
    # Chỉ dành tên mã cho chức năng sau (thư mời phỏng vấn, cảm ơn, thử việc);
    # chưa có nội dung nên không seed.
    INTERVIEW_INVITATION = "INTERVIEW_INVITATION"
    THANK_YOU = "THANK_YOU"
    PROBATION_OFFER = "PROBATION_OFFER"


# Biến luôn bí mật theo mẫu, bất kể caller có khai báo secret_vars hay không: mã OTP
# không bao giờ được lưu rõ (NFR22). Token khác vẫn do caller chỉ định secret_vars.
TEMPLATE_SECRET_VARS: dict[str, frozenset[str]] = {
    TemplateCode.OTP_APPLY.value: frozenset({"otp_code"}),
    TemplateCode.INTERVIEW_INVITE.value: frozenset({"confirm_url"}),
    TemplateCode.REJECT_THANK_YOU.value: frozenset({"consent_url"}),
}


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of ``sendNow``; never carries message content or secrets."""

    outbox_id: int
    status: EmailStatus
    attempts: int
    error_code: str | None


@dataclass(frozen=True)
class HrRecipient:
    account_id: uuid.UUID
    email: str
