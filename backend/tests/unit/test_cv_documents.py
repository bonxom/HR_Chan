# Kiểm tra CV thật: loại file theo nội dung (không theo đuôi), PDF/DOCX có lớp chữ,
# tối đa 5 MB, chặn PDF chỉ ảnh/có mật khẩu, zip bomb, XML nguy hiểm. Không OCR, không AI.
"""CV document inspection (plan task 6).

Contract of ``app.modules.candidates.documents``:

* ``MAX_CV_BYTES = 5 * 1024 * 1024``; ``PDF_MIME``; ``DOCX_MIME``.
* ``inspect_cv(data: bytes, filename: str) -> InspectedCv`` (synchronous, pure; the
  service runs it in a worker thread). ``InspectedCv`` has ``mime_type`` (detected from
  the content, never from the extension or the client's Content-Type) and
  ``text_length`` (characters of extracted text).
* Rejections raise ``CvRejected`` with ``.code`` and ``.status_code``:
  ``too_large`` 413, ``unsupported_type`` 415, ``no_text`` 422, ``encrypted`` 422,
  ``unsafe_document`` 422 (zip bomb, DTD/entities), ``unreadable`` 422 (corrupt file).
"""

import time

import pytest
from cv_samples import (
    CV_TEXT,
    PNG_BYTES,
    make_billion_laughs_docx,
    make_docx,
    make_encrypted_pdf,
    make_image_only_pdf,
    make_padded_pdf,
    make_pdf,
    make_plain_zip,
    make_xxe_docx,
    make_zip_bomb_docx,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def inspect(data: bytes, filename: str):
    from app.modules.candidates.documents import inspect_cv

    return inspect_cv(data, filename)


def rejected(data: bytes, filename: str):
    from app.modules.candidates.documents import CvRejected

    with pytest.raises(CvRejected) as error:
        inspect(data, filename)
    return error.value


def test_constants_match_the_rules() -> None:
    from app.modules.candidates.documents import DOCX_MIME as docx
    from app.modules.candidates.documents import MAX_CV_BYTES, PDF_MIME

    assert MAX_CV_BYTES == 5 * 1024 * 1024
    assert PDF_MIME == "application/pdf"
    assert docx == DOCX_MIME


def test_pdf_with_text_is_accepted() -> None:
    result = inspect(make_pdf(), "cv.pdf")
    assert result.mime_type == "application/pdf"
    assert result.text_length >= 50


def test_docx_with_text_is_accepted() -> None:
    result = inspect(make_docx(), "cv.docx")
    assert result.mime_type == DOCX_MIME
    assert result.text_length >= len(CV_TEXT) - 5


def test_exactly_five_megabytes_is_allowed_and_one_byte_more_is_not() -> None:
    limit = 5 * 1024 * 1024
    assert inspect(make_padded_pdf(limit), "cv.pdf").mime_type == "application/pdf"
    error = rejected(make_padded_pdf(limit + 1), "cv.pdf")
    assert (error.code, error.status_code) == ("too_large", 413)


@pytest.mark.parametrize(
    ("data", "filename"),
    [
        (PNG_BYTES, "cv.pdf"),
        (b"MZ\x90\x00" + b"\x00" * 100, "cv.pdf"),
        (b"Plain text resume pretending to be a document", "cv.docx"),
        (make_plain_zip(), "cv.docx"),
        (make_docx(include_document=False), "cv.docx"),
        (b"{\\rtf1\\ansi Resume}", "cv.doc"),
    ],
    ids=["png-as-pdf", "exe-as-pdf", "text-as-docx", "zip-as-docx", "docx-no-body", "rtf"],
)
def test_real_type_is_checked_not_the_extension(data: bytes, filename: str) -> None:
    error = rejected(data, filename)
    assert (error.code, error.status_code) == ("unsupported_type", 415)


@pytest.mark.parametrize(
    "data",
    [make_image_only_pdf(), make_pdf(""), make_docx(None)],
    ids=["image-only-pdf", "empty-pdf", "docx-without-text"],
)
def test_documents_without_a_text_layer_are_rejected(data: bytes) -> None:
    filename = "cv.docx" if data[:2] == b"PK" else "cv.pdf"
    error = rejected(data, filename)
    assert (error.code, error.status_code) == ("no_text", 422)


def test_password_protected_pdf_is_rejected() -> None:
    error = rejected(make_encrypted_pdf(), "cv.pdf")
    assert (error.code, error.status_code) == ("encrypted", 422)


def test_zip_bomb_is_rejected_quickly_without_full_extraction() -> None:
    bomb = make_zip_bomb_docx(60)
    assert len(bomb) < 5 * 1024 * 1024  # small on the wire
    started = time.monotonic()
    error = rejected(bomb, "cv.docx")
    assert (error.code, error.status_code) == ("unsafe_document", 422)
    assert time.monotonic() - started < 5


@pytest.mark.parametrize(
    "data", [make_xxe_docx(), make_billion_laughs_docx()], ids=["xxe", "billion-laughs"]
)
def test_dangerous_xml_is_rejected(data: bytes) -> None:
    error = rejected(data, "cv.docx")
    assert (error.code, error.status_code) == ("unsafe_document", 422)


def test_corrupt_pdf_is_rejected_as_unreadable() -> None:
    data = b"%PDF-1.4\n" + b"\x00garbage" * 50
    error = rejected(data, "cv.pdf")
    assert error.status_code in (415, 422)
    assert error.code in ("unreadable", "unsupported_type")


def test_rejection_message_does_not_echo_file_content() -> None:
    error = rejected(make_xxe_docx(), "cv.docx")
    assert "passwd" not in str(error) and "ENTITY" not in str(error)
