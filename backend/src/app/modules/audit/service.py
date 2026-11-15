"""Append-only audit writer and Admin listing. Callers own transactions."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Failure, failure
from app.core.pagination import CursorError, decode_cursor, encode_cursor
from app.modules.audit.models import AuditEvent
from app.modules.audit.repository import add_event
from app.modules.audit.repository import list_events as list_events_query
from app.modules.audit.schemas import AuditEventInput, sanitize_metadata


async def record_event(session: AsyncSession, event: AuditEventInput) -> None:
    """Flush one allowlisted event; a later rollback also discards the event."""
    row = AuditEvent(
        actor_id=event.actor_id,
        action=event.action.value,
        outcome=event.outcome,
        target_type=event.target_type,
        target_id=event.target_id,
        event_metadata=sanitize_metadata(event.metadata),
    )
    await add_event(session, row)


@dataclass(frozen=True)
class AuditPage:
    items: list[AuditEvent]
    next_cursor: str | None


async def list_events(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int = 25,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> AuditPage | Failure:
    if not 1 <= limit <= 100:
        return failure(400, "invalid_cursor", "Page size must be 1-100")
    try:
        decoded = decode_cursor(cursor) if cursor else None
    except CursorError as exc:
        return failure(400, "invalid_cursor", str(exc))

    rows, has_more = await list_events_query(
        session,
        limit=limit,
        cursor=decoded,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    next_cursor = encode_cursor(rows[-1].timestamp, rows[-1].id) if has_more and rows else None
    return AuditPage(items=rows, next_cursor=next_cursor)
