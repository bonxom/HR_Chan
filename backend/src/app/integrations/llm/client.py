from typing import Protocol


class LLMClient(Protocol):
    async def rewrite_query(self, query: str) -> str: ...
