# Kiểm tra cấu trúc bảng ứng tuyển theo context 02 trên PostgreSQL riêng đã migrate.
# Mỗi ràng buộc được thử bằng SQL thật; tên ràng buộc lấy đúng từ context 02.
"""Schema of candidates, cv_submissions, otp_codes and applications (plan task 1).

Source: context 02 (columns, enums, CHECK/UNIQUE/FK/index/trigger) with the approved
mapping of context 00 section 4.11: every reference to ``users`` becomes a UUID FK to
``accounts.id`` and history goes to ``audit_events``. Business IDs stay BIGINT.

Red before migration 0005: the tables and enums do not exist yet.
"""

import json
import uuid
from datetime import timedelta

import pytest
from apply_support import (
    DOCX_MIME,
    FIVE_MB,
    INSERT_APPLICATION,
    INSERT_OTP,
    INSERT_SUBMISSION,
    application_values,
    apply_cleanup,
    build_world,
    insert_account,
    insert_application,
    insert_criteria_set,
    insert_draft_job,
    insert_submission,
    now_utc,
    otp_values,
    submission_values,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]  # fixture re-exported for pytest

APPLICATION_STATUSES = [
    "SCORING",
    "PENDING_HR_REVIEW",
    "INTERVIEW_INVITED",
    "INTERVIEW_CONFIRMED",
    "INTERVIEW_DECLINED",
    "AWAITING_INTERVIEW_RESULT",
    "INTERVIEW_PASSED",
    "INTERVIEW_FAILED",
    "REJECTED",
    "AWAITING_ACCOUNT",
    "ON_PROBATION",
    "PROBATION_DECLINED",
    "PROBATION_PASSED",
    "PROBATION_FAILED",
]

ENUMS = {
    "ai_score_status": ["PENDING", "SCORED", "NEEDS_REVIEW", "FAILED"],
    "application_status": APPLICATION_STATUSES,
    "otp_purpose": ["APPLY", "RESET_PASSWORD"],
    "parse_status": ["PENDING", "PARSED", "PARTIAL", "FAILED"],
    "scan_status": ["PENDING", "CLEAN", "INFECTED"],
}

# column -> (udt_name, nullable, character_maximum_length or (precision, scale))
COLUMNS = {
    "candidates": {
        "id": ("int8", False, None),
        "email": ("citext", False, None),
        "full_name": ("varchar", False, 100),
        "phone": ("bpchar", False, 10),
        "created_at": ("timestamptz", False, None),
        "anonymized_at": ("timestamptz", True, None),
    },
    "cv_submissions": {
        "id": ("int8", False, None),
        "candidate_id": ("int8", False, None),
        "cv_storage_key": ("varchar", False, 100),
        "cv_original_name": ("varchar", False, 255),
        "cv_mime_type": ("varchar", False, 100),
        "cv_size_bytes": ("int4", False, None),
        "cv_sha256": ("bpchar", False, 64),
        "cv_scan_status": ("scan_status", False, None),
        "consent_at": ("timestamptz", False, None),
        "consent_policy_ver": ("varchar", False, 20),
        "parse_status": ("parse_status", False, None),
        "parsed_data": ("jsonb", True, None),
        "embedding": ("vector", True, None),
        "suggestions": ("jsonb", True, None),
        "ip": ("inet", True, None),
        "created_at": ("timestamptz", False, None),
        "expires_at": ("timestamptz", False, None),
    },
    "otp_codes": {
        "id": ("int8", False, None),
        "email": ("citext", False, None),
        "purpose": ("otp_purpose", False, None),
        "code_hash": ("text", False, None),
        "submission_id": ("int8", True, None),
        "job_id": ("int8", True, None),
        "user_id": ("uuid", True, None),  # users(id) -> accounts(id) UUID (00 §4.11)
        "attempts": ("int2", False, None),
        "created_at": ("timestamptz", False, None),
        "expires_at": ("timestamptz", False, None),
        "consumed_at": ("timestamptz", True, None),
        "invalidated_at": ("timestamptz", True, None),
        "ip": ("inet", True, None),
    },
    "applications": {
        "id": ("int8", False, None),
        "candidate_id": ("int8", False, None),
        "job_id": ("int8", False, None),
        "submission_id": ("int8", False, None),
        "status": ("application_status", False, None),
        "submitted_at": ("timestamptz", False, None),
        "criteria_set_id": ("int8", True, None),
        "ai_status": ("ai_score_status", False, None),
        "ai_total_score": ("numeric", True, (5, 2)),
        "ai_failure_reason": ("text", True, None),
        "hr_note": ("text", True, None),
        "email_issue": ("varchar", True, 100),
        "review_due_at": ("timestamptz", True, None),
        "decided_by": ("uuid", True, None),  # users(id) -> accounts(id) UUID (00 §4.11)
        "decided_at": ("timestamptz", True, None),
        "reject_reason_code": ("varchar", True, 40),
        "reject_reason_text": ("text", True, None),
        "updated_at": ("timestamptz", False, None),
        "version": ("int4", False, None),
    },
}

