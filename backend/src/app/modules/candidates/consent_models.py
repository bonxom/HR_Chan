from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsentSource(StrEnum):
    NO_MATCH_SCREEN = "NO_MATCH_SCREEN"
    THANK_YOU_LINK = "THANK_YOU_LINK"


class TalentPoolConsent(Base):
    __tablename__ = "talent_pool_consents"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    source: Mapped[ConsentSource] = mapped_column(Enum(ConsentSource, name="consent_source"))
    policy_ver: Mapped[str] = mapped_column(String(20))
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("expires_at > consented_at", name="talent_pool_expiry"),
        Index(
            "talent_pool_one_active",
            "candidate_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
