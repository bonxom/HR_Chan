import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


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
        assert set(client.get("/openapi.json").json()["paths"]) == {"/health"}
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = client.get("/health", headers={"Origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in response.headers
