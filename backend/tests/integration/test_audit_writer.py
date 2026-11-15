import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.modules.audit.models import AuditOutcome
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.audit.service import record_event

pytestmark = pytest.mark.database

ACTOR_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TARGET_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


def event(**overrides: object) -> AuditEventInput:
    values: dict[str, object] = {
        "action": AuditAction.ACCOUNT_LOCKED,
        "outcome": AuditOutcome.SUCCESS,
        "actor_id": ACTOR_ID,
        "target_type": "account",
        "target_id": str(TARGET_ID),
        "metadata": {"reason": "security review", "previous_status": "ACTIVE"},
    }
    values.update(overrides)
    return AuditEventInput(**values)


async def event_count(session) -> int:
    return int(await session.scalar(text("SELECT count(*) FROM audit_events")) or 0)


async def test_records_allowlisted_event_in_caller_transaction(db_session) -> None:
    await record_event(db_session, event())
    await db_session.commit()

    row = (await db_session.execute(text("SELECT * FROM audit_events"))).one()
    assert row.actor_id == ACTOR_ID
    assert row.action == "account.locked"
    assert row.outcome == "SUCCESS"
    assert row.target_type == "account"
    assert row.target_id == str(TARGET_ID)
    assert row.metadata == {"reason": "security review", "previous_status": "ACTIVE"}
    assert row.timestamp is not None


async def test_caller_rollback_discards_the_event(db_session) -> None:
    await record_event(db_session, event())
    await db_session.rollback()
    assert await event_count(db_session) == 0


async def test_flush_exposes_the_event_before_commit(db_session) -> None:
    await record_event(db_session, event())
    assert await event_count(db_session) == 1


@pytest.mark.parametrize(
    "metadata",
    [
        {"password": "plain-text"},
        {"refresh_token": "abc"},
        {"email": "candidate@example.test"},
        {"cv_text": "content"},
        {"evaluation": {"score": 10}},
        {"arbitrary": "value"},
    ],
)
async def test_rejects_non_allowlisted_or_sensitive_metadata(db_session, metadata) -> None:
    with pytest.raises(ValueError):
        await record_event(db_session, event(metadata=metadata))
    await db_session.rollback()
    assert await event_count(db_session) == 0


async def test_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        AuditEventInput(action="exam.grade", outcome=AuditOutcome.SUCCESS)


async def test_rejects_unknown_outcome() -> None:
    with pytest.raises(ValidationError):
        AuditEventInput(action=AuditAction.LOGOUT, outcome="PARTIAL")
