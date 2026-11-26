import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

EXPECTED_PATHS = {
    "/api/v1/responses/resolve",
    "/api/v1/responses/submit",
    "/api/applications",
    "/api/applications/{application_id}",
    "/api/applications/{application_id}/cv",
    "/api/applications/{application_id}/interview-slots",
    "/api/applications/{application_id}/invite",
    "/api/applications/{application_id}/reject",
    "/api/v1/applications/{application_id}",
    "/api/v1/applications/{application_id}/cv",
    "/api/v1/applications/{application_id}/interview-slots",
    "/api/v1/applications/{application_id}/invite",
    "/api/v1/applications/{application_id}/reject",
    "/health",
    "/api/v1/candidates/submissions",
    "/api/v1/applications/otp",
    "/api/v1/applications",
    "/api/v1/public/jobs",
    "/api/v1/public/jobs/{job_id}",
    "/api/v1/auth/login",
    "/api/v1/auth/dev-login",
    "/api/v1/auth/csrf",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/auth/password/recovery",
    "/api/v1/auth/refresh",
    "/api/v1/auth/activity",
    "/api/v1/auth/password/change",
    "/api/v1/auth/password/complete",
    "/api/v1/accounts",
    "/api/v1/accounts/{account_id}/roles",
    "/api/v1/accounts/{account_id}/lock",
    "/api/v1/accounts/{account_id}/unlock",
    "/api/v1/accounts/{account_id}/disable",
    "/api/v1/accounts/{account_id}/invitation",
    "/api/v1/audit-events",
    "/api/v1/jobs",
    "/api/v1/jobs/{job_id}",
    "/api/v1/jobs/{job_id}/publish",
    "/api/v1/jobs/{job_id}/close",
    "/api/v1/jobs/{job_id}/criteria",
    "/api/v1/jobs/{job_id}/criteria/versions",
    "/api/v1/interviewers",
    "/api/v1/departments",
}


@pytest.fixture
def app():
    # Unreachable database deliberately proves liveness does not connect.
    return create_app(
        Settings(
            _env_file=None, database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused"
        )
    )


def test_health_docs_and_cors(app):
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert set(client.get("/openapi.json").json()["paths"]) == EXPECTED_PATHS
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = client.get("/health", headers={"Origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in response.headers


def test_credentialed_cors_allows_csrf_header(app):
    with TestClient(app) as client:
        preflight = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert "x-csrf-token" in preflight.headers["access-control-allow-headers"].lower()


def test_wildcard_cors_origin_is_rejected_with_credentials() -> None:
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, cors_origins=["*"]))
