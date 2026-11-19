# Kiểm tra bảng email_templates/email_outbox theo context 02 trên PostgreSQL riêng.
# Trigger required_vars và các CHECK chống header injection được thử bằng SQL thật.
"""Schema of email_templates and email_outbox (plan task 1).

Source: context 02 (``email_templates``, ``email_outbox``, enum ``email_status``,
trigger ``email_templates_vars`` -> ``trg_template_required_vars``) with the approved
mapping of context 00 section 4.11 (``updated_by``/``user_id`` are UUID FKs to accounts).

The trigger rule comes from context 02/BR46: "Mẫu email phải chứa đủ biến bắt buộc",
with variables written ``{ten_bien}`` in the body. Whether a variable that appears only
in the subject satisfies the rule is not fixed by the sources, so it is not asserted.
"""

import uuid

import pytest
from apply_support import (
    INSERT_OUTBOX,
    apply_cleanup,
    build_world,
    insert_application,
    insert_template,
    now_utc,
    outbox_values,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]

TEMPLATE = "TEST_SCHEMA_TEMPLATE"

COLUMNS = {
    "email_templates": {
        "code": ("varchar", False, 50),
        "subject": ("varchar", False, 255),
        "body": ("text", False, None),
        "required_vars": ("_text", False, None),
        "updated_by": ("uuid", True, None),
        "updated_at": ("timestamptz", False, None),
    },
    "email_outbox": {
        "id": ("int8", False, None),
        "template_code": ("varchar", False, 50),
        "to_email": ("citext", False, None),
        "subject": ("varchar", False, 255),
        "body": ("text", False, None),
        "application_id": ("int8", True, None),
        "user_id": ("uuid", True, None),
        "status": ("email_status", False, None),
        "attempts": ("int2", False, None),
        "next_attempt_at": ("timestamptz", False, None),
        "last_error": ("text", True, None),
        "created_at": ("timestamptz", False, None),
        "sent_at": ("timestamptz", True, None),
    },
}

CONSTRAINTS = {
    "email_templates_pkey": ("email_templates", "p"),
    "email_templates_updated_by_fkey": ("email_templates", "f"),
    "email_outbox_pkey": ("email_outbox", "p"),
    "email_outbox_attempts_check": ("email_outbox", "c"),
    "email_outbox_failed_has_error": ("email_outbox", "c"),
    "email_outbox_sent_at_only_sent": ("email_outbox", "c"),
    "email_outbox_sent_complete": ("email_outbox", "c"),
    "email_outbox_subject_no_newline": ("email_outbox", "c"),
    "email_outbox_to_email_check": ("email_outbox", "c"),
    "email_outbox_application_id_fkey": ("email_outbox", "f"),
    "email_outbox_template_code_fkey": ("email_outbox", "f"),
    "email_outbox_user_id_fkey": ("email_outbox", "f"),
}

FK_TARGETS = {
    "email_templates_updated_by_fkey": "accounts",
    "email_outbox_application_id_fkey": "applications",
    "email_outbox_template_code_fkey": "email_templates",
    "email_outbox_user_id_fkey": "accounts",
}

INDEXES = {
    "ix_email_outbox_application": ["(application_id)", "application_id IS NOT NULL"],
    "ix_email_outbox_due": ["(next_attempt_at)", "status = 'PENDING'"],
}


@pytest.fixture
async def template(apply_cleanup, session_factory) -> str:
    async with session_factory() as session:
        await insert_template(
            session,
            TEMPLATE,
            subject="Xin chào {full_name}",
            body="Chào {full_name}, mã của bạn là {otp_code}.",
            required_vars=["full_name", "otp_code"],
        )
        await session.commit()
    return TEMPLATE


async def expect_violation(session_factory, statement, params, constraint: str | None = None):
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as error:
            await session.execute(
                text(statement) if isinstance(statement, str) else statement, params
            )
            await session.commit()
        await session.rollback()
    if constraint is not None:
        assert constraint in str(error.value), str(error.value)
    return error.value


async def expect_ok(session_factory, statement, params):
    async with session_factory() as session:
        result = await session.execute(
            text(statement) if isinstance(statement, str) else statement, params
        )
        value = result.scalar_one_or_none() if result.returns_rows else None
        await session.commit()
    return value


# ---- catalog --------------------------------------------------------------------------


async def test_email_status_enum(db_session) -> None:
    rows = await db_session.scalars(
        text(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid"
            " WHERE t.typname = 'email_status' ORDER BY e.enumsortorder"
        )
    )
    assert list(rows) == ["PENDING", "SENT", "FAILED"]


async def test_email_outbox_exists(db_session) -> None:
    value = await db_session.scalar(text("SELECT to_regclass('public.email_outbox')::text"))
    assert value == "email_outbox"


