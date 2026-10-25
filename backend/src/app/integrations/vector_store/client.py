from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class VectorMatch:
    entity_id: UUID
    distance: float


class VectorSearchClient(Protocol):
    async def search(self, embedding: list[float], *, limit: int) -> list[VectorMatch]: ...
