from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import Settings
from app.main import create_app
from app.modules.accounts.dev_fixtures import DEV_SEED_PASSWORD
from app.modules.auth.passwords import hash_password_async

pytestmark = pytest.mark.database

ORIGIN = {"Origin": "http://localhost:5173"}
DEV_LOGIN_URL = "/api/v1/auth/dev-login"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


@pytest.fixture
async def dev_client(
    settings: Settings, email_outbox, clean_database
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        settings.model_copy(update={"dev_login_enabled": True}), email_client=email_outbox
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client


async def dev_login(client, persona: str = "hr", headers: dict[str, str] | None = ORIGIN):
    return await client.post(DEV_LOGIN_URL, json={"persona": persona}, headers=headers or {})


async def test_route_is_hidden_when_not_enabled(app_client) -> None:
    response = await dev_login(app_client)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_creates_the_persona_and_opens_a_real_session(dev_client, session_factory) -> None:
    response = await dev_login(dev_client, "hr")
    assert response.status_code == 200
    body = response.json()
    assert body["account"]["email"] == "dev.hr@sis.hust.edu.vn"
    assert body["account"]["roles"] == ["HR"]
    assert body["token_type"] == "bearer"
    assert any(
        header.startswith("refresh_token=") for header in response.headers.get_list("set-cookie")
    )

    me = await dev_client.get(ME_URL, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "dev.hr@sis.hust.edu.vn"

    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT status, password_hash FROM accounts WHERE email = :email"),
                {"email": "dev.hr@sis.hust.edu.vn"},
            )
        ).one()
    assert row.status == "ACTIVE"
    assert row.password_hash is not None
    # The generated password is unknown, so the bypass is not a known shared secret.
    from app.modules.auth.passwords import verify_password

    assert not verify_password(DEV_SEED_PASSWORD, row.password_hash)


async def test_bypass_keeps_working_after_a_password_change(dev_client, session_factory) -> None:
    assert (await dev_login(dev_client, "hr")).status_code == 200

    async with session_factory() as session:
        await session.execute(
            text("UPDATE accounts SET password_hash = :hash WHERE email = :email"),
            {
                "hash": await hash_password_async("changed-password-123"),
                "email": "dev.hr@sis.hust.edu.vn",
            },
        )
        await session.commit()

    changed = await dev_client.post(
        LOGIN_URL,
        json={"email": "dev.hr@sis.hust.edu.vn", "password": "changed-password-123"},
        headers=ORIGIN,
    )
    assert changed.status_code == 200
    assert (await dev_login(dev_client, "hr")).status_code == 200


async def test_reports_inactive_persona_without_creating_a_session(
    dev_client, session_factory
) -> None:
    assert (await dev_login(dev_client, "trainee")).status_code == 200

    async with session_factory() as session:
        await session.execute(
            text("UPDATE accounts SET status = 'LOCKED' WHERE email = :email"),
            {"email": "dev.trainee@sis.hust.edu.vn"},
        )
        await session.execute(text("DELETE FROM auth_sessions"))
        await session.commit()

    response = await dev_login(dev_client, "trainee")
    assert response.status_code == 409
    assert "LOCKED" in response.json()["error"]["message"]

    async with session_factory() as session:
        sessions = await session.scalar(text("SELECT count(*) FROM auth_sessions"))
    assert sessions == 0


async def test_unknown_persona_is_not_found(dev_client) -> None:
    assert (await dev_login(dev_client, "root")).status_code == 404


async def test_requires_a_trusted_origin(dev_client) -> None:
    response = await dev_login(dev_client, "hr", headers={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "untrusted_origin"


async def test_records_a_distinct_audit_event(dev_client, session_factory) -> None:
    await dev_login(dev_client, "manager")

    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT actor_id, action, outcome, metadata FROM audit_events "
                    "WHERE action = 'auth.dev_login'"
                )
            )
        ).one()
        actor_email = await session.scalar(
            text("SELECT email FROM accounts WHERE id = :id"), {"id": row.actor_id}
        )

    assert row.outcome == "SUCCESS"
    assert row.metadata == {"persona": "manager"}
    assert actor_email == "dev.manager@sis.hust.edu.vn"
