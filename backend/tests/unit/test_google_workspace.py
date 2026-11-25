from datetime import UTC, datetime, timedelta

from app.integrations.google_workspace.client import FakeGoogleWorkspace


async def test_fake_event_lifecycle_and_busy_intervals():
    google = FakeGoogleWorkspace()
    start = datetime(2026, 12, 1, 3, tzinfo=UTC)
    end = start + timedelta(hours=1)
    assert await google.free_busy(["iv@example.test"], start, end) == []
    event = await google.create_event("iv@example.test", start, end, "Interview")
    assert event.meet_link.startswith("https://meet.google.com/")
    assert await google.free_busy(["iv@example.test"], start, end) == [(start, end)]
    await google.cancel_event(event.event_id)
    assert await google.free_busy(["iv@example.test"], start, end) == []
