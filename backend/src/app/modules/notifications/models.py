import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import CIText

# Đăng ký bảng được tham chiếu bằng FK để flush/metadata luôn phân giải được
# (chỉ import model, không import service để tránh vòng phụ thuộc).
from app.modules.accounts import models as _account_models  # noqa: F401
from app.modules.applications import models as _application_models  # noqa: F401


class EmailStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


MAX_ATTEMPTS = 4  # lần đầu + tối đa 3 lần thử lại (BR11)
SUBJECT_MAX = 255


class EmailTemplate(Base):
    """System email template; trigger ``email_templates_vars`` keeps required variables."""

    __tablename__ = "email_templates"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    subject: Mapped[str] = mapped_column(String(SUBJECT_MAX), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    required_vars: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", name="email_templates_updated_by_fkey")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EmailOutbox(Base):
    """Outgoing mail written in the business transaction (context 02 ``email_outbox``).

    ``body`` holds a versioned internal envelope while PENDING (see ``payloads``) and a
    redacted copy once SENT/FAILED. CHECK constraints live in migration 0005.
    """

    __tablename__ = "email_outbox"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    template_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("email_templates.code", name="email_outbox_template_code_fkey"),
        nullable=False,
    )
    to_email: Mapped[str] = mapped_column(CIText(), nullable=False)
    subject: Mapped[str] = mapped_column(String(SUBJECT_MAX), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    application_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("applications.id", name="email_outbox_application_id_fkey")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", name="email_outbox_user_id_fkey")
    )
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status"),
        nullable=False,
        server_default=EmailStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_email_outbox_application",
            "application_id",
            postgresql_where="application_id IS NOT NULL",
        ),
        Index(
            "ix_email_outbox_due",
            "next_attempt_at",
            postgresql_where="status = 'PENDING'::email_status",
        ),
    )
