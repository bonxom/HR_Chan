from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.exceptions import Failure
from app.core.security import AdminPrincipal
from app.db.session import SessionDep
from app.modules.audit import service
from app.modules.audit.schemas import AuditEventPageRead, AuditEventRead

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=AuditEventPageRead)
async def list_audit_events(
    principal: AdminPrincipal,
    session: SessionDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    actor_id: UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
) -> AuditEventPageRead:
    result = await service.list_events(
        session,
        cursor=cursor,
        limit=limit,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    if isinstance(result, Failure):
        result.raise_error()
    return AuditEventPageRead(
        items=[AuditEventRead.from_event(event) for event in result.items],
        next_cursor=result.next_cursor,
    )
