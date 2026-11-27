from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.applications.models import ApplicationStatus


class ApplicationCountsOut(BaseModel):
    total: int
    overdue: int
    by_status: dict[ApplicationStatus, int]


class ApplicationFilters(BaseModel):
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)
    job_id: int | None = Field(default=None, ge=1, le=9_223_372_036_854_775_807)
    status: ApplicationStatus | None = None
    submitted_from: datetime | None = None
    submitted_to: datetime | None = None
    score_min: Decimal | None = Field(default=None, ge=0, le=100)
    score_max: Decimal | None = Field(default=None, ge=0, le=100)
    overdue: bool | None = None
    email_issue: bool | None = None
    q: str | None = Field(default=None, max_length=200)
    sort: str = Field(
        default="submitted_at", pattern="^(submitted_at|ai_total_score|review_due_at)$"
    )
    order: str = Field(default="desc", pattern="^(asc|desc)$")

    @model_validator(mode="after")
    def valid_ranges(self):
        for value in (self.submitted_from, self.submitted_to):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Thời gian phải có múi giờ")
        for first, last in (
            (self.submitted_from, self.submitted_to),
            (self.score_min, self.score_max),
        ):
            if first is not None and last is not None and first > last:
                raise ValueError("Khoảng lọc không hợp lệ")
        return self


class RejectReason(StrEnum):
    NOT_QUALIFIED = "NOT_QUALIFIED"
    SKILL_MISMATCH = "SKILL_MISMATCH"
    INSUFFICIENT_EXPERIENCE = "INSUFFICIENT_EXPERIENCE"
    POSITION_FILLED = "POSITION_FILLED"
    OTHER = "OTHER"


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason_code: RejectReason
    reason_text: str | None = Field(default=None, max_length=500)
    version: int = Field(ge=1, le=2_147_483_647)

    @model_validator(mode="after")
    def other_reason(self):
        if self.reason_code == RejectReason.OTHER and not self.reason_text:
            raise ValueError("Vui lòng nhập lý do khác")
        return self
