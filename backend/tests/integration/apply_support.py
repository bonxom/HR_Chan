# Helper dùng chung cho test schema/notification/worker của luồng ứng tuyển + outbox.
# Không phải file test (pytest không thu thập); import như `import apply_support`.
"""Shared SQL helpers and fixtures for the application and email outbox suites.

Rows are written with explicit SQL against the dedicated, migrated test database so the
schema tests do not depend on services that are implemented later in the plan. Every
NOT NULL column of context 02 is given an explicit value: the tests never rely on
column defaults that the design does not specify.

Cleanup: ``clean_database`` (tests/conftest.py) truncates ``accounts`` with CASCADE,
which also empties every table holding a FK to accounts (email_templates, email_outbox,
otp_codes, applications, job_postings ...). ``candidates`` and ``cv_submissions`` do not
reference accounts, so ``apply_cleanup`` empties the new tables explicitly. It skips
tables that do not exist yet, so a Red run reports the missing schema, not a teardown
error.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

NEW_TABLES = (
    "email_outbox",
    "otp_codes",
    "applications",
    "cv_submissions",
    "candidates",
    "email_templates",
)

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FIVE_MB = 5 * 1024 * 1024
# Placeholder hash only; never a real password hash.
FAKE_PASSWORD_HASH = "test-only-not-a-real-hash"


def now_utc() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def apply_cleanup(clean_database, session_factory) -> AsyncIterator[None]:
    """Empty the new tables after the test (runs before ``clean_database`` teardown)."""
    yield
    async with session_factory() as session:
        existing = [
            name
            for name in NEW_TABLES
            if await session.scalar(text("SELECT to_regclass(:n)"), {"n": f"public.{name}"})
        ]
        if existing:
            await session.execute(text(f"TRUNCATE TABLE {', '.join(existing)} CASCADE"))
        await session.commit()


# ---- reference data -----------------------------------------------------------------


async def insert_account(
    session,
    *,
    email: str | None = None,
    roles: list[str] | None = None,
    status: str = "ACTIVE",
    account_type: str = "EMPLOYEE",
) -> uuid.UUID:
    account_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO accounts (id, full_name, email, account_type, roles, status,"
            " password_hash) VALUES (:id, :name, :email, CAST(:type AS account_type),"
            " CAST(:roles AS text[]), CAST(:status AS account_status), :hash)"
        ),
        {
            "id": account_id,
            "name": "Tài khoản thử",
            "email": email or f"acct-{account_id.hex[:10]}@sis.hust.edu.vn",
            "type": account_type,
            "roles": roles if roles is not None else ["HR"],
            "status": status,
            "hash": FAKE_PASSWORD_HASH if status != "PENDING_SETUP" else None,
        },
    )
    return account_id


async def insert_department(session, name: str = "Phòng Kỹ thuật") -> int:
    await session.execute(
        text("INSERT INTO departments (name) VALUES (:n) ON CONFLICT (name) DO NOTHING"),
        {"n": name},
    )
    return await session.scalar(text("SELECT id FROM departments WHERE name = :n"), {"n": name})


async def insert_draft_job(session, *, created_by: uuid.UUID, title: str = "Tin thử") -> int:
    department_id = await insert_department(session)
    return await session.scalar(
        text(
            "INSERT INTO job_postings (title, department_id, status, created_by)"
            " VALUES (:t, :d, 'DRAFT', :c) RETURNING id"
        ),
        {"t": title, "d": department_id, "c": created_by},
    )


async def insert_criteria_set(session, *, job_id: int, created_by: uuid.UUID, version=1) -> int:
    return await session.scalar(
        text(
            "INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by)"
            " VALUES (:j, :v, 70, :c) RETURNING id"
        ),
        {"j": job_id, "v": version, "c": created_by},
    )


# ---- candidates / submissions / applications ------------------------------------------


async def insert_candidate(session, *, email: str | None = None, phone="0912345678", **extra):
    values = {
        "email": email or f"cand-{uuid.uuid4().hex[:10]}@example.test",
        "full_name": "Nguyễn Văn Ứng Viên",
        "phone": phone,
        "created_at": now_utc(),
    }
    values.update(extra)
    return await session.scalar(
        text(
            "INSERT INTO candidates (email, full_name, phone, created_at)"
            " VALUES (:email, :full_name, :phone, :created_at) RETURNING id"
        ),
        values,
    )


def submission_values(candidate_id: int, /, **overrides) -> dict:
    created = now_utc()
    values = {
        "candidate_id": candidate_id,
        "cv_storage_key": uuid.uuid4().hex,
        "cv_original_name": "cv.pdf",
        "cv_mime_type": PDF_MIME,
        "cv_size_bytes": 1024,
        "cv_sha256": "a" * 64,
        "cv_scan_status": "CLEAN",
        "consent_at": created,
        "consent_policy_ver": "2026-11",
        "parse_status": "PENDING",
        "parsed_data": None,
        "suggestions": None,
        "ip": "127.0.0.1",
        "created_at": created,
        "expires_at": created + timedelta(hours=24),
    }
    values.update(overrides)
    return values


INSERT_SUBMISSION = text(
    "INSERT INTO cv_submissions (candidate_id, cv_storage_key, cv_original_name, cv_mime_type,"
    " cv_size_bytes, cv_sha256, cv_scan_status, consent_at, consent_policy_ver, parse_status,"
    " parsed_data, suggestions, ip, created_at, expires_at)"
    " VALUES (:candidate_id, :cv_storage_key, :cv_original_name, :cv_mime_type, :cv_size_bytes,"
    " :cv_sha256, CAST(:cv_scan_status AS scan_status), :consent_at, :consent_policy_ver,"
    " CAST(:parse_status AS parse_status), CAST(:parsed_data AS jsonb),"
    " CAST(:suggestions AS jsonb), CAST(:ip AS inet), :created_at, :expires_at)"
    " RETURNING id"
)


async def insert_submission(session, candidate_id: int, /, **overrides) -> int:
    return await session.scalar(INSERT_SUBMISSION, submission_values(candidate_id, **overrides))


def application_values(candidate_id: int, job_id: int, submission_id: int, /, **overrides) -> dict:
    # Positional-only base: overrides may replace candidate_id/job_id/submission_id.
    at = now_utc()
    values = {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "submission_id": submission_id,
        "status": "SCORING",
        "submitted_at": at,
        "criteria_set_id": None,
        "ai_status": "PENDING",
        "ai_total_score": None,
        "decided_by": None,
        "decided_at": None,
        "reject_reason_code": None,
        "reject_reason_text": None,
        "email_issue": None,
        "updated_at": at,
        "version": 1,
    }
    values.update(overrides)
    return values


INSERT_APPLICATION = text(
    "INSERT INTO applications (candidate_id, job_id, submission_id, status, submitted_at,"
    " criteria_set_id, ai_status, ai_total_score, decided_by, decided_at, reject_reason_code,"
    " reject_reason_text, email_issue, updated_at, version)"
    " VALUES (:candidate_id, :job_id, :submission_id, CAST(:status AS application_status),"
    " :submitted_at, :criteria_set_id, CAST(:ai_status AS ai_score_status), :ai_total_score,"
    " :decided_by, :decided_at, :reject_reason_code, :reject_reason_text, :email_issue,"
    " :updated_at, :version) RETURNING id"
)


async def insert_application(session, candidate_id, job_id, submission_id, /, **overrides) -> int:
    return await session.scalar(
        INSERT_APPLICATION, application_values(candidate_id, job_id, submission_id, **overrides)
    )


# ---- OTP ------------------------------------------------------------------------------


def otp_values(**overrides) -> dict:
    created = now_utc()
    values = {
        "email": "otp@example.test",
        "purpose": "APPLY",
        "code_hash": "hmac-sha256-placeholder",
        "submission_id": None,
        "job_id": None,
        "user_id": None,
        "attempts": 0,
        "created_at": created,
        "expires_at": created + timedelta(minutes=5),
        "consumed_at": None,
        "invalidated_at": None,
        "ip": None,
    }
    values.update(overrides)
    return values


INSERT_OTP = text(
    "INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, user_id, attempts,"
    " created_at, expires_at, consumed_at, invalidated_at, ip)"
    " VALUES (:email, CAST(:purpose AS otp_purpose), :code_hash, :submission_id, :job_id,"
    " :user_id, :attempts, :created_at, :expires_at, :consumed_at, :invalidated_at,"
    " CAST(:ip AS inet)) RETURNING id"
)


async def insert_otp(session, **overrides) -> int:
    return await session.scalar(INSERT_OTP, otp_values(**overrides))


# ---- email templates / outbox ---------------------------------------------------------


async def insert_template(
    session, code: str, *, subject: str, body: str, required_vars: list[str]
) -> None:
    await session.execute(
        text(
            "INSERT INTO email_templates (code, subject, body, required_vars, updated_at)"
            " VALUES (:code, :subject, :body, CAST(:vars AS text[]), :at)"
        ),
        {"code": code, "subject": subject, "body": body, "vars": required_vars, "at": now_utc()},
    )


def outbox_values(template_code: str, /, **overrides) -> dict:
    # Positional-only base: an override may replace template_code itself.
    at = now_utc()
    values = {
        "template_code": template_code,
        "to_email": "recipient@example.test",
        "subject": "Tiêu đề",
        "body": "Nội dung đã che",
        "application_id": None,
        "user_id": None,
        "status": "PENDING",
        "attempts": 0,
        "next_attempt_at": at,
        "last_error": None,
        "created_at": at,
        "sent_at": None,
    }
    values.update(overrides)
    return values


INSERT_OUTBOX = text(
    "INSERT INTO email_outbox (template_code, to_email, subject, body, application_id, user_id,"
    " status, attempts, next_attempt_at, last_error, created_at, sent_at)"
    " VALUES (:template_code, :to_email, :subject, :body, :application_id, :user_id,"
    " CAST(:status AS email_status), :attempts, :next_attempt_at, :last_error, :created_at,"
    " :sent_at) RETURNING id"
)


async def insert_outbox(session, template_code: str, /, **overrides) -> int:
    return await session.scalar(INSERT_OUTBOX, outbox_values(template_code, **overrides))


async def outbox_row(session_factory, outbox_id: int):
    async with session_factory() as session:
        return (
            await session.execute(
                text(
                    "SELECT id, template_code, to_email, subject, body, application_id, user_id,"
                    " status::text AS status, attempts, next_attempt_at, last_error, created_at,"
                    " sent_at FROM email_outbox WHERE id = :id"
                ),
                {"id": outbox_id},
            )
        ).one_or_none()


async def outbox_rows(session_factory, template_code: str | None = None) -> list:
    query = (
        "SELECT id, template_code, to_email, subject, body, application_id, user_id,"
        " status::text AS status, attempts, next_attempt_at, last_error, sent_at"
        " FROM email_outbox"
    )
    params: dict = {}
    if template_code is not None:
        query += " WHERE template_code = :code"
        params["code"] = template_code
    async with session_factory() as session:
        return list((await session.execute(text(query + " ORDER BY id"), params)).all())


# ---- controllable email service -------------------------------------------------------


class ScriptedEmailService:
    """IEmailService stand-in: each send consumes the next scripted outcome.

    ``None`` means delivered; an exception instance is raised. When the script is empty
    every send succeeds. ``on_send`` (async, receives the message) runs before the
    outcome so a test can inspect the database while delivery is in flight, or block on
    an event to hold the row lock.
    """

    simulated = True

    def __init__(self, *outcomes, on_send=None) -> None:
        self.outcomes = list(outcomes)
        self.attempted: list = []  # every message handed to send(), in order
        self.delivered: list = []  # messages for which send() returned normally
        self.on_send = on_send

    async def send(self, message) -> None:
        self.attempted.append(message)
        if self.on_send is not None:
            await self.on_send(message)
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome
        self.delivered.append(message)


# ---- an application "world" -----------------------------------------------------------


@dataclass
class ApplyWorld:
    hr_id: uuid.UUID
    job_id: int
    criteria_set_id: int
    candidate_id: int
    candidate_email: str
    submission_id: int


async def build_world(session_factory) -> ApplyWorld:
    """Commit an HR account, a DRAFT posting with one criteria set, a candidate and a CV."""
    async with session_factory() as session:
        hr_id = await insert_account(session, roles=["HR"])
        job_id = await insert_draft_job(session, created_by=hr_id)
        set_id = await insert_criteria_set(session, job_id=job_id, created_by=hr_id)
        email = f"cand-{uuid.uuid4().hex[:10]}@example.test"
        candidate_id = await insert_candidate(session, email=email)
        submission_id = await insert_submission(session, candidate_id)
        await session.commit()
    return ApplyWorld(hr_id, job_id, set_id, candidate_id, email, submission_id)
