# Kiểm thử API với PostgreSQL riêng: fixture tạo quyền/danh mục/tiêu chí thật.
# Các ca cạnh tranh giữ transaction để kiểm tra version và row lock.
"""Job postings and scoring criteria (create, update, publish, close, criteria versions)."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core import clock
from app.core.exceptions import Failure
from app.main import create_app
from app.modules.audit.schemas import AuditAction, AuditEventInput
from app.modules.recruitment.schemas import JobUpdateIn
from app.modules.recruitment.service import JobPostingService, company_today

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
JOBS_URL = "/api/v1/jobs"
PASSWORD = "employee-password-value"
ADMIN_PASSWORD = "administrator-password-value"


@pytest.fixture
async def departments(clean_database, session_factory) -> dict[str, int]:
    """Reference data: departments and the default auto-invite threshold setting."""
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO departments (name) VALUES ('Phòng Kỹ thuật'), ('Phòng Kinh doanh')"
                " ON CONFLICT (name) DO NOTHING"
            )
        )
        await session.execute(
            text(
                "INSERT INTO system_settings"
                " (key, value, default_value, min_value, max_value, unit)"
                " VALUES ('auto_invite_threshold', 70, 70, 0, 100, 'điểm')"
                " ON CONFLICT (key) DO UPDATE SET value = 70"
            )
        )
        rows = (await session.execute(text("SELECT name, id FROM departments"))).all()
        await session.commit()
    return {name: identifier for name, identifier in rows}


@pytest.fixture
async def client(settings, email_outbox, clean_database) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, email_client=email_outbox)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def interviewers(active_account_factory) -> list[str]:
    first = await active_account_factory("iv.one@sis.hust.edu.vn", ["INTERVIEWER"])
    second = await active_account_factory("iv.two@sis.hust.edu.vn", ["INTERVIEWER", "HR"])
    return [str(first.id), str(second.id)]


@pytest.fixture
async def hr(client, employee_account, departments, interviewers) -> dict[str, str]:
    return await login(client, employee_account.email)


def criteria(available: list[str], **overrides) -> dict:
    payload = {
        "criteria": [
            {"name": "Kinh nghiệm Java", "description": "Từ 2 năm", "weight": 60},
            {
                "name": "Tiếng Anh",
                "description": "Đọc hiểu tài liệu",
                "is_mandatory": True,
                "weight": 40,
            },
        ],
        "interviewer_ids": available[:1],
    }
    payload.update(overrides)
    return payload


def job_payload(departments: dict[str, int], **overrides) -> dict:
    payload = {
        "title": "Lập trình viên Backend",
        "department_id": departments["Phòng Kỹ thuật"],
        "description": "Phát triển API",
        "requirements": "Python, PostgreSQL",
        "benefits": "Lương tháng 13",
        "headcount": 2,
        "work_mode": "Toàn thời gian",
        "location": "Hà Nội",
        "deadline": (company_today() + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


async def create_open_job(client, hr, departments, interviewers, **overrides) -> dict:
    response = await client.post(
        JOBS_URL,
        json=job_payload(departments, publish=True, criteria=criteria(interviewers), **overrides),
        headers=hr,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def audit_rows(session_factory, job_id: int) -> list:
    async with session_factory() as session:
        return list(
            (
                await session.execute(
                    text(
                        "SELECT action, actor_id, metadata FROM audit_events"
                        " WHERE target_type = 'job_posting' AND target_id = :id"
                        " ORDER BY timestamp, id"
                    ),
                    {"id": str(job_id)},
                )
            ).all()
        )


# ---- success paths ------------------------------------------------------------------


async def test_create_draft_without_criteria(client, hr, departments, session_factory) -> None:
    response = await client.post(
        JOBS_URL,
        json={"title": "Nháp", "department_id": departments["Phòng Kinh doanh"]},
        headers=hr,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["version"] == 1
    assert body["current_criteria"] is None
    assert body["interviewers"] == []
    assert body["department_name"] == "Phòng Kinh doanh"
    assert [row.action for row in await audit_rows(session_factory, body["id"])] == ["job.created"]


async def test_create_and_publish_immediately(
    client, hr, departments, interviewers, employee_account
) -> None:
    body = await create_open_job(client, hr, departments, interviewers)
    assert body["status"] == "OPEN"
    current = body["current_criteria"]
    assert current["version_no"] == 1
    assert current["auto_invite_threshold"] == "70.00"  # default from system_settings
    assert [item["name"] for item in current["criteria"]] == ["Kinh nghiệm Java", "Tiếng Anh"]
    assert current["created_by"] == str(employee_account.id)
    assert [item["id"] for item in body["interviewers"]] == interviewers[:1]
    assert body["created_by"] == str(employee_account.id)


async def test_update_records_only_changed_fields(
    client, hr, departments, interviewers, session_factory
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    payload = job_payload(departments, title="Kỹ sư Backend", version=job["version"])
    response = await client.put(f"{JOBS_URL}/{job['id']}", json=payload, headers=hr)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Kỹ sư Backend"
    assert body["version"] == job["version"] + 1

    rows = await audit_rows(session_factory, job["id"])
    assert rows[-1].action == "job.updated"
    assert rows[-1].metadata == {
        "changes": {"title": {"before": "Lập trình viên Backend", "after": "Kỹ sư Backend"}}
    }

    unchanged = await client.put(
        f"{JOBS_URL}/{job['id']}",
        json=job_payload(departments, title="Kỹ sư Backend", version=body["version"]),
        headers=hr,
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["version"] == body["version"]


async def test_publish_draft_then_close(client, hr, departments, interviewers) -> None:
    created = await client.post(
        JOBS_URL, json=job_payload(departments, criteria=criteria(interviewers)), headers=hr
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "DRAFT"
    assert draft["current_criteria"]["version_no"] == 1

    published = await client.post(
        f"{JOBS_URL}/{draft['id']}/publish", json={"version": draft["version"]}, headers=hr
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "OPEN"

    closed = await client.post(
        f"{JOBS_URL}/{draft['id']}/close",
        json={"version": published.json()["version"]},
        headers=hr,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"] is not None


async def test_saving_criteria_twice_creates_versions(
    client, hr, departments, interviewers, session_factory
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    second = criteria(
        interviewers,
        auto_invite_threshold=85,
        criteria=[
            {"name": "SQL", "description": "Viết truy vấn", "weight": 50.5},
            {"name": "Giao tiếp", "description": "Trình bày rõ", "weight": 49.5},
        ],
        interviewer_ids=interviewers[1:],
    )
    response = await client.put(
        f"{JOBS_URL}/{job['id']}/criteria", json={**second, "version": job["version"]}, headers=hr
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_criteria"]["version_no"] == 2
    assert body["current_criteria"]["auto_invite_threshold"] == "85.00"
    assert [item["id"] for item in body["interviewers"]] == interviewers[1:]
    assert body["version"] == job["version"] + 1

    versions = await client.get(f"{JOBS_URL}/{job['id']}/criteria/versions", headers=hr)
    assert versions.status_code == 200
    listed = versions.json()
    assert [item["version_no"] for item in listed] == [2, 1]
    assert [item["name"] for item in listed[1]["criteria"]] == ["Kinh nghiệm Java", "Tiếng Anh"]

    rows = await audit_rows(session_factory, job["id"])
    assert rows[-1].action == "job.criteria_saved"
    assert rows[-1].metadata["version_no"] == 2
    assert set(rows[-1].metadata["changes"]) == {"interviewer_ids", "auto_invite_threshold"}


async def test_list_search_filter_and_sort(client, hr, departments, interviewers) -> None:
    await create_open_job(client, hr, departments, interviewers, title="Kế toán 100%_A")
    await create_open_job(
        client,
        hr,
        departments,
        interviewers,
        title="Nhân viên bán hàng",
        department_id=departments["Phòng Kinh doanh"],
        deadline=(company_today() + timedelta(days=5)).isoformat(),
    )
    await client.post(
        JOBS_URL,
        json={"title": "Nháp kế toán", "department_id": departments["Phòng Kỹ thuật"]},
        headers=hr,
    )

    everything = (await client.get(JOBS_URL, headers=hr)).json()
    assert everything["total"] == 3
    assert everything["items"][0]["title"] == "Nháp kế toán"  # newest first
    # The list carries work mode and location; a draft created without them returns null.
    assert everything["items"][0]["work_mode"] is None
    assert everything["items"][0]["location"] is None
    published = next(item for item in everything["items"] if item["title"] == "Kế toán 100%_A")
    assert (published["work_mode"], published["location"]) == ("Toàn thời gian", "Hà Nội")

    searched = (await client.get(JOBS_URL, params={"q": "100%_"}, headers=hr)).json()
    assert [item["title"] for item in searched["items"]] == ["Kế toán 100%_A"]

    opened = (await client.get(JOBS_URL, params={"status": "OPEN"}, headers=hr)).json()
    assert opened["total"] == 2

    by_department = (
        await client.get(
            JOBS_URL, params={"department_id": departments["Phòng Kinh doanh"]}, headers=hr
        )
    ).json()
    assert [item["title"] for item in by_department["items"]] == ["Nhân viên bán hàng"]

    by_deadline = (
        await client.get(JOBS_URL, params={"sort": "deadline", "order": "asc"}, headers=hr)
    ).json()
    assert [item["title"] for item in by_deadline["items"]] == [
        "Nhân viên bán hàng",
        "Kế toán 100%_A",
        "Nháp kế toán",
    ]

    paged = (await client.get(JOBS_URL, params={"page": 2, "page_size": 2}, headers=hr)).json()
    assert paged["total"] == 3 and len(paged["items"]) == 1


async def test_reference_lookups(client, hr, departments, interviewers) -> None:
    listed = await client.get("/api/v1/departments", headers=hr)
    assert listed.status_code == 200
    assert {item["name"] for item in listed.json()} >= set(departments)

    options = await client.get("/api/v1/interviewers", headers=hr)
    assert options.status_code == 200
    assert {item["id"] for item in options.json()} == set(interviewers)


# ---- rule violations ----------------------------------------------------------------


async def test_weights_must_sum_to_100(client, hr, departments, interviewers) -> None:
    bad = criteria(
        interviewers,
        criteria=[
            {"name": "A", "description": "a", "weight": 60},
            {"name": "B", "description": "b", "weight": 30},
        ],
    )
    response = await client.post(
        JOBS_URL, json=job_payload(departments, publish=True, criteria=bad), headers=hr
    )
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "job_rule_violation",
        "message": "Tổng trọng số các tiêu chí phải bằng 100 (hiện là 90)",
    }


async def test_duplicate_criterion_names_rejected(client, hr, departments, interviewers) -> None:
    bad = criteria(
        interviewers,
        criteria=[
            {"name": "Java", "description": "a", "weight": 50},
            {"name": "java", "description": "b", "weight": 50},
        ],
    )
    response = await client.post(JOBS_URL, json=job_payload(departments, criteria=bad), headers=hr)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "job_rule_violation"
    assert "không được trùng" in response.json()["error"]["message"]


async def test_interviewers_required_and_must_hold_role(
    client, hr, departments, interviewers, employee_account
) -> None:
    missing = await client.post(
        JOBS_URL,
        json=job_payload(departments, criteria=criteria(interviewers, interviewer_ids=[])),
        headers=hr,
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message"] == "Bộ tiêu chí phải có ít nhất 1 người phỏng vấn"

    not_interviewer = await client.post(
        JOBS_URL,
        json=job_payload(
            departments, criteria=criteria(interviewers, interviewer_ids=[str(employee_account.id)])
        ),
        headers=hr,
    )
    assert not_interviewer.status_code == 422
    assert not_interviewer.json()["error"]["code"] == "job_rule_violation"


async def test_publish_requires_complete_fields(client, hr, departments, interviewers) -> None:
    incomplete = job_payload(
        departments, description=None, headcount=None, publish=True, criteria=criteria(interviewers)
    )
    response = await client.post(JOBS_URL, json=incomplete, headers=hr)
    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "mô tả công việc" in message and "số lượng cần tuyển" in message

    no_criteria = await client.post(JOBS_URL, json=job_payload(departments), headers=hr)
    draft = no_criteria.json()
    publish = await client.post(
        f"{JOBS_URL}/{draft['id']}/publish", json={"version": draft["version"]}, headers=hr
    )
    assert publish.status_code == 422
    assert "bộ tiêu chí" in publish.json()["error"]["message"]


async def test_publish_rejects_past_deadline(client, hr, departments, interviewers) -> None:
    past = (company_today() - timedelta(days=1)).isoformat()
    response = await client.post(
        JOBS_URL,
        json=job_payload(departments, deadline=past, publish=True, criteria=criteria(interviewers)),
        headers=hr,
    )
    assert response.status_code == 422
    assert "Hạn nộp" in response.json()["error"]["message"]


async def test_closed_job_is_read_only(client, hr, departments, interviewers) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    closed = (
        await client.post(
            f"{JOBS_URL}/{job['id']}/close", json={"version": job["version"]}, headers=hr
        )
    ).json()
    version = closed["version"]

    edit = await client.put(
        f"{JOBS_URL}/{job['id']}",
        json=job_payload(departments, title="Sửa", version=version),
        headers=hr,
    )
    assert edit.status_code == 422
    assert "Tin đã đóng" in edit.json()["error"]["message"]

    reopen = await client.post(
        f"{JOBS_URL}/{job['id']}/publish", json={"version": version}, headers=hr
    )
    assert reopen.status_code == 422
    assert "không thể mở lại" in reopen.json()["error"]["message"]

    new_criteria = await client.put(
        f"{JOBS_URL}/{job['id']}/criteria",
        json={**criteria(interviewers), "version": version},
        headers=hr,
    )
    assert new_criteria.status_code == 422

    close_again = await client.post(
        f"{JOBS_URL}/{job['id']}/close", json={"version": version}, headers=hr
    )
    assert close_again.status_code == 422


async def test_stale_version_returns_409(client, hr, departments, interviewers) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    stale = job["version"]
    first = await client.put(
        f"{JOBS_URL}/{job['id']}",
        json=job_payload(departments, headcount=5, version=stale),
        headers=hr,
    )
    assert first.status_code == 200

    second = await client.put(
        f"{JOBS_URL}/{job['id']}",
        json=job_payload(departments, headcount=7, version=stale),
        headers=hr,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "version_conflict"

    criteria_conflict = await client.put(
        f"{JOBS_URL}/{job['id']}/criteria",
        json={**criteria(interviewers), "version": stale},
        headers=hr,
    )
    assert criteria_conflict.status_code == 409


async def test_unknown_job_returns_404(client, hr) -> None:
    assert (await client.get(f"{JOBS_URL}/999999", headers=hr)).status_code == 404


# ---- authorization ------------------------------------------------------------------


async def test_only_hr_employees_may_call(
    client, departments, interviewers, admin_account, employee_account
) -> None:
    assert (await client.get(JOBS_URL)).status_code == 401

    interviewer = await login(client, "iv.one@sis.hust.edu.vn")
    administrator = await login(client, admin_account.email, ADMIN_PASSWORD)
    for headers in (interviewer, administrator):
        assert (await client.get(JOBS_URL, headers=headers)).status_code == 403
        assert (
            await client.post(JOBS_URL, json=job_payload(departments), headers=headers)
        ).status_code == 403
        assert (await client.get("/api/v1/interviewers", headers=headers)).status_code == 403
        assert (await client.get("/api/v1/departments", headers=headers)).status_code == 403


# ---- background behaviour and database safeguards -----------------------------------


async def test_close_expired_jobs(client, hr, departments, interviewers, session_factory) -> None:
    due_today = await create_open_job(
        client, hr, departments, interviewers, deadline=company_today().isoformat()
    )
    later = await create_open_job(client, hr, departments, interviewers, title="Còn hạn")

    async with session_factory() as session:
        assert await JobPostingService(session).close_expired_jobs() == []  # deadline day itself
        closed = await JobPostingService(session).close_expired_jobs(
            now=clock.utcnow() + timedelta(days=1)
        )
    assert closed == [due_today["id"]]

    expired = (await client.get(f"{JOBS_URL}/{due_today['id']}", headers=hr)).json()
    assert expired["status"] == "CLOSED" and expired["closed_at"] is not None
    assert expired["version"] == due_today["version"] + 1
    assert (await client.get(f"{JOBS_URL}/{later['id']}", headers=hr)).json()["status"] == "OPEN"

    rows = await audit_rows(session_factory, due_today["id"])
    assert rows[-1].action == "job.closed"
    assert rows[-1].actor_id is None
    assert rows[-1].metadata["reason"] == "Quá hạn nộp hồ sơ"


async def test_stored_criteria_are_immutable(
    client, hr, departments, interviewers, session_factory
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    criterion_id = job["current_criteria"]["criteria"][0]["id"]
    async with session_factory() as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE criteria SET weight = 10 WHERE id = :id"), {"id": criterion_id}
            )
        await session.rollback()


async def test_weight_sum_trigger_checks_at_commit(
    client, hr, departments, interviewers, session_factory
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    async with session_factory() as session:
        set_id = await session.scalar(
            text(
                "INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by)"
                " SELECT id, 9, 50, created_by FROM job_postings WHERE id = :id RETURNING id"
            ),
            {"id": job["id"]},
        )
        await session.execute(
            text(
                "INSERT INTO criteria (criteria_set_id, name, description, weight)"
                " VALUES (:set_id, 'Một nửa', 'x', 50)"
            ),
            {"set_id": set_id},
        )
        with pytest.raises(DBAPIError):
            await session.commit()
        await session.rollback()


# ---- numeric bounds on path, query and body (422 before any query) ------------------

MAX_INTEGER = 2_147_483_647
MAX_BIGINT = 9_223_372_036_854_775_807


def job_requests(job_id: int, departments: dict[str, int], interviewers: list[str]) -> list:
    """Every endpoint taking a job ID, each with an otherwise valid body."""
    url = f"{JOBS_URL}/{job_id}"
    return [
        ("GET", url, None),
        ("PUT", url, job_payload(departments, version=1)),
        ("POST", f"{url}/publish", {"version": 1}),
        ("POST", f"{url}/close", {"version": 1}),
        ("PUT", f"{url}/criteria", {**criteria(interviewers), "version": 1}),
        ("GET", f"{url}/criteria/versions", None),
    ]


@pytest.mark.parametrize("job_id", [0, -1, MAX_BIGINT + 1, 10**30])
async def test_job_id_outside_bigint_range_is_rejected(
    client, hr, departments, interviewers, job_id
) -> None:
    for method, url, body in job_requests(job_id, departments, interviewers):
        response = await client.request(method, url, json=body, headers=hr)
        assert response.status_code == 422, (method, url, response.text)


async def test_largest_bigint_job_id_is_accepted(client, hr, departments, interviewers) -> None:
    response = await client.get(f"{JOBS_URL}/{MAX_BIGINT}", headers=hr)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"

    versions = await client.get(f"{JOBS_URL}/{MAX_BIGINT}/criteria/versions", headers=hr)
    assert versions.status_code == 404


@pytest.mark.parametrize("department_id", [0, -1, MAX_BIGINT + 1, 10**30])
async def test_department_filter_outside_bigint_range_is_rejected(
    client, hr, department_id
) -> None:
    response = await client.get(JOBS_URL, params={"department_id": department_id}, headers=hr)
    assert response.status_code == 422, response.text


async def test_department_filter_accepts_largest_bigint(client, hr) -> None:
    response = await client.get(JOBS_URL, params={"department_id": MAX_BIGINT}, headers=hr)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"page": MAX_BIGINT, "page_size": 100},
        {"page": MAX_BIGINT + 1},
        {"page": 10**30, "page_size": 1},
    ],
)
async def test_page_whose_offset_overflows_is_rejected(client, hr, params) -> None:
    response = await client.get(JOBS_URL, params=params, headers=hr)
    assert response.status_code == 422, response.text


async def test_large_page_within_range_is_accepted(client, hr) -> None:
    response = await client.get(JOBS_URL, params={"page": 1000, "page_size": 100}, headers=hr)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["page"] == 1000


@pytest.mark.parametrize(
    "overrides",
    [
        {"headcount": MAX_INTEGER + 1},
        {"headcount": 0},
        {"headcount": -1},
        {"department_id": MAX_BIGINT + 1},
        {"department_id": 0},
    ],
)
async def test_create_body_numbers_outside_range_are_rejected(
    client, hr, departments, overrides
) -> None:
    response = await client.post(JOBS_URL, json=job_payload(departments, **overrides), headers=hr)
    assert response.status_code == 422, response.text


async def test_create_accepts_largest_integer_headcount(client, hr, departments) -> None:
    response = await client.post(
        JOBS_URL, json=job_payload(departments, headcount=MAX_INTEGER), headers=hr
    )
    assert response.status_code == 201, response.text
    assert response.json()["headcount"] == MAX_INTEGER


@pytest.mark.parametrize(
    "overrides",
    [
        {"headcount": MAX_INTEGER + 1},
        {"department_id": MAX_BIGINT + 1},
        {"version": MAX_INTEGER + 1},
        {"version": 0},
    ],
)
async def test_update_body_numbers_outside_range_are_rejected(
    client, hr, departments, interviewers, overrides
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    payload = {**job_payload(departments, version=job["version"]), **overrides}
    response = await client.put(f"{JOBS_URL}/{job['id']}", json=payload, headers=hr)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("version", [0, MAX_INTEGER + 1, MAX_BIGINT + 1])
async def test_version_bodies_outside_integer_range_are_rejected(
    client, hr, departments, interviewers, version
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    url = f"{JOBS_URL}/{job['id']}"
    for method, path, body in (
        ("POST", f"{url}/publish", {"version": version}),
        ("POST", f"{url}/close", {"version": version}),
        ("PUT", f"{url}/criteria", {**criteria(interviewers), "version": version}),
    ):
        response = await client.request(method, path, json=body, headers=hr)
        assert response.status_code == 422, (method, path, response.text)


# ---- admin audit output hides job business content ----------------------------------

AUDIT_URL = "/api/v1/audit-events"


async def test_admin_audit_listing_hides_job_changes_but_database_keeps_them(
    client, hr, departments, interviewers, admin_account, session_factory
) -> None:
    job = await create_open_job(client, hr, departments, interviewers)
    secret_description = "Mô tả nội bộ: hệ thống lương thưởng"
    secret_requirements = "Yêu cầu nội bộ: Kafka, Kubernetes"
    secret_benefits = "Quyền lợi nội bộ: thưởng cổ phiếu"
    updated = await client.put(
        f"{JOBS_URL}/{job['id']}",
        json=job_payload(
            departments,
            description=secret_description,
            requirements=secret_requirements,
            benefits=secret_benefits,
            version=job["version"],
        ),
        headers=hr,
    )
    assert updated.status_code == 200, updated.text
    saved = await client.put(
        f"{JOBS_URL}/{job['id']}/criteria",
        json={
            **criteria(interviewers, auto_invite_threshold=85, interviewer_ids=interviewers[1:]),
            "version": updated.json()["version"],
        },
        headers=hr,
    )
    assert saved.status_code == 200, saved.text

    admin = await login(client, admin_account.email, ADMIN_PASSWORD)
    listed = await client.get(
        AUDIT_URL,
        params={"target_type": "job_posting", "target_id": str(job["id"]), "limit": 100},
        headers=admin,
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert {item["action"] for item in items} == {
        "job.created",
        "job.updated",
        "job.criteria_saved",
    }
    for item in items:
        assert "changes" not in item["metadata"], item
    criteria_item = next(item for item in items if item["action"] == "job.criteria_saved")
    assert criteria_item["metadata"] == {"version_no": 2}
    for hidden in (
        secret_description,
        secret_requirements,
        secret_benefits,
        "Phát triển API",
        "Python, PostgreSQL",
        "auto_invite_threshold",
        "interviewer_ids",
        *interviewers,
    ):
        assert hidden not in listed.text, hidden

    # Administrative (account) events keep exactly the metadata that is stored.
    accounts = await client.get(
        AUDIT_URL, params={"target_type": "account", "limit": 100}, headers=admin
    )
    assert accounts.status_code == 200, accounts.text
    async with session_factory() as session:
        stored_accounts = {
            str(row.id): row.metadata
            for row in (
                await session.execute(
                    text("SELECT id, metadata FROM audit_events WHERE target_type = 'account'")
                )
            ).all()
        }
    assert accounts.json()["items"]
    for item in accounts.json()["items"]:
        assert item["metadata"] == stored_accounts[item["id"]]

    # The database still holds the full before/after history.
    rows = await audit_rows(session_factory, job["id"])
    update_changes = next(row for row in rows if row.action == "job.updated").metadata["changes"]
    assert update_changes["description"] == {
        "before": "Phát triển API",
        "after": secret_description,
    }
    assert update_changes["requirements"] == {
        "before": "Python, PostgreSQL",
        "after": secret_requirements,
    }
    assert update_changes["benefits"] == {"before": "Lương tháng 13", "after": secret_benefits}

    criteria_meta = next(row for row in rows if row.action == "job.criteria_saved").metadata
    assert criteria_meta["version_no"] == 2
    threshold = criteria_meta["changes"]["auto_invite_threshold"]
    assert Decimal(threshold["before"]) == Decimal("70")
    assert Decimal(threshold["after"]) == Decimal("85")
    assert criteria_meta["changes"]["interviewer_ids"] == {
        "before": sorted(interviewers[:1]),
        "after": sorted(interviewers[1:]),
    }


# ---- expiry: worker sweep and expired OPEN postings ---------------------------------

LOCK_TIMEOUT = 10.0


async def set_deadline(session_factory, job_id: int, deadline: date) -> None:
    """Move a posting's deadline directly in the test database (no global clock change)."""
    async with session_factory() as session:
        await session.execute(
            text("UPDATE job_postings SET deadline = :deadline WHERE id = :id"),
            {"deadline": deadline, "id": job_id},
        )
        await session.commit()


