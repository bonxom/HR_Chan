"""Remove temporary CV submissions 24 hours after upload (plan task 6).

Each submission is claimed with ``FOR UPDATE SKIP LOCKED`` and re-checked under that lock:
a submission referenced by an application (or locked by a submit in progress) is never
removed. Its OTP rows are deleted first (FK), then the row, and only after the commit the
encrypted file. A file that cannot be removed is left for the orphan sweep, which only
looks at keys of this feature's own store and only at files that no submission references
and that are older than an hour (an upload in progress may not have committed yet).
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.otp.models import OtpCode
from app.modules.candidates import repository

logger = logging.getLogger(__name__)

ORPHAN_MIN_AGE = timedelta(hours=1)
ORPHAN_BATCH = 200


async def cleanup_expired_submissions(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    now: datetime,
    *,
    batch_size: int = 100,
) -> int:
    removed = 0
    seen: list[int] = []
    while len(seen) < batch_size:
        async with session_factory() as session:
            submission = await repository.claim_expired_submission(session, now, seen)
            if submission is None:
                await session.rollback()
                break
            seen.append(submission.id)
            # Kiểm tra lại dưới khóa: một lượt nộp hồ sơ có thể vừa commit application.
            if await repository.is_referenced(session, submission.id):
                await session.rollback()
                continue
            key = submission.cv_storage_key
            await session.execute(delete(OtpCode).where(OtpCode.submission_id == submission.id))
            await session.delete(submission)
            await session.commit()
        removed += 1
        try:
            await storage.delete(key)
        except Exception as exc:
            logger.warning("Expired CV file could not be removed (%s)", type(exc).__name__)
    await _sweep_orphans(session_factory, storage, now)
    return removed


async def _sweep_orphans(session_factory, storage, now: datetime) -> None:
    list_stale = getattr(storage, "stale_keys", None)
    if list_stale is None:
        return
    try:
        candidates = await list_stale(now - ORPHAN_MIN_AGE, ORPHAN_BATCH)
    except Exception as exc:
        logger.warning("CV orphan sweep skipped (%s)", type(exc).__name__)
        return
    if not candidates:
        return
    async with session_factory() as session:
        referenced = await repository.known_storage_keys(session, candidates)
    for key in candidates:
        if key in referenced:
            continue
        try:
            await storage.delete(key)
        except Exception as exc:
            logger.warning("CV orphan could not be removed (%s)", type(exc).__name__)
