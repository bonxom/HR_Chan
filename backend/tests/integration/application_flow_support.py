# Helper cho test tasks 5–9 (outbox tài khoản, nộp CV, OTP, hồ sơ, tin công khai, CLI).
# Không phải file test. Mọi adapter giả chỉ được inject qua create_app trong test.
"""Shared fixtures and builders for the application flow suites (plan tasks 5–9).

Production contract assumed by these helpers (approved spec/plan, defined in the tests):

* ``create_app(settings=None, email_client=None, *, email_service=None, storage=None,
  scanner=None, captcha=None)``; existing calls ``create_app(settings, email_client=...)``
  keep working. Nothing is contacted at startup (``/health`` needs no scanner/email).
* Settings (no secret defaults): ``cv_storage_dir``, ``cv_encryption_key``,
  ``submission_token_secret``, ``otp_secret``, ``turnstile_secret_key``,
  ``turnstile_expected_hostname``, ``turnstile_expected_action``, ``clamav_host``,
  ``clamav_port``, ``clamav_timeout_seconds``, ``consent_policy_version``
  (plus ``outbox_encryption_key`` from task 3).
* ``app.integrations.antivirus.client``: ``ScanVerdict`` (CLEAN/INFECTED),
  ``ScannerUnavailableError``; ``app.integrations.captcha.client``:
  ``CaptchaUnavailableError``; ``app.integrations.storage.encrypted_local``:
  ``EncryptedLocalStorage(root, key)``.
* Every new service reads time through ``app.core.clock.utcnow()`` (module attribute),
  so ``frozen_clock`` moves time for TTL/cooldown/lock/24 h tests.

Cleanup: ``flow_cleanup`` empties the application tables (``apply_cleanup``) and uses a
private per-test CV directory; ``clean_database`` (conftest) empties accounts, limiters
and audit events.
"""

import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from apply_support import (
    ScriptedEmailService,
    apply_cleanup,
    insert_account,
    insert_criteria_set,
    insert_department,
    now_utc,
)
from cv_samples import make_pdf
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text

__all__ = ["ScriptedEmailService", "apply_cleanup"]

ORIGIN = {"Origin": "http://localhost:5173"}
SUBMISSIONS_URL = "/api/v1/candidates/submissions"
OTP_URL = "/api/v1/applications/otp"
APPLICATIONS_URL = "/api/v1/applications"
PUBLIC_JOBS_URL = "/api/v1/public/jobs"

# Test-only secrets (never production values).
TEST_KEYS = {
    "outbox_encryption_key": "test-outbox-encryption-key-0123456789abcdef",
    "cv_encryption_key": "test-cv-storage-encryption-key-0123456789ab",
    "submission_token_secret": "test-submission-capability-secret-0123456789",
    "otp_secret": "test-otp-hmac-pepper-secret-0123456789abcdef",
    "turnstile_secret_key": "test-turnstile-secret-not-real-0123456789",
}

OTP_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")


# ---- settings / clock -------------------------------------------------------------------


def flow_settings(settings, cv_dir: Path, **overrides):
    values = {name: SecretStr(value) for name, value in TEST_KEYS.items()}
    values.update({"cv_storage_dir": cv_dir, "consent_policy_version": "2026-11"})
    values.update(overrides)
    return settings.model_copy(update=values)


@dataclass
class FrozenClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> datetime:
        self.now = self.now + timedelta(**delta)
        return self.now


@pytest.fixture
def frozen_clock(monkeypatch) -> FrozenClock:
    from app.core import clock

    frozen = FrozenClock(now_utc().replace(microsecond=0))
    monkeypatch.setattr(clock, "utcnow", frozen)
    return frozen


# ---- fake adapters (test injection only) ------------------------------------------------


@dataclass
class FakeCaptcha:
    result: bool = True
    error: Exception | None = None
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        self.calls.append((token, remote_ip))
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class FakeScanner:
    verdict: str = "CLEAN"
    error: Exception | None = None
    scanned: list[int] = field(default_factory=list)

    async def scan(self, data: bytes):
        from app.integrations.antivirus.client import ScanVerdict

        self.scanned.append(len(data))
        if self.error is not None:
            raise self.error
        return ScanVerdict(self.verdict)


def scanner_unavailable():
    from app.integrations.antivirus.client import ScannerUnavailableError

    return ScannerUnavailableError("scanner_timeout")


