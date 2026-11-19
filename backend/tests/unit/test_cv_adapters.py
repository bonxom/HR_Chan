# Adapter của luồng nộp CV: kho file AES-GCM riêng tư, ClamAV INSTREAM (máy chủ giả trên
# loopback), Cloudflare Turnstile (httpx MockTransport). Không gọi dịch vụ thật.
"""Storage, antivirus and CAPTCHA adapters (plan task 6).

Contracts:

* ``app.integrations.storage.encrypted_local.EncryptedLocalStorage(root: Path, key: bytes)``
  with ``await put(data) -> str`` (random opaque key, 32–100 chars of ``[A-Za-z0-9_-]``),
  ``await get(key) -> bytes``, ``await delete(key)`` (idempotent). Files live directly in
  ``root``; content is AES-GCM encrypted with a random nonce and the storage key as
  associated data. Errors: ``StorageError`` base, ``StorageKeyError`` (malformed key /
  path traversal), ``StorageIntegrityError`` (tampered file or wrong key). A key shorter
  than 32 bytes is refused with ``ValueError``.
* ``app.integrations.antivirus.client.ClamAVScanner(host, port, *, timeout=10.0)``;
  ``await scan(data) -> ScanVerdict`` (CLEAN/INFECTED) using ``zINSTREAM`` with 4-byte
  big-endian chunk lengths and a zero-length terminator; any timeout, disconnect or error
  reply raises ``ScannerUnavailableError`` (fail closed, never CLEAN).
* ``app.integrations.captcha.client.TurnstileVerifier(secret_key, *, expected_hostname=None,
  expected_action=None, timeout=10.0, transport=None)``; ``await verify(token, remote_ip)
  -> bool`` posts form fields ``secret``/``response``/``remoteip`` to
  ``TURNSTILE_VERIFY_URL``; network/HTTP errors raise ``CaptchaUnavailableError``.
"""

import asyncio
import contextlib
import struct
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings

KEY = b"k" * 32
CV = b"%PDF-1.4 private CV of Nguyen Van A, phone 0912345678"


# ---- encrypted local storage ----------------------------------------------------------


def storage(root: Path, key: bytes = KEY):
    from app.integrations.storage.encrypted_local import EncryptedLocalStorage

    return EncryptedLocalStorage(root, key)


async def test_storage_round_trip_encrypts_with_random_names_and_nonces(tmp_path) -> None:
    store = storage(tmp_path)
    first = await store.put(CV)
    second = await store.put(CV)

    assert first != second
    for key in (first, second):
        assert 32 <= len(key) <= 100
        assert all(char.isalnum() or char in "-_" for char in key)
    files = sorted(path for path in tmp_path.rglob("*") if path.is_file())
    assert len(files) == 2
    contents = [path.read_bytes() for path in files]
    assert contents[0] != contents[1]  # random nonce per file
    for blob in contents:
        assert CV not in blob and b"Nguyen Van A" not in blob
    assert await store.get(first) == CV
    assert await store.get(second) == CV


async def test_storage_detects_tampering_and_wrong_keys(tmp_path) -> None:
    from app.integrations.storage.encrypted_local import StorageIntegrityError

    store = storage(tmp_path)
    key = await store.put(CV)
    with pytest.raises(StorageIntegrityError):
        await storage(tmp_path, b"x" * 32).get(key)

    [path] = [p for p in tmp_path.rglob("*") if p.is_file()]
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 0x01
    path.write_bytes(bytes(blob))
    with pytest.raises(StorageIntegrityError):
        await store.get(key)


