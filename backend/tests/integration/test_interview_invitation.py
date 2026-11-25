import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from application_flow_support import FailingTrigger
from apply_support import apply_cleanup, build_world, insert_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import AppError
from app.core.interview_scheduler import InterviewScheduler
from app.core.security import Principal, get_current_principal
from app.integrations.google_workspace.client import FakeGoogleWorkspace
from app.main import create_app
from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountType, EmployeeRole
from app.modules.applications.invitation_service import InterviewInvitationService
from app.modules.notifications.seeds import seed_email_templates

__all__ = ["apply_cleanup"]
pytestmark = pytest.mark.database
NOW = datetime(2026, 11, 25, 3, tzinfo=UTC)
START = datetime(2026, 11, 30, 3, tzinfo=UTC)


@pytest.fixture
async def invitation_world(apply_cleanup, session_factory, settings, monkeypatch):
    monkeypatch.setattr("app.core.clock.utcnow", lambda: NOW)
    world = await build_world(session_factory)
    async with session_factory.begin() as session:
        await session.execute(
            text("INSERT INTO job_interviewers(job_id,user_id) VALUES(:job,:hr)"),
            {"job": world.job_id, "hr": world.hr_id},
        )
        application_id = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            status="PENDING_HR_REVIEW",
        )
        await seed_email_templates(session)
    return world, application_id


async def invoke(session_factory, settings, google, world, application_id, **kwargs):
    async with session_factory() as session:
        return await InterviewInvitationService(session, settings, google, session_factory).invite(
            application_id, world.hr_id, START, 1, **kwargs
        )


