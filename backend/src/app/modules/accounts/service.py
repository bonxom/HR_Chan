"""Account lifecycle services. Each service owns its transaction boundaries."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import Settings
from app.core.exceptions import Failure, failure
from app.core.pagination import CursorError, decode_cursor, encode_cursor
from app.integrations.email.client import EmailClient, deliver
from app.integrations.email.templates import invitation_message, recovery_message
from app.modules.accounts import repository
from app.modules.accounts.models import Account
from app.modules.accounts.rules import (
    AccountStatus,
    AccountType,
    EmployeeRole,
    RuleViolation,
    ensure_allowed_email_domain,
    validate_account_roles,
    validate_employee_roles,
    validate_full_name,
    validate_page_size,
    validate_password,
    validate_reason,
)
from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event
from app.modules.auth import password_links, sessions
from app.modules.auth.models import PasswordLinkPurpose
from app.modules.auth.passwords import hash_password_async
from app.modules.auth.rate_limits import LimitRule, consume
from app.modules.auth.tokens import limiter_identifier

EMAIL_SENT = "sent"
EMAIL_FAILED = "failed"

INVALID_LINK_MESSAGE = "This password link is invalid or has expired. Request a new email."


@dataclass(frozen=True)
class AccountDeliveryResult:
    account: Account
    email_delivery: str


def invalid_link() -> Failure:
    return failure(400, "invalid_password_link", INVALID_LINK_MESSAGE)


async def _deliver_link_email(
    account: Account,
    token: str,
    purpose: PasswordLinkPurpose,
    *,
    settings: Settings,
    email_client: EmailClient | None,
) -> str:
    builder = invitation_message if purpose is PasswordLinkPurpose.INVITATION else recovery_message
    message = builder(
        to=account.email,
        full_name=account.full_name,
        token=token,
        frontend_url=settings.frontend_url,
    )
    return EMAIL_SENT if await deliver(email_client, message) else EMAIL_FAILED


async def create_account(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    full_name: str,
    email: str,
    account_type: AccountType,
    roles: list[str],
    settings: Settings,
    email_client: EmailClient | None,
    now: datetime | None = None,
) -> AccountDeliveryResult | Failure:
    moment = now or clock.utcnow()
    try:
        normalized_email = ensure_allowed_email_domain(email, settings.allowed_email_domains)
        validated_name = validate_full_name(full_name)
        validated_roles = validate_account_roles(account_type, roles)
    except RuleViolation as exc:
        return failure(400, "invalid_account", str(exc))

    await repository.acquire_administration_lock(session)
    if await repository.get_by_email(session, normalized_email) is not None:
        await session.rollback()
        return failure(409, "duplicate_email", "An account with this email already exists")

    account = Account(
        full_name=validated_name,
        email=normalized_email,
        account_type=AccountType(account_type),
        roles=[role.value for role in validated_roles],
        status=AccountStatus.PENDING_SETUP,
        password_hash=None,
    )
    try:
        await repository.add_account(session, account)
    except IntegrityError:
        await session.rollback()
        return failure(409, "duplicate_email", "An account with this email already exists")

    _, token = await password_links.create_link(
        session,
        account.id,
        PasswordLinkPurpose.INVITATION,
        settings=settings,
        now=moment,
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(account.id),
            metadata={"roles": account.roles, "status": account.status.value},
        ),
    )
    await session.commit()

    delivery = await _deliver_link_email(
        account,
        token,
        PasswordLinkPurpose.INVITATION,
        settings=settings,
        email_client=email_client,
    )
    return AccountDeliveryResult(account=account, email_delivery=delivery)


async def bootstrap_admin(
    session: AsyncSession,
    *,
    full_name: str,
    email: str,
    settings: Settings,
    email_client: EmailClient | None,
    now: datetime | None = None,
) -> AccountDeliveryResult | Failure:
    """Create the first Admin; only valid while no Admin account row exists."""
    moment = now or clock.utcnow()
    try:
        normalized_email = ensure_allowed_email_domain(email, settings.allowed_email_domains)
        validated_name = validate_full_name(full_name)
    except RuleViolation as exc:
        return failure(400, "invalid_account", str(exc))

    await repository.acquire_administration_lock(session)
    if await repository.admin_exists(session):
        await session.rollback()
        return failure(
            409, "admin_already_exists", "An Admin account already exists; bootstrap refused"
        )

    account = Account(
        full_name=validated_name,
        email=normalized_email,
        account_type=AccountType.ADMIN,
        roles=[],
        status=AccountStatus.PENDING_SETUP,
        password_hash=None,
    )
    try:
        await repository.add_account(session, account)
    except IntegrityError:
        await session.rollback()
        return failure(409, "duplicate_email", "An account with this email already exists")

    _, token = await password_links.create_link(
        session,
        account.id,
        PasswordLinkPurpose.INVITATION,
        settings=settings,
        now=moment,
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="account",
            target_id=str(account.id),
            metadata={"roles": [], "status": account.status.value},
        ),
    )
    await session.commit()

    delivery = await _deliver_link_email(
        account,
        token,
        PasswordLinkPurpose.INVITATION,
        settings=settings,
        email_client=email_client,
    )
    return AccountDeliveryResult(account=account, email_delivery=delivery)


async def request_password_email(
    session: AsyncSession,
    *,
    email: str,
    settings: Settings,
    email_client: EmailClient | None,
    client_ip: str | None = None,
    now: datetime | None = None,
) -> Failure | None:
    """Public recovery: identical outcome for every account state and delivery result."""
    moment = now or clock.utcnow()
    ip_decision = await consume(
        session,
        limiter_identifier(
            settings.require_limiter_secret(), "recovery-ip", client_ip or "unidentified"
        ),
        LimitRule(
            max_attempts=settings.recovery_ip_limit,
            window_seconds=settings.recovery_ip_window_seconds,
            block_seconds=settings.recovery_ip_block_seconds,
        ),
        moment,
    )
    if ip_decision.blocked:
        await session.commit()
        return failure(
            429, "rate_limited", "Too many requests", retry_after=ip_decision.retry_after
        )

    try:
        normalized_email = ensure_allowed_email_domain(email, settings.allowed_email_domains)
    except RuleViolation:
        await session.commit()
        return None

    account = await repository.get_by_email(session, normalized_email, for_update=True)
    if account is None or account.status not in (
        AccountStatus.PENDING_SETUP,
        AccountStatus.PASSWORD_RESET_REQUIRED,
        AccountStatus.ACTIVE,
    ):
        await session.commit()
        return None

    retry_after = await password_links.reserve_email_quota(
        session, account.id, settings=settings, now=moment
    )
    if retry_after is not None:
        await session.commit()
        return None

    purpose = password_links.purpose_for_status(account.status)
    _, token = await password_links.create_link(
        session, account.id, purpose, settings=settings, now=moment
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.PASSWORD_RECOVERY_REQUESTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="account",
            target_id=str(account.id),
            metadata={"purpose": purpose.value},
        ),
    )
    await session.commit()

    await _deliver_link_email(account, token, purpose, settings=settings, email_client=email_client)
    return None


async def resend_invitation(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    settings: Settings,
    email_client: EmailClient | None,
    now: datetime | None = None,
) -> AccountDeliveryResult | Failure:
    moment = now or clock.utcnow()
    account = await repository.get_by_id(session, account_id, for_update=True)
    if account is None:
        await session.rollback()
        return failure(404, "account_not_found", "Account not found")
    if account.status not in (
        AccountStatus.PENDING_SETUP,
        AccountStatus.PASSWORD_RESET_REQUIRED,
    ):
        await session.rollback()
        return failure(
            409,
            "invalid_status_transition",
            "Invitations can only be resent for accounts awaiting setup or reset",
        )

    retry_after = await password_links.reserve_email_quota(
        session, account.id, settings=settings, now=moment
    )
    if retry_after is not None:
        await session.commit()
        return failure(
            429,
            "rate_limited",
            "Please wait before requesting another email",
            retry_after=retry_after,
        )

    purpose = password_links.purpose_for_status(account.status)
    _, token = await password_links.create_link(
        session, account.id, purpose, settings=settings, now=moment
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_INVITATION_RESENT,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(account.id),
            metadata={"purpose": purpose.value},
        ),
    )
    await session.commit()

    delivery = await _deliver_link_email(
        account, token, purpose, settings=settings, email_client=email_client
    )
    return AccountDeliveryResult(account=account, email_delivery=delivery)


async def complete_password_link(
    session: AsyncSession,
    *,
    token: str,
    new_password: str,
    settings: Settings,
    now: datetime | None = None,
) -> Account | Failure:
    moment = now or clock.utcnow()
    try:
        validated_password = validate_password(new_password)
    except RuleViolation as exc:
        return failure(400, "invalid_password", str(exc))

    account_id = await password_links.peek_link_account_id(session, token)
    if account_id is None:
        await session.rollback()
        return invalid_link()

    # Lock ordering: account, then password link.
    account = await repository.get_by_id(session, account_id, for_update=True)
    link = await password_links.lock_link(session, token)
    if account is None or link is None or not password_links.link_is_usable(link, moment):
        await session.rollback()
        return invalid_link()

    eligible_statuses = (
        (AccountStatus.PENDING_SETUP,)
        if link.purpose is PasswordLinkPurpose.INVITATION
        else (AccountStatus.ACTIVE, AccountStatus.PASSWORD_RESET_REQUIRED)
    )
    if account.status not in eligible_statuses:
        await session.rollback()
        return invalid_link()

    account.password_hash = await hash_password_async(validated_password)
    account.status = AccountStatus.ACTIVE
    link.consumed_at = moment
    await password_links.invalidate_outstanding(session, account.id, now=moment, keep_id=link.id)
    await sessions.revoke_all_sessions(
        session,
        account.id,
        now=moment,
        reason=sessions.REASON_PASSWORD_RESET,
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.PASSWORD_SETUP,
            outcome=AuditOutcome.SUCCESS,
            target_type="account",
            target_id=str(account.id),
            metadata={"purpose": link.purpose.value},
        ),
    )
    await session.commit()
    return account


@dataclass(frozen=True)
class AccountPage:
    items: list[Account]
    next_cursor: str | None


def _forbidden() -> Failure:
    return failure(403, "forbidden", "Administrator permission required")


async def _live_admin(session: AsyncSession, actor_id: uuid.UUID) -> Account | None:
    """Revalidate the actor after the administration lock, never trusting a stale principal."""
    actor = await repository.get_by_id(session, actor_id, for_update=True)
    if (
        actor is None
        or actor.account_type is not AccountType.ADMIN
        or actor.status is not AccountStatus.ACTIVE
    ):
        return None
    return actor


async def list_accounts(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 25,
    status: AccountStatus | None = None,
    account_type: AccountType | None = None,
) -> AccountPage | Failure:
    try:
        page_size = validate_page_size(limit)
        decoded = decode_cursor(cursor) if cursor else None
    except (CursorError, RuleViolation) as exc:
        return failure(400, "invalid_cursor", str(exc))

    rows, has_more = await repository.list_accounts(
        session,
        limit=page_size,
        cursor=decoded,
        status=status,
        account_type=account_type,
    )
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return AccountPage(items=rows, next_cursor=next_cursor)


async def replace_roles(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    roles: list[EmployeeRole],
) -> Account | Failure:
    await repository.acquire_administration_lock(session)
    if await _live_admin(session, actor_id) is None:
        await session.rollback()
        return _forbidden()

    target = await repository.get_by_id(session, account_id, for_update=True)
    if target is None:
        await session.rollback()
        return failure(404, "account_not_found", "Account not found")
    if target.account_type is not AccountType.EMPLOYEE:
        await session.rollback()
        return failure(
            409, "invalid_account_type", "Employee roles apply only to employee accounts"
        )
    try:
        validated = validate_employee_roles([role.value for role in roles])
    except RuleViolation as exc:
        await session.rollback()
        return failure(400, "invalid_roles", str(exc))

    previous_roles = list(target.roles)
    target.roles = [role.value for role in validated]
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_ROLES_REPLACED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(target.id),
            metadata={"roles": target.roles, "previous_roles": previous_roles},
        ),
    )
    await session.commit()
    return target


async def lock_account(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> Account | Failure:
    moment = now or clock.utcnow()
    try:
        validated_reason = validate_reason(reason)
    except RuleViolation as exc:
        return failure(400, "invalid_reason", str(exc))

    await repository.acquire_administration_lock(session)
    if await _live_admin(session, actor_id) is None:
        await session.rollback()
        return _forbidden()
    if actor_id == account_id:
        await session.rollback()
        return failure(
            409,
            "self_administration_forbidden",
            "Administrators cannot lock or disable their own account",
        )

    target = await repository.get_by_id(session, account_id, for_update=True)
    if target is None:
        await session.rollback()
        return failure(404, "account_not_found", "Account not found")
    if target.status in (AccountStatus.LOCKED, AccountStatus.DISABLED):
        await session.rollback()
        return failure(
            409, "invalid_status_transition", "Account cannot be locked from its current status"
        )
    if (
        target.account_type is AccountType.ADMIN
        and target.status is AccountStatus.ACTIVE
        and await repository.active_admin_count(session) <= 1
    ):
        await session.rollback()
        return failure(
            409, "final_admin_protected", "The final active Administrator cannot be locked"
        )

    previous_status = target.status
    target.status = AccountStatus.LOCKED
    await sessions.revoke_all_sessions(
        session, target.id, now=moment, reason=sessions.REASON_LOCKED
    )
    await password_links.invalidate_outstanding(session, target.id, now=moment)
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_LOCKED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(target.id),
            metadata={"reason": validated_reason, "previous_status": previous_status.value},
        ),
    )
    await session.commit()
    return target


async def disable_account(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> Account | Failure:
    moment = now or clock.utcnow()
    try:
        validated_reason = validate_reason(reason)
    except RuleViolation as exc:
        return failure(400, "invalid_reason", str(exc))

    await repository.acquire_administration_lock(session)
    if await _live_admin(session, actor_id) is None:
        await session.rollback()
        return _forbidden()
    if actor_id == account_id:
        await session.rollback()
        return failure(
            409,
            "self_administration_forbidden",
            "Administrators cannot lock or disable their own account",
        )

    target = await repository.get_by_id(session, account_id, for_update=True)
    if target is None:
        await session.rollback()
        return failure(404, "account_not_found", "Account not found")
    if target.status is AccountStatus.DISABLED:
        await session.rollback()
        return failure(409, "invalid_status_transition", "Account is already disabled")
    if (
        target.account_type is AccountType.ADMIN
        and target.status is AccountStatus.ACTIVE
        and await repository.active_admin_count(session) <= 1
    ):
        await session.rollback()
        return failure(
            409, "final_admin_protected", "The final active Administrator cannot be disabled"
        )

    previous_status = target.status
    target.status = AccountStatus.DISABLED
    await sessions.revoke_all_sessions(
        session, target.id, now=moment, reason=sessions.REASON_DISABLED
    )
    await password_links.invalidate_outstanding(session, target.id, now=moment)
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_DISABLED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(target.id),
            metadata={"reason": validated_reason, "previous_status": previous_status.value},
        ),
    )
    await session.commit()
    return target


async def unlock_account(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    settings: Settings,
    email_client: EmailClient | None,
    now: datetime | None = None,
) -> AccountDeliveryResult | Failure:
    moment = now or clock.utcnow()
    await repository.acquire_administration_lock(session)
    if await _live_admin(session, actor_id) is None:
        await session.rollback()
        return _forbidden()

    target = await repository.get_by_id(session, account_id, for_update=True)
    if target is None:
        await session.rollback()
        return failure(404, "account_not_found", "Account not found")
    if target.status is not AccountStatus.LOCKED:
        await session.rollback()
        return failure(409, "invalid_status_transition", "Only locked accounts can be unlocked")

    target.status = AccountStatus.PASSWORD_RESET_REQUIRED
    target.password_hash = None
    await password_links.invalidate_outstanding(session, target.id, now=moment)
    _, token = await password_links.create_link(
        session,
        target.id,
        PasswordLinkPurpose.RECOVERY,
        settings=settings,
        now=moment,
    )
    await record_event(
        session,
        AuditEventInput(
            action=AuditAction.ACCOUNT_UNLOCKED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            target_type="account",
            target_id=str(target.id),
            metadata={"previous_status": AccountStatus.LOCKED.value},
        ),
    )
    await session.commit()

    delivery = await _deliver_link_email(
        target, token, PasswordLinkPurpose.RECOVERY, settings=settings, email_client=email_client
    )
    return AccountDeliveryResult(account=target, email_delivery=delivery)
