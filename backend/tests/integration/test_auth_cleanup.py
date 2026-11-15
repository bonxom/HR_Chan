import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.cli import cleanup_auth
from app.core.config import Settings
from app.modules.accounts.rules import AccountType
from app.modules.accounts.service import create_account

pytestmark = pytest.mark.database

NOW = datetime.now(UTC)


async def seed(settings: Settings, session_factory) -> dict[str, uuid.UUID]:
    async with session_factory() as session:
        result = await create_account(
            session,
            actor_id=None,
            full_name="Cleanup Target",
            email="cleanup@sis.hust.edu.vn",
            account_type=AccountType.EMPLOYEE,
            roles=["HR"],
            settings=settings,
            email_client=None,
        )
    account_id = result.account.id

    ids = {
        "expired_limit": uuid.uuid4(),
        "live_limit": uuid.uuid4(),
        "expired_link": uuid.uuid4(),
        "consumed_link": uuid.uuid4(),
        "live_link": uuid.uuid4(),
        "expired_session": uuid.uuid4(),
        "live_session": uuid.uuid4(),
    }
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO auth_rate_limits"
                " (key, count, window_started_at, updated_at, expires_at)"
                " VALUES (:key, 3, :now, :now, :expires_at)"
            ),
            [
                {
                    "key": "login-account:expired",
                    "now": NOW - timedelta(days=2),
                    "expires_at": NOW - timedelta(days=1),
                },
                {
                    "key": "login-account:live",
                    "now": NOW,
                    "expires_at": NOW + timedelta(hours=1),
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO auth_password_links"
                " (id, account_id, purpose, token_hash, created_at, expires_at,"
                " consumed_at, invalidated_at)"
                " VALUES (:id, :account_id, 'INVITATION', :token_hash, :created_at,"
                " :expires_at, :consumed_at, NULL)"
            ),
            [
                {
                    "id": ids["expired_link"],
                    "account_id": account_id,
                    "token_hash": "a" * 64,
                    "created_at": NOW - timedelta(days=3),
                    "expires_at": NOW - timedelta(days=1),
                    "consumed_at": None,
                },
                {
                    "id": ids["consumed_link"],
                    "account_id": account_id,
                    "token_hash": "b" * 64,
                    "created_at": NOW - timedelta(days=3),
                    "expires_at": NOW - timedelta(hours=30),
                    "consumed_at": NOW - timedelta(days=2),
                },
                {
                    "id": ids["live_link"],
                    "account_id": account_id,
                    "token_hash": "c" * 64,
                    "created_at": NOW,
                    "expires_at": NOW + timedelta(hours=1),
                    "consumed_at": None,
                },
            ],
        )
        session_rows = [
            {
                "id": ids["expired_session"],
                "absolute_expires_at": NOW - timedelta(days=1),
            },
            {
                "id": ids["live_session"],
                "absolute_expires_at": NOW + timedelta(hours=1),
            },
        ]
        for row in session_rows:
            await session.execute(
                text(
                    "INSERT INTO auth_sessions (id, account_id, credential_version,"
                    " created_at, last_activity_at, absolute_expires_at)"
                    " VALUES (:id, :account_id, 0, :now, :now, :absolute_expires_at)"
                ),
                {**row, "account_id": account_id, "now": NOW},
            )
        await session.execute(
            text(
                "INSERT INTO auth_refresh_tokens"
                " (id, session_id, token_hash, issued_at, expires_at, consumed_at)"
                " VALUES (:id, :session_id, :token_hash, :issued_at, :expires_at, NULL)"
            ),
            [
                {
                    "id": uuid.uuid4(),
                    "session_id": ids["expired_session"],
                    "token_hash": "d" * 64,
                    "issued_at": NOW - timedelta(days=2),
                    "expires_at": NOW - timedelta(days=1),
                },
                {
                    "id": uuid.uuid4(),
                    "session_id": ids["live_session"],
                    "token_hash": "e" * 64,
                    "issued_at": NOW - timedelta(minutes=5),
                    "expires_at": NOW + timedelta(hours=12),
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO audit_events (id, action, outcome, timestamp, metadata)"
                " VALUES (:id, 'account.created', 'SUCCESS', :now, '{}'::jsonb)"
            ),
            {"id": uuid.uuid4(), "now": NOW},
        )
        await session.commit()
    return ids


async def test_cleanup_removes_only_expired_auth_records(
    clean_database, session_factory, settings
) -> None:
    await seed(settings, session_factory)
    async with session_factory() as session:
        audit_before = await session.scalar(text("SELECT count(*) FROM audit_events"))

    removed = await cleanup_auth(session_factory, batch_size=100)
    assert removed["rate_limits"] == 1
    assert removed["expired_links"] == 1
    assert removed["retired_links"] == 1
    assert removed["refresh_tokens"] == 1

    async with session_factory() as session:
        keys = (await session.execute(text("SELECT key FROM auth_rate_limits"))).scalars().all()
        link_hashes = (
            (await session.execute(text("SELECT token_hash FROM auth_password_links")))
            .scalars()
            .all()
        )
        token_hashes = (
            (await session.execute(text("SELECT token_hash FROM auth_refresh_tokens")))
            .scalars()
            .all()
        )
        sessions = (await session.execute(text("SELECT count(*) FROM auth_sessions"))).scalar()
        accounts = (await session.execute(text("SELECT count(*) FROM accounts"))).scalar()
        audit = (await session.execute(text("SELECT count(*) FROM audit_events"))).scalar()

    assert keys == ["login-account:live"]
    assert "c" * 64 in link_hashes
    assert "a" * 64 not in link_hashes
    assert "b" * 64 not in link_hashes
    assert token_hashes == ["e" * 64]
    assert sessions == 2
    assert accounts == 1
    assert audit == audit_before


async def test_cleanup_respects_the_batch_size(clean_database, session_factory, settings) -> None:
    await seed(settings, session_factory)
    totals = {"rate_limits": 0, "expired_links": 0, "retired_links": 0, "refresh_tokens": 0}
    for _ in range(8):
        removed = await cleanup_auth(session_factory, batch_size=1)
        for key, value in removed.items():
            assert value <= 1
            totals[key] += value
        if not any(removed.values()):
            break
    assert totals == {
        "rate_limits": 1,
        "expired_links": 1,
        "retired_links": 1,
        "refresh_tokens": 1,
    }