async def job_row(session_factory, job_id: int):
    async with session_factory() as session:
        return (
            await session.execute(
                text(
                    "SELECT title, status::text AS status, version, deadline, closed_at,"
                    " current_criteria_set_id FROM job_postings WHERE id = :id"
                ),
                {"id": job_id},
            )
        ).one()


async def actions_for(session_factory, job_id: int, action: str) -> list:
    return [row for row in await audit_rows(session_factory, job_id) if row.action == action]


@pytest.fixture
async def expired_job(client, hr, departments, interviewers, session_factory) -> dict:
    """An OPEN posting whose deadline was yesterday, not yet swept by the worker."""
    job = await create_open_job(client, hr, departments, interviewers)
    await set_deadline(session_factory, job["id"], company_today() - timedelta(days=1))
    return job


async def test_worker_sweep_closes_each_expired_job_once(
    client, hr, departments, interviewers, session_factory, expired_job
) -> None:
    from app.worker import close_expired_once

    today = company_today()
    yesterday = today - timedelta(days=1)
    due_today = await create_open_job(
        client, hr, departments, interviewers, title="Hạn hôm nay", deadline=today.isoformat()
    )
    draft = await client.post(JOBS_URL, json=job_payload(departments, title="Nháp"), headers=hr)
    assert draft.status_code == 201, draft.text
    draft = draft.json()
    await set_deadline(session_factory, draft["id"], yesterday)
    already = await create_open_job(client, hr, departments, interviewers, title="Đã đóng")
    closed = await client.post(
        f"{JOBS_URL}/{already['id']}/close", json={"version": already["version"]}, headers=hr
    )
    assert closed.status_code == 200, closed.text
    closed = closed.json()
    await set_deadline(session_factory, already["id"], yesterday)

    first = await close_expired_once(session_factory)
    second = await close_expired_once(session_factory)
    assert (first, second) == (1, 0)

    expired = await job_row(session_factory, expired_job["id"])
    assert expired.status == "CLOSED"
    assert expired.closed_at is not None
    assert expired.version == expired_job["version"] + 1
    sweeps = await actions_for(session_factory, expired_job["id"], "job.closed")
    assert len(sweeps) == 1
    assert sweeps[0].actor_id is None
    assert sweeps[0].metadata["reason"] == "Quá hạn nộp hồ sơ"

    still_open = await job_row(session_factory, due_today["id"])
    assert (still_open.status, still_open.version) == ("OPEN", due_today["version"])
    untouched_draft = await job_row(session_factory, draft["id"])
    assert (untouched_draft.status, untouched_draft.version) == ("DRAFT", draft["version"])
    untouched_closed = await job_row(session_factory, already["id"])
    assert (untouched_closed.status, untouched_closed.version) == ("CLOSED", closed["version"])
    manual_close = await actions_for(session_factory, already["id"], "job.closed")
    assert len(manual_close) == 1 and manual_close[0].actor_id is not None


