# Kiểm tra response audit che nội dung nghiệp vụ với Admin nhưng giữ bản gốc.
"""Admin audit output hides job posting business changes but keeps stored history."""

import copy
import uuid
from datetime import UTC, datetime

from app.modules.audit.models import AuditEvent, AuditOutcome
from app.modules.audit.schemas import AuditEventRead


def make_event(*, action: str, target_type: str, metadata: dict) -> AuditEvent:
    return AuditEvent(
        id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        action=action,
        outcome=AuditOutcome.SUCCESS,
        timestamp=datetime(2026, 11, 17, 3, 0, tzinfo=UTC),
        target_type=target_type,
        target_id="42",
        event_metadata=metadata,
    )


def job_update_metadata() -> dict:
    return {
        "changes": {
            "description": {"before": "Mô tả cũ", "after": "Mô tả nội bộ mới"},
            "requirements": {"before": "Python", "after": "Python, Kafka"},
            "benefits": {"before": None, "after": "Thưởng cổ phiếu"},
        }
    }


def criteria_saved_metadata() -> dict:
    return {
        "version_no": 2,
        "changes": {
            "auto_invite_threshold": {"before": "70.00", "after": "85"},
            "interviewer_ids": {
                "before": ["00000000-0000-4000-8000-000000000001"],
                "after": ["00000000-0000-4000-8000-000000000002"],
            },
        },
    }


def test_job_update_changes_are_hidden_without_mutating_the_event() -> None:
    original = job_update_metadata()
    event = make_event(action="job.updated", target_type="job_posting", metadata=original)
    stored = event.event_metadata

    first = AuditEventRead.from_event(event)
    second = AuditEventRead.from_event(event)

    for visible in (first, second):
        assert "changes" not in visible.metadata
        assert visible.metadata == {}
    assert event.event_metadata is stored
    assert event.event_metadata == job_update_metadata()
    assert event.event_metadata["changes"] == original["changes"]


def test_criteria_saved_hides_threshold_and_interviewers_but_keeps_version_no() -> None:
    event = make_event(
        action="job.criteria_saved",
        target_type="job_posting",
        metadata=criteria_saved_metadata(),
    )

    visible = AuditEventRead.from_event(event)

    assert visible.metadata == {"version_no": 2}
    assert "000000000002" not in visible.model_dump_json()
    assert "85" not in str(visible.metadata)
    assert event.event_metadata == criteria_saved_metadata()


def test_job_events_without_changes_keep_their_metadata() -> None:
    metadata = {"previous_status": "OPEN", "status": "CLOSED", "reason": "Quá hạn nộp hồ sơ"}
    event = make_event(
        action="job.closed", target_type="job_posting", metadata=copy.deepcopy(metadata)
    )

    assert AuditEventRead.from_event(event).metadata == metadata
    assert event.event_metadata == metadata


def test_account_event_metadata_is_returned_unchanged() -> None:
    metadata = {"roles": ["HR", "INTERVIEWER"], "previous_roles": ["HR"], "reason": "Điều chuyển"}
    event = make_event(
        action="account.roles_replaced", target_type="account", metadata=copy.deepcopy(metadata)
    )

    visible = AuditEventRead.from_event(event)

    assert visible.metadata == metadata
    assert visible.target_type == "account"
    assert event.event_metadata == metadata


def test_application_status_history_is_hidden_from_admin_but_kept() -> None:
    stored = {"changes": {"status": {"before": "SCORING", "after": "PENDING_HR_REVIEW"}}}
    event = make_event(
        action="application.status_changed",
        target_type="application",
        metadata=copy.deepcopy(stored),
    )

    visible = AuditEventRead.from_event(event)

    assert visible.metadata == {}
    assert "PENDING_HR_REVIEW" not in visible.model_dump_json()
    assert visible.action == "application.status_changed"
    assert event.event_metadata == stored


def test_other_fields_are_copied_from_the_event() -> None:
    event = make_event(
        action="job.updated", target_type="job_posting", metadata=job_update_metadata()
    )

    visible = AuditEventRead.from_event(event)

    assert visible.id == event.id
    assert visible.actor_id == event.actor_id
    assert visible.action == "job.updated"
    assert visible.outcome is AuditOutcome.SUCCESS
    assert visible.timestamp == event.timestamp
    assert visible.target_type == "job_posting"
    assert visible.target_id == "42"
