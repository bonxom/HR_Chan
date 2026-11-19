"""Versioned internal envelope stored in ``email_outbox.body`` while a row is PENDING.

Design (approved spec): the schema has one ``body`` column and no mode/secret column, so
a PENDING row holds ``outbox:v1:<mode>:<json>``:

* ``mode`` is ``queued`` (worker delivers) or ``immediate`` (sendNow only; the worker
  never claims it). The mode is part of the fixed prefix so SQL can filter it without
  parsing JSON (a corrupted body must not break the batch query).
* ``redacted``: subject/text/html with every secret replaced by ``REDACTION_MARK``.
* ``meta``: operational data only (``otp_id`` of an immediate OTP mail).
* ``payload``: for queued mail with secrets, the full rendering encrypted with AES-GCM
  (key derived from ``OUTBOX_ENCRYPTION_KEY``). Immediate mail never has a payload: the
  OTP exists only in memory.

When a row becomes SENT/FAILED the envelope is replaced by the redacted text, so no
payload (not even ciphertext) is kept. The envelope is never shown in API/UI.
"""

import base64
import binascii
import json
import os
from dataclasses import dataclass, field
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.modules.notifications.rendering import RenderedEmail

VERSION = 1
QUEUED = "queued"
IMMEDIATE = "immediate"
PREFIX = f"outbox:v{VERSION}:"
QUEUED_PREFIX = f"{PREFIX}{QUEUED}:"
IMMEDIATE_PREFIX = f"{PREFIX}{IMMEDIATE}:"
# Thân thư thay thế khi envelope hỏng: không giữ lại nội dung không kiểm soát được.
UNREADABLE_BODY = "[Nội dung thư không hợp lệ đã được loại bỏ]"
ALLOWED_META = frozenset({"otp_id"})
_NONCE_BYTES = 12
_KDF_INFO = b"hr-chan email outbox payload v1"


class EnvelopeError(ValueError):
    """Body is not a valid envelope or its payload cannot be authenticated."""


@dataclass(frozen=True, repr=False)
class Envelope:
    mode: str
    redacted: RenderedEmail
    meta: dict[str, Any] = field(default_factory=dict)
    payload: str | None = None

    def __repr__(self) -> str:
        return f"Envelope(mode={self.mode!r})"

    @property
    def otp_id(self) -> int | None:
        value = self.meta.get("otp_id")
        return value if isinstance(value, int) and not isinstance(value, bool) else None


def _derive_key(secret: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_KDF_INFO).derive(secret)


def _aad(mode: str) -> bytes:
    return f"{PREFIX}{mode}".encode()


def _as_dict(rendered: RenderedEmail) -> dict[str, str]:
    return {"subject": rendered.subject, "text": rendered.text_body, "html": rendered.html_body}


def _from_dict(data: Any) -> RenderedEmail:
    if not isinstance(data, dict) or not all(
        isinstance(data.get(key), str) for key in ("subject", "text", "html")
    ):
        raise EnvelopeError("Envelope content is malformed")
    return RenderedEmail(data["subject"], data["text"], data["html"])


def check_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    meta = dict(meta or {})
    unknown = set(meta) - ALLOWED_META
    if unknown:
        raise ValueError("Unsupported immediate metadata key")
    otp_id = meta.get("otp_id")
    if otp_id is not None and (not isinstance(otp_id, int) or isinstance(otp_id, bool)):
        raise ValueError("otp_id must be an integer")
    return meta


def build_envelope(
    mode: str,
    redacted: RenderedEmail,
    *,
    meta: dict[str, Any] | None = None,
    secret: RenderedEmail | None = None,
    key: bytes | None = None,
) -> str:
    if mode not in (QUEUED, IMMEDIATE):
        raise ValueError("Unknown envelope mode")
    payload = None
    if secret is not None:
        if mode != QUEUED or key is None:
            raise ValueError("Only queued mail may carry an encrypted payload")
        nonce = os.urandom(_NONCE_BYTES)
        plaintext = json.dumps(_as_dict(secret), ensure_ascii=False).encode()
        ciphertext = AESGCM(_derive_key(key)).encrypt(nonce, plaintext, _aad(mode))
        payload = base64.b64encode(nonce + ciphertext).decode("ascii")
    document = {
        "v": VERSION,
        "redacted": _as_dict(redacted),
        "meta": check_meta(meta),
        # Payload để cuối envelope (chỉ là ciphertext base64).
        "payload": payload,
    }
    return f"{PREFIX}{mode}:" + json.dumps(document, ensure_ascii=False)


def parse_envelope(body: str) -> Envelope:
    for mode in (QUEUED, IMMEDIATE):
        prefix = f"{PREFIX}{mode}:"
        if body.startswith(prefix):
            raw = body[len(prefix) :]
            break
    else:
        raise EnvelopeError("Body is not an outbox envelope")
    try:
        document = json.loads(raw)
    except ValueError:
        raise EnvelopeError("Envelope is not valid JSON") from None
    if not isinstance(document, dict) or document.get("v") != VERSION:
        raise EnvelopeError("Unsupported envelope version")
    meta = document.get("meta")
    payload = document.get("payload")
    if not isinstance(meta, dict) or (payload is not None and not isinstance(payload, str)):
        raise EnvelopeError("Envelope fields are malformed")
    if payload is not None and mode != QUEUED:
        raise EnvelopeError("Immediate mail must not carry a payload")
    try:
        meta = check_meta(meta)
    except ValueError:
        raise EnvelopeError("Envelope metadata is malformed") from None
    redacted = _from_dict(document.get("redacted"))
    return Envelope(mode=mode, redacted=redacted, meta=meta, payload=payload)


def decrypt_payload(envelope: Envelope, key: bytes) -> RenderedEmail:
    if envelope.payload is None:
        raise EnvelopeError("Envelope has no payload")
    try:
        blob = base64.b64decode(envelope.payload, validate=True)
        if len(blob) <= _NONCE_BYTES:
            raise EnvelopeError("Payload is truncated")
        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        plaintext = AESGCM(_derive_key(key)).decrypt(nonce, ciphertext, _aad(envelope.mode))
        return _from_dict(json.loads(plaintext))
    except EnvelopeError:
        raise
    except (InvalidTag, binascii.Error, ValueError):
        # Sai khóa hoặc dữ liệu bị sửa: không bao giờ gửi nội dung giải mã sai.
        raise EnvelopeError("Payload cannot be authenticated") from None
