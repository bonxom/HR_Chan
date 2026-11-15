from fastapi import APIRouter, Request, Response

from app.core.exceptions import Failure
from app.core.security import (
    CurrentPrincipal,
    SettingsDep,
    client_ip,
    get_email_client,
    unauthorized,
)
from app.db.session import SessionDep
from app.modules.accounts import repository as account_repository
from app.modules.accounts import service as account_service
from app.modules.accounts.schemas import AccountRead
from app.modules.auth import csrf, service
from app.modules.auth.schemas import (
    CsrfResponse,
    DevLoginRequest,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    PasswordCompleteRequest,
    PasswordRecoveryRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

RECOVERY_ACCEPTED = MessageResponse(status="accepted")


def _complete_session_response(
    response: Response, result: service.SessionTokens, settings
) -> TokenResponse:
    csrf.set_refresh_cookie(response, result.refresh_token, settings, result.refresh_expires_in)
    csrf_token, _ = csrf.create_csrf_token(settings)
    csrf.set_csrf_cookie(response, csrf_token, settings)
    csrf.no_store(response)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        account=AccountRead.from_account(result.account),
    )


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(
    payload: DevLoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    csrf.require_trusted_origin(request, settings)
    result = await service.dev_login(session, persona_id=payload.persona, settings=settings)
    if isinstance(result, Failure):
        result.raise_error()
    return _complete_session_response(response, result, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    csrf.require_trusted_origin(request, settings)
    result = await service.login(
        session,
        email=str(payload.email),
        password=payload.password,
        settings=settings,
        client_ip=client_ip(request, settings),
    )
    if isinstance(result, Failure):
        result.raise_error()

    csrf.set_refresh_cookie(response, result.refresh_token, settings, result.refresh_expires_in)
    csrf_token, _ = csrf.create_csrf_token(settings)
    csrf.set_csrf_cookie(response, csrf_token, settings)
    csrf.no_store(response)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        account=AccountRead.from_account(result.account),
    )


@router.get("/csrf", response_model=CsrfResponse)
async def bootstrap_csrf(response: Response, settings: SettingsDep) -> CsrfResponse:
    token, proof = csrf.create_csrf_token(settings)
    csrf.set_csrf_cookie(response, token, settings)
    csrf.no_store(response)
    return CsrfResponse(csrf_token=proof)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    csrf.require_trusted_origin(request, settings)
    refresh_token = csrf.read_refresh_cookie(request)
    if refresh_token:
        # CSRF proof is only meaningful while a credential cookie can act.
        csrf.require_csrf(request, settings)
    await service.logout(session, refresh_token=refresh_token, settings=settings)
    response = Response(status_code=204)
    csrf.clear_credential_cookies(response, settings)
    csrf.no_store(response)
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    csrf.require_trusted_origin(request, settings)
    csrf.require_csrf(request, settings)
    csrf.no_store(response)
    result = await service.refresh(
        session, refresh_token=csrf.read_refresh_cookie(request), settings=settings
    )
    if isinstance(result, Failure):
        csrf.clear_credential_cookies(response, settings)
        result.raise_error()
    csrf.set_refresh_cookie(response, result.refresh_token, settings, result.refresh_expires_in)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        account=AccountRead.from_account(result.account),
    )


@router.post("/activity", status_code=204)
async def report_activity(
    principal: CurrentPrincipal, session: SessionDep, settings: SettingsDep
) -> Response:
    await service.record_activity(
        session, principal_session_id=principal.session_id, settings=settings
    )
    return Response(status_code=204)


@router.post("/password/change", response_model=TokenResponse)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    principal: CurrentPrincipal,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    csrf.require_trusted_origin(request, settings)
    csrf.require_csrf(request, settings)
    csrf.no_store(response)
    result = await service.change_password(
        session,
        account_id=principal.account_id,
        session_id=principal.session_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        expected_version=principal.credential_version,
        settings=settings,
    )
    if isinstance(result, Failure):
        result.raise_error()
    csrf.set_refresh_cookie(response, result.refresh_token, settings, result.refresh_expires_in)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        account=AccountRead.from_account(result.account),
    )


@router.get("/me", response_model=AccountRead)
async def current_account(
    response: Response, principal: CurrentPrincipal, session: SessionDep
) -> AccountRead:
    account = await account_repository.get_by_id(session, principal.account_id)
    if account is None:
        raise unauthorized()
    csrf.no_store(response)
    return AccountRead.from_account(account)


@router.post("/password/recovery", status_code=202, response_model=MessageResponse)
async def request_password_recovery(
    payload: PasswordRecoveryRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> MessageResponse:
    csrf.require_trusted_origin(request, settings)
    outcome = await account_service.request_password_email(
        session,
        email=str(payload.email),
        settings=settings,
        email_client=get_email_client(request),
        client_ip=client_ip(request, settings),
    )
    if isinstance(outcome, Failure):
        outcome.raise_error()
    csrf.no_store(response)
    return RECOVERY_ACCEPTED


@router.post("/password/complete", status_code=204)
async def complete_password(
    payload: PasswordCompleteRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    csrf.require_trusted_origin(request, settings)
    outcome = await account_service.complete_password_link(
        session,
        token=payload.token,
        new_password=payload.new_password,
        settings=settings,
    )
    if isinstance(outcome, Failure):
        outcome.raise_error()
    response = Response(status_code=204)
    csrf.no_store(response)
    return response