# name -> (table, contype) ; p=PK u=UNIQUE c=CHECK f=FK
CONSTRAINTS = {
    "candidates_pkey": ("candidates", "p"),
    "candidates_email_key": ("candidates", "u"),
    "candidates_phone_check": ("candidates", "c"),
    "cv_submissions_pkey": ("cv_submissions", "p"),
    "cv_submissions_cv_storage_key_key": ("cv_submissions", "u"),
    "cv_submissions_cv_mime_type_check": ("cv_submissions", "c"),
    "cv_submissions_cv_size_bytes_check": ("cv_submissions", "c"),
    "cv_submissions_expiry": ("cv_submissions", "c"),
    "cv_submissions_parsed_has_data": ("cv_submissions", "c"),
    "cv_submissions_suggestions_check": ("cv_submissions", "c"),
    "cv_submissions_candidate_id_fkey": ("cv_submissions", "f"),
    "otp_codes_pkey": ("otp_codes", "p"),
    "otp_codes_attempts_check": ("otp_codes", "c"),
    "otp_codes_expiry": ("otp_codes", "c"),
    "otp_codes_purpose_refs": ("otp_codes", "c"),
    "otp_codes_job_id_fkey": ("otp_codes", "f"),
    "otp_codes_submission_id_fkey": ("otp_codes", "f"),
    "otp_codes_user_id_fkey": ("otp_codes", "f"),
    "applications_pkey": ("applications", "p"),
    "applications_candidate_id_job_id_key": ("applications", "u"),
    "applications_ai_total_score_check": ("applications", "c"),
    "applications_other_reason_text": ("applications", "c"),
    "applications_reject_reason_text_check": ("applications", "c"),
    "applications_rejected_by_hr": ("applications", "c"),
    "applications_scored_complete": ("applications", "c"),
    "applications_candidate_id_fkey": ("applications", "f"),
    "applications_criteria_set_fk": ("applications", "f"),
    "applications_decided_by_fkey": ("applications", "f"),
    "applications_job_id_fkey": ("applications", "f"),
    "applications_submission_id_fkey": ("applications", "f"),
}

# FK name -> referenced table (accounts replaces users per 00 §4.11)
FK_TARGETS = {
    "cv_submissions_candidate_id_fkey": "candidates",
    "otp_codes_job_id_fkey": "job_postings",
    "otp_codes_submission_id_fkey": "cv_submissions",
    "otp_codes_user_id_fkey": "accounts",
    "applications_candidate_id_fkey": "candidates",
    "applications_criteria_set_fk": "criteria_sets",
    "applications_decided_by_fkey": "accounts",
    "applications_job_id_fkey": "job_postings",
    "applications_submission_id_fkey": "cv_submissions",
}

# index -> fragments that must appear in pg_indexes.indexdef
INDEXES = {
    "cv_submissions_expiry_idx": ["cv_submissions", "(expires_at)"],
    "otp_one_live_code": [
        "UNIQUE",
        "(email, purpose)",
        "consumed_at IS NULL",
        "invalidated_at IS NULL",
    ],
    "otp_rate_idx": ["(email, purpose, created_at)"],
    "applications_job_idx": ["(job_id, status)"],
    "applications_status_idx": ["(status, submitted_at)"],
}


@pytest.fixture
async def world(apply_cleanup, session_factory):
    return await build_world(session_factory)


def as_sql(statement):
    return text(statement) if isinstance(statement, str) else statement


async def expect_violation(session_factory, statement, params, constraint: str | None = None):
    """Run one statement in its own transaction and require a database error."""
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as error:
            await session.execute(as_sql(statement), params)
            await session.commit()
        await session.rollback()
    if constraint is not None:
        assert constraint in str(error.value), str(error.value)


