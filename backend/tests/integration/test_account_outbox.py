# Email tài khoản đi qua outbox: tài khoản, liên kết đặt mật khẩu, nhật ký và thư cùng một
# giao dịch; trả "queued", chưa gọi SMTP; rollback không để lại thư; quên mật khẩu vẫn trả
# cùng một thông báo. Fixture riêng (không dùng fixture tài khoản cũ của conftest).
"""Account emails through the outbox (plan task 5).

Contract:

* ``create_account``, ``bootstrap_admin``, ``resend_invitation``, ``unlock_account`` and
  ``request_password_email`` keep their signatures (``email_client`` is still accepted)
  but enqueue ACCOUNT_INVITATION / PASSWORD_RECOVERY with
  ``NotificationService.enqueue`` inside the same transaction as the account, password
  link and audit event, with the link as a secret variable. ``email_delivery`` is
  ``"queued"``; no SMTP call happens before the worker runs.
* The queued mail, once delivered by ``deliver_due_batch``, carries a working link.
* If the mail cannot be queued (e.g. template missing) or the audit write fails, nothing
  of the operation is committed.
* Password recovery answers identically for every account state; only eligible
  accounts get a PASSWORD_RECOVERY row. The CLI ``bootstrap-admin`` reports ``queued``.
"""

import re
import uuid
from datetime import timedelta

import pytest
from apply_support import ScriptedEmailService, apply_cleanup, now_utc, outbox_rows
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text

from app.core.exceptions import Failure

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]

ORIGIN = {"Origin": "http://localhost:5173"}
OUTBOX_KEY = "test-outbox-encryption-key-0123456789abcdef"
ADMIN_EMAIL = "quan.tri@sis.hust.edu.vn"
ADMIN_PASSWORD = "administrator-password-value"
TOKEN_IN_LINK = re.compile(r"#token=([A-Za-z0-9_\-]+)")


@pytest.fixture
def queued_settings(settings):
    return settings.model_copy(update={"outbox_encryption_key": SecretStr(OUTBOX_KEY)})


@pytest.fixture
async def templates(apply_cleanup, session_factory) -> None:
    from app.modules.notifications.seeds import seed_email_templates

    async with session_factory() as session:
        await seed_email_templates(session)
        await session.commit()


@pytest.fixture
def recorder() -> ScriptedEmailService:
    return ScriptedEmailService()


async def insert_active(
    session_factory,
    *,
    email: str,
    account_type: str = "EMPLOYEE",
    roles: list[str] | None = None,
    status: str = "ACTIVE",
    password: str = ADMIN_PASSWORD,
) -> uuid.UUID:
    from app.modules.auth.passwords import hash_password_async

    account_id = uuid.uuid4()
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO accounts (id, full_name, email, account_type, roles, status,"
                " password_hash) VALUES (:id, 'Người dùng thử', :email,"
                " CAST(:type AS account_type), CAST(:roles AS text[]),"
                " CAST(:status AS account_status), :hash)"
            ),
            {
                "id": account_id,
                "email": email,
                "type": account_type,
                "roles": roles if roles is not None else ["HR"],
                "status": status,
                "hash": await hash_password_async(password),
            },
        )
        await session.commit()
    return account_id


async def counts(session_factory, email: str) -> dict[str, int]:
    async with session_factory() as session:
        account_id = await session.scalar(
            text("SELECT id FROM accounts WHERE email = :e"), {"e": email}
        )
        return {
            "accounts": int(account_id is not None),
            "links": await session.scalar(
                text("SELECT count(*) FROM auth_password_links WHERE account_id = :a"),
                {"a": account_id},
            )
            if account_id
            else 0,
            "audit": await session.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action = 'account.created'"
                    " AND target_id = :a"
                ),
                {"a": str(account_id)},
            )
            if account_id
            else 0,
            "outbox": await session.scalar(
                text("SELECT count(*) FROM email_outbox WHERE to_email = :e"), {"e": email}
            ),
        }


async def deliver_all(session_factory, settings):
    from app.integrations.email.service import FakeEmailService
    from app.modules.notifications.worker import deliver_due_batch

    sender = FakeEmailService()
    await deliver_due_batch(session_factory, sender, settings, now_utc())
    return sender.sent


async def create(session_factory, settings, recorder, email: str):
    from app.modules.accounts import service as account_service
    from app.modules.accounts.rules import AccountType

    async with session_factory() as session:
        return await account_service.create_account(
            session,
            actor_id=None,
            full_name="Nhân viên mới",
            email=email,
            account_type=AccountType.EMPLOYEE,
            roles=["HR"],
            settings=settings,
            email_client=recorder,
        )


# ---- creation -----------------------------------------------------------------------------


async def test_account_creation_queues_the_invitation_in_the_same_transaction(
    templates, session_factory, queued_settings, recorder
) -> None:
    from app.modules.accounts import service as account_service

    email = "nhan.vien.moi@sis.hust.edu.vn"
    result = await create(session_factory, queued_settings, recorder, email)

    assert isinstance(result, account_service.AccountDeliveryResult), result
    assert result.email_delivery == "queued"
    assert recorder.attempted == []  # SMTP not called before the worker
    assert await counts(session_factory, email) == {
        "accounts": 1,
        "links": 1,
        "audit": 1,
        "outbox": 1,
    }
    [row] = await outbox_rows(session_factory, "ACCOUNT_INVITATION")
    assert (row.status, row.attempts, row.user_id) == ("PENDING", 0, result.account.id)
    assert "#token=" not in row.body

    [message] = await deliver_all(session_factory, queued_settings)
    token = TOKEN_IN_LINK.search(message.text_body).group(1)
    async with session_factory() as session:
        completed = await account_service.complete_password_link(
            session, token=token, new_password="new-password-value", settings=queued_settings
        )
    assert not isinstance(completed, Failure), completed
    [sent] = await outbox_rows(session_factory, "ACCOUNT_INVITATION")
    assert sent.status == "SENT" and token not in sent.body


