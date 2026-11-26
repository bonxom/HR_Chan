import pytest
from apply_support import apply_cleanup
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from test_talent_pool_responses import issue

from app.main import create_app

__all__ = ["apply_cleanup"]


@pytest.mark.parametrize(
    "body",
    [
        {"token": "secret-do-not-echo", "action": "UNKNOWN"},
        {"token": "secret-do-not-echo", "extra": True},
        {"token": "secret-do-not-echo", "secret-do-not-echo": True},
        {"token": "secret-do-not-echo", "note": "x" * 501, "action": "ACCEPTED"},
    ],
)
async def test_public_validation_never_echoes_token(settings, body):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            response = await client.post("/api/v1/responses/submit", json=body)
    assert response.status_code == 422
    assert "secret-do-not-echo" not in response.text
    assert response.headers["cache-control"] == "private, no-store"


async def test_anonymous_resolve_is_read_only_and_submit_returns_minimal_receipt(
    apply_cleanup, session_factory, settings
):
    _, token = await issue(session_factory)
    async with session_factory() as session:
        before = (
            await session.execute(
                text(
                    "SELECT (SELECT count(*) FROM audit_events),"
                    " (SELECT count(*) FROM talent_pool_consents),"
                    " (SELECT count(*) FROM response_links WHERE used_at IS NOT NULL)"
                )
            )
        ).one()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            response = await client.post("/api/v1/responses/resolve", json={"token": token})
            assert response.status_code == 200
            view = response.json()
            assert view["completed"] is False
            assert token not in response.text
            assert response.headers["referrer-policy"] == "no-referrer"
            async with session_factory() as session:
                after = (
                    await session.execute(
                        text(
                            "SELECT (SELECT count(*) FROM audit_events),"
                            " (SELECT count(*) FROM talent_pool_consents),"
                            " (SELECT count(*) FROM response_links WHERE used_at IS NOT NULL)"
                        )
                    )
                ).one()
            assert after == before
            payload = dict(
                token=token,
                action="ACCEPTED",
                policy_ver=view["policy_ver"],
                consent_snapshot=view["consent_snapshot"],
            )
            result = await client.post("/api/v1/responses/submit", json=payload)
            assert result.status_code == 200
            receipt = await client.post("/api/v1/responses/resolve", json={"token": token})
            assert receipt.status_code == 200
            assert set(receipt.json()) == {"completed", "outcome", "completed_at"}
            assert receipt.json()["outcome"] == "ACCEPTED"
            replay = await client.post("/api/v1/responses/submit", json=payload)
            assert replay.status_code == 422
            assert replay.json()["error"]["code"] == "invalid_response_link"
