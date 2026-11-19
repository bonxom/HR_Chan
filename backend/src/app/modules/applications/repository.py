"""Application queries. Callers own every transaction."""

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.recruitment.models import JobPosting


async def get_job(session: AsyncSession, job_id: int) -> JobPosting | None:
    return await session.get(JobPosting, job_id)


async def lock_job_for_share(session: AsyncSession, job_id: int) -> JobPosting | None:
    """FOR SHARE: many submits may run together, an HR close/update (FOR UPDATE) waits.

    ``populate_existing`` đọc lại bản đã commit mới nhất sau khi chờ khóa.
    """
    return await session.scalar(
        select(JobPosting)
        .where(JobPosting.id == job_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )


async def application_exists(session: AsyncSession, candidate_id: int, job_id: int) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Application.candidate_id == candidate_id, Application.job_id == job_id
                )
            )
        )
    )


async def add_application(session: AsyncSession, application: Application) -> int:
    session.add(application)
    await session.flush()
    return application.id
