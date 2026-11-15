"""Browser credential cookies and signed double-submit CSRF protection."""

import hashlib
import hmac
import secrets

from fastapi import Request, Response
from starlette.responses import Response as StarletteResponse

from app.core.config import Settings
from app.core.exceptions import AppError

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
REFRESH_COOKIE_NAME = "refresh_token"
CREDENTIAL_COOKIE_PATH = "/api/v1/auth"


def _sign(token: str, settings: Settings) -> str:
    return hmac.new(settings.require_jwt_secret(), token.encode(), hashlib.sha256).hexdigest()


def create_csrf_token(settings: Settings) -> tuple[str, str]:
    """Return the cookie value and the signed proof the browser submits."""
    token = secrets.token_urlsafe(32)
    return token, f"{token}.{_sign(token, settings)}"


def verify_csrf_proof(proof: str, cookie_value: str | None, settings: Settings) -> bool:
    if not cookie_value:
        return False
    token, separator, signature = proof.partition(".")
    if not separator or not token or not signature:
        return False
    if not hmac.compare_digest(token, cookie_value):
        return False
    return hmac.compare_digest(signature, _sign(token, settings))


def _cookie_options(settings: Settings) -> dict[str, object]:
    return {
        "path": CREDENTIAL_COOKIE_PATH,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
    }


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(CSRF_COOKIE_NAME, token, **_cookie_options(settings))


def set_refresh_cookie(response: Response, token: str, settings: Settings, max_age: int) -> None:
    response.set_cookie(REFRESH_COOKIE_NAME, token, max_age=max_age, **_cookie_options(settings))


def clear_credential_cookies(response: Response, settings: Settings) -> None:
    options = _cookie_options(settings)
    for name in (REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(name, **options)


def read_csrf_cookie(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE_NAME)


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def require_csrf(request: Request, settings: Settings) -> None:
    proof = request.headers.get(CSRF_HEADER_NAME)
    cookie_value = read_csrf_cookie(request)
    if not proof or not verify_csrf_proof(proof, cookie_value, settings):
        raise AppError("CSRF verification failed", status_code=403, code="csrf_verification_failed")


def require_trusted_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        raise AppError("Trusted origin required", status_code=403, code="untrusted_origin")
    if origin.rstrip("/") not in {
        candidate.rstrip("/") for candidate in settings.browser_origins()
    }:
        raise AppError("Origin is not trusted", status_code=403, code="untrusted_origin")


def no_store(response: StarletteResponse) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
