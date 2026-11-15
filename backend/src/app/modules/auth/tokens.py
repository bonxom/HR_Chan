"""Access-token signing, strict verification, and opaque secret helpers."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from app.core.config import Settings, get_settings

JWT_ALGORITHM = "HS256"
OPAQUE_TOKEN_BYTES = 32
REQUIRED_CLAIMS = ("sub", "sid", "ver", "iss", "aud", "iat", "exp")


class TokenError(Exception):
    """Raised when a token is malformed, expired, or otherwise unacceptable."""


@dataclass(frozen=True)
class AccessClaims:
    account_id: uuid.UUID
    session_id: uuid.UUID
    credential_version: int
    issued_at: datetime
    expires_at: datetime


def issue_access_token(
    account_id: uuid.UUID,
    session_id: uuid.UUID,
    version: int,
    now: datetime,
    settings: Settings | None = None,
) -> str:
    config = settings or get_settings()
    expires_at = now + timedelta(seconds=config.access_token_ttl_seconds)
    payload = {
        "sub": str(account_id),
        "sid": str(session_id),
        "ver": version,
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, config.require_jwt_secret(), algorithm=JWT_ALGORITHM)


def verify_access_token(
    token: str, now: datetime, settings: Settings | None = None
) -> AccessClaims:
    config = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            config.require_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            audience=config.jwt_audience,
            issuer=config.jwt_issuer,
            # Lifetime is checked against the injected clock, not the process clock.
            options={
                "require": list(REQUIRED_CLAIMS),
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
            leeway=timedelta(seconds=0),
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid access token") from exc

    if set(REQUIRED_CLAIMS) - payload.keys():
        raise TokenError("Missing claims")

    version = payload["ver"]
    issued_at_value = payload["iat"]
    expires_at_value = payload["exp"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise TokenError("Invalid credential version")
    if not isinstance(issued_at_value, int) or isinstance(issued_at_value, bool):
        raise TokenError("Invalid issuance time")
    if not isinstance(expires_at_value, int) or isinstance(expires_at_value, bool):
        raise TokenError("Invalid expiration time")
    now_timestamp = int(now.timestamp())
    if issued_at_value > now_timestamp:
        raise TokenError("Token issued in the future")
    if now_timestamp >= expires_at_value:
        raise TokenError("Access token expired")

    try:
        account_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (ValueError, AttributeError, TypeError) as exc:
        raise TokenError("Invalid subject or session identifier") from exc

    return AccessClaims(
        account_id=account_id,
        session_id=session_id,
        credential_version=version,
        issued_at=datetime.fromtimestamp(issued_at_value, tz=now.tzinfo),
        expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=now.tzinfo),
    )


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(OPAQUE_TOKEN_BYTES)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def limiter_identifier(secret: bytes, namespace: str, value: str) -> str:
    digest = hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"{namespace}:{digest}"
