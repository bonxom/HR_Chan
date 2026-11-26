import asyncio
from datetime import timedelta

import pytest
from application_flow_support import FailingTrigger
from apply_support import apply_cleanup, build_world, insert_application
from sqlalchemy import select, text

from app.core.exceptions import AppError
from app.core.response_links import ResponseLinkService
from app.modules.candidates.consent_models import TalentPoolConsent
from app.modules.responses.schemas import SubmitIn
from app.modules.responses.service import CandidateResponseService

__all__ = ["apply_cleanup"]
pytestmark = pytest.mark.database


async def issue(session_factory, world=None):
    world = world or await build_world(session_factory)
    async with session_factory.begin() as session:
        application_id = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
        )
        now = await session.scalar(text("SELECT clock_timestamp()"))
        link = await ResponseLinkService(session, "https://candidate.test").issue(
            purpose="TALENT_POOL_CONSENT",
            application_id=application_id,
            now=now,
            expires_at=now + timedelta(days=2),
        )
    return world, link.url.rsplit("/", 1)[1]


async def resolve(session_factory, settings, token):
    async with session_factory() as session:
        return await CandidateResponseService(session, settings).resolve(token)


async def submit(session_factory, settings, token, view, action="ACCEPTED"):
    async with session_factory() as session:
        return await CandidateResponseService(session, settings).submit(
            SubmitIn(
                token=token,
                action=action,
                policy_ver=view["policy_ver"],
                consent_snapshot=view["consent_snapshot"],
            )
        )


async def test_grant_acknowledgement_and_terminal_receipt(apply_cleanup, session_factory, settings):
    world, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    assert view["consent_mode"] == "GRANT"
    assert view["retention_months"] == 12
    await submit(session_factory, settings, token, view)
    receipt = await resolve(session_factory, settings, token)
    assert set(receipt) == {"completed", "outcome", "completed_at"}
    assert receipt["outcome"] == "ACCEPTED"
    async with session_factory() as session:
        grant = await session.scalar(select(TalentPoolConsent))
        original = (grant.consented_at, grant.expires_at, grant.policy_ver)
        assert grant.expires_at > grant.consented_at + timedelta(days=360)
    async with session_factory.begin() as session:
        now = await session.scalar(text("SELECT clock_timestamp()"))
        link = await ResponseLinkService(session, "https://candidate.test").issue(
            purpose="TALENT_POOL_CONSENT",
            application_id=grant.application_id,
            now=now,
            expires_at=now + timedelta(days=2),
        )
    next_token = link.url.rsplit("/", 1)[1]
    ack = await resolve(session_factory, settings, next_token)
    assert ack["consent_mode"] == "ACKNOWLEDGE"
    assert ack["allowed_actions"] == ["ACCEPTED"]
    with pytest.raises(AppError) as error:
        await submit(session_factory, settings, next_token, ack, "DECLINED")
    assert error.value.status_code == 422
    await submit(session_factory, settings, next_token, ack)
    async with session_factory() as session:
        grant = await session.scalar(select(TalentPoolConsent))
        assert original == (grant.consented_at, grant.expires_at, grant.policy_ver)


async def test_concurrent_submit_wins_once_and_leaves_one_grant(
    apply_cleanup, session_factory, settings
):
    _, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    results = await asyncio.gather(
        submit(session_factory, settings, token, view),
        submit(session_factory, settings, token, view),
        return_exceptions=True,
    )
    assert sum(isinstance(value, dict) for value in results) == 1
    loser = next(value for value in results if isinstance(value, Exception))
    assert isinstance(loser, AppError) and loser.status_code == 422
    async with session_factory() as session:
        assert len(list(await session.scalars(select(TalentPoolConsent)))) == 1


async def test_stale_policy_and_validation_never_consume_link(
    apply_cleanup, session_factory, settings
):
    _, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    async with session_factory() as session:
        payload = SubmitIn(
            token=token,
            action="ACCEPTED",
            policy_ver="unknown",
            consent_snapshot=view["consent_snapshot"],
        )
        with pytest.raises(AppError) as error:
            await CandidateResponseService(session, settings).submit(payload)
        assert error.value.code == "policy_changed"
    assert (await resolve(session_factory, settings, token))["completed"] is False
    await submit(session_factory, settings, token, view, "DECLINED")
    async with session_factory() as session:
        assert len(list(await session.scalars(select(TalentPoolConsent)))) == 0


async def test_expired_and_revoked_grants_require_fresh_permission(
    apply_cleanup, session_factory, settings
):
    _, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    await submit(session_factory, settings, token, view)
    async with session_factory.begin() as session:
        grant = await session.scalar(select(TalentPoolConsent))
        app_id, grant_id = grant.application_id, grant.id
        grant.consented_at -= timedelta(days=800)
        grant.expires_at -= timedelta(days=800)
        now = await session.scalar(text("SELECT clock_timestamp()"))
        link = await ResponseLinkService(session, "https://candidate.test").issue(
            purpose="TALENT_POOL_CONSENT",
            application_id=app_id,
            now=now,
            expires_at=now + timedelta(days=2),
        )
    token = link.url.rsplit("/", 1)[1]
    await submit(session_factory, settings, token, await resolve(session_factory, settings, token))
    async with session_factory.begin() as session:
        grant = await session.scalar(select(TalentPoolConsent))
        assert grant.id == grant_id
        grant.revoked_at = await session.scalar(text("SELECT clock_timestamp()"))
        now = grant.revoked_at
        link = await ResponseLinkService(session, "https://candidate.test").issue(
            purpose="TALENT_POOL_CONSENT",
            application_id=app_id,
            now=now,
            expires_at=now + timedelta(days=2),
        )
    token = link.url.rsplit("/", 1)[1]
    await submit(session_factory, settings, token, await resolve(session_factory, settings, token))
    async with session_factory() as session:
        assert len(list(await session.scalars(select(TalentPoolConsent)))) == 2


