"""PostgreSQL-backed rate limiting shared by every backend worker.

Each limiter key holds an unguessable HMAC digest so raw emails and IP addresses
are never stored. Counter updates use one atomic upsert, which serializes
concurrent attempts on the same key.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

RETENTION_SLACK_SECONDS = 60

UPSERT = text(
    """
    INSERT INTO auth_rate_limits AS limits
        (key, count, window_started_at, blocked_until, updated_at, expires_at)
    VALUES (:key, 1, :now, NULL, :now, :expires_at)
    ON CONFLICT (key) DO UPDATE SET
        count = CASE
            WHEN limits.blocked_until IS NOT NULL AND limits.blocked_until > :now
                THEN limits.count
            WHEN limits.window_started_at <= :window_start THEN 1
            ELSE limits.count + 1
        END,
        window_started_at = CASE
            WHEN limits.blocked_until IS NOT NULL AND limits.blocked_until > :now
                THEN limits.window_started_at
            WHEN limits.window_started_at <= :window_start THEN :now
            ELSE limits.window_started_at
        END,
        blocked_until = CASE
            WHEN limits.blocked_until IS NOT NULL AND limits.blocked_until > :now
                THEN limits.blocked_until
            WHEN limits.window_started_at <= :window_start THEN NULL
            WHEN limits.count + 1 > :max_attempts THEN :block_until
            ELSE NULL
        END,
        updated_at = :now,
        expires_at = GREATEST(limits.expires_at, :expires_at)
    RETURNING count AS attempt_count, window_started_at, blocked_until
    """
)

SELECT_STATUS = text(
    "SELECT count AS attempt_count, window_started_at, blocked_until "
    "FROM auth_rate_limits WHERE key = :key"
)


@dataclass(frozen=True)
class LimitRule:
    max_attempts: int
    window_seconds: int
    block_seconds: int = 0


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    retry_after: int | None = None

    @property
    def blocked(self) -> bool:
        return not self.allowed


def _retry_seconds(target: datetime, now: datetime) -> int:
    return max(1, math.ceil((target - now).total_seconds()))


async def check(session: AsyncSession, key: str, rule: LimitRule, now: datetime) -> LimitDecision:
    """Deny when the window already holds the maximum attempts, without counting."""
    row = (await session.execute(SELECT_STATUS, {"key": key})).one_or_none()
    if row is None:
        return LimitDecision(allowed=True)
    if row.blocked_until is not None and row.blocked_until > now:
        return LimitDecision(allowed=False, retry_after=_retry_seconds(row.blocked_until, now))
    window_ends = row.window_started_at + timedelta(seconds=rule.window_seconds)
    if row.attempt_count >= rule.max_attempts and window_ends > now:
        return LimitDecision(allowed=False, retry_after=_retry_seconds(window_ends, now))
    return LimitDecision(allowed=True)


async def consume(session: AsyncSession, key: str, rule: LimitRule, now: datetime) -> LimitDecision:
    """Atomically count one attempt for ``key`` and report whether it may proceed."""
    block_until = now + timedelta(seconds=rule.block_seconds)
    retention = now + timedelta(
        seconds=max(rule.window_seconds, rule.block_seconds) + RETENTION_SLACK_SECONDS
    )
    row = (
        await session.execute(
            UPSERT,
            {
                "key": key,
                "now": now,
                "window_start": now - timedelta(seconds=rule.window_seconds),
                "max_attempts": rule.max_attempts,
                "block_until": block_until,
                "expires_at": retention,
            },
        )
    ).one()

    attempt_count: int = row.attempt_count
    blocked_until: datetime | None = row.blocked_until
    window_started_at: datetime = row.window_started_at

    if blocked_until is not None and blocked_until > now:
        return LimitDecision(allowed=False, retry_after=_retry_seconds(blocked_until, now))
    if attempt_count > rule.max_attempts:
        window_ends = window_started_at + timedelta(seconds=rule.window_seconds)
        return LimitDecision(allowed=False, retry_after=_retry_seconds(window_ends, now))
    return LimitDecision(allowed=True)


async def clear(session: AsyncSession, key: str) -> None:
    await session.execute(text("DELETE FROM auth_rate_limits WHERE key = :key"), {"key": key})
