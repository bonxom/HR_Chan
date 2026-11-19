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
    # Chỉ dành tên mã cho chức năng sau (thư mời phỏng vấn, cảm ơn, thử việc);
    # chưa có nội dung nên không seed.
    INTERVIEW_INVITATION = "INTERVIEW_INVITATION"
    THANK_YOU = "THANK_YOU"
    PROBATION_OFFER = "PROBATION_OFFER"


# Biến luôn bí mật theo mẫu, bất kể caller có khai báo secret_vars hay không: mã OTP
# không bao giờ được lưu rõ (NFR22). Token khác vẫn do caller chỉ định secret_vars.
TEMPLATE_SECRET_VARS: dict[str, frozenset[str]] = {
    TemplateCode.OTP_APPLY.value: frozenset({"otp_code"}),
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
