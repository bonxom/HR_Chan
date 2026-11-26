from sqlalchemy import select, text

from app.core.response_handler import ResponseContext
from app.core.response_links import ResponseLink, hash_token
from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate
from app.modules.interviews.models import Interview
from app.modules.recruitment.models import JobPosting


async def decision_time(session):
    return await session.scalar(text("SELECT clock_timestamp()"))


async def find_link(session, token):
    return await session.scalar(
        select(ResponseLink).where(ResponseLink.token_hash == hash_token(token))
    )


async def lock_response(session, link_id, skip_locked=False):
    initial = await session.get(ResponseLink, link_id)
    if initial is None:
        return None
    application_id = initial.application_id
    interview_id = initial.interview_id
    purpose = initial.purpose
    query = (
        select(Application)
        .where(Application.id == application_id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )
    application = await session.scalar(query)
    if application is None:
        return None
    interview = None
    if interview_id is not None:
        interview = await session.scalar(
            select(Interview)
            .where(Interview.id == interview_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    candidate_query = select(Candidate).where(Candidate.id == application.candidate_id)
    if purpose == "TALENT_POOL_CONSENT":
        candidate_query = candidate_query.with_for_update()
    candidate = await session.scalar(candidate_query.execution_options(populate_existing=True))
    link = await session.scalar(
        select(ResponseLink)
        .where(ResponseLink.id == link_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if link is None or link.application_id != application.id:
        return None
    if link.interview_id != interview_id or link.purpose != purpose:
        return None
    if interview is not None and interview.application_id != application.id:
        return None
    job = await session.get(JobPosting, application.job_id)
    return ResponseContext(
        application, link, interview, candidate, job, await decision_time(session)
    )
