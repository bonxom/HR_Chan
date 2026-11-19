"""OTP persistence helpers. Callers own the transaction."""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.otp.models import OtpCode, OtpPurpose


async def invalidate_live_code(session: AsyncSession, otp_id: int, at: datetime) -> bool:
    """Invalidate exactly this code if it is still live; newer codes are never touched.

    An already invalidated or consumed code keeps its original timestamps.
    """
    result = await session.execute(
        update(OtpCode)
        .where(
            OtpCode.id == otp_id,
            OtpCode.consumed_at.is_(None),
            OtpCode.invalidated_at.is_(None),
        )
        .values(invalidated_at=at)
    )
    return bool(result.rowcount)


async def serialize_email(session: AsyncSession, email: str, purpose: OtpPurpose) -> None:
    """Transaction-scoped advisory lock per email + purpose.

    Hai yêu cầu gửi mã cùng email chạy tuần tự: không thể cùng vượt cooldown hay tạo hai
    mã còn hiệu lực. Khóa tự nhả khi giao dịch kết thúc.
    """
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(f"otp:{purpose}:{email}", 0)))
    )


async def issued_since(
    session: AsyncSession, email: str, purpose: OtpPurpose, since: datetime
) -> list[datetime]:
    rows = await session.scalars(
        select(OtpCode.created_at)
        .where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.created_at > since)
        .order_by(OtpCode.created_at)
    )
    return list(rows)


async def last_issued(session: AsyncSession, email: str, purpose: OtpPurpose) -> datetime | None:
    return await session.scalar(
        select(func.max(OtpCode.created_at)).where(
            OtpCode.email == email, OtpCode.purpose == purpose
        )
    )


async def invalidate_live_for_email(
    session: AsyncSession, email: str, purpose: OtpPurpose, at: datetime
) -> None:
    await session.execute(
        update(OtpCode)
        .where(
            OtpCode.email == email,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
            OtpCode.invalidated_at.is_(None),
        )
        .values(invalidated_at=at)
    )


async def lock_latest_code(
    session: AsyncSession, email: str, purpose: OtpPurpose
) -> OtpCode | None:
    """Most recent code for email + purpose (any state), row-locked."""
    return await session.scalar(
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.purpose == purpose)
        .order_by(OtpCode.created_at.desc(), OtpCode.id.desc())
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_live_code(session: AsyncSession, email: str, purpose: OtpPurpose) -> OtpCode | None:
    return await session.scalar(
        select(OtpCode)
        .where(
            OtpCode.email == email,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
            OtpCode.invalidated_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
