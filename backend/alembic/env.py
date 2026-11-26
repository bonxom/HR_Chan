import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core import response_links as response_link_models  # noqa: F401
from app.core.config import get_settings
from app.core.otp import models as otp_models  # noqa: F401
from app.db.base import Base
from app.modules.accounts import models as account_models  # noqa: F401
from app.modules.applications import models as application_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.candidates import consent_models  # noqa: F401
from app.modules.candidates import models as candidate_models  # noqa: F401
from app.modules.departments import models as department_models  # noqa: F401
from app.modules.interviews import models as interview_models  # noqa: F401
from app.modules.notifications import models as notification_models  # noqa: F401
from app.modules.recruitment import models as recruitment_models  # noqa: F401
from app.modules.settings import models as settings_models  # noqa: F401

# Các import models ở trên đăng ký bảng vào metadata. Nếu thiếu module tuyển dụng,
# autogenerate có thể hiểu nhầm các bảng đang có trong database là cần xóa.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(str(get_settings().database_url), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
