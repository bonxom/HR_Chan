import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


async def add_event(session: AsyncSession, event: AuditEvent) -> None:
    session.add(event)
    await session.flush()


def _keyset_condition(cursor: tuple[datetime, uuid.UUID]):
    timestamp, identifier = cursor
    return or_(
        AuditEvent.timestamp < timestamp,
        and_(AuditEvent.timestamp == timestamp, AuditEvent.id < identifier),
    )


async def list_events(
    session: AsyncSession,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> tuple[list[AuditEvent], bool]:
    statement = select(AuditEvent).order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
    if actor_id is not None:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if action is not None:
        statement = statement.where(AuditEvent.action == action)
    if target_type is not None:
        statement = statement.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        statement = statement.where(AuditEvent.target_id == target_id)
    if from_ts is not None:
        statement = statement.where(AuditEvent.timestamp >= from_ts)
    if to_ts is not None:
        statement = statement.where(AuditEvent.timestamp <= to_ts)
    if cursor is not None:
        statement = statement.where(_keyset_condition(cursor))
    rows = list((await session.scalars(statement.limit(limit + 1))).all())
    return rows[:limit], len(rows) > limit
