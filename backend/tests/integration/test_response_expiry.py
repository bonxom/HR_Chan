import asyncio
from uuid import uuid4

import pytest
from apply_support import apply_cleanup
from sqlalchemy import event, text
from test_interview_responses import response_world, submit

from app.core.exceptions import AppError
from app.integrations.google_workspace.client import FakeGoogleWorkspace, GoogleWorkspaceError
from app.modules.responses.calendar_sync import CalendarCancellationSweep
from app.modules.responses.expiry import expire_response_links

__all__ = ["response_world", "apply_cleanup"]


@pytest.mark.parametrize("mode", ["late", "retry"])
async def test_expiry_revisits_older_links_despite_continuous_arrivals(
    response_world, session_factory, settings, monkeypatch, mode
):
    from app.modules.responses import expiry

    _, application_id, _, _ = response_world
    async with session_factory.begin() as session:
        await session.execute(text("DELETE FROM response_links"))

    async def add_link(expired=True):
        async with session_factory.begin() as session:
            return await session.scalar(
                text(
                    "INSERT INTO response_links"
                    "(token_hash,purpose,application_id,created_at,expires_at)"
                    " VALUES (:hash,'TALENT_POOL_CONSENT',:application_id,"
                    "clock_timestamp()-interval '3 days',"
                    "clock_timestamp()+CASE WHEN :expired THEN interval '-1 second'"
                    " ELSE interval '1 day' END) RETURNING id"
                ),
                {"hash": uuid4().hex, "application_id": application_id, "expired": expired},
            )

    older_id = await add_link(expired=mode == "retry")
    await add_link()
    recovered = False
    real_notify = expiry.notify_expired

    async def notify(session, config, context):
        if context.link.id == older_id and not recovered:
            raise RuntimeError("temporarily unavailable")
        await real_notify(session, config, context)

    monkeypatch.setattr(expiry, "notify_expired", notify)
    sweep = expiry.ResponseExpirySweep(session_factory, settings, batch_size=1)
    await sweep.run()
    if mode == "retry":
        await sweep.run()
    recovered = True
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "UPDATE response_links SET expires_at=clock_timestamp()-interval '1 second'"
                " WHERE id=:id"
            ),
            {"id": older_id},
        )
    for _ in range(4):
        await add_link()
        await sweep.run()
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT outcome::text FROM response_links WHERE id=:id"), {"id": older_id}
            )
            == "EXPIRED"
        )


@pytest.mark.parametrize("mode", ["late", "retry"])
async def test_calendar_revisits_older_events_despite_continuous_arrivals(
    response_world, session_factory, settings, mode
):
    _, _, older_id, token = response_world
    await submit(session_factory, settings, token, "DECLINED", "Bận")
    async with session_factory.begin() as session:
        await session.execute(
            text("UPDATE interviews SET needs_manual_calendar_fix=:pending WHERE id=:id"),
            {"pending": mode == "retry", "id": older_id},
        )

    async def add_event():
        async with session_factory.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO interviews(application_id,interviewer_id,start_at,end_at,"
                    "status,auto_scheduled,created_by,google_event_id,needs_manual_calendar_fix)"
                    " SELECT application_id,interviewer_id,start_at,end_at,'CANCELLED',"
                    "auto_scheduled,created_by,:event,true FROM interviews WHERE id=:id"
                ),
                {"id": older_id, "event": uuid4().hex},
            )

    class RecoveringGoogle:
        recovered = False

        async def cancel_event(self, event_id):
            if event_id == "fake-event" and not self.recovered:
                raise GoogleWorkspaceError("temporarily unavailable")

    google = RecoveringGoogle()
    sweep = CalendarCancellationSweep(session_factory, google, batch_size=1)
    await add_event()
    await sweep.run()
    if mode == "retry":
        await sweep.run()
    google.recovered = True
    async with session_factory.begin() as session:
        await session.execute(
            text("UPDATE interviews SET needs_manual_calendar_fix=true WHERE id=:id"),
            {"id": older_id},
        )
    for _ in range(4):
        await add_event()
        await sweep.run()
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"),
                {"id": older_id},
            )
            is False
        )


async def expire_now(session_factory):
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "UPDATE response_links SET created_at=clock_timestamp()-interval '3 days',"
                "expires_at=clock_timestamp()-interval '1 second'"
            )
        )


