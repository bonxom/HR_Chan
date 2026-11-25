"""Link lifecycle and interview persistence on PostgreSQL."""

import asyncio
from datetime import timedelta

import pytest
from apply_support import apply_cleanup, build_world, insert_application, now_utc
from sqlalchemy import text

from app.core.exceptions import AppError
from app.core.response_links import LinkOutcome, LinkPurpose, ResponseLinkService

__all__ = ["apply_cleanup"]


@pytest.fixture
async def application_id(apply_cleanup, session_factory):
    world = await build_world(session_factory)
    async with session_factory.begin() as session:
        return await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )


async def test_response_link_replacement_expiry_and_atomic_use(application_id, session_factory):
    now = now_utc()
    async with session_factory.begin() as session:
        service = ResponseLinkService(session, "https://example.test")
        old = await service.issue(
            purpose=LinkPurpose.TALENT_POOL_CONSENT,
            application_id=application_id,
            expires_at=now + timedelta(days=2),
            now=now,
        )
        new = await service.issue(
            purpose=LinkPurpose.TALENT_POOL_CONSENT,
            application_id=application_id,
            expires_at=now + timedelta(days=2),
            now=now,
        )
        token = new.url.rsplit("/", 1)[-1]
        with pytest.raises(AppError):
            await service.verify(old.url.rsplit("/", 1)[-1], now=now)
        with pytest.raises(AppError):
            await service.verify(token, now=now + timedelta(days=2))
        stored = await session.scalar(
            text("SELECT token_hash FROM response_links WHERE id=:id"), {"id": new.id}
        )
        assert token not in stored and len(stored) == 64

    async def consume():
        try:
            async with session_factory.begin() as session:
                await ResponseLinkService(session, "https://example.test").mark_used(
                    token, LinkOutcome.ACCEPTED, now=now
                )
            return True
        except AppError:
            return False

    assert sorted(await asyncio.gather(consume(), consume())) == [False, True]
    async with session_factory.begin() as session:
        assert not await ResponseLinkService(session, "https://example.test").invalidate(new.id)


async def test_interview_constraints_and_adjacent_slots(application_id, session_factory):
    from sqlalchemy.exc import IntegrityError

    async with session_factory.begin() as session:
        actor = await session.scalar(text("SELECT created_by FROM job_postings LIMIT 1"))
        first = await session.scalar(
            text(
                "INSERT INTO interviews(application_id,interviewer_id,"
                "start_at,end_at,auto_scheduled,created_by) VALUES (:app,:actor,"
                "'2026-12-01 03:00Z','2026-12-01 04:00Z',false,:actor) RETURNING id"
            ),
            {"app": application_id, "actor": actor},
        )
        assert first
        for start, end in (
            ("2026-12-01 03:30Z", "2026-12-01 04:30Z"),
            ("2026-12-01 05:00Z", "2026-12-01 04:00Z"),
        ):
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(
                        text(
                            "INSERT INTO interviews(application_id,interviewer_id,"
                            "start_at,end_at,auto_scheduled,created_by) VALUES (:app,:actor,"
                            "CAST(CAST(:s AS text) AS timestamptz),"
                            "CAST(CAST(:e AS text) AS timestamptz),false,:actor)"
                        ),
                        {"app": application_id, "actor": actor, "s": start, "e": end},
                    )


async def test_invalidate_and_wrong_purpose(application_id, session_factory):
    now = now_utc()
    async with session_factory.begin() as session:
        service = ResponseLinkService(session, "https://example.test")
        issued = await service.issue(
            purpose=LinkPurpose.TALENT_POOL_CONSENT,
            application_id=application_id,
            expires_at=now + timedelta(days=2),
            now=now,
        )
        token = issued.url.rsplit("/", 1)[-1]
        with pytest.raises(AppError):
            await service.verify(token, purpose=LinkPurpose.CONFIRM_INTERVIEW, now=now)
        with pytest.raises(AppError):
            await service.mark_used(token, LinkOutcome.RESCHEDULE_REQUESTED, now=now)
        assert await service.invalidate(issued.id, now=now)
        assert not await service.invalidate(issued.id, now=now)
        with pytest.raises(AppError):
            await service.verify(token, now=now)


@pytest.mark.parametrize("terminal", ["SENT", "FAILED"])
async def test_consent_url_encrypted_and_masked_after_delivery(
    application_id, session_factory, settings, terminal
):
    from apply_support import ScriptedEmailService, outbox_row
    from pydantic import SecretStr

    from app.integrations.email.errors import PermanentEmailError
    from app.modules.notifications.service import NotificationService
    from app.modules.notifications.worker import deliver_due_batch

    config = settings.model_copy(
        update={
            "outbox_encryption_key": SecretStr("response-link-test-key-0123456789abcdef"),
        }
    )
    now = now_utc()
    async with session_factory.begin() as session:
        issued = await ResponseLinkService(session, "https://example.test").issue(
            purpose=LinkPurpose.TALENT_POOL_CONSENT,
            application_id=application_id,
            expires_at=now + timedelta(days=2),
            now=now,
        )
        outbox_id = await NotificationService(config).enqueue(
            session,
            template_code="REJECT_THANK_YOU",
            to="candidate@example.test",
            application_id=application_id,
            vars={
                "full_name": "Candidate",
                "job_title": "Engineer",
                "consent_url": issued.url,
                "response_deadline": "01/12/2026 17:30",
            },
            secret_vars={"consent_url"},
        )
    token = issued.url.rsplit("/", 1)[-1]
    pending = await outbox_row(session_factory, outbox_id)
    assert token not in pending.body and issued.url not in pending.body
    sender = ScriptedEmailService(
        *([PermanentEmailError("smtp_550")] if terminal == "FAILED" else [])
    )
    await deliver_due_batch(session_factory, sender, config, now_utc())
    result = await outbox_row(session_factory, outbox_id)
    assert result.status == terminal
    assert token not in result.body and issued.url not in result.body
    assert issued.url in sender.attempted[0].text_body
