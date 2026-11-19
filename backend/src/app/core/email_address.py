"""Single-mailbox validation shared by settings, SMTP and the outbox.

CR/LF are normalized away first (header injection, NFR18), then exactly one bare
``local@domain`` address must remain: no display name, list, whitespace or control
character. Syntax is checked with ``email-validator`` (no DNS/MX lookup, no network).
``test_environment=True`` accepts the reserved ``.test`` domain used by local
development, Mailpit and the test suite.
"""

from email_validator import EmailNotValidError, validate_email

_FORBIDDEN = frozenset(',;<>"\\')


def normalize_mailbox(value: str | None) -> str:
    """Return the normalized address or raise ``ValueError`` (never echoes the value)."""
    if value is None:
        raise ValueError("Email address is required")
    cleaned = value.replace("\r", " ").replace("\n", " ").strip()
    if (
        not cleaned
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in cleaned)
        or any(char in _FORBIDDEN for char in cleaned)
    ):
        raise ValueError("Email address must be exactly one mailbox")
    try:
        result = validate_email(
            cleaned,
            check_deliverability=False,
            test_environment=True,
            allow_quoted_local=False,
            allow_domain_literal=False,
            allow_display_name=False,
        )
    except EmailNotValidError:
        # Thông báo của thư viện có thể lặp lại địa chỉ; không đưa nó ra ngoài.
        raise ValueError("Email address must be exactly one mailbox") from None
    return result.normalized


def strip_line_breaks(value: str) -> str:
    """Header-safe single line: CR/LF become spaces."""
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())
