"""Build production adapters from Settings without contacting any external service.

A feature whose configuration is missing gets ``None`` and answers 503 when used; the
API and worker still start, so ``/health`` and OpenAPI stay available.
"""

from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.antivirus.client import ClamAVScanner
from app.integrations.captcha.client import TurnstileVerifier
from app.integrations.google_workspace.client import FakeGoogleWorkspace, IGoogleWorkspace
from app.integrations.llm.scoring import FakeAIAgent, IAIAgent
from app.integrations.storage.encrypted_local import EncryptedLocalStorage


def build_cv_storage(settings: Settings) -> EncryptedLocalStorage | None:
    # Chỉ nhận đường dẫn tuyệt đối: tránh vô tình ghi CV vào thư mục làm việc/public.
    if settings.cv_storage_dir is None or not Path(settings.cv_storage_dir).is_absolute():
        return None
    try:
        key = settings.require_cv_encryption_key()
    except AppError:
        return None
    return EncryptedLocalStorage(Path(settings.cv_storage_dir), key)


def build_captcha(settings: Settings) -> TurnstileVerifier | None:
    # Không có secret thì không có CAPTCHA: endpoint trả 503, không bao giờ bỏ qua kiểm tra.
    if settings.turnstile_secret_key is None:
        return None
    secret = settings.turnstile_secret_key.get_secret_value()
    if not secret:
        return None
    return TurnstileVerifier(
        secret,
        expected_hostname=settings.turnstile_expected_hostname,
        expected_action=settings.turnstile_expected_action,
        timeout=settings.captcha_timeout_seconds,
    )


def build_scanner(settings: Settings) -> ClamAVScanner:
    # Chỉ tạo đối tượng; không kết nối ClamAV lúc khởi động.
    return ClamAVScanner(
        settings.clamav_host, settings.clamav_port, timeout=settings.clamav_timeout_seconds
    )


def build_scoring_agent() -> IAIAgent:
    return FakeAIAgent()


def build_google_workspace() -> IGoogleWorkspace:
    return FakeGoogleWorkspace()