async def expect_ok(session_factory, statement, params):
    async with session_factory() as session:
        result = await session.execute(as_sql(statement), params)
        value = result.scalar_one_or_none() if result.returns_rows else None
        await session.commit()
    return value


# ---- catalog ------------------------------------------------------------------------


async def test_tables_exist(db_session) -> None:
    for table in COLUMNS:
        value = await db_session.scalar(
            text("SELECT to_regclass(:t)::text"), {"t": f"public.{table}"}
        )
        assert value == table


@pytest.mark.parametrize("enum_name", sorted(ENUMS))
async def test_enum_values_match_context(db_session, enum_name) -> None:
    rows = await db_session.scalars(
        text(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid"
            " WHERE t.typname = :n ORDER BY e.enumsortorder"
        ),
        {"n": enum_name},
    )
    assert list(rows) == ENUMS[enum_name]


@pytest.mark.parametrize("table", sorted(COLUMNS))
async def test_columns_types_and_nullability(db_session, table) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT column_name, udt_name, is_nullable, character_maximum_length,"
                " numeric_precision, numeric_scale FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        )
    ).all()
    actual = {}
    for row in rows:
        size = row.character_maximum_length
        if row.udt_name == "numeric":
            size = (row.numeric_precision, row.numeric_scale)
        actual[row.column_name] = (row.udt_name, row.is_nullable == "YES", size)
    assert actual == COLUMNS[table]


async def test_embedding_has_1536_dimensions(db_session) -> None:
    typmod = await db_session.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute"
            " WHERE attrelid = 'public.cv_submissions'::regclass AND attname = 'embedding'"
        )
    )
    assert typmod == 1536


async def test_named_constraints_exist(db_session) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT c.conname, r.relname, c.contype::text AS contype"
                " FROM pg_constraint c JOIN pg_class r ON r.oid = c.conrelid"
                " WHERE c.conname = ANY(:names)"
            ),
            {"names": list(CONSTRAINTS)},
        )
    ).all()
    assert {row.conname: (row.relname, row.contype) for row in rows} == CONSTRAINTS


async def test_foreign_keys_reference_the_mapped_tables(db_session) -> None:
    rows = (
        await db_session.execute(
            text(
                "SELECT c.conname, t.relname AS target FROM pg_constraint c"
                " JOIN pg_class t ON t.oid = c.confrelid WHERE c.conname = ANY(:names)"
            ),
            {"names": list(FK_TARGETS)},
        )
    ).all()
    assert {row.conname: row.target for row in rows} == FK_TARGETS


async def test_new_foreign_keys_do_not_cascade_deletes(db_session) -> None:
    # Tin có hồ sơ được bảo vệ; không cascade xóa hồ sơ/CV (spec "Worker" cuối mục).
    rows = (
        await db_session.execute(
            text(
                "SELECT conname, confdeltype::text AS deltype FROM pg_constraint"
                " WHERE conname = ANY(:names)"
            ),
            {"names": list(FK_TARGETS)},
        )
    ).all()
    assert rows and all(row.deltype != "c" for row in rows), rows


async def test_criteria_set_fk_is_composite_with_job(db_session) -> None:
    columns = await db_session.scalar(
        text(
            "SELECT array_agg(a.attname::text ORDER BY k.ord) FROM pg_constraint c"
            " CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)"
            " JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum"
            " WHERE c.conname = 'applications_criteria_set_fk'"
        )
    )
    assert columns == ["criteria_set_id", "job_id"]


@pytest.mark.parametrize("index", sorted(INDEXES))
async def test_indexes_match_context(db_session, index) -> None:
    definition = await db_session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"),
        {"n": index},
    )
    assert definition is not None, index
    for fragment in INDEXES[index]:
        assert fragment in definition, (fragment, definition)


def test_orm_models_register_the_tables() -> None:
    # alembic/env.py imports these modules so autogenerate/check sees the tables.
    from app.core.otp.models import OtpCode, OtpPurpose
    from app.db.base import Base
    from app.modules.applications.models import AiScoreStatus, Application, ApplicationStatus
    from app.modules.candidates.models import Candidate, CvSubmission, ParseStatus, ScanStatus

    assert OtpCode.__tablename__ == "otp_codes"
    assert Application.__tablename__ == "applications"
    assert Candidate.__tablename__ == "candidates"
    assert CvSubmission.__tablename__ == "cv_submissions"
    assert [s.value for s in ApplicationStatus] == APPLICATION_STATUSES
    assert [s.value for s in AiScoreStatus] == ENUMS["ai_score_status"]
    assert [s.value for s in OtpPurpose] == ENUMS["otp_purpose"]
    assert [s.value for s in ParseStatus] == ENUMS["parse_status"]
    assert [s.value for s in ScanStatus] == ENUMS["scan_status"]
    for table in COLUMNS:
        assert table in Base.metadata.tables


