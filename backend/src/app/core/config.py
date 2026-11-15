from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import AppError

MIN_SECRET_CHARS = 32

# Read `backend/.env` regardless of the shell's working directory.
BACKEND_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HR Chan API"
    database_url: PostgresDsn = "postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    # Browser origins allowed to perform credential-changing authentication requests.
    trusted_origins: list[str] | None = None
    frontend_url: str = "http://localhost:5173"
    allowed_email_domains: list[str] = ["sis.hust.edu.vn"]

    # Fixed HS256 signing; the secret is backend-only and has no usable default.
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "hr-chan-api"
    jwt_audience: str = "hr-chan-web"
    access_token_ttl_seconds: int = 300

    # HMAC key used to store unguessable limiter identifiers.
    limiter_secret: SecretStr | None = None

    session_idle_seconds: int = 1800
    session_absolute_seconds: int = 43200
    activity_min_interval_seconds: int = 60

    invitation_ttl_seconds: int = 86400
    recovery_ttl_seconds: int = 1800

    login_failure_limit: int = 5
    login_failure_window_seconds: int = 900
    login_block_seconds: int = 900
    login_ip_limit: int = 50
    login_ip_window_seconds: int = 900
    recovery_ip_limit: int = 20
    recovery_ip_window_seconds: int = 3600
    recovery_ip_block_seconds: int = 60
    email_min_interval_seconds: int = 60
    email_hourly_limit: int = 5

    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_starttls: bool = False
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str = "no-reply@sis.hust.edu.vn"
    smtp_from_name: str = "HR Chan"
    smtp_timeout_seconds: float = 10.0

    # Forwarded client IP headers are ignored unless a deployment opts in.
    trust_forwarded_for: bool = False

    # Allows `seed-dev-accounts` to create development fixtures. Never enable it
    # for a database that holds real accounts.
    dev_seed_enabled: bool = False

    # Enables `POST /auth/dev-login`, a development-only bypass for the fixed
    # `dev.*` personas. Never enable it outside local development.
    dev_login_enabled: bool = False

    def browser_origins(self) -> list[str]:
        return list(self.trusted_origins if self.trusted_origins is not None else self.cors_origins)

    def _require_secret(self, value: SecretStr | None, name: str) -> bytes:
        raw = value.get_secret_value() if value is not None else ""
        if len(raw) < MIN_SECRET_CHARS:
            raise AppError(
                f"Authentication is not configured: add {name} (at least "
                f"{MIN_SECRET_CHARS} characters) to backend/.env and restart the API",
                status_code=503,
                code="authentication_unavailable",
            )
        return raw.encode()

    def require_jwt_secret(self) -> bytes:
        return self._require_secret(self.jwt_secret, "JWT_SECRET")

    def require_limiter_secret(self) -> bytes:
        return self._require_secret(self.limiter_secret, "LIMITER_SECRET")


@lru_cache
def get_settings() -> Settings:
    return Settings()
