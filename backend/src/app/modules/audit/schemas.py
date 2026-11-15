"""Allowlisted audit event contracts."""

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
    }
)

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
        return cls(
            id=event.id,
            actor_id=event.actor_id,
            action=event.action,
            outcome=event.outcome,
            timestamp=event.timestamp,
            target_type=event.target_type,
            target_id=event.target_id,
            metadata=event.event_metadata,
        )


class AuditEventPageRead(BaseModel):
    items: list[AuditEventRead]
    next_cursor: str | None
