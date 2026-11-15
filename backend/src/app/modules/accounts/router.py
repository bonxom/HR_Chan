from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.exceptions import Failure
from app.core.security import AdminPrincipal, SettingsDep, get_email_client
from app.db.session import SessionDep
from app.modules.accounts import service
from app.modules.accounts.rules import AccountStatus, AccountType
from app.modules.accounts.schemas import (
    AccountCreateRequest,
    AccountDeliveryRead,
    AccountPageRead,
    AccountRead,
    ReasonRequest,
    RolesReplaceRequest,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=AccountPageRead)
async def list_accounts(
    principal: AdminPrincipal,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    status: AccountStatus | None = None,
    account_type: AccountType | None = None,
) -> AccountPageRead:
    result = await service.list_accounts(
        session, cursor=cursor, limit=limit, status=status, account_type=account_type
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountPageRead(
        items=[AccountRead.from_account(account) for account in result.items],
        next_cursor=result.next_cursor,
    )


@router.post("", status_code=201, response_model=AccountDeliveryRead)
async def create_account(
    payload: AccountCreateRequest,
    request: Request,
    principal: AdminPrincipal,
    session: SessionDep,
    settings: SettingsDep,
) -> AccountDeliveryRead:
    result = await service.create_account(
        session,
        actor_id=principal.account_id,
        full_name=payload.full_name,
        email=str(payload.email),
        account_type=payload.account_type,
        roles=[role.value for role in payload.roles],
        settings=settings,
        email_client=get_email_client(request),
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountDeliveryRead(
        account=AccountRead.from_account(result.account),
        email_delivery=result.email_delivery,
    )


@router.put("/{account_id}/roles", response_model=AccountRead)
async def replace_roles(
    account_id: UUID,
    payload: RolesReplaceRequest,
    principal: AdminPrincipal,
    session: SessionDep,
) -> AccountRead:
    result = await service.replace_roles(
        session,
        actor_id=principal.account_id,
        account_id=account_id,
        roles=payload.roles,
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountRead.from_account(result)


@router.post("/{account_id}/lock", response_model=AccountRead)
async def lock_account(
    account_id: UUID,
    payload: ReasonRequest,
    principal: AdminPrincipal,
    session: SessionDep,
) -> AccountRead:
    result = await service.lock_account(
        session,
        actor_id=principal.account_id,
        account_id=account_id,
        reason=payload.reason,
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountRead.from_account(result)


@router.post("/{account_id}/unlock", response_model=AccountDeliveryRead)
async def unlock_account(
    account_id: UUID,
    request: Request,
    principal: AdminPrincipal,
    session: SessionDep,
    settings: SettingsDep,
) -> AccountDeliveryRead:
    result = await service.unlock_account(
        session,
        actor_id=principal.account_id,
        account_id=account_id,
        settings=settings,
        email_client=get_email_client(request),
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountDeliveryRead(
        account=AccountRead.from_account(result.account),
        email_delivery=result.email_delivery,
    )


@router.post("/{account_id}/disable", response_model=AccountRead)
async def disable_account(
    account_id: UUID,
    payload: ReasonRequest,
    principal: AdminPrincipal,
    session: SessionDep,
) -> AccountRead:
    result = await service.disable_account(
        session,
        actor_id=principal.account_id,
        account_id=account_id,
        reason=payload.reason,
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountRead.from_account(result)


@router.post("/{account_id}/invitation", response_model=AccountDeliveryRead)
async def resend_invitation(
    account_id: UUID,
    request: Request,
    principal: AdminPrincipal,
    session: SessionDep,
    settings: SettingsDep,
) -> AccountDeliveryRead:
    result = await service.resend_invitation(
        session,
        actor_id=principal.account_id,
        account_id=account_id,
        settings=settings,
        email_client=get_email_client(request),
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AccountDeliveryRead(
        account=AccountRead.from_account(result.account),
        email_delivery=result.email_delivery,
    )
