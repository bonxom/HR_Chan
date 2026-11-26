import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
RESPONSE_PATHS = {"/api/v1/responses/resolve", "/api/v1/responses/submit"}


def response_headers(request):
    if request.url.path in RESPONSE_PATHS:
        return {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    return {}


class AppError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "application_error",
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = headers


@dataclass(frozen=True)
class Failure:
    """Expected service outcome raised as an error only after its transaction commits."""

    status_code: int
    code: str
    message: str
    retry_after: int | None = None

    def to_error(self) -> AppError:
        headers = {"Retry-After": str(self.retry_after)} if self.retry_after is not None else None
        return AppError(self.message, status_code=self.status_code, code=self.code, headers=headers)

    def raise_error(self) -> None:
        raise self.to_error()


def failure(status_code: int, code: str, message: str, retry_after: int | None = None) -> Failure:
    return Failure(status_code=status_code, code=code, message=message, retry_after=retry_after)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path not in RESPONSE_PATHS:
            return await request_validation_exception_handler(request, exc)
        # Input, ctx and arbitrary extra-field names may contain the submitted token.
        fields = {"token", "action", "note", "policy_ver", "consent_snapshot"}
        detail = [
            {
                "type": item["type"],
                "loc": [part for part in item["loc"] if part == "body" or part in fields],
                "msg": item["msg"],
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content={"detail": detail}, headers=response_headers(request)
        )

    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers={**response_headers(request), **(exc.headers or {})},
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        if request.url.path in RESPONSE_PATHS:
            logger.error("Candidate response failed (%s)", type(exc).__name__)
        else:
            logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "An unexpected error occurred"}
            },
            headers=response_headers(request),
        )
