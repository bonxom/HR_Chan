"""Reusable identity dependencies and permission checks.

Domain policies decide resource access; this module only exposes the current
principal, Admin requirements, and trusted client addressing.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core import clock
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.session import SessionDep
from app.integrations.email.client import EmailClient
from app.modules.accounts.rules import AccountStatus, AccountType, EmployeeRole
from app.modules.auth import repository
from app.modules.auth.tokens import TokenError, verify_access_token


def get_app_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise AppError(
            "Application settings are unavailable",
            status_code=500,
            code="configuration_error",
        )
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def unauthorized() -> AppError:
    return AppError("Authentication required", status_code=401, code="invalid_session")


@dataclass(frozen=True)
class Principal:
    account_id: UUID
    account_type: AccountType
    roles: tuple[EmployeeRole, ...]
    session_id: UUID
    credential_version: int
    session_absolute_expires_at: datetime


async def get_current_principal(
    request: Request, session: SessionDep, settings: SettingsDep
) -> Principal:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized()
    now = clock.utcnow()
    try:
        claims = verify_access_token(token.strip(), now, settings)
    except TokenError:
        raise unauthorized() from None

    loaded = await repository.get_session_with_account(session, claims.session_id)
    if loaded is None:
        raise unauthorized()
    session_row, account = loaded

    idle_deadline = session_row.last_activity_at + timedelta(seconds=settings.session_idle_seconds)
    if (
        account.id != claims.account_id
        or session_row.revoked_at is not None
        or session_row.absolute_expires_at <= now
        or idle_deadline <= now
        or session_row.credential_version != claims.credential_version
        or account.status is not AccountStatus.ACTIVE
    ):
        raise unauthorized()

    return Principal(
        account_id=account.id,
        account_type=account.account_type,
        roles=tuple(EmployeeRole(role) for role in account.roles),
        session_id=session_row.id,
        credential_version=session_row.credential_version,
        session_absolute_expires_at=session_row.absolute_expires_at,
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    if principal.account_type is not AccountType.ADMIN:
        raise AppError("Administrator permission required", status_code=403, code="forbidden")
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]


def get_email_client(request: Request) -> EmailClient | None:
    return getattr(request.app.state, "email_client", None)


def client_ip(request: Request, settings: Settings) -> str:
    """Forwarded headers are only honored in deployments that opt in."""
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unidentified"
