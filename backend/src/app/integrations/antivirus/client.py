"""ClamAV (clamd) scanning over the INSTREAM protocol.

The whole exchange (connect, stream, reply) is bounded by one timeout (<= 10 s, NFR04).
Anything other than an explicit ``OK``/``FOUND`` reply - timeout, refused connection,
error reply, size limit - raises ``ScannerUnavailableError``: a CV is never treated as
clean when the scanner could not decide. Content and replies are never logged.
"""

import asyncio
import contextlib
import struct
from enum import StrEnum
from typing import Protocol

CHUNK_BYTES = 64 * 1024
MAX_REPLY_BYTES = 4096


class ScanVerdict(StrEnum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"


class ScannerUnavailableError(Exception):
    def __init__(self, code: str = "scanner_unavailable") -> None:
        super().__init__(code)
        self.code = code


class VirusScanner(Protocol):
    async def scan(self, data: bytes) -> ScanVerdict: ...


class ClamAVScanner:
    def __init__(self, host: str, port: int, *, timeout: float = 10.0) -> None:
        self._host = host
        self._port = port
        self._timeout = min(timeout, 10.0)

    async def _exchange(self, data: bytes) -> bytes:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            writer.write(b"zINSTREAM\0")
            for start in range(0, len(data), CHUNK_BYTES):
                chunk = data[start : start + CHUNK_BYTES]
                writer.write(struct.pack(">I", len(chunk)) + chunk)
                await writer.drain()
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            reply = bytearray()
            while len(reply) < MAX_REPLY_BYTES:
                part = await reader.read(MAX_REPLY_BYTES - len(reply))
                if not part:
                    break
                reply += part
                if b"\0" in part:
                    break
            return bytes(reply)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def scan(self, data: bytes) -> ScanVerdict:
        try:
            async with asyncio.timeout(self._timeout):
                reply = await self._exchange(data)
        except TimeoutError:
            raise ScannerUnavailableError("scanner_timeout") from None
        except OSError:
            raise ScannerUnavailableError("scanner_unreachable") from None
        text = reply.split(b"\0", 1)[0].strip()
        if text.endswith(b"FOUND"):
            return ScanVerdict.INFECTED
        if text.endswith(b": OK") or text == b"OK":
            return ScanVerdict.CLEAN
        raise ScannerUnavailableError("scanner_error")
