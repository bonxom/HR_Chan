# CLI email: seed-email-templates chạy lại an toàn; send-test-email đi qua sendNow/outbox,
# outbox chỉ giữ bản che, không in nội dung/mã/bí mật, exit code khác 0 khi FAILED.
"""``python -m app.cli seed-email-templates`` and ``send-test-email`` (plan task 9).

Contract (``app.cli``):

* ``seed-email-templates`` -> exit 0, payload ``{"status": "seeded", "inserted": n}``;
  rerunning inserts 0 and keeps templates an Admin edited.
* ``send-test-email --to ADDRESS [--template CODE]`` (default ``OTP_APPLY`` with built-in
  sample values; secrets masked like any OTP mail) uses ``NotificationService.sendNow``
  with ``app.cli.build_email_service(settings)`` (module-level name). Payload
  ``{"status": "sent", "outbox_id": id, "simulated": bool}`` with exit 0, or
  ``{"status": "failed", "error_code": code}`` with exit 1 (also for an invalid address or
  a missing template). Output never contains the body, the sample code or credentials.
"""

import json

import pytest
from application_flow_support import OTP_PATTERN
from apply_support import ScriptedEmailService, apply_cleanup, outbox_rows
from pydantic import SecretStr
from sqlalchemy import text

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup"]

OUTBOX_KEY = "test-outbox-encryption-key-0123456789abcdef"
SMTP_PASSWORD = "smtp-password-placeholder"


@pytest.fixture
def cli_settings(settings):
    return settings.model_copy(
        update={
            "outbox_encryption_key": SecretStr(OUTBOX_KEY),
            "smtp_password": SecretStr(SMTP_PASSWORD),
        }
    )


@pytest.fixture
def sender(monkeypatch) -> ScriptedEmailService:
    from app import cli

    scripted = ScriptedEmailService()
    monkeypatch.setattr(cli, "build_email_service", lambda settings: scripted)
    return scripted


async def run(settings, *argv):
    from app import cli

    return await cli.dispatch(cli.build_parser().parse_args(list(argv)), settings)


async def drop_templates(session_factory) -> None:
    # clean_database seeds templates before each DB test; start from an empty table here.
    async with session_factory() as session:
        await session.execute(text("DELETE FROM email_templates"))
        await session.commit()


async def test_seed_command_is_idempotent_and_keeps_edits(
    apply_cleanup, session_factory, cli_settings
) -> None:
    await drop_templates(session_factory)
    code, payload = await run(cli_settings, "seed-email-templates")
    assert code == 0
    assert payload["status"] == "seeded" and payload["inserted"] >= 4

    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE email_templates SET subject = 'Đã chỉnh {job_title}'"
                " WHERE code = 'OTP_APPLY'"
            )
        )
        await session.commit()
    code, payload = await run(cli_settings, "seed-email-templates")
    assert (code, payload["inserted"]) == (0, 0)
    async with session_factory() as session:
        subject = await session.scalar(
            text("SELECT subject FROM email_templates WHERE code = 'OTP_APPLY'")
        )
    assert subject == "Đã chỉnh {job_title}"


async def test_send_test_email_goes_through_send_now_and_masks_the_outbox(
    apply_cleanup, session_factory, cli_settings, sender
) -> None:
    await run(cli_settings, "seed-email-templates")

    code, payload = await run(cli_settings, "send-test-email", "--to", "thu.nghiem@example.test")

    assert code == 0, payload
    assert payload["status"] == "sent" and isinstance(payload["outbox_id"], int)
    [message] = sender.delivered
    assert message.to == "thu.nghiem@example.test"
    sample = OTP_PATTERN.search(message.text_body).group(1)
    [row] = await outbox_rows(session_factory, "OTP_APPLY")
    assert (row.id, row.status) == (payload["outbox_id"], "SENT")
    assert sample not in row.body and sample not in row.subject
    printed = json.dumps(payload, ensure_ascii=False)
    for leaked in (sample, message.text_body[:40], SMTP_PASSWORD, OUTBOX_KEY):
        assert leaked not in printed


async def test_failed_test_email_exits_non_zero_with_only_the_code(
    apply_cleanup, session_factory, cli_settings, sender
) -> None:
    from app.integrations.email.errors import PermanentEmailError

    await run(cli_settings, "seed-email-templates")
    sender.outcomes = [PermanentEmailError("smtp_550")]

    code, payload = await run(cli_settings, "send-test-email", "--to", "khong.nhan@example.test")

    assert code == 1
    assert payload == {"status": "failed", "error_code": "smtp_550"}
    [row] = await outbox_rows(session_factory, "OTP_APPLY")
    assert row.status == "FAILED"


@pytest.mark.parametrize(
    ("argv", "seeded"),
    [
        (("send-test-email", "--to", "a@example.test\r\nBcc: b@example.test"), True),
        (("send-test-email", "--to", "a@example.test", "--template", "NO_SUCH"), True),
        (("send-test-email", "--to", "a@example.test"), False),
    ],
    ids=["injected-address", "unknown-template", "templates-not-seeded"],
)
async def test_unusable_requests_fail_without_sending(
    apply_cleanup, session_factory, cli_settings, sender, argv, seeded
) -> None:
    if seeded:
        await run(cli_settings, "seed-email-templates")
    else:
        await drop_templates(session_factory)
    code, payload = await run(cli_settings, *argv)
    assert code == 1
    assert payload["status"] == "failed" and payload["error_code"]
    assert sender.attempted == []
    assert await outbox_rows(session_factory) == []


def test_main_prints_json_without_secrets(apply_cleanup, cli_settings, sender, capsys) -> None:
    from app import cli

    assert cli.main(["seed-email-templates"], cli_settings) == 0
    assert cli.main(["send-test-email", "--to", "in.ra@example.test"], cli_settings) == 0
    output = capsys.readouterr().out
    payloads = [json.loads(line) for line in output.splitlines() if line.strip()]
    assert payloads[-1]["status"] == "sent"
    sample = OTP_PATTERN.search(sender.delivered[-1].text_body).group(1)
    assert sample not in output and SMTP_PASSWORD not in output
