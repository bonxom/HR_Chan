from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.responses.interview_handler import InterviewResponseHandler


def context():
    now = datetime(2026, 12, 1, tzinfo=UTC)
    return SimpleNamespace(
        application=SimpleNamespace(id=1, status="INTERVIEW_INVITED", version=1),
        interview=SimpleNamespace(
            id=2,
            application_id=1,
            status="SCHEDULED",
            start_at=now + timedelta(days=3),
            meet_link="https://meet.google.com/abc-defg-hij",
        ),
        link=SimpleNamespace(interview_id=2),
        now=now,
    )


@pytest.mark.parametrize("state", ["CONFIRMED", "CANCELLED", "RESCHEDULE_REQUESTED"])
def test_handler_rejects_stale_interview_state(state):
    handler = InterviewResponseHandler(None, None)
    ctx = context()
    ctx.interview.status = state
    with pytest.raises(Exception) as failure:
        handler.validate(ctx)
    assert failure.value.code == "invalid_response_link"