# ---- candidates -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("phone", "constraint"),
    [
        ("091234567", "candidates_phone_check"),  # char(10) pads to "091234567 "
        ("09123456ab", "candidates_phone_check"),
        ("+849123456", "candidates_phone_check"),
        # 11 characters: character(10) rejects it (string data right truncation) before
        # the CHECK runs; the row is still refused, under another error.
        ("09123456789", None),
    ],
)
async def test_candidate_phone_must_be_ten_digits(
    world, session_factory, phone, constraint
) -> None:
    await expect_violation(
        session_factory,
        "INSERT INTO candidates (email, full_name, phone, created_at)"
        " VALUES ('p@example.test', 'A', :phone, now())",
        {"phone": phone},
        constraint,
    )


async def test_candidate_email_is_unique_case_insensitively(world, session_factory) -> None:
    await expect_violation(
        session_factory,
        "INSERT INTO candidates (email, full_name, phone, created_at)"
        " VALUES (:e, 'B', '0987654321', now())",
        {"e": world.candidate_email.upper()},
        "candidates_email_key",
    )


# ---- cv_submissions -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"cv_mime_type": "image/png"}, "cv_submissions_cv_mime_type_check"),
        ({"cv_mime_type": "application/msword"}, "cv_submissions_cv_mime_type_check"),
        ({"cv_size_bytes": 0}, "cv_submissions_cv_size_bytes_check"),
        ({"cv_size_bytes": FIVE_MB + 1}, "cv_submissions_cv_size_bytes_check"),
        ({"parse_status": "PARSED"}, "cv_submissions_parsed_has_data"),
        ({"parse_status": "PARTIAL"}, "cv_submissions_parsed_has_data"),
        ({"suggestions": json.dumps({"job_id": 1})}, "cv_submissions_suggestions_check"),
        (
            {"suggestions": json.dumps([{"job_id": n} for n in range(11)])},
            "cv_submissions_suggestions_check",
        ),
    ],
    ids=[
        "png",
        "doc",
        "empty",
        "over-5mb",
        "parsed-no-data",
        "partial-no-data",
        "suggestions-object",
        "suggestions-11",
    ],
)
async def test_submission_checks(world, session_factory, overrides, constraint) -> None:
    await expect_violation(
        session_factory,
        INSERT_SUBMISSION,
        submission_values(world.candidate_id, **overrides),
        constraint,
    )


async def test_submission_expiry_must_follow_creation(world, session_factory) -> None:
    created = now_utc()
    await expect_violation(
        session_factory,
        INSERT_SUBMISSION,
        submission_values(world.candidate_id, created_at=created, expires_at=created),
        "cv_submissions_expiry",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"cv_mime_type": DOCX_MIME, "cv_size_bytes": FIVE_MB},
        {"parse_status": "FAILED"},
        {"parse_status": "PARSED", "parsed_data": json.dumps({"skills": ["Python"]})},
        {"suggestions": json.dumps([{"job_id": n} for n in range(10)])},
    ],
    ids=["docx-5mb", "failed-no-data", "parsed-with-data", "ten-suggestions"],
)
async def test_submission_valid_rows_are_accepted(world, session_factory, overrides) -> None:
    assert await expect_ok(
        session_factory, INSERT_SUBMISSION, submission_values(world.candidate_id, **overrides)
    )


async def test_submission_storage_key_is_unique_and_candidate_must_exist(
    world, session_factory
) -> None:
    key = uuid.uuid4().hex
    values = submission_values(world.candidate_id, cv_storage_key=key)
    await expect_ok(session_factory, INSERT_SUBMISSION, values)
    await expect_violation(
        session_factory,
        INSERT_SUBMISSION,
        submission_values(world.candidate_id, cv_storage_key=key),
        "cv_submissions_cv_storage_key_key",
    )
    await expect_violation(
        session_factory,
        INSERT_SUBMISSION,
        submission_values(9_000_000_000),
        "cv_submissions_candidate_id_fkey",
    )


