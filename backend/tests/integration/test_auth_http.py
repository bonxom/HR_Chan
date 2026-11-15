import pytest
from sqlalchemy import text

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
EMPLOYEE_PASSWORD = "employee-password-value"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


async def login(client, email: str, password: str, headers: dict[str, str] | None = ORIGIN):
    return await client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers=headers or {}
    )


def set_cookie_header(response, name: str) -> str:
    return next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{name}=")
    )


async def test_login_returns_tokens_and_scoped_cookies(employee_account, app_client) -> None:
    response = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 300
    assert body["access_token"]
    assert body["account"]["id"] == str(employee_account.id)
    assert body["account"]["roles"] == ["HR"]
    assert body["account"]["status"] == "ACTIVE"
    assert "password" not in response.text
    assert response.headers["cache-control"] == "no-store"

    refresh_cookie = set_cookie_header(response, "refresh_token").lower()
    assert "httponly" in refresh_cookie
    assert "path=/api/v1/auth" in refresh_cookie
    assert "samesite=lax" in refresh_cookie
    assert "secure" not in refresh_cookie
    csrf_cookie = set_cookie_header(response, "csrf_token").lower()
    assert "httponly" in csrf_cookie


async def test_login_failures_share_one_generic_response(
    employee_account, pending_account_factory, app_client
) -> None:
    pending = await pending_account_factory()
    responses = [
        await login(app_client, "nobody@sis.hust.edu.vn", "unknown-password"),
        await login(app_client, pending.email, "unknown-password"),
        await login(app_client, employee_account.email, "wrong-password-value"),
    ]
    bodies = [response.json() for response in responses]
    assert {response.status_code for response in responses} == {401}
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0]["error"]["code"] == "invalid_credentials"
    for response in responses:
        assert "set-cookie" not in response.headers.keys()
        assert pending.email not in response.text


async def test_login_requires_a_trusted_origin(employee_account, app_client) -> None:
    missing = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD, headers={})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "untrusted_origin"

    untrusted = await login(
        app_client,
        employee_account.email,
        EMPLOYEE_PASSWORD,
        headers={"Origin": "https://evil.example"},
    )
    assert untrusted.status_code == 403


async def test_five_failures_block_the_identifier(employee_account, app_client) -> None:
    for _ in range(5):
        assert (
            await login(app_client, employee_account.email, "wrong-password-value")
        ).status_code == 401

    blocked = await login(app_client, employee_account.email, "wrong-password-value")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0

    # The block also applies to a correct password until the window expires.
    still_blocked = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    assert still_blocked.status_code == 429


async def test_successful_login_clears_the_failure_counter(employee_account, app_client) -> None:
    for _ in range(4):
        assert (
            await login(app_client, employee_account.email, "wrong-password-value")
        ).status_code == 401
    assert (await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)).status_code == 200

    for _ in range(4):
        assert (
            await login(app_client, employee_account.email, "wrong-password-value")
        ).status_code == 401


async def test_current_account_requires_a_bearer_token(employee_account, app_client) -> None:
    assert (await app_client.get(ME_URL)).status_code == 401

    response = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    token = response.json()["access_token"]
    me = await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == employee_account.email
    assert "password_hash" not in me.text
    assert me.headers["cache-control"] == "no-store"

    anonymous = await app_client.get(ME_URL, headers={"Authorization": "Bearer not-a-real-token"})
    assert anonymous.status_code == 401


async def test_cookie_credentials_do_not_authenticate_bearer_routes(
    employee_account, app_client
) -> None:
    assert (await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)).status_code == 200
    assert (await app_client.get(ME_URL)).status_code == 401


async def test_logout_revokes_the_session_and_rejects_the_old_token(
    employee_account, app_client
) -> None:
    logged_in = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    token = logged_in.json()["access_token"]
    proof = (await app_client.get("/api/v1/auth/csrf")).json()["csrf_token"]

    logout = await app_client.post("/api/v1/auth/logout", headers={**ORIGIN, "X-CSRF-Token": proof})
    assert logout.status_code == 204
    assert "refresh_token=" in set_cookie_header(logout, "refresh_token")

    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401

    repeated = await app_client.post("/api/v1/auth/logout", headers=ORIGIN)
    assert repeated.status_code == 204


async def test_revoked_session_cannot_use_an_unexpired_token(
    employee_account, app_client, session_factory
) -> None:
    token = (await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)).json()[
        "access_token"
    ]
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET revoked_at = now(), revoked_reason = 'logout'")
        )
        await session.commit()
    response = await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_locked_account_invalidates_an_existing_token(
    employee_account, app_client, session_factory
) -> None:
    token = (await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)).json()[
        "access_token"
    ]
    async with session_factory() as session:
        await session.execute(
            text("UPDATE accounts SET status = 'LOCKED' WHERE email = :email"),
            {"email": employee_account.email},
        )
        await session.commit()
    response = await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_role_and_type_changes_apply_to_the_next_request(
    employee_account, app_client, session_factory
) -> None:
    logged_in = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    token = logged_in.json()["access_token"]

    async with session_factory() as session:
        await session.execute(
            text("UPDATE accounts SET roles = ARRAY['INTERVIEWER']::text[] WHERE email = :email"),
            {"email": employee_account.email},
        )
        await session.commit()

    me = await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["roles"] == ["INTERVIEWER"]


async def test_login_records_audit_events(employee_account, app_client, session_factory) -> None:
    await login(app_client, employee_account.email, "wrong-password-value")
    await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    async with session_factory() as session:
        actions = (
            await session.execute(
                text(
                    "SELECT action, outcome FROM audit_events "
                    "WHERE action LIKE 'auth.login%' ORDER BY timestamp, action"
                )
            )
        ).all()
    assert [(row.action, row.outcome) for row in actions] == [
        ("auth.login.failed", "FAILURE"),
        ("auth.login.succeeded", "SUCCESS"),
    ]
    async with session_factory() as session:
        last_login = await session.scalar(
            text("SELECT last_login_at FROM accounts WHERE email = :email"),
            {"email": employee_account.email},
        )
    assert last_login is not None


async def test_disabled_account_cannot_log_in(
    employee_account, app_client, session_factory
) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE accounts SET status = 'DISABLED' WHERE email = :email"),
            {"email": employee_account.email},
        )
        await session.commit()
    response = await login(app_client, employee_account.email, EMPLOYEE_PASSWORD)
    assert response.status_code == 401
