from sqlalchemy import BigInteger, Boolean, Identity, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Danh mục do hệ thống nhân sự cung cấp; phần tuyển dụng chỉ tham chiếu/chọn.
class Department(Base):
    """Company department, supplied by the larger HR system (read-only here)."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    __table_args__ = (UniqueConstraint("name", name="departments_name_key"),)
