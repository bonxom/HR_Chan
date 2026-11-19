from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import CIText

EMBEDDING_DIMENSIONS = 1536


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"


class ParseStatus(StrEnum):
    PENDING = "PENDING"
    PARSED = "PARSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Candidate(Base):
    """Candidate without an account, identified by an OTP-verified email (context 02).

    CHECK constraints (phone format) live in migration 0005.
    """

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(CIText(), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("email", name="candidates_email_key"),)


class CvSubmission(Base):
    """One CV upload with consent; deleted after 24 h unless used by an application."""

    __tablename__ = "cv_submissions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidates.id", name="cv_submissions_candidate_id_fkey"),
        nullable=False,
    )
    cv_storage_key: Mapped[str] = mapped_column(String(100), nullable=False)
    cv_original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cv_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    cv_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    cv_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    cv_scan_status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status"), nullable=False
    )
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_policy_ver: Mapped[str] = mapped_column(String(20), nullable=False)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), nullable=False
    )
    parsed_data: Mapped[Any | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    suggestions: Mapped[Any | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("cv_storage_key", name="cv_submissions_cv_storage_key_key"),
        Index("cv_submissions_expiry_idx", "expires_at"),
    )
