"""Single source of server time so tests can inject a controlled clock."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