# ---- otp_codes ------------------------------------------------------------------------


def apply_otp(world, **overrides) -> dict:
    # Merge so an override (email/job_id/submission_id/user_id) replaces the base value.
    base = {
        "email": world.candidate_email,
        "submission_id": world.submission_id,
        "job_id": world.job_id,
    }
    return otp_values(**{**base, **overrides})


@pytest.mark.parametrize("attempts", [-1, 6])
async def test_otp_attempts_range(world, session_factory, attempts) -> None:
    await expect_violation(
        session_factory, INSERT_OTP, apply_otp(world, attempts=attempts), "otp_codes_attempts_check"
    )


async def test_otp_accepts_five_attempts_and_requires_expiry_after_creation(
    world, session_factory
) -> None:
    assert await expect_ok(session_factory, INSERT_OTP, apply_otp(world, attempts=5))
    created = now_utc()
    await expect_violation(
        session_factory,
        INSERT_OTP,
        apply_otp(world, email="other@example.test", created_at=created, expires_at=created),
        "otp_codes_expiry",
    )


async def test_otp_purpose_references(world, session_factory) -> None:
    def reset(**overrides):
        return otp_values(email="reset@sis.hust.edu.vn", purpose="RESET_PASSWORD", **overrides)

    for params in (
        apply_otp(world, submission_id=None),
        apply_otp(world, job_id=None),
        apply_otp(world, user_id=world.hr_id),
        reset(),
        reset(user_id=world.hr_id, job_id=world.job_id),
        reset(user_id=world.hr_id, submission_id=world.submission_id),
    ):
        await expect_violation(session_factory, INSERT_OTP, params, "otp_codes_purpose_refs")
    assert await expect_ok(session_factory, INSERT_OTP, reset(user_id=world.hr_id))


async def test_otp_foreign_keys(world, session_factory) -> None:
    for overrides, constraint in (
        ({"job_id": 9_000_000_000}, "otp_codes_job_id_fkey"),
        ({"submission_id": 9_000_000_000}, "otp_codes_submission_id_fkey"),
    ):
        params = apply_otp(world, **overrides)
        await expect_violation(session_factory, INSERT_OTP, params, constraint)
    await expect_violation(
        session_factory,
        INSERT_OTP,
        otp_values(purpose="RESET_PASSWORD", user_id=uuid.uuid4()),
        "otp_codes_user_id_fkey",
    )


async def test_only_one_live_otp_per_email_and_purpose(world, session_factory) -> None:
    first = await expect_ok(session_factory, INSERT_OTP, apply_otp(world))
    # citext: same address in another case is the same recipient.
    await expect_violation(
        session_factory,
        INSERT_OTP,
        apply_otp(world, email=world.candidate_email.upper()),
        "otp_one_live_code",
    )
    # Another purpose for the same address is independent.
    async with session_factory() as session:
        await insert_account(session, email=world.candidate_email, roles=["HR"])
        user_id = await session.scalar(
            text("SELECT id FROM accounts WHERE email = :e"), {"e": world.candidate_email}
        )
        await session.commit()
    assert await expect_ok(
        session_factory,
        INSERT_OTP,
        otp_values(email=world.candidate_email, purpose="RESET_PASSWORD", user_id=user_id),
    )
    # Invalidating (resend) or consuming the live code frees the slot.
    async with session_factory() as session:
        await session.execute(
            text("UPDATE otp_codes SET invalidated_at = now() WHERE id = :id"), {"id": first}
        )
        await session.commit()
    second = await expect_ok(session_factory, INSERT_OTP, apply_otp(world))
    async with session_factory() as session:
        await session.execute(
            text("UPDATE otp_codes SET consumed_at = now() WHERE id = :id"), {"id": second}
        )
        await session.commit()
    assert await expect_ok(session_factory, INSERT_OTP, apply_otp(world))


# ---- applications ---------------------------------------------------------------------


def app_values(world, **overrides) -> dict:
    return application_values(world.candidate_id, world.job_id, world.submission_id, **overrides)


async def test_application_minimal_scoring_row_is_accepted(world, session_factory) -> None:
    values = app_values(world, criteria_set_id=world.criteria_set_id)
    assert await expect_ok(session_factory, INSERT_APPLICATION, values)


