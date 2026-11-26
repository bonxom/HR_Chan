import logging

from sqlalchemy import func, select, text

from app.core.exceptions import AppError
from app.core.response_links import LinkPurpose, ResponseLink, ResponseLinkService
from app.modules.audit.schemas import AuditAction
from app.modules.responses import repository
from app.modules.responses.interview_handler import InterviewResponseHandler
from app.modules.responses.notifications import audit_response, notify_expired

logger = logging.getLogger(__name__)
PURPOSES = (LinkPurpose.CONFIRM_INTERVIEW, LinkPurpose.TALENT_POOL_CONSENT)


class ResponseExpirySweep:
    """Bounded expiry work with a cursor retained across worker sweeps."""

    def __init__(self, session_factory, settings, *, batch_size=32):
        self.session_factory = session_factory
        self.settings = settings
        self.batch_size = batch_size
        self.cursor = 0
        self.upper_bound: int | None = None

    async def run(self):
        async with self.session_factory() as session:
            now = await repository.decision_time(session)
            eligible = select(ResponseLink.id).where(
                ResponseLink.purpose.in_(PURPOSES),
                ResponseLink.used_at.is_(None),
                ResponseLink.invalidated_at.is_(None),
                ResponseLink.expires_at <= now,
            )
            if self.upper_bound is None:
                # New arrivals wait for the next pass so older rows get retried.
                self.upper_bound = await session.scalar(
                    eligible.with_only_columns(func.max(ResponseLink.id))
                )
                if self.upper_bound is None:
                    return 0
            ids = list(
                await session.scalars(
                    eligible.where(
                        ResponseLink.id > self.cursor,
                        ResponseLink.id <= self.upper_bound,
                    )
                    .order_by(ResponseLink.id)
                    .limit(self.batch_size)
                )
            )
        if not ids:
            self.cursor = 0
            self.upper_bound = None
            return 0
        processed = 0
        for link_id in ids:
            self.cursor = link_id
            try:
                async with self.session_factory.begin() as session:
                    context = await repository.lock_response(session, link_id, skip_locked=True)
                    if context is None:
                        continue
                    link = context.link
                    if (
                        link.used_at is not None
                        or link.invalidated_at is not None
                        or link.expires_at > context.now
                        or link.purpose not in PURPOSES
                    ):
                        continue
                    await session.execute(text("SELECT set_config('app.actor_id','',true)"))
                    if link.purpose == LinkPurpose.CONFIRM_INTERVIEW:
                        handler = InterviewResponseHandler(session, self.settings)
                        try:
                            handler.validate(context)
                        except AppError:
                            link.invalidated_at = context.now
                            await audit_response(
                                session,
                                context,
                                AuditAction.RESPONSE_INVALIDATED,
                                {"reason": "stale_interview"},
                            )
                            continue
                        await handler.expire(context)
                    await ResponseLinkService(session, self.settings.public_base_url).expire_locked(
                        link, context.now
                    )
                    await audit_response(
                        session,
                        context,
                        AuditAction.RESPONSE_EXPIRED,
                        {"outcome": "EXPIRED", "reason": "Không phản hồi trong thời hạn"},
                    )
                    await notify_expired(session, self.settings, context)
                processed += 1
            except Exception as exc:
                logger.error("Response expiry failed for link %d (%s)", link_id, type(exc).__name__)
        return processed


async def expire_response_links(session_factory, settings, batch_size=32):
    """Run one standalone batch; workers retain a ResponseExpirySweep instance."""
    return await ResponseExpirySweep(session_factory, settings, batch_size=batch_size).run()
