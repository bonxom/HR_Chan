from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=512, repr=False)


class SubmitIn(ResolveIn):
    action: Literal["ACCEPTED", "DECLINED", "RESCHEDULE_REQUESTED"]
    note: str | None = Field(default=None, max_length=500, pattern=r"^[^\x00]*$")
    policy_ver: str | None = Field(default=None, max_length=20)
    consent_snapshot: str | None = Field(default=None, max_length=64)


class ResponseReceiptOut(BaseModel):
    completed: Literal[True] = True
    outcome: str
    completed_at: datetime


class ResponseViewOut(BaseModel):
    completed: Literal[False] = False
    purpose: str
    job_title: str
    expires_at: datetime
    allowed_actions: list[str]
    start_at: datetime | None = None
    meet_link: str | None = None
    can_reschedule: bool | None = None
    consent_mode: Literal["GRANT", "ACKNOWLEDGE"] | None = None
    policy_ver: str | None = None
    policy_text: str | None = None
    retention_months: int | None = None
    consent_snapshot: str | None = None
    consent_expires_at: datetime | None = None


class ResponseResultOut(BaseModel):
    outcome: str
    message: str
    application_status: str | None = None
    interview_status: str | None = None
