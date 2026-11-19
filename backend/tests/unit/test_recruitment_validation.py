# Kiểm tra giới hạn schema trước khi dữ liệu vượt miền số của PostgreSQL tới DB.
# Có cả giá trị sai và sát biên hợp lệ để tránh chặn nhầm dữ liệu.
"""Numeric bounds on job posting request schemas.

Values must fit the PostgreSQL column/parameter types so that out-of-range input is a
422 validation error instead of a database error (HTTP 500):

- headcount, version: INTEGER (1..2147483647)
- department_id: BIGINT (1..9223372036854775807)
"""

from collections.abc import Callable
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from app.modules.recruitment.schemas import CriteriaSaveIn, JobCreateIn, JobUpdateIn, VersionIn

MAX_INTEGER = 2_147_483_647
MAX_BIGINT = 9_223_372_036_854_775_807


def job_fields(**overrides) -> dict:
    return {"title": "Tin kiểm thử", "department_id": 1, **overrides}


def criteria_fields(**overrides) -> dict:
    return {
        "criteria": [{"name": "Kỹ năng", "description": "Mô tả", "weight": 100}],
        "interviewer_ids": [str(uuid4())],
        **overrides,
    }


JOB_MODELS: dict[str, Callable[..., BaseModel]] = {
    "create": lambda **fields: JobCreateIn(**job_fields(**fields)),
    "update": lambda **fields: JobUpdateIn(**job_fields(version=1, **fields)),
}

VERSIONED_MODELS: dict[str, Callable[[int], BaseModel]] = {
    "update": lambda version: JobUpdateIn(**job_fields(version=version)),
    "publish_close": lambda version: VersionIn(version=version),
    "criteria": lambda version: CriteriaSaveIn(**criteria_fields(version=version)),
}


def test_headcount_outside_integer_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JobCreateIn(title="Tin kiểm thử", department_id=1, headcount=2147483648)


@pytest.mark.parametrize("model", sorted(JOB_MODELS))
@pytest.mark.parametrize("headcount", [1, MAX_INTEGER])
def test_headcount_accepts_integer_boundaries(model: str, headcount: int) -> None:
    assert JOB_MODELS[model](headcount=headcount).headcount == headcount


@pytest.mark.parametrize("model", sorted(JOB_MODELS))
@pytest.mark.parametrize("headcount", [0, -1, MAX_INTEGER + 1, MAX_BIGINT + 1])
def test_headcount_outside_range_is_rejected(model: str, headcount: int) -> None:
    with pytest.raises(ValidationError):
        JOB_MODELS[model](headcount=headcount)


@pytest.mark.parametrize("model", sorted(JOB_MODELS))
@pytest.mark.parametrize("department_id", [1, MAX_BIGINT])
def test_department_id_accepts_bigint_boundaries(model: str, department_id: int) -> None:
    assert JOB_MODELS[model](department_id=department_id).department_id == department_id


@pytest.mark.parametrize("model", sorted(JOB_MODELS))
@pytest.mark.parametrize("department_id", [0, -1, MAX_BIGINT + 1, 10**30])
def test_department_id_outside_bigint_range_is_rejected(model: str, department_id: int) -> None:
    with pytest.raises(ValidationError):
        JOB_MODELS[model](department_id=department_id)


@pytest.mark.parametrize("model", sorted(VERSIONED_MODELS))
@pytest.mark.parametrize("version", [1, MAX_INTEGER])
def test_version_accepts_integer_boundaries(model: str, version: int) -> None:
    assert VERSIONED_MODELS[model](version).version == version


@pytest.mark.parametrize("model", sorted(VERSIONED_MODELS))
@pytest.mark.parametrize("version", [0, -1, MAX_INTEGER + 1, MAX_BIGINT + 1])
def test_version_outside_integer_range_is_rejected(model: str, version: int) -> None:
    with pytest.raises(ValidationError):
        VERSIONED_MODELS[model](version)
