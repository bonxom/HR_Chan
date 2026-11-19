"""Restricted template rendering: only ``{snake_case}`` placeholders, single pass.

No ``str.format``/eval: attribute access, indexing, conversions and format specs are
rejected. Text keeps values verbatim; HTML escapes every literal segment and value.
Subjects never keep CR/LF (NFR18). Secret variables are replaced by ``REDACTION_MARK``
in the redacted copy that is the only version stored in the outbox after delivery.
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from html import escape

from app.core.email_address import normalize_mailbox, strip_line_breaks

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
VARIABLE_NAME = re.compile(r"[a-z][a-z0-9_]*")
REDACTION_MARK = "[đã ẩn]"
SUBJECT_MAX = 255


class TemplateRenderError(ValueError):
    """Template uses an invalid placeholder or a variable has no value."""


class InvalidRecipientError(ValueError):
    """The recipient is not exactly one mailbox."""


@dataclass(frozen=True, repr=False)
class RenderedEmail:
    subject: str
    text_body: str
    html_body: str

    def __repr__(self) -> str:
        return "RenderedEmail(<content hidden>)"


@dataclass(frozen=True, repr=False)
class RenderResult:
    full: RenderedEmail
    redacted: RenderedEmail

    def __repr__(self) -> str:
        return "RenderResult(<content hidden>)"


def placeholders(text: str) -> list[str]:
    names = []
    for match in PLACEHOLDER.finditer(text):
        name = match.group(1)
        if not VARIABLE_NAME.fullmatch(name):
            # Không lặp lại nội dung placeholder lạ trong thông báo lỗi.
            raise TemplateRenderError("Template placeholders must look like {snake_case_name}")
        names.append(name)
    return names


def _substitute(text: str, values: Mapping[str, str], *, html: bool) -> str:
    parts: list[str] = []
    position = 0
    for match in PLACEHOLDER.finditer(text):
        literal = text[position : match.start()]
        value = values[match.group(1)]
        parts.append(escape(literal) if html else literal)
        parts.append(escape(value) if html else value)
        position = match.end()
    tail = text[position:]
    parts.append(escape(tail) if html else tail)
    return "".join(parts)


def _render(subject: str, body: str, values: Mapping[str, str]) -> RenderedEmail:
    rendered_subject = strip_line_breaks(_substitute(subject, values, html=False))
    text_body = _substitute(body, values, html=False)
    html_inner = _substitute(body, values, html=True).replace("\r\n", "\n")
    html_body = (
        '<!DOCTYPE html><html><body><div style="font-family:sans-serif">'
        + html_inner.replace("\n", "<br>\n")
        + "</div></body></html>"
    )
    return RenderedEmail(rendered_subject[:SUBJECT_MAX], text_body, html_body)


def render_template(
    subject: str,
    body: str,
    values: Mapping[str, object],
    *,
    required_vars: Collection[str],
    secret_vars: Collection[str] = frozenset(),
) -> RenderResult:
    used = set(placeholders(subject)) | set(placeholders(body))
    for name in required_vars:
        if not VARIABLE_NAME.fullmatch(name):
            raise TemplateRenderError("Required variables must be snake_case names")
    needed = used | set(required_vars)
    missing = sorted(name for name in needed if values.get(name) is None)
    if missing:
        # Chỉ nêu tên biến, không bao giờ in giá trị (có thể là OTP/token).
        raise TemplateRenderError(f"Missing template variable(s): {', '.join(missing)}")
    full_values = {name: str(values[name]) for name in needed}
    redacted_values = {
        name: (REDACTION_MARK if name in secret_vars else value)
        for name, value in full_values.items()
    }
    return RenderResult(
        full=_render(subject, body, full_values),
        redacted=_render(subject, body, redacted_values),
    )


def normalize_recipient(to: str) -> str:
    try:
        return normalize_mailbox(to)
    except ValueError:
        raise InvalidRecipientError("Recipient must be exactly one email address") from None
