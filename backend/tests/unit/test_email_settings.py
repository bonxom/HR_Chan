# Cấu hình email: biến mới, alias tương thích, cấu hình mâu thuẫn và chế độ fake.
# Không đọc backend/.env (_env_file=None); mọi giá trị đều giả, không có secret thật.
"""Email settings and the provider factory (plan task 2).

Contract (approved spec "SMTP và hợp đồng dịch vụ"):

* ``EMAIL_PROVIDER=fake|smtp``; ``SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS/USE_SSL``;
  ``MAIL_FROM_ADDRESS/NAME``. Settings fields: ``email_provider``, ``smtp_use_tls``,
  ``smtp_use_ssl``, ``mail_from_address``, ``mail_from_name`` (plus the existing
  ``smtp_host``, ``smtp_port``, ``smtp_username``, ``smtp_password``,
  ``smtp_timeout_seconds``).
* Legacy aliases stay accepted: ``SMTP_STARTTLS`` -> use TLS, ``SMTP_FROM_EMAIL`` ->
  from address, ``SMTP_FROM_NAME`` -> from name. Old and new names with different values
  are a configuration error; equal values are fine.
* TLS and SSL together, SMTP without a host, or an invalid sender are rejected.
* ``build_email_service(settings)`` returns ``FakeEmailService`` (simulation only) or
  ``SmtpEmailService``.

The default of ``EMAIL_PROVIDER`` is deliberately not asserted here (see the report).
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

ENV_NAMES = (
    "EMAIL_PROVIDER",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_STARTTLS",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "MAIL_FROM_ADDRESS",
    "MAIL_FROM_NAME",
    "SMTP_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_email_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def smtp_settings(**overrides) -> Settings:
    values = {
        "email_provider": "smtp",
        "smtp_host": "smtp.example.test",
        "smtp_port": 587,
        "mail_from_address": "no-reply@sis.hust.edu.vn",
        "mail_from_name": "HR Chan",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# ---- new variables --------------------------------------------------------------------


def test_reads_the_new_variables_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password-placeholder")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    monkeypatch.setenv("MAIL_FROM_ADDRESS", "sender@example.test")
    monkeypatch.setenv("MAIL_FROM_NAME", "Tuyển dụng HR Chan")

    settings = Settings(_env_file=None)

    assert settings.email_provider == "smtp"
    assert (settings.smtp_host, settings.smtp_port) == ("smtp.gmail.com", 587)
    assert settings.smtp_username == "sender@example.test"
    assert settings.smtp_password.get_secret_value() == "app-password-placeholder"
    assert (settings.smtp_use_tls, settings.smtp_use_ssl) == (True, False)
    assert settings.mail_from_address == "sender@example.test"
    assert settings.mail_from_name == "Tuyển dụng HR Chan"


def test_password_is_secret_and_not_in_repr() -> None:
    settings = smtp_settings(smtp_password="app-password-placeholder")
    assert "app-password-placeholder" not in repr(settings)
    assert "app-password-placeholder" not in str(settings.model_dump())


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, email_provider="sendgrid")


# ---- legacy aliases -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("legacy", "value", "field", "expected"),
    [
        ("SMTP_STARTTLS", "true", "smtp_use_tls", True),
        (
            "SMTP_FROM_EMAIL",
            "legacy@sis.hust.edu.vn",
            "mail_from_address",
            "legacy@sis.hust.edu.vn",
        ),
        ("SMTP_FROM_NAME", "HR Chan cũ", "mail_from_name", "HR Chan cũ"),
    ],
)
def test_legacy_names_are_still_accepted(monkeypatch, legacy, value, field, expected) -> None:
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv(legacy, value)
    assert getattr(Settings(_env_file=None), field) == expected


@pytest.mark.parametrize(
    ("legacy", "new", "legacy_value", "new_value"),
    [
        ("SMTP_STARTTLS", "SMTP_USE_TLS", "true", "false"),
        ("SMTP_FROM_EMAIL", "MAIL_FROM_ADDRESS", "a@sis.hust.edu.vn", "b@sis.hust.edu.vn"),
        ("SMTP_FROM_NAME", "MAIL_FROM_NAME", "Tên A", "Tên B"),
    ],
)
def test_conflicting_legacy_and_new_values_are_rejected(
    monkeypatch, legacy, new, legacy_value, new_value
) -> None:
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv(legacy, legacy_value)
    monkeypatch.setenv(new, new_value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("legacy", "new", "value"),
    [
        ("SMTP_STARTTLS", "SMTP_USE_TLS", "true"),
        ("SMTP_FROM_EMAIL", "MAIL_FROM_ADDRESS", "same@sis.hust.edu.vn"),
        ("SMTP_FROM_NAME", "MAIL_FROM_NAME", "Cùng tên"),
    ],
)
def test_equal_legacy_and_new_values_are_accepted(monkeypatch, legacy, new, value) -> None:
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv(legacy, value)
    monkeypatch.setenv(new, value)
    Settings(_env_file=None)


# ---- contradictory or unsafe configuration --------------------------------------------


def test_tls_and_ssl_together_are_rejected() -> None:
    with pytest.raises(ValidationError):
        smtp_settings(smtp_use_tls=True, smtp_use_ssl=True)


def test_smtp_provider_requires_a_host() -> None:
    with pytest.raises(ValidationError):
        smtp_settings(smtp_host=None)
    with pytest.raises(ValidationError):
        smtp_settings(smtp_host="")


@pytest.mark.parametrize(
    "sender",
    [
        "not-an-address",
        "@sis.hust.edu.vn",
        "a@b@sis.hust.edu.vn",
        "no-reply@sis.hust.edu.vn\r\nBcc: evil@example.test",
        "one@example.test, two@example.test",
    ],
)
def test_invalid_sender_address_is_rejected(sender: str) -> None:
    with pytest.raises(ValidationError):
        smtp_settings(mail_from_address=sender)


def test_sender_name_cannot_inject_headers() -> None:
    with pytest.raises(ValidationError):
        smtp_settings(mail_from_name="HR Chan\r\nBcc: evil@example.test")


def test_timeout_defaults_to_ten_seconds_and_cannot_exceed_it() -> None:
    assert Settings(_env_file=None).smtp_timeout_seconds == 10
    for value in (0, -1, 10.5, 60):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, smtp_timeout_seconds=value)


def test_existing_test_settings_without_smtp_still_load() -> None:
    # tests/conftest.py builds Settings(smtp_host=None) without EMAIL_PROVIDER for every
    # account test; whatever the default provider is, that baseline must keep loading.
    Settings(_env_file=None, smtp_host=None)


# ---- provider factory -----------------------------------------------------------------


def test_fake_provider_is_an_explicit_simulation() -> None:
    from app.integrations.email.service import FakeEmailService, build_email_service

    service = build_email_service(Settings(_env_file=None, email_provider="fake"))
    assert isinstance(service, FakeEmailService)
    assert service.simulated is True
    assert service.sent == []


def test_smtp_provider_builds_the_smtp_service() -> None:
    from app.integrations.email.service import SmtpEmailService, build_email_service

    service = build_email_service(smtp_settings())
    assert isinstance(service, SmtpEmailService)
    assert service.simulated is False


async def test_fake_service_records_messages_without_network() -> None:
    from app.integrations.email.client import EmailMessage
    from app.integrations.email.service import FakeEmailService

    service = FakeEmailService()
    message = EmailMessage(
        to="recipient@example.test", subject="Chủ đề", text_body="Nội dung", html_body="<p>x</p>"
    )
    await service.send(message)
    assert service.sent == [message]
