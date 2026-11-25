import asyncio
from datetime import UTC, date, datetime

import pytest
from application_flow_support import (
    FailingTrigger,
    apply_cleanup,
    flow,
    flow_cleanup,
    flow_factory,
    frozen_clock,
    insert_open_job,
    last_otp,
    request_otp,
    rows,
    scalar,
    submit,
    upload_ok,
)
from apply_support import insert_criteria_set
from sqlalchemy import text

from app.modules.applications.scoring import QUALIFIED_NOTE, CvScoringService, score_pending_batch

__all__ = ["apply_cleanup", "flow", "flow_cleanup", "flow_factory", "frozen_clock"]
pytestmark = pytest.mark.database


class Agent:
    def __init__(self, mandatory=55):
        self.mandatory = mandatory
        self.calls = 0

    async def score_criteria(self, cv, criteria):
        assert cv.startswith(b"%PDF")
        self.calls += 1
        if self.mandatory == "error":
            raise RuntimeError("sensitive input")
        if self.mandatory == "timeout":
            await asyncio.sleep(10)
        if self.mandatory == "invalid":
            return []
        return [
            {"criterion_id": criterion.id, "score": score, "comment": "Synthetic"}
            for criterion, score in zip(criteria, [self.mandatory, 95], strict=True)
        ]


async def create_application(flow, job, email):
    submission = await upload_ok(flow.client, email=email)
    assert (await request_otp(flow.client, submission, job.id)).status_code == 200
    result = await submit(flow.client, submission, job.id, last_otp(flow.email))
    assert result.status_code == 201, result.text
    return result.json()["application_id"]


async def activate_version(session_factory, job, version):
    async with session_factory.begin() as session:
        await session.execute(
            text("UPDATE job_postings SET current_criteria_set_id=:v WHERE id=:j"),
            {"v": version, "j": job.id},
        )


@pytest.fixture
async def posting(flow, session_factory):
    job = await insert_open_job(session_factory)
    async with session_factory.begin() as session:
        criteria_id = await insert_criteria_set(
            session, job_id=job.id, created_by=job.hr_id, version=2
        )
        await session.execute(
            text(
                "INSERT INTO criteria"
                " (criteria_set_id,name,description,is_mandatory,min_score,weight)"
                " VALUES (:id,'A','A',true,60,25), (:id,'B','B',false,NULL,75)"
            ),
            {"id": criteria_id},
        )
    await activate_version(session_factory, job, criteria_id)
    return job


@pytest.mark.parametrize(
    ("mandatory", "expected_total", "qualified"), [(55, 85, False), (60, 86.25, True)]
)
async def test_otp_to_scored_history_uses_submission_version_once(
    flow, posting, session_factory, frozen_clock, mandatory, expected_total, qualified
):
    aid = await create_application(flow, posting, "alice@example.test")
    await activate_version(session_factory, posting, posting.criteria_set_id)
    agent = Agent(mandatory)
    service = CvScoringService(agent, flow.storage, 5)
    frozen_clock.now = datetime(2026, 12, 4, 8, tzinfo=UTC)
    async with session_factory.begin() as session:
        await session.execute(
            text("INSERT INTO holidays (holiday_date,name) VALUES (:d,'Test')"),
            {"d": date(2026, 12, 7)},
        )
    try:
        processed = await asyncio.gather(
            score_pending_batch(session_factory, service, {}),
            score_pending_batch(session_factory, service, {}),
        )
        assert sum(processed) == 1 and agent.calls == 1
        assert await score_pending_batch(session_factory, service, {}) == 0
        [app] = await rows(session_factory, "SELECT * FROM applications WHERE id=:id", id=aid)
        assert (app.status, app.ai_status, app.ai_total_score) == (
            "PENDING_HR_REVIEW",
            "SCORED",
            expected_total,
        )
        assert app.version == 2
        assert app.hr_note == (QUALIFIED_NOTE if qualified else None)
        assert app.review_due_at == datetime(2026, 12, 14, 10, 30, tzinfo=UTC)
        scores = await rows(
            session_factory,
            "SELECT score, weight_snapshot, meets_mandatory, ai_comment"
            " FROM application_scores WHERE application_id=:id ORDER BY criterion_id",
            id=aid,
        )
        assert scores == [(mandatory, 25, qualified, "Synthetic"), (95, 75, None, "Synthetic")]
        assert await scalar(session_factory, "SELECT count(*) FROM email_outbox") == 1
    finally:
        async with session_factory.begin() as session:
            await session.execute(
                text("DELETE FROM holidays WHERE holiday_date=:d"), {"d": date(2026, 12, 7)}
            )


@pytest.mark.parametrize(
    ("mode", "ai_status", "reason"),
    [
        ("invalid", "NEEDS_REVIEW", "invalid_scoring_response"),
        ("error", "FAILED", "scoring_provider_failed"),
        ("timeout", "FAILED", "scoring_provider_failed"),
        ("no_store", "NEEDS_REVIEW", "cv_unavailable"),
    ],
)
async def test_non_scorable_routes_to_review_without_partial_scores(
    flow, posting, session_factory, mode, ai_status, reason
):
    aid = await create_application(flow, posting, "alice@example.test")
    service = CvScoringService(Agent(mode), None if mode == "no_store" else flow.storage, 0.01)
    assert await score_pending_batch(session_factory, service, {}) == 1
    [app] = await rows(session_factory, "SELECT * FROM applications WHERE id=:id", id=aid)
    assert (app.status, app.ai_status, app.ai_failure_reason) == (
        "PENDING_HR_REVIEW",
        ai_status,
        reason,
    )
    assert app.ai_total_score is None and app.hr_note is None and app.review_due_at is not None
    assert await scalar(session_factory, "SELECT count(*) FROM application_scores") == 0


async def test_transaction_rollback_and_delayed_retry_allow_new_work(
    flow, posting, session_factory
):
    first = await create_application(flow, posting, "alice@example.test")
    service = CvScoringService(Agent(), flow.storage, 5)
    retry_after = {}
    async with FailingTrigger(session_factory, "application_scores"):
        assert await score_pending_batch(session_factory, service, retry_after) == 0
    assert first in retry_after
    assert (
        await scalar(session_factory, "SELECT status FROM applications WHERE id=:id", id=first)
        == "SCORING"
    )
    assert await scalar(session_factory, "SELECT count(*) FROM application_scores") == 0
    await create_application(flow, posting, "bob@example.test")
    assert await score_pending_batch(session_factory, service, retry_after) == 1
    retry_after[first] = 0
    assert await score_pending_batch(session_factory, service, retry_after) == 1
