"""Retention dates on the company calendar (UTC+7)."""

from datetime import date, datetime, timedelta, timezone

COMPANY_TZ = timezone(timedelta(hours=7))


def deletion_due_date(closed_at: datetime | None) -> date | None:
    """Two calendar years after closing; leap-day anniversaries fall on February 28."""
    if closed_at is None:
        return None
    # Chuyển sang ngày công ty trước khi cộng năm; UTC có thể còn ở ngày hôm trước.
    closed = closed_at.astimezone(COMPANY_TZ).date()
    try:
        return closed.replace(year=closed.year + 2)
    except ValueError:
        # Ngày 29/2 không tồn tại ở năm đích thì lấy ngày cuối tháng 2 là 28/2.
        return closed.replace(year=closed.year + 2, day=28)