@pytest.mark.parametrize("operation", ["edit", "extend_deadline", "save_criteria"])
async def test_expired_open_job_cannot_be_changed_before_the_sweep(
    client, hr, departments, interviewers, session_factory, expired_job, operation
) -> None:
    job_id = expired_job["id"]
    yesterday = company_today() - timedelta(days=1)
    version = (await client.get(f"{JOBS_URL}/{job_id}", headers=hr)).json()["version"]
    if operation == "edit":
        response = await client.put(
            f"{JOBS_URL}/{job_id}",
            json=job_payload(
                departments, title="Sửa sau hạn", deadline=yesterday.isoformat(), version=version
            ),
            headers=hr,
        )
    elif operation == "extend_deadline":
        response = await client.put(
            f"{JOBS_URL}/{job_id}",
            json=job_payload(
                departments,
                deadline=(company_today() + timedelta(days=30)).isoformat(),
                version=version,
            ),
            headers=hr,
        )
    else:
        response = await client.put(
            f"{JOBS_URL}/{job_id}/criteria",
            json={**criteria(interviewers, interviewer_ids=interviewers[1:]), "version": version},
            headers=hr,
        )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "job_rule_violation"

    row = await job_row(session_factory, job_id)
    assert row.title == "Lập trình viên Backend"
    assert row.deadline == yesterday
    assert row.current_criteria_set_id == expired_job["current_criteria"]["id"]
    assert await actions_for(session_factory, job_id, "job.updated") == []
    assert await actions_for(session_factory, job_id, "job.criteria_saved") == []


