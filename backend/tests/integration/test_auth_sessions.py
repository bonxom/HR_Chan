import asyncio

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
CSRF_URL = "/api/v1/auth/csrf"
REFRESH_URL = "/api/v1/auth/refresh"
ACTIVITY_URL = "/api/v1/auth/activity"
ME_URL = "/api/v1/auth/me"
PASSWORD = "employee-password-value"


async def csrf_proof(client) -> str:
    return (await client.get(CSRF_URL)).json()["csrf_token"]


def cookie_header(refresh_token: str, proof: str) -> str:
    return f"refresh_token={refresh_token}; csrf_token={proof.split('.')[0]}"


async def login(client, email: str, password: str = PASSWORD):
    return await client.post(LOGIN_URL, json={"email": email, "password": password}, headers=ORIGIN)


async def post_refresh(client, proof: str, refresh_token: str | None = None):
    headers = {**ORIGIN, "X-CSRF-Token": proof}
    if refresh_token is not None:
        headers["Cookie"] = cookie_header(refresh_token, proof)
    return await client.post(REFRESH_URL, headers=headers)


async def test_refresh_rotates_the_cookie_and_keeps_the_absolute_limit(
    employee_account, app_client
) -> None:
    await login(app_client, employee_account.email)
    original = app_client.cookies["refresh_token"]
    proof = await csrf_proof(app_client)

    refreshed = await post_refresh(app_client, proof)
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert app_client.cookies["refresh_token"] != original
    cookie = next(
        header
        for header in refreshed.headers.get_list("set-cookie")
        if header.startswith("refresh_token=")
    )
    max_age = int(cookie.lower().split("max-age=")[1].split(";")[0])
    assert 0 < max_age <= 43200
    me = await app_client.get(ME_URL, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


async def test_replayed_refresh_token_revokes_only_its_own_session(
    employee_account, app_client
) -> None:
    first = await login(app_client, employee_account.email)
    first_refresh = app_client.cookies["refresh_token"]
    second = await login(app_client, employee_account.email)
    second_refresh = app_client.cookies["refresh_token"]
    assert first_refresh != second_refresh
    proof = await csrf_proof(app_client)

    rotated = await post_refresh(app_client, proof, first_refresh)
    assert rotated.status_code == 200

    replay = await post_refresh(app_client, proof, first_refresh)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_session"

    # The rotated token belongs to the revoked family.
    assert (
        await post_refresh(app_client, proof, app_client.cookies["refresh_token"])
    ).status_code == 401
    # The other device keeps working.
    other = await post_refresh(app_client, proof, second_refresh)
    assert other.status_code == 200

    assert (
        await app_client.get(
            ME_URL, headers={"Authorization": f"Bearer {first.json()['access_token']}"}
        )
    ).status_code == 401
    assert second.status_code == 200


async def test_concurrent_refresh_attempts_rotate_exactly_once(
    employee_account, app_client, session_factory
) -> None:
    await login(app_client, employee_account.email)
    token = app_client.cookies["refresh_token"]
    proof = await csrf_proof(app_client)

    first, second = await asyncio.gather(
        post_refresh(app_client, proof, token), post_refresh(app_client, proof, token)
    )
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [200, 401]

    async with session_factory() as session:
        revoked = await session.scalar(
            text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL")
        )
    assert revoked == 1


async def test_idle_expiry_blocks_refresh(employee_account, app_client, session_factory) -> None:
    await login(app_client, employee_account.email)
    proof = await csrf_proof(app_client)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET last_activity_at = now() - interval '31 minutes'")
        )
        await session.commit()
    assert (await post_refresh(app_client, proof)).status_code == 401


async def test_absolute_expiry_blocks_refresh_and_access(
    employee_account, app_client, session_factory
) -> None:
    logged_in = await login(app_client, employee_account.email)
    proof = await csrf_proof(app_client)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET absolute_expires_at = now() - interval '1 second'")
        )
        await session.commit()

    assert (await post_refresh(app_client, proof)).status_code == 401
    response = await app_client.get(
        ME_URL, headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    )
    assert response.status_code == 401


async def test_refresh_does_not_extend_the_idle_timer(
    employee_account, app_client, session_factory
) -> None:
    await login(app_client, employee_account.email)
    proof = await csrf_proof(app_client)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET last_activity_at = now() - interval '29 minutes'")
        )
        await session.commit()
        stale_activity = await session.scalar(text("SELECT last_activity_at FROM auth_sessions"))

    assert (await post_refresh(app_client, proof)).status_code == 200

    async with session_factory() as session:
        current_activity = await session.scalar(text("SELECT last_activity_at FROM auth_sessions"))
    assert current_activity == stale_activity


async def test_activity_extends_idle_time_at_most_once_per_minute(
    employee_account, app_client, session_factory
) -> None:
    logged_in = await login(app_client, employee_account.email)
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET last_activity_at = now() - interval '2 minutes'")
        )
        await session.commit()

    assert (await app_client.post(ACTIVITY_URL, headers=headers)).status_code == 204
    async with session_factory() as session:
        extended = await session.scalar(text("SELECT last_activity_at FROM auth_sessions"))

    assert (await app_client.post(ACTIVITY_URL, headers=headers)).status_code == 204
    async with session_factory() as session:
        unchanged = await session.scalar(text("SELECT last_activity_at FROM auth_sessions"))
    assert unchanged == extended


async def test_activity_cannot_revive_an_absolutely_expired_session(
    employee_account, app_client, session_factory
) -> None:
    logged_in = await login(app_client, employee_account.email)
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_sessions SET absolute_expires_at = now() - interval '1 second'")
        )
        await session.commit()

    # The access token itself is already rejected by the principal check.
    assert (await app_client.post(ACTIVITY_URL, headers=headers)).status_code == 401


async def test_expired_refresh_token_is_rejected(
    employee_account, app_client, session_factory
) -> None:
    await login(app_client, employee_account.email)
    proof = await csrf_proof(app_client)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE auth_refresh_tokens SET expires_at = now() - interval '1 second'")
        )
        await session.commit()
    assert (await post_refresh(app_client, proof)).status_code == 401


async def test_refresh_and_activity_require_bearer_and_csrf(employee_account, app_client) -> None:
    await login(app_client, employee_account.email)
    assert (await app_client.post(REFRESH_URL, headers=ORIGIN)).status_code == 403
    assert (await app_client.post(ACTIVITY_URL)).status_code == 401
