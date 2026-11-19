"""Public application DTOs (capability in the JSON body, never in the URL)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

INT64_MAX = 9_223_372_036_854_775_807
BigId = Annotated[int, Field(ge=1, le=INT64_MAX)]


class OtpRequestIn(BaseModel):
    submission_id: BigId
    submission_token: str = Field(min_length=1, max_length=200)
    job_id: BigId


class ApplicationSubmitIn(OtpRequestIn):
    otp_code: str = Field(min_length=1, max_length=16)


class OtpIssuedOut(BaseModel):
    expires_at: datetime
    resend_available_at: datetime


class ApplicationCreatedOut(BaseModel):
    application_id: int
    submitted_at: datetime
    message: str
