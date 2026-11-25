from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    meet_link: str


class GoogleWorkspaceError(Exception):
    pass


class IGoogleWorkspace(Protocol):
    async def free_busy(
        self, emails: list[str], start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]: ...
    async def create_event(
        self, email: str, start: datetime, end: datetime, title: str
    ) -> CalendarEvent: ...
    async def update_event(self, event_id: str, start: datetime, end: datetime) -> None: ...
    async def cancel_event(self, event_id: str) -> None: ...


class FakeGoogleWorkspace:
    def __init__(self):
        self.busy: dict[str, list[tuple[datetime, datetime]]] = {}
        self.events: dict[str, tuple[str, datetime, datetime]] = {}
        self.cancelled: list[str] = []
        self.fail_create = False
        self.fail_cancel = False
        self.fail_busy = False

    async def free_busy(self, emails, start, end):
        if self.fail_busy:
            raise GoogleWorkspaceError("free_busy_failed")
        intervals = [interval for email in emails for interval in self.busy.get(email, [])]
        intervals += [(a, b) for email, a, b in self.events.values() if email in emails]
        return [(a, b) for a, b in intervals if a < end and b > start]

    async def create_event(self, email, start, end, title):
        if self.fail_create:
            raise GoogleWorkspaceError("create_failed")
        event_id = uuid4().hex
        self.events[event_id] = (email, start, end)
        return CalendarEvent(event_id, "https://meet.google.com/abc-defg-hij")

    async def update_event(self, event_id, start, end):
        email, _, _ = self.events[event_id]
        self.events[event_id] = (email, start, end)

    async def cancel_event(self, event_id):
        if self.fail_cancel:
            raise GoogleWorkspaceError("cancel_failed")
        self.events.pop(event_id, None)
        self.cancelled.append(event_id)
