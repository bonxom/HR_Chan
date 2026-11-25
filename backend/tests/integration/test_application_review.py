from datetime import UTC, datetime, timedelta

import pytest
from apply_support import apply_cleanup, build_world, insert_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import create_app
from app.modules.candidates.envelope import PendingContact, pack


class Store:
    async def get(self, key):
        return pack(
            b"%PDF-test-original", PendingContact("Test", "test@example.test", "0912345678")
        )


@pytest.fixture
async def api(settings, clean_database):
    app = create_app(settings, storage=Store())
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


async def login(api, account, password="employee-password-value"):
    response = await api.post(
        "/api/v1/auth/login",
        json={"email": account.email, "password": password},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def application(session_factory):
    world = await build_world(session_factory)
    async with session_factory.begin() as session:
        aid = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            status="PENDING_HR_REVIEW",
            review_due_at=datetime.now(UTC) - timedelta(days=1),
        )
        await session.execute(
            text("UPDATE applications SET review_due_at=:due WHERE id=:id"),
            {"due": datetime.now(UTC) - timedelta(days=1), "id": aid},
        )
        await session.execute(
            text(
                "INSERT INTO system_settings(key,value,default_value,min_value,max_value)"
                " VALUES ('response_deadline_days',2,2,1,5) ON CONFLICT(key) DO NOTHING"
            )
        )
    return world, aid


async def test_hr_http_reads_filters_and_cv(api, employee_account, apply_cleanup, session_factory):
    headers = await login(api, employee_account)
    world, aid = await application(session_factory)
    for query, count in (
        (f"job_id={world.job_id}", 1),
        ("score_min=80", 0),
        ("overdue=true", 1),
        ("overdue=false", 0),
        ("email_issue=true", 0),
        ("email_issue=false", 1),
        ("status=REJECTED", 0),
        ("q=Nguy", 1),
        ("submitted_to=2020-01-01T00:00:00Z", 0),
    ):
        response = await api.get("/api/v1/applications?" + query, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == count
    for sort in ("submitted_at", "ai_total_score", "review_due_at"):
        response = await api.get(
            "/api/v1/applications?sort=" + sort + "&order=asc", headers=headers
        )
        assert response.json()["items"][0]["id"] == aid
    response = await api.get(f"/api/v1/applications/{aid}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["candidate"]["email"] == world.candidate_email
    assert "storage" not in response.text
    response = await api.get(f"/api/v1/applications/{aid}/cv", headers=headers)
    assert response.content == b"%PDF-test-original"
    assert response.headers["cache-control"] == "private, no-store"
    response = await api.get(
        "/api/v1/applications?submitted_from=2026-01-01T00:00:00&submitted_to=2027-01-01T00:00:00Z",
        headers=headers,
    )
    assert response.status_code == 422


async def test_detail_preserves_scoring_snapshot(
    api, employee_account, apply_cleanup, session_factory
):
    headers = await login(api, employee_account)
    world, aid = await application(session_factory)
    async with session_factory.begin() as session:
        cid = await session.scalar(
            text(
                "INSERT INTO criteria"
                "(criteria_set_id,name,description,weight,is_mandatory,min_score)"
                " VALUES (:set,'SQL','SQL',100,true,60) RETURNING id"
            ),
            {"set": world.criteria_set_id},
        )
        await session.execute(
            text(
                "UPDATE applications SET criteria_set_id=:set,ai_status='SCORED',ai_total_score=55"
                " WHERE id=:id"
            ),
            {"set": world.criteria_set_id, "id": aid},
        )
        await session.execute(
            text(
                "INSERT INTO application_scores"
                " VALUES (:app,:criterion,55,75,'Specific comment',false)"
            ),
            {"app": aid, "criterion": cid},
        )
    result = await api.get(f"/api/v1/applications/{aid}", headers=headers)
    score = result.json()["scores"][0]
    assert score["weight_snapshot"] == 75
    assert score["min_score"] == 60 and score["meets_mandatory"] is False
    assert score["ai_comment"] == "Specific comment"


async def test_list_orders_and_ranges_multiple_rows(
    api, employee_account, apply_cleanup, session_factory
):
    headers = await login(api, employee_account)
    first, first_id = await application(session_factory)
    second, second_id = await application(session_factory)
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "UPDATE applications SET ai_total_score=40,submitted_at=:at,email_issue='failed'"
                " WHERE id=:id"
            ),
            {"at": now - timedelta(days=2), "id": first_id},
        )
        await session.execute(
            text("UPDATE applications SET ai_total_score=90,submitted_at=:at WHERE id=:id"),
            {"at": now, "id": second_id},
        )
    for sort in ("submitted_at", "ai_total_score"):
        result = await api.get(
            "/api/v1/applications?sort=" + sort + "&order=desc&page_size=1", headers=headers
        )
        assert result.json()["total"] == 2 and result.json()["items"][0]["id"] == second_id
    for query in ("score_min=40&score_max=40", "email_issue=true", f"job_id={first.job_id}"):
        result = await api.get("/api/v1/applications?" + query, headers=headers)
        assert [row["id"] for row in result.json()["items"]] == [first_id]


