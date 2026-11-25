import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
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
    false,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from app.db.base import Base

EMBEDDING_DIMENSIONS = 1536


class JobStatus(StrEnum):
    # DRAFT: đang soạn; OPEN: đã đăng; CLOSED: đã đóng và không mở lại tin cũ.
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class JobPosting(Base):
    """Job posting; only OPEN postings are shown to candidates and used for suggestions.

    CHECK constraints (job_closed_at, job_open_complete, lengths) live in migration 0003.
    """

    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", name="job_postings_department_id_fkey"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    benefits: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    headcount: Mapped[int | None] = mapped_column(Integer)
    work_mode: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, server_default=JobStatus.DRAFT.value
    )
    # Trỏ tới bản tiêu chí hiện hành; các bản cũ vẫn được giữ trong criteria_sets.
    current_criteria_set_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", name="job_postings_created_by_fkey"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        # Ghép thêm job ID để không thể trỏ nhầm bộ tiêu chí của tin khác.
        # FK vòng được kiểm tra cuối transaction, sau khi đã tạo đủ job và set.
        ForeignKeyConstraint(
            ["current_criteria_set_id", "id"],
            ["criteria_sets.id", "criteria_sets.job_id"],
            name="job_current_criteria_fk",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index("ix_job_postings_status_created", "status", "created_at"),
        Index(
            "ix_job_postings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where="status = 'OPEN'::job_status",
        ),
    )


class CriteriaSet(Base):
    """One saved version of a posting's scoring criteria."""

    __tablename__ = "criteria_sets"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Cascade chỉ dọn lịch sử khi xóa cả tin; trigger0004 chặn sửa/xóa set riêng lẻ.
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("job_postings.id", name="criteria_sets_job_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_invite_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", name="criteria_sets_created_by_fkey"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("id", "job_id", name="criteria_sets_id_job_id_key"),
        UniqueConstraint("job_id", "version_no", name="criteria_sets_job_id_version_no_key"),
    )


class Criterion(Base):
    """A single criterion; immutable once stored (enforced by a trigger)."""

    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Mỗi tiêu chí thuộc đúng một phiên bản; không sửa trực tiếp sau khi lưu.
    criteria_set_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("criteria_sets.id", name="criteria_criteria_set_id_fkey", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    min_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("criteria_set_id", "name", name="criteria_criteria_set_id_name_key"),
        CheckConstraint(
            "(is_mandatory AND min_score IS NOT NULL AND min_score BETWEEN 0 AND 100)"
            " OR (NOT is_mandatory AND min_score IS NULL)",
            name=conv("criteria_min_score_mandatory"),
        ),
    )


class JobInterviewer(Base):
    """Interviewer assigned to a posting."""

    __tablename__ = "job_interviewers"

    # Bảng nối phân công: xóa tin chỉ xóa liên kết, không xóa tài khoản nhân viên.
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("job_postings.id", name="job_interviewers_job_id_fkey", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", name="job_interviewers_user_id_fkey"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
