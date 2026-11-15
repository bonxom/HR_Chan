"""Password link lifecycle: creation, quota, and single-use completion."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.accounts.rules import AccountStatus
from app.modules.auth.models import AuthPasswordLink, PasswordLinkPurpose
from app.modules.auth.rate_limits import LimitRule, consume
from app.modules.auth.tokens import generate_opaque_token, hash_opaque_token, limiter_identifier

HOUR_SECONDS = 3600


def link_ttl_seconds(purpose: PasswordLinkPurpose, settings: Settings) -> int:
    if purpose is PasswordLinkPurpose.INVITATION:
        return settings.invitation_ttl_seconds
    return settings.recovery_ttl_seconds


def purpose_for_status(status: AccountStatus) -> PasswordLinkPurpose:
    if status is AccountStatus.PENDING_SETUP:
        return PasswordLinkPurpose.INVITATION
    return PasswordLinkPurpose.RECOVERY


async def create_link(
    session: AsyncSession,
    account_id: uuid.UUID,
    purpose: PasswordLinkPurpose,
    *,
    settings: Settings,
    now: datetime,
) -> tuple[AuthPasswordLink, str]:
    token = generate_opaque_token()
    link = AuthPasswordLink(
        account_id=account_id,
        purpose=purpose,
        token_hash=hash_opaque_token(token),
        created_at=now,
        expires_at=now + timedelta(seconds=link_ttl_seconds(purpose, settings)),
    )
    session.add(link)
    await session.flush()
    return link, token


async def lock_link(session: AsyncSession, token: str) -> AuthPasswordLink | None:
    return await session.scalar(
        select(AuthPasswordLink)
        .where(AuthPasswordLink.token_hash == hash_opaque_token(token))
        .with_for_update()
    )


async def peek_link_account_id(session: AsyncSession, token: str) -> uuid.UUID | None:
    return await session.scalar(
        select(AuthPasswordLink.account_id).where(
            AuthPasswordLink.token_hash == hash_opaque_token(token)
        )
    )


def link_is_usable(link: AuthPasswordLink, now: datetime) -> bool:
    return link.consumed_at is None and link.invalidated_at is None and link.expires_at > now


async def invalidate_outstanding(
    session: AsyncSession,
    account_id: uuid.UUID,
    *,
    now: datetime,
    keep_id: uuid.UUID | None = None,
) -> None:
    statement = update(AuthPasswordLink).where(
        AuthPasswordLink.account_id == account_id,
        AuthPasswordLink.consumed_at.is_(None),
        AuthPasswordLink.invalidated_at.is_(None),
    )
    if keep_id is not None:
        statement = statement.where(AuthPasswordLink.id != keep_id)
    await session.execute(statement.values(invalidated_at=now))


async def reserve_email_quota(
    session: AsyncSession, account_id: uuid.UUID, *, settings: Settings, now: datetime
) -> int | None:
    """Return retry seconds when the account may not receive another email."""
    secret = settings.require_limiter_secret()
    key = limiter_identifier(secret, "email", str(account_id))
    cooldown = await consume(
        session,
        f"{key}:cooldown",
        LimitRule(
            max_attempts=1,
            window_seconds=settings.email_min_interval_seconds,
        ),
        now,
    )
    if cooldown.blocked:
        return cooldown.retry_after
    hourly = await consume(
        session,
        f"{key}:hourly",
        LimitRule(max_attempts=settings.email_hourly_limit, window_seconds=HOUR_SECONDS),
        now,
    )
    if hourly.blocked:
        return hourly.retry_after
    return None
