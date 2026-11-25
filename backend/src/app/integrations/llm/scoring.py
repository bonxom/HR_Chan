"""AI scoring boundary and local deterministic demo provider."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScoringCriterion:
    id: int
    name: str
    description: str


class IAIAgent(Protocol):
    async def score_criteria(self, cv: bytes, criteria: Sequence[ScoringCriterion]) -> object: ...


class FakeAIAgent:
    """Produce reproducible synthetic scores; the service evaluates mandatory floors."""

    async def score_criteria(self, cv: bytes, criteria: Sequence[ScoringCriterion]) -> object:
        fingerprint = hashlib.sha256(cv).digest()
        result = []
        for criterion in criteria:
            digest = hashlib.sha256(fingerprint + criterion.id.to_bytes(8)).digest()
            result.append(
                {
                    "criterion_id": criterion.id,
                    "score": int.from_bytes(digest[:2]) % 101,
                    "comment": "Điểm mô phỏng để kiểm thử quy trình.",
                }
            )
        return result