async def test_ciphertext_is_bound_to_its_storage_key(tmp_path) -> None:
    from app.integrations.storage.encrypted_local import StorageIntegrityError

    store = storage(tmp_path)
    first = await store.put(CV)
    second = await store.put(b"another document")
    files = {p.name: p for p in tmp_path.rglob("*") if p.is_file()}
    # Swap the encrypted files: associated data (the key) must reject the swap.
    a = next(p for name, p in files.items() if first in name)
    b = next(p for name, p in files.items() if second in name)
    a_bytes, b_bytes = a.read_bytes(), b.read_bytes()
    a.write_bytes(b_bytes)
    b.write_bytes(a_bytes)
    with pytest.raises(StorageIntegrityError):
        await store.get(first)


@pytest.mark.parametrize(
    "key",
    ["../outside", "..\\outside", "a/b" * 12, "/etc/passwd", "C:\\x", "", "short", "x" * 101],
)
async def test_storage_rejects_malformed_keys_and_path_traversal(tmp_path, key) -> None:
    from app.integrations.storage.encrypted_local import StorageKeyError

    root = tmp_path / "store"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not touch")
    store = storage(root)
    with pytest.raises(StorageKeyError):
        await store.get(key)
    with pytest.raises(StorageKeyError):
        await store.delete(key)
    assert outside.read_bytes() == b"do not touch"


async def test_delete_is_idempotent_and_only_removes_its_file(tmp_path) -> None:
    store = storage(tmp_path)
    keep = await store.put(b"keep me")
    gone = await store.put(b"remove me")
    await store.delete(gone)
    await store.delete(gone)
    assert await store.get(keep) == b"keep me"
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1


def test_storage_refuses_a_short_key(tmp_path) -> None:
    with pytest.raises(ValueError):
        storage(tmp_path, b"short")


# ---- ClamAV INSTREAM over loopback -----------------------------------------------------


class FakeClamd:
    """Minimal clamd speaking INSTREAM on 127.0.0.1 (network simulation, no ClamAV)."""

    def __init__(self, reply: bytes | None, *, close_early: bool = False) -> None:
        self.reply = reply
        self.close_early = close_early
        self.received: list[bytes] = []
        self.commands: list[bytes] = []
        self.server: asyncio.base_events.Server | None = None
        self.stop = asyncio.Event()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            self.commands.append(await reader.readexactly(10))
            if self.close_early:
                return
            payload = bytearray()
            while True:
                (size,) = struct.unpack(">I", await reader.readexactly(4))
                if size == 0:
                    break
                payload += await reader.readexactly(size)
            self.received.append(bytes(payload))
            if self.reply is None:
                await self.stop.wait()  # never answers while the client is waiting
                return
            writer.write(self.reply)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def __aenter__(self) -> tuple[str, int]:
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        host, port = self.server.sockets[0].getsockname()[:2]
        return host, port

    async def __aexit__(self, *exc) -> None:
        self.stop.set()
        self.server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.server.wait_closed(), 2)


async def scan_with(reply: bytes | None, data: bytes = CV, *, timeout=2.0, close_early=False):
    from app.integrations.antivirus.client import ClamAVScanner

    fake = FakeClamd(reply, close_early=close_early)
    async with fake as (host, port):
        verdict = await asyncio.wait_for(ClamAVScanner(host, port, timeout=timeout).scan(data), 10)
    return verdict, fake


async def test_clean_file_uses_the_instream_protocol() -> None:
    from app.integrations.antivirus.client import ScanVerdict

    big = CV * 5000  # several chunks
    verdict, fake = await scan_with(b"stream: OK\0", big)
    assert verdict is ScanVerdict.CLEAN
    assert fake.commands == [b"zINSTREAM\0"]
    assert fake.received == [big]


async def test_infected_file_is_reported() -> None:
    from app.integrations.antivirus.client import ScanVerdict

    verdict, _fake = await scan_with(b"stream: Eicar-Test-Signature FOUND\0")
    assert verdict is ScanVerdict.INFECTED


