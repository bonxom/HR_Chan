"""Upgrade the populated application schema without replacing business records."""

from uuid import uuid4

from apply_support import (
    insert_account,
    insert_application,
    insert_candidate,
    insert_criteria_set,
    insert_draft_job,
    insert_submission,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from test_scoring_migration import upgrade


async def test_0007_preserves_existing_application_rows(db_engine):
    async with create_async_engine(db_engine.url, poolclass=NullPool).connect() as connection:
        schema = "interview_migration_" + uuid4().hex
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
        await connection.execute(text(f"SET LOCAL search_path = {schema}, public"))
        await connection.run_sync(upgrade, "base", "0006")
        actor = await insert_account(connection)
        job = await insert_draft_job(connection, created_by=actor)
        criteria_set = await insert_criteria_set(connection, job_id=job, created_by=actor)
        candidate = await insert_candidate(connection)
        submission = await insert_submission(connection, candidate)
        application = await insert_application(
            connection, candidate, job, submission, criteria_set_id=criteria_set
        )
        before = (
            await connection.execute(
                text("SELECT * FROM applications WHERE id=:id"), {"id": application}
            )
        ).one()
        await connection.run_sync(upgrade, "0006", "0007")
        after = (
            await connection.execute(
                text("SELECT * FROM applications WHERE id=:id"), {"id": application}
            )
        ).one()
        assert before == after
        assert await connection.scalar(text("SELECT count(*) FROM interviews")) == 0
        assert await connection.scalar(text("SELECT count(*) FROM response_links")) == 0
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM accounts WHERE id=:id"), {"id": actor}
            )
            == 1
        )