# ---- expiry vs. concurrent locked update (independent sessions) ---------------------


def gate_audit(
    monkeypatch, predicate: Callable[[AuditEventInput], bool]
) -> tuple[asyncio.Event, asyncio.Event]:
    """Pause the first matching audit write (row lock held) until ``release`` is set."""
    from app.modules.recruitment import service as recruitment_service

    original = recruitment_service.record_event
    reached = asyncio.Event()
    release = asyncio.Event()

    async def gated(session, event: AuditEventInput) -> None:
        if predicate(event) and not reached.is_set():
            reached.set()
            await asyncio.wait_for(release.wait(), LOCK_TIMEOUT)
        await original(session, event)

    monkeypatch.setattr(recruitment_service, "record_event", gated)
    return reached, release


async def wait_for_lock_waiter(session_factory) -> None:
    """Return once another backend is blocked on a row lock in job_postings."""

    async def poll() -> None:
        while True:
            async with session_factory() as session:
                waiting = await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity"
                        " WHERE datname = current_database() AND pid <> pg_backend_pid()"
                        " AND wait_event_type = 'Lock' AND query ILIKE '%job_postings%'"
                    )
                )
            if waiting:
                return
            await asyncio.sleep(0.02)  # polling interval only; the bound is the timeout

    await asyncio.wait_for(poll(), LOCK_TIMEOUT)


