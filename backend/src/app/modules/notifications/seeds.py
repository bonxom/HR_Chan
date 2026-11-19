"""Idempotent default email templates.

Only missing codes are inserted; a template an Admin already edited is never
overwritten. Every required variable appears in the body (trigger
``trg_template_required_vars`` checks it again in the database).
"""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import EmailTemplate
from app.modules.notifications.schemas import TemplateCode


@dataclass(frozen=True)
class TemplateSeed:
    code: TemplateCode
    subject: str
    body: str
    required_vars: tuple[str, ...]


TEMPLATE_SEEDS: tuple[TemplateSeed, ...] = (
    TemplateSeed(
        TemplateCode.OTP_APPLY,
        "Mã xác thực nộp hồ sơ – {job_title}",
        "Xin chào {full_name},\n\n"
        "Mã xác thực để nộp hồ sơ vào vị trí {job_title} là: {otp_code}\n"
        "Mã có hiệu lực trong {ttl_minutes} phút. Không chia sẻ mã này với bất kỳ ai.\n\n"
        "Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua email.",
        ("full_name", "otp_code", "ttl_minutes", "job_title"),
    ),
    TemplateSeed(
        TemplateCode.ACCOUNT_INVITATION,
        "Kích hoạt tài khoản HR Chan",
        "Xin chào {full_name},\n\n"
        "Một tài khoản HR Chan đã được tạo cho bạn. Hãy đặt mật khẩu trong vòng "
        "{ttl_hours} giờ tại liên kết sau:\n\n{set_password_url}\n\n"
        "Nếu bạn không mong đợi email này, hãy bỏ qua.",
        ("full_name", "set_password_url", "ttl_hours"),
    ),
    TemplateSeed(
        TemplateCode.PASSWORD_RECOVERY,
        "Đặt lại mật khẩu HR Chan",
        "Xin chào {full_name},\n\n"
        "Dùng liên kết dưới đây trong vòng {ttl_minutes} phút để đặt mật khẩu mới:\n\n"
        "{set_password_url}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email; mật khẩu hiện tại không thay đổi.",
        ("full_name", "set_password_url", "ttl_minutes"),
    ),
    TemplateSeed(
        TemplateCode.EMAIL_DELIVERY_FAILED,
        "[Nội bộ] Gửi email thất bại – hồ sơ #{application_id}",
        "[Thông báo nội bộ của hệ thống]\n\n"
        "Email mẫu {failed_template} gửi cho hồ sơ #{application_id} đã thất bại "
        "(mã lỗi: {error_code}).\n"
        "Hồ sơ đã được gắn cờ lỗi email; vui lòng kiểm tra và liên hệ ứng viên nếu cần.",
        ("application_id", "failed_template", "error_code"),
    ),
)


async def seed_email_templates(session: AsyncSession) -> int:
    """Insert missing templates in the caller's transaction; return how many were added."""
    inserted = 0
    for seed in TEMPLATE_SEEDS:
        result = await session.execute(
            insert(EmailTemplate)
            .values(
                code=seed.code.value,
                subject=seed.subject,
                body=seed.body,
                required_vars=list(seed.required_vars),
                updated_at=func.now(),
            )
            .on_conflict_do_nothing(index_elements=["code"])
            .returning(EmailTemplate.code)
        )
        if result.scalar_one_or_none() is not None:
            inserted += 1
    return inserted
