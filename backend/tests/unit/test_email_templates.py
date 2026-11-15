from app.integrations.email.templates import (
    invitation_message,
    password_link_url,
    recovery_message,
)

FRONTEND_URL = "https://hr.example.test"


def test_link_uses_configured_frontend_url_and_fragment() -> None:
    url = password_link_url(FRONTEND_URL, "raw-token-value")
    assert url == "https://hr.example.test/set-password#token=raw-token-value"
    assert password_link_url("https://hr.example.test/", "t") == (
        "https://hr.example.test/set-password#token=t"
    )


def test_invitation_message_contains_the_link_in_both_bodies() -> None:
    message = invitation_message(
        to="user@sis.hust.edu.vn",
        full_name="Nguyễn Văn A",
        token="invite-token",
        frontend_url=FRONTEND_URL,
    )
    assert message.to == "user@sis.hust.edu.vn"
    assert "Activate" in message.subject
    assert "24 hours" in message.text_body
    assert "invite-token" in message.text_body
    assert "invite-token" in message.html_body
    assert "Nguyễn Văn A" in message.text_body


def test_recovery_message_documents_the_shorter_expiry() -> None:
    message = recovery_message(
        to="user@sis.hust.edu.vn",
        full_name="Nguyễn Văn A",
        token="recovery-token",
        frontend_url=FRONTEND_URL,
    )
    assert "30 minutes" in message.text_body
    assert "30 minutes" in message.html_body.replace("\n", " ")
    assert "recovery-token" in message.text_body


def test_html_body_escapes_user_supplied_name() -> None:
    message = invitation_message(
        to="user@sis.hust.edu.vn",
        full_name='<script>alert("x")</script>',
        token="token-value",
        frontend_url=FRONTEND_URL,
    )
    assert "<script>" not in message.html_body
    assert "&lt;script&gt;" in message.html_body


def test_messages_never_contain_a_plaintext_password() -> None:
    message = invitation_message(
        to="user@sis.hust.edu.vn",
        full_name="User",
        token="token-value",
        frontend_url=FRONTEND_URL,
    )
    assert "password:" not in message.text_body.lower()
    assert "password:" not in message.html_body.lower()
