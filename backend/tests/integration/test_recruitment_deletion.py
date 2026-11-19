# Kiểm tra xóa nguyên cây và rollback khi lỗi trên database thử riêng.
# Timestamps cũ chỉ được tạo trong fixture, không sửa dữ liệu ứng dụng.
"""Permanent deletion: HR deletes drafts; the worker purges CLOSED postings after two years.

Contracts exercised here (approved spec and plan, 17/11/2026):

* ``DELETE /api/v1/jobs/{id}`` with a ``VersionIn`` body, HR only, ``204`` on success.
  Only DRAFT postings are deleted by hand; OPEN and every CLOSED posting are refused.
* ``JobPostingService.delete_draft_job(actor_id=, job_id=, expected_version=)`` and
  ``JobPostingService.purge_closed_jobs(now=None, batch_size=100) -> list[int]``.
* ``app.worker.purge_closed_once(session_factory) -> int``.
* Both paths audit through ``app.modules.recruitment.service.record_event`` with the
  ``job.deleted`` action (the same seam the expiry tests gate on).

Fixtures come from the job posting suite so setup and cleanup stay identical. Old data
is produced by moving timestamps directly in the dedicated test database only.
"""

import asyncio
import contextlib
import logging
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone

import pytest
import test_recruitment_jobs as jobs_suite
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app.core import clock
from app.core.exceptions import Failure
from app.modules.recruitment.service import JobPostingService

pytestmark = pytest.mark.database

# Real fixtures of the job posting suite (function scope, same database cleanup).
client = jobs_suite.client
hr = jobs_suite.hr
departments = jobs_suite.departments
interviewers = jobs_suite.interviewers

JOBS_URL = jobs_suite.JOBS_URL
ADMIN_PASSWORD = jobs_suite.ADMIN_PASSWORD
LOCK_TIMEOUT = jobs_suite.LOCK_TIMEOUT
audit_rows = jobs_suite.audit_rows
create_open_job = jobs_suite.create_open_job
criteria = jobs_suite.criteria
gate_audit = jobs_suite.gate_audit
job_payload = jobs_suite.job_payload
login = jobs_suite.login
settle = jobs_suite.settle
wait_for_lock_waiter = jobs_suite.wait_for_lock_waiter

COMPANY_TZ = timezone(timedelta(hours=7))
DELETED = "job.deleted"
MAX_BIGINT = 9_223_372_036_854_775_807
# 10:00 on 17/11/2026 in Vietnam.
NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


# ---- helpers ------------------------------------------------------------------------


async def delete_job(client, headers, job_id: int, version: int | None, **extra):
    body = {"version": version, **extra} if version is not None else None
    return await client.request("DELETE", f"{JOBS_URL}/{job_id}", json=body, headers=headers)


async def create_draft(client, hr, departments, **overrides) -> dict:
    payload = {"title": "Nháp trống", "department_id": departments["Phòng Kỹ thuật"]}
    payload.update(overrides)
    response = await client.post(JOBS_URL, json=payload, headers=hr)
    assert response.status_code == 201, response.text
    return response.json()


