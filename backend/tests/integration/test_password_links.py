import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.exceptions import Failure
from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus, AccountType
from app.modules.accounts.service import (
    AccountDeliveryResult,
    complete_password_link,
    create_account,
    request_password_email,
)
from app.modules.auth.models import AuthSession
from app.modules.auth.passwords import verify_password

pytestmark = pytest.mark.database

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
ADMIN_ID = uuid.UUID("99999999-9999-4999-8999-999999999999")
CLIENT_IP = "198.51.100.25"


async def create_employee(
    session,
    settings: Settings,
    outbox,
    *,
    email: str = "employee@sis.hust.edu.vn",
    roles: list[str] | None = None,
    now: datetime = NOW,
) -> Account:
    result = await create_account(
        session,
        actor_id=ADMIN_ID,
        full_name="Nguyễn Văn Nhân Viên",
        email=email,
        account_type=AccountType.EMPLOYEE,
        roles=roles if roles is not None else ["HR"],
        settings=settings,
        email_client=outbox,
        now=now,
    )
    assert isinstance(result, AccountDeliveryResult), result
    assert result.email_delivery == "queued"
    await outbox.drain()  # worker thật gửi thư mời đã xếp hàng
    return result.account


async def request_and_drain(session, settings: Settings, outbox, *, email: str, now: datetime):
    outcome = await request_password_email(
        session,
        email=email,
        settings=settings,
        email_client=outbox,
        client_ip=CLIENT_IP,
        now=now,
    )
    await outbox.drain()
    return outcome


async def reload_account(session, account_id: uuid.UUID) -> Account:
    return await session.scalar(
        select(Account).where(Account.id == account_id).execution_options(populate_existing=True)
    )


async def add_session(session, account_id: uuid.UUID, now: datetime = NOW) -> AuthSession:
    row = AuthSession(
        account_id=account_id,
        credential_version=0,
        created_at=now,
        last_activity_at=now,
        absolute_expires_at=now + timedelta(hours=12),
    )
    session.add(row)
    await session.commit()
    return row


async def test_creation_invites_and_completion_activates(
    db_session, settings, email_outbox
) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    assert account.status is AccountStatus.PENDING_SETUP
    assert len(email_outbox.messages) == 1
    assert "employee@sis.hust.edu.vn" == account.email

    completed = await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="  mật khẩu an toàn  ",
        settings=settings,
        now=NOW + timedelta(minutes=5),
    )
    assert isinstance(completed, Account), completed
    assert completed.status is AccountStatus.ACTIVE
    assert verify_password("  mật khẩu an toàn  ", completed.password_hash)
    link = (
        await db_session.execute(
            text("SELECT consumed_at, invalidated_at FROM auth_password_links")
        )
    ).one()
    assert link.consumed_at is not None
    audit = await db_session.scalar(
        text("SELECT count(*) FROM audit_events WHERE action = 'auth.password.setup'")
    )
    assert audit == 1


async def test_completing_one_link_invalidates_every_other(
    db_session, settings, email_outbox
) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    first_token = email_outbox.last_token
    await request_and_drain(
        db_session, settings, email_outbox, email=account.email, now=NOW + timedelta(seconds=61)
    )
    second_token = email_outbox.last_token
    assert first_token != second_token

    completed = await complete_password_link(
        db_session,
        token=second_token,
        new_password="a-second-password",
        settings=settings,
        now=NOW + timedelta(seconds=90),
    )
    assert isinstance(completed, Account)
    reused = await complete_password_link(
        db_session,
        token=first_token,
        new_password="another-password",
        settings=settings,
        now=NOW + timedelta(seconds=95),
    )
    assert isinstance(reused, Failure)
    assert reused.status_code == 400
    assert reused.code == "invalid_password_link"


async def test_expired_link_is_rejected_with_the_safe_error(
    db_session, settings, email_outbox
) -> None:
    await create_employee(db_session, settings, email_outbox)
    result = await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="valid-password",
        settings=settings,
        now=NOW + timedelta(hours=25),
    )
    unknown = await complete_password_link(
        db_session,
        token="never-issued-token",
        new_password="valid-password",
        settings=settings,
        now=NOW,
    )
    assert isinstance(result, Failure) and isinstance(unknown, Failure)
    assert result.message == unknown.message
    assert result.status_code == unknown.status_code == 400


