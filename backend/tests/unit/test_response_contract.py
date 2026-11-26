import pytest
from pydantic import ValidationError

from app.modules.responses.schemas import ResolveIn, SubmitIn


def test_response_contract_forbids_extra_and_bounds_token():
    with pytest.raises(ValidationError):
        ResolveIn(token="secret", ignored=True)
    with pytest.raises(ValidationError):
        ResolveIn(token="x" * 513)
    with pytest.raises(ValidationError):
        SubmitIn(token="secret", action="EXPIRED")
    assert SubmitIn(token="secret", action="ACCEPTED").action == "ACCEPTED"
