import pytest

from app.core.config import Settings
from app.core.exceptions import AppError


def test_auth_secrets_have_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("LIMITER_SECRET", raising=False)
    settings = Settings(_env_file=None)
    assert settings.jwt_secret is None
    assert settings.limiter_secret is None


def test_auth_fails_closed_when_secrets_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("LIMITER_SECRET", raising=False)
    settings = Settings(_env_file=None)
    for accessor, name in (
        (settings.require_jwt_secret, "JWT_SECRET"),
        (settings.require_limiter_secret, "LIMITER_SECRET"),
    ):
        with pytest.raises(AppError) as error:
            accessor()
        assert error.value.status_code == 503
        assert error.value.code == "authentication_unavailable"
        assert name in error.value.message
        assert "backend/.env" in error.value.message


def test_reads_the_env_file_next_to_the_backend_directory() -> None:
    from app.core.config import BACKEND_DIR, ENV_FILE

    assert ENV_FILE == BACKEND_DIR / ".env"
    assert ENV_FILE.parent.name == "backend"


@pytest.mark.parametrize("secret", ["", "short", "a" * 31])
def test_rejects_short_secrets(secret: str) -> None:
    settings = Settings(_env_file=None, jwt_secret=secret, limiter_secret=secret)
    with pytest.raises(AppError):
        settings.require_jwt_secret()
    with pytest.raises(AppError):
        settings.require_limiter_secret()


def test_accepts_configured_secret_of_sufficient_length() -> None:
    settings = Settings(_env_file=None, jwt_secret="j" * 32, limiter_secret="l" * 32)
    assert settings.require_jwt_secret() == b"j" * 32
    assert settings.require_limiter_secret() == b"l" * 32


def test_trusted_origins_fall_back_to_cors_origins() -> None:
    settings = Settings(_env_file=None, cors_origins=["http://localhost:5173"])
    assert settings.browser_origins() == ["http://localhost:5173"]
    overridden = Settings(
        _env_file=None,
        cors_origins=["http://localhost:5173"],
        trusted_origins=["https://hr.example.test"],
    )
    assert overridden.browser_origins() == ["https://hr.example.test"]


def test_forwarded_client_headers_are_untrusted_by_default() -> None:
    assert Settings(_env_file=None).trust_forwarded_for is False
