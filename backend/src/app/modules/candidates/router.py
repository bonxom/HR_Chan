"""Public CV upload. No account; the response capability authorizes later steps."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.adapters import get_captcha, get_cv_storage, get_scanner
from app.core.security import SettingsDep, client_ip
from app.db.session import SessionDep
from app.modules.candidates.documents import MAX_CV_BYTES
from app.modules.candidates.schemas import SubmissionOut
from app.modules.candidates.service import SubmissionForm, SubmissionService

router = APIRouter(prefix="/candidates", tags=["candidates"])

OptionalForm = Annotated[str | None, Form()]


@router.post("/submissions", status_code=201, response_model=SubmissionOut)
async def create_submission(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage=Depends(get_cv_storage),  # noqa: B008
    scanner=Depends(get_scanner),  # noqa: B008
    captcha=Depends(get_captcha),  # noqa: B008
    full_name: OptionalForm = None,
    email: OptionalForm = None,
    phone: OptionalForm = None,
    consent: OptionalForm = None,
    captcha_token: OptionalForm = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> SubmissionOut:
    data = None
    filename = None
    if file is not None:
        filename = file.filename
        # Đọc có giới hạn: quá 5 MB thì chỉ cần biết là quá, không giữ thêm dữ liệu.
        data = await file.read(MAX_CV_BYTES + 1)
    form = SubmissionForm(full_name, email, phone, consent, captcha_token, filename, data)
    created = await SubmissionService(session, settings).create(
        form,
        storage=storage,
        scanner=scanner,
        captcha=captcha,
        client_ip=client_ip(request, settings),
    )
    return SubmissionOut(
        submission_id=created.submission_id,
        submission_token=created.submission_token,
        expires_at=created.expires_at,
    )
