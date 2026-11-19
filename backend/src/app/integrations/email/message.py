"""Provider-independent email message (no imports of adapters, so no import cycle)."""

from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str
    # Message-ID ổn định theo dòng outbox để đối soát khi SMTP có thể nhận trùng.
    message_id: str | None = None

    def __repr__(self) -> str:
        # Body/recipient may hold tokens, OTP codes or personal data: never print them.
        return f"EmailMessage(message_id={self.message_id!r})"
