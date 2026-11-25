"""Background jobs: posting expiry/retention and email outbox delivery.

Runs as its own process, never inside the API: ``uv run python -m app.worker``.
It sweeps once at startup, then every ``JOB_EXPIRY_INTERVAL_SECONDS`` via APScheduler.
Retention also runs at startup and daily at 02:00 in UTC+7, on its own schedule.
Queued outbox mail is delivered every ``EMAIL_OUTBOX_INTERVAL_SECONDS`` (30 s), and
abandoned immediate mail (API stopped mid-send) is marked FAILED on the same cadence.
It does not run migrations. Logs never include the database URL or exception text,
which may carry credentials; failures are reported by exception type only.
"""

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.otp.cleanup import purge_stale_codes
from app.integrations.email.service import IEmailService, build_email_service
from app.integrations.factories import build_cv_storage, build_scoring_agent
from app.modules.applications.reminders import remind_overdue_reviews
from app.modules.applications.scoring import CvScoringService, score_pending_batch
from app.modules.candidates.cleanup import cleanup_expired_submissions
from app.modules.notifications.worker import deliver_due_batch, fail_abandoned_immediate
from app.modules.recruitment.retention import COMPANY_TZ
from app.modules.recruitment.service import JobPostingService

logger = logging.getLogger(__name__)

SWEEP_JOB_ID = "close-expired-jobs"
PURGE_JOB_ID = "purge-closed-jobs"
OUTBOX_JOB_ID = "deliver-email-outbox"
ABANDONED_JOB_ID = "fail-abandoned-immediate-email"
CV_CLEANUP_JOB_ID = "cleanup-expired-cv-submissions"
OTP_CLEANUP_JOB_ID = "purge-stale-otp-codes"
SCORING_JOB_ID = "score-pending-applications"
REVIEW_REMINDER_JOB_ID = "remind-overdue-reviews"


async def close_expired_once(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Run one expiry sweep in its own session and return how many postings were closed."""
    async with session_factory() as session:
        closed = await JobPostingService(session).close_expired_jobs()
    return len(closed)


async def purge_closed_once(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """One retention sweep in an independent database session."""
    async with session_factory() as session:
        purged = await JobPostingService(session).purge_closed_jobs()
    return len(purged)


# Task được theo dõi riêng để Ctrl+C/shutdown không hủy giữa lúc đang commit.
# asyncio.shield bảo vệ tác vụ con; drain chờ xong rồi mới đóng kết nối database.
class _Sweeper:
    """Runs sweeps as tracked tasks so shutdown can let an in-flight one commit.

    APScheduler's asyncio executor cancels running job futures on shutdown; each sweep
    therefore runs in its own task, shielded from that cancellation and drained before
    the engine is disposed.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._active: set[asyncio.Task[None]] = set()
        self._closing = False

    async def run(self) -> None:
        if self._closing:
            return
        task = asyncio.ensure_future(self._sweep())
        self._active.add(task)
        task.add_done_callback(self._active.discard)
        await asyncio.shield(task)

    async def _sweep(self) -> None:
        try:
            closed = await close_expired_once(self._session_factory)
        except Exception as exc:  # one failed sweep must not stop later ones
            logger.error("Expired job sweep failed (%s)", type(exc).__name__)
            return
        if closed:
            logger.info("Closed %d expired job posting(s)", closed)

    async def drain(self) -> None:
        """Refuse new sweeps and wait for running ones to finish their transaction."""
        self._closing = True
        if self._active:
            await asyncio.gather(*self._active, return_exceptions=True)


class _Purger(_Sweeper):
    # Dùng lại cơ chế shutdown an toàn nhưng chạy retention trong session riêng,
    # độc lập với tác vụ đóng tin hết hạn.
    async def _sweep(self) -> None:
        try:
            purged = await purge_closed_once(self._session_factory)
        except Exception as exc:
            logger.error("Closed job retention sweep failed (%s)", type(exc).__name__)
            return
        if purged:
            logger.info("Purged %d closed job posting(s)", purged)


class _OutboxDeliverer(_Sweeper):
    # Mỗi lượt gửi tối đa N thư xếp hàng; shutdown chờ lượt đang chạy ghi xong kết quả.
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        email_service: IEmailService,
        settings: Settings,
    ) -> None:
        super().__init__(session_factory)
        self._email_service = email_service
        self._settings = settings

    async def _sweep(self) -> None:
        try:
            sent = await deliver_due_batch(
                self._session_factory, self._email_service, self._settings, clock.utcnow()
            )
        except Exception as exc:
            logger.error("Email outbox batch failed (%s)", type(exc).__name__)
            return
        if sent:
            logger.info("Processed %d outbox email(s)", sent)


class _CvCleaner(_Sweeper):
    # Dọn CV tạm quá 24 giờ chưa thành hồ sơ; chỉ trong kho CV riêng của tính năng.
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], storage) -> None:
        super().__init__(session_factory)
        self._storage = storage

    async def _sweep(self) -> None:
        if self._storage is None:
            logger.warning("CV cleanup skipped: CV storage is not configured")
            return
        try:
            removed = await cleanup_expired_submissions(
                self._session_factory, self._storage, clock.utcnow()
            )
        except Exception as exc:
            logger.error("CV cleanup failed (%s)", type(exc).__name__)
            return
        if removed:
            logger.info("Removed %d expired CV submission(s)", removed)


