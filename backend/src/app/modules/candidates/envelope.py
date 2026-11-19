"""Plaintext layout of a stored submission (encrypted as a whole by the CV store).

The unverified contact typed at upload (full name, email, phone) travels inside the same
encrypted object as the CV, so it is never written in clear to the database and can only
replace a candidate's data after OTP verification. Layout::

    b"HRSUB1" | 4-byte big-endian header length | JSON header | original CV bytes
"""

import json
import struct
from dataclasses import dataclass

MAGIC = b"HRSUB1"


class EnvelopeFormatError(ValueError):
    """Stored object is not a submission envelope."""


@dataclass(frozen=True, repr=False)
class PendingContact:
    full_name: str
    email: str
    phone: str

    def __repr__(self) -> str:
        return "PendingContact(<hidden>)"


def pack(cv: bytes, contact: PendingContact) -> bytes:
    header = json.dumps(
        {"full_name": contact.full_name, "email": contact.email, "phone": contact.phone},
        ensure_ascii=False,
    ).encode()
    return MAGIC + struct.pack(">I", len(header)) + header + cv


def unpack(blob: bytes) -> tuple[bytes, PendingContact]:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 4:
        raise EnvelopeFormatError("Not a submission envelope")
    (size,) = struct.unpack(">I", blob[len(MAGIC) : len(MAGIC) + 4])
    start = len(MAGIC) + 4
    try:
        data = json.loads(blob[start : start + size])
        contact = PendingContact(str(data["full_name"]), str(data["email"]), str(data["phone"]))
    except (ValueError, KeyError, TypeError):
        raise EnvelopeFormatError("Submission envelope header is malformed") from None
    return blob[start + size :], contact
