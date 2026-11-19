from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.models import Department


async def list_departments(session: AsyncSession) -> list[Department]:
    # Trả cả phòng đã ngừng hoạt động để tin cũ vẫn hiển thị được phòng đã chọn.
    # Frontend chỉ cho chọn phòng đang hoạt động khi tạo tin mới.
    return list((await session.scalars(select(Department).order_by(Department.name))).all())


async def get_by_id(session: AsyncSession, department_id: int) -> Department | None:
    return await session.get(Department, department_id)