async def test_two_applications_serialize_candidate_and_refresh_stale_view(
    apply_cleanup, session_factory, settings
):
    world, first = await issue(session_factory)
    other = await build_world(session_factory)
    async with session_factory.begin() as session:
        app_id = await insert_application(
            session, world.candidate_id, other.job_id, world.submission_id
        )
        now = await session.scalar(text("SELECT clock_timestamp()"))
        link = await ResponseLinkService(session, "https://candidate.test").issue(
            purpose="TALENT_POOL_CONSENT",
            application_id=app_id,
            now=now,
            expires_at=now + timedelta(days=2),
        )
    second = link.url.rsplit("/", 1)[1]
    view1 = await resolve(session_factory, settings, first)
    view2 = await resolve(session_factory, settings, second)
    results = await asyncio.gather(
        submit(session_factory, settings, first, view1),
        submit(session_factory, settings, second, view2),
        return_exceptions=True,
    )
    assert sum(isinstance(value, dict) for value in results) == 1
    assert next(value for value in results if isinstance(value, AppError)).code == "consent_changed"
    pending = second if isinstance(results[0], dict) else first
    refreshed = await resolve(session_factory, settings, pending)
    assert refreshed["consent_mode"] == "ACKNOWLEDGE"
    await submit(session_factory, settings, pending, refreshed)


async def test_failed_audit_rolls_back_grant_and_token(apply_cleanup, session_factory, settings):
    _, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    async with FailingTrigger(session_factory, "audit_events"):
        with pytest.raises(AppError) as error:
            await submit(session_factory, settings, token, view)
        assert error.value.status_code == 503
    assert (await resolve(session_factory, settings, token))["completed"] is False
    async with session_factory() as session:
        assert await session.scalar(select(TalentPoolConsent.id)) is None


@pytest.mark.parametrize(
    ("action", "missing"),
    [
        ("ACCEPTED", "policy_ver"),
        ("ACCEPTED", "consent_snapshot"),
        ("DECLINED", "consent_snapshot"),
    ],
)
async def test_acceptance_requires_displayed_policy_and_snapshot(
    apply_cleanup, session_factory, settings, action, missing
):
    _, token = await issue(session_factory)
    view = await resolve(session_factory, settings, token)
    values = dict(
        token=token,
        action=action,
        policy_ver=view["policy_ver"],
        consent_snapshot=view["consent_snapshot"],
    )
    values.pop(missing)
    async with session_factory() as session:
        with pytest.raises(AppError) as error:
            await CandidateResponseService(session, settings).submit(SubmitIn(**values))
    assert error.value.status_code == 422
    assert (await resolve(session_factory, settings, token))["completed"] is False


async def test_receipt_expires_and_never_exposes_domain_data(
    apply_cleanup, session_factory, settings
):
    _, token = await issue(session_factory)
    await submit(session_factory, settings, token, await resolve(session_factory, settings, token))
    before = await resolve(session_factory, settings, token)
    async with session_factory.begin() as session:
        await session.execute(text("UPDATE applications SET hr_note='private'"))
    assert await resolve(session_factory, settings, token) == before
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "UPDATE response_links SET created_at=clock_timestamp()-interval '3 days',"
                " expires_at=clock_timestamp()-interval '1 second'"
            )
        )
    with pytest.raises(AppError) as error:
        await resolve(session_factory, settings, token)
    assert error.value.code == "invalid_response_link"


@pytest.mark.parametrize(("months", "expected"), [(1, "2028-02-29"), (12, "2029-01-31")])
async def test_month_end_uses_calendar_months(
    apply_cleanup, session_factory, settings, monkeypatch, months, expected
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.modules.responses import repository

    _, token = await issue(session_factory)
    now = datetime(2028, 1, 31, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))

    async def fixed_time(session):
        return now

    monkeypatch.setattr(repository, "decision_time", fixed_time)
    async with session_factory.begin() as session:
        await session.execute(
            text("UPDATE system_settings SET value=:n WHERE key='talent_pool_months'"),
            {"n": months},
        )
        await session.execute(
            text("UPDATE response_links SET created_at=:at,expires_at=:until"),
            {"at": now - timedelta(hours=1), "until": now + timedelta(days=1)},
        )
    await submit(session_factory, settings, token, await resolve(session_factory, settings, token))
    async with session_factory() as session:
        grant = await session.scalar(select(TalentPoolConsent))
        assert (
            grant.expires_at.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat() == expected
        )
