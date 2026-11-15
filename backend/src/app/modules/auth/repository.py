import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account
from app.modules.auth.models import AuthRefreshToken, AuthSession


async def add_session(session: AsyncSession, row: AuthSession) -> None:
    session.add(row)
    await session.flush()


async def get_session(
    session: AsyncSession, session_id: uuid.UUID, *, for_update: bool = False
) -> AuthSession | None:
    statement = select(AuthSession).where(AuthSession.id == session_id)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def get_session_with_account(
    session: AsyncSession, session_id: uuid.UUID
) -> tuple[AuthSession, Account] | None:
    row = (
        await session.execute(
            select(AuthSession, Account)
            .join(Account, Account.id == AuthSession.account_id)
            .where(AuthSession.id == session_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def add_refresh_token(session: AsyncSession, row: AuthRefreshToken) -> None:
    session.add(row)
    await session.flush()


async def get_refresh_token(
    session: AsyncSession, token_hash: str, *, for_update: bool = False
) -> AuthRefreshToken | None:
    statement = select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def get_account_id_for_refresh_token(
    session: AsyncSession, token_hash: str
) -> tuple[uuid.UUID, uuid.UUID] | None:
    row = (
        await session.execute(
            select(AuthSession.account_id, AuthSession.id)
            .join(AuthRefreshToken, AuthRefreshToken.session_id == AuthSession.id)
            .where(AuthRefreshToken.token_hash == token_hash)
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]
