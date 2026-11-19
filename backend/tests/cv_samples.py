# Sinh CV mẫu nhỏ bằng stdlib (không thêm dependency test): PDF có/không lớp chữ, PDF mã
# hóa, DOCX hợp lệ/không chữ, zip bomb, XML nguy hiểm. Không phải file test.
"""Small CV samples built with the standard library only."""

import io
import zipfile

CV_TEXT = (
    "Nguyen Van A - Backend developer. Five years of Python, PostgreSQL and FastAPI. "
    "Built recruitment and payroll systems; led a team of four engineers."
)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _pdf(objects: list[bytes], trailer_extra: bytes = b"") -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R ".encode()
        + trailer_extra
        + f" >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def _stream(content: bytes) -> bytes:
    return f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"


def _page_objects(content: bytes) -> list[bytes]:
    return [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        _stream(content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]


def make_pdf(body_text: str = CV_TEXT) -> bytes:
    escaped = body_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return _pdf(_page_objects(f"BT /F1 11 Tf 40 740 Td ({escaped}) Tj ET".encode()))


def make_image_only_pdf() -> bytes:
    # Chỉ có nét vẽ, không có lớp chữ (như CV scan; hệ thống không OCR).
    return _pdf(_page_objects(b"0.5 g 40 400 300 300 re f 0 0 m 612 792 l S"))


def make_encrypted_pdf() -> bytes:
    objects = _page_objects(b"BT /F1 11 Tf 40 740 Td (secret) Tj ET")
    objects.append(
        b"<< /Filter /Standard /V 1 /R 2 /O <"
        + b"41" * 32
        + b"> /U <"
        + b"42" * 32
        + b"> /P -44 >>"
    )
    return _pdf(objects, b"/Encrypt 6 0 R /ID [<" + b"00" * 16 + b"> <" + b"00" * 16 + b">]")


def make_padded_pdf(total_bytes: int) -> bytes:
    """A readable PDF grown to ``total_bytes`` with a trailing comment."""
    base = make_pdf()
    return base + b"%" + b"0" * max(0, total_bytes - len(base) - 2) + b"\n"


DOCX_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
    b'relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    b'officedocument.wordprocessingml.document.main+xml"/></Types>'
)
DOCX_RELS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    b'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
)
W_NS = b"http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def document_xml(body_text: str | None = CV_TEXT, *, prolog: bytes = b"") -> bytes:
    run = (
        b"<w:p><w:r><w:t>" + body_text.encode() + b"</w:t></w:r></w:p>" if body_text else b"<w:p/>"
    )
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + prolog
        + b'<w:document xmlns:w="'
        + W_NS
        + b'"><w:body>'
        + run
        + b"</w:body></w:document>"
    )


def make_docx(
    body_text: str | None = CV_TEXT,
    *,
    document: bytes | None = None,
    parts: dict[str, bytes] | None = None,
    include_document: bool = True,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", DOCX_RELS)
        if include_document:
            archive.writestr("word/document.xml", document or document_xml(body_text))
        for name, data in (parts or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


def make_zip_bomb_docx(uncompressed_mb: int = 60) -> bytes:
    # Nén còn rất nhỏ nhưng giải nén ra hàng chục MB.
    filler = b"<w:p><w:r><w:t>" + b"A" * (uncompressed_mb * 1024 * 1024) + b"</w:t></w:r></w:p>"
    document = (
        b'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="'
        + W_NS
        + b'"><w:body>'
        + filler
        + b"</w:body></w:document>"
    )
    return make_docx(document=document)


def make_xxe_docx() -> bytes:
    prolog = b'<!DOCTYPE w:document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    return make_docx(document=document_xml("&xxe; " + CV_TEXT, prolog=prolog))


def make_billion_laughs_docx() -> bytes:
    entities = [b'<!ENTITY lol0 "lol">']
    for level in range(1, 9):
        expansion = f"&lol{level - 1};" * 10
        entities.append(f'<!ENTITY lol{level} "{expansion}">'.encode())
    prolog = b"<!DOCTYPE w:document [" + b"".join(entities) + b"]>"
    return make_docx(document=document_xml("&lol8; " + CV_TEXT, prolog=prolog))


def make_plain_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("notes.txt", CV_TEXT)
    return buffer.getvalue()