@pytest.mark.parametrize("table", sorted(COLUMNS))
async def test_columns_types_and_nullability(db_session, table) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT column_name, udt_name, is_nullable, character_maximum_length"
                " FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        )
    ).all()
    actual = {
        row.column_name: (row.udt_name, row.is_nullable == "YES", row.character_maximum_length)
        for row in rows
    }
    assert actual == COLUMNS[table]


async def test_named_constraints_and_fk_targets(db_session) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT c.conname, r.relname, c.contype::text AS contype, t.relname AS target,"
                " c.confdeltype::text AS deltype"
                " FROM pg_constraint c JOIN pg_class r ON r.oid = c.conrelid"
                " LEFT JOIN pg_class t ON t.oid = c.confrelid WHERE c.conname = ANY(:names)"
            ),
            {"names": list(CONSTRAINTS)},
        )
    ).all()
    assert {row.conname: (row.relname, row.contype) for row in rows} == CONSTRAINTS
    assert {row.conname: row.target for row in rows if row.contype == "f"} == FK_TARGETS
    # Deleting an application/template/account never silently deletes sent-mail history.
    assert all(row.deltype != "c" for row in rows if row.contype == "f")


@pytest.mark.parametrize("index", sorted(INDEXES))
async def test_indexes_match_context(db_session, index) -> None:
    definition = await db_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"),
        {"n": index},
    )
    assert definition is not None, index
    for fragment in INDEXES[index]:
        assert fragment in definition, (fragment, definition)


async def test_required_vars_trigger_is_registered(db_session) -> None:
    row = (
        await db_session.execute(
            text(
                "SELECT p.proname, t.tgtype FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid"
                " WHERE t.tgrelid = 'public.email_templates'::regclass"
                " AND t.tgname = 'email_templates_vars'"
            )
        )
    ).one()
    assert row.proname == "trg_template_required_vars"
    assert row.tgtype & 1 and row.tgtype & 2  # FOR EACH ROW, BEFORE
    assert row.tgtype & 4 and row.tgtype & 16  # INSERT and UPDATE


def test_orm_models_register_the_tables() -> None:
    from app.db.base import Base
    from app.modules.notifications.models import EmailOutbox, EmailStatus, EmailTemplate

    assert EmailTemplate.__tablename__ == "email_templates"
    assert EmailOutbox.__tablename__ == "email_outbox"
    assert [s.value for s in EmailStatus] == ["PENDING", "SENT", "FAILED"]
    assert {"email_templates", "email_outbox"} <= set(Base.metadata.tables)


# ---- trg_template_required_vars -------------------------------------------------------


INSERT_TEMPLATE = (
    "INSERT INTO email_templates (code, subject, body, required_vars, updated_at)"
    " VALUES (:code, :subject, :body, CAST(:vars AS text[]), now())"
)


async def test_template_with_every_required_variable_is_accepted(template, session_factory):
    async with session_factory() as session:
        stored = await session.scalar(
            text("SELECT required_vars FROM email_templates WHERE code = :c"), {"c": template}
        )
    assert stored == ["full_name", "otp_code"]


@pytest.mark.parametrize(
    "body",
    ["Chào bạn, mã của bạn là {otp_code}.", "Chào {full_name}.", "Không có biến nào."],
    ids=["missing-full-name", "missing-otp", "missing-both"],
)
async def test_insert_missing_a_required_variable_is_rejected(
    apply_cleanup, session_factory, body
) -> None:
    await expect_violation(
        session_factory,
        INSERT_TEMPLATE,
        {
            "code": "TEST_MISSING",
            "subject": "Tiêu đề không biến",
            "body": body,
            "vars": ["full_name", "otp_code"],
        },
    )
    async with session_factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM email_templates WHERE code = 'TEST_MISSING'")
        )
    assert count == 0


async def test_required_variable_in_the_subject_only_is_accepted(
    apply_cleanup, session_factory
) -> None:
    # Quyết định triển khai (đã duyệt): biến có mặt ở tiêu đề hoặc nội dung đều đạt.
    await expect_ok(
        session_factory,
        INSERT_TEMPLATE,
        {
            "code": "TEST_SUBJECT_ONLY",
            "subject": "Hồ sơ #{application_id}",
            "body": "Nội dung không lặp lại biến.",
            "vars": ["application_id"],
        },
    )


async def test_update_removing_a_required_variable_is_rejected(template, session_factory) -> None:
    await expect_violation(
        session_factory,
        "UPDATE email_templates SET body = 'Chào {full_name}.' WHERE code = :c",
        {"c": template},
    )