async def test_invite_persists_interview_and_secret_link(
    invitation_world, session_factory, settings
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    result = await invoke(session_factory, settings, google, world, application_id)
    assert result["status"] == "INTERVIEW_INVITED"
    async with session_factory() as session:
        row = (await session.execute(text("SELECT * FROM interviews"))).one()
        assert row.end_at == START + timedelta(hours=1)
        assert row.auto_scheduled is False
        link = (await session.execute(text("SELECT * FROM response_links"))).one()
        assert len(link.token_hash) == 64
        body = await session.scalar(text("SELECT body FROM email_outbox"))
        assert "/r/" not in body
        assert len(google.events) == 1


@pytest.mark.parametrize("failure", ["google", "database"])
async def test_failure_keeps_application_pending(
    invitation_world, session_factory, settings, failure
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    if failure == "google":
        google.fail_create = True
        with pytest.raises(AppError, match="Không tạo"):
            await invoke(session_factory, settings, google, world, application_id)
    else:
        async with FailingTrigger(session_factory, "response_links"):
            with pytest.raises(DBAPIError):
                await invoke(session_factory, settings, google, world, application_id)
        assert len(google.cancelled) == 1
    assert google.events == {}
    async with session_factory() as session:
        assert await session.scalar(text("SELECT status FROM applications")) == "PENDING_HR_REVIEW"


async def test_scheduler_holiday_closing_and_adjacency(invitation_world, session_factory):
    world, _ = invitation_world
    async with session_factory() as session:
        google = FakeGoogleWorkspace()
        interviewer = await session.get(Account, world.hr_id)
        scheduler = InterviewScheduler(session, google)
        slots = await scheduler.suggest(interviewer, NOW.date(), START.date(), NOW)
        assert len(slots) == 5
        assert slots[0]["start_at"].isoformat() == "2026-11-30T08:00:00+07:00"
        await scheduler.validate(interviewer, START, NOW)
        await google.create_event(interviewer.email, START, START + timedelta(hours=1), "")
        await scheduler.validate(interviewer, START + timedelta(hours=1), NOW)
        await scheduler.validate(interviewer, START + timedelta(hours=1, minutes=15), NOW)
        with pytest.raises(AppError):
            await scheduler.validate(interviewer, START.replace(hour=10), NOW)


async def test_two_applications_race_cancels_losing_event(
    invitation_world, session_factory, settings
):
    world, application_id = invitation_world
    other = await build_world(session_factory)
    async with session_factory.begin() as session:
        await session.execute(
            text("INSERT INTO job_interviewers(job_id,user_id) VALUES(:job,:hr)"),
            {"job": other.job_id, "hr": world.hr_id},
        )
        second_id = await insert_application(
            session,
            other.candidate_id,
            other.job_id,
            other.submission_id,
            status="PENDING_HR_REVIEW",
        )

    class RacingGoogle(FakeGoogleWorkspace):
        def __init__(self):
            super().__init__()
            self.ready = asyncio.Event()
            self.started = 0

        async def create_event(self, *args):
            event = await super().create_event(*args)
            self.started += 1
            if self.started == 2:
                self.ready.set()
            await self.ready.wait()
            return event

        async def free_busy(self, emails, start, end):
            # Both calendar reads race before either newly created event is visible.
            return []

    google = RacingGoogle()
    results = await asyncio.wait_for(
        asyncio.gather(
            invoke(session_factory, settings, google, world, application_id),
            invoke(session_factory, settings, google, other, second_id),
            return_exceptions=True,
        ),
        timeout=10,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    failure = next(result for result in results if isinstance(result, Exception))
    assert isinstance(failure, AppError) and failure.status_code == 409
    assert len(google.events) == len(google.cancelled) == 1


@pytest.mark.parametrize("committed", [False, True])
async def test_ambiguous_commit_reconciles_event(
    invitation_world, session_factory, settings, committed
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    async with session_factory() as session:
        original = session.commit

        async def uncertain_commit():
            if committed:
                await original()
            raise ConnectionError("commit outcome unknown")

        session.commit = uncertain_commit
        with pytest.raises(ConnectionError):
            await InterviewInvitationService(session, settings, google, session_factory).invite(
                application_id, world.hr_id, START, 1
            )
    assert len(google.events) == int(committed)
    assert len(google.cancelled) == int(not committed)


async def test_holiday_and_calendar_busy_are_excluded(invitation_world, session_factory):
    world, _ = invitation_world
    async with session_factory.begin() as session:
        interviewer = await session.get(Account, world.hr_id)
        google = FakeGoogleWorkspace()
        scheduler = InterviewScheduler(session, google)
        google.busy[interviewer.email] = [(START, START + timedelta(hours=1))]
        with pytest.raises(AppError, match="vừa có người"):
            await scheduler.validate(interviewer, START, NOW)
        await session.execute(
            text("INSERT INTO holidays(holiday_date,name) VALUES('2026-11-30','test holiday')")
        )
        try:
            assert await scheduler.suggest(interviewer, NOW.date(), START.date(), NOW) == []
            with pytest.raises(AppError, match="không hợp lệ"):
                await scheduler.validate(interviewer, START, NOW)
        finally:
            await session.execute(text("DELETE FROM holidays WHERE holiday_date='2026-11-30'"))


@pytest.mark.parametrize(
    "start",
    [
        datetime(2026, 11, 28, 3, tzinfo=UTC),
        datetime(2026, 11, 27, 3, tzinfo=UTC),
        datetime(2026, 11, 30, 0, 30, tzinfo=UTC),
        datetime(2026, 11, 30, 10, tzinfo=UTC),
    ],
)
async def test_invalid_hours_or_early_date_rejected(invitation_world, session_factory, start):
    world, _ = invitation_world
    async with session_factory() as session:
        interviewer = await session.get(Account, world.hr_id)
        with pytest.raises(AppError, match="không hợp lệ"):
            await InterviewScheduler(session, FakeGoogleWorkspace()).validate(
                interviewer, start, NOW
            )


@pytest.mark.parametrize("status", ["SCHEDULED", "CONFIRMED", "RESCHEDULE_REQUESTED"])
async def test_active_database_interviews_block_slots(invitation_world, session_factory, status):
    world, application_id = invitation_world
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO interviews(application_id,interviewer_id,start_at,end_at,status,"
                "auto_scheduled,created_by,reschedule_note) VALUES(:app,:hr,:start,:end,"
                "CAST(:status AS interview_status),false,:hr,'Requested')"
            ),
            {
                "app": application_id,
                "hr": world.hr_id,
                "start": START,
                "end": START + timedelta(hours=1),
                "status": status,
            },
        )
        interviewer = await session.get(Account, world.hr_id)
        scheduler = InterviewScheduler(session, FakeGoogleWorkspace())
        with pytest.raises(AppError, match="vừa có người"):
            await scheduler.validate(interviewer, START, NOW)
        await scheduler.validate(interviewer, START + timedelta(hours=1), NOW)


async def test_stale_version_never_creates_event(invitation_world, session_factory, settings):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    async with session_factory() as session:
        with pytest.raises(AppError) as error:
            await InterviewInvitationService(session, settings, google, session_factory).invite(
                application_id, world.hr_id, START, 99
            )
        assert error.value.status_code == 409
    assert google.events == {}


async def test_booking_deadlock_is_a_compensated_slot_conflict(
    invitation_world, session_factory, settings
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    async with session_factory.begin() as session:
        await session.execute(
            text("""
            CREATE FUNCTION test_booking_deadlock() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'booking deadlock' USING ERRCODE='40P01';
            END $$;
        """)
        )
        await session.execute(
            text(
                "CREATE TRIGGER test_booking_deadlock BEFORE INSERT ON interviews"
                " FOR EACH ROW EXECUTE FUNCTION test_booking_deadlock()"
            )
        )
    try:
        with pytest.raises(AppError) as failure:
            await invoke(session_factory, settings, google, world, application_id)
        assert failure.value.status_code == 409
        assert failure.value.code == "slot_conflict"
        assert len(google.cancelled) == 1
        assert google.events == {}
        async with session_factory() as session:
            assert (
                await session.scalar(
                    text("SELECT status FROM applications WHERE id=:id"), {"id": application_id}
                )
                == "PENDING_HR_REVIEW"
            )
    finally:
        async with session_factory.begin() as session:
            await session.execute(text("DROP TRIGGER test_booking_deadlock ON interviews"))
            await session.execute(text("DROP FUNCTION test_booking_deadlock()"))


async def test_failed_compensation_logs_event_identifier(
    invitation_world, session_factory, settings, caplog
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    google.fail_cancel = True
    async with FailingTrigger(session_factory, "response_links"):
        with pytest.raises(DBAPIError):
            await invoke(session_factory, settings, google, world, application_id)
    assert len(google.events) == 1
    event_id = next(iter(google.events))
    assert event_id in caplog.text


async def test_unresolved_commit_logs_identifier_without_cancelling(
    invitation_world, session_factory, settings, caplog
):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()

    def unavailable_factory():
        raise ConnectionError("database unavailable")

    async with session_factory() as session:

        async def uncertain_commit():
            raise ConnectionError("unknown commit outcome")

        session.commit = uncertain_commit
        with pytest.raises(ConnectionError):
            await InterviewInvitationService(session, settings, google, unavailable_factory).invite(
                application_id, world.hr_id, START, 1
            )
    assert len(google.events) == 1
    assert next(iter(google.events)) in caplog.text
    assert google.cancelled == []


async def test_exact_api_slots_and_invite_contract(invitation_world, session_factory, settings):
    world, application_id = invitation_world
    google = FakeGoogleWorkspace()
    app = create_app(settings, google_workspace=google)
    principal = Principal(
        account_id=world.hr_id,
        account_type=AccountType.EMPLOYEE,
        roles=(EmployeeRole.HR,),
        session_id=uuid4(),
        credential_version=1,
        session_absolute_expires_at=NOW + timedelta(hours=1),
    )
    app.dependency_overrides[get_current_principal] = lambda: principal
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            response = await client.get(
                f"/api/applications/{application_id}/interview-slots",
                params={"date_from": "2026-11-25", "date_to": "2026-11-30"},
            )
            assert response.status_code == 200, response.text
            assert len(response.json()) == 5
            payload = {"start_at": START.isoformat(), "version": 1}
            for extra in ({"end_at": START.isoformat()}, {"duration": 30}):
                response = await client.post(
                    f"/api/applications/{application_id}/invite", json=payload | extra
                )
                assert response.status_code == 422
            response = await client.post(f"/api/applications/{application_id}/invite", json=payload)
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "INTERVIEW_INVITED"
            assert "confirm_url" not in response.text
            response = await client.post(f"/api/applications/{application_id}/invite", json=payload)
            assert response.status_code == 409
