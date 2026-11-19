import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.core.exceptions import Failure
from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus, AccountType
from app.modules.accounts.service import (
    AccountDeliveryResult,
    bootstrap_admin,
    create_account,
    request_password_email,
)

pytestmark = pytest.mark.database

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


async def bootstrap(session, settings, outbox, *, email="admin@sis.hust.edu.vn"):
    return await bootstrap_admin(
        session,
        full_name="Initial Administrator",
        email=email,
        settings=settings,
        email_client=outbox,
        now=NOW,
    )


async def test_bootstrap_creates_one_pending_admin(db_session, settings, email_outbox) -> None:
    result = await bootstrap(db_session, settings, email_outbox)
    assert isinstance(result, AccountDeliveryResult), result
    assert result.account.account_type is AccountType.ADMIN
    assert result.account.roles == []
    assert result.account.status is AccountStatus.PENDING_SETUP
    assert result.email_delivery == "queued"
    assert email_outbox.messages == []  # chưa gọi SMTP trước khi worker chạy
    assert len(await email_outbox.drain()) == 1

    statement = (
        "SELECT actor_id, action, target_id FROM audit_events WHERE action = 'account.created'"
    )
    audit = (await db_session.execute(text(statement))).one()
    assert audit.actor_id is None
    assert audit.target_id == str(result.account.id)


async def test_second_bootstrap_is_refused(db_session, settings, email_outbox) -> None:
    await bootstrap(db_session, settings, email_outbox)
    second = await bootstrap(db_session, settings, email_outbox, email="other@sis.hust.edu.vn")
    assert isinstance(second, Failure)
    assert second.status_code == 409
    assert second.code == "admin_already_exists"
    assert await db_session.scalar(text("SELECT count(*) FROM accounts")) == 1


async def test_pending_admin_blocks_bootstrap(db_session, settings, email_outbox) -> None:
    first = await bootstrap(db_session, settings, email_outbox)
    assert isinstance(first, AccountDeliveryResult)
    second = await bootstrap(db_session, settings, email_outbox, email="second@sis.hust.edu.vn")
    assert isinstance(second, Failure)


async def test_employee_accounts_do_not_block_bootstrap(db_session, settings, email_outbox) -> None:
    employee = await create_account(
        db_session,
        actor_id=None,
        full_name="Existing Employee",
        email="employee@sis.hust.edu.vn",
        account_type=AccountType.EMPLOYEE,
        roles=["HR"],
        settings=settings,
        email_client=email_outbox,
        now=NOW,
    )
    assert isinstance(employee, AccountDeliveryResult)
    admin = await bootstrap(db_session, settings, email_outbox)
    assert isinstance(admin, AccountDeliveryResult)
    assert admin.account.account_type is AccountType.ADMIN


@pytest.mark.parametrize(
    "email",
    ["admin@gmail.com", "admin@sub.sis.hust.edu.vn", "not-an-email"],
)
async def test_bootstrap_rejects_disallowed_domains(
    db_session, settings, email_outbox, email: str
) -> None:
    result = await bootstrap(db_session, settings, email_outbox, email=email)
    assert isinstance(result, Failure)
    assert result.status_code == 400
    assert await db_session.scalar(text("SELECT count(*) FROM accounts")) == 0


async def test_delivery_failure_keeps_the_pending_admin_and_can_be_retried(
    db_session, settings, email_outbox
) -> None:
    created = await bootstrap(db_session, settings, email_outbox)
    assert isinstance(created, AccountDeliveryResult)
    assert created.email_delivery == "queued"

    # SMTP lỗi khi worker gửi: thư ở lại PENDING với lỗi tạm, tài khoản vẫn giữ nguyên.
    email_outbox.failing = True
    assert await email_outbox.drain() == []
    row = (
        await db_session.execute(
            text(
                "SELECT status::text AS status, attempts, last_error FROM email_outbox"
                " WHERE template_code = 'ACCOUNT_INVITATION'"
            )
        )
    ).one()
    assert (row.status, row.attempts, row.last_error) == ("PENDING", 1, "send_error")

    email_outbox.failing = False
    await request_password_email(
        db_session,
        email=created.account.email,
        settings=settings,
        email_client=email_outbox,
        client_ip="198.51.100.7",
        now=NOW + timedelta(seconds=61),
    )
    # Thư mới đến ngay; thư lỗi chờ lượt thử lại sau 5 phút.
    assert len(await email_outbox.drain()) == 1
    assert isinstance(
        await bootstrap(db_session, settings, email_outbox, email="another@sis.hust.edu.vn"),
        Failure,
    )


async def test_concurrent_bootstrap_attempts_create_one_admin(
    clean_database, session_factory, settings, email_outbox
) -> None:
    async def attempt(index: int):
        async with session_factory() as worker:
            return await bootstrap(
                worker, settings, email_outbox, email=f"admin{index}@sis.hust.edu.vn"
            )

    results = await asyncio.gather(*(attempt(index) for index in range(4)))
    successes = [item for item in results if isinstance(item, AccountDeliveryResult)]
    failures = [item for item in results if isinstance(item, Failure)]
    assert len(successes) == 1
    assert len(failures) == 3
    assert all(item.status_code == 409 for item in failures)

    async with session_factory() as reader:
        assert (
            await reader.scalar(text("SELECT count(*) FROM accounts WHERE account_type = 'ADMIN'"))
            == 1
        )
        assert await reader.scalar(text("SELECT count(*) FROM auth_password_links")) == 1


async def test_bootstrapped_admin_can_complete_setup(db_session, settings, email_outbox) -> None:
    from app.modules.accounts.service import complete_password_link

    result = await bootstrap(db_session, settings, email_outbox)
    assert isinstance(result, AccountDeliveryResult)
    await email_outbox.drain()
    completed = await complete_password_link(
        db_session,
        token=email_outbox.last_token,
        new_password="admin-password",
        settings=settings,
        now=NOW + timedelta(minutes=1),
    )
    assert isinstance(completed, Account)
    assert completed.status is AccountStatus.ACTIVE
    assert completed.account_type is AccountType.ADMIN
