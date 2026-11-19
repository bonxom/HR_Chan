# API tin tuyển dụng công khai cho ứng viên: chỉ tin OPEN còn hạn, không lộ tiêu chí,
# người phỏng vấn, người tạo hay version nội bộ; không cần đăng nhập; API HR vẫn được bảo vệ.
"""``GET /api/v1/public/jobs`` and ``GET /api/v1/public/jobs/{id}`` (plan task 8, backend).

Contract:

* No authentication. Only postings with ``status = OPEN`` and ``deadline >= company
  today`` (UTC+7, same rule as the expiry sweep) are visible, even before the sweep.
* List query parameters follow the HR list conventions: ``page`` (>= 1), ``page_size``
  (1..100, default 20), optional ``q`` (title search, <= 200 chars) and ``department_id``;
  response ``{items, total, page, page_size}``; invalid values -> 422.
* List items have exactly ``PUBLIC_SUMMARY_KEYS``; detail adds ``description``,
  ``requirements`` and ``benefits`` (``PUBLIC_DETAIL_KEYS``). Nothing about criteria,
  thresholds, interviewers, creators, versions, status history or embeddings.
* Detail of a DRAFT, CLOSED, expired or unknown posting -> 404 ``job_not_found``.
* ``/api/v1/jobs`` (HR) still answers 401 without a token.
"""

from datetime import timedelta

import pytest
from application_flow_support import (
    PUBLIC_JOBS_URL,
    apply_cleanup,
    close_job,
    error_code,
    insert_open_job,
)
from apply_support import insert_account, insert_draft_job
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]

PUBLIC_SUMMARY_KEYS = {
    "id",
    "title",
    "department_id",
    "department_name",
    "headcount",
    "work_mode",
    "location",
    "deadline",
}
PUBLIC_DETAIL_KEYS = PUBLIC_SUMMARY_KEYS | {"description", "requirements", "benefits"}
INTERNAL_MARKERS = ("Tiêu chí nội bộ", "Chấm nội bộ", "interviewer", "criteria", "created_by")


@pytest.fixture
async def public_client(apply_cleanup, settings):
    from app.main import create_app

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


@pytest.fixture
async def postings(session_factory):
    from app.modules.recruitment.service import company_today

    today = company_today()
    async with session_factory() as session:
        hr = await insert_account(session, roles=["HR", "INTERVIEWER"])
        await session.commit()
    visible = await insert_open_job(session_factory, title="Kỹ sư dữ liệu", hr_id=hr)
    due_today = await insert_open_job(
        session_factory, title="Hạn hôm nay", deadline=today, hr_id=hr
    )
    sales = await insert_open_job(
        session_factory, title="Nhân viên kinh doanh", department="Phòng Kinh doanh", hr_id=hr
    )
    expired = await insert_open_job(
        session_factory, title="Đã quá hạn", deadline=today - timedelta(days=1), hr_id=hr
    )
    closed = await insert_open_job(session_factory, title="Đã đóng", hr_id=hr)
    await close_job(session_factory, closed.id)
    async with session_factory() as session:
        draft_id = await insert_draft_job(session, created_by=hr, title="Bản nháp bí mật")
        await session.commit()
    return {
        "visible": visible,
        "due_today": due_today,
        "sales": sales,
        "expired": expired,
        "closed": closed,
        "draft_id": draft_id,
    }


async def test_list_shows_only_open_postings_within_their_deadline(public_client, postings) -> None:
    response = await public_client.get(PUBLIC_JOBS_URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    ids = {item["id"] for item in body["items"]}
    assert ids == {postings["visible"].id, postings["due_today"].id, postings["sales"].id}
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 20
    for item in body["items"]:
        assert set(item) == PUBLIC_SUMMARY_KEYS
    for marker in INTERNAL_MARKERS + ("Bản nháp bí mật", "Đã đóng", "Đã quá hạn"):
        assert marker not in response.text


async def test_detail_exposes_only_public_fields(public_client, postings) -> None:
    job = postings["visible"]
    response = await public_client.get(f"{PUBLIC_JOBS_URL}/{job.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == PUBLIC_DETAIL_KEYS
    assert body["title"] == "Kỹ sư dữ liệu"
    assert body["description"] == "Mô tả công khai"
    assert body["department_name"] == "Phòng Kỹ thuật"
    for marker in INTERNAL_MARKERS + (str(job.hr_id), "auto_invite_threshold", "version"):
        assert marker not in response.text


@pytest.mark.parametrize("which", ["expired", "closed", "draft_id", "missing"])
async def test_non_public_postings_are_not_found(public_client, postings, which) -> None:
    job_id = {
        "expired": postings["expired"].id,
        "closed": postings["closed"].id,
        "draft_id": postings["draft_id"],
        "missing": 9_000_000_000,
    }[which]
    response = await public_client.get(f"{PUBLIC_JOBS_URL}/{job_id}")
    assert response.status_code == 404
    assert error_code(response) == "job_not_found"


async def test_search_department_filter_and_pagination(public_client, postings) -> None:
    searched = (await public_client.get(PUBLIC_JOBS_URL, params={"q": "dữ liệu"})).json()
    assert [item["id"] for item in searched["items"]] == [postings["visible"].id]

    listed = (await public_client.get(PUBLIC_JOBS_URL)).json()["items"]
    sales_department = next(
        item["department_id"] for item in listed if item["id"] == postings["sales"].id
    )
    department = (
        await public_client.get(PUBLIC_JOBS_URL, params={"department_id": sales_department})
    ).json()
    assert [item["id"] for item in department["items"]] == [postings["sales"].id]

    first = (await public_client.get(PUBLIC_JOBS_URL, params={"page_size": 2})).json()
    second = (await public_client.get(PUBLIC_JOBS_URL, params={"page_size": 2, "page": 2})).json()
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"q": "x" * 201}, {"department_id": 0}],
)
async def test_invalid_list_parameters_are_422(public_client, postings, params) -> None:
    response = await public_client.get(PUBLIC_JOBS_URL, params=params)
    assert response.status_code == 422


@pytest.mark.parametrize("job_id", ["0", "-1", "abc", str(2**63)])
async def test_invalid_detail_ids_are_422(public_client, postings, job_id) -> None:
    response = await public_client.get(f"{PUBLIC_JOBS_URL}/{job_id}")
    assert response.status_code == 422


async def test_hr_job_api_is_still_protected(public_client, postings) -> None:
    assert (await public_client.get("/api/v1/jobs")).status_code == 401
    job = postings["visible"]
    assert (await public_client.get(f"/api/v1/jobs/{job.id}")).status_code == 401
