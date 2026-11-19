# Kiểm tra địa chỉ email một hộp thư: cú pháp chặt (email-validator, không DNS),
# chuẩn hóa CR/LF, nhận .test cho dev/test, lỗi không lặp lại giá trị.
"""``app.core.email_address.normalize_mailbox`` (foundation fix, Codex early review).

Malformed syntax and control characters must be rejected up front, so they become a
permanent ``invalid_recipient`` instead of a temporary SMTP error that is retried.
"""

import pytest

from app.core.email_address import normalize_mailbox


@pytest.mark.parametrize(
    "value",
    [
        "a@.",
        "a@-bad..example",
        "a..b@example.com",
        "a\x00b@example.com",
        "a\tb@example.com",
        ".a@example.com",
        "a.@example.com",
        "a@example..com",
        "a@exa mple.com",
        "a@",
        "@example.com",
        "a@b@example.com",
        '"a b"@example.com',
        "a@[127.0.0.1]",
        "Tên <a@example.com>",
        "a@example.com, b@example.com",
        "a@example.com;b@example.com",
        "victim@example.test\r\nBcc: evil@example.test",
        "",
        "   ",
    ],
)
def test_malformed_or_multiple_addresses_are_rejected(value: str) -> None:
    with pytest.raises(ValueError) as error:
        normalize_mailbox(value)
    if value.strip():
        assert value.strip() not in str(error.value)


def test_none_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_mailbox(None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ung.vien@example.test", "ung.vien@example.test"),
        ("recipient@example.test", "recipient@example.test"),
        ("no-reply@sis.hust.edu.vn", "no-reply@sis.hust.edu.vn"),
        ("first.last+tag@gmail.com", "first.last+tag@gmail.com"),
        ("  padded@example.test \r\n", "padded@example.test"),
    ],
)
def test_valid_single_mailbox_is_accepted_without_network(value: str, expected: str) -> None:
    assert normalize_mailbox(value) == expected


def test_validation_never_touches_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    import email_validator.deliverability as deliverability

    def no_network(*args, **kwargs):
        raise AssertionError("DNS lookup attempted")

    monkeypatch.setattr(deliverability, "validate_email_deliverability", no_network)
    assert normalize_mailbox("someone@example.com") == "someone@example.com"
