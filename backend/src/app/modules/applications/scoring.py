"""Score the criteria version captured by the OTP submission transaction."""

import asyncio
import logging
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.integrations.llm.scoring import IAIAgent, ScoringCriterion
from app.integrations.storage.client import ObjectStorage, StorageError
from app.modules.applications import repository
from app.modules.applications.models import (
    AiScoreStatus,
    Application,
    ApplicationScore,
    ApplicationStatus,
)
from app.modules.candidates.envelope import EnvelopeFormatError, unpack
from app.modules.candidates.models import CvSubmission
from app.modules.recruitment.models import CriteriaSet, Criterion
from app.modules.recruitment.repository import CriteriaRepository

logger = logging.getLogger(__name__)
QUALIFIED_NOTE = "Đạt ngưỡng – cần mời thủ công"


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    criterion_id: StrictInt
    score: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    comment: str = Field(min_length=1, pattern=r"^[^\x00]*$")


_SCORE_LIST = TypeAdapter(list[CriterionScore])


def validate_scores(raw: object, criteria: Sequence[Criterion]) -> dict[int, CriterionScore]:
    items = _SCORE_LIST.validate_python(raw)
    mapped = {item.criterion_id: item for item in items}
    if len(mapped) != len(items) or set(mapped) != {criterion.id for criterion in criteria}:
        raise ValueError("Scores must cover every criterion exactly once")
    return mapped


def weighted_total(scores: dict[int, CriterionScore], criteria: Sequence[Criterion]) -> Decimal:
    total = sum((scores[item.id].score * item.weight for item in criteria), Decimal(0))
    return (total / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check_mandatory(
    scores: dict[int, CriterionScore], criteria: Sequence[Criterion]
) -> tuple[dict[int, bool | None], bool]:
    outcomes = {
        item.id: scores[item.id].score >= item.min_score if item.is_mandatory else None
        for item in criteria
    }
    return outcomes, False not in outcomes.values()


class CvScoringService:
    def __init__(self, agent: IAIAgent, storage: ObjectStorage | None, timeout: float):
        self.agent = agent
        self.storage = storage
        self.timeout = timeout

    async def score(self, session: AsyncSession, application: Application) -> None:
        if application.criteria_set_id is None:
            application.ai_status = AiScoreStatus.NEEDS_REVIEW
            application.ai_failure_reason = "criteria_unavailable"
        else:
            await self._evaluate(session, application)
        now = clock.utcnow()
        due = await session.scalar(
            text(
                "SELECT working_deadline(:at, value::integer) FROM system_settings"
                " WHERE key = 'hr_review_days'"
            ),
            {"at": now},
        )
        if due is None:
            raise RuntimeError("Missing review deadline setting")
        application.review_due_at = due
        application.updated_at = now
        application.version += 1
        application.status = ApplicationStatus.PENDING_HR_REVIEW

    async def _evaluate(self, session: AsyncSession, application: Application) -> None:
        set_id = application.criteria_set_id
        criteria_set = await session.get(CriteriaSet, set_id)
        criteria = (await CriteriaRepository(session).list_for_sets([set_id]))[set_id]
        if criteria_set is None or not criteria or sum(item.weight for item in criteria) != 100:
            application.ai_status = AiScoreStatus.NEEDS_REVIEW
            application.ai_failure_reason = "criteria_unavailable"
            return
        submission = await session.get(CvSubmission, application.submission_id)
        try:
            if submission is None or self.storage is None:
                raise StorageError("missing storage")
            cv, _ = unpack(await self.storage.get(submission.cv_storage_key))
            if not cv:
                raise EnvelopeFormatError("empty CV")
        except (StorageError, OSError, EnvelopeFormatError):
            application.ai_status = AiScoreStatus.NEEDS_REVIEW
            application.ai_failure_reason = "cv_unavailable"
            return
        inputs = [ScoringCriterion(item.id, item.name, item.description) for item in criteria]
        try:
            async with asyncio.timeout(self.timeout):
                raw = await self.agent.score_criteria(cv, inputs)
        except Exception:
            application.ai_status = AiScoreStatus.FAILED
            application.ai_failure_reason = "scoring_provider_failed"
            return
        try:
            scores = validate_scores(raw, criteria)
        except ValueError:
            application.ai_status = AiScoreStatus.NEEDS_REVIEW
            application.ai_failure_reason = "invalid_scoring_response"
            return
        total = weighted_total(scores, criteria)
        outcomes, mandatory_ok = check_mandatory(scores, criteria)
        session.add_all(
            [
                ApplicationScore(
                    application_id=application.id,
                    criterion_id=item.id,
                    score=scores[item.id].score,
                    ai_comment=scores[item.id].comment,
                    weight_snapshot=item.weight,
                    meets_mandatory=outcomes[item.id],
                )
                for item in criteria
            ]
        )
        await session.flush()
        application.ai_total_score = total
        application.ai_status = AiScoreStatus.SCORED
        application.hr_note = (
            QUALIFIED_NOTE if total >= criteria_set.auto_invite_threshold and mandatory_ok else None
        )


async def score_pending_batch(
    session_factory: async_sessionmaker[AsyncSession],
    service: CvScoringService,
    retry_after: dict[int, float],
    batch_size: int = 32,
) -> int:
    for row_id in list(retry_after):
        if retry_after[row_id] <= monotonic():
            del retry_after[row_id]
    processed = 0
    for _ in range(batch_size):
        row_id = None
        try:
            async with session_factory.begin() as session:
                application = await repository.claim_pending_scoring(session, retry_after.keys())
                if application is None:
                    break
                row_id = application.id
                await service.score(session, application)
            processed += 1
        except Exception as exc:
            if row_id is None:
                raise
            retry_after[row_id] = monotonic() + 30
            logger.error(
                "Application %d scoring transaction failed (%s)", row_id, type(exc).__name__
            )
    return processed
