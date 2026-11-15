"""Session lifecycle helpers shared by login, refresh, and administration."""

import uuid
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthSession

REASON_LOGOUT = "logout"
REASON_PASSWORD_CHANGE = "password_change"
REASON_PASSWORD_RESET = "password_reset"
REASON_LOCKED = "account_locked"
REASON_DISABLED = "account_disabled"
REASON_REPLAY = "refresh_replay"


async def revoke_all_sessions(
    session: AsyncSession,
    account_id: uuid.UUID,
    *,
    now: datetime,
    reason: str,
    except_session_id: uuid.UUID | None = None,
) -> None:
    statement = update(AuthSession).where(
        AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None)
    )
    if except_session_id is not None:
        statement = statement.where(AuthSession.id != except_session_id)
    await session.execute(statement.values(revoked_at=now, revoked_reason=reason))