async def test_one_application_per_candidate_and_job(world, session_factory) -> None:
    await expect_ok(session_factory, INSERT_APPLICATION, app_values(world))
    await expect_violation(
        session_factory,
        INSERT_APPLICATION,
        app_values(world),
        "applications_candidate_id_job_id_key",
    )


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"ai_total_score": -0.01}, "applications_ai_total_score_check"),
        ({"ai_total_score": 100.01}, "applications_ai_total_score_check"),
        ({"ai_status": "SCORED"}, "applications_scored_complete"),
        ({"ai_status": "SCORED", "ai_total_score": 80}, "applications_scored_complete"),
        ({"status": "REJECTED"}, "applications_rejected_by_hr"),
        ({"reject_reason_code": "OTHER"}, "applications_other_reason_text"),
        (
            {"reject_reason_code": "OTHER", "reject_reason_text": "   "},
            "applications_other_reason_text",
        ),
        ({"reject_reason_text": "x" * 501}, "applications_reject_reason_text_check"),
    ],
    ids=[
        "score-low",
        "score-high",
        "scored-empty",
        "scored-no-set",
        "rejected-no-hr",
        "other-no-text",
        "other-blank",
        "text-501",
    ],
)
async def test_application_checks(world, session_factory, overrides, constraint) -> None:
    await expect_violation(
        session_factory, INSERT_APPLICATION, app_values(world, **overrides), constraint
    )


async def test_application_rows_meeting_the_checks_are_accepted(world, session_factory) -> None:
    rejected = app_values(
        world,
        status="REJECTED",
        decided_by=world.hr_id,
        decided_at=now_utc(),
        reject_reason_code="OTHER",
        reject_reason_text="x" * 500,
        ai_status="SCORED",
        ai_total_score=100,
        criteria_set_id=world.criteria_set_id,
    )
    assert await expect_ok(session_factory, INSERT_APPLICATION, rejected)


async def test_email_issue_is_limited_to_100_characters(world, session_factory) -> None:
    await expect_violation(
        session_factory, INSERT_APPLICATION, app_values(world, email_issue="e" * 101), None
    )
    assert await expect_ok(
        session_factory, INSERT_APPLICATION, app_values(world, email_issue="e" * 100)
    )


async def test_application_foreign_keys(world, session_factory) -> None:
    for overrides, constraint in (
        ({"candidate_id": 9_000_000_000}, "applications_candidate_id_fkey"),
        ({"job_id": 9_000_000_000}, "applications_job_id_fkey"),
        ({"submission_id": 9_000_000_000}, "applications_submission_id_fkey"),
        ({"decided_by": uuid.uuid4()}, "applications_decided_by_fkey"),
    ):
        await expect_violation(
            session_factory, INSERT_APPLICATION, app_values(world, **overrides), constraint
        )


async def test_criteria_set_must_belong_to_the_same_job(world, session_factory) -> None:
    async with session_factory() as session:
        other_job = await insert_draft_job(session, created_by=world.hr_id, title="Tin khác")
        other_set = await insert_criteria_set(session, job_id=other_job, created_by=world.hr_id)
        await session.commit()
    await expect_violation(
        session_factory,
        INSERT_APPLICATION,
        app_values(world, criteria_set_id=other_set),
        "applications_criteria_set_fk",
    )


async def test_posting_with_an_application_cannot_be_deleted(world, session_factory) -> None:
    async with session_factory() as session:
        await insert_application(
            session,
            world.candidate_id,
            world.job_id,
            world.submission_id,
            criteria_set_id=world.criteria_set_id,
        )
        await session.commit()
    await expect_violation(
        session_factory, "DELETE FROM job_postings WHERE id = :id", {"id": world.job_id}
    )
    async with session_factory() as session:
        remaining = await session.scalar(
            text(
                "SELECT (SELECT count(*) FROM job_postings WHERE id = :id)"
                " + (SELECT count(*) FROM criteria_sets WHERE job_id = :id)"
                " + (SELECT count(*) FROM applications WHERE job_id = :id)"
            ),
            {"id": world.job_id},
        )
    assert remaining == 3


async def test_submission_and_candidate_with_an_application_cannot_be_deleted(
    world, session_factory
) -> None:
    async with session_factory() as session:
        await insert_application(session, world.candidate_id, world.job_id, world.submission_id)
        await session.commit()
    await expect_violation(
        session_factory, "DELETE FROM cv_submissions WHERE id = :id", {"id": world.submission_id}
    )
    await expect_violation(
        session_factory, "DELETE FROM candidates WHERE id = :id", {"id": world.candidate_id}
    )


