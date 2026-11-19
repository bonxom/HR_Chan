"""Request (*In) and response (*Out) contracts for job postings and criteria."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.recruitment.models import JobStatus

TITLE_MAX = 200
DESCRIPTION_MAX = 5000
REQUIREMENTS_MAX = 5000
BENEFITS_MAX = 3000
WORK_MODE_MAX = 50
LOCATION_MAX = 200
CRITERION_NAME_MAX = 150
CRITERION_DESCRIPTION_MAX = 1000
TOTAL_WEIGHT = Decimal("100")

# PostgreSQL column ranges: INTEGER for headcount/version, BIGINT for identifiers.
# Values outside them are rejected as 422 before any query runs.
INT32_MAX = 2_147_483_647
INT64_MAX = 9_223_372_036_854_775_807

Headcount = Annotated[int, Field(gt=0, le=INT32_MAX)]
RowVersion = Annotated[int, Field(ge=1, le=INT32_MAX)]
BigId = Annotated[int, Field(ge=1, le=INT64_MAX)]

Weight = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
Threshold = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class _In(BaseModel):
    # Loại khoảng trắng hai đầu và từ chối trường lạ ngay ở biên API.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class CriterionIn(_In):
    name: str = Field(min_length=1, max_length=CRITERION_NAME_MAX)
    description: str = Field(min_length=1, max_length=CRITERION_DESCRIPTION_MAX)
    is_mandatory: bool = False
    weight: Weight


class CriteriaIn(_In):
    """A complete criteria set: criteria, weights, auto-invite threshold, interviewers."""

    # null yêu cầu service lấy ngưỡng trong system_settings, không dùng giá trị UI.
    auto_invite_threshold: Threshold | None = None
    # Set-level business rules (at least one criterion and interviewer, weights summing to
    # 100, unique names) are checked in CriteriaService so they share the AppError format.
    criteria: list[CriterionIn] = Field(default_factory=list)
    interviewer_ids: list[UUID] = Field(default_factory=list)


class CriteriaSaveIn(CriteriaIn):
    version: Annotated[
        int,
        Field(ge=1, le=INT32_MAX, description="Version of the job posting the client last read"),
    ]


class JobFieldsIn(_In):
    # Schema cho phép thiếu dữ liệu khi lưu nháp; service kiểm tra thêm lúc đăng.
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    department_id: BigId
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    requirements: str | None = Field(default=None, max_length=REQUIREMENTS_MAX)
    benefits: str | None = Field(default=None, max_length=BENEFITS_MAX)
    headcount: Headcount | None = None
    work_mode: str | None = Field(default=None, max_length=WORK_MODE_MAX)
    location: str | None = Field(default=None, max_length=LOCATION_MAX)
    deadline: date | None = None

    _blank = field_validator(
        "description", "requirements", "benefits", "work_mode", "location", mode="before"
    )(_blank_to_none)


class JobCreateIn(JobFieldsIn):
    # Một endpoint phục vụ cả Lưu nháp và Đăng tin bằng cờ publish.
    publish: bool = False
    criteria: CriteriaIn | None = None


class JobUpdateIn(JobFieldsIn):
    # Version của lần đọc trước giúp service phát hiện cập nhật đồng thời (409).
    version: RowVersion


class VersionIn(_In):
    version: RowVersion


class JobSort(StrEnum):
    CREATED_AT = "created_at"
    DEADLINE = "deadline"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class DepartmentOut(BaseModel):
    id: int
    name: str
    is_active: bool


class InterviewerOut(BaseModel):
    id: UUID
    full_name: str


class CriterionOut(BaseModel):
    id: int
    name: str
    description: str
    is_mandatory: bool
    weight: Decimal


class CriteriaSetOut(BaseModel):
    id: int
    version_no: int
    auto_invite_threshold: Decimal
    created_by: UUID
    created_at: datetime
    criteria: list[CriterionOut]


class JobSummaryOut(BaseModel):
    id: int
    title: str
    department_id: int
    department_name: str
    status: JobStatus
    headcount: int | None
    work_mode: str | None
    location: str | None
    deadline: date | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    # Ngày suy ra từ closed_at để UI và worker dùng cùng một quy tắc lưu trữ.
    deletion_due_date: date | None = None
    version: int


class JobDetailOut(JobSummaryOut):
    description: str | None
    requirements: str | None
    benefits: str | None
    created_by: UUID
    current_criteria: CriteriaSetOut | None
    interviewers: list[InterviewerOut]


class JobPageOut(BaseModel):
    items: list[JobSummaryOut]
    total: int
    page: int
    page_size: int
