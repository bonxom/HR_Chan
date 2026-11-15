import pytest

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
ACCOUNTS_URL = "/api/v1/accounts"
AUDIT_URL = "/api/v1/audit-events"
ADMIN_EMAIL = "admin@sis.hust.edu.vn"
ADMIN_PASSWORD = "administrator-password-value"
EMPLOYEE_PASSWORD = "employee-password-value"


async def auth_headers(client, email: str, password: str) -> dict[str, str]:
    response = await client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_audit_listing_requires_an_administrator(
    employee_account, admin_account, app_client
) -> None:
    assert (await app_client.get(AUDIT_URL)).status_code == 401
    employee_headers = await auth_headers(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    assert (await app_client.get(AUDIT_URL, headers=employee_headers)).status_code == 403


async def test_audit_events_are_metadata_only(employee_account, admin_account, app_client) -> None:
    headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    created = await app_client.post(
        ACCOUNTS_URL,
        json={
            "full_name": "Audited Employee",
            "email": "audited@sis.hust.edu.vn",
            "account_type": "EMPLOYEE",
            "roles": ["HR"],
        },
        headers=headers,
    )
    assert created.status_code == 201
    target_id = created.json()["account"]["id"]

    response = await app_client.get(AUDIT_URL, headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    for item in items:
        assert set(item) == {
            "id",
            "actor_id",
            "action",
            "outcome",
            "timestamp",
            "target_type",
            "target_id",
            "metadata",
        }
        assert set(item["metadata"]) <= {
            "reason",
            "roles",
            "previous_roles",
            "status",
            "previous_status",
            "purpose",
            "email_delivery",
        }
        assert all(
            value is None or "token" not in str(value).lower()
            for value in item["metadata"].values()
        )

    filtered = await app_client.get(AUDIT_URL, params={"target_id": target_id}, headers=headers)
    assert [item["action"] for item in filtered.json()["items"]] == ["account.created"]


async def test_audit_filters_and_cursor_pagination(
    employee_account, admin_account, app_client, session_factory
) -> None:
    headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    for index in range(3):
        assert (
            await app_client.post(
                ACCOUNTS_URL,
                json={
                    "full_name": f"Filtered {index}",
                    "email": f"filtered{index}@sis.hust.edu.vn",
                    "account_type": "EMPLOYEE",
                    "roles": ["HR"],
                },
                headers=headers,
            )
        ).status_code == 201

    by_action = await app_client.get(
        AUDIT_URL, params={"action": "account.created"}, headers=headers
    )
    assert {item["action"] for item in by_action.json()["items"]} == {"account.created"}

    by_actor = await app_client.get(
        AUDIT_URL, params={"actor_id": str(admin_account.id)}, headers=headers
    )
    assert by_actor.status_code == 200
    assert {item["actor_id"] for item in by_actor.json()["items"]} == {str(admin_account.id)}

    page_one = await app_client.get(AUDIT_URL, params={"limit": 2}, headers=headers)
    assert page_one.status_code == 200
    assert len(page_one.json()["items"]) == 2
    cursor = page_one.json()["next_cursor"]
    assert cursor

    seen = [item["id"] for item in page_one.json()["items"]]
    while cursor:
        page = await app_client.get(
            AUDIT_URL, params={"limit": 2, "cursor": cursor}, headers=headers
        )
        assert page.status_code == 200
        seen.extend(item["id"] for item in page.json()["items"])
        cursor = page.json()["next_cursor"]
    assert len(seen) == len(set(seen))

    future = await app_client.get(
        AUDIT_URL, params={"from": "2999-01-01T00:00:00Z"}, headers=headers
    )
    assert future.status_code == 200
    assert future.json()["items"] == []

    invalid = await app_client.get(AUDIT_URL, params={"cursor": "garbage"}, headers=headers)
    assert invalid.status_code == 400

    async with session_factory() as session:
        total = await session.scalar(
            __import__("sqlalchemy").text("SELECT count(*) FROM audit_events")
        )
    assert total >= len(seen)


async def test_audit_api_has_no_mutation_endpoints(admin_account, app_client) -> None:
    headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    for method, payload in (("post", {}), ("put", {}), ("delete", None)):
        response = await getattr(app_client, method)(
            AUDIT_URL,
            **({"json": payload} if payload is not None else {}),
            headers=headers,
        )
        assert response.status_code == 405


async def test_audit_failure_rolls_back_the_administrative_change(
    employee_account, admin_account, session_factory, monkeypatch
) -> None:
    from sqlalchemy import text

    from app.modules.accounts import service as account_service
    from app.modules.accounts.rules import EmployeeRole

    async def failing_record_event(*args, **kwargs):
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(account_service, "record_event", failing_record_event)
    async with session_factory() as session:
        with pytest.raises(RuntimeError):
            await account_service.replace_roles(
                session,
                actor_id=admin_account.id,
                account_id=employee_account.id,
                roles=[EmployeeRole.INTERVIEWER],
            )
        await session.rollback()

    async with session_factory() as session:
        roles = await session.scalar(
            text("SELECT roles FROM accounts WHERE id = :id"),
            {"id": employee_account.id},
        )
    assert roles == ["HR"]