# ---- application history trigger (audit_logs -> audit_events, 00 §4.11) ---------------
#
# Context 02: trigger applications_history (AFTER INSERT, UPDATE) -> trg_application_history,
# "Ghi nhật ký mỗi lần đổi trạng thái hồ sơ, người thực hiện lấy từ app.actor_id".
# 00 §4.11: before/after go to metadata.changes; actor ids are account UUIDs.
# NOT fixed by the sources (reported to the reviewer, deliberately not asserted here):
# the audit_events.action string, target_type spelling and outcome value.


async def application_history(session_factory, app_id: int) -> list:
    async with session_factory() as session:
        return list(
            (
                await session.execute(
                    text(
                        "SELECT actor_id, metadata FROM audit_events WHERE target_id = :id"
                        " AND target_type IS DISTINCT FROM 'job_posting'"
                        " AND metadata ? 'changes' AND metadata->'changes' ? 'status'"
                        " ORDER BY timestamp, id"
                    ),
                    {"id": str(app_id)},
                )
            ).all()
        )


async def test_trigger_is_registered_after_insert_and_update(db_session) -> None:
    row = (
        await db_session.execute(
            text(
                "SELECT t.tgname, p.proname, t.tgtype FROM pg_trigger t"
                " JOIN pg_proc p ON p.oid = t.tgfoid"
                " WHERE t.tgrelid = 'public.applications'::regclass"
                " AND t.tgname = 'applications_history'"
            )
        )
    ).one()
    assert row.proname == "trg_application_history"
    tgtype = row.tgtype
    assert tgtype & 1  # FOR EACH ROW
    assert not tgtype & 2  # AFTER
    assert tgtype & 4 and tgtype & 16  # INSERT and UPDATE


async def test_insert_and_status_change_are_recorded_with_the_session_actor(
    world, session_factory
) -> None:
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.commit()

    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.actor_id', :actor, true)"), {"actor": str(world.hr_id)}
        )
        await session.execute(
            text(
                "UPDATE applications SET status = 'PENDING_HR_REVIEW', updated_at = now()"
                " WHERE id = :id"
            ),
            {"id": app_id},
        )
        await session.commit()

    history = await application_history(session_factory, app_id)
    assert len(history) == 2
    created, changed = history
    # Inserted by the candidate flow without app.actor_id: no actor (system/candidate).
    assert created.actor_id is None
    assert created.metadata["changes"]["status"]["after"] == "SCORING"
    assert changed.actor_id == world.hr_id
    assert changed.metadata["changes"]["status"] == {
        "before": "SCORING",
        "after": "PENDING_HR_REVIEW",
    }


async def test_update_without_status_change_is_not_recorded(world, session_factory) -> None:
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.commit()
    async with session_factory() as session:
        await session.execute(
            text("UPDATE applications SET email_issue = 'smtp_550' WHERE id = :id"), {"id": app_id}
        )
        await session.commit()
    assert len(await application_history(session_factory, app_id)) == 1


async def test_history_metadata_holds_no_candidate_personal_data(world, session_factory) -> None:
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.commit()
    (row,) = await application_history(session_factory, app_id)
    dumped = json.dumps(row.metadata, ensure_ascii=False)
    for personal in (world.candidate_email, "Nguyễn Văn Ứng Viên", "0912345678"):
        assert personal not in dumped


async def test_history_is_rolled_back_with_the_change(world, session_factory) -> None:
    async with session_factory() as session:
        app_id = await insert_application(
            session, world.candidate_id, world.job_id, world.submission_id
        )
        await session.rollback()
    assert await application_history(session_factory, app_id) == []


async def test_unreferenced_expired_submission_remains_deletable(world, session_factory) -> None:
    # Cleanup after 24 h is task 6; the schema itself must not block deleting a CV
    # submission that no application or OTP references.
    async with session_factory() as session:
        created = now_utc() - timedelta(days=2)
        orphan = await insert_submission(
            session,
            world.candidate_id,
            created_at=created,
            expires_at=created + timedelta(hours=24),
        )
        await session.commit()
    await expect_ok(session_factory, "DELETE FROM cv_submissions WHERE id = :id", {"id": orphan})
