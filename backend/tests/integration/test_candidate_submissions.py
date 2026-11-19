# API nhận CV thật: multipart, đồng ý xử lý dữ liệu, CAPTCHA phía server, kiểm tra file,
# quét mã độc, lưu mã hóa ngoài public, capability riêng, giới hạn 10 lần/IP/giờ bền.
"""``POST /api/v1/candidates/submissions`` (plan task 6).

Contract (see ``application_flow_support`` for create_app/settings):

* multipart fields ``full_name`` (1–100), ``email``, ``phone`` (10 digits), ``consent``
  (must be true), ``captcha_token``, ``file``.
* 201 ``{submission_id, submission_token, expires_at}`` (24 h); never a storage key,
  path or URL. 422 uses FastAPI's ``detail[].loc`` with the field name last and a
  Vietnamese ``msg``; 413 ``cv_too_large``; 415 ``cv_unsupported_type``; 429
  ``rate_limited`` + ``Retry-After``; 503 ``captcha_unavailable`` /
  ``scanner_unavailable`` / ``application_unavailable`` (missing secrets).
* Order: limit -> fields/consent -> CAPTCHA -> document checks -> scan -> encrypted
  store -> DB. Any rejection leaves no file and no row; a DB failure removes the file.
* A submission never changes an existing candidate's contact data before OTP.
"""

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from application_flow_support import (
    SUBMISSIONS_URL,
    FailingTrigger,
    apply_cleanup,
    captcha_unavailable,
    error_code,
    field_errors,
    flow,
    flow_cleanup,
    flow_factory,
    frozen_clock,
    rows,
    scalar,
    scanner_unavailable,
    stored_files,
    upload,
    upload_fields,
    upload_ok,
)
from apply_support import insert_candidate
from cv_samples import (
    PNG_BYTES,
    make_docx,
    make_encrypted_pdf,
    make_image_only_pdf,
    make_padded_pdf,
    make_pdf,
    make_xxe_docx,
    make_zip_bomb_docx,
)

pytestmark = pytest.mark.database

__all__ = ["apply_cleanup", "flow", "flow_cleanup", "flow_factory", "frozen_clock"]

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def submission_count(session_factory) -> int:
    return await scalar(session_factory, "SELECT count(*) FROM cv_submissions")


async def assert_nothing_stored(flow_app, session_factory) -> None:
    assert await submission_count(session_factory) == 0
    assert stored_files(flow_app.settings.cv_storage_dir) == []


# ---- success ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file",
    [("cv.pdf", make_pdf(), "application/pdf"), ("Hồ sơ của tôi.docx", make_docx(), DOCX_MIME)],
    ids=["pdf", "docx"],
)
async def test_clean_cv_creates_a_temporary_submission(
    flow, session_factory, frozen_clock, file
) -> None:
    response = await upload(flow.client, file=file)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"submission_id", "submission_token", "expires_at"}
    expires = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    assert expires == frozen_clock.now + timedelta(hours=24)
    assert len(body["submission_token"]) >= 32
    assert str(flow.settings.cv_storage_dir) not in response.text

    [row] = await rows(
        session_factory,
        "SELECT cv_storage_key, cv_original_name, cv_mime_type, cv_size_bytes, cv_sha256,"
        " cv_scan_status::text AS scan, consent_at, consent_policy_ver,"
        " parse_status::text AS parse, expires_at, created_at FROM cv_submissions",
    )
    name, data, mime = file
    assert row.cv_mime_type == mime
    assert row.cv_size_bytes == len(data)
    assert row.cv_sha256 == hashlib.sha256(data).hexdigest()
    assert row.scan == "CLEAN" and row.parse == "PENDING"
    assert row.consent_policy_ver == "2026-11" and row.consent_at == frozen_clock.now
    assert row.expires_at - row.created_at == timedelta(hours=24)
    assert row.cv_original_name == name
    assert row.cv_storage_key not in response.text
    # One encrypted file, named by the opaque key, never by the original name or email.
    [stored] = stored_files(flow.settings.cv_storage_dir)
    assert row.cv_storage_key in stored.name
    assert name not in stored.name and "ung.vien" not in stored.name
    assert data not in stored.read_bytes()
    # Liên hệ chưa xác minh nằm cùng CV trong đối tượng mã hóa (không ghi rõ vào DB).
    from app.modules.candidates.envelope import unpack

    cv, contact = unpack(await flow.storage.get(row.cv_storage_key))
    assert cv == data
    assert (contact.full_name, contact.email, contact.phone) == (
        "Nguyễn Văn A",
        "ung.vien@example.test",
        "0912345678",
    )
    assert b"Nguy" not in stored.read_bytes()
    assert flow.scanner.scanned == [len(data)]
    assert flow.captcha.calls and flow.captcha.calls[0][0] == "captcha-pass"


