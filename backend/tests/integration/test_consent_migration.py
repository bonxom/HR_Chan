from uuid import uuid4

import pytest
from apply_support import insert_account, insert_candidate, insert_draft_job
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from test_scoring_migration import upgrade


async def test_consent_upgrade_preserves_rows_and_guards_active_grants(db_engine):
    async with create_async_engine(db_engine.url, poolclass=NullPool).connect() as connection:
        schema = "consent_migration_" + uuid4().hex
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
        await connection.execute(text(f"SET LOCAL search_path={schema},public"))
        await connection.run_sync(upgrade, "base", "0007")
        account = await insert_account(connection)
        job = await insert_draft_job(connection, created_by=account)
        candidate = await insert_candidate(connection)
        await connection.run_sync(upgrade, "0007", "0008")
        assert await connection.scalar(text("SELECT id FROM job_postings")) == job
        query = text(
            "INSERT INTO talent_pool_consents(candidate_id,source,policy_ver,expires_at)"
            " VALUES(:candidate,'THANK_YOU_LINK','talent-pool-v1',now()+interval '1 year')"
        )
        await connection.execute(query, {"candidate": candidate})
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(query, {"candidate": candidate})
        assert (
            await connection.scalar(
                text("SELECT value FROM system_settings WHERE key='talent_pool_months'")
            )
            == 12
        )
