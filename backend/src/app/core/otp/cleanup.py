"""Remove stale OTP rows so old codes never pin postings or CVs through their FKs.

A row is stale when it expired more than 24 hours ago: beyond the hourly resend window
and the 15-minute wrong-code lock (the lock itself lives in ``auth_rate_limits``), so
deleting it changes no rule. Deletion runs in bounded batches.
"""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

STALE_AFTER = timedelta(hours=24)
BATCH_SIZE = 1000
MAX_BATCHES = 100

_DELETE = text(
    "DELETE FROM otp_codes WHERE id IN ("
    " SELECT id FROM otp_codes WHERE expires_at < :cutoff ORDER BY id LIMIT :batch"
    " FOR UPDATE SKIP LOCKED)"
)


async def purge_stale_codes(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> int:
    removed = 0
    cutoff = now - STALE_AFTER
    for _ in range(MAX_BATCHES):
        async with session_factory() as session:
            result = await session.execute(_DELETE, {"cutoff": cutoff, "batch": BATCH_SIZE})
            await session.commit()
        count = result.rowcount or 0
        removed += count
        if count < BATCH_SIZE:
            break
    return removed