async def settle(release: asyncio.Event, *tasks: asyncio.Task | None) -> None:
    """Never leave a blocked transaction behind (it would hang database cleanup)."""
    release.set()
    running = [task for task in tasks if task is not None]
    if not running:
        return
    _done, pending = await asyncio.wait(running, timeout=LOCK_TIMEOUT)
    for task in pending:
        task.cancel()
    await asyncio.gather(*running, return_exceptions=True)


@pytest.mark.parametrize("extend_deadline", [True, False], ids=["extends", "keeps-deadline"])
async def test_expiry_sweep_waits_for_a_locked_update_and_rechecks(
    client,
    hr,
    departments,
    interviewers,
    employee_account,
    session_factory,
    monkeypatch,
    extend_deadline,
) -> None:
    today = company_today()
    job = await create_open_job(client, hr, departments, interviewers, deadline=today.isoformat())
    version = job["version"]
    new_deadline = today + timedelta(days=30) if extend_deadline else today
    payload = JobUpdateIn(
        **job_payload(
            departments,
            title="Cập nhật đang giữ khóa",
            deadline=new_deadline.isoformat(),
            version=version,
        )
    )
    reached, release = gate_audit(
        monkeypatch, lambda event: event.action is AuditAction.JOB_UPDATED
    )

    async def update() -> int | Failure:
        async with session_factory() as session:
            return await JobPostingService(session).update_job(
                actor_id=employee_account.id,
                job_id=job["id"],
                payload=payload,
                expected_version=version,
            )

    async def sweep() -> list[int]:
        # Worker's view of "tomorrow": today's deadline has now passed.
        async with session_factory() as session:
            return await JobPostingService(session).close_expired_jobs(
                now=clock.utcnow() + timedelta(days=1)
            )

    update_task = asyncio.create_task(update())
    sweep_task: asyncio.Task | None = None
    try:
        await asyncio.wait_for(reached.wait(), LOCK_TIMEOUT)
        sweep_task = asyncio.create_task(sweep())
        await wait_for_lock_waiter(session_factory)
        assert not sweep_task.done()
        release.set()
        updated, closed = await asyncio.wait_for(
            asyncio.gather(update_task, sweep_task), LOCK_TIMEOUT
        )
    finally:
        await settle(release, update_task, sweep_task)

    assert updated == job["id"]
    row = await job_row(session_factory, job["id"])
    assert row.title == "Cập nhật đang giữ khóa"
    assert len(await actions_for(session_factory, job["id"], "job.updated")) == 1
    if extend_deadline:
        assert closed == []
        assert (row.status, row.version, row.deadline) == ("OPEN", version + 1, new_deadline)
        assert await actions_for(session_factory, job["id"], "job.closed") == []
    else:
        assert closed == [job["id"]]
        assert (row.status, row.version) == ("CLOSED", version + 2)
        assert len(await actions_for(session_factory, job["id"], "job.closed")) == 1


