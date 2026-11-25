import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


ACTIVE = "status IN ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED')"


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    interviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"), server_default="SCHEDULED"
    )
    google_event_id: Mapped[str | None] = mapped_column(String(200))
    meet_link: Mapped[str | None] = mapped_column(String(300))
    auto_scheduled: Mapped[bool] = mapped_column(Boolean)
    reschedule_note: Mapped[str | None] = mapped_column(String(500))
    needs_manual_calendar_fix: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    decline_reason: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="interviews_time_order"),
        CheckConstraint(
            "auto_scheduled OR created_by IS NOT NULL", name="interviews_creator_required"
        ),
        CheckConstraint(
            "status <> 'RESCHEDULE_REQUESTED' OR length(trim(coalesce(reschedule_note,''))) > 0",
            name="interviews_reschedule_note_required",
        ),
        CheckConstraint(
            "decline_reason IS NULL OR status = 'CANCELLED'",
            name="interviews_decline_only_cancelled",
        ),
        ExcludeConstraint(
            ("interviewer_id", "="),
            (func.tstzrange(start_at, end_at), "&&"),
            where=text(ACTIVE),
            using="gist",
            name="interviews_no_overlap",
        ),
        Index(
            "interviews_one_active", "application_id", unique=True, postgresql_where=text(ACTIVE)
        ),
    )


class ProbationOffer(Base):
    __tablename__ = "probation_offers"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    start_date: Mapped[date] = mapped_column(Date)
    duration_days: Mapped[int] = mapped_column(SmallInteger)
    location: Mapped[str] = mapped_column(String(200))
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decline_reason: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("application_id", name="probation_offers_application_id_key"),
        CheckConstraint(
            "duration_days BETWEEN 1 AND 180", name="probation_offers_duration_days_check"
        ),
    )
