import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.database

INSERT_ACCOUNT = text(
    """
    INSERT INTO accounts (id, full_name, email, account_type, roles, status, password_hash)
    VALUES (
        :id, :full_name, :email, CAST(:account_type AS account_type),
        CAST(:roles AS text[]), CAST(:status AS account_status), :password_hash
    )
    """
)


def account_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "full_name": "Test Employee",
        "email": f"user-{uuid.uuid4().hex[:8]}@sis.hust.edu.vn",
        "account_type": "EMPLOYEE",
        "roles": ["HR"],
        "status": "PENDING_SETUP",
        "password_hash": None,
    }
    values.update(overrides)
    return values


async def insert_account(session, **overrides: object) -> None:
    await session.execute(INSERT_ACCOUNT, account_values(**overrides))


async def expect_integrity_error(session, **overrides: object) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await insert_account(session, **overrides)


async def test_creates_the_six_specification_tables(db_session) -> None:
    rows = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(:names) ORDER BY table_name"
        ),
        {
            "names": [
                "accounts",
                "audit_events",
                "auth_password_links",
                "auth_rate_limits",
                "auth_refresh_tokens",
                "auth_sessions",
            ]
        },
    )
    assert [row.table_name for row in rows] == [
        "accounts",
        "audit_events",
        "auth_password_links",
        "auth_rate_limits",
        "auth_refresh_tokens",
        "auth_sessions",
    ]


async def test_accepts_valid_employee_and_admin_rows(db_session) -> None:
    await insert_account(db_session, roles=["HR", "INTERVIEWER"])
    await insert_account(db_session, roles=["PROBATION"])
    await insert_account(db_session, account_type="ADMIN", roles=[], email="admin@sis.hust.edu.vn")
    await db_session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"roles": []},
        {"roles": ["PROBATION", "HR"]},
        {"roles": ["HR", "HR"]},
        {"roles": ["CEO"]},
        {"account_type": "ADMIN", "roles": ["HR"]},
        {"roles": ["HR", None]},
        {"status": "ACTIVE", "password_hash": None},
    ],
)
async def test_storage_rejects_invalid_account_rows(db_session, overrides) -> None:
    await expect_integrity_error(db_session, **overrides)


async def test_storage_rejects_unknown_enum_values(db_session) -> None:
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await insert_account(db_session, status="DELETED")


async def test_email_uniqueness_is_case_insensitive_after_normalization(db_session) -> None:
    await insert_account(db_session, email="duplicate@sis.hust.edu.vn")
    await expect_integrity_error(db_session, email="duplicate@sis.hust.edu.vn")


def test_account_model_documents_the_department_deferral() -> None:
    from app.modules.accounts.models import Account

    assert "Departments and department-scoped authorization are intentionally deferred" in (
        Account.__doc__ or ""
    )
