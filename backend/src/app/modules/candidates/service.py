"""Accept a real CV upload (plan task 6).

Order: per-IP limit (committed at once) -> fields and consent -> server-side CAPTCHA ->
size/type/text checks (in a thread) -> ClamAV scan -> encrypted store -> database.
Every rejection leaves no file and no row; if the database step fails after the file
was stored, the file is removed again. Unverified contact data is kept only inside the
encrypted object; an existing candidate is never changed before OTP verification.
"""

import asyncio
import hashlib
import ipaddress
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.adapters import field_error, field_errors
from app.core.config import Settings
from app.core.email_address import normalize_mailbox
from app.core.exceptions import AppError
from app.integrations.antivirus.client import ScannerUnavailableError, ScanVerdict
from app.integrations.captcha.client import CaptchaUnavailableError
from app.integrations.storage.client import StorageError
from app.modules.auth.rate_limits import LimitRule, consume
from app.modules.auth.tokens import limiter_identifier
from app.modules.candidates import capability, repository
from app.modules.candidates.documents import MAX_CV_BYTES, CvRejected, inspect_cv
from app.modules.candidates.envelope import PendingContact, pack
from app.modules.candidates.models import CvSubmission, ParseStatus, ScanStatus

logger = logging.getLogger(__name__)

SUBMISSION_TTL = timedelta(hours=24)
UPLOAD_LIMIT = LimitRule(max_attempts=10, window_seconds=3600)
FULL_NAME_MAX = 100
PHONE_PATTERN = re.compile(r"[0-9]{10}")
CONSENT_VALUES = frozenset({"true", "1", "on", "yes"})


@dataclass(frozen=True)
class SubmissionForm:
    full_name: str | None
    email: str | None
    phone: str | None
    consent: str | None
    captcha_token: str | None
    filename: str | None
    data: bytes | None


@dataclass(frozen=True)
class CreatedSubmission:
    submission_id: int
    submission_token: str
    expires_at: datetime


def _rate_limited(retry_after: int | None) -> AppError:
    return AppError(
        "Bạn đã gửi quá nhiều hồ sơ trong một giờ. Vui lòng thử lại sau.",
        status_code=429,
        code="rate_limited",
        headers={"Retry-After": str(retry_after or 60)},
    )


def _unavailable(code: str, message: str) -> AppError:
    return AppError(message, status_code=503, code=code)


def _validate(form: SubmissionForm) -> tuple[PendingContact, str, bytes]:
    errors: dict[str, str] = {}
    full_name = " ".join((form.full_name or "").split())
    if not full_name:
        errors["full_name"] = "Vui lòng nhập họ tên."
    elif len(full_name) > FULL_NAME_MAX or any(
        unicodedata.category(char) == "Cc" for char in full_name
    ):
        errors["full_name"] = "Họ tên tối đa 100 ký tự và không chứa ký tự điều khiển."
    email = ""
    try:
        email = normalize_mailbox(form.email).lower()
    except ValueError:
        errors["email"] = "Email không hợp lệ."
    phone = (form.phone or "").strip()
    if not PHONE_PATTERN.fullmatch(phone):
        errors["phone"] = "Số điện thoại phải gồm đúng 10 chữ số."
    if (form.consent or "").strip().lower() not in CONSENT_VALUES:
        errors["consent"] = "Bạn cần đồng ý cho phép xử lý dữ liệu cá nhân để nộp hồ sơ."
    if not (form.captcha_token or "").strip():
        errors["captcha_token"] = "Vui lòng hoàn thành CAPTCHA."
    if form.data is None or not form.filename:
        errors["file"] = "Vui lòng chọn tệp CV (PDF hoặc DOCX)."
    if errors:
        raise field_errors(errors)
    return PendingContact(full_name, email, phone), form.captcha_token.strip(), form.data


def _original_name(filename: str) -> str:
    name = re.split(r"[\\/]", filename)[-1]
    name = "".join(char for char in name if unicodedata.category(char)[0] != "C").strip()
    return (name or "cv")[:255]


