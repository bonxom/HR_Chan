import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus, AccountType

# One fixed transaction-scoped advisory lock serializes account administration.
ADMINISTRATION_LOCK_KEY = 8_002_412_345_678


async def acquire_administration_lock(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMINISTRATION_LOCK_KEY}
    )


async def get_by_email(
    session: AsyncSession, email: str, *, for_update: bool = False
) -> Account | None:
    statement = select(Account).where(Account.email == email)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def get_by_id(
    session: AsyncSession, account_id: UUID, *, for_update: bool = False
) -> Account | None:
    statement = select(Account).where(Account.id == account_id)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def add_account(session: AsyncSession, account: Account) -> None:
    session.add(account)
    await session.flush()


async def admin_exists(session: AsyncSession) -> bool:
    found = await session.scalar(
        select(func.count()).select_from(Account).where(Account.account_type == AccountType.ADMIN)
    )
    return bool(found)


async def active_admin_count(session: AsyncSession) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Account)
        .where(
            Account.account_type == AccountType.ADMIN,
            Account.status == AccountStatus.ACTIVE,
        )
    )
    return int(count or 0)


def _keyset_condition(cursor: tuple[datetime, uuid.UUID]):
    timestamp, identifier = cursor
    return or_(
        Account.created_at < timestamp,
        and_(Account.created_at == timestamp, Account.id < identifier),
    )


async def list_accounts(
    session: AsyncSession,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    status: AccountStatus | None = None,
    account_type: AccountType | None = None,
) -> tuple[list[Account], bool]:
    statement = select(Account).order_by(Account.created_at.desc(), Account.id.desc())
    if status is not None:
        statement = statement.where(Account.status == status)
    if account_type is not None:
        statement = statement.where(Account.account_type == account_type)
    if cursor is not None:
        statement = statement.where(_keyset_condition(cursor))
    rows = list((await session.scalars(statement.limit(limit + 1))).all())
    return rows[:limit], len(rows) > limit
