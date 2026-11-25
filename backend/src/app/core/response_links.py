"""Single-use response links. Callers own the transaction."""

import hashlib
import secrets
from dataclasses import dataclass, field
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
    Text,
    UniqueConstraint,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.core.exceptions import AppError
from app.db.base import Base
from app.modules.interviews import models as _interview_models  # noqa: F401


class LinkPurpose(StrEnum):
    CONFIRM_INTERVIEW = "CONFIRM_INTERVIEW"
    PROBATION_OFFER = "PROBATION_OFFER"
    TALENT_POOL_CONSENT = "TALENT_POOL_CONSENT"


class LinkOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    EXPIRED = "EXPIRED"


class ResponseLink(Base):
    __tablename__ = "response_links"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    token_hash: Mapped[str] = mapped_column(Text)
    purpose: Mapped[LinkPurpose] = mapped_column(Enum(LinkPurpose, name="link_purpose"))
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    interview_id: Mapped[int | None] = mapped_column(ForeignKey("interviews.id"))
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("probation_offers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[LinkOutcome | None] = mapped_column(Enum(LinkOutcome, name="link_outcome"))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("token_hash", name="response_links_token_hash_key"),
        CheckConstraint("expires_at > created_at", name="response_links_expiry"),
        CheckConstraint("(used_at IS NULL) = (outcome IS NULL)", name="response_links_used_pair"),
        CheckConstraint(
            "invalidated_at IS NULL OR used_at IS NULL", name="response_links_not_used_and_invalid"
        ),
        CheckConstraint(
            "(purpose='CONFIRM_INTERVIEW' AND interview_id IS NOT NULL AND offer_id IS NULL)"
            " OR (purpose='PROBATION_OFFER' AND offer_id IS NOT NULL AND interview_id IS NULL)"
            " OR (purpose='TALENT_POOL_CONSENT' AND interview_id IS NULL AND offer_id IS NULL)",
            name="response_links_purpose_refs",
        ),
        CheckConstraint(
            "outcome IS DISTINCT FROM 'RESCHEDULE_REQUESTED' OR purpose='CONFIRM_INTERVIEW'",
            name="response_links_reschedule_only_interview",
        ),
        Index(
            "response_links_expiry_idx",
            "expires_at",
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )


@dataclass(frozen=True)
class IssuedLink:
    id: int
    url: str = field(repr=False)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def invalid_link():
    return AppError(
        "Đường dẫn không hợp lệ hoặc đã hết hạn", status_code=422, code="invalid_response_link"
    )


class ResponseLinkService:
    def __init__(self, session: AsyncSession, public_base_url: str):
        self.session = session
        self.base = public_base_url.rstrip("/")

    async def issue(
        self,
        *,
        purpose: LinkPurpose | str,
        application_id: int,
        expires_at: datetime,
        interview_id: int | None = None,
        offer_id: int | None = None,
        now: datetime | None = None,
    ) -> IssuedLink:
        now = now or clock.utcnow()
        purpose = LinkPurpose(purpose)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"response-link:{application_id}:{purpose.value}"},
        )
        await self.session.execute(
            update(ResponseLink)
            .where(
                ResponseLink.application_id == application_id,
                ResponseLink.purpose == purpose,
                ResponseLink.used_at.is_(None),
                ResponseLink.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        token = secrets.token_urlsafe(32)
        row = ResponseLink(
            token_hash=hash_token(token),
            purpose=purpose,
            application_id=application_id,
            interview_id=interview_id,
            offer_id=offer_id,
            created_at=now,
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return IssuedLink(row.id, f"{self.base}/r/{token}")

    async def verify(
        self,
        token: str,
        purpose: LinkPurpose | str | None = None,
        now: datetime | None = None,
    ) -> ResponseLink:
        now = now or clock.utcnow()
        row = await self.session.scalar(
            select(ResponseLink)
            .where(
                ResponseLink.token_hash == hash_token(token),
                ResponseLink.used_at.is_(None),
                ResponseLink.invalidated_at.is_(None),
                ResponseLink.expires_at > now,
            )
            .with_for_update()
        )
        if row is None or (purpose is not None and row.purpose != LinkPurpose(purpose)):
            raise invalid_link()
        return row

    async def mark_used(
        self,
        token: str,
        outcome: LinkOutcome | str,
        now: datetime | None = None,
    ) -> ResponseLink:
        now = now or clock.utcnow()
        row = await self.verify(token, now=now)
        outcome = LinkOutcome(outcome)
        if (
            outcome == LinkOutcome.RESCHEDULE_REQUESTED
            and row.purpose != LinkPurpose.CONFIRM_INTERVIEW
        ):
            raise invalid_link()
        row.used_at = now
        row.outcome = outcome
        await self.session.flush()
        return row

    async def invalidate(self, link_id: int, now: datetime | None = None) -> bool:
        result = await self.session.execute(
            update(ResponseLink)
            .where(
                ResponseLink.id == link_id,
                ResponseLink.used_at.is_(None),
                ResponseLink.invalidated_at.is_(None),
            )
            .values(invalidated_at=now or clock.utcnow())
        )
        return bool(result.rowcount)
