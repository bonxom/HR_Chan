from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import AppError
from app.core.response_handler import ResponseContext
from app.core.response_links import LinkOutcome, LinkPurpose, invalid_link
from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate
from app.modules.interviews.models import Interview
from app.modules.recruitment.models import JobPosting
from app.modules.responses import repository
from app.modules.responses.consent_handler import TalentPoolResponseHandler

SUPPORTED = {LinkPurpose.CONFIRM_INTERVIEW, LinkPurpose.TALENT_POOL_CONSENT}


class CandidateResponseService:
    def __init__(self, session, settings):
        self.session = session
        self.settings = settings

    def handler(self, purpose):
        if purpose == LinkPurpose.TALENT_POOL_CONSENT:
            return TalentPoolResponseHandler(self.session, self.settings)
        from app.modules.responses.interview_handler import InterviewResponseHandler

        return InterviewResponseHandler(self.session, self.settings)

    async def resolve(self, token):
        try:
            link = await repository.find_link(self.session, token)
            now = await repository.decision_time(self.session)
            if (
                link is None
                or link.purpose not in SUPPORTED
                or link.invalidated_at is not None
                or link.expires_at <= now
            ):
                raise invalid_link()
            if link.used_at is not None:
                return {"completed": True, "outcome": link.outcome, "completed_at": link.used_at}
            app = await self.session.get(Application, link.application_id)
            interview = (
                await self.session.get(Interview, link.interview_id) if link.interview_id else None
            )
            if app is None or (interview is not None and interview.application_id != app.id):
                raise invalid_link()
            candidate = await self.session.get(Candidate, app.candidate_id)
            job = await self.session.get(JobPosting, app.job_id)
            ctx = ResponseContext(app, link, interview, candidate, job, now)
            details = await self.handler(link.purpose).view(ctx)
            return dict(
                completed=False,
                purpose=link.purpose,
                job_title=job.title,
                expires_at=link.expires_at,
                **details,
            )
        except DBAPIError:
            await self.session.rollback()
            raise AppError("Dịch vụ tạm thời không sẵn sàng", 503, "response_unavailable") from None

    async def submit(self, payload):
        try:
            initial = await repository.find_link(self.session, payload.token)
            if initial is None or initial.purpose not in SUPPORTED:
                raise invalid_link()
            ctx = await repository.lock_response(self.session, initial.id)
            if (
                ctx is None
                or ctx.link.used_at is not None
                or ctx.link.invalidated_at is not None
                or ctx.link.expires_at <= ctx.now
            ):
                raise invalid_link()
            await self.session.execute(text("SELECT set_config('app.actor_id','',true)"))
            result = await self.handler(ctx.link.purpose).execute(ctx, payload)
            ctx.link.used_at = ctx.now
            ctx.link.outcome = LinkOutcome(result["outcome"])
            await self.session.commit()
            return result
        except DBAPIError:
            await self.session.rollback()
            raise AppError("Dịch vụ tạm thời không sẵn sàng", 503, "response_unavailable") from None
        except Exception:
            await self.session.rollback()
            raise
