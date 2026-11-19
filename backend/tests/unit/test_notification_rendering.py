# Render mẫu email: chỉ {ten_bien}, thiếu biến là lỗi, escape HTML từng giá trị,
# loại CR/LF khỏi tiêu đề, che biến bí mật và chuẩn hóa đúng một người nhận.
"""Restricted template rendering (plan task 3).

Contract of ``app.modules.notifications.rendering``:

* ``render_template(subject, body, values, *, required_vars, secret_vars=frozenset())``
  returns ``RenderResult`` with ``.full`` and ``.redacted``; each is a ``RenderedEmail``
  (``subject``, ``text_body``, ``html_body``). ``.redacted`` replaces every secret value
  with ``REDACTION_MARK``.
* Only ``{snake_case}`` placeholders are allowed; anything else (attribute/index access,
  conversions, format specs, positional fields) raises ``TemplateRenderError``. A missing
  required or referenced variable raises ``TemplateRenderError`` naming the variable but
  never echoing a value. Substitution is single-pass: values are data, never re-expanded.
* Text keeps values verbatim; HTML escapes each value. CR/LF never survive in a subject.
* ``normalize_recipient(to)`` strips surrounding whitespace, rejects CR/LF and anything
  other than exactly one mailbox with ``InvalidRecipientError``.
"""

import pytest

BODY = "Chào {full_name},\nMã của bạn là {otp_code}, hiệu lực {ttl_minutes} phút ({job_title})."
SUBJECT = "Mã xác thực ứng tuyển {job_title}"
VALUES = {
    "full_name": "Nguyễn Văn A",
    "otp_code": "482913",
    "ttl_minutes": "5",
    "job_title": "Lập trình viên Backend",
}
REQUIRED = ("full_name", "otp_code", "ttl_minutes", "job_title")


def render(subject=SUBJECT, body=BODY, values=None, required=REQUIRED, secret=frozenset()):
    from app.modules.notifications.rendering import render_template

    return render_template(
        subject,
        body,
        dict(VALUES if values is None else values),
        required_vars=required,
        secret_vars=frozenset(secret),
    )


def test_substitutes_every_placeholder_in_subject_text_and_html() -> None:
    full = render().full
    assert full.subject == "Mã xác thực ứng tuyển Lập trình viên Backend"
    for value in VALUES.values():
        assert value in full.text_body
        assert value in full.html_body
    assert "{" not in full.text_body and "}" not in full.text_body


def test_html_escapes_each_value_and_text_keeps_it_verbatim() -> None:
    script = '<script>alert("x")</script>'
    full = render(values={**VALUES, "full_name": script}).full
    assert script in full.text_body
    assert "<script>" not in full.html_body
    assert "&lt;script&gt;" in full.html_body


def test_values_are_not_expanded_a_second_time() -> None:
    full = render(values={**VALUES, "full_name": "{otp_code}"}).full
    assert full.text_body.count("482913") == 1
    assert "{otp_code}" in full.text_body


@pytest.mark.parametrize("missing", ["full_name", "otp_code", "job_title"])
def test_missing_variable_is_an_error_without_echoing_values(missing) -> None:
    from app.modules.notifications.rendering import TemplateRenderError

    values = {key: value for key, value in VALUES.items() if key != missing}
    with pytest.raises(TemplateRenderError) as error:
        render(values=values)
    assert missing in str(error.value)
    assert "482913" not in str(error.value)


def test_placeholder_used_but_not_required_still_needs_a_value() -> None:
    from app.modules.notifications.rendering import TemplateRenderError

    with pytest.raises(TemplateRenderError):
        render(body=BODY + " {extra_note}", required=REQUIRED)


@pytest.mark.parametrize(
    "placeholder",
    [
        "{full_name.__class__}",
        "{full_name[0]}",
        "{full_name!r}",
        "{full_name:>40}",
        "{0}",
        "{}",
        "{FullName}",
        "{full name}",
        "{__import__('os')}",
    ],
)
def test_only_simple_snake_case_placeholders_are_allowed(placeholder) -> None:
    from app.modules.notifications.rendering import TemplateRenderError

    with pytest.raises(TemplateRenderError):
        render(body=BODY + " " + placeholder)


def test_subject_never_keeps_line_breaks() -> None:
    full = render(values={**VALUES, "job_title": "Dev\r\nBcc: evil@example.test\nX: y"}).full
    assert "\r" not in full.subject and "\n" not in full.subject


def test_redacted_copy_hides_secrets_everywhere_and_keeps_other_values() -> None:
    from app.modules.notifications.rendering import REDACTION_MARK

    result = render(secret={"otp_code"})
    assert "482913" in result.full.text_body and "482913" in result.full.html_body
    for part in (result.redacted.subject, result.redacted.text_body, result.redacted.html_body):
        assert "482913" not in part
    assert REDACTION_MARK in result.redacted.text_body
    assert "Nguyễn Văn A" in result.redacted.text_body
    assert REDACTION_MARK and "482913" not in REDACTION_MARK


def test_secret_in_subject_is_redacted_too() -> None:
    result = render(subject="Mã {otp_code}", secret={"otp_code"})
    assert "482913" in result.full.subject
    assert "482913" not in result.redacted.subject


def test_render_result_repr_does_not_reveal_secrets() -> None:
    result = render(secret={"otp_code"})
    assert "482913" not in repr(result)


@pytest.mark.parametrize(
    "to",
    [
        "victim@example.test\r\nBcc: evil@example.test",
        "victim@example.test\nevil@example.test",
        "victim@example.test, evil@example.test",
        "victim@example.test;evil@example.test",
        "no-at-sign",
        "@example.test",
        "",
    ],
)
def test_recipient_must_be_exactly_one_mailbox(to) -> None:
    from app.modules.notifications.rendering import InvalidRecipientError, normalize_recipient

    with pytest.raises(InvalidRecipientError):
        normalize_recipient(to)


def test_recipient_surrounding_whitespace_is_trimmed() -> None:
    from app.modules.notifications.rendering import normalize_recipient

    assert normalize_recipient("  ung.vien@example.test ") == "ung.vien@example.test"
    # CR/LF are normalized away first, then exactly one mailbox must remain.
    assert normalize_recipient("ung.vien@example.test\r\n") == "ung.vien@example.test"