async def test_expiry_once_and_calendar_retry(response_world, session_factory, settings):
    _, aid, iid, token = response_world
    await expire_now(session_factory)
    await asyncio.gather(*(expire_response_links(session_factory, settings) for _ in range(2)))
    assert await expire_response_links(session_factory, settings) == 0
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT outcome::text,used_at,invalidated_at FROM response_links")
            )
        ).one()
        assert row.outcome == "EXPIRED" and row.used_at is not None and row.invalidated_at is None
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 3
        assert (
            await session.scalar(
                text("SELECT status::text FROM applications WHERE id=:id"), {"id": aid}
            )
            == "INTERVIEW_DECLINED"
        )
    with pytest.raises(AppError):
        await submit(session_factory, settings, token, "ACCEPTED")
    google = FakeGoogleWorkspace()
    google.fail_cancel = True
    sweep = CalendarCancellationSweep(session_factory, google)
    assert await sweep.run() == 0
    async with session_factory() as session:
        assert await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": iid}
        )
    google.fail_cancel = False
    await sweep.run()  # wrap the cursor
    assert await sweep.run() == 1
    async with session_factory() as session:
        assert not await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": iid}
        )
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 3


@pytest.mark.parametrize("action", ["ACCEPTED", "RESCHEDULE_REQUESTED"])
async def test_consumed_response_cannot_expire(response_world, session_factory, settings, action):
    _, _, iid, token = response_world
    await submit(session_factory, settings, token, action, "Đổi buổi")
    await expire_now(session_factory)
    assert await expire_response_links(session_factory, settings) == 0
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT status::text FROM interviews WHERE id=:id"), {"id": iid}
            )
            != "CANCELLED"
        )


async def test_invalidated_response_skips_expiry(response_world, session_factory, settings):
    await expire_now(session_factory)
    async with session_factory.begin() as session:
        await session.execute(text("UPDATE response_links SET invalidated_at=clock_timestamp()"))
    assert await expire_response_links(session_factory, settings) == 0
    async with session_factory() as session:
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 0


async def test_stale_interview_is_invalidated(response_world, session_factory, settings):
    _, _, iid, _ = response_world
    await expire_now(session_factory)
    async with session_factory.begin() as session:
        await session.execute(
            text("UPDATE interviews SET status='CONFIRMED' WHERE id=:id"), {"id": iid}
        )
    assert await expire_response_links(session_factory, settings) == 0
    async with session_factory() as session:
        assert await session.scalar(text("SELECT invalidated_at FROM response_links")) is not None
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 0


async def test_retry_cursor_advances_past_failed_event(response_world, session_factory, settings):
    _, _, iid, token = response_world
    await submit(session_factory, settings, token, "DECLINED", "Bận")
    async with session_factory.begin() as session:
        # A completed/cancelled second record can coexist with the first.
        second = await session.scalar(
            text(
                "INSERT INTO interviews(application_id,interviewer_id,start_at,end_at,status,"
                "auto_scheduled,created_by,google_event_id,needs_manual_calendar_fix)"
                " SELECT application_id,interviewer_id,start_at,end_at,'CANCELLED',"
                " auto_scheduled,created_by,'second-event',true FROM interviews"
                " WHERE id=:id RETURNING id"
            ),
            {"id": iid},
        )

    class SelectiveGoogle:
        async def cancel_event(self, event_id):
            if event_id == "fake-event":
                raise GoogleWorkspaceError("failure")

    sweep = CalendarCancellationSweep(session_factory, SelectiveGoogle(), batch_size=1)
    assert await sweep.run() == 0
    assert await sweep.run() == 1
    async with session_factory() as session:
        assert not await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": second}
        )


async def test_expiry_cursor_bounds_work_and_retries_failed_rows(
    response_world, session_factory, settings, monkeypatch
):
    from app.modules.responses import expiry

    _, aid, _, _ = response_world
    async with session_factory.begin() as session:
        # Consent links have independent expiry decisions and no interview side effects.
        await session.execute(text("DELETE FROM response_links"))
        ids = list(
            await session.scalars(
                text(
                    "INSERT INTO response_links"
                    " (token_hash,purpose,application_id,created_at,expires_at)"
                    " SELECT md5(n::text),'TALENT_POOL_CONSENT',:aid,"
                    " clock_timestamp()-interval '3 days',clock_timestamp()-interval '1 second'"
                    " FROM generate_series(1,4) n RETURNING id"
                ),
                {"aid": aid},
            )
        )
    real_notify = expiry.notify_expired
    attempts = []

    async def fail_first_batch(session, settings, context):
        attempts.append(context.link.id)
        if context.link.id in ids[:2]:
            raise RuntimeError("permanent row failure")
        await real_notify(session, settings, context)

    monkeypatch.setattr(expiry, "notify_expired", fail_first_batch)
    sweep = expiry.ResponseExpirySweep(session_factory, settings, batch_size=2)
    assert await sweep.run() == 0
    assert attempts == ids[:2]
    assert await sweep.run() == 2
    assert attempts == ids
    await sweep.run()  # Reaching the end wraps the next bounded sweep.
    assert await sweep.run() == 0
    assert attempts == ids + ids[:2]
    async with session_factory() as session:
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 4


