"""Shared fixtures for unit, integration, and database tests."""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.exceptions import Failure
from app.integrations.email.client import EmailMessage
from app.main import create_app
from app.modules.accounts import service as account_service
from app.modules.accounts.rules import AccountType

TEST_JWT_SECRET = "test-jwt-signing-secret-0123456789abcdef"
TEST_LIMITER_SECRET = "test-limiter-hmac-secret-0123456789ab"
TEST_OUTBOX_KEY = "test-outbox-encryption-key-0123456789abcdef"

AUTH_TABLES = (
    "audit_events",
    "auth_rate_limits",
    "auth_password_links",
    "auth_refresh_tokens",
    "auth_sessions",
    "accounts",
)

TEST_ORIGIN = "http://localhost:5173"


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated migrated test database")
    if url == str(Settings(_env_file=None).database_url):
        raise RuntimeError("TEST_DATABASE_URL must not point to the application database")
    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _test_database_url()


@pytest.fixture(scope="session")
async def db_engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def clean_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Remove data owned by the preceding test from the dedicated test database.

    Email templates reference accounts, so the cleanup's TRUNCATE ... CASCADE empties
    them; they are seeded again (idempotently) before each database test because every
    account email now goes through the outbox.
    """
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as seed:
        # Account cleanup cascades to settings through updated_by, including seed rows.
        await seed.execute(
            text(
                "INSERT INTO system_settings"
                " (key,value,value_json,default_value,min_value,max_value) VALUES"
                ' (\'working_hours\',NULL,\'{"start":"08:00","end":"17:30"}\',NULL,NULL,NULL),'
                " ('hr_review_days',5,NULL,5,1,10),"
                " ('response_deadline_days',2,NULL,2,1,5),"
                " ('talent_pool_months',12,NULL,12,1,24),"
                " ('max_reschedule_requests',2,NULL,2,0,5),"
                " ('reschedule_handle_days',1,NULL,1,1,3)"
                " ON CONFLICT (key) DO NOTHING"
            )
        )
        await seed_email_templates(seed)
        await seed.commit()
    yield
    async with session_factory() as cleanup:
        await cleanup.execute(text(f"TRUNCATE TABLE {', '.join(AUTH_TABLES)} CASCADE"))
        await cleanup.commit()


@pytest.fixture
async def db_session(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
def settings(test_database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=test_database_url,
        cors_origins=[TEST_ORIGIN],
        trusted_origins=[TEST_ORIGIN],
        frontend_url=TEST_ORIGIN,
        jwt_secret=TEST_JWT_SECRET,
        limiter_secret=TEST_LIMITER_SECRET,
        cookie_secure=False,
        smtp_host=None,
        outbox_encryption_key=TEST_OUTBOX_KEY,
    )


class RecordingEmailClient:
    """Email service stand-in fed by the real outbox worker; never contacts SMTP.

    Account emails are queued in the outbox (task 5). ``drain()`` runs the real worker
    once (``deliver_due_batch``) with this object as the email service, so ``messages``
    only holds what the worker actually delivered. ``failing`` makes the next sends fail
    the way an SMTP outage would (the worker records a temporary error and retries
    after five minutes).
    """

    def __init__(self, session_factory=None, settings: Settings | None = None) -> None:
        self.messages: list[EmailMessage] = []
        self.failing = False
        self._session_factory = session_factory
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        if self.failing:
            raise RuntimeError("SMTP is unavailable")
        self.messages.append(message)

    async def drain(self) -> list[EmailMessage]:
        from datetime import UTC, datetime, timedelta

        from app.modules.notifications.worker import deliver_due_batch

        assert self._session_factory is not None and self._settings is not None
        before = len(self.messages)
        await deliver_due_batch(
            self._session_factory,
            self,
            self._settings,
            datetime.now(UTC) + timedelta(seconds=1),
        )
        return self.messages[before:]

    @property
    def last_token(self) -> str:
        return self.messages[-1].text_body.split("#token=")[1].split()[0]


@pytest.fixture
def email_outbox(session_factory, settings) -> RecordingEmailClient:
    return RecordingEmailClient(session_factory, settings)


EMPLOYEE_PASSWORD = "employee-password-value"
ADMIN_PASSWORD = "administrator-password-value"
EMPLOYEE_EMAIL = "employee@sis.hust.edu.vn"
ADMIN_EMAIL = "admin@sis.hust.edu.vn"


async def _create_pending(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    outbox: RecordingEmailClient,
    *,
    email: str,
    account_type: AccountType = AccountType.EMPLOYEE,
    roles: list[str] | None = None,
):
    async with session_factory() as session:
        if account_type is AccountType.ADMIN:
            result = await account_service.bootstrap_admin(
                session,
                full_name="Test Administrator",
                email=email,
                settings=settings,
                email_client=outbox,
            )
        else:
            result = await account_service.create_account(
                session,
                actor_id=None,
                full_name="Test Employee",
                email=email,
                account_type=account_type,
                roles=roles if roles is not None else ["HR"],
                settings=settings,
                email_client=outbox,
            )
    assert isinstance(result, account_service.AccountDeliveryResult), result
    assert result.email_delivery == "queued"
    # Thư đã xếp hàng: chạy worker thật một lượt để lấy liên kết đặt mật khẩu.
    await outbox.drain()
    return result.account, outbox.last_token


async def _create_active(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    outbox: RecordingEmailClient,
    *,
    email: str,
    password: str,
    account_type: AccountType = AccountType.EMPLOYEE,
    roles: list[str] | None = None,
):
    account, token = await _create_pending(
        session_factory, settings, outbox, email=email, account_type=account_type, roles=roles
    )
    async with session_factory() as session:
        completed = await account_service.complete_password_link(
            session, token=token, new_password=password, settings=settings
        )
    assert not isinstance(completed, Failure), completed
    return completed


@pytest.fixture
async def pending_account_factory(clean_database, session_factory, settings, email_outbox):
    async def make(
        email: str = "pending@sis.hust.edu.vn",
        account_type: AccountType = AccountType.EMPLOYEE,
        roles: list[str] | None = None,
    ):
        account, _token = await _create_pending(
            session_factory,
            settings,
            email_outbox,
            email=email,
            account_type=account_type,
            roles=roles,
        )
        return account

    return make


@pytest.fixture
async def active_account_factory(clean_database, session_factory, settings, email_outbox):
    async def make(email: str, roles: list[str], password: str = EMPLOYEE_PASSWORD):
        return await _create_active(
            session_factory, settings, email_outbox, email=email, password=password, roles=roles
        )

    return make


@pytest.fixture
async def employee_account(clean_database, session_factory, settings, email_outbox):
    return await _create_active(
        session_factory,
        settings,
        email_outbox,
        email=EMPLOYEE_EMAIL,
        password=EMPLOYEE_PASSWORD,
    )


@pytest.fixture
async def admin_account(clean_database, session_factory, settings, email_outbox):
    return await _create_active(
        session_factory,
        settings,
        email_outbox,
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        account_type=AccountType.ADMIN,
        roles=[],
    )


@pytest.fixture
async def app_client(settings, email_outbox, clean_database) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, email_client=email_outbox)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
