"""Invitation and recovery message templates.

Links carry the token in a URL fragment so it never reaches server logs or a
third-party referrer. Only the configured frontend URL is used.
"""

from html import escape

from app.integrations.email.client import EmailMessage

SET_PASSWORD_PATH = "/set-password"


def password_link_url(frontend_url: str, token: str) -> str:
    return f"{frontend_url.rstrip('/')}{SET_PASSWORD_PATH}#token={token}"


def invitation_message(*, to: str, full_name: str, token: str, frontend_url: str) -> EmailMessage:
    url = password_link_url(frontend_url, token)
    name = escape(full_name)
    return EmailMessage(
        to=to,
        subject="Activate your HR Chan account",
        text_body=(
            f"Hello {full_name},\n\n"
            "An HR Chan account was created for you. Set your password within 24 hours:\n\n"
            f"{url}\n\n"
            "If you were not expecting this invitation, ignore this message.\n"
        ),
        html_body=(
            f"<p>Hello {name},</p>"
            "<p>An HR Chan account was created for you. Set your password within 24 hours:</p>"
            f'<p><a href="{escape(url, quote=True)}">Set your password</a></p>'
            "<p>If you were not expecting this invitation, ignore this message.</p>"
        ),
    )


def recovery_message(*, to: str, full_name: str, token: str, frontend_url: str) -> EmailMessage:
    url = password_link_url(frontend_url, token)
    name = escape(full_name)
    return EmailMessage(
        to=to,
        subject="Reset your HR Chan password",
        text_body=(
            f"Hello {full_name},\n\n"
            "Use the link below within 30 minutes to set a new password:\n\n"
            f"{url}\n\n"
            "If you did not request this, ignore this message; your password stays unchanged.\n"
        ),
        html_body=(
            f"<p>Hello {name},</p>"
            "<p>Use the link below within 30 minutes to set a new password:</p>"
            f'<p><a href="{escape(url, quote=True)}">Set a new password</a></p>'
            "<p>If you did not request this, ignore this message; "
            "your password stays unchanged.</p>"
        ),
    )
