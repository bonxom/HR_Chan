"""Allowlisted audit event contracts."""

import copy
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.audit.models import AuditEvent, AuditOutcome

METADATA_ALLOWLIST = frozenset(
    {
        "reason",
        "roles",
        "previous_roles",
        "status",
        "previous_status",
        "purpose",
        "email_delivery",
        "persona",
        # Job posting history: {field: {"before": ..., "after": ...}} for changed fields.
        "changes",
        "version_no",
    }
)

# Metadata kept in the database for auditing but not returned by the Admin audit API.
# Job posting "changes" hold business content (descriptions, requirements, benefits,
# thresholds, interviewer IDs) that Administrators are not allowed to read.
HIDDEN_METADATA_BY_TARGET: dict[str, frozenset[str]] = {
    # Giữ lịch sử thay đổi trong DB nhưng không trả nội dung nghiệp vụ cho Admin.
    "job_posting": frozenset({"changes"}),
    # Lịch sử trạng thái hồ sơ (trigger applications_history) là dữ liệu nghiệp vụ;
    # Admin không được xem (quy tắc Admin không xem dữ liệu nghiệp vụ).
    "application": frozenset({"changes"}),
}

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "hash",
    "email",
    "cv",
    "evaluation",
    "credential",
)


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login.succeeded"
    DEV_LOGIN = "auth.dev_login"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    PASSWORD_SETUP = "auth.password.setup"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_RECOVERY_REQUESTED = "auth.password.recovery_requested"
    REFRESH_REPLAYED = "auth.refresh.replayed"
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_LOCKED = "account.locked"
    ACCOUNT_UNLOCKED = "account.unlocked"
    ACCOUNT_DISABLED = "account.disabled"
    ACCOUNT_ROLES_REPLACED = "account.roles_replaced"
    ACCOUNT_INVITATION_RESENT = "account.invitation_resent"
    JOB_CREATED = "job.created"
    JOB_UPDATED = "job.updated"
    JOB_PUBLISHED = "job.published"
    JOB_CLOSED = "job.closed"
    # Luồng xóa tay có actor HR; worker dùng cùng action với actor_id null.
    JOB_DELETED = "job.deleted"
    JOB_CRITERIA_SAVED = "job.criteria_saved"
    # Ghi bởi trigger trg_application_history trong database (migration 0005).
    APPLICATION_CREATED = "application.created"
    APPLICATION_STATUS_CHANGED = "application.status_changed"
    APPLICATION_LISTED = "application.listed"
    APPLICATION_VIEWED = "application.viewed"
    APPLICATION_CV_DOWNLOADED = "application.cv_downloaded"
    APPLICATION_REJECTED = "application.rejected"
    INTERVIEW_CONFIRMED = "interview.confirmed"
    INTERVIEW_DECLINED = "interview.declined"
    INTERVIEW_RESCHEDULE_REQUESTED = "interview.reschedule_requested"
    RESPONSE_EXPIRED = "response.expired"
    RESPONSE_INVALIDATED = "response.invalidated"
    TALENT_POOL_CONSENT_GRANTED = "talent_pool.consent_granted"
    TALENT_POOL_CONSENT_ACKNOWLEDGED = "talent_pool.consent_acknowledged"
    TALENT_POOL_CONSENT_DECLINED = "talent_pool.consent_declined"


class AuditEventInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: AuditAction
    outcome: AuditOutcome
    actor_id: uuid.UUID | None = None
    target_type: str | None = Field(default=None, max_length=32)
    target_id: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep only the documented metadata keys and reject sensitive-looking ones."""
    for key in metadata:
        lowered = key.lower()
        if lowered in METADATA_ALLOWLIST:
            continue
        if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
            raise ValueError(f"Audit metadata key is not permitted: {key}")
        raise ValueError(f"Audit metadata key is not allowlisted: {key}")
    return dict(metadata)


class AuditEventRead(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    outcome: AuditOutcome
    timestamp: datetime
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any]

    @classmethod
    def from_event(cls, event: AuditEvent) -> "AuditEventRead":
        """Build the Admin view; the stored event and its metadata are never modified."""
        hidden = HIDDEN_METADATA_BY_TARGET.get(event.target_type or "", frozenset())
        metadata = {
            key: copy.deepcopy(value)
            for key, value in (event.event_metadata or {}).items()
            if key not in hidden
        }
        return cls(
            id=event.id,
            actor_id=event.actor_id,
            action=event.action,
            outcome=event.outcome,
            timestamp=event.timestamp,
            target_type=event.target_type,
            target_id=event.target_id,
            metadata=metadata,
        )


class AuditEventPageRead(BaseModel):
    items: list[AuditEventRead]
    next_cursor: str | None
