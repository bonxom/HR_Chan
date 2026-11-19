"""ASGI body guard for the public CV upload, applied before the multipart parser.

Only ``POST /api/v1/candidates/submissions`` is limited (CV 5 MiB + 64 KiB of metadata).
The body is buffered up to the limit; a larger body, declared or streamed without
``Content-Length``, is answered with 413 without being parsed or logged.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.modules.candidates.documents import MAX_CV_BYTES

UPLOAD_PATH = "/api/v1/candidates/submissions"
METADATA_ALLOWANCE = 64 * 1024
MAX_BODY_BYTES = MAX_CV_BYTES + METADATA_ALLOWANCE
_BODY = json.dumps(
    {"error": {"code": "cv_too_large", "message": "Tệp CV vượt quá dung lượng tối đa 5 MB."}}
).encode()


class UploadBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != UPLOAD_PATH
        ):
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await self._reject(send)
            return
        buffered: list[Message] = []
        size = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                await self._reject(send)
                return
            if not message.get("more_body", False):
                break
        replay = iter(buffered)

        async def replaying_receive() -> Message:
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        await self.app(scope, replaying_receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_BODY)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _BODY})