async def test_upload_does_not_overwrite_an_existing_candidate(flow, session_factory) -> None:
    async with session_factory() as session:
        await insert_candidate(
            session, email="da.co@example.test", full_name="Tên đã xác minh", phone="0900000000"
        )
        await session.commit()

    await upload_ok(
        flow.client, email="DA.CO@example.test", full_name="Kẻ mạo danh", phone="0999999999"
    )

    [candidate] = await rows(
        session_factory,
        "SELECT full_name, phone FROM candidates WHERE email = 'da.co@example.test'",
    )
    assert (candidate.full_name, candidate.phone) == ("Tên đã xác minh", "0900000000")
    assert await scalar(session_factory, "SELECT count(*) FROM candidates") == 1


async def test_unverified_contact_is_not_stored_in_clear_outside_the_new_candidate(
    flow, session_factory
) -> None:
    async with session_factory() as session:
        await insert_candidate(session, email="da.co@example.test", full_name="Tên cũ")
        await session.commit()
    await upload_ok(flow.client, email="da.co@example.test", full_name="Tên Mới Chưa Xác Minh")
    dump = json.dumps(
        [list(map(str, r)) for r in await rows(session_factory, "SELECT * FROM cv_submissions")]
    )
    assert "Tên Mới Chưa Xác Minh" not in dump


# ---- field validation, consent, CAPTCHA ---------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"full_name": ""}, "full_name"),
        ({"full_name": "A" * 101}, "full_name"),
        ({"email": "khong-hop-le"}, "email"),
        ({"email": "a@example.test\r\nBcc: b@example.test"}, "email"),
        ({"phone": "09123"}, "phone"),
        ({"phone": "09123456ab"}, "phone"),
        ({"consent": "false"}, "consent"),
        ({"consent": None}, "consent"),
        ({"captcha_token": None}, "captcha_token"),
    ],
)
async def test_invalid_fields_are_reported_on_the_field(
    flow, session_factory, fields, field
) -> None:
    response = await upload(flow.client, **fields)
    errors = field_errors(response)
    assert field in errors
    assert errors[field]  # Vietnamese message shown under the input
    await assert_nothing_stored(flow, session_factory)
    assert flow.scanner.scanned == []


async def test_missing_file_is_a_field_error(flow, session_factory) -> None:
    errors = field_errors(await upload(flow.client, file=None))
    assert "file" in errors
    await assert_nothing_stored(flow, session_factory)


async def test_failed_captcha_is_a_field_error_and_nothing_is_scanned(
    flow, session_factory
) -> None:
    flow.captcha.result = False
    errors = field_errors(await upload(flow.client))
    assert "captcha_token" in errors
    assert flow.scanner.scanned == []
    await assert_nothing_stored(flow, session_factory)


async def test_captcha_outage_fails_closed(flow, session_factory) -> None:
    flow.captcha.error = captcha_unavailable()
    response = await upload(flow.client)
    assert response.status_code == 503
    assert error_code(response) == "captcha_unavailable"
    await assert_nothing_stored(flow, session_factory)


# ---- document checks and scanning ---------------------------------------------------------


