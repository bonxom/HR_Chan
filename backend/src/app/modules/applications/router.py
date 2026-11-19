"""Public OTP and application endpoints (no account; the capability is in the body)."""

from fastapi import APIRouter, Depends, Request

from app.core.adapters import get_cv_storage, get_email_service
from app.core.security import SettingsDep, client_ip
from app.db.session import SessionDep
from app.modules.applications.schemas import (
    ApplicationCreatedOut,
    ApplicationSubmitIn,
    OtpIssuedOut,
    OtpRequestIn,
)
from app.modules.applications.service import THANK_YOU, ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/otp", response_model=OtpIssuedOut)
async def request_otp(
    payload: OtpRequestIn,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage=Depends(get_cv_storage),  # noqa: B008
    email_service=Depends(get_email_service),  # noqa: B008
) -> OtpIssuedOut:
    issued = await ApplicationService(session, settings).request_otp(
        submission_id=payload.submission_id,
        submission_token=payload.submission_token,
        job_id=payload.job_id,
        storage=storage,
        email_service=email_service,
        session_factory=request.app.state.session_factory,
        client_ip=client_ip(request, settings),
    )
    return OtpIssuedOut(
        expires_at=issued.expires_at, resend_available_at=issued.resend_available_at
    )


@router.post("", status_code=201, response_model=ApplicationCreatedOut)
async def submit_application(
    payload: ApplicationSubmitIn,
    session: SessionDep,
    settings: SettingsDep,
    storage=Depends(get_cv_storage),  # noqa: B008
) -> ApplicationCreatedOut:
    created = await ApplicationService(session, settings).submit(
        submission_id=payload.submission_id,
        submission_token=payload.submission_token,
        job_id=payload.job_id,
        otp_code=payload.otp_code,
        storage=storage,
    )
    return ApplicationCreatedOut(
        application_id=created.application_id,
        submitted_at=created.submitted_at,
        message=THANK_YOU,
    )
