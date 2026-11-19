import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Bảng được tham chiếu bằng FK; chỉ import model.
from app.modules.accounts import models as _account_models  # noqa: F401
from app.modules.candidates import models as _candidate_models  # noqa: F401
from app.modules.recruitment import models as _recruitment_models  # noqa: F401


class ApplicationStatus(StrEnum):
    SCORING = "SCORING"
    PENDING_HR_REVIEW = "PENDING_HR_REVIEW"
    INTERVIEW_INVITED = "INTERVIEW_INVITED"
    INTERVIEW_CONFIRMED = "INTERVIEW_CONFIRMED"
    INTERVIEW_DECLINED = "INTERVIEW_DECLINED"
    AWAITING_INTERVIEW_RESULT = "AWAITING_INTERVIEW_RESULT"
    INTERVIEW_PASSED = "INTERVIEW_PASSED"
    INTERVIEW_FAILED = "INTERVIEW_FAILED"
    REJECTED = "REJECTED"
    AWAITING_ACCOUNT = "AWAITING_ACCOUNT"
    ON_PROBATION = "ON_PROBATION"
    PROBATION_DECLINED = "PROBATION_DECLINED"
    PROBATION_PASSED = "PROBATION_PASSED"
    PROBATION_FAILED = "PROBATION_FAILED"


class AiScoreStatus(StrEnum):
    PENDING = "PENDING"
    SCORED = "SCORED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


EMAIL_ISSUE_MAX = 100


class Application(Base):
    """One candidate applying to one posting after OTP verification (context 02).

    CHECK constraints and the ``applications_history`` trigger (status history written to
    ``audit_events``) live in migration 0005. ``decided_by`` references ``accounts.id``.
    No FK here cascades: a posting, CV or candidate with applications cannot be deleted.
    """

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidates.id", name="applications_candidate_id_fkey"),
        nullable=False,
    )
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("job_postings.id", name="applications_job_id_fkey"),
        nullable=False,
    )
    submission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cv_submissions.id", name="applications_submission_id_fkey"),
        nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    criteria_set_id: Mapped[int | None] = mapped_column(BigInteger)
    ai_status: Mapped[AiScoreStatus] = mapped_column(
        Enum(AiScoreStatus, name="ai_score_status"), nullable=False
    )
    ai_total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ai_failure_reason: Mapped[str | None] = mapped_column(Text)
    hr_note: Mapped[str | None] = mapped_column(Text)
    email_issue: Mapped[str | None] = mapped_column(String(EMAIL_ISSUE_MAX))
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", name="applications_decided_by_fkey")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason_code: Mapped[str | None] = mapped_column(String(40))
    reject_reason_text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        # Bộ tiêu chí phải thuộc đúng tin của hồ sơ (FK ghép criteria_set_id + job_id).
        ForeignKeyConstraint(
            ["criteria_set_id", "job_id"],
            ["criteria_sets.id", "criteria_sets.job_id"],
            name="applications_criteria_set_fk",
        ),
        UniqueConstraint("candidate_id", "job_id", name="applications_candidate_id_job_id_key"),
        Index("applications_job_idx", "job_id", "status"),
        Index("applications_status_idx", "status", "submitted_at"),
    )
