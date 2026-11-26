from dataclasses import dataclass
from datetime import datetime

from app.core.response_links import ResponseLink
from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate
from app.modules.interviews.models import Interview
from app.modules.recruitment.models import JobPosting


@dataclass
class ResponseContext:
    application: Application
    link: ResponseLink
    interview: Interview | None
    candidate: Candidate
    job: JobPosting
    now: datetime


class ResponseHandler:
    """Purpose handlers execute inside the response service's transaction."""

    def __init__(self, session, settings):
        self.session = session
        self.settings = settings

    async def view(self, context: ResponseContext) -> dict:
        raise NotImplementedError

    async def apply(self, context: ResponseContext, payload) -> dict:
        raise NotImplementedError

    async def execute(self, context: ResponseContext, payload) -> dict:
        # Both entry points use the same purpose-specific state checks.
        await self.view(context)
        return await self.apply(context, payload)
