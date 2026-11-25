from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.router import api_router
from app.core.body_limit import UploadBodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.integrations.email.client import EmailClient, build_email_client
from app.integrations.email.service import build_email_service
from app.integrations.factories import (
    build_captcha,
    build_cv_storage,
    build_google_workspace,
    build_scanner,
)


def create_app(
    settings: Settings | None = None,
    email_client: EmailClient | None = None,
    *,
    email_service=None,
    storage=None,
    scanner=None,
    captcha=None,
    google_workspace=None,
) -> FastAPI:
    """Build the API. The keyword adapters are injection points used by tests only."""
    config = settings or get_settings()
    if "*" in config.cors_origins:
        raise ValueError("CORS origins must be explicit when credentialed requests are enabled")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level)
        engine = create_async_engine(str(config.database_url), pool_pre_ping=True)
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = config
        app.state.email_client = email_client or build_email_client(config)
        # Adapter chỉ được dựng, không kết nối dịch vụ ngoài lúc khởi động.
        app.state.email_service = email_service or build_email_service(config)
        app.state.cv_storage = storage if storage is not None else build_cv_storage(config)
        app.state.scanner = scanner if scanner is not None else build_scanner(config)
        app.state.captcha = captcha if captcha is not None else build_captcha(config)
        app.state.google_workspace = (
            google_workspace if google_workspace is not None else build_google_workspace()
        )
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    # Thêm trước CORS để phản hồi 413 vẫn có header CORS.
    app.add_middleware(UploadBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    from app.modules.applications.review_router import router as review_router

    app.include_router(review_router, prefix="/api")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
