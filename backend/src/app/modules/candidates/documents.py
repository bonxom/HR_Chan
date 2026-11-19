"""Inspect an uploaded CV by its real content (PDF/DOCX with a text layer, <= 5 MiB).

Synchronous and side-effect free: the service runs it in a worker thread. The type is
detected from the bytes, never from the file name or the client's Content-Type. No OCR:
a document without extractable text is rejected. DOCX archives are checked from the
central directory before anything is decompressed (zip bomb), XML is parsed with
``defusedxml`` and any DTD/entity is refused (XXE, billion laughs). Rejection messages
never echo file content.
"""

import io
import re
import zipfile
from dataclasses import dataclass

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as safe_fromstring

MAX_CV_BYTES = 5 * 1024 * 1024
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

MAX_PDF_PAGES = 50
MAX_TEXT_CHARS = 200_000
MAX_DOCX_MEMBERS = 1000
MAX_DOCX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_DOCX_MEMBER_BYTES = 15 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_ENCRYPT_MARKER = re.compile(rb"/Encrypt\s*(?:\d+\s+\d+\s+R|<<)")

MESSAGES = {
    "too_large": "Tệp CV vượt quá dung lượng tối đa 5 MB.",
    "unsupported_type": "Chỉ chấp nhận CV định dạng PDF hoặc DOCX.",
    "no_text": "CV không có lớp chữ đọc được (ví dụ bản scan ảnh). Vui lòng gửi tệp có chữ.",
    "encrypted": "CV đang được đặt mật khẩu. Vui lòng gửi tệp không mã hóa.",
    "unsafe_document": "Tệp CV có cấu trúc không an toàn nên không thể tiếp nhận.",
    "unreadable": "Không đọc được tệp CV. Vui lòng kiểm tra và gửi lại.",
}
STATUS = {"too_large": 413, "unsupported_type": 415}


class CvRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        self.status_code = STATUS.get(code, 422)
        self.message = MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class InspectedCv:
    mime_type: str
    text_length: int


def _check_text(text: str, mime_type: str) -> InspectedCv:
    # Chỉ từ chối khi không có ký tự nào ngoài khoảng trắng.
    if not text.strip():
        raise CvRejected("no_text")
    return InspectedCv(mime_type=mime_type, text_length=len(text.strip()))


def _inspect_pdf(data: bytes) -> InspectedCv:
    if _ENCRYPT_MARKER.search(data):
        raise CvRejected("encrypted")
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise CvRejected("encrypted")
        pages = reader.pages
        if len(pages) == 0:
            raise CvRejected("unreadable")
        if len(pages) > MAX_PDF_PAGES:
            raise CvRejected("unsafe_document")
        parts: list[str] = []
        total = 0
        for page in pages:
            chunk = page.extract_text() or ""
            parts.append(chunk)
            total += len(chunk)
            if total >= MAX_TEXT_CHARS:
                break
    except CvRejected:
        raise
    except Exception:
        # Lỗi cấu trúc PDF: không đưa thông báo của thư viện ra ngoài.
        raise CvRejected("unreadable") from None
    return _check_text("".join(parts), PDF_MIME)


def _inspect_docx(data: bytes) -> InspectedCv:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError):
        raise CvRejected("unsupported_type") from None
    with archive:
        try:
            infos = archive.infolist()
        except Exception:
            raise CvRejected("unreadable") from None
        names = {info.filename for info in infos}
        if "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise CvRejected("unsupported_type")
        if len(infos) > MAX_DOCX_MEMBERS:
            raise CvRejected("unsafe_document")
        # Kiểm tra kích thước khai báo trước khi giải nén bất cứ thứ gì (zip bomb).
        if sum(info.file_size for info in infos) > MAX_DOCX_TOTAL_BYTES:
            raise CvRejected("unsafe_document")
        for info in infos:
            if info.flag_bits & 0x1:
                raise CvRejected("encrypted")
            if info.file_size > MAX_DOCX_MEMBER_BYTES:
                raise CvRejected("unsafe_document")
            if info.file_size > 1024 * 1024 and info.file_size > MAX_COMPRESSION_RATIO * max(
                info.compress_size, 1
            ):
                raise CvRejected("unsafe_document")
        document = archive.getinfo("word/document.xml")
        try:
            with archive.open(document) as handle:
                # Đọc có giới hạn: kích thước khai báo trong zip có thể bị làm giả.
                xml = handle.read(MAX_DOCX_MEMBER_BYTES + 1)
        except Exception:
            raise CvRejected("unreadable") from None
        if len(xml) > MAX_DOCX_MEMBER_BYTES:
            raise CvRejected("unsafe_document")
    try:
        root = safe_fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException:
        raise CvRejected("unsafe_document") from None
    except (ParseError, ValueError):
        raise CvRejected("unreadable") from None
    text = " ".join(node.text for node in root.iter(f"{{{WORD_NS}}}t") if node.text)
    return _check_text(text, DOCX_MIME)


def inspect_cv(data: bytes, filename: str) -> InspectedCv:
    """Validate a CV; ``filename`` is informational only and never decides the type."""
    if len(data) > MAX_CV_BYTES:
        raise CvRejected("too_large")
    if data.startswith(b"%PDF-"):
        return _inspect_pdf(data)
    if data.startswith(b"PK\x03\x04"):
        return _inspect_docx(data)
    raise CvRejected("unsupported_type")