@pytest.mark.parametrize("prefix", ["/api/v1/applications", "/api/applications"])
@pytest.mark.parametrize("role", ["admin", "interviewer"])
async def test_all_review_routes_require_hr(
    api, prefix, role, admin_account, active_account_factory, apply_cleanup
):
    account = (
        admin_account
        if role == "admin"
        else await active_account_factory("reader@sis.hust.edu.vn", ["INTERVIEWER"])
    )
    headers = await login(
        api,
        account,
        "administrator-password-value" if role == "admin" else "employee-password-value",
    )
    for method, path, body in [
        ("GET", "", None),
        ("GET", "/1", None),
        ("GET", "/1/cv", None),
        ("GET", "/1/interview-slots?date_from=2026-12-01&date_to=2026-12-10", None),
        ("POST", "/1/invite", {"start_at": "2026-12-10T10:00:00+07:00", "version": 1}),
        ("POST", "/1/reject", {"reason_code": "NOT_QUALIFIED", "version": 1}),
    ]:
        response = await api.request(method, prefix + path, json=body, headers=headers)
        assert response.status_code == 403, response.text


async def test_rejection_atomic_and_secret_email(
    api, employee_account, apply_cleanup, session_factory, settings, email_outbox
):
    from app.modules.notifications.worker import deliver_due_batch

    headers = await login(api, employee_account)
    world, aid = await application(session_factory)
    invalid = await api.post(
        f"/api/v1/applications/{aid}/reject",
        headers=headers,
        json={"reason_code": "OTHER", "version": 1},
    )
    assert invalid.status_code == 422
    stale = await api.post(
        f"/api/v1/applications/{aid}/reject",
        headers=headers,
        json={"reason_code": "OTHER", "reason_text": "internal-only", "version": 2},
    )
    assert stale.status_code == 409
    result = await api.post(
        f"/api/v1/applications/{aid}/reject",
        headers=headers,
        json={"reason_code": "OTHER", "reason_text": "internal-only", "version": 1},
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "REJECTED"
    assert "consent_url" not in result.text
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT length(token_hash) FROM response_links WHERE application_id=:id"),
                {"id": aid},
            )
            == 64
        )
        assert "internal-only" not in await session.scalar(
            text("SELECT body FROM email_outbox WHERE application_id=:id"), {"id": aid}
        )
    await deliver_due_batch(
        session_factory, email_outbox, settings, datetime.now(UTC) + timedelta(seconds=1)
    )
    mail = email_outbox.messages[-1].text_body
    assert "/r/" in mail and "internal-only" not in mail
    again = await api.post(
        f"/api/v1/applications/{aid}/reject",
        headers=headers,
        json={"reason_code": "NOT_QUALIFIED", "version": 2},
    )
    assert again.status_code == 409


async def test_rejection_rolls_back_link_when_template_missing(
    apply_cleanup, session_factory, settings
):
    from app.modules.applications.review_schemas import RejectIn
    from app.modules.applications.review_service import ApplicationReviewService
    from app.modules.notifications.service import TemplateNotFoundError

    world, aid = await application(session_factory)
    async with session_factory.begin() as session:
        await session.execute(text("DELETE FROM email_templates WHERE code='REJECT_THANK_YOU'"))
    async with session_factory() as session:
        with pytest.raises(TemplateNotFoundError):
            await ApplicationReviewService(session).reject(
                world.hr_id, aid, RejectIn(reason_code="NOT_QUALIFIED", version=1), settings
            )
    async with session_factory() as session:
        assert (
            await session.scalar(text("SELECT status FROM applications WHERE id=:id"), {"id": aid})
            == "PENDING_HR_REVIEW"
        )
        assert await session.scalar(text("SELECT count(*) FROM response_links")) == 0


__all__ = ["apply_cleanup"]
pytestmark = pytest.mark.database


async def test_review_lists_filters_and_records_access(apply_cleanup, session_factory):
    from app.modules.applications.review_schemas import ApplicationFilters
    from app.modules.applications.review_service import ApplicationReviewService

    world = await build_world(session_factory)
    async with session_factory.begin() as session:
        aid = await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            status="PENDING_HR_REVIEW",
        )
    async with session_factory() as session:
        service = ApplicationReviewService(session)
        page = await service.list(world.hr_id, ApplicationFilters(q=world.candidate_email))
        assert page["total"] == 1 and page["items"][0]["id"] == aid
        assert (await service.list(world.hr_id, ApplicationFilters(q="absent")))["total"] == 0
        detail = await service.detail(world.hr_id, aid)
        assert detail["candidate"]["email"] == world.candidate_email
        assert detail["status_history"][0]["after"] == "PENDING_HR_REVIEW"
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT count(*) FROM audit_events WHERE action = 'application.viewed'")
            )
            == 1
        )