def captcha_unavailable():
    from app.integrations.captcha.client import CaptchaUnavailableError

    return CaptchaUnavailableError("captcha_timeout")


def make_storage(settings):
    from app.integrations.storage.encrypted_local import EncryptedLocalStorage

    return EncryptedLocalStorage(
        Path(settings.cv_storage_dir), settings.cv_encryption_key.get_secret_value().encode()
    )


@dataclass
class FlowApp:
    client: AsyncClient
    email: ScriptedEmailService
    scanner: FakeScanner
    captcha: FakeCaptcha
    settings: object
    storage: object


@pytest.fixture
async def flow_cleanup(apply_cleanup, tmp_path) -> AsyncIterator[Path]:
    cv_dir = tmp_path / "private-cv-store"
    cv_dir.mkdir()
    yield cv_dir


@pytest.fixture
async def flow_factory(flow_cleanup, settings, session_factory):
    """Build independent app instances that share the dedicated database and CV store."""
    from app.main import create_app
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as session:
        await seed_email_templates(session)
        await session.commit()

    contexts = []

    async def make(*, client_ip: str = "127.0.0.1", **settings_overrides) -> FlowApp:
        config = flow_settings(settings, flow_cleanup, **settings_overrides)
        email = ScriptedEmailService()
        # Transport kịch bản mô phỏng gửi thật thành công; guard 503 của API vẫn áp dụng cho Fake.
        email.simulated = False
        scanner = FakeScanner()
        captcha = FakeCaptcha()
        # Thiếu cấu hình kho: không inject, để app tự dựng và phải từ chối an toàn (503).
        configured = config.cv_storage_dir is not None and config.cv_encryption_key is not None
        storage = make_storage(config) if configured else None
        app = create_app(
            config, email_service=email, storage=storage, scanner=scanner, captcha=captcha
        )
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        client = AsyncClient(
            # Lỗi không lường trước được trả về như response 500 (không ném vào test).
            transport=ASGITransport(app=app, client=(client_ip, 50000), raise_app_exceptions=False),
            base_url="http://testserver",
            headers=ORIGIN,
        )
        contexts.append((lifespan, client))
        return FlowApp(client, email, scanner, captcha, config, storage)

    try:
        yield make
    finally:
        for lifespan, client in reversed(contexts):
            await client.aclose()
            await lifespan.__aexit__(None, None, None)


@pytest.fixture
async def flow(flow_factory) -> FlowApp:
    return await flow_factory()


def stored_files(cv_dir: Path) -> list[Path]:
    return [path for path in Path(cv_dir).rglob("*") if path.is_file()]


# ---- HTTP helpers ------------------------------------------------------------------------


def field_errors(response) -> dict[str, str]:
    """FastAPI-style 422 body: {"detail": [{"loc": [..., field], "msg": ...}]}."""
    assert response.status_code == 422, response.text
    return {str(item["loc"][-1]): item["msg"] for item in response.json()["detail"]}


def error_code(response) -> str:
    return response.json()["error"]["code"]


def upload_fields(**overrides) -> dict:
    fields = {
        "full_name": "Nguyễn Văn A",
        "email": "ung.vien@example.test",
        "phone": "0912345678",
        "consent": "true",
        "captcha_token": "captcha-pass",
    }
    fields.update(overrides)
    return {key: value for key, value in fields.items() if value is not None}


DEFAULT_FILE = ("cv.pdf", None, "application/pdf")


async def upload(client: AsyncClient, *, file=DEFAULT_FILE, **fields):
    files = None
    if file is not None:
        name, data, content_type = file
        files = {"file": (name, make_pdf() if data is None else data, content_type)}
    return await client.post(SUBMISSIONS_URL, data=upload_fields(**fields), files=files)