async def test_stale_update_waiting_on_the_expiry_sweep_fails(
    client, hr, departments, session_factory, monkeypatch, expired_job
) -> None:
    job_id = expired_job["id"]
    version = expired_job["version"]
    reached, release = gate_audit(
        monkeypatch,
        lambda event: event.action is AuditAction.JOB_CLOSED and event.actor_id is None,
    )

    async def sweep() -> list[int]:
        async with session_factory() as session:
            return await JobPostingService(session).close_expired_jobs()

    sweep_task = asyncio.create_task(sweep())
    update_task: asyncio.Task | None = None
    try:
        await asyncio.wait_for(reached.wait(), LOCK_TIMEOUT)
        update_task = asyncio.create_task(
            client.put(
                f"{JOBS_URL}/{job_id}",
                json=job_payload(departments, title="Sửa khi đang đóng", version=version),
                headers=hr,
            )
        )
        await wait_for_lock_waiter(session_factory)
        assert not update_task.done()
        release.set()
        closed, response = await asyncio.wait_for(
            asyncio.gather(sweep_task, update_task), LOCK_TIMEOUT
        )
    finally:
        await settle(release, sweep_task, update_task)

    assert closed == [job_id]
    assert response.status_code in (409, 422), response.text
    row = await job_row(session_factory, job_id)
    assert (row.status, row.version, row.title) == ("CLOSED", version + 1, "Lập trình viên Backend")
    assert len(await actions_for(session_factory, job_id, "job.closed")) == 1
    assert await actions_for(session_factory, job_id, "job.updated") == []
