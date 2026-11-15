"""Opaque keyset pagination cursors shared by list endpoints."""

import base64
import json
import uuid
from datetime import datetime


class CursorError(ValueError):
    """Raised when a client supplies an opaque cursor that cannot be decoded."""


def encode_cursor(timestamp: datetime, identifier: uuid.UUID) -> str:
    payload = json.dumps(
        {"ts": timestamp.isoformat(), "id": str(identifier)}, separators=(",", ":")
    )
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        return datetime.fromisoformat(payload["ts"]), uuid.UUID(payload["id"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise CursorError("Invalid pagination cursor") from exc
