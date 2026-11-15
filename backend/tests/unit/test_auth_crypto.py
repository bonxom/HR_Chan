import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.modules.accounts.rules import RuleViolation, validate_password
from app.modules.auth.passwords import (
    hash_password,
    hash_password_async,
    verify_dummy_password,
    verify_password,
    verify_password_async,
)
from app.modules.auth.tokens import (
    JWT_ALGORITHM,
    TokenError,
    generate_opaque_token,
    hash_opaque_token,
    issue_access_token,
    limiter_identifier,
    verify_access_token,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
ACCOUNT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
SESSION_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def payload_for(settings: Settings, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sub": str(ACCOUNT_ID),
        "sid": str(SESSION_ID),
        "ver": 0,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=5)).timestamp()),
    }
    payload.update(overrides)
    return payload


def test_password_characters_are_preserved() -> None:
    password = "  Mật khẩu có dấu cách & ký tự  "
    encoded = hash_password(password)
    assert encoded.startswith("$argon2id$")
    assert verify_password(password, encoded)
    assert not verify_password(password.strip(), encoded)
    assert not verify_password("wrong password", encoded)


def test_hashes_are_salted_and_distinct() -> None:
    first = hash_password("same-password-value")
    second = hash_password("same-password-value")
    assert first != second
    assert verify_password("same-password-value", first)
    assert verify_password("same-password-value", second)


def test_verification_rejects_missing_or_malformed_hashes() -> None:
    assert not verify_password("anything", None)
    assert not verify_password("anything", "not-a-hash")


@pytest.mark.parametrize("length", [8, 128])
def test_boundary_length_passwords_round_trip(length: int) -> None:
    password = "p" * length
    assert validate_password(password) == password
    assert verify_password(password, hash_password(password))


@pytest.mark.parametrize("length", [7, 129])
def test_out_of_bound_lengths_are_rejected_by_validation(length: int) -> None:
    with pytest.raises(RuleViolation):
        validate_password("p" * length)


async def test_password_helpers_offload_to_threads() -> None:
    encoded = await hash_password_async("threaded-password")
    assert await verify_password_async("threaded-password", encoded)
    assert not await verify_password_async("threaded-password", None)
    assert await verify_dummy_password("threaded-password") is False


def test_issues_and_verifies_access_claims(settings: Settings) -> None:
    token = issue_access_token(ACCOUNT_ID, SESSION_ID, 3, NOW, settings)
    claims = verify_access_token(token, NOW + timedelta(minutes=4), settings)
    assert claims.account_id == ACCOUNT_ID
    assert claims.session_id == SESSION_ID
    assert claims.credential_version == 3
    assert claims.issued_at == NOW


def test_rejects_token_signed_with_another_secret(settings: Settings) -> None:
    token = jwt.encode(
        payload_for(settings), "another-secret-value-0123456789abcdef", algorithm="HS256"
    )
    with pytest.raises(TokenError):
        verify_access_token(token, NOW, settings)


def test_rejects_algorithm_not_configured(settings: Settings) -> None:
    token = jwt.encode(payload_for(settings), "x" * 40, algorithm="HS512")
    with pytest.raises(TokenError):
        verify_access_token(token, NOW, settings)
    unsigned = jwt.encode(payload_for(settings), key="", algorithm="none")
    with pytest.raises(TokenError):
        verify_access_token(unsigned, NOW, settings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-audience"},
        {"iss": "another-issuer"},
        {"sub": "not-a-uuid"},
        {"sid": "not-a-uuid"},
        {"ver": "1"},
        {"ver": -1},
        {"ver": True},
        {"exp": int((NOW - timedelta(seconds=1)).timestamp())},
        {"iat": int((NOW + timedelta(minutes=1)).timestamp())},
    ],
)
def test_rejects_untrusted_claim_values(settings: Settings, overrides: dict[str, object]) -> None:
    token = jwt.encode(
        payload_for(settings, **overrides),
        settings.jwt_secret.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(TokenError):
        verify_access_token(token, NOW, settings)


@pytest.mark.parametrize("missing", ["sub", "sid", "ver", "iss", "aud", "iat", "exp"])
def test_rejects_missing_required_claims(settings: Settings, missing: str) -> None:
    payload = payload_for(settings)
    payload.pop(missing)
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    with pytest.raises(TokenError):
        verify_access_token(token, NOW, settings)


def test_rejects_malformed_token_text(settings: Settings) -> None:
    with pytest.raises(TokenError):
        verify_access_token("not.a.jwt", NOW, settings)


def test_rejects_modified_payload(settings: Settings) -> None:
    token = issue_access_token(ACCOUNT_ID, SESSION_ID, 0, NOW, settings)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload[:-2]}AA.{signature}"
    with pytest.raises(TokenError):
        verify_access_token(tampered, NOW, settings)


def test_opaque_tokens_are_random_and_hashes_are_stable() -> None:
    first = generate_opaque_token()
    second = generate_opaque_token()
    assert first != second
    assert len(first) >= 42
    assert hash_opaque_token(first) == hash_opaque_token(first)
    assert hash_opaque_token(first) != hash_opaque_token(second)
    assert len(hash_opaque_token(first)) == 64


def test_limiter_identifiers_depend_on_namespace_and_secret() -> None:
    secret = b"limiter-secret-value-for-tests-0123456789"
    value = "User@sis.hust.edu.vn"
    identifier = limiter_identifier(secret, "login-account", value)
    assert identifier == limiter_identifier(secret, "login-account", value)
    assert identifier != limiter_identifier(secret, "login-ip", value)
    assert identifier != limiter_identifier(
        b"other-secret-value-0123456789abcdef", "login-account", value
    )
    assert value.lower() not in identifier
