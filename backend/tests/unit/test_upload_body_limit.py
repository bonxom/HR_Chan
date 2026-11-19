"""Regression: body guard, CAPTCHA total timeout and text-only CV rule."""

import asyncio

import httpx
import pytest

from app.core.body_limit import MAX_BODY_BYTES, UPLOAD_PATH, UploadBodyLimitMiddleware
from app.integrations.captcha.client import CaptchaUnavailableError, TurnstileVerifier


async def _inner(scope, receive, send):
    received = 0
    while True:
        message = await receive()
        received += len(message.get("body", b""))
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(received).encode()})


async def _call(path: str, chunks: list[bytes], headers=(), method="POST"):
    app = UploadBodyLimitMiddleware(_inner)
    queue = [
        {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1}
        for i, c in enumerate(chunks)
    ]
    sent: list[dict] = []

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": method, "path": path, "headers": list(headers)}
    await app(scope, receive, send)
    return sent[0]["status"], sent[-1].get("body", b"")


async def test_streamed_oversize_body_without_content_length_is_413() -> None:
    chunk = b"x" * 65536
    status, _ = await _call(UPLOAD_PATH, [chunk] * (MAX_BODY_BYTES // 65536 + 2))
    assert status == 413


async def test_declared_oversize_is_413_before_reading() -> None:
    status, _ = await _call(UPLOAD_PATH, [b""], [(b"content-length", b"99999999")])
    assert status == 413


async def test_valid_upload_and_other_routes_pass_through() -> None:
    assert await _call(UPLOAD_PATH, [b"a" * 1000]) == (200, b"1000")
    big = [b"x" * 65536] * (MAX_BODY_BYTES // 65536 + 2)
    assert (await _call("/api/v1/auth/login", big))[0] == 200
    assert (await _call(UPLOAD_PATH, [b"abc"], method="GET"))[0] == 200


async def test_captcha_timeout_covers_whole_call() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.15)
        return httpx.Response(200, json={"success": True})

    verifier = TurnstileVerifier("secret", timeout=0.01, transport=httpx.MockTransport(slow))
    with pytest.raises(CaptchaUnavailableError):
        await verifier.verify("token", None)


def test_short_but_real_text_is_accepted() -> None:
    from app.modules.candidates.documents import PDF_MIME, _check_text

    assert _check_text("Nguyen An", PDF_MIME).text_length == 9
