"""Private shared event storage for the local development calendar."""

import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.integrations.google_workspace.client import (
    CalendarEvent,
    FakeGoogleWorkspace,
    GoogleWorkspaceError,
)


class SqliteFakeGoogleWorkspace(FakeGoogleWorkspace):
    def __init__(self, path: str | Path, busy_timeout: float = 1):
        super().__init__()
        self.path = str(path)
        self.busy_timeout = busy_timeout
        self._memory: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    @contextmanager
    def _connection(self):
        with self._lock:
            connection = None
            try:
                if self.path == ":memory:":
                    if self._memory is None:
                        self._memory = sqlite3.connect(
                            ":memory:", timeout=self.busy_timeout, check_same_thread=False
                        )
                    connection = self._memory
                else:
                    Path(self.path).parent.mkdir(parents=True, exist_ok=True)
                    connection = sqlite3.connect(self.path, timeout=self.busy_timeout)
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS events ("
                    "id TEXT PRIMARY KEY,email TEXT NOT NULL,start_at TEXT NOT NULL,"
                    "end_at TEXT NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0)"
                )
                with connection:
                    yield connection
            except (sqlite3.Error, OSError):
                raise GoogleWorkspaceError("fake_calendar_unavailable") from None
            finally:
                if connection is not None and self.path != ":memory:":
                    connection.close()

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if value.utcoffset() is None:
            raise GoogleWorkspaceError("invalid_calendar_time")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    async def create_event(self, email, start, end, title):
        if self.fail_create:
            raise GoogleWorkspaceError("create_failed")
        start_text, end_text = self._timestamp(start), self._timestamp(end)
        event_id = uuid4().hex

        def create():
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO events(id,email,start_at,end_at) VALUES(?,?,?,?)",
                    (event_id, email, start_text, end_text),
                )

        await asyncio.to_thread(create)
        return CalendarEvent(event_id, "https://meet.google.com/abc-defg-hij")

    async def free_busy(self, emails, start, end):
        configured = await super().free_busy(emails, start, end)
        if not emails:
            return configured
        start_text, end_text = self._timestamp(start), self._timestamp(end)

        def lookup():
            placeholders = ",".join("?" for _ in emails)
            with self._connection() as connection:
                return connection.execute(
                    f"SELECT start_at,end_at FROM events WHERE email IN ({placeholders})"
                    " AND cancelled=0 AND start_at < ? AND end_at > ?",
                    (*emails, end_text, start_text),
                ).fetchall()

        rows = await asyncio.to_thread(lookup)
        return configured + [
            (datetime.fromisoformat(first), datetime.fromisoformat(last)) for first, last in rows
        ]

    async def cancel_event(self, event_id):
        if self.fail_cancel:
            raise GoogleWorkspaceError("cancel_failed")

        def cancel():
            with self._connection() as connection:
                result = connection.execute("UPDATE events SET cancelled=1 WHERE id=?", (event_id,))
                if not result.rowcount:
                    raise GoogleWorkspaceError("unknown_calendar_event")

        await asyncio.to_thread(cancel)
        self.cancelled.append(event_id)

    async def update_event(self, event_id, start, end):
        start_text, end_text = self._timestamp(start), self._timestamp(end)

        def update():
            with self._connection() as connection:
                result = connection.execute(
                    "UPDATE events SET start_at=?,end_at=? WHERE id=? AND cancelled=0",
                    (start_text, end_text, event_id),
                )
                if not result.rowcount:
                    raise GoogleWorkspaceError("unknown_calendar_event")

        await asyncio.to_thread(update)

    def close(self):
        with self._lock:
            if self._memory is not None:
                self._memory.close()
                self._memory = None
