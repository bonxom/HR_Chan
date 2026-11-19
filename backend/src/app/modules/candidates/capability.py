"""Signed capability proving the right to use one CV submission.

A numeric submission ID is not a permission. The upload returns a token signed with
``SUBMISSION_TOKEN_SECRET`` (dedicated to this purpose, never the account JWT secret)
that binds the submission ID, its random storage key and its expiry (24 h). The token
is only sent in JSON bodies, never in URLs, and is never logged.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime

_DOMAIN = "hr-chan-submission-capability-v1"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signature(secret: bytes, submission_id: int, storage_key: str, expires: int, nonce: str):
    message = f"{_DOMAIN}|{submission_id}|{storage_key}|{expires}|{nonce}".encode()
    return _b64(hmac.new(secret, message, hashlib.sha256).digest())


def issue(secret: bytes, *, submission_id: int, storage_key: str, expires_at: datetime) -> str:
    expires = int(expires_at.timestamp())
    nonce = secrets.token_urlsafe(12)
    return f"{expires}.{nonce}.{_signature(secret, submission_id, storage_key, expires, nonce)}"


def verify(
    secret: bytes,
    token: str | None,
    *,
    submission_id: int,
    storage_key: str,
    expires_at: datetime,
    now: datetime,
) -> bool:
    if not token or len(token) > 200:
        return False
    parts = token.split(".")
    if len(parts) != 3 or not parts[0].isdigit():
        return False
    expires_text, nonce, signature = parts
    expected = _signature(secret, submission_id, storage_key, int(expires_text), nonce)
    if not hmac.compare_digest(signature, expected):
        return False
    # Hạn trong token phải khớp hạn của bản ghi và chưa qua.
    if int(expires_text) != int(expires_at.timestamp()):
        return False
    return now < expires_at
