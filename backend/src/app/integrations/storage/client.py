"""Private object storage boundary addressed by opaque keys only."""

from typing import Protocol


class StorageError(Exception):
    """Base error; messages never contain file content or filesystem paths."""


class StorageKeyError(StorageError):
    """Malformed key (would escape the store or is not one of its keys)."""


class StorageIntegrityError(StorageError):
    """Stored object missing, tampered with, or encrypted with another key."""


class ObjectStorage(Protocol):
    async def put(self, data: bytes) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...
