import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Holiday(Base):
    __tablename__ = "holidays"

    holiday_date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))


# Nguồn cấu hình dùng chung; ngưỡng mời phỏng vấn không được hard-code ở frontend.
class SystemSetting(Base):
    """Configurable parameter (deadline, threshold, working hours) with its allowed range."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    value_json: Mapped[Any | None] = mapped_column(JSONB)
    default_value: Mapped[Decimal | None] = mapped_column(Numeric)
    min_value: Mapped[Decimal | None] = mapped_column(Numeric)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", name="system_settings_updated_by_fkey"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
