from decimal import Decimal

import pytest

from app.modules.applications.scoring import check_mandatory, validate_scores, weighted_total
from app.modules.recruitment.models import Criterion


def criterion(id, weight, floor=None):
    row = Criterion(id=id, weight=Decimal(weight), is_mandatory=floor is not None)
    row.min_score = Decimal(floor) if floor is not None else None
    return row


def response(*values):
    return [
        {"criterion_id": index, "score": score, "comment": "Nhận xét"}
        for index, score in enumerate(values, 1)
    ]


def test_mandatory_floor_independent_of_total_and_inclusive():
    criteria = [criterion(1, "25", "60"), criterion(2, "75")]
    scores = validate_scores(response(55, 95), criteria)
    assert weighted_total(scores, criteria) == Decimal("85.00")
    assert check_mandatory(scores, criteria) == ({1: False, 2: None}, False)
    scores = validate_scores(response(60, 95), criteria)
    assert check_mandatory(scores, criteria) == ({1: True, 2: None}, True)


def test_decimal_rounded_once_and_no_mandatory():
    criteria = [criterion(1, "50"), criterion(2, "50")]
    scores = validate_scores(response("69.99", 70), criteria)
    assert weighted_total(scores, criteria) == Decimal("70.00")
    assert check_mandatory(scores, criteria) == ({1: None, 2: None}, True)


@pytest.mark.parametrize(
    "raw",
    [
        [],
        response(70, 80),
        response(1.111),
        response(True),
        response("NaN"),
        response(101),
        [{"criterion_id": 1, "score": 75, "comment": "ok", "meets_mandatory": True}],
        [{"criterion_id": 1, "score": 75}],
        response(70) * 2,
    ],
)
def test_invalid_output_cannot_produce_scores(raw):
    with pytest.raises(ValueError):
        validate_scores(raw, [criterion(1, "100")])
