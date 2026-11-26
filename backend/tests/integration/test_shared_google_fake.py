"""The development calendar must survive independent API and worker processes."""

import multiprocessing
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.google_workspace.client import GoogleWorkspaceError


def create_in_process(path, result):
    import asyncio

    from app.integrations.google_workspace.sqlite_fake import SqliteFakeGoogleWorkspace

    async def create():
        start = datetime(2026, 12, 1, 3, tzinfo=UTC)
        event = await SqliteFakeGoogleWorkspace(path).create_event(
            "interviewer@example.test", start, start + timedelta(hours=1), "Interview"
        )
        result.put(event.event_id)

    asyncio.run(create())


def cancel_in_process(path, event_id):
    import asyncio

    from app.integrations.google_workspace.sqlite_fake import SqliteFakeGoogleWorkspace

    asyncio.run(SqliteFakeGoogleWorkspace(path).cancel_event(event_id))


async def test_calendar_shared_across_processes_and_restart(tmp_path):
    from app.integrations.google_workspace.sqlite_fake import SqliteFakeGoogleWorkspace

    path = str(tmp_path / "calendar.sqlite3")
    context = multiprocessing.get_context("spawn")
    result = context.Queue()
    creator = context.Process(target=create_in_process, args=(path, result))
    creator.start()
    creator.join(15)
    assert creator.exitcode == 0
    event_id = result.get(timeout=2)
    start = datetime(2026, 12, 1, 3, tzinfo=UTC)
    calendar = SqliteFakeGoogleWorkspace(path)
    assert await calendar.free_busy(["interviewer@example.test"], start, start + timedelta(hours=2))
    canceller = context.Process(target=cancel_in_process, args=(path, event_id))
    canceller.start()
    canceller.join(15)
    assert canceller.exitcode == 0
    assert (
        await calendar.free_busy(["interviewer@example.test"], start, start + timedelta(hours=2))
        == []
    )
    await SqliteFakeGoogleWorkspace(path).cancel_event(event_id)
    with pytest.raises(GoogleWorkspaceError):
        await calendar.cancel_event("unknown")
    result.close()
    result.join_thread()


async def test_calendar_busy_error_is_bounded_and_retryable(tmp_path):
    from app.integrations.google_workspace.sqlite_fake import SqliteFakeGoogleWorkspace

    path = str(tmp_path / "calendar.sqlite3")
    calendar = SqliteFakeGoogleWorkspace(path, busy_timeout=0.05)
    start = datetime(2026, 12, 1, 3, tzinfo=UTC)
    event = await calendar.create_event(
        "interviewer@example.test", start, start + timedelta(hours=1), ""
    )
    with sqlite3.connect(path) as blocker:
        blocker.execute("BEGIN EXCLUSIVE")
        with pytest.raises(GoogleWorkspaceError):
            await calendar.cancel_event(event.event_id)
        blocker.rollback()
    await calendar.cancel_event(event.event_id)


async def test_in_memory_calendar_retains_its_connection():
    from app.integrations.google_workspace.sqlite_fake import SqliteFakeGoogleWorkspace

    calendar = SqliteFakeGoogleWorkspace(":memory:")
    start = datetime(2026, 12, 1, 3, tzinfo=UTC)
    event = await calendar.create_event(
        "interviewer@example.test", start, start + timedelta(hours=1), ""
    )
    assert await calendar.free_busy(["interviewer@example.test"], start, start + timedelta(hours=2))
    await calendar.cancel_event(event.event_id)
    await calendar.cancel_event(event.event_id)
    calendar.close()


def test_factory_resolves_shared_relative_path_against_backend():
    from app.core.config import BACKEND_DIR, Settings
    from app.integrations.factories import build_google_workspace

    settings = Settings(_env_file=None, fake_google_db_path="local/calendar.sqlite3")
    calendar = build_google_workspace(settings)
    assert calendar.path == str(BACKEND_DIR / "local" / "calendar.sqlite3")