def _inet(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


class SubmissionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def _consume_upload_quota(self, ip: str, now: datetime) -> None:
        key = limiter_identifier(self.settings.require_limiter_secret(), "cv-upload-ip", ip)
        decision = await consume(self.session, key, UPLOAD_LIMIT, now)
        # Bộ đếm được commit ngay, kể cả khi yêu cầu bị từ chối ở bước sau.
        await self.session.commit()
        if decision.blocked:
            raise _rate_limited(decision.retry_after)

    async def create(
        self, form: SubmissionForm, *, storage, scanner, captcha, client_ip: str
    ) -> CreatedSubmission:
        secret = self.settings.require_submission_token_secret()
        now = clock.utcnow()
        await self._consume_upload_quota(client_ip, now)

        contact, captcha_token, data = _validate(form)

        try:
            human = await captcha.verify(captcha_token, client_ip)
        except CaptchaUnavailableError:
            raise _unavailable(
                "captcha_unavailable", "Không kiểm tra được CAPTCHA lúc này. Vui lòng thử lại."
            ) from None
        if not human:
            raise field_error(
                "captcha_token", "Xác minh CAPTCHA không thành công. Vui lòng thử lại."
            )

        if len(data) > MAX_CV_BYTES:
            raise AppError(
                "Tệp CV vượt quá dung lượng tối đa 5 MB.", status_code=413, code="cv_too_large"
            )
        try:
            # Phân tích tệp chạy trong thread để không chặn event loop.
            inspected = await asyncio.to_thread(inspect_cv, data, form.filename or "")
        except CvRejected as rejection:
            if rejection.status_code == 413:
                raise AppError(rejection.message, status_code=413, code="cv_too_large") from None
            if rejection.status_code == 415:
                raise AppError(
                    rejection.message, status_code=415, code="cv_unsupported_type"
                ) from None
            raise field_error("file", rejection.message) from None

        try:
            verdict = await scanner.scan(data)
        except ScannerUnavailableError:
            raise _unavailable(
                "scanner_unavailable", "Không kiểm tra được an toàn tệp lúc này. Vui lòng thử lại."
            ) from None
        if verdict is not ScanVerdict.CLEAN:
            raise field_error(
                "file", "Tệp CV không an toàn (phát hiện mã độc) nên không được nhận."
            )

        digest = hashlib.sha256(data).hexdigest()
        try:
            storage_key = await storage.put(pack(data, contact))
        except (StorageError, OSError):
            logger.error("CV store write failed")
            raise _unavailable(
                "application_unavailable", "Không lưu được CV lúc này. Vui lòng thử lại sau."
            ) from None

        expires_at = now + SUBMISSION_TTL
        try:
            candidate_id = await repository.get_or_create_candidate(
                self.session,
                email=contact.email,
                full_name=contact.full_name,
                phone=contact.phone,
                now=now,
            )
            submission_id = await repository.add_submission(
                self.session,
                CvSubmission(
                    candidate_id=candidate_id,
                    cv_storage_key=storage_key,
                    cv_original_name=_original_name(form.filename or ""),
                    cv_mime_type=inspected.mime_type,
                    cv_size_bytes=len(data),
                    cv_sha256=digest,
                    cv_scan_status=ScanStatus.CLEAN,
                    consent_at=now,
                    consent_policy_ver=self.settings.consent_policy_version,
                    parse_status=ParseStatus.PENDING,
                    ip=_inet(client_ip),
                    created_at=now,
                    expires_at=expires_at,
                ),
            )
            await self.session.commit()
        except Exception as exc:
            # Bù trừ: DB không lưu được thì xóa file vừa ghi. Chỉ log loại lỗi (không SQL,
            # không tham số chứa dữ liệu cá nhân).
            await self.session.rollback()
            await _delete_quietly(storage, storage_key)
            logger.error("CV submission could not be saved (%s)", type(exc).__name__)
            raise AppError(
                "Không lưu được hồ sơ lúc này. Vui lòng thử lại sau.",
                status_code=500,
                code="internal_error",
            ) from None

        token = capability.issue(
            secret, submission_id=submission_id, storage_key=storage_key, expires_at=expires_at
        )
        return CreatedSubmission(submission_id, token, expires_at)


async def _delete_quietly(storage, key: str) -> None:
    try:
        await storage.delete(key)
    except Exception as exc:  # file mồ côi sẽ được tác vụ dọn định kỳ xử lý
        logger.warning("Could not remove an unsaved CV file (%s)", type(exc).__name__)
