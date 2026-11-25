from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.adapters import get_cv_storage
from app.core.security import HrPrincipal, SettingsDep
from app.db.session import SessionDep
from app.modules.applications.review_schemas import ApplicationFilters, RejectIn
from app.modules.applications.review_service import ApplicationReviewService

router = APIRouter(prefix="/applications", tags=["application-review"])
ApplicationId = Annotated[int, Path(ge=1, le=9_223_372_036_854_775_807)]


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interviewer_id: UUID | None = None
    start_at: datetime
    version: int = Field(ge=1, le=2_147_483_647)

    @field_validator("start_at")
    @classmethod
    def aware_start(cls, value):
        if value.utcoffset() is None:
            raise ValueError("Thời gian phải có múi giờ")
        return value


@router.get("")
async def list_applications(
    principal: HrPrincipal,
    session: SessionDep,
    filters: Annotated[ApplicationFilters, Query()],
    response: Response,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await ApplicationReviewService(session).list(principal.account_id, filters)


@router.get("/{application_id}")
async def detail(
    application_id: ApplicationId, principal: HrPrincipal, session: SessionDep, response: Response
):
    response.headers["Cache-Control"] = "private, no-store"
    return await ApplicationReviewService(session).detail(principal.account_id, application_id)


@router.get("/{application_id}/cv")
async def cv(
    application_id: ApplicationId,
    principal: HrPrincipal,
    session: SessionDep,
    storage=Depends(get_cv_storage),  # noqa: B008
):
    content, mime, headers = await ApplicationReviewService(session).download_cv(
        principal.account_id, application_id, storage
    )
    return Response(content=content, media_type=mime, headers=headers)


@router.post("/{application_id}/reject")
async def reject(
    application_id: ApplicationId,
    payload: RejectIn,
    principal: HrPrincipal,
    session: SessionDep,
    settings: SettingsDep,
):
    return await ApplicationReviewService(session).reject(
        principal.account_id, application_id, payload, settings
    )


@router.get("/{application_id}/interview-slots")
async def slots(
    application_id: ApplicationId,
    principal: HrPrincipal,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    date_from: date,
    date_to: date,
    interviewer_id: UUID | None = None,
):
    from app.modules.applications.invitation_service import InterviewInvitationService

    service = InterviewInvitationService(
        session, settings, request.app.state.google_workspace, request.app.state.session_factory
    )
    try:
        return await service.slots(application_id, interviewer_id, date_from, date_to)
    finally:
        await session.rollback()


@router.post("/{application_id}/invite")
async def invite(
    application_id: ApplicationId,
    payload: InviteIn,
    principal: HrPrincipal,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
):
    from app.modules.applications.invitation_service import InterviewInvitationService

    service = InterviewInvitationService(
        session, settings, request.app.state.google_workspace, request.app.state.session_factory
    )
    return await service.invite(
        application_id,
        principal.account_id,
        payload.start_at,
        payload.version,
        payload.interviewer_id,
    )
