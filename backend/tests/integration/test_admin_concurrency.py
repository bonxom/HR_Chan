import asyncio

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
LOGIN_URL = "/api/v1/auth/login"
ACCOUNTS_URL = "/api/v1/accounts"
ADMIN_EMAIL = "admin@sis.hust.edu.vn"
ADMIN_PASSWORD = "administrator-password-value"
SECOND_ADMIN_EMAIL = "second.admin@sis.hust.edu.vn"
SECOND_ADMIN_PASSWORD = "second-administrator-password"
SECOND_ADMIN_ID = "00000000-0000-4000-8000-000000000000"


async def auth_headers(client, email: str, password: str) -> dict[str, str]:
    response = await client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_second_admin(client, headers, email_outbox) -> dict[str, str]:
    created = await client.post(
        ACCOUNTS_URL,
        json={
            "full_name": "Second Administrator",
            "email": SECOND_ADMIN_EMAIL,
            "account_type": "ADMIN",
            "roles": [],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    completed = await client.post(
        "/api/v1/auth/password/complete",
        json={"token": email_outbox.last_token, "new_password": SECOND_ADMIN_PASSWORD},
        headers=ORIGIN,
    )
    assert completed.status_code == 204
    return await auth_headers(client, SECOND_ADMIN_EMAIL, SECOND_ADMIN_PASSWORD)


async def test_two_admins_racing_to_disable_each_other(
    admin_account, app_client, email_outbox, session_factory
) -> None:
    first_headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    second_headers = await create_second_admin(app_client, first_headers, email_outbox)
    second_id = (
        await app_client.get(ACCOUNTS_URL, params={"account_type": "ADMIN"}, headers=first_headers)
    ).json()["items"]
    second_account_id = next(
        item["id"] for item in second_id if item["email"] == SECOND_ADMIN_EMAIL
    )

    results = await asyncio.gather(
        app_client.post(
            f"{ACCOUNTS_URL}/{second_account_id}/disable",
            json={"reason": "racing disable"},
            headers=first_headers,
        ),
        app_client.post(
            f"{ACCOUNTS_URL}/{admin_account.id}/disable",
            json={"reason": "racing disable"},
            headers=second_headers,
        ),
    )
    # The loser is stopped either by session revocation (401) or actor revalidation (403).
    assert sorted(result.status_code for result in results) in ([200, 401], [200, 403])

    async with session_factory() as session:
        active_admins = await session.scalar(
            text("SELECT count(*) FROM accounts WHERE account_type = 'ADMIN' AND status = 'ACTIVE'")
        )
    assert active_admins == 1


async def test_concurrent_lock_of_the_same_employee(
    employee_account, admin_account, app_client
) -> None:
    headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    results = await asyncio.gather(
        app_client.post(
            f"{ACCOUNTS_URL}/{employee_account.id}/lock",
            json={"reason": "first"},
            headers=headers,
        ),
        app_client.post(
            f"{ACCOUNTS_URL}/{employee_account.id}/lock",
            json={"reason": "second"},
            headers=headers,
        ),
    )
    assert sorted(result.status_code for result in results) == [200, 409]


async def test_concurrent_role_replacements_keep_one_valid_set(
    employee_account, admin_account, app_client
) -> None:
    headers = await auth_headers(app_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    results = await asyncio.gather(
        app_client.put(
            f"{ACCOUNTS_URL}/{employee_account.id}/roles",
            json={"roles": ["HR", "INTERVIEWER"]},
            headers=headers,
        ),
        app_client.put(
            f"{ACCOUNTS_URL}/{employee_account.id}/roles",
            json={"roles": ["DEPT_MANAGER"]},
            headers=headers,
        ),
    )
    assert [result.status_code for result in results] == [200, 200]

    listed = await app_client.get(
        ACCOUNTS_URL, params={"account_type": "EMPLOYEE"}, headers=headers
    )
    roles = next(
        item["roles"] for item in listed.json()["items"] if item["id"] == str(employee_account.id)
    )
    assert roles in (["HR", "INTERVIEWER"], ["DEPT_MANAGER"])