async def test_locked_and_disabled_accounts_cannot_complete_links(
    db_session, settings, email_outbox
) -> None:
    locked = await create_employee(
        db_session, settings, email_outbox, email="locked@sis.hust.edu.vn"
    )
    locked_token = email_outbox.last_token
    locked.status = AccountStatus.LOCKED
    await db_session.commit()
    assert isinstance(
        await complete_password_link(
            db_session,
            token=locked_token,
            new_password="valid-password",
            settings=settings,
            now=NOW,
        ),
        Failure,
    )

    disabled = await create_employee(
        db_session, settings, email_outbox, email="disabled@sis.hust.edu.vn"
    )
    disabled_token = email_outbox.last_token
    disabled.status = AccountStatus.DISABLED
    await db_session.commit()
    assert isinstance(
        await complete_password_link(
            db_session,
            token=disabled_token,
            new_password="valid-password",
            settings=settings,
            now=NOW,
        ),
        Failure,
    )


async def test_short_password_is_rejected_without_consuming_the_link(
    db_session, settings, email_outbox
) -> None:
    await create_employee(db_session, settings, email_outbox)
    token = email_outbox.last_token
    rejected = await complete_password_link(
        db_session, token=token, new_password="1234567", settings=settings, now=NOW
    )
    assert isinstance(rejected, Failure)
    assert rejected.code == "invalid_password"
    accepted = await complete_password_link(
        db_session, token=token, new_password="12345678", settings=settings, now=NOW
    )
    assert isinstance(accepted, Account)


async def test_public_recovery_is_generic_for_unknown_and_disallowed_addresses(
    db_session, settings, email_outbox
) -> None:
    unknown = await request_password_email(
        db_session,
        email="nobody@sis.hust.edu.vn",
        settings=settings,
        email_client=email_outbox,
        client_ip=CLIENT_IP,
        now=NOW,
    )
    disallowed = await request_password_email(
        db_session,
        email="person@gmail.com",
        settings=settings,
        email_client=email_outbox,
        client_ip=CLIENT_IP,
        now=NOW + timedelta(seconds=1),
    )
    assert unknown is None and disallowed is None
    assert await email_outbox.drain() == []
    assert await db_session.scalar(text("SELECT count(*) FROM email_outbox")) == 0
    assert await db_session.scalar(text("SELECT count(*) FROM accounts")) == 0


async def test_active_recovery_leaves_password_and_sessions_untouched(
    db_session, settings, email_outbox
) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="initial-password",
        settings=settings,
        now=NOW,
    )
    active_session = await add_session(db_session, account.id)
    before = await reload_account(db_session, account.id)
    hash_before = before.password_hash

    await request_password_email(
        db_session,
        email=account.email,
        settings=settings,
        email_client=email_outbox,
        client_ip=CLIENT_IP,
        now=NOW + timedelta(seconds=61),
    )
    after = await reload_account(db_session, account.id)
    assert after.password_hash == hash_before
    assert after.status is AccountStatus.ACTIVE
    await db_session.refresh(active_session)
    assert active_session.revoked_at is None


async def test_recovery_completion_revokes_sessions_and_activates(
    db_session, settings, email_outbox
) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="initial-password",
        settings=settings,
        now=NOW,
    )
    active_session = await add_session(db_session, account.id)

    await request_and_drain(
        db_session, settings, email_outbox, email=account.email, now=NOW + timedelta(seconds=61)
    )
    completed = await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="replacement-password",
        settings=settings,
        now=NOW + timedelta(seconds=90),
    )
    assert isinstance(completed, Account)
    assert completed.status is AccountStatus.ACTIVE
    assert verify_password("replacement-password", completed.password_hash)
    await db_session.refresh(active_session)
    assert active_session.revoked_at is not None


async def test_reset_required_account_can_request_and_complete_recovery(
    db_session, settings, email_outbox
) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    invitation_token = email_outbox.last_token
    account.status = AccountStatus.PASSWORD_RESET_REQUIRED
    account.password_hash = None
    await db_session.commit()

    stale = await complete_password_link(
        db_session,
        token=invitation_token,
        new_password="new-password-value",
        settings=settings,
        now=NOW,
    )
    assert isinstance(stale, Failure)
    assert stale.status_code == 400
    account_email = "employee@sis.hust.edu.vn"

    await request_and_drain(
        db_session, settings, email_outbox, email=account_email, now=NOW + timedelta(seconds=61)
    )
    completion = await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="new-password-value",
        settings=settings,
        now=NOW + timedelta(seconds=90),
    )
    assert isinstance(completion, Account)
    assert completion.status is AccountStatus.ACTIVE


