import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Identity, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import CIText

# Bảng được tham chiếu bằng FK; chỉ import model, không import service/router nghiệp vụ.
from app.modules.accounts import models as _account_models  # noqa: F401
from app.modules.candidates import models as _candidate_models  # noqa: F401
from app.modules.recruitment import models as _recruitment_models  # noqa: F401


class OtpPurpose(StrEnum):
    APPLY = "APPLY"
    RESET_PASSWORD = "RESET_PASSWORD"


class OtpCode(Base):
    """A hashed one-time code bound to one purpose (context 02 ``otp_codes``).

    CHECK constraints (attempts 0..5, expiry, purpose references) live in migration 0005.
    The plain code is never stored. ``user_id`` references ``accounts.id`` (00 §4.11).
    """

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(CIText(), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(
        Enum(OtpPurpose, name="otp_purpose"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    submission_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cv_submissions.id", name="otp_codes_submission_id_fkey")
    )
    job_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("job_postings.id", name="otp_codes_job_id_fkey")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", name="otp_codes_user_id_fkey")
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)

    __table_args__ = (
        # Chỉ một mã còn hiệu lực cho mỗi email + mục đích; gửi lại phải vô hiệu mã cũ.
        Index(
            "otp_one_live_code",
            "email",
            "purpose",
            unique=True,
            postgresql_where="consumed_at IS NULL AND invalidated_at IS NULL",
        ),
        Index("otp_rate_idx", "email", "purpose", "created_at"),
    )
