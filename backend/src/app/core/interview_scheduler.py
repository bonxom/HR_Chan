from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.core.exceptions import AppError
from app.modules.interviews.models import Interview
from app.modules.settings.models import Holiday, SystemSetting

COMPANY_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ACTIVE = ("SCHEDULED", "CONFIRMED", "RESCHEDULE_REQUESTED")


class InterviewScheduler:
    def __init__(self, session, google, duration_minutes=60):
        self.session = session
        self.google = google
        self.duration = timedelta(minutes=duration_minutes)

    async def calendar(self):
        settings = await self.session.get(SystemSetting, "working_hours")
        hours = settings.value_json
        holidays = set(await self.session.scalars(select(Holiday.holiday_date)))
        return time.fromisoformat(hours["start"]), time.fromisoformat(hours["end"]), holidays

    async def deadline(self, now):
        return await self.session.scalar(
            text(
                "SELECT working_deadline(:now,value::integer) FROM system_settings"
                " WHERE key='response_deadline_days'"
            ),
            {"now": now},
        )

    async def earliest(self, now, holidays):
        day = (await self.deadline(now)).astimezone(COMPANY_TZ).date() + timedelta(days=1)
        while day.weekday() >= 5 or day in holidays:
            day += timedelta(days=1)
        return day

    async def validate(self, interviewer, start, now):
        if start.tzinfo is None or start.utcoffset() is None:
            raise AppError("Giờ phỏng vấn cần có múi giờ", 422, "invalid_slot")
        opening, closing, holidays = await self.calendar()
        local = start.astimezone(COMPANY_TZ)
        end = local + self.duration
        if (
            local.weekday() >= 5
            or local.date() in holidays
            or local.date() < await self.earliest(now, holidays)
            or local.time() < opening
            or end.date() != local.date()
            or end.time() > closing
        ):
            raise AppError("Giờ phỏng vấn không hợp lệ", 422, "invalid_slot")
        occupied = await self.session.scalar(
            select(Interview.id)
            .where(
                Interview.interviewer_id == interviewer.id,
                Interview.status.in_(ACTIVE),
                Interview.start_at < end,
                Interview.end_at > start,
            )
            .limit(1)
        )
        if occupied or await self.google.free_busy([interviewer.email], start, end):
            raise AppError("Khung giờ vừa có người đặt", 409, "slot_conflict")
        return end

    async def suggest(self, interviewer, date_from, date_to, now):
        opening, closing, holidays = await self.calendar()
        day = max(date_from, await self.earliest(now, holidays))
        result = []
        while day <= date_to and len(result) < 5:
            if day.weekday() < 5 and day not in holidays:
                start = datetime.combine(day, opening, COMPANY_TZ)
                limit = datetime.combine(day, closing, COMPANY_TZ)
                while start + self.duration <= limit and len(result) < 5:
                    try:
                        end = await self.validate(interviewer, start, now)
                        result.append({"start_at": start, "end_at": end})
                    except AppError as exc:
                        if exc.code != "slot_conflict":
                            raise
                    start += timedelta(minutes=30)
            if day == date_to:
                break
            day += timedelta(days=1)
        return result

    async def reserve(
        self,
        *,
        application_id,
        interviewer_id,
        start_at,
        end_at,
        status="SCHEDULED",
        auto_scheduled,
        created_by,
        google_event_id,
        meet_link,
    ):
        """Persist a validated reservation in the caller's transaction."""
        interview = Interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            start_at=start_at,
            end_at=end_at,
            status=status,
            auto_scheduled=auto_scheduled,
            created_by=created_by,
            google_event_id=google_event_id,
            meet_link=meet_link,
        )
        self.session.add(interview)
        await self.session.flush()
        return interview
