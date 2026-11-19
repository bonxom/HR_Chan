import asyncio

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
CSRF_URL = "/api/v1/auth/csrf"
CHANGE_URL = "/api/v1/auth/password/change"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"
OLD_PASSWORD = "employee-password-value"
NEW_PASSWORD = "replacement-password-value"


async def login(client, password: str = OLD_PASSWORD):
    return await client.post(
        LOGIN_URL, json={"email": "employee@sis.hust.edu.vn", "password": password}, headers=ORIGIN
    )


async def csrf_proof(client) -> str:
    return (await client.get(CSRF_URL)).json()["csrf_token"]


async def change(client, token: str, proof: str, current: str, new: str):
    return await client.post(
        CHANGE_URL,
        json={"current_password": current, "new_password": new},
        headers={**ORIGIN, "X-CSRF-Token": proof, "Authorization": f"Bearer {token}"},
    )


async def test_change_rotates_only_the_current_session(employee_account, app_client) -> None:
    first = await login(app_client)
    first_token = first.json()["access_token"]
    first_refresh = app_client.cookies["refresh_token"]
    second = await login(app_client)
    second_token = second.json()["access_token"]
    second_refresh = app_client.cookies["refresh_token"]
    assert first_refresh != second_refresh
    proof = await csrf_proof(app_client)

    changed = await change(app_client, first_token, proof, OLD_PASSWORD, NEW_PASSWORD)
    assert changed.status_code == 200
    new_token = changed.json()["access_token"]
    assert new_token != first_token

    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {new_token}"})
    ).status_code == 200
    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {first_token}"})
    ).status_code == 401
    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {second_token}"})
    ).status_code == 401

    headers = {**ORIGIN, "X-CSRF-Token": proof}
    assert (
        await app_client.post(
            REFRESH_URL,
            headers={
                **headers,
                "Cookie": f"refresh_token={second_refresh}; csrf_token={proof.split('.')[0]}",
            },
        )
    ).status_code == 401


async def test_change_requires_the_current_password(employee_account, app_client) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)

    rejected = await change(app_client, token, proof, "wrong-password-value", NEW_PASSWORD)
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_current_password"
    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200


async def test_change_never_applies_a_short_password(employee_account, app_client) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)
    rejected = await change(app_client, token, proof, OLD_PASSWORD, "1234567")
    assert rejected.status_code == 422
    assert (await login(app_client)).status_code == 200


async def test_change_requires_csrf_and_trusted_origin(employee_account, app_client) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)
    missing_csrf = await app_client.post(
        CHANGE_URL,
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        headers={**ORIGIN, "Authorization": f"Bearer {token}"},
    )
    assert missing_csrf.status_code == 403
    untrusted = await app_client.post(
        CHANGE_URL,
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        headers={
            "Origin": "https://evil.example",
            "X-CSRF-Token": proof,
            "Authorization": f"Bearer {token}",
        },
    )
    assert untrusted.status_code == 403


async def test_new_password_is_required_at_the_next_login(employee_account, app_client) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)
    assert (await change(app_client, token, proof, OLD_PASSWORD, NEW_PASSWORD)).status_code == 200

    assert (await login(app_client, OLD_PASSWORD)).status_code == 401
    assert (await login(app_client, NEW_PASSWORD)).status_code == 200


async def test_change_invalidates_outstanding_password_links(
    employee_account, app_client, email_outbox
) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)

    recovery = await app_client.post(
        "/api/v1/auth/password/recovery",
        json={"email": employee_account.email},
        headers=ORIGIN,
    )
    assert recovery.status_code == 202
    [recovery_mail] = await email_outbox.drain()
    assert recovery_mail.to == employee_account.email
    token_from_email = email_outbox.last_token

    changed = await change(app_client, token, proof, OLD_PASSWORD, NEW_PASSWORD)
    assert changed.status_code == 200

    completion = await app_client.post(
        "/api/v1/auth/password/complete",
        json={"token": token_from_email, "new_password": "a-third-password-value"},
        headers=ORIGIN,
    )
    assert completion.status_code == 400
    assert completion.json()["error"]["code"] == "invalid_password_link"


async def test_stale_concurrent_change_is_rejected(employee_account, app_client) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)

    results = await asyncio.gather(
        change(app_client, token, proof, OLD_PASSWORD, "first-replacement-value"),
        change(app_client, token, proof, OLD_PASSWORD, "second-replacement-value"),
    )
    statuses = sorted(result.status_code for result in results)
    assert statuses == [200, 401]


async def test_change_records_an_audit_event(employee_account, app_client, session_factory) -> None:
    token = (await login(app_client)).json()["access_token"]
    proof = await csrf_proof(app_client)
    await change(app_client, token, proof, OLD_PASSWORD, NEW_PASSWORD)

    async with session_factory() as session:
        actions = (
            await session.execute(
                text("SELECT action FROM audit_events WHERE action = 'auth.password.changed'")
            )
        ).all()
    assert [row.action for row in actions] == ["auth.password.changed"]
