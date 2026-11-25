"""Exercise the actual upgrade with two populated historical criteria versions."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from apply_support import insert_account, insert_criteria_set, insert_draft_job
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base

pytestmark = pytest.mark.database


def upgrade(connection, first, last):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
    with Operations.context(context):
        for revision in reversed(list(scripts.iterate_revisions(last, first))):
            revision.module.upgrade()


async def test_legacy_criteria_backfill_and_immutable_versions(db_engine):
    # All schema changes and test rows roll back together, including on failure.
    # Temporary enum OIDs must leave the process with this connection after rollback.
    async with create_async_engine(db_engine.url, poolclass=NullPool).connect() as connection:
        schema = "scoring_migration_" + uuid4().hex
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
        await connection.execute(text(f"SET LOCAL search_path = {schema}, public"))
        await connection.run_sync(upgrade, "base", "0005")
        actor = await insert_account(connection)
        job = await insert_draft_job(connection, created_by=actor)
        for version in (1, 2):
            criteria_set = await insert_criteria_set(
                connection, job_id=job, created_by=actor, version=version
            )
            await connection.execute(
                text(
                    "INSERT INTO criteria(criteria_set_id,name,description,is_mandatory,weight)"
                    " VALUES (:id,'Required','Technical',true,70),"
                    " (:id,'Optional','General',false,30)"
                ),
                {"id": criteria_set},
            )
        await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        # Force a later DDL failure and prove both the backfill and trigger change roll back.
        with pytest.raises(ProgrammingError, match="already exists"):
            async with connection.begin_nested():
                await connection.execute(text("CREATE TABLE application_scores (id integer)"))
                await connection.run_sync(upgrade, "0005", "0006")
        assert not await connection.scalar(
            text(
                "SELECT EXISTS (SELECT FROM pg_attribute WHERE attrelid='criteria'::regclass"
                " AND attname='min_score' AND NOT attisdropped)"
            )
        )
        assert await connection.scalar(
            text(
                "SELECT tgenabled = 'O' FROM pg_trigger WHERE tgrelid='criteria'::regclass"
                " AND tgname='criteria_immutable'"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO system_settings (key,value,min_value,max_value,default_value)"
                " VALUES ('hr_review_days',7,1,10,5)"
            )
        )
        await connection.run_sync(upgrade, "0005", "0006")
        assert (
            await connection.scalar(
                text("SELECT value FROM system_settings WHERE key='hr_review_days'")
            )
            == 7
        )
        await connection.execute(text("INSERT INTO holidays VALUES ('2026-11-30','Test holiday')"))
        assert await connection.scalar(
            text(
                "SELECT working_deadline('2026-11-27 18:00+07', 1)"
                " = timestamptz '2026-12-01 17:30+07'"
            )
        )
        result = await connection.execute(
            text("SELECT is_mandatory,min_score FROM criteria ORDER BY id")
        )
        assert result.all() == [(True, 50), (False, None)] * 2
        with pytest.raises(IntegrityError, match="immutable"):
            async with connection.begin_nested():
                await connection.execute(
                    text("UPDATE criteria SET min_score=75 WHERE is_mandatory")
                )
        for mandatory, floor in ((True, None), (False, 0), (True, 120)):
            with pytest.raises(IntegrityError, match="criteria_min_score_mandatory"):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "INSERT INTO criteria"
                            "(criteria_set_id,name,description,is_mandatory,weight,min_score)"
                            " VALUES (:id,'Invalid','Invalid',:mandatory,100,:floor)"
                        ),
                        {"id": criteria_set, "mandatory": mandatory, "floor": floor},
                    )
