from fastapi import APIRouter, Response

from app.core.security import SettingsDep
from app.db.session import SessionDep
from app.modules.responses.schemas import (
    ResolveIn,
    ResponseReceiptOut,
    ResponseResultOut,
    ResponseViewOut,
    SubmitIn,
)
from app.modules.responses.service import CandidateResponseService

router = APIRouter(prefix="/responses", tags=["candidate-responses"])


def private_headers(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.post(
    "/resolve",
    response_model=ResponseViewOut | ResponseReceiptOut,
    response_model_exclude_none=True,
)
async def resolve(
    payload: ResolveIn, session: SessionDep, settings: SettingsDep, response: Response
):
    private_headers(response)
    return await CandidateResponseService(session, settings).resolve(payload.token)


@router.post("/submit", response_model=ResponseResultOut, response_model_exclude_none=True)
async def submit(payload: SubmitIn, session: SessionDep, settings: SettingsDep, response: Response):
    private_headers(response)
    return await CandidateResponseService(session, settings).submit(payload)
