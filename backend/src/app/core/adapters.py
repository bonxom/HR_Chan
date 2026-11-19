"""Request access to injected external adapters (email, CV store, scanner, CAPTCHA).

``create_app`` stores them on ``app.state``; production builds them from Settings and
tests inject controlled fakes. A missing adapter (feature not configured) answers 503
when the feature is used, never at startup, so ``/health`` and OpenAPI stay available.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import AppError

UNAVAILABLE_MESSAGE = "Chức năng nộp hồ sơ tạm thời chưa sẵn sàng. Vui lòng thử lại sau."


def _state(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise AppError(UNAVAILABLE_MESSAGE, status_code=503, code="application_unavailable")
    return value


def get_email_service(request: Request):
    return _state(request, "email_service")


def get_cv_storage(request: Request):
    return _state(request, "cv_storage")


def get_scanner(request: Request):
    return _state(request, "scanner")


def get_captcha(request: Request):
    value = getattr(request.app.state, "captcha", None)
    if value is None:
        raise AppError(
            "Không kiểm tra được CAPTCHA lúc này. Vui lòng thử lại sau.",
            status_code=503,
            code="captcha_unavailable",
        )
    return value


def field_error(field: str, message: str) -> RequestValidationError:
    """422 in FastAPI's default shape, with the field last in ``loc`` and a Vietnamese msg.

    The submitted value is never echoed back.
    """
    return field_errors({field: message})


def field_errors(errors: dict[str, str]) -> RequestValidationError:
    return RequestValidationError(
        [
            {"type": "value_error", "loc": ("body", field), "msg": message, "input": None}
            for field, message in errors.items()
        ]
    )