async def test_missing_template_rolls_back_the_whole_creation(
    apply_cleanup, session_factory, queued_settings, recorder
) -> None:
    email = "khong.mau@sis.hust.edu.vn"
    async with session_factory() as session:  # clean_database seeds templates; remove them
        await session.execute(text("DELETE FROM email_templates"))
        await session.commit()
    try:
        await create(session_factory, queued_settings, recorder, email)
    except Exception:  # either a Failure or an exception is acceptable, never a partial row
        pass
    assert await counts(session_factory, email) == {
        "accounts": 0,
        "links": 0,
        "audit": 0,
        "outbox": 0,
    }
    assert recorder.attempted == []


async def test_failed_audit_rolls_back_the_queued_mail(
    templates, session_factory, queued_settings, recorder, monkeypatch
) -> None:
    from app.modules.accounts import service as account_service

    async def failing(session, event) -> None:
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(account_service, "record_event", failing)
    email = "loi.nhat.ky@sis.hust.edu.vn"
    with pytest.raises(RuntimeError):
        await create(session_factory, queued_settings, recorder, email)
    assert (await counts(session_factory, email))["outbox"] == 0
    assert (await counts(session_factory, email))["accounts"] == 0


async def test_bootstrap_resend_and_unlock_are_queued_too(
    templates, session_factory, queued_settings, recorder
) -> None:
    from app.modules.accounts import service as account_service

    admin_id = await insert_active(
        session_factory, email=ADMIN_EMAIL, account_type="ADMIN", roles=[]
    )
    created = await create(
        session_factory, queued_settings, recorder, "cho.kich.hoat@sis.hust.edu.vn"
    )
    locked_id = await insert_active(
        session_factory, email="bi.khoa@sis.hust.edu.vn", status="LOCKED"
    )

    async with session_factory() as session:
        resent = await account_service.resend_invitation(
            session,
            actor_id=admin_id,
            account_id=created.account.id,
            settings=queued_settings,
            email_client=recorder,
            now=now_utc() + timedelta(minutes=2),  # past the per-account email cooldown
        )
    async with session_factory() as session:
        unlocked = await account_service.unlock_account(
            session,
            actor_id=admin_id,
            account_id=locked_id,
            settings=queued_settings,
            email_client=recorder,
        )

    assert resent.email_delivery == "queued" and unlocked.email_delivery == "queued"
    assert recorder.attempted == []
    assert len(await outbox_rows(session_factory, "ACCOUNT_INVITATION")) == 2
    assert len(await outbox_rows(session_factory, "PASSWORD_RECOVERY")) == 1


async def test_cli_bootstrap_reports_queued_without_printing_the_link(
    templates, session_factory, queued_settings, monkeypatch
) -> None:
    from app import cli

    values = cli.build_parser().parse_args(
        ["bootstrap-admin", "--email", ADMIN_EMAIL, "--name", "Quản trị viên"]
    )
    code, payload = await cli.dispatch(values, queued_settings)

    assert code == 0
    assert payload["email_delivery"] == "queued"
    assert "token" not in str(payload).lower()
    [row] = await outbox_rows(session_factory, "ACCOUNT_INVITATION")
    assert row.to_email == ADMIN_EMAIL and row.status == "PENDING"


# ---- HTTP: admin creation and generic recovery ---------------------------------------------


@pytest.fixture
async def http(templates, queued_settings, recorder):
    from app.main import create_app

    app = create_app(queued_settings, email_client=recorder)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver", headers=ORIGIN
        ) as client:
            yield client


async def test_admin_api_reports_queued_delivery(http, session_factory, recorder) -> None:
    await insert_active(session_factory, email=ADMIN_EMAIL, account_type="ADMIN", roles=[])
    login = await http.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await http.post(
        "/api/v1/accounts",
        json={
            "full_name": "Nhân viên API",
            "email": "qua.api@sis.hust.edu.vn",
            "account_type": "EMPLOYEE",
            "roles": ["HR"],
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["email_delivery"] == "queued"
    assert recorder.attempted == []
    assert len(await outbox_rows(session_factory, "ACCOUNT_INVITATION")) == 1


async def test_recovery_answer_is_identical_and_only_eligible_accounts_get_mail(
    http, session_factory, recorder
) -> None:
    await insert_active(session_factory, email="dang.lam@sis.hust.edu.vn")
    await insert_active(session_factory, email="da.khoa@sis.hust.edu.vn", status="LOCKED")

    answers = []
    for email in (
        "dang.lam@sis.hust.edu.vn",
        "khong.ton.tai@sis.hust.edu.vn",
        "da.khoa@sis.hust.edu.vn",
    ):
        response = await http.post("/api/v1/auth/password/recovery", json={"email": email})
        answers.append((response.status_code, response.json()))

    assert len(set(map(str, answers))) == 1
    assert answers[0][0] == 202
    assert "email_delivery" not in str(answers[0][1])
    rows = await outbox_rows(session_factory, "PASSWORD_RECOVERY")
    assert [row.to_email for row in rows] == ["dang.lam@sis.hust.edu.vn"]
    assert "#token=" not in rows[0].body
    assert recorder.attempted == []
