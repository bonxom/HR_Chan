from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.modules.accounts.rules import PASSWORD_MAX_CHARS, PASSWORD_MIN_CHARS
from app.modules.accounts.schemas import AccountRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_CHARS)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    account: AccountRead


class DevLoginRequest(BaseModel):
    persona: str = Field(min_length=1, max_length=32)


class CsrfResponse(BaseModel):
    csrf_token: str


class PasswordRecoveryRequest(BaseModel):
    email: EmailStr


class PasswordCompleteRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=PASSWORD_MIN_CHARS, max_length=PASSWORD_MAX_CHARS)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_CHARS)
    new_password: str = Field(min_length=PASSWORD_MIN_CHARS, max_length=PASSWORD_MAX_CHARS)


class MessageResponse(BaseModel):
    status: str
