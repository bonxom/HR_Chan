import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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
    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "An unexpected error occurred"}
            },
        )
