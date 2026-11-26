from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    PositiveInt,
    PostgresDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.email_address import normalize_mailbox
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
    public_base_url: str = "http://localhost:5173"
    interview_duration_minutes: PositiveInt = 60
    talent_pool_policy_version: str = Field(default="talent-pool-v1", min_length=1, max_length=20)
    fake_google_db_path: Path = BACKEND_DIR / ".local" / "fake-google.sqlite3"
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

    # Email. EMAIL_PROVIDER=fake chỉ mô phỏng (không gửi ra ngoài); smtp gửi thật qua
    # SMTP_HOST (Mailpit khi phát triển). Bỏ trống thì suy ra: có SMTP_HOST -> smtp,
    # không có -> fake, để cấu hình Mailpit/auth cũ vẫn hoạt động như trước.
    email_provider: Literal["fake", "smtp"] | None = None
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = False  # STARTTLS (ví dụ 587)
    smtp_use_ssl: bool = False  # TLS ngay từ đầu (ví dụ 465)
    mail_from_address: str = "no-reply@sis.hust.edu.vn"
    mail_from_name: str = "HR Chan"
    # NFR04: mỗi lượt gửi tối đa 10 giây cho toàn bộ thao tác mạng.
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=10)

    # Tên biến cũ, vẫn nhận để không làm hỏng backend/.env đang có. Khác giá trị với
    # tên mới là lỗi cấu hình; chỉ đọc qua các trường mới ở trên.
    smtp_starttls: bool | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None

    # Khóa mã hóa payload bí mật của thư xếp hàng (AES-GCM). Không có mặc định; chỉ bắt
    # buộc khi thật sự xếp hàng/gửi thư có biến bí mật, không ảnh hưởng /health.
    outbox_encryption_key: SecretStr | None = None
    # Worker outbox: chu kỳ quét (giây) và số thư tối đa mỗi lượt.
    email_outbox_interval_seconds: PositiveInt = 30
    email_outbox_batch_size: PositiveInt = 20

    # Ứng tuyển. Mọi khóa/bí mật không có mặc định; thiếu thì chức năng trả 503 khi dùng,
    # /health và OpenAPI vẫn hoạt động. Kho CV phải là thư mục riêng, ngoài public/static.
    cv_storage_dir: Path | None = None
    cv_encryption_key: SecretStr | None = None
    submission_token_secret: SecretStr | None = None
    otp_secret: SecretStr | None = None
    consent_policy_version: str = Field(default="2026-11", min_length=1, max_length=20)
    # Cloudflare Turnstile: secret chỉ ở backend; hostname/action được kiểm khi cấu hình.
    turnstile_secret_key: SecretStr | None = None
    turnstile_expected_hostname: str | None = None
    turnstile_expected_action: str | None = None
    captcha_timeout_seconds: float = Field(default=10.0, gt=0, le=10)
    # ClamAV clamd (INSTREAM) trên loopback; lỗi/timeout thì từ chối CV.
    clamav_host: str = "127.0.0.1"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    clamav_timeout_seconds: float = Field(default=10.0, gt=0, le=10)
    # Tác vụ dọn CV tạm/OTP cũ trong worker (giây).
    application_cleanup_interval_seconds: PositiveInt = 3600
    cv_scoring_interval_seconds: PositiveInt = 30
    cv_scoring_timeout_seconds: float = Field(default=10, gt=0)

    # Forwarded client IP headers are ignored unless a deployment opts in.
    trust_forwarded_for: bool = False

    # Allows `seed-dev-accounts` to create development fixtures. Never enable it
    # for a database that holds real accounts.
    dev_seed_enabled: bool = False

    # Enables `POST /auth/dev-login`, a development-only bypass for the fixed
    # `dev.*` personas. Never enable it outside local development.
    dev_login_enabled: bool = False

    # Số giây giữa các lần worker đóng tin OPEN đã quá hạn nộp; phải lớn hơn 0.
    # Lịch xóa CLOSED sau hai năm là cron riêng, không phụ thuộc khoảng quét này.
    job_expiry_interval_seconds: PositiveInt = 60

    @field_validator(
        "cv_storage_dir",
        "turnstile_expected_hostname",
        "turnstile_expected_action",
        mode="before",
    )
    @classmethod
    def _blank_means_unset(cls, value):
        # Biến để trống trong .env là "chưa cấu hình", không phải thư mục hiện tại ("").
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _check_email_settings(self) -> "Settings":
        explicit = self.model_fields_set
        for legacy, new in (
            ("smtp_starttls", "smtp_use_tls"),
            ("smtp_from_email", "mail_from_address"),
            ("smtp_from_name", "mail_from_name"),
        ):
            legacy_value = getattr(self, legacy)
            if legacy_value is None:
                continue
            if new in explicit and getattr(self, new) != legacy_value:
                raise ValueError(f"{legacy.upper()} conflicts with {new.upper()}; keep one value")
            object.__setattr__(self, new, legacy_value)

        # Biến để trống trong .env nghĩa là "không cấu hình" (không AUTH với Mailpit).
        if self.smtp_host is not None and not self.smtp_host.strip():
            object.__setattr__(self, "smtp_host", None)
        if self.smtp_username is not None and not self.smtp_username.strip():
            object.__setattr__(self, "smtp_username", None)
        if self.smtp_password is not None and not self.smtp_password.get_secret_value():
            object.__setattr__(self, "smtp_password", None)
        if self.email_provider is None:
            object.__setattr__(
                self, "email_provider", "smtp" if self.smtp_host is not None else "fake"
            )
        if self.email_provider == "smtp" and self.smtp_host is None:
            raise ValueError("EMAIL_PROVIDER=smtp requires SMTP_HOST")
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be enabled")
        try:
            object.__setattr__(self, "mail_from_address", normalize_mailbox(self.mail_from_address))
        except ValueError:
            raise ValueError("MAIL_FROM_ADDRESS must be exactly one email address") from None
        if "\r" in self.mail_from_name or "\n" in self.mail_from_name:
            raise ValueError("MAIL_FROM_NAME must not contain line breaks")
        return self

    def require_outbox_key(self) -> bytes:
        """Secret for encrypted queued payloads; fails closed when not configured."""
        raw = (
            self.outbox_encryption_key.get_secret_value()
            if self.outbox_encryption_key is not None
            else ""
        )
        if len(raw) < MIN_SECRET_CHARS:
            raise AppError(
                "Email outbox is not configured: add OUTBOX_ENCRYPTION_KEY (at least "
                f"{MIN_SECRET_CHARS} characters) to backend/.env and restart",
                status_code=503,
                code="email_unavailable",
            )
        return raw.encode()

    def _require_feature_secret(self, value: SecretStr | None, name: str) -> bytes:
        raw = value.get_secret_value() if value is not None else ""
        if len(raw) < MIN_SECRET_CHARS:
            raise AppError(
                "Chức năng nộp hồ sơ tạm thời chưa sẵn sàng. Vui lòng thử lại sau.",
                status_code=503,
                code="application_unavailable",
            )
        return raw.encode()

    def require_cv_encryption_key(self) -> bytes:
        return self._require_feature_secret(self.cv_encryption_key, "CV_ENCRYPTION_KEY")

    def require_submission_token_secret(self) -> bytes:
        return self._require_feature_secret(self.submission_token_secret, "SUBMISSION_TOKEN_SECRET")

    def require_otp_secret(self) -> bytes:
        return self._require_feature_secret(self.otp_secret, "OTP_SECRET")

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
