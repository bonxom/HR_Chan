from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import SystemSetting

AUTO_INVITE_THRESHOLD = "auto_invite_threshold"


async def get_numeric(session: AsyncSession, key: str) -> Decimal | None:
    # Trả None khi thiếu hàng/giá trị để service quyết định báo lỗi cấu hình.
    setting = await session.get(SystemSetting, key)
    return setting.value if setting is not None else None
