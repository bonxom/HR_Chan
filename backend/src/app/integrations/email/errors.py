"""Classified delivery errors carrying only a normalized, non-sensitive code.

Codes: ``smtp_timeout``, ``smtp_connection``, ``smtp_<status>`` (server reply),
``invalid_recipient``, ``smtp_not_supported``, ``smtp_error`` (anything unexpected).
Raw server text and exception messages are never stored here.
"""


class EmailDeliveryError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.code!r})"


class TemporaryEmailError(EmailDeliveryError):
    """Network error, timeout or SMTP 4xx: may be retried."""


class PermanentEmailError(EmailDeliveryError):
    """Invalid address or SMTP 5xx rejection: never retried."""
