import asyncio
import logging

from sqlalchemy import func, select, update

from app.modules.interviews.models import Interview, InterviewStatus

logger = logging.getLogger(__name__)


class CalendarCancellationSweep:
    def __init__(self, session_factory, google, *, timeout=10, batch_size=32):
        self.session_factory = session_factory
        self.google = google
        self.timeout = timeout
        self.batch_size = batch_size
        self.cursor = 0
        self.upper_bound: int | None = None

    async def run(self):
        async with self.session_factory() as session:
            pending = select(Interview.id, Interview.google_event_id).where(
                Interview.status == InterviewStatus.CANCELLED,
                Interview.needs_manual_calendar_fix.is_(True),
                Interview.google_event_id.is_not(None),
                Interview.google_event_id != "",
            )
            if self.upper_bound is None:
                # Finish a finite pass before revisiting older pending events.
                self.upper_bound = await session.scalar(
                    pending.with_only_columns(func.max(Interview.id))
                )
                if self.upper_bound is None:
                    return 0
            pending = (
                pending.where(
                    Interview.id > self.cursor,
                    Interview.id <= self.upper_bound,
                )
                .order_by(Interview.id)
                .limit(self.batch_size)
            )
            rows = (await session.execute(pending)).all()
        if not rows:
            self.cursor = 0
            self.upper_bound = None
            return 0
        cleared = 0
        for interview_id, event_id in rows:
            self.cursor = interview_id
            try:
                # The PostgreSQL read transaction has closed before the adapter call.
                async with asyncio.timeout(self.timeout):
                    await self.google.cancel_event(event_id)
                async with self.session_factory.begin() as session:
                    result = await session.execute(
                        update(Interview)
                        .where(
                            Interview.id == interview_id,
                            Interview.google_event_id == event_id,
                            Interview.status == InterviewStatus.CANCELLED,
                            Interview.needs_manual_calendar_fix.is_(True),
                        )
                        .values(needs_manual_calendar_fix=False)
                    )
                    cleared += result.rowcount
            except Exception as exc:
                logger.error(
                    "Calendar cancellation pending for google_event_id=%s (%s)",
                    event_id,
                    type(exc).__name__,
                )
        return cleared
