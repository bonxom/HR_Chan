"""OTP generation and keyed hashing (NFR22: stored only as a hash).

The code is 6 random digits from ``secrets``. The stored value is an HMAC-SHA256 keyed
with ``OTP_SECRET`` over a domain-separated message that binds the code to its purpose,
email and (for APPLY) submission and job, so a code is useless for another binding even
if the hash leaked. Comparison is constant-time.
"""

import hashlib
import hmac
import secrets

CODE_DIGITS = 6
_DOMAIN = "hr-chan-otp-v1"


def generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(
    secret: bytes,
    *,
    code: str,
    purpose: str,
    email: str,
    submission_id: int | None = None,
    job_id: int | None = None,
) -> str:
    message = "|".join(
        (
            _DOMAIN,
            purpose,
            email.strip().lower(),
            str(submission_id or ""),
            str(job_id or ""),
            code,
        )
    )
    return "v1$" + hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()


def verify_code(secret: bytes, stored_hash: str, **binding) -> bool:
    return hmac.compare_digest(stored_hash, hash_code(secret, **binding))


def is_well_formed(code: str | None) -> bool:
    return bool(code) and len(code) == CODE_DIGITS and code.isascii() and code.isdigit()
