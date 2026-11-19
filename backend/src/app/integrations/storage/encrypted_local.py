"""Encrypted local file store for CVs (outside any public/static directory).

* Keys are random (``secrets.token_urlsafe``), never derived from the file name or the
  candidate; a key is also the file name, so only ``[A-Za-z0-9_-]{32,100}`` is accepted
  (no separators, no ``..``): a key can never address a path outside ``root``.
* Each object is AES-256-GCM encrypted with a fresh 96-bit nonce; the storage key is the
  associated data, so swapping two files is detected. The AES key is derived (HKDF) from
  the configured secret, which must be stable across restarts.
* Symlinks inside the store are refused. Writes go to a temporary file then are renamed,
  so a crash never leaves a half-written object under a valid key.
"""

import asyncio
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.integrations.storage.client import (
    StorageError,
    StorageIntegrityError,
    StorageKeyError,
)

__all__ = [
    "EncryptedLocalStorage",
    "StorageError",
    "StorageIntegrityError",
    "StorageKeyError",
]

KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,100}")
_NONCE_BYTES = 12
_MAGIC = b"HRCV1"
_KDF_INFO = b"hr-chan cv storage v1"
MIN_KEY_BYTES = 32


class EncryptedLocalStorage:
    def __init__(self, root: Path, key: bytes) -> None:
        if len(key) < MIN_KEY_BYTES:
            raise ValueError("CV storage key must be at least 32 bytes")
        self._root = Path(root)
        self._aead = AESGCM(
            HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_KDF_INFO).derive(key)
        )

    # ---- helpers ---------------------------------------------------------------------

    def _path(self, key: str) -> Path:
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise StorageKeyError("Invalid storage key")
        return self._root / key

    def _ensure_root(self) -> Path:
        root = self._root
        if root.is_symlink():
            raise StorageError("Storage root must not be a symlink")
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def _write(self, key: str, data: bytes) -> None:
        root = self._ensure_root()
        target = self._path(key)
        nonce = os.urandom(_NONCE_BYTES)
        blob = _MAGIC + nonce + self._aead.encrypt(nonce, data, key.encode())
        temporary = root / f".tmp-{secrets.token_hex(16)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _read(self, key: str) -> bytes:
        path = self._path(key)
        if path.is_symlink():
            raise StorageIntegrityError("Stored object is not a regular file")
        try:
            blob = path.read_bytes()
        except FileNotFoundError:
            raise StorageIntegrityError("Stored object is missing") from None
        if not blob.startswith(_MAGIC) or len(blob) < len(_MAGIC) + _NONCE_BYTES + 16:
            raise StorageIntegrityError("Stored object is corrupt")
        nonce = blob[len(_MAGIC) : len(_MAGIC) + _NONCE_BYTES]
        try:
            return self._aead.decrypt(nonce, blob[len(_MAGIC) + _NONCE_BYTES :], key.encode())
        except InvalidTag:
            raise StorageIntegrityError("Stored object failed authentication") from None

    def _remove(self, key: str) -> None:
        path = self._path(key)
        if path.is_symlink():
            # Không theo symlink: chỉ gỡ chính liên kết nằm trong kho.
            path.unlink(missing_ok=True)
            return
        path.unlink(missing_ok=True)

    def _keys(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return [
            entry.name
            for entry in self._root.iterdir()
            if entry.is_file() and not entry.is_symlink() and KEY_PATTERN.fullmatch(entry.name)
        ]

    # ---- public API (file I/O runs in a worker thread) ---------------------------------

    async def put(self, data: bytes) -> str:
        key = secrets.token_urlsafe(32)  # 43 ký tự ngẫu nhiên
        await asyncio.to_thread(self._write, key, data)
        return key

    async def get(self, key: str) -> bytes:
        self._path(key)
        return await asyncio.to_thread(self._read, key)

    async def delete(self, key: str) -> None:
        self._path(key)
        await asyncio.to_thread(self._remove, key)

    async def list_keys(self) -> list[str]:
        """Keys of objects owned by this store (for orphan cleanup)."""
        return await asyncio.to_thread(self._keys)

    def _stale(self, older_than: datetime, limit: int) -> list[str]:
        cutoff = older_than.timestamp()
        stale: list[str] = []
        for key in self._keys():
            try:
                if (self._root / key).stat().st_mtime < cutoff:
                    stale.append(key)
            except FileNotFoundError:
                continue
            if len(stale) >= limit:
                break
        return stale

    async def stale_keys(self, older_than: datetime, limit: int) -> list[str]:
        """Own keys whose file was last written before ``older_than`` (orphan sweep)."""
        return await asyncio.to_thread(self._stale, older_than, limit)