async def create_complete_draft(client, hr, departments, interviewers, **overrides) -> dict:
    """A DRAFT with every field and one criteria version, ready to publish."""
    response = await client.post(
        JOBS_URL,
        json=job_payload(departments, criteria=criteria(interviewers), **overrides),
        headers=hr,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "DRAFT"
    return body


async def create_versioned_draft(client, hr, departments, interviewers) -> dict:
    """A DRAFT with two criteria versions and changed interviewers."""
    draft = await create_complete_draft(
        client,
        hr,
        departments,
        interviewers,
        title="Nháp nhiều phiên bản",
        description="Mô tả nội bộ của bản nháp",
    )
    second = criteria(
        interviewers,
        criteria=[
            {"name": "Tiêu chí bí mật", "description": "Chấm điểm nội bộ", "weight": 70},
            {"name": "Giao tiếp", "description": "Trình bày rõ", "weight": 30},
        ],
        interviewer_ids=interviewers[1:],
    )
    saved = await client.put(
        f"{JOBS_URL}/{draft['id']}/criteria",
        json={**second, "version": draft["version"]},
        headers=hr,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["current_criteria"]["version_no"] == 2
    return body


async def set_closed_at(session_factory, job_id: int, closed_at: datetime) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE job_postings SET closed_at = :closed_at WHERE id = :id"),
            {"closed_at": closed_at, "id": job_id},
        )
        await session.commit()


async def age_job(session_factory, job_id: int, created_at: datetime) -> None:
    """Make a DRAFT/OPEN posting look old; age alone must never make it purgeable."""
    async with session_factory() as session:
        await session.execute(
            text("UPDATE job_postings SET created_at = :at, updated_at = :at WHERE id = :id"),
            {"at": created_at, "id": job_id},
        )
        await session.commit()


async def create_closed_job(
    client, hr, departments, interviewers, session_factory, *, title: str, closed_at: datetime
) -> dict:
    job = await create_open_job(client, hr, departments, interviewers, title=title)
    closed = await client.post(
        f"{JOBS_URL}/{job['id']}/close", json={"version": job["version"]}, headers=hr
    )
    assert closed.status_code == 200, closed.text
    await set_closed_at(session_factory, job["id"], closed_at)
    return closed.json()


async def job_tree(session_factory, job_id: int) -> dict:
    """IDs of the posting and of every child row that belongs only to it."""
    params = {"id": job_id}
    async with session_factory() as session:
        jobs = await session.scalar(
            text("SELECT count(*) FROM job_postings WHERE id = :id"), params
        )
        sets = (
            await session.scalars(
                text("SELECT id FROM criteria_sets WHERE job_id = :id ORDER BY id"), params
            )
        ).all()
        items = (
            await session.scalars(
                text(
                    "SELECT c.id FROM criteria c JOIN criteria_sets s ON s.id = c.criteria_set_id"
                    " WHERE s.job_id = :id ORDER BY c.id"
                ),
                params,
            )
        ).all()
        assigned = (
            await session.scalars(
                text("SELECT user_id FROM job_interviewers WHERE job_id = :id ORDER BY user_id"),
                params,
            )
        ).all()
    return {
        "job": jobs,
        "sets": list(sets),
        "criteria": list(items),
        "interviewers": list(assigned),
    }


async def leftovers(session_factory, job_id: int, tree: dict) -> dict[str, int]:
    """Rows of a captured tree still present (by ID, so orphans would be counted too)."""
    async with session_factory() as session:
        return {
            "job": await session.scalar(
                text("SELECT count(*) FROM job_postings WHERE id = :id"), {"id": job_id}
            ),
            "sets": await session.scalar(
                text("SELECT count(*) FROM criteria_sets WHERE id = ANY(:ids)"),
                {"ids": tree["sets"]},
            ),
            "criteria": await session.scalar(
                text("SELECT count(*) FROM criteria WHERE id = ANY(:ids)"),
                {"ids": tree["criteria"]},
            ),
            "interviewers": await session.scalar(
                text("SELECT count(*) FROM job_interviewers WHERE job_id = :id"), {"id": job_id}
            ),
        }


GONE = {"job": 0, "sets": 0, "criteria": 0, "interviewers": 0}


async def reference_counts(session_factory) -> dict[str, int]:
    async with session_factory() as session:
        return {
            table: await session.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in ("accounts", "departments", "system_settings")
        }


async def deleted_events(session_factory, job_id: int) -> list:
    return [row for row in await audit_rows(session_factory, job_id) if row.action == DELETED]


def assert_safe_metadata(metadata: dict, *hidden: str) -> None:
    assert "changes" not in metadata
    dumped = str(metadata)
    for value in hidden:
        assert value not in dumped, value


class JobReference:
    """A table outside the deletion scope that references job_postings (test DB only).

    Deletion must not cascade into it: the referenced posting is refused or skipped.
    """

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def add(self, job_id: int) -> None:
        async with self.session_factory() as session:
            await session.execute(
                text("INSERT INTO test_job_reference_probe (job_id) VALUES (:id)"), {"id": job_id}
            )
            await session.commit()

    async def remove(self, job_id: int) -> None:
        async with self.session_factory() as session:
            await session.execute(
                text("DELETE FROM test_job_reference_probe WHERE job_id = :id"), {"id": job_id}
            )
            await session.commit()

    async def count(self, job_id: int) -> int:
        async with self.session_factory() as session:
            return await session.scalar(
                text("SELECT count(*) FROM test_job_reference_probe WHERE job_id = :id"),
                {"id": job_id},
            )


@pytest.fixture
async def job_reference(clean_database, session_factory) -> AsyncIterator[JobReference]:
    # Depends on clean_database so it is torn down (dropped) before the truncation runs.
    async with session_factory() as session:
        await session.execute(text("DROP TABLE IF EXISTS test_job_reference_probe"))
        await session.execute(
            text(
                "CREATE TABLE test_job_reference_probe ("
                " id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
                " job_id bigint NOT NULL REFERENCES job_postings (id))"
            )
        )
        await session.commit()
    try:
        yield JobReference(session_factory)
    finally:
        async with session_factory() as session:
            await session.execute(text("DROP TABLE IF EXISTS test_job_reference_probe"))
            await session.commit()


async def purge(session_factory, now: datetime = NOW, batch_size: int = 100) -> list[int]:
    async with session_factory() as session:
        return await JobPostingService(session).purge_closed_jobs(now=now, batch_size=batch_size)


async def delete_draft(session_factory, actor_id, job_id: int, version: int):
    async with session_factory() as session:
        return await JobPostingService(session).delete_draft_job(
            actor_id=actor_id, job_id=job_id, expected_version=version
        )


# ---- HR deletes drafts --------------------------------------------------------------


async def test_hr_deletes_an_empty_draft(
    client, hr, departments, employee_account, session_factory
) -> None:
    draft = await create_draft(client, hr, departments)
    assert draft["current_criteria"] is None

    response = await delete_job(client, hr, draft["id"], draft["version"])

    assert response.status_code == 204, response.text
    assert response.content == b""
    assert (await client.get(f"{JOBS_URL}/{draft['id']}", headers=hr)).status_code == 404
    versions = await client.get(f"{JOBS_URL}/{draft['id']}/criteria/versions", headers=hr)
    assert versions.status_code == 404
    listed = (await client.get(JOBS_URL, headers=hr)).json()
    assert listed["total"] == 0 and listed["items"] == []

    rows = await audit_rows(session_factory, draft["id"])
    assert [row.action for row in rows] == ["job.created", DELETED]  # history is kept
    deleted = rows[-1]
    assert deleted.actor_id == employee_account.id
    assert deleted.metadata["previous_status"] == "DRAFT"
    assert_safe_metadata(deleted.metadata, "Nháp trống")


async def test_hr_deletes_a_versioned_draft_and_only_its_own_rows(
    client, hr, departments, interviewers, employee_account, session_factory
) -> None:
    sibling = await create_open_job(client, hr, departments, interviewers, title="Tin giữ lại")
    draft = await create_versioned_draft(client, hr, departments, interviewers)
    tree = await job_tree(session_factory, draft["id"])
    assert len(tree["sets"]) == 2 and len(tree["criteria"]) == 4 and tree["interviewers"]
    sibling_tree = await job_tree(session_factory, sibling["id"])
    references = await reference_counts(session_factory)
    history = [row.action for row in await audit_rows(session_factory, draft["id"])]

    response = await delete_job(client, hr, draft["id"], draft["version"])

    assert response.status_code == 204, response.text
    assert await leftovers(session_factory, draft["id"], tree) == GONE
    # Unrelated rows: another posting, accounts (incl. interviewers), departments, settings.
    assert await job_tree(session_factory, sibling["id"]) == sibling_tree
    sibling_now = (await client.get(f"{JOBS_URL}/{sibling['id']}", headers=hr)).json()
    assert (sibling_now["status"], sibling_now["version"]) == ("OPEN", sibling["version"])
    assert await reference_counts(session_factory) == references
    options = (await client.get("/api/v1/interviewers", headers=hr)).json()
    assert {item["id"] for item in options} == set(interviewers)
    listed = (await client.get(JOBS_URL, headers=hr)).json()
    assert [item["id"] for item in listed["items"]] == [sibling["id"]]

    rows = await audit_rows(session_factory, draft["id"])
    assert [row.action for row in rows] == [*history, DELETED]
    deleted = rows[-1]
    assert deleted.actor_id == employee_account.id
    assert deleted.metadata["previous_status"] == "DRAFT"
    assert_safe_metadata(
        deleted.metadata,
        "Nháp nhiều phiên bản",
        "Mô tả nội bộ của bản nháp",
        "Tiêu chí bí mật",
        "Kinh nghiệm Java",
        *interviewers,
    )


async def test_admin_audit_listing_shows_the_deletion_without_job_content(
    client, hr, departments, interviewers, admin_account
) -> None:
    draft = await create_versioned_draft(client, hr, departments, interviewers)
    assert (await delete_job(client, hr, draft["id"], draft["version"])).status_code == 204

    admin = await login(client, admin_account.email, ADMIN_PASSWORD)
    listed = await client.get(
        "/api/v1/audit-events",
        params={"target_type": "job_posting", "target_id": str(draft["id"]), "action": DELETED},
        headers=admin,
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["metadata"]["previous_status"] == "DRAFT"
    for hidden in ("Nháp nhiều phiên bản", "Mô tả nội bộ của bản nháp", "Tiêu chí bí mật"):
        assert hidden not in listed.text


# ---- refusals keep every row --------------------------------------------------------


async def test_open_and_closed_postings_cannot_be_deleted_by_hand(
    client, hr, departments, interviewers, session_factory
) -> None:
    opened = await create_open_job(client, hr, departments, interviewers, title="Đang mở")
    # Closed long enough ago to be due: only the worker may remove it.
    closed = await create_closed_job(
        client,
        hr,
        departments,
        interviewers,
        session_factory,
        title="Đã đóng đủ hạn",
        closed_at=clock.utcnow() - timedelta(days=3 * 366),
    )
    for job in (opened, closed):
        tree = await job_tree(session_factory, job["id"])
        response = await delete_job(client, hr, job["id"], job["version"])
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "job_rule_violation"
        assert await job_tree(session_factory, job["id"]) == tree
        assert await deleted_events(session_factory, job["id"]) == []
        current = (await client.get(f"{JOBS_URL}/{job['id']}", headers=hr)).json()
        assert (current["status"], current["version"]) == (job["status"], job["version"])


async def test_stale_version_returns_409_and_keeps_the_draft(
    client, hr, departments, session_factory
) -> None:
    draft = await create_draft(client, hr, departments)
    edited = await client.put(
        f"{JOBS_URL}/{draft['id']}",
        json={
            "title": "Người khác vừa sửa",
            "department_id": departments["Phòng Kỹ thuật"],
            "version": draft["version"],
        },
        headers=hr,
    )
    assert edited.status_code == 200, edited.text

    response = await delete_job(client, hr, draft["id"], draft["version"])

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "version_conflict"
    current = (await client.get(f"{JOBS_URL}/{draft['id']}", headers=hr)).json()
    assert (current["title"], current["version"]) == ("Người khác vừa sửa", draft["version"] + 1)
    assert await deleted_events(session_factory, draft["id"]) == []


async def test_deleting_a_missing_or_already_deleted_posting_returns_404(
    client, hr, departments, session_factory
) -> None:
    draft = await create_draft(client, hr, departments)
    assert (await delete_job(client, hr, draft["id"], draft["version"])).status_code == 204

    again = await delete_job(client, hr, draft["id"], draft["version"])
    assert again.status_code == 404, again.text
    assert again.json()["error"]["code"] == "job_not_found"
    assert len(await deleted_events(session_factory, draft["id"])) == 1

    unknown = await delete_job(client, hr, MAX_BIGINT, 1)
    assert unknown.status_code == 404, unknown.text


@pytest.mark.parametrize(
    ("path_id", "body"),
    [
        (None, None),
        (None, {}),
        (None, {"version": 0}),
        (None, {"version": 2_147_483_648}),
        (None, {"version": "một"}),
        (None, {"version": 1, "status": "DRAFT"}),
        (0, {"version": 1}),
        (MAX_BIGINT + 1, {"version": 1}),
    ],
    ids=[
        "no-body",
        "empty-body",
        "version-zero",
        "version-overflow",
        "version-text",
        "extra-field",
        "id-zero",
        "id-overflow",
    ],
)
async def test_invalid_delete_requests_return_422_without_deleting(
    client, hr, departments, session_factory, path_id, body
) -> None:
    draft = await create_draft(client, hr, departments)
    target = draft["id"] if path_id is None else path_id
    response = await client.request("DELETE", f"{JOBS_URL}/{target}", json=body, headers=hr)

    assert response.status_code == 422, response.text
    assert (await job_tree(session_factory, draft["id"]))["job"] == 1
    assert await deleted_events(session_factory, draft["id"]) == []


async def test_only_hr_employees_may_delete(
    client, hr, departments, interviewers, admin_account, session_factory
) -> None:
    draft = await create_draft(client, hr, departments)
    body = {"version": draft["version"]}
    url = f"{JOBS_URL}/{draft['id']}"

    assert (await client.request("DELETE", url, json=body)).status_code == 401
    interviewer = await login(client, "iv.one@sis.hust.edu.vn")
    administrator = await login(client, admin_account.email, ADMIN_PASSWORD)
    for headers in (interviewer, administrator):
        response = await client.request("DELETE", url, json=body, headers=headers)
        assert response.status_code == 403, response.text

    assert (await job_tree(session_factory, draft["id"]))["job"] == 1
    assert await deleted_events(session_factory, draft["id"]) == []


async def test_failed_audit_rolls_back_the_whole_deletion(
    client, hr, departments, interviewers, employee_account, session_factory, monkeypatch
) -> None:
    from app.modules.recruitment import service as recruitment_service

    draft = await create_versioned_draft(client, hr, departments, interviewers)
    tree = await job_tree(session_factory, draft["id"])
    original = recruitment_service.record_event

    async def failing(session, audit_event) -> None:
        if audit_event.action == DELETED:
            raise RuntimeError("audit store unavailable")
        await original(session, audit_event)

    monkeypatch.setattr(recruitment_service, "record_event", failing)
    result = None
    with contextlib.suppress(RuntimeError):
        result = await delete_draft(
            session_factory, employee_account.id, draft["id"], draft["version"]
        )
    # Either the error propagates or a Failure is returned; never a successful deletion.
    assert result is None or isinstance(result, Failure)

    assert await job_tree(session_factory, draft["id"]) == tree
    assert await deleted_events(session_factory, draft["id"]) == []


async def test_draft_referenced_outside_the_deletion_scope_is_refused_safely(
    client, hr, departments, interviewers, session_factory, job_reference
) -> None:
    draft = await create_versioned_draft(client, hr, departments, interviewers)
    await job_reference.add(draft["id"])
    tree = await job_tree(session_factory, draft["id"])

    response = await delete_job(client, hr, draft["id"], draft["version"])

    assert response.status_code in (409, 422), response.text
    message = response.json()["error"]["message"]
    assert message
    for leaked in ("test_job_reference_probe", "fkey", "violates", "foreign key", "SQL"):
        assert leaked.lower() not in message.lower(), message
    # Nothing was cascaded or partially deleted.
    assert await job_tree(session_factory, draft["id"]) == tree
    assert await job_reference.count(draft["id"]) == 1
    assert await deleted_events(session_factory, draft["id"]) == []


# ---- database safeguards after the deletion migration -------------------------------


async def test_criteria_and_sets_stay_protected_but_the_draft_can_be_deleted(
    client, hr, departments, interviewers, session_factory
) -> None:
    draft = await create_versioned_draft(client, hr, departments, interviewers)
    tree = await job_tree(session_factory, draft["id"])
    old_set, current_set = tree["sets"]
    assert current_set == draft["current_criteria"]["id"]
    first_criterion = tree["criteria"][0]

    for statement, params in (
        ("UPDATE criteria SET weight = 10 WHERE id = :id", {"id": first_criterion}),
        ("DELETE FROM criteria WHERE id = :id", {"id": first_criterion}),
        ("DELETE FROM criteria WHERE criteria_set_id = :id", {"id": old_set}),
        ("DELETE FROM criteria_sets WHERE id = :id", {"id": old_set}),
        ("DELETE FROM criteria_sets WHERE id = :id", {"id": current_set}),
    ):
        async with session_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text(statement), params)
                await session.commit()
            await session.rollback()
        assert await job_tree(session_factory, draft["id"]) == tree, statement

    response = await delete_job(client, hr, draft["id"], draft["version"])
    assert response.status_code == 204, response.text
    assert await leftovers(session_factory, draft["id"], tree) == GONE


# ---- concurrent publish and delete (independent sessions) ---------------------------


async def test_publish_holding_the_lock_wins_over_a_stale_delete(
    client, hr, departments, interviewers, employee_account, session_factory, monkeypatch
) -> None:
    draft = await create_complete_draft(client, hr, departments, interviewers)
    reached, release = gate_audit(monkeypatch, lambda e: e.action == "job.published")

    async def publish():
        async with session_factory() as session:
            return await JobPostingService(session).publish_job(
                actor_id=employee_account.id, job_id=draft["id"], expected_version=draft["version"]
            )

    publish_task = asyncio.create_task(publish())
    delete_task: asyncio.Task | None = None
    try:
        await asyncio.wait_for(reached.wait(), LOCK_TIMEOUT)
        delete_task = asyncio.create_task(
            delete_draft(session_factory, employee_account.id, draft["id"], draft["version"])
        )
        await wait_for_lock_waiter(session_factory)
        assert not delete_task.done()
        release.set()
        published, deleted = await asyncio.wait_for(
            asyncio.gather(publish_task, delete_task), LOCK_TIMEOUT
        )
    finally:
        await settle(release, publish_task, delete_task)

    assert published == draft["id"]
    assert isinstance(deleted, Failure) and deleted.status_code == 409
    current = (await client.get(f"{JOBS_URL}/{draft['id']}", headers=hr)).json()
    assert current["status"] == "OPEN"
    assert await deleted_events(session_factory, draft["id"]) == []


async def test_delete_holding_the_lock_wins_over_a_publish(
    client, hr, departments, interviewers, employee_account, session_factory, monkeypatch
) -> None:
    draft = await create_complete_draft(client, hr, departments, interviewers)
    tree = await job_tree(session_factory, draft["id"])
    reached, release = gate_audit(monkeypatch, lambda e: e.action == DELETED)

    delete_task = asyncio.create_task(
        delete_draft(session_factory, employee_account.id, draft["id"], draft["version"])
    )
    publish_task: asyncio.Task | None = None
    try:
        await asyncio.wait_for(reached.wait(), LOCK_TIMEOUT)
        publish_task = asyncio.create_task(
            client.post(
                f"{JOBS_URL}/{draft['id']}/publish", json={"version": draft["version"]}, headers=hr
            )
        )
        await wait_for_lock_waiter(session_factory)
        assert not publish_task.done()
        release.set()
        deleted, response = await asyncio.wait_for(
            asyncio.gather(delete_task, publish_task), LOCK_TIMEOUT
        )
    finally:
        await settle(release, delete_task, publish_task)

    assert not isinstance(deleted, Failure), deleted
    assert response.status_code == 404, response.text
    assert await leftovers(session_factory, draft["id"], tree) == GONE
    actions = [row.action for row in await audit_rows(session_factory, draft["id"])]
    assert "job.published" not in actions
    assert actions.count(DELETED) == 1


# ---- due date exposed to the interface ----------------------------------------------


def expected_due(closed_at_iso: str) -> str:
    local = datetime.fromisoformat(closed_at_iso.replace("Z", "+00:00")).astimezone(COMPANY_TZ)
    day = local.date()
    try:
        return day.replace(year=day.year + 2).isoformat()
    except ValueError:  # 29 February -> 28 February
        return day.replace(year=day.year + 2, day=28).isoformat()


async def test_closed_postings_expose_the_deletion_due_date(
    client, hr, departments, interviewers, session_factory
) -> None:
    draft = await create_draft(client, hr, departments)
    opened = await create_open_job(client, hr, departments, interviewers, title="Đang mở")
    assert draft["deletion_due_date"] is None
    assert opened["deletion_due_date"] is None

    to_close = await create_open_job(client, hr, departments, interviewers, title="Sẽ đóng")
    closed = await client.post(
        f"{JOBS_URL}/{to_close['id']}/close", json={"version": to_close["version"]}, headers=hr
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["deletion_due_date"] == expected_due(body["closed_at"])

    page = (await client.get(JOBS_URL, headers=hr)).json()
    listed = {item["id"]: item for item in page["items"]}
    assert listed[to_close["id"]]["deletion_due_date"] == body["deletion_due_date"]
    assert listed[draft["id"]]["deletion_due_date"] is None
    assert listed[opened["id"]]["deletion_due_date"] is None

    # Closed at 00:30 on 29/02/2024 in Vietnam (still 28/02 in UTC).
    await set_closed_at(session_factory, to_close["id"], datetime(2024, 2, 28, 17, 30, tzinfo=UTC))
    detail = (await client.get(f"{JOBS_URL}/{to_close['id']}", headers=hr)).json()
    assert detail["deletion_due_date"] == "2026-02-28"


# ---- retention purge ----------------------------------------------------------------


async def test_purge_deletes_closed_postings_from_the_due_day_on(
    client, hr, departments, interviewers, session_factory
) -> None:
    def closed(title: str, closed_at: datetime):
        return create_closed_job(
            client, hr, departments, interviewers, session_factory, title=title, closed_at=closed_at
        )

    # NOW is 17/11/2026 in Vietnam.
    not_yet = await closed("Chưa đủ hạn", datetime(2024, 11, 17, 17, 0, tzinfo=UTC))  # 18/11/2024
    exact = await closed("Đúng hạn", datetime(2024, 11, 16, 17, 0, tzinfo=UTC))  # 17/11/2024 00:00
    older = await closed("Quá hạn", datetime(2023, 5, 1, 3, 0, tzinfo=UTC))
    draft = await create_draft(client, hr, departments, title="Nháp rất cũ")
    opened = await create_open_job(client, hr, departments, interviewers, title="Mở rất lâu")
    for job in (draft, opened):
        await age_job(session_factory, job["id"], datetime(2019, 1, 1, tzinfo=UTC))

    trees = {
        job["id"]: await job_tree(session_factory, job["id"])
        for job in (not_yet, exact, older, draft, opened)
    }
    references = await reference_counts(session_factory)

    purged = await purge(session_factory)

    assert sorted(purged) == sorted([exact["id"], older["id"]])
    for job in (exact, older):
        assert await leftovers(session_factory, job["id"], trees[job["id"]]) == GONE
        events = await deleted_events(session_factory, job["id"])
        assert len(events) == 1
        assert events[0].actor_id is None
        assert events[0].metadata["previous_status"] == "CLOSED"
        assert events[0].metadata.get("reason")
        assert_safe_metadata(events[0].metadata, job["title"], "Phát triển API", "Kinh nghiệm Java")
        # Earlier history of the posting is kept.
        actions = [row.action for row in await audit_rows(session_factory, job["id"])]
        assert actions == ["job.created", "job.closed", DELETED]
    for job in (not_yet, draft, opened):
        assert await job_tree(session_factory, job["id"]) == trees[job["id"]]
        assert await deleted_events(session_factory, job["id"]) == []
    assert await reference_counts(session_factory) == references

    # A second sweep finds nothing and audits nothing twice.
    assert await purge(session_factory) == []
    for job in (exact, older):
        assert len(await deleted_events(session_factory, job["id"])) == 1

    # The next company day the remaining posting becomes due.
    assert await purge(session_factory, now=NOW + timedelta(days=1)) == [not_yet["id"]]


async def test_purge_leap_day_closing_is_due_on_28_february(
    client, hr, departments, interviewers, session_factory
) -> None:
    job = await create_closed_job(
        client,
        hr,
        departments,
        interviewers,
        session_factory,
        title="Đóng ngày nhuận",
        closed_at=datetime(2024, 2, 29, 10, 0, tzinfo=COMPANY_TZ),
    )
    before = datetime(2026, 2, 27, 23, 59, 59, tzinfo=COMPANY_TZ)
    on_the_day = datetime(2026, 2, 28, 0, 0, 0, tzinfo=COMPANY_TZ)

    assert await purge(session_factory, now=before) == []
    assert (await job_tree(session_factory, job["id"]))["job"] == 1
    assert await purge(session_factory, now=on_the_day) == [job["id"]]


async def test_purge_failure_on_one_posting_does_not_block_the_others(
    client, hr, departments, interviewers, session_factory, job_reference, caplog
) -> None:
    caplog.set_level(logging.WARNING)
    old = datetime(2022, 1, 10, 3, 0, tzinfo=UTC)
    blocked = await create_closed_job(
        client, hr, departments, interviewers, session_factory, title="Bị tham chiếu", closed_at=old
    )
    second = await create_closed_job(
        client, hr, departments, interviewers, session_factory, title="Tin thứ hai", closed_at=old
    )
    third = await create_closed_job(
        client, hr, departments, interviewers, session_factory, title="Tin thứ ba", closed_at=old
    )
    await job_reference.add(blocked["id"])
    blocked_tree = await job_tree(session_factory, blocked["id"])

    # The blocked posting comes first in every batch of one; the cursor must move on.
    purged = await purge(session_factory, batch_size=1)

    assert sorted(purged) == sorted([second["id"], third["id"]])
    assert await job_tree(session_factory, blocked["id"]) == blocked_tree
    assert await job_reference.count(blocked["id"]) == 1
    assert await deleted_events(session_factory, blocked["id"]) == []
    for job in (second, third):
        assert len(await deleted_events(session_factory, job["id"])) == 1
    # The failure is reported, without business content or database error text.
    assert any(record.levelno >= logging.WARNING for record in caplog.records)
    for leaked in ("Bị tham chiếu", "test_job_reference_probe", "violates"):
        assert leaked not in caplog.text

    # Retried on the next sweep once the blocking reference is gone.
    await job_reference.remove(blocked["id"])
    assert await purge(session_factory, batch_size=1) == [blocked["id"]]
    assert await leftovers(session_factory, blocked["id"], blocked_tree) == GONE


@contextmanager
def capture_sql(engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


SELECT_JOBS = re.compile(r"^\s*select\b.*\bfrom\s+job_postings\b", re.IGNORECASE | re.DOTALL)
LIMITED = re.compile(r"\blimit\b", re.IGNORECASE)
SINGLE_ROW = re.compile(r"\bid\s*=", re.IGNORECASE)


async def test_purge_reads_candidates_in_bounded_batches(
    client, hr, departments, interviewers, session_factory, db_engine
) -> None:
    old = datetime(2022, 1, 10, 3, 0, tzinfo=UTC)
    jobs = [
        await create_closed_job(
            client, hr, departments, interviewers, session_factory, title=f"Lô {n}", closed_at=old
        )
        for n in range(3)
    ]

    with capture_sql(db_engine) as statements:
        purged = await purge(session_factory, batch_size=2)

    assert purged == sorted(job["id"] for job in jobs)
    reads = [statement for statement in statements if SELECT_JOBS.search(statement)]
    assert any(LIMITED.search(statement) for statement in reads), reads
    # Every read of job_postings is either a bounded batch or a single-row (re)lock.
    unbounded = [
        statement
        for statement in reads
        if not LIMITED.search(statement) and not SINGLE_ROW.search(statement)
    ]
    assert unbounded == []


async def test_concurrent_purges_never_delete_or_audit_a_posting_twice(
    client, hr, departments, interviewers, session_factory, monkeypatch
) -> None:
    old = datetime(2022, 1, 10, 3, 0, tzinfo=UTC)
    jobs = [
        await create_closed_job(
            client,
            hr,
            departments,
            interviewers,
            session_factory,
            title=f"Song song {n}",
            closed_at=old,
        )
        for n in range(3)
    ]
    first_id = min(job["id"] for job in jobs)
    reached, release = gate_audit(
        monkeypatch, lambda e: e.action == DELETED and e.target_id == str(first_id)
    )

    worker_a = asyncio.create_task(purge(session_factory, batch_size=2))
    worker_b: asyncio.Task | None = None
    try:
        await asyncio.wait_for(reached.wait(), LOCK_TIMEOUT)
        # Worker A holds the first posting; worker B skips it instead of waiting.
        worker_b = asyncio.create_task(purge(session_factory, batch_size=2))
        purged_b = await asyncio.wait_for(worker_b, LOCK_TIMEOUT)
        assert first_id not in purged_b
        release.set()
        purged_a = await asyncio.wait_for(worker_a, LOCK_TIMEOUT)
    finally:
        await settle(release, worker_a, worker_b)

    assert first_id in purged_a
    assert set(purged_a).isdisjoint(purged_b)
    assert sorted(purged_a + purged_b) == sorted(job["id"] for job in jobs)
    for job in jobs:
        assert len(await deleted_events(session_factory, job["id"])) == 1
        assert (await job_tree(session_factory, job["id"]))["job"] == 0


async def test_worker_purge_once_uses_the_application_clock(
    client, hr, departments, interviewers, session_factory
) -> None:
    from app.worker import purge_closed_once

    due = await create_closed_job(
        client,
        hr,
        departments,
        interviewers,
        session_factory,
        title="Đóng ba năm trước",
        closed_at=clock.utcnow() - timedelta(days=3 * 366),
    )
    recent = await create_closed_job(
        client,
        hr,
        departments,
        interviewers,
        session_factory,
        title="Vừa đóng",
        closed_at=clock.utcnow() - timedelta(days=30),
    )

    assert await purge_closed_once(session_factory) == 1
    assert await purge_closed_once(session_factory) == 0
    assert (await job_tree(session_factory, due["id"]))["job"] == 0
    assert (await job_tree(session_factory, recent["id"]))["job"] == 1
    assert len(await deleted_events(session_factory, due["id"])) == 1


@pytest.mark.parametrize("change", ["threshold", "posting"])
async def test_criteria_set_updates_cannot_modify_threshold_or_move_history(
    client, hr, departments, interviewers, session_factory, change
) -> None:
    draft = await create_versioned_draft(client, hr, departments, interviewers)
    other = await create_draft(client, hr, departments, title="Không được nhận lịch sử tin khác")
    tree = await job_tree(session_factory, draft["id"])
    old_set = tree["sets"][0]
    if change == "threshold":
        statement = "UPDATE criteria_sets SET auto_invite_threshold = 25 WHERE id = :id"
        params = {"id": old_set}
    else:
        statement = "UPDATE criteria_sets SET job_id = :other WHERE id = :id"
        params = {"id": old_set, "other": other["id"]}
    async with session_factory() as session:
        with pytest.raises(DBAPIError):
            await session.execute(text(statement), params)
            await session.commit()
        await session.rollback()
    assert await job_tree(session_factory, draft["id"]) == tree