async def test_file_over_five_megabytes_is_413(flow, session_factory) -> None:
    big = make_padded_pdf(5 * 1024 * 1024 + 1)
    response = await upload(flow.client, file=("cv.pdf", big, "application/pdf"))
    assert response.status_code == 413
    assert error_code(response) == "cv_too_large"
    await assert_nothing_stored(flow, session_factory)


async def test_fake_pdf_is_415(flow, session_factory) -> None:
    response = await upload(flow.client, file=("cv.pdf", PNG_BYTES, "application/pdf"))
    assert response.status_code == 415
    assert error_code(response) == "cv_unsupported_type"
    await assert_nothing_stored(flow, session_factory)


@pytest.mark.parametrize(
    "file",
    [
        ("cv.pdf", make_image_only_pdf(), "application/pdf"),
        ("cv.pdf", make_encrypted_pdf(), "application/pdf"),
        ("cv.docx", make_zip_bomb_docx(40), DOCX_MIME),
        ("cv.docx", make_xxe_docx(), DOCX_MIME),
    ],
    ids=["image-only", "password", "zip-bomb", "xxe"],
)
async def test_unusable_documents_are_file_errors(flow, session_factory, file) -> None:
    errors = field_errors(await upload(flow.client, file=file))
    assert "file" in errors
    assert flow.scanner.scanned == []
    await assert_nothing_stored(flow, session_factory)


async def test_infected_file_is_rejected_and_never_stored(flow, session_factory) -> None:
    flow.scanner.verdict = "INFECTED"
    errors = field_errors(await upload(flow.client))
    assert "file" in errors
    await assert_nothing_stored(flow, session_factory)


async def test_scanner_outage_fails_closed(flow, session_factory) -> None:
    flow.scanner.error = scanner_unavailable()
    response = await upload(flow.client)
    assert response.status_code == 503
    assert error_code(response) == "scanner_unavailable"
    await assert_nothing_stored(flow, session_factory)


async def test_database_failure_removes_the_stored_file(flow, session_factory) -> None:
    async with FailingTrigger(session_factory, "cv_submissions"):
        response = await upload(flow.client)
    assert response.status_code >= 500
    for leaked in ("injected test failure", "cv_submissions", "Traceback"):
        assert leaked not in response.text
    await assert_nothing_stored(flow, session_factory)


@pytest.mark.parametrize(
    "missing", ["cv_encryption_key", "submission_token_secret", "cv_storage_dir"]
)
async def test_missing_configuration_fails_closed(flow_factory, session_factory, missing) -> None:
    app = await flow_factory(**{missing: None})
    response = await upload(app.client)
    assert response.status_code == 503
    assert await submission_count(session_factory) == 0


# ---- durable upload limit: 10 per IP per hour --------------------------------------------


async def test_ten_uploads_per_ip_per_hour_across_app_instances(
    flow_factory, session_factory, frozen_clock
) -> None:
    first = await flow_factory()
    second = await flow_factory()
    other_ip = await flow_factory(client_ip="198.51.100.20")

    for n in range(10):
        app = first if n % 2 else second
        await upload_ok(app.client, email=f"ung.vien.{n}@example.test")

    blocked = await upload(first.client, email="ung.vien.x@example.test")
    assert blocked.status_code == 429
    assert error_code(blocked) == "rate_limited"
    retry_after = int(blocked.headers["Retry-After"])
    assert 0 < retry_after <= 3600
    # Forwarded headers are not trusted by default: they cannot reset the limit.
    spoofed = await second.client.post(
        SUBMISSIONS_URL,
        data=upload_fields(email="a@example.test"),
        files={"file": ("cv.pdf", make_pdf(), "application/pdf")},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert spoofed.status_code == 429
    # Another client address has its own counter.
    await upload_ok(other_ip.client, email="khac@example.test")

    frozen_clock.advance(hours=1, seconds=1)
    await upload_ok(first.client, email="sau.mot.gio@example.test")
    assert await submission_count(session_factory) == 12
