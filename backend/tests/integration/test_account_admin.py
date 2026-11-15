import pytest

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
ACCOUNTS_URL = "/api/v1/accounts"
ADMIN_EMAIL = "admin@sis.hust.edu.vn"
ADMIN_PASSWORD = "administrator-password-value"
EMPLOYEE_PASSWORD = "employee-password-value"
SECOND_ADMIN_PASSWORD = "second-administrator-password"


async def auth_headers(client, email: str, password: str) -> dict[str, str]:
    response = await client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def admin_headers(client) -> dict[str, str]:
    return await auth_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)


async def create_account(client, headers, **overrides) -> dict:
    payload = {
        "full_name": "New Employee",
        "email": "new.employee@sis.hust.edu.vn",
        "account_type": "EMPLOYEE",
        "roles": ["HR"],
    }
    payload.update(overrides)
    return await client.post(ACCOUNTS_URL, json=payload, headers=headers)


async def test_actor_matrix_for_account_administration(
    employee_account, admin_account, app_client
) -> None:
    assert (await app_client.get(ACCOUNTS_URL)).status_code == 401

    employee_headers = await auth_headers(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    assert (await app_client.get(ACCOUNTS_URL, headers=employee_headers)).status_code == 403
    assert (
        await app_client.post(
            ACCOUNTS_URL,
            json={"full_name": "X", "email": "x@sis.hust.edu.vn"},
            headers=employee_headers,
        )
    ).status_code == 403

    administrator = await admin_headers(app_client)
    assert (await app_client.get(ACCOUNTS_URL, headers=administrator)).status_code == 200


async def test_admin_creates_employee_and_admin_accounts(
    admin_account, app_client, email_outbox
) -> None:
    headers = await admin_headers(app_client)

    created = await create_account(app_client, headers)
    assert created.status_code == 201
    body = created.json()
    assert body["account"]["status"] == "PENDING_SETUP"
    assert body["account"]["roles"] == ["HR"]
    assert body["email_delivery"] == "sent"

    administrator = await create_account(
        app_client,
        headers,
        email="second.admin@sis.hust.edu.vn",
        account_type="ADMIN",
        roles=[],
    )
    assert administrator.status_code == 201
    assert administrator.json()["account"]["roles"] == []

    assert (
        await create_account(app_client, headers, email="bad.roles@sis.hust.edu.vn", roles=[])
    ).status_code == 400
    assert (
        await create_account(
            app_client,
            headers,
            email="admin.roles@sis.hust.edu.vn",
            account_type="ADMIN",
            roles=["HR"],
        )
    ).status_code == 400
    assert (await create_account(app_client, headers, email="person@gmail.com")).status_code == 400

    duplicate = await create_account(app_client, headers, email="NEW.EMPLOYEE@sis.hust.edu.vn")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_email"


async def test_creation_delivery_failure_is_reported(
    admin_account, app_client, email_outbox
) -> None:
    headers = await admin_headers(app_client)
    email_outbox.failing = True
    created = await create_account(app_client, headers, email="undelivered@sis.hust.edu.vn")
    assert created.status_code == 201
    assert created.json()["email_delivery"] == "failed"
    assert created.json()["account"]["status"] == "PENDING_SETUP"


async def test_role_replacement_applies_to_live_sessions(
    employee_account, admin_account, app_client
) -> None:
    headers = await admin_headers(app_client)
    employee_headers = await auth_headers(app_client, employee_account.email, EMPLOYEE_PASSWORD)

    response = await app_client.put(
        f"{ACCOUNTS_URL}/{employee_account.id}/roles",
        json={"roles": ["INTERVIEWER", "DEPT_MANAGER"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["roles"] == ["INTERVIEWER", "DEPT_MANAGER"]

    me = await app_client.get("/api/v1/auth/me", headers=employee_headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["INTERVIEWER", "DEPT_MANAGER"]

    for invalid in (["PROBATION", "HR"], [], ["UNKNOWN"]):
        rejected = await app_client.put(
            f"{ACCOUNTS_URL}/{employee_account.id}/roles",
            json={"roles": invalid},
            headers=headers,
        )
        assert rejected.status_code in (400, 422)

    admin_target = await app_client.put(
        f"{ACCOUNTS_URL}/{admin_account.id}/roles",
        json={"roles": ["HR"]},
        headers=headers,
    )
    assert admin_target.status_code == 409
    assert admin_target.json()["error"]["code"] == "invalid_account_type"


async def test_lock_unlock_and_disable_lifecycle(
    employee_account, admin_account, app_client, email_outbox
) -> None:
    headers = await admin_headers(app_client)
    url = f"{ACCOUNTS_URL}/{employee_account.id}"

    assert (
        await app_client.post(f"{url}/lock", json={"reason": ""}, headers=headers)
    ).status_code in (
        400,
        422,
    )
    locked = await app_client.post(
        f"{url}/lock", json={"reason": "security review"}, headers=headers
    )
    assert locked.status_code == 200
    assert locked.json()["status"] == "LOCKED"
    assert (
        await app_client.post(
            LOGIN_URL,
            json={"email": employee_account.email, "password": EMPLOYEE_PASSWORD},
            headers=ORIGIN,
        )
    ).status_code == 401
    assert (
        await app_client.post(f"{url}/lock", json={"reason": "again"}, headers=headers)
    ).status_code == 409

    unlocked = await app_client.post(f"{url}/unlock", headers=headers)
    assert unlocked.status_code == 200
    assert unlocked.json()["account"]["status"] == "PASSWORD_RESET_REQUIRED"
    assert unlocked.json()["email_delivery"] == "sent"
    assert (await app_client.post(f"{url}/unlock", headers=headers)).status_code == 409

    completed = await app_client.post(
        "/api/v1/auth/password/complete",
        json={"token": email_outbox.last_token, "new_password": "reset-password-value"},
        headers=ORIGIN,
    )
    assert completed.status_code == 204
    assert (
        await app_client.post(
            LOGIN_URL,
            json={"email": employee_account.email, "password": "reset-password-value"},
            headers=ORIGIN,
        )
    ).status_code == 200

    disabled = await app_client.post(
        f"{url}/disable", json={"reason": "left the company"}, headers=headers
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    assert (
        await app_client.post(f"{url}/disable", json={"reason": "again"}, headers=headers)
    ).status_code == 409
    assert (
        await app_client.post(f"{url}/lock", json={"reason": "again"}, headers=headers)
    ).status_code == 409
    assert (await app_client.post(f"{url}/unlock", headers=headers)).status_code == 409
    assert (
        await app_client.post(
            LOGIN_URL,
            json={"email": employee_account.email, "password": "reset-password-value"},
            headers=ORIGIN,
        )
    ).status_code == 401


async def test_self_lock_and_self_disable_are_forbidden(
    admin_account, app_client, email_outbox
) -> None:
    headers = await admin_headers(app_client)
    url = f"{ACCOUNTS_URL}/{admin_account.id}"
    assert (
        await app_client.post(f"{url}/lock", json={"reason": "self"}, headers=headers)
    ).status_code == 409
    assert (
        await app_client.post(f"{url}/disable", json={"reason": "self"}, headers=headers)
    ).status_code == 409

    created = await create_account(
        app_client,
        headers,
        email="second.admin@sis.hust.edu.vn",
        account_type="ADMIN",
        roles=[],
    )
    assert created.status_code == 201


async def test_final_admin_guard_blocks_the_last_active_administrator(
    admin_account, app_client, email_outbox, monkeypatch
) -> None:
    from app.modules.accounts import repository

    headers = await admin_headers(app_client)
    created = await create_account(
        app_client,
        headers,
        email="another.admin@sis.hust.edu.vn",
        account_type="ADMIN",
        roles=[],
    )
    assert created.status_code == 201
    target_id = created.json()["account"]["id"]

    activated = await app_client.post(
        "/api/v1/auth/password/complete",
        json={"token": email_outbox.last_token, "new_password": SECOND_ADMIN_PASSWORD},
        headers=ORIGIN,
    )
    assert activated.status_code == 204

    async def only_one_active_admin(session):
        return 1

    monkeypatch.setattr(repository, "active_admin_count", only_one_active_admin)
    blocked = await app_client.post(
        f"{ACCOUNTS_URL}/{target_id}/disable",
        json={"reason": "remove last admin"},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "final_admin_protected"


async def test_account_listing_paginates_and_filters(
    employee_account, admin_account, app_client
) -> None:
    headers = await admin_headers(app_client)
    for index in range(3):
        await create_account(app_client, headers, email=f"listing{index}@sis.hust.edu.vn")

    first = await app_client.get(ACCOUNTS_URL, params={"limit": 2}, headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"]

    second = await app_client.get(
        ACCOUNTS_URL, params={"limit": 2, "cursor": body["next_cursor"]}, headers=headers
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 2
    ids = {item["id"] for item in body["items"]} | {item["id"] for item in second.json()["items"]}
    assert len(ids) == 4

    pending = await app_client.get(
        ACCOUNTS_URL, params={"status": "PENDING_SETUP"}, headers=headers
    )
    assert pending.status_code == 200
    assert {item["status"] for item in pending.json()["items"]} == {"PENDING_SETUP"}

    admins = await app_client.get(ACCOUNTS_URL, params={"account_type": "ADMIN"}, headers=headers)
    assert [item["account_type"] for item in admins.json()["items"]] == ["ADMIN"]

    assert (
        await app_client.get(ACCOUNTS_URL, params={"limit": 0}, headers=headers)
    ).status_code == 422
    assert (
        await app_client.get(ACCOUNTS_URL, params={"limit": 101}, headers=headers)
    ).status_code == 422
    invalid = await app_client.get(ACCOUNTS_URL, params={"cursor": "not-a-cursor"}, headers=headers)
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_cursor"


async def test_invitation_resend_is_limited_to_pending_accounts(
    employee_account, admin_account, app_client, email_outbox
) -> None:
    headers = await admin_headers(app_client)
    pending = await create_account(app_client, headers, email="pending.invite@sis.hust.edu.vn")
    pending_id = pending.json()["account"]["id"]

    resent = await app_client.post(f"{ACCOUNTS_URL}/{pending_id}/invitation", headers=headers)
    assert resent.status_code == 200
    assert resent.json()["email_delivery"] == "sent"

    throttled = await app_client.post(f"{ACCOUNTS_URL}/{pending_id}/invitation", headers=headers)
    assert throttled.status_code == 429
    assert throttled.headers["retry-after"]

    active = await app_client.post(
        f"{ACCOUNTS_URL}/{employee_account.id}/invitation", headers=headers
    )
    assert active.status_code == 409

    missing = await app_client.post(
        f"{ACCOUNTS_URL}/00000000-0000-4000-8000-000000000000/invitation", headers=headers
    )
    assert missing.status_code == 404
