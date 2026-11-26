import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from application_flow_support import FailingTrigger
from apply_support import apply_cleanup, build_world, insert_application
from sqlalchemy import text

from app.core.exceptions import AppError
from app.core.response_links import ResponseLinkService
from app.modules.responses.schemas import SubmitIn
from app.modules.responses.service import CandidateResponseService

__all__ = ["apply_cleanup"]


@pytest.fixture
async def response_world(apply_cleanup, session_factory):
    world = await build_world(session_factory)
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "INSERT INTO system_settings(key,value,default_value,min_value,max_value) VALUES"
                " ('max_reschedule_requests',2,2,0,5),('reschedule_handle_days',1,1,1,3)"
                " ON CONFLICT(key) DO NOTHING"
            )
        )
        aid = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            status="INTERVIEW_INVITED",
        )
        iid = await session.scalar(
            text(
                "INSERT INTO interviews(application_id,interviewer_id,start_at,end_at,"
                "auto_scheduled,created_by,google_event_id,meet_link) VALUES"
                " (:app,:hr,:start,:end,false,:hr,'fake-event','https://meet.google.com/abc-defg-hij')"
                " RETURNING id"
            ),
            {
                "app": aid,
                "hr": world.hr_id,
                "start": now + timedelta(days=5),
                "end": now + timedelta(days=5, hours=1),
            },
        )
        link = await ResponseLinkService(session, "http://localhost").issue(
            purpose="CONFIRM_INTERVIEW",
            application_id=aid,
            interview_id=iid,
            expires_at=now + timedelta(days=2),
            now=now,
        )
    return world, aid, iid, link.url.rsplit("/", 1)[-1]


async def submit(session_factory, settings, token, action, note=None):
    async with session_factory() as session:
        return await CandidateResponseService(session, settings).submit(
            SubmitIn(token=token, action=action, note=note)
        )


@pytest.mark.parametrize(
    ("action", "interview_state", "application_state"),
    [
        ("ACCEPTED", "CONFIRMED", "INTERVIEW_CONFIRMED"),
        ("DECLINED", "CANCELLED", "INTERVIEW_DECLINED"),
        ("RESCHEDULE_REQUESTED", "RESCHEDULE_REQUESTED", "INTERVIEW_INVITED"),
    ],
)
async def test_interview_response_is_atomic_and_single_use(
    response_world, session_factory, settings, action, interview_state, application_state
):
    _, aid, iid, token = response_world
    result = await submit(session_factory, settings, token, action, "Ghi chú")
    assert result["interview_status"] == interview_state
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT a.status::text,a.version,i.status::text,i.needs_manual_calendar_fix,"
                    "l.outcome::text,l.used_at FROM applications a JOIN interviews i"
                    " ON i.application_id=a.id JOIN response_links l ON l.interview_id=i.id"
                    " WHERE a.id=:id"
                ),
                {"id": aid},
            )
        ).one()
        assert row[:3] == (application_state, 2, interview_state)
        assert row.needs_manual_calendar_fix == (action == "DECLINED")
        assert row.outcome == action and row.used_at is not None
        count = await session.scalar(text("SELECT count(*) FROM email_outbox"))
        assert count == (2 if action == "DECLINED" else 1)
        receipt = await CandidateResponseService(session, settings).resolve(token)
        assert set(receipt) == {"completed", "outcome", "completed_at"}
    with pytest.raises(AppError):
        await submit(session_factory, settings, token, action, "Ghi chú")


@pytest.mark.parametrize("action", ["DECLINED", "RESCHEDULE_REQUESTED"])
@pytest.mark.parametrize("note", ["", "  "])
async def test_missing_note_preserves_link(response_world, session_factory, settings, action, note):
    _, _, _, token = response_world
    with pytest.raises(AppError) as failure:
        await submit(session_factory, settings, token, action, note)
    assert failure.value.status_code == 422
    async with session_factory() as session:
        assert await session.scalar(text("SELECT used_at FROM response_links")) is None


async def test_third_reschedule_request_is_blocked(response_world, session_factory, settings):
    _, aid, _, token = response_world
    async with session_factory.begin() as session:
        for _ in range(2):
            await session.execute(
                text(
                    "INSERT INTO audit_events(id,action,outcome,target_type,target_id,metadata)"
                    " VALUES(gen_random_uuid(),'interview.reschedule_requested','SUCCESS',"
                    "'application',:id,'{}')"
                ),
                {"id": str(aid)},
            )
    async with session_factory() as session:
        view = await CandidateResponseService(session, settings).resolve(token)
        assert not view["can_reschedule"]
        assert "RESCHEDULE_REQUESTED" not in view["allowed_actions"]
    with pytest.raises(AppError):
        await submit(session_factory, settings, token, "RESCHEDULE_REQUESTED", "Đổi buổi")


async def test_concurrent_submit_has_one_winner(response_world, session_factory, settings):
    _, _, _, token = response_world
    results = await asyncio.gather(
        *(submit(session_factory, settings, token, "ACCEPTED") for _ in range(2)),
        return_exceptions=True,
    )
    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(isinstance(item, AppError) for item in results) == 1
    async with session_factory() as session:
        assert await session.scalar(text("SELECT count(*) FROM email_outbox")) == 1


async def test_outbox_failure_rolls_back_decision(response_world, session_factory, settings):
    _, aid, _, token = response_world
    async with FailingTrigger(session_factory, "email_outbox"):
        with pytest.raises(AppError) as failure:
            await submit(session_factory, settings, token, "DECLINED", "Lý do")
        assert failure.value.status_code == 503
    async with session_factory() as session:
        assert await session.scalar(text("SELECT used_at FROM response_links")) is None
        assert (
            await session.scalar(
                text("SELECT status::text FROM applications WHERE id=:id"), {"id": aid}
            )
            == "INTERVIEW_INVITED"
        )
