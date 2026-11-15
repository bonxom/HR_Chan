import pytest

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
CSRF_URL = "/api/v1/auth/csrf"
LOGOUT_URL = "/api/v1/auth/logout"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
PASSWORD = "employee-password-value"


async def csrf_proof(client) -> str:
    response = await client.get(CSRF_URL)
    assert response.status_code == 200
    return response.json()["csrf_token"]


async def authenticated(client, email: str) -> str:
    response = await client.post(
        LOGIN_URL, json={"email": email, "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_csrf_bootstrap_issues_cookie_and_signed_proof(app_client) -> None:
    response = await app_client.get(CSRF_URL)
    assert response.status_code == 200
    proof = response.json()["csrf_token"]
    token, separator, signature = proof.partition(".")
    assert separator and token and signature
    assert set(response.json()) == {"csrf_token"}
    assert response.headers["cache-control"] == "no-store"
    cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith("csrf_token=")
    )
    attributes = cookie.lower()
    assert "httponly" in attributes
    assert "path=/api/v1/auth" in attributes
    assert token == cookie.split(";", 1)[0].split("=", 1)[1]


async def test_logout_requires_csrf_proof_and_leaves_the_session_alive(
    employee_account, app_client
) -> None:
    token = await authenticated(app_client, employee_account.email)
    await csrf_proof(app_client)

    rejected = await app_client.post(LOGOUT_URL, headers=ORIGIN)
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "csrf_verification_failed"

    tricked = await app_client.post(LOGOUT_URL, headers={**ORIGIN, "X-CSRF-Token": "forged.proof"})
    assert tricked.status_code == 403
    assert (
        await app_client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200


async def test_logout_rejects_a_proof_that_does_not_match_the_cookie(
    employee_account, app_client
) -> None:
    await authenticated(app_client, employee_account.email)
    valid = await csrf_proof(app_client)
    other = (await app_client.get(CSRF_URL)).json()["csrf_token"]
    assert valid != other
    # The second bootstrap replaced the cookie, so the earlier proof is stale.
    stale = await app_client.post(LOGOUT_URL, headers={**ORIGIN, "X-CSRF-Token": valid})
    assert stale.status_code == 403
    accepted = await app_client.post(LOGOUT_URL, headers={**ORIGIN, "X-CSRF-Token": other})
    assert accepted.status_code == 204


async def test_unsafe_auth_routes_require_trusted_origin(app_client) -> None:
    for path, payload in (
        (LOGOUT_URL, None),
        ("/api/v1/auth/password/recovery", {"email": "someone@sis.hust.edu.vn"}),
        ("/api/v1/auth/password/complete", {"token": "token", "new_password": "password-value"}),
    ):
        response = await app_client.post(
            path, json=payload, headers={"Origin": "https://untrusted.example"}
        )
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "untrusted_origin"


async def test_protected_bearer_routes_ignore_origin_and_cookies(
    employee_account, app_client
) -> None:
    await authenticated(app_client, employee_account.email)
    response = await app_client.get(ME_URL, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 401
