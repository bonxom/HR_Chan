"""Candidate and CV submission queries. Callers own every transaction."""

from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate, CvSubmission


async def get_or_create_candidate(
    session: AsyncSession, *, email: str, full_name: str, phone: str, now: datetime
) -> int:
    """Return the candidate for ``email``; create a placeholder only if none exists.

    Không bao giờ ghi đè thông tin của ứng viên đã có: dữ liệu mới chỉ thay thế sau OTP.
    ``ON CONFLICT DO NOTHING`` tránh lỗi khi hai lần tải lên cùng email chạy song song.
    """
    created = await session.scalar(
        insert(Candidate)
        .values(email=email, full_name=full_name, phone=phone, created_at=now)
        .on_conflict_do_nothing(index_elements=["email"])
        .returning(Candidate.id)
    )
    if created is not None:
        return created
    return await session.scalar(select(Candidate.id).where(Candidate.email == email))


async def add_submission(session: AsyncSession, submission: CvSubmission) -> int:
    session.add(submission)
    await session.flush()
    return submission.id


async def get_submission(session: AsyncSession, submission_id: int) -> CvSubmission | None:
    return await session.get(CvSubmission, submission_id)


async def lock_submission(session: AsyncSession, submission_id: int) -> CvSubmission | None:
    return await session.scalar(
        select(CvSubmission)
        .where(CvSubmission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_candidate(session: AsyncSession, candidate_id: int) -> Candidate | None:
    return await session.get(Candidate, candidate_id)


async def lock_candidate(session: AsyncSession, candidate_id: int) -> Candidate | None:
    return await session.scalar(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def unreferenced():
    return ~exists().where(Application.submission_id == CvSubmission.id)


async def claim_expired_submission(
    session: AsyncSession, now: datetime, skip_ids: list[int]
) -> CvSubmission | None:
    """Lock one expired, unused submission; rows held by another transaction are skipped."""
    query = (
        select(CvSubmission)
        .where(CvSubmission.expires_at <= now, unreferenced())
        .order_by(CvSubmission.id)
        .limit(1)
        .with_for_update(skip_locked=True, of=CvSubmission)
    )
    if skip_ids:
        query = query.where(CvSubmission.id.not_in(skip_ids))
    return await session.scalar(query)


async def is_referenced(session: AsyncSession, submission_id: int) -> bool:
    return bool(
        await session.scalar(select(exists().where(Application.submission_id == submission_id)))
    )


async def known_storage_keys(session: AsyncSession, keys: list[str]) -> set[str]:
    if not keys:
        return set()
    rows = await session.scalars(
        select(CvSubmission.cv_storage_key).where(CvSubmission.cv_storage_key.in_(keys))
    )
    return set(rows)
