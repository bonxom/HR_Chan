import pytest
from sqlalchemy import text

from app.cli import DEV_ACCOUNTS, DEV_SEED_PASSWORD, seed_dev_accounts
from app.core.config import Settings
from app.modules.accounts.rules import AccountStatus, AccountType
from app.modules.accounts.service import create_account
from app.modules.auth.passwords import verify_password

pytestmark = pytest.mark.database

REAL_EMAIL = "real.person@sis.hust.edu.vn"


def seed_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"dev_seed_enabled": True})


async def account_count(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(text("SELECT count(*) FROM accounts")) or 0)


async def test_refuses_to_seed_without_the_development_gate(
    clean_database, session_factory, settings
) -> None:
    code, payload = await seed_dev_accounts(session_factory, settings)
    assert code == 1
    assert payload["code"] == "dev_seed_disabled"
    assert await account_count(session_factory) == 0


async def test_seeds_active_personas_with_the_development_password(
    clean_database, session_factory, settings
) -> None:
    code, payload = await seed_dev_accounts(session_factory, seed_settings(settings))
    assert code == 0
    assert payload["status"] == "seeded"
    assert len(payload["accounts"]) == len(DEV_ACCOUNTS)

    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT email, full_name, account_type, roles, status, password_hash "
                    "FROM accounts ORDER BY email"
                )
            )
        ).all()

    assert len(rows) == len(DEV_ACCOUNTS)
    expected = {
        email: (name, account_type, list(roles))
        for email, name, account_type, roles in DEV_ACCOUNTS
    }
    for row in rows:
        name, account_type, roles = expected[row.email]
        assert row.full_name == name
        assert row.account_type == account_type.value
        assert row.roles == roles
        assert row.status == AccountStatus.ACTIVE.value
        assert verify_password(DEV_SEED_PASSWORD, row.password_hash)


async def test_reseed_restores_modified_fixtures(clean_database, session_factory, settings) -> None:
    enabled = seed_settings(settings)
    await seed_dev_accounts(session_factory, enabled)

    async with session_factory() as session:
        original_id = await session.scalar(
            text("SELECT id FROM accounts WHERE email = 'dev.hr@sis.hust.edu.vn'")
        )
        await session.execute(
            text(
                "UPDATE accounts SET status = 'LOCKED', roles = ARRAY['PROBATION']::text[],"
                " password_hash = NULL WHERE email = 'dev.hr@sis.hust.edu.vn'"
            )
        )
        await session.commit()

    code, _payload = await seed_dev_accounts(session_factory, enabled)
    assert code == 0

    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, status, roles, password_hash FROM accounts "
                    "WHERE email = 'dev.hr@sis.hust.edu.vn'"
                )
            )
        ).one()

    assert row.id == original_id
    assert row.status == AccountStatus.ACTIVE.value
    assert row.roles == ["HR"]
    assert verify_password(DEV_SEED_PASSWORD, row.password_hash)
    assert await account_count(session_factory) == len(DEV_ACCOUNTS)


async def test_leaves_unrelated_accounts_untouched(
    clean_database, session_factory, settings
) -> None:
    async with session_factory() as session:
        created = await create_account(
            session,
            actor_id=None,
            full_name="Real Person",
            email=REAL_EMAIL,
            account_type=AccountType.EMPLOYEE,
            roles=["INTERVIEWER"],
            settings=settings,
            email_client=None,
        )
    assert not hasattr(created, "status_code")

    await seed_dev_accounts(session_factory, seed_settings(settings))

    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT account_type, roles, status, password_hash FROM accounts"
                    " WHERE email = :email"
                ),
                {"email": REAL_EMAIL},
            )
        ).one()

    assert row.account_type == AccountType.EMPLOYEE.value
    assert row.roles == ["INTERVIEWER"]
    assert row.status == AccountStatus.PENDING_SETUP.value
    assert row.password_hash is None


async def test_reports_missing_auth_secrets_after_seeding(
    clean_database, session_factory, settings
) -> None:
    unconfigured = settings.model_copy(
        update={"dev_seed_enabled": True, "jwt_secret": None, "limiter_secret": None}
    )
    code, payload = await seed_dev_accounts(session_factory, unconfigured)
    assert code == 0
    warnings = payload["warnings"]
    assert any("JWT_SECRET" in warning for warning in warnings)
    assert any("LIMITER_SECRET" in warning for warning in warnings)
    assert "restart the API" in payload["next"]


async def test_demo_reference_data_is_idempotent(clean_database, session_factory, settings):
    await seed_dev_accounts(session_factory, seed_settings(settings))
    await seed_dev_accounts(session_factory, seed_settings(settings))
    async with session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT count(*) FROM departments WHERE name='Demo Recruitment'")
            )
            == 1
        )
        assert (
            await session.scalar(
                text("SELECT count(*) FROM holidays WHERE holiday_date='2027-01-01'")
            )
            == 1
        )
        roles = (
            (
                await session.execute(
                    text(
                        "SELECT roles FROM accounts WHERE email IN "
                        "('dev.hr@sis.hust.edu.vn','dev.interviewer@sis.hust.edu.vn',"
                        "'dev.manager@sis.hust.edu.vn')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(roles) == [["DEPT_MANAGER"], ["HR"], ["INTERVIEWER"]]