async def test_locked_account_cannot_request_a_link(db_session, settings, email_outbox) -> None:
    account = await create_employee(db_session, settings, email_outbox)
    account.status = AccountStatus.LOCKED
    await db_session.commit()
    await request_and_drain(
        db_session, settings, email_outbox, email=account.email, now=NOW + timedelta(seconds=61)
    )
    assert len(email_outbox.messages) == 1  # chỉ thư mời ban đầu


async def test_email_quota_limits_frequency_per_account(db_session, settings, email_outbox) -> None:
    account = await create_employee(db_session, settings, email_outbox)

    async def send(offset: int) -> None:
        await request_and_drain(
            db_session,
            settings,
            email_outbox,
            email=account.email,
            now=NOW + timedelta(seconds=offset),
        )

    await send(1)
    assert len(email_outbox.messages) == 2
    await send(30)
    assert len(email_outbox.messages) == 2
    await send(62)
    assert len(email_outbox.messages) == 3

    for step in range(1, 4):
        await send(62 + step * 61)
    assert len(email_outbox.messages) == 6
    await send(62 + 4 * 61)
    assert len(email_outbox.messages) == 6


async def test_recovery_ip_limit_returns_typed_throttle(db_session, settings, email_outbox) -> None:
    denied = None
    for index in range(settings.recovery_ip_limit + 1):
        outcome = await request_password_email(
            db_session,
            email="someone@sis.hust.edu.vn",
            settings=settings,
            email_client=email_outbox,
            client_ip="203.0.113.99",
            now=NOW + timedelta(seconds=index),
        )
        if outcome is not None:
            denied = outcome
            break
    assert isinstance(denied, Failure)
    assert denied.status_code == 429
    assert denied.retry_after is not None and denied.retry_after > 0


async def test_delivery_failure_preserves_account_and_link(
    db_session, settings, email_outbox
) -> None:
    result = await create_account(
        db_session,
        actor_id=ADMIN_ID,
        full_name="Delivery Failure",
        email="failure@sis.hust.edu.vn",
        account_type=AccountType.EMPLOYEE,
        roles=["HR"],
        settings=settings,
        email_client=email_outbox,
        now=NOW,
    )
    assert isinstance(result, AccountDeliveryResult)
    assert result.email_delivery == "queued"
    # SMTP lỗi khi worker gửi: tài khoản và liên kết vẫn còn, thư chờ thử lại.
    email_outbox.failing = True
    assert await email_outbox.drain() == []
    assert result.account.status is AccountStatus.PENDING_SETUP
    remaining = await db_session.scalar(
        text("SELECT count(*) FROM auth_password_links WHERE consumed_at IS NULL")
    )
    assert remaining == 1
    pending = await db_session.scalar(
        text("SELECT last_error FROM email_outbox WHERE status = 'PENDING'")
    )
    assert pending == "send_error"

    email_outbox.failing = False
    await request_and_drain(
        db_session,
        settings,
        email_outbox,
        email=result.account.email,
        now=NOW + timedelta(seconds=61),
    )
    assert len(email_outbox.messages) == 1


async def test_simultaneous_completion_allows_exactly_one_success(
    clean_database, session_factory, settings, email_outbox
) -> None:
    async with session_factory() as setup:
        await create_employee(setup, settings, email_outbox)
    token = email_outbox.last_token

    async def attempt(index: int):
        async with session_factory() as worker:
            return await complete_password_link(
                worker,
                token=token,
                new_password=f"password-number-{index}",
                settings=settings,
                now=NOW + timedelta(minutes=1),
            )

    results = await asyncio.gather(*(attempt(index) for index in range(4)))
    successes = [item for item in results if isinstance(item, Account)]
    failures = [item for item in results if isinstance(item, Failure)]
    assert len(successes) == 1
    assert len(failures) == 3
    assert all(item.status_code == 400 for item in failures)