async def upload_ok(client: AsyncClient, **kwargs) -> dict:
    response = await upload(client, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def capability(submission: dict, job_id: int) -> dict:
    return {
        "submission_id": submission["submission_id"],
        "submission_token": submission["submission_token"],
        "job_id": job_id,
    }


async def request_otp(client: AsyncClient, submission: dict, job_id: int):
    return await client.post(OTP_URL, json=capability(submission, job_id))


async def submit(client: AsyncClient, submission: dict, job_id: int, code: str):
    return await client.post(
        APPLICATIONS_URL, json={**capability(submission, job_id), "otp_code": code}
    )


def last_otp(email: ScriptedEmailService) -> str:
    message = email.attempted[-1]
    match = OTP_PATTERN.search(message.text_body)
    assert match, "OTP email without a 6-digit code"
    return match.group(1)


def wrong_code(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


# ---- reference data ----------------------------------------------------------------------


@dataclass
class PostedJob:
    id: int
    criteria_set_id: int
    hr_id: uuid.UUID
    title: str


async def insert_open_job(
    session_factory,
    *,
    title: str = "Lập trình viên Backend",
    deadline: date | None = None,
    department: str = "Phòng Kỹ thuật",
    hr_id: uuid.UUID | None = None,
) -> PostedJob:
    """Commit an OPEN posting with one criteria set (weights 60/40) and an interviewer."""
    from app.modules.recruitment.service import company_today

    async with session_factory() as session:
        creator = hr_id or await insert_account(session, roles=["HR", "INTERVIEWER"])
        department_id = await insert_department(session, department)
        job_id = await session.scalar(
            text(
                "INSERT INTO job_postings (title, department_id, status, created_by, description,"
                " requirements, benefits, headcount, work_mode, location, deadline)"
                " VALUES (:title, :dept, 'DRAFT', :by, 'Mô tả công khai', 'Yêu cầu công khai',"
                " 'Quyền lợi công khai', 2, 'Toàn thời gian', 'Hà Nội', :deadline) RETURNING id"
            ),
            {
                "title": title,
                "dept": department_id,
                "by": creator,
                "deadline": deadline or company_today() + timedelta(days=30),
            },
        )
        set_id = await insert_criteria_set(session, job_id=job_id, created_by=creator)
        await session.execute(
            text(
                "INSERT INTO criteria"
                " (criteria_set_id, name, description, is_mandatory, weight, min_score)"
                " VALUES (:s, 'Tiêu chí nội bộ Java', 'Chấm nội bộ', true, 60, 50),"
                " (:s, 'Tiêu chí nội bộ Anh văn', 'Chấm nội bộ', false, 40, NULL)"
            ),
            {"s": set_id},
        )
        await session.execute(
            text("INSERT INTO job_interviewers (job_id, user_id) VALUES (:j, :u)"),
            {"j": job_id, "u": creator},
        )
        await session.execute(
            text(
                "UPDATE job_postings SET status = 'OPEN', current_criteria_set_id = :s"
                " WHERE id = :j"
            ),
            {"s": set_id, "j": job_id},
        )
        await session.commit()
    return PostedJob(job_id, set_id, creator, title)


async def close_job(session_factory, job_id: int) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE job_postings SET status = 'CLOSED', closed_at = now() WHERE id = :j"),
            {"j": job_id},
        )
        await session.commit()


async def set_deadline(session_factory, job_id: int, deadline: date) -> None:
    async with session_factory() as session:
        await session.execute(
            text("UPDATE job_postings SET deadline = :d WHERE id = :j"),
            {"d": deadline, "j": job_id},
        )
        await session.commit()


async def scalar(session_factory, sql: str, **params):
    async with session_factory() as session:
        return await session.scalar(text(sql), params)


async def rows(session_factory, sql: str, **params) -> list:
    async with session_factory() as session:
        return list((await session.execute(text(sql), params)).all())


class FailingTrigger:
    """Temporarily make INSERTs into ``table`` fail (dedicated test DB only)."""

    def __init__(self, session_factory, table: str) -> None:
        self.session_factory = session_factory
        self.table = table
        self.name = f"test_fail_{table}"

    async def __aenter__(self):
        async with self.session_factory() as session:
            await session.execute(
                text(
                    f"CREATE OR REPLACE FUNCTION {self.name}() RETURNS trigger LANGUAGE plpgsql"
                    " AS $$ BEGIN RAISE EXCEPTION 'injected test failure'; END; $$"
                )
            )
            await session.execute(
                text(
                    f"CREATE TRIGGER {self.name} BEFORE INSERT ON {self.table}"
                    f" FOR EACH ROW EXECUTE FUNCTION {self.name}()"
                )
            )
            await session.commit()
        return self

    async def __aexit__(self, *exc) -> None:
        async with self.session_factory() as session:
            await session.execute(text(f"DROP TRIGGER IF EXISTS {self.name} ON {self.table}"))
            await session.execute(text(f"DROP FUNCTION IF EXISTS {self.name}()"))
            await session.commit()
