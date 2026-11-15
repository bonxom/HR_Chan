import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.modules.auth.rate_limits import LimitRule, check, clear, consume
from app.modules.auth.tokens import limiter_identifier

pytestmark = pytest.mark.database

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
SECRET = b"limiter-hmac-secret-for-tests-0123456789"
FAILURE_RULE = LimitRule(max_attempts=5, window_seconds=900, block_seconds=900)
COOLDOWN_RULE = LimitRule(max_attempts=1, window_seconds=60)


def key_for(namespace: str = "login-account", value: str = "user@sis.hust.edu.vn") -> str:
    return limiter_identifier(SECRET, namespace, value)


async def test_allows_failures_up_to_the_limit_then_blocks(db_session) -> None:
    key = key_for()
    for offset in range(5):
        decision = await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
        assert decision.allowed

    blocked = await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=10))
    assert blocked.allowed is False
    assert blocked.retry_after == 900
    await db_session.commit()


async def test_block_expires_and_counters_reset(db_session) -> None:
    key = key_for()
    for offset in range(6):
        await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
    blocked_until = NOW + timedelta(seconds=905)
    assert (
        await consume(db_session, key, FAILURE_RULE, blocked_until - timedelta(seconds=1))
    ).allowed is False

    after_block = blocked_until + timedelta(seconds=1)
    assert (await consume(db_session, key, FAILURE_RULE, after_block)).allowed is True


async def test_window_expiry_resets_counters_without_a_block(db_session) -> None:
    rule = LimitRule(max_attempts=5, window_seconds=60)
    key = key_for("login-ip", "203.0.113.10")
    for offset in range(5):
        assert (await consume(db_session, key, rule, NOW + timedelta(seconds=offset))).allowed
    denied = await consume(db_session, key, rule, NOW + timedelta(seconds=5))
    assert denied.allowed is False
    assert denied.retry_after is not None and denied.retry_after <= 60
    assert (await consume(db_session, key, rule, NOW + timedelta(seconds=61))).allowed


async def test_cooldown_rule_enforces_minimum_gap(db_session) -> None:
    key = key_for("email-account", "user@sis.hust.edu.vn")
    assert (await consume(db_session, key, COOLDOWN_RULE, NOW)).allowed
    denied = await consume(db_session, key, COOLDOWN_RULE, NOW + timedelta(seconds=30))
    assert denied.allowed is False
    assert denied.retry_after == 30
    assert (await consume(db_session, key, COOLDOWN_RULE, NOW + timedelta(seconds=60))).allowed


async def test_check_reports_an_active_block_without_counting(db_session) -> None:
    key = key_for()
    assert (await check(db_session, key, FAILURE_RULE, NOW)).allowed
    for offset in range(6):
        await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
    await db_session.commit()

    blocked = await check(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=30))
    assert blocked.allowed is False
    assert blocked.retry_after is not None
    assert 860 <= blocked.retry_after <= 880


async def test_check_denies_once_the_window_is_full(db_session) -> None:
    key = key_for()
    for offset in range(5):
        await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
    await db_session.commit()

    assert (
        await check(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=10))
    ).allowed is False
    assert (
        await check(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=901))
    ).allowed is True


async def test_clear_removes_the_counter(db_session) -> None:
    key = key_for()
    for offset in range(6):
        await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
    await clear(db_session, key)
    assert (await consume(db_session, key, FAILURE_RULE, NOW + timedelta(seconds=60))).allowed


async def test_state_is_shared_across_independent_sessions(clean_database, session_factory) -> None:
    key = key_for()
    for offset in range(3):
        async with session_factory() as worker:
            assert (
                await consume(worker, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
            ).allowed
            await worker.commit()
    async with session_factory() as other_worker:
        for offset in range(3, 5):
            assert (
                await consume(other_worker, key, FAILURE_RULE, NOW + timedelta(seconds=offset))
            ).allowed
        await other_worker.commit()
        assert (
            await consume(other_worker, key, FAILURE_RULE, NOW + timedelta(seconds=6))
        ).allowed is False


async def test_simultaneous_attempts_are_counted_exactly_once_each(
    clean_database, session_factory
) -> None:
    key = key_for()

    async def attempt() -> bool:
        async with session_factory() as worker:
            decision = await consume(worker, key, FAILURE_RULE, NOW)
            await worker.commit()
            return decision.allowed

    results = await asyncio.gather(*(attempt() for _ in range(10)))
    assert results.count(True) == 5
    assert results.count(False) == 5

    async with session_factory() as reader:
        # Blocked attempts leave the counter unchanged once the block is active.
        assert (
            await reader.scalar(
                text("SELECT count FROM auth_rate_limits WHERE key = :key"), {"key": key}
            )
            == 6
        )
        expires_at = await reader.scalar(
            text("SELECT expires_at FROM auth_rate_limits WHERE key = :key"), {"key": key}
        )
    assert expires_at <= NOW + timedelta(seconds=900 + 60)


async def test_stored_keys_do_not_reveal_identifiers(db_session) -> None:
    raw = "person@sis.hust.edu.vn"
    await consume(db_session, key_for(value=raw), FAILURE_RULE, NOW)
    await db_session.commit()
    stored = await db_session.scalar(text("SELECT key FROM auth_rate_limits"))
    assert raw not in stored
    assert stored.startswith("login-account:")