@pytest.mark.parametrize(
    ("reply", "close_early"),
    [
        (None, False),  # no answer: whole call bounded by the timeout
        (b"INSTREAM size limit exceeded. ERROR\0", False),
        (b"", True),  # connection dropped
        (b"garbage\0", False),
    ],
    ids=["timeout", "error-reply", "disconnect", "unknown-reply"],
)
async def test_scanner_problems_fail_closed(reply, close_early) -> None:
    from app.integrations.antivirus.client import ScannerUnavailableError

    with pytest.raises(ScannerUnavailableError):
        await scan_with(reply, timeout=0.5, close_early=close_early)


async def test_unreachable_scanner_fails_closed() -> None:
    from app.integrations.antivirus.client import ClamAVScanner, ScannerUnavailableError

    probe = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = probe.sockets[0].getsockname()[1]
    probe.close()
    await probe.wait_closed()
    with pytest.raises(ScannerUnavailableError):
        await ClamAVScanner("127.0.0.1", port, timeout=0.5).scan(CV)


# ---- Cloudflare Turnstile (server-side verification) -----------------------------------


def turnstile(handler, **options):
    from app.integrations.captcha.client import TurnstileVerifier

    return TurnstileVerifier(
        "turnstile-secret-placeholder", transport=httpx.MockTransport(handler), **options
    )


async def test_turnstile_posts_secret_token_and_ip_to_the_official_endpoint() -> None:
    from app.integrations.captcha.client import TURNSTILE_VERIFY_URL

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True, "hostname": "hr.example.test"})

    verifier = turnstile(handler, expected_hostname="hr.example.test")
    assert await verifier.verify("token-from-widget", "203.0.113.7") is True
    [request] = seen
    assert str(request.url) == TURNSTILE_VERIFY_URL
    assert TURNSTILE_VERIFY_URL == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    form = dict(httpx.QueryParams(request.content.decode()))
    assert form == {
        "secret": "turnstile-secret-placeholder",
        "response": "token-from-widget",
        "remoteip": "203.0.113.7",
    }


@pytest.mark.parametrize(
    ("body", "options"),
    [
        ({"success": False, "error-codes": ["invalid-input-response"]}, {}),
        ({"success": True, "hostname": "evil.example"}, {"expected_hostname": "hr.example.test"}),
        ({"success": True, "action": "login"}, {"expected_action": "apply"}),
    ],
    ids=["failed", "wrong-hostname", "wrong-action"],
)
async def test_turnstile_rejections(body, options) -> None:
    verifier = turnstile(lambda request: httpx.Response(200, json=body), **options)
    assert await verifier.verify("token", None) is False


async def test_empty_token_is_rejected_without_a_network_call() -> None:
    calls: list[httpx.Request] = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"success": True})

    assert await turnstile(handler).verify("", None) is False
    assert calls == []


@pytest.mark.parametrize("failure", ["http-500", "timeout", "not-json"])
async def test_turnstile_outage_fails_closed(failure) -> None:
    from app.integrations.captcha.client import CaptchaUnavailableError

    def handler(request):
        if failure == "timeout":
            raise httpx.ConnectTimeout("timed out", request=request)
        if failure == "http-500":
            return httpx.Response(500)
        return httpx.Response(200, content=b"<html>")

    with pytest.raises(CaptchaUnavailableError):
        await turnstile(handler).verify("token", None)


# ---- configuration: no secret defaults, health needs nothing --------------------------


def test_application_secrets_have_no_defaults(monkeypatch) -> None:
    for name in (
        "CV_ENCRYPTION_KEY",
        "SUBMISSION_TOKEN_SECRET",
        "OTP_SECRET",
        "TURNSTILE_SECRET_KEY",
        "CV_STORAGE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.cv_encryption_key is None
    assert settings.submission_token_secret is None
    assert settings.otp_secret is None
    assert settings.turnstile_secret_key is None
    assert settings.cv_storage_dir is None
    assert settings.clamav_timeout_seconds <= 10


async def test_health_does_not_need_scanner_captcha_storage_or_email() -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app(
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none",
            clamav_host="127.0.0.1",
            clamav_port=1,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
