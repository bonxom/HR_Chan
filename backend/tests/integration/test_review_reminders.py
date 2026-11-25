import asyncio
from datetime import UTC, datetime

import pytest
from apply_support import apply_cleanup, build_world, insert_account, insert_application
from sqlalchemy import text

__all__ = ["apply_cleanup"]
pytestmark = pytest.mark.database


@pytest.mark.parametrize("mode", ["empty", "holiday", "weekend", "before_open", "inactive"])
async def test_digest_skips_ineligible_work(apply_cleanup, session_factory, settings, mode):
    from app.modules.applications.reminders import remind_overdue_reviews

    world = await build_world(session_factory)
    now = datetime(2026, 12, 9, 3, tzinfo=UTC)
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO system_settings(key,value_json) VALUES ('working_hours',"
                '\'{"start":"08:00","end":"17:30"}\') ON CONFLICT(key) DO NOTHING'
            )
        )
        if mode != "empty":
            aid = await insert_application(
                session,
                world.candidate_id,
                world.job_id,
                world.submission_id,
                status="PENDING_HR_REVIEW",
            )
            await session.execute(
                text("UPDATE applications SET review_due_at=:at WHERE id=:id"),
                {"at": datetime(2026, 12, 1, tzinfo=UTC), "id": aid},
            )
        if mode == "holiday":
            await session.execute(
                text(
                    "INSERT INTO holidays VALUES ('2026-12-09','Test holiday')"
                    " ON CONFLICT DO NOTHING"
                )
            )
        if mode == "inactive":
            await session.execute(
                text("UPDATE accounts SET status='LOCKED' WHERE id=:id"), {"id": world.hr_id}
            )
    if mode == "weekend":
        now = datetime(2026, 12, 12, 3, tzinfo=UTC)
    if mode == "before_open":
        now = datetime(2026, 12, 9, 0, tzinfo=UTC)
    assert await remind_overdue_reviews(session_factory, settings, now) == 0
    if mode == "holiday":
        async with session_factory.begin() as session:
            await session.execute(text("DELETE FROM holidays WHERE holiday_date='2026-12-09'"))


async def test_digest_is_atomic_and_catches_up(apply_cleanup, session_factory, settings):
    from app.modules.applications.reminders import remind_overdue_reviews

    world = await build_world(session_factory)
    now = datetime(2026, 12, 9, 3, tzinfo=UTC)
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO system_settings(key,value_json) VALUES ('working_hours',"
                '\'{"start":"08:00","end":"17:30"}\') ON CONFLICT(key) DO NOTHING'
            )
        )
        aid = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            status="PENDING_HR_REVIEW",
            review_due_at=datetime(2026, 12, 8, tzinfo=UTC),
        )
        await session.execute(
            text("UPDATE applications SET review_due_at=:due WHERE id=:id"),
            {"due": datetime(2026, 12, 8, tzinfo=UTC), "id": aid},
        )
    await asyncio.gather(
        *(remind_overdue_reviews(session_factory, settings, now) for _ in range(2))
    )
    await remind_overdue_reviews(session_factory, settings, now)
    async with session_factory() as session:
        assert (
            await session.scalar(
                text(
                    "SELECT count(*) FROM email_outbox WHERE template_code='REVIEW_OVERDUE_DIGEST'"
                )
            )
            == 1
        )
    async with session_factory.begin() as session:
        await insert_account(session, roles=["HR"])
    assert await remind_overdue_reviews(session_factory, settings, now) == 1
    assert await remind_overdue_reviews(session_factory, settings, now.replace(day=10)) == 2