class _Scorer(_Sweeper):
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], service: CvScoringService
    ):
        super().__init__(session_factory)
        self._service = service
        self._retry_after: dict[int, float] = {}

    async def _sweep(self) -> None:
        try:
            await score_pending_batch(self._session_factory, self._service, self._retry_after)
        except Exception as exc:
            logger.error("Scoring worker failed (%s)", type(exc).__name__)


class _ReviewReminder(_Sweeper):
    def __init__(self, session_factory, settings):
        super().__init__(session_factory)
        self._settings = settings

    async def _sweep(self):
        try:
            await remind_overdue_reviews(self._session_factory, self._settings)
        except Exception as exc:
            logger.error("Review reminders failed (%s)", type(exc).__name__)


class _OtpPurger(_Sweeper):
    # Xóa OTP đã hết hạn quá 24 giờ để không giữ FK tới tin/CV mãi.
    async def _sweep(self) -> None:
        try:
            removed = await purge_stale_codes(self._session_factory, clock.utcnow())
        except Exception as exc:
            logger.error("OTP cleanup failed (%s)", type(exc).__name__)
            return
        if removed:
            logger.info("Removed %d stale OTP code(s)", removed)


class _AbandonedImmediateCloser(_Sweeper):
    # Chốt FAILED thư gửi ngay bị bỏ dở khi API dừng giữa chừng; không gửi lại.
    async def _sweep(self) -> None:
        try:
            closed = await fail_abandoned_immediate(self._session_factory, clock.utcnow())
        except Exception as exc:
            logger.error("Abandoned immediate email sweep failed (%s)", type(exc).__name__)
            return
        if closed:
            logger.info("Closed %d abandoned immediate email(s)", closed)


async def run_worker(settings: Settings, stop_event: asyncio.Event) -> None:
    """Sweep now, then on the configured interval until ``stop_event`` is set."""
    # Dựng dịch vụ email trước engine: cấu hình sai thì dừng mà không rò kết nối.
    email_service = build_email_service(settings)
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    sweeper = _Sweeper(session_factory)
    purger = _Purger(session_factory)
    outbox = _OutboxDeliverer(session_factory, email_service, settings)
    abandoned = _AbandonedImmediateCloser(session_factory)
    cv_storage = build_cv_storage(settings)
    cv_cleaner = _CvCleaner(session_factory, cv_storage)
    scorer = _Scorer(
        session_factory,
        CvScoringService(build_scoring_agent(), cv_storage, settings.cv_scoring_timeout_seconds),
    )
    otp_purger = _OtpPurger(session_factory)
    review_reminder = _ReviewReminder(session_factory, settings)
    scheduler = AsyncIOScheduler()
    started = False
    try:
        await sweeper.run()
        scheduler.add_job(
            sweeper.run,
            "interval",
            seconds=settings.job_expiry_interval_seconds,
            id=SWEEP_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            purger.run,
            # Cron theo UTC+7; khác với khoảng quét đóng tin tính bằng giây ở trên.
            "cron",
            hour=2,
            minute=0,
            timezone=COMPANY_TZ,
            id=PURGE_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        # Outbox chạy theo chu kỳ riêng; nhiều tiến trình worker vẫn an toàn nhờ
        # FOR UPDATE SKIP LOCKED trong database.
        scheduler.add_job(
            outbox.run,
            "interval",
            seconds=settings.email_outbox_interval_seconds,
            id=OUTBOX_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            abandoned.run,
            "interval",
            seconds=settings.email_outbox_interval_seconds,
            id=ABANDONED_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        for runner, job_id in ((cv_cleaner, CV_CLEANUP_JOB_ID), (otp_purger, OTP_CLEANUP_JOB_ID)):
            scheduler.add_job(
                runner.run,
                "interval",
                seconds=settings.application_cleanup_interval_seconds,
                id=job_id,
                max_instances=1,
                coalesce=True,
            )
        scheduler.start()
        started = True
        logger.info(
            "Job expiry worker started (interval %d seconds)",
            settings.job_expiry_interval_seconds,
        )
        # Quét bù tin đủ hạn khi worker từng bị tắt. Scheduler đã chạy nên việc
        # dọn nhiều tin cũ không chặn lịch đóng tin hết hạn.
        scheduler.add_job(
            scorer.run,
            "interval",
            seconds=settings.cv_scoring_interval_seconds,
            id=SCORING_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        await purger.run()
        scheduler.add_job(
            review_reminder.run,
            "interval",
            seconds=30,
            id=REVIEW_REMINDER_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        await review_reminder.run()
        await stop_event.wait()
    finally:
        if started:
            scheduler.pause()
        await sweeper.drain()
        await purger.drain()
        await outbox.drain()
        await abandoned.drain()
        await cv_cleaner.drain()
        await scorer.drain()
        await otp_purger.drain()
        await review_reminder.drain()
        if started:
            scheduler.shutdown(wait=False)
            # AsyncIOScheduler.shutdown is dispatched onto the loop; let it run.
            await asyncio.sleep(0)
        await engine.dispose()
        logger.info("Job expiry worker stopped")


async def _serve(settings: Settings) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows: Ctrl+C cancels the main task instead; run_worker's finally
            # still drains the running sweep and disposes the engine.
            pass
    await run_worker(settings, stop_event)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        asyncio.run(_serve(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
