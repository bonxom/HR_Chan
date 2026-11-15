"""Authentication mechanics: login, logout, refresh, activity, and password change."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.exceptions import Failure, failure
from app.modules.accounts import repository as account_repository
from app.modules.accounts.dev_fixtures import DEV_PERSONAS_BY_ID
from app.modules.accounts.models import Account
from app.modules.accounts.rules import (
    AccountStatus,
    RuleViolation,
    normalize_email,
    validate_password,
)
from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event
from app.modules.auth import password_links, repository, sessions
from app.modules.auth.models import AuthRefreshToken, AuthSession
from app.modules.auth.passwords import (
    hash_password_async,
    verify_dummy_password,
    verify_password_async,
)
from app.modules.auth.rate_limits import LimitRule, check, clear, consume
from app.modules.auth.tokens import (
    generate_opaque_token,
    hash_opaque_token,
    issue_access_token,
    limiter_identifier,
)

INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password"


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    account: Account


def _login_keys(settings: Settings, email: str, client_ip: str | None) -> tuple[str, str]:
    secret = settings.require_limiter_secret()
    return (
        limiter_identifier(secret, "login-account", email),
        limiter_identifier(secret, "login-ip", client_ip or "unidentified"),
    )


def _failure_rule(settings: Settings) -> LimitRule:
    return LimitRule(
        max_attempts=settings.login_failure_limit,
        window_seconds=settings.login_failure_window_seconds,
        block_seconds=settings.login_block_seconds,
    )


async def _create_session(
    session: AsyncSession, account: Account, *, settings: Settings, now: datetime
) -> tuple[AuthSession, str]:
    row = AuthSession(
        account_id=account.id,
        credential_version=0,
        created_at=now,
        last_activity_at=now,
        absolute_expires_at=now + timedelta(seconds=settings.session_absolute_seconds),
    )
    await repository.add_session(session, row)
    raw_token = generate_opaque_token()
    await repository.add_refresh_token(
        session,
        AuthRefreshToken(
            session_id=row.id,
            token_hash=hash_opaque_token(raw_token),
            issued_at=now,
            expires_at=row.absolute_expires_at,
        ),
    )
    return row, raw_token


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    settings: Settings,
    client_ip: str | None = None,
    now: datetime | None = None,
) -> SessionTokens | Failure:
    moment = now or clock.utcnow()
    normalized_email = normalize_email(email)
    identifier_key, ip_key = _login_keys(settings, normalized_email, client_ip)

    ip_rule = LimitRule(
        max_attempts=settings.login_ip_limit,
        window_seconds=settings.login_ip_window_seconds,
        block_seconds=settings.login_block_seconds,
    )
    ip_decision = await check(session, ip_key, ip_rule, moment)
    if ip_decision.blocked:
        await session.commit()
        return failure(
            429, "rate_limited", "Too many login attempts", retry_after=ip_decision.retry_after
        )

    identifier_decision = await check(session, identifier_key, _failure_rule(settings), moment)
    if identifier_decision.blocked:
        await session.commit()
        return failure(
            429,
            "rate_limited",
            "Too many login attempts",
            retry_after=identifier_decision.retry_after,
        )
    await consume(session, ip_key, ip_rule, moment)

    account = await account_repository.get_by_email(session, normalized_email)
    if account is None or account.password_hash is None:
        await verify_dummy_password(password)
        password_valid = False
    else:
        password_valid = await verify_password_async(password, account.password_hash)

    if not password_valid or account is None or account.status is not AccountStatus.ACTIVE:
        decision = await consume(session, identifier_key, _failure_rule(settings), moment)
        await record_event(
            session,
            AuditEventInput(
                action=AuditAction.LOGIN_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_id=account.id if account is not None else None,
                target_type="account" if account is not None else None,
                target_id=str(account.id) if account is not None else None,
            ),
        )
        await session.commit()
        if decision.blocked:
            return failure(
                429,
                "rate_limited",
                "Too many login attempts",
                retry_after=decision.retry_after,
            )
        return failure(401, "invalid_credentials", INVALID_CREDENTIALS_MESSAGE)

    await clear_identifier_failures(session, identifier_key)
    session_row, refresh_token = await _create_session(
        session, account, settings=settings, now=moment
    )
    account.last_login_at = moment
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.LOGIN_SUCCEEDED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=account.id,
            target_type="account",
            target_id=str(account.id),
        ),
    )
    await session.commit()

    return SessionTokens(
        access_token=issue_access_token(
            account.id, session_row.id, session_row.credential_version, moment, settings
        ),
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl_seconds,
        refresh_expires_in=settings.session_absolute_seconds,
        account=account,
    )


async def dev_login(
    session: AsyncSession,
    *,
    persona_id: str,
    settings: Settings,
    now: datetime | None = None,
) -> SessionTokens | Failure:
    """Development-only password bypass for the fixed `dev.*` personas.

    The session is a normal credentialed session: status checks, revocation, CSRF,
    and authorization still apply. The endpoint disappears unless explicitly enabled.
    """
    if not settings.dev_login_enabled:
        return failure(404, "not_found", "Not found")
    persona = DEV_PERSONAS_BY_ID.get(persona_id)
    if persona is None:
        return failure(404, "not_found", "Not found")

    moment = now or clock.utcnow()
    account = await account_repository.get_by_email(session, persona.email, for_update=True)
    if account is None:
        # Self-heal so the development buttons work on a fresh database.
        account = Account(
            full_name=persona.full_name,
            email=persona.email,
            account_type=persona.account_type,
            roles=list(persona.roles),
            status=AccountStatus.ACTIVE,
            password_hash=await hash_password_async(generate_opaque_token()),
        )
        await account_repository.add_account(session, account)
        await record_event(
            session,
            AuditEventInput(
                action=AuditAction.ACCOUNT_CREATED,
                outcome=AuditOutcome.SUCCESS,
                target_type="account",
                target_id=str(account.id),
                metadata={"roles": account.roles, "status": account.status.value},
            ),
        )

    if account.status is not AccountStatus.ACTIVE:
        status_value = account.status.value
        await session.rollback()
        return failure(
            409,
            "invalid_status_transition",
            f"Dev account {persona.email} is {status_value}; unlock it or run seed-dev-accounts.",
        )

    session_row, refresh_token = await _create_session(
        session, account, settings=settings, now=moment
    )
    account.last_login_at = moment
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.DEV_LOGIN,
            outcome=AuditOutcome.SUCCESS,
            actor_id=account.id,
            target_type="account",
            target_id=str(account.id),
            metadata={"persona": persona.id},
        ),
    )
    await session.commit()
    return _token_response(account, session_row, refresh_token, settings=settings, moment=moment)


async def clear_identifier_failures(session: AsyncSession, identifier_key: str) -> None:
    await clear(session, identifier_key)


async def logout(
    session: AsyncSession,
    *,
    refresh_token: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> bool:
    """Revoke the current session; safe when the cookie is absent or already revoked."""
    moment = now or clock.utcnow()
    if not refresh_token:
        return False
    token_hash = hash_opaque_token(refresh_token)
    identifiers = await repository.get_account_id_for_refresh_token(session, token_hash)
    if identifiers is None:
        await session.rollback()
        return False
    account_id, session_id = identifiers

    # Lock ordering: account, then session, then token.
    await account_repository.get_by_id(session, account_id, for_update=True)
    session_row = await repository.get_session(session, session_id, for_update=True)
    token_row = await repository.get_refresh_token(session, token_hash, for_update=True)
    if session_row is None or token_row is None or session_row.revoked_at is not None:
        await session.rollback()
        return False

    session_row.revoked_at = moment
    session_row.revoked_reason = sessions.REASON_LOGOUT
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.LOGOUT,
            outcome=AuditOutcome.SUCCESS,
            actor_id=account_id,
            target_type="account",
            target_id=str(account_id),
        ),
    )
    await session.commit()
    return True


def _invalid_session() -> Failure:
    return failure(401, "invalid_session", "The session is no longer valid")


def _token_response(
    account: Account,
    session_row: AuthSession,
    refresh_token: str,
    *,
    settings: Settings,
    moment: datetime,
) -> SessionTokens:
    remaining = max(1, int((session_row.absolute_expires_at - moment).total_seconds()))
    return SessionTokens(
        access_token=issue_access_token(
            account.id, session_row.id, session_row.credential_version, moment, settings
        ),
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl_seconds,
        refresh_expires_in=remaining,
        account=account,
    )


async def _rotate_refresh_token(
    session: AsyncSession, session_row: AuthSession, *, now: datetime
) -> str:
    raw_token = generate_opaque_token()
    await repository.add_refresh_token(
        session,
        AuthRefreshToken(
            session_id=session_row.id,
            token_hash=hash_opaque_token(raw_token),
            issued_at=now,
            expires_at=session_row.absolute_expires_at,
        ),
    )
    return raw_token


async def refresh(
    session: AsyncSession,
    *,
    refresh_token: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> SessionTokens | Failure:
    """Rotate a refresh token; replay revokes only its own session family."""
    moment = now or clock.utcnow()
    if not refresh_token:
        await session.rollback()
        return _invalid_session()

    token_hash = hash_opaque_token(refresh_token)
    identifiers = await repository.get_account_id_for_refresh_token(session, token_hash)
    if identifiers is None:
        await session.rollback()
        return _invalid_session()
    account_id, session_id = identifiers

    # Lock ordering: account, then session, then token.
    account = await account_repository.get_by_id(session, account_id, for_update=True)
    session_row = await repository.get_session(session, session_id, for_update=True)
    token_row = await repository.get_refresh_token(session, token_hash, for_update=True)
    if account is None or session_row is None or token_row is None:
        await session.rollback()
        return _invalid_session()

    if token_row.consumed_at is not None:
        if session_row.revoked_at is None:
            session_row.revoked_at = moment
            session_row.revoked_reason = sessions.REASON_REPLAY
        await record_event(
            session,
            AuditEventInput(
                action=AuditAction.REFRESH_REPLAYED,
                outcome=AuditOutcome.FAILURE,
                actor_id=account_id,
                target_type="account",
                target_id=str(account_id),
            ),
        )
        await session.commit()
        return _invalid_session()

    idle_deadline = session_row.last_activity_at + timedelta(seconds=settings.session_idle_seconds)
    if (
        session_row.revoked_at is not None
        or session_row.absolute_expires_at <= moment
        or idle_deadline <= moment
        or token_row.expires_at <= moment
        or account.status is not AccountStatus.ACTIVE
    ):
        await session.rollback()
        return _invalid_session()

    token_row.consumed_at = moment
    new_refresh = await _rotate_refresh_token(session, session_row, now=moment)
    await session.commit()
    return _token_response(account, session_row, new_refresh, settings=settings, moment=moment)


async def record_activity(
    session: AsyncSession,
    *,
    principal_session_id: uuid.UUID,
    settings: Settings,
    now: datetime | None = None,
) -> bool:
    """Persist server-side activity, never extending the absolute session limit."""
    moment = now or clock.utcnow()
    session_row = await repository.get_session(session, principal_session_id, for_update=True)
    if session_row is None or session_row.revoked_at is not None:
        await session.rollback()
        return False
    if session_row.absolute_expires_at <= moment:
        await session.rollback()
        return False
    idle_deadline = session_row.last_activity_at + timedelta(seconds=settings.session_idle_seconds)
    if idle_deadline <= moment:
        await session.rollback()
        return False
    elapsed = (moment - session_row.last_activity_at).total_seconds()
    if elapsed < settings.activity_min_interval_seconds:
        await session.rollback()
        return False
    session_row.last_activity_at = moment
    await session.commit()
    return True


async def change_password(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    session_id: uuid.UUID,
    current_password: str,
    new_password: str,
    expected_version: int,
    settings: Settings,
    now: datetime | None = None,
) -> SessionTokens | Failure:
    """Rotate the performing session's credentials and revoke every other session."""
    moment = now or clock.utcnow()
    try:
        validated_password = validate_password(new_password)
    except RuleViolation as exc:
        return failure(400, "invalid_password", str(exc))

    account = await account_repository.get_by_id(session, account_id, for_update=True)
    current_session = await repository.get_session(session, session_id, for_update=True)
    if (
        account is None
        or current_session is None
        or current_session.revoked_at is not None
        or current_session.credential_version != expected_version
    ):
        await session.rollback()
        return _invalid_session()

    if not await verify_password_async(current_password, account.password_hash):
        await session.rollback()
        return failure(400, "invalid_current_password", "The current password is incorrect")

    account.password_hash = await hash_password_async(validated_password)
    current_session.credential_version += 1
    await session.execute(
        update(AuthRefreshToken)
        .where(
            AuthRefreshToken.session_id == current_session.id,
            AuthRefreshToken.consumed_at.is_(None),
        )
        .values(consumed_at=moment)
    )
    new_refresh = await _rotate_refresh_token(session, current_session, now=moment)
    await sessions.revoke_all_sessions(
        session,
        account.id,
        now=moment,
        reason=sessions.REASON_PASSWORD_CHANGE,
        except_session_id=current_session.id,
    )
    await password_links.invalidate_outstanding(session, account.id, now=moment)
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.PASSWORD_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=account.id,
            target_type="account",
            target_id=str(account.id),
        ),
    )
    await session.commit()
    return _token_response(account, current_session, new_refresh, settings=settings, moment=moment)