async def test_response_waits_for_parent_while_expiry_skips_locked_parent(
    response_world, session_factory, settings, db_engine
):
    _, aid, iid, token = response_world
    waiting = asyncio.Event()

    def observe_parent_lock(connection, cursor, statement, parameters, context, many):
        if "FROM applications" in statement and "FOR UPDATE" in statement:
            waiting.set()

    async with session_factory.begin() as owner:
        await owner.execute(
            text("SELECT id FROM applications WHERE id=:id FOR UPDATE"), {"id": aid}
        )
        await owner.execute(
            text(
                "UPDATE response_links SET created_at=clock_timestamp()-interval '3 days',"
                " expires_at=clock_timestamp()-interval '1 second'"
            )
        )
    # Keep only the parent lock; the response must not lock its children before it.
    async with session_factory.begin() as owner:
        await owner.execute(
            text("SELECT id FROM applications WHERE id=:id FOR UPDATE"), {"id": aid}
        )
        event.listen(db_engine.sync_engine, "before_cursor_execute", observe_parent_lock)
        task = asyncio.create_task(submit(session_factory, settings, token, "ACCEPTED"))
        try:
            await asyncio.wait_for(waiting.wait(), 3)
            async with session_factory.begin() as probe:
                await probe.execute(
                    text("SELECT id FROM interviews WHERE id=:id FOR UPDATE NOWAIT"), {"id": iid}
                )
                await probe.execute(text("SELECT id FROM response_links FOR UPDATE NOWAIT"))
            assert await asyncio.wait_for(expire_response_links(session_factory, settings), 3) == 0
            assert not task.done()
        finally:
            event.remove(db_engine.sync_engine, "before_cursor_execute", observe_parent_lock)
    with pytest.raises(AppError) as failure:
        await asyncio.wait_for(task, 3)
    assert failure.value.code == "invalid_response_link"
    assert await expire_response_links(session_factory, settings) == 1


async def test_calendar_success_before_database_failure_recovers_after_restart(
    response_world, session_factory, settings, db_engine
):
    _, _, iid, token = response_world
    await submit(session_factory, settings, token, "DECLINED", "Busy")

    class IdempotentGoogle:
        calls = 0
        cancelled = False

        async def cancel_event(self, event_id):
            assert event_id == "fake-event"
            assert db_engine.pool.checkedout() == 0
            self.calls += 1
            self.cancelled = True

    def fail_flag_clear(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE interviews SET needs_manual_calendar_fix"):
            raise RuntimeError("process failed after remote cancellation")

    google = IdempotentGoogle()
    event.listen(db_engine.sync_engine, "before_cursor_execute", fail_flag_clear)
    try:
        assert await CalendarCancellationSweep(session_factory, google).run() == 0
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", fail_flag_clear)
    assert google.cancelled
    async with session_factory() as session:
        assert await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": iid}
        )
    assert await CalendarCancellationSweep(session_factory, google).run() == 1
    assert google.calls == 2
    async with session_factory() as session:
        assert not await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": iid}
        )
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 2


async def test_calendar_timeout_keeps_flag_and_advances_cursor(
    response_world, session_factory, settings
):
    _, _, iid, token = response_world
    await submit(session_factory, settings, token, "DECLINED", "Busy")

    class HangingGoogle:
        async def cancel_event(self, event_id):
            await asyncio.Event().wait()

    sweep = CalendarCancellationSweep(session_factory, HangingGoogle(), timeout=0.01)
    assert await asyncio.wait_for(sweep.run(), 3) == 0
    assert sweep.cursor == iid
    async with session_factory() as session:
        assert await session.scalar(
            text("SELECT needs_manual_calendar_fix FROM interviews WHERE id=:id"), {"id": iid}
        )
