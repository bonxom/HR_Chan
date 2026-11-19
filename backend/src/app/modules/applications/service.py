"""Apply with a real OTP (plan task 7).

``request_otp`` checks the capability, the posting and duplicates, then - serialized per
email with an advisory lock - enforces the wrong-code lock, the 60 s cooldown and the
hourly resend limit, invalidates the previous code, stores the new code's HMAC and
commits *before* sending it with ``NotificationService.sendNow`` (an email cannot be
rolled back). A failed send invalidates exactly that code.

``submit`` locks in one fixed order - posting (FOR SHARE), submission, candidate, live
code - re-checks everything under those locks, then in one transaction updates the
verified contact, creates the application (SCORING / ai PENDING / no score), consumes the
code; the status history is written by the database trigger. Wrong codes are counted
and committed before the error is returned; the 5th one locks the email for 15 minutes.
No confirmation email is sent.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.core.adapters import field_error
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.otp import crypto
from app.core.otp import repository as otp_repository
from app.core.otp.models import OtpCode, OtpPurpose
from app.modules.applications import repository
from app.modules.applications.models import AiScoreStatus, Application, ApplicationStatus
from app.modules.auth.rate_limits import LimitRule, check, consume
from app.modules.auth.tokens import limiter_identifier
from app.modules.candidates import capability
from app.modules.candidates import repository as candidate_repository
from app.modules.candidates.envelope import PendingContact, unpack
from app.modules.candidates.models import CvSubmission, ScanStatus
from app.modules.notifications.models import EmailStatus
from app.modules.notifications.schemas import TemplateCode
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.models import JobPosting, JobStatus
from app.modules.recruitment.retention import COMPANY_TZ

logger = logging.getLogger(__name__)

OTP_TTL = timedelta(minutes=5)
RESEND_COOLDOWN = timedelta(seconds=60)
RESEND_WINDOW = timedelta(hours=1)
MAX_CODES_PER_WINDOW = 4  # mã đầu tiên + tối đa 3 lần gửi lại mỗi giờ
MAX_WRONG_ATTEMPTS = 5
LOCK_RULE = LimitRule(max_attempts=1, window_seconds=15 * 60)

THANK_YOU = "Cảm ơn bạn đã ứng tuyển. Hồ sơ đã được tiếp nhận và đang chờ xử lý."
WRONG_CODE = "Mã xác thực không đúng hoặc đã hết hạn."


@dataclass(frozen=True)
class OtpIssued:
    expires_at: datetime
    resend_available_at: datetime


@dataclass(frozen=True)
class ApplicationCreated:
    application_id: int
    submitted_at: datetime


def _retry_seconds(until: datetime, now: datetime) -> int:
    return max(1, math.ceil((until - now).total_seconds()))


def _invalid_submission() -> AppError:
    return AppError(
        "Phiên nộp hồ sơ không hợp lệ hoặc đã hết hạn. Vui lòng tải CV lên lại.",
        status_code=403,
        code="invalid_submission",
    )


def _job_not_found() -> AppError:
    return AppError("Không tìm thấy tin tuyển dụng.", status_code=404, code="job_not_found")


def _job_not_accepting() -> AppError:
    return AppError(
        "Tin tuyển dụng đã đóng hoặc hết hạn nhận hồ sơ.", status_code=409, code="job_not_accepting"
    )


def _already_applied() -> AppError:
    return AppError(
        "Email này đã nộp hồ sơ cho vị trí này.", status_code=409, code="already_applied"
    )


def _locked(retry_after: int) -> AppError:
    return AppError(
        "Bạn đã nhập sai mã quá 5 lần. Vui lòng thử lại sau 15 phút.",
        status_code=429,
        code="otp_locked",
        headers={"Retry-After": str(retry_after)},
    )


def _rate_limited(retry_after: int) -> AppError:
    return AppError(
        "Bạn vừa yêu cầu mã. Vui lòng chờ trước khi gửi lại.",
        status_code=429,
        code="rate_limited",
        headers={"Retry-After": str(retry_after)},
    )


def _email_unavailable() -> AppError:
    return AppError(
        "Không gửi được email mã xác thực lúc này. Vui lòng thử lại sau.",
        status_code=503,
        code="email_unavailable",
    )


def accepting(job: JobPosting, now: datetime) -> bool:
    today = now.astimezone(COMPANY_TZ).date()
    return job.status is JobStatus.OPEN and job.deadline is not None and job.deadline >= today


class ApplicationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    # ---- shared checks -------------------------------------------------------------

    async def _verified_submission(
        self, submission_id: int, token: str, secret: bytes, now: datetime
    ) -> CvSubmission:
        submission = await candidate_repository.get_submission(self.session, submission_id)
        if (
            submission is None
            or submission.cv_scan_status is not ScanStatus.CLEAN
            or not capability.verify(
                secret,
                token,
                submission_id=submission.id,
                storage_key=submission.cv_storage_key,
                expires_at=submission.expires_at,
                now=now,
            )
        ):
            await self.session.rollback()
            raise _invalid_submission()
        return submission

    async def _pending_contact(self, storage, submission: CvSubmission) -> PendingContact:
        try:
            _cv, contact = unpack(await storage.get(submission.cv_storage_key))
        except Exception as exc:  # StorageError, EnvelopeFormatError, OSError...
            logger.error("Stored submission could not be read (%s)", type(exc).__name__)
            raise AppError(
                "Không đọc được hồ sơ tạm. Vui lòng tải CV lên lại.",
                status_code=503,
                code="application_unavailable",
            ) from None
        return contact

    def _lock_key(self, email: str) -> str:
        return limiter_identifier(self.settings.require_limiter_secret(), "apply-otp-lock", email)

    async def _raise_if_locked(self, email: str, now: datetime) -> None:
        decision = await check(self.session, self._lock_key(email), LOCK_RULE, now)
        if decision.blocked:
            await self.session.rollback()
            raise _locked(decision.retry_after or LOCK_RULE.window_seconds)

    # ---- OTP -----------------------------------------------------------------------

    async def request_otp(
        self,
        *,
        submission_id: int,
        submission_token: str,
        job_id: int,
        storage,
        email_service,
        session_factory: async_sessionmaker[AsyncSession],
        client_ip: str | None,
    ) -> OtpIssued:
        # Chế độ mô phỏng không gửi thư thật: không được báo đã gửi mã cho ứng viên.
        if getattr(email_service, "simulated", False):
            raise _email_unavailable()
        otp_secret = self.settings.require_otp_secret()
        token_secret = self.settings.require_submission_token_secret()
        now = clock.utcnow()
        submission = await self._verified_submission(
            submission_id, submission_token, token_secret, now
        )
        contact = await self._pending_contact(storage, submission)
        await self.session.rollback()  # kết thúc giao dịch đọc trước khi bắt đầu khóa

        # Cùng thứ tự khóa với submit: tin -> submission -> ứng viên -> (email) -> mã OTP.
        # FK của mã mới cần key-share trên submission nên phải khóa submission trước mã cũ.
        job = await repository.lock_job_for_share(self.session, job_id)
        if job is None:
            await self.session.rollback()
            raise _job_not_found()
        if not accepting(job, now):
            await self.session.rollback()
            raise _job_not_accepting()
        locked = await candidate_repository.lock_submission(self.session, submission_id)
        if locked is None or locked.expires_at <= now:
            await self.session.rollback()
            raise _invalid_submission()
        submission = locked
        candidate = await candidate_repository.lock_candidate(self.session, locked.candidate_id)
        if await repository.application_exists(self.session, candidate.id, job.id):
            await self.session.rollback()
            raise _already_applied()
        email = candidate.email

        # Tuần tự hóa theo email: cooldown, giới hạn gửi lại và "một mã còn hiệu lực" được
        # kiểm tra và ghi trong cùng một giao dịch giữ khóa.
        await otp_repository.serialize_email(self.session, email, OtpPurpose.APPLY)
        await self._raise_if_locked(email, now)
        last = await otp_repository.last_issued(self.session, email, OtpPurpose.APPLY)
        if last is not None and now - last < RESEND_COOLDOWN:
            await self.session.rollback()
            raise _rate_limited(_retry_seconds(last + RESEND_COOLDOWN, now))
        recent = await otp_repository.issued_since(
            self.session, email, OtpPurpose.APPLY, now - RESEND_WINDOW
        )
        if len(recent) >= MAX_CODES_PER_WINDOW:
            await self.session.rollback()
            raise _rate_limited(_retry_seconds(recent[0] + RESEND_WINDOW, now))

        # Ngân sách nhập sai thuộc về email/mục đích, không thuộc riêng một mã: mã thay thế kế
        # thừa số lần sai (< 5). Đã qua _raise_if_locked nên attempts == 5 nghĩa là khóa 15 phút
        # đã hết hạn: ngân sách mới bắt đầu từ 0.
        # Lấy mã MỚI NHẤT (kể cả mã bị vô hiệu do gửi lỗi); mã mới nhất đã dùng thành công
        # nghĩa là lần xác thực trước đã xong nên ngân sách bắt đầu lại.
        previous = await otp_repository.lock_latest_code(self.session, email, OtpPurpose.APPLY)
        carried = (
            previous.attempts
            if previous is not None
            and previous.consumed_at is None
            and previous.attempts < MAX_WRONG_ATTEMPTS
            else 0
        )
        await otp_repository.invalidate_live_for_email(self.session, email, OtpPurpose.APPLY, now)
        code = crypto.generate_code()
        otp = OtpCode(
            email=email,
            purpose=OtpPurpose.APPLY,
            code_hash=crypto.hash_code(
                otp_secret,
                code=code,
                purpose=OtpPurpose.APPLY.value,
                email=email,
                submission_id=submission.id,
                job_id=job.id,
            ),
            submission_id=submission.id,
            job_id=job.id,
            attempts=carried,
            created_at=now,
            expires_at=now + OTP_TTL,
            ip=None,
        )
        self.session.add(otp)
        await self.session.flush()
        otp_id = otp.id
        job_title = job.title
        # Commit trước khi gửi: thư đã gửi không rollback được như DB.
        await self.session.commit()

        try:
            result = await NotificationService(self.settings).sendNow(
                session_factory,
                email_service,
                template_code=TemplateCode.OTP_APPLY,
                to=email,
                vars={
                    "full_name": contact.full_name,
                    "otp_code": code,
                    "ttl_minutes": str(int(OTP_TTL.total_seconds() // 60)),
                    "job_title": job_title,
                },
                secret_vars=frozenset({"otp_code"}),
                immediate_metadata={"otp_id": otp_id},
            )
        except (AppError, LookupError, ValueError) as exc:
            logger.error("OTP email could not be prepared (%s)", type(exc).__name__)
            async with session_factory() as cleanup:
                await otp_repository.invalidate_live_code(cleanup, otp_id, clock.utcnow())
                await cleanup.commit()
            raise _email_unavailable() from None
        if result.status is not EmailStatus.SENT:
            # sendNow đã vô hiệu đúng mã này (metadata otp_id); không đụng mã khác.
            raise _email_unavailable()
        return OtpIssued(expires_at=now + OTP_TTL, resend_available_at=now + RESEND_COOLDOWN)

    # ---- submit --------------------------------------------------------------------

    async def submit(
        self,
        *,
        submission_id: int,
        submission_token: str,
        job_id: int,
        otp_code: str,
        storage,
    ) -> ApplicationCreated:
        otp_secret = self.settings.require_otp_secret()
        token_secret = self.settings.require_submission_token_secret()
        now = clock.utcnow()
        submission = await self._verified_submission(
            submission_id, submission_token, token_secret, now
        )
        contact = await self._pending_contact(storage, submission)
        await self.session.rollback()  # kết thúc giao dịch đọc trước khi bắt đầu khóa

        # Thứ tự khóa cố định: tin -> submission -> ứng viên -> mã OTP.
        job = await repository.lock_job_for_share(self.session, job_id)
        if job is None:
            await self.session.rollback()
            raise _job_not_found()
        if not accepting(job, now):
            await self.session.rollback()
            raise _job_not_accepting()
        locked = await candidate_repository.lock_submission(self.session, submission_id)
        if locked is None or locked.expires_at <= now:
            await self.session.rollback()
            raise _invalid_submission()
        candidate = await candidate_repository.lock_candidate(self.session, locked.candidate_id)
        email = candidate.email
        await self._raise_if_locked(email, now)
        if await repository.application_exists(self.session, candidate.id, job.id):
            await self.session.rollback()
            raise _already_applied()

        live = await otp_repository.lock_live_code(self.session, email, OtpPurpose.APPLY)
        usable = live is not None and live.expires_at > now
        valid = (
            usable
            and crypto.is_well_formed(otp_code)
            and live.submission_id == locked.id
            and live.job_id == job.id
            and crypto.verify_code(
                otp_secret,
                live.code_hash,
                code=otp_code,
                purpose=OtpPurpose.APPLY.value,
                email=email,
                submission_id=locked.id,
                job_id=job.id,
            )
        )
        if not valid:
            await self._record_wrong_attempt(live if usable else None, email, now)
            raise field_error("otp_code", WRONG_CODE)

        candidate.full_name = contact.full_name
        candidate.phone = contact.phone
        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            submission_id=locked.id,
            status=ApplicationStatus.SCORING,
            submitted_at=now,
            criteria_set_id=job.current_criteria_set_id,
            ai_status=AiScoreStatus.PENDING,
            ai_total_score=None,
            updated_at=now,
            version=1,
        )
        live.consumed_at = now
        try:
            application_id = await repository.add_application(self.session, application)
            await self.session.commit()
        except IntegrityError:
            # Hai lượt nộp song song: UNIQUE (candidate, job) giữ đúng một hồ sơ.
            await self.session.rollback()
            raise _already_applied() from None
        except DBAPIError as exc:
            await self.session.rollback()
            logger.error("Application could not be saved (%s)", type(exc).__name__)
            raise AppError(
                "Không lưu được hồ sơ lúc này. Mã xác thực vẫn dùng được, vui lòng thử lại.",
                status_code=500,
                code="internal_error",
            ) from None
        return ApplicationCreated(application_id=application_id, submitted_at=now)

    async def _record_wrong_attempt(self, live: OtpCode | None, email: str, now: datetime) -> None:
        """Count a wrong entry and commit it before the error response (never rolled back)."""
        if live is not None:
            live.attempts = min(live.attempts + 1, MAX_WRONG_ATTEMPTS)
            if live.attempts >= MAX_WRONG_ATTEMPTS:
                # Lần sai thứ 5: khóa ngay 15 phút theo email (gửi lại không gỡ khóa).
                await consume(self.session, self._lock_key(email), LOCK_RULE, now)
                await self.session.commit()
                raise _locked(LOCK_RULE.window_seconds)
        await self.session.commit()
