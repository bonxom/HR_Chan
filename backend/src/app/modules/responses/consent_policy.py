from types import MappingProxyType

from app.core.exceptions import AppError

POLICIES = MappingProxyType(
    {
        "talent-pool-v1": (
            "Tôi đồng ý để công ty lưu hồ sơ của tôi trong {months} tháng "
            "để liên hệ khi có vị trí tuyển dụng phù hợp."
        )
    }
)


def policy_text(version: str, months: int) -> str:
    template = POLICIES.get(version)
    if template is None:
        raise AppError("Không tải được nội dung chính sách", 503, "consent_policy_unavailable")
    return template.format(months=months)