async def test_update_adding_a_required_variable_absent_from_body_is_rejected(
    template, session_factory
) -> None:
    await expect_violation(
        session_factory,
        "UPDATE email_templates SET required_vars = ARRAY['full_name','otp_code','job_title']"
        " WHERE code = :c",
        {"c": template},
    )


async def test_update_keeping_the_variables_is_accepted(template, session_factory) -> None:
    await expect_ok(
        session_factory,
        "UPDATE email_templates SET body = 'Mã {otp_code} dành cho {full_name}.',"
        " updated_at = now() WHERE code = :c",
        {"c": template},
    )


# ---- email_outbox CHECKs --------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"attempts": -1}, "email_outbox_attempts_check"),
        ({"attempts": 5}, "email_outbox_attempts_check"),
        (
            {"status": "FAILED", "attempts": 0, "last_error": "smtp_550"},
            "email_outbox_failed_has_error",
        ),
        ({"status": "FAILED", "attempts": 1, "last_error": None}, "email_outbox_failed_has_error"),
        ({"status": "PENDING", "sent_at": "now"}, "email_outbox_sent_at_only_sent"),
        (
            {"status": "FAILED", "attempts": 1, "last_error": "x", "sent_at": "now"},
            "email_outbox_sent_at_only_sent",
        ),
        ({"status": "SENT", "attempts": 1, "sent_at": None}, "email_outbox_sent_complete"),
        ({"status": "SENT", "attempts": 0, "sent_at": "now"}, "email_outbox_sent_complete"),
        ({"subject": "Xin chào\r\nBcc: evil@example.test"}, "email_outbox_subject_no_newline"),
        ({"subject": "Dòng một\nDòng hai"}, "email_outbox_subject_no_newline"),
        (
            {"to_email": "victim@example.test\r\nBcc: evil@example.test"},
            "email_outbox_to_email_check",
        ),
        ({"to_email": "victim@example.test\n"}, "email_outbox_to_email_check"),
        ({"to_email": "@example.test"}, "email_outbox_to_email_check"),
        ({"to_email": "no-at-sign.example.test"}, "email_outbox_to_email_check"),
    ],
    ids=[
        "attempts-negative",
        "attempts-5",
        "failed-no-attempt",
        "failed-no-error",
        "pending-sent-at",
        "failed-sent-at",
        "sent-no-sent-at",
        "sent-no-attempt",
        "subject-crlf",
        "subject-lf",
        "to-crlf-bcc",
        "to-trailing-lf",
        "to-empty-local",
        "to-no-at",
    ],
)
async def test_outbox_checks(template, session_factory, overrides, constraint) -> None:
    values = outbox_values(template, **overrides)
    if values["sent_at"] == "now":
        values["sent_at"] = now_utc()
    await expect_violation(session_factory, INSERT_OUTBOX, values, constraint)


@pytest.mark.parametrize(
    "overrides",
    [
        {"attempts": 4},
        {"status": "SENT", "attempts": 1, "sent_at": "now"},
        {"status": "FAILED", "attempts": 4, "last_error": "smtp_timeout"},
        {"status": "FAILED", "attempts": 1, "last_error": "invalid_recipient"},
    ],
    ids=["pending-4", "sent", "failed-4", "failed-permanent"],
)
async def test_outbox_valid_rows_are_accepted(template, session_factory, overrides) -> None:
    values = outbox_values(template, **overrides)
    if values["sent_at"] == "now":
        values["sent_at"] = now_utc()
    assert await expect_ok(session_factory, INSERT_OUTBOX, values)


async def test_outbox_foreign_keys(template, session_factory) -> None:
    for overrides, constraint in (
        ({"template_code": "NO_SUCH_TEMPLATE"}, "email_outbox_template_code_fkey"),
        ({"application_id": 9_000_000_000}, "email_outbox_application_id_fkey"),
        ({"user_id": uuid.uuid4()}, "email_outbox_user_id_fkey"),
    ):
        values = outbox_values(template, **overrides)
        await expect_violation(session_factory, INSERT_OUTBOX, values, constraint)


async def test_outbox_links_to_an_application_and_an_account(template, session_factory) -> None:
    world = await build_world(session_factory)
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.commit()
    row_id = await expect_ok(
        session_factory,
        INSERT_OUTBOX,
        outbox_values(template, application_id=app_id, user_id=world.hr_id),
    )
    assert row_id
    # The referenced application cannot be removed while mail history points at it.
    await expect_violation(
        session_factory, "DELETE FROM applications WHERE id = :id", {"id": app_id}
    )


async def test_template_in_use_cannot_be_deleted(template, session_factory) -> None:
    await expect_ok(session_factory, INSERT_OUTBOX, outbox_values(template))
    await expect_violation(
        session_factory, "DELETE FROM email_templates WHERE code = :c", {"c": template}
    )
