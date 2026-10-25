from typing import Protocol


class EmbeddingClient(Protocol):
    async def embed(self, text: str) -> list[float]: ...
