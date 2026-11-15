import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.accounts.rules import AccountStatus, AccountType, EmployeeRole

_ROLE_LITERALS = ", ".join(f"'{role.value}'" for role in EmployeeRole)


class Account(Base):
    """An internal account identity and its administrative lifecycle state.

    Departments and department-scoped authorization are intentionally deferred until
    organizational data and the corresponding business modules are implemented.
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Stored normalized (trimmed, lowercased); uniqueness is therefore case-insensitive.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type"), nullable=False
    )
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"), nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"roles <@ ARRAY[{_ROLE_LITERALS}]::text[]", name="roles_known"),
        CheckConstraint("array_position(roles, NULL) IS NULL", name="roles_without_nulls"),
        CheckConstraint(
            "cardinality(roles) = 0 OR array_ndims(roles) = 1",
            name="roles_one_dimensional",
        ),
        CheckConstraint(
            "cardinality(roles) = "
            "(('HR' = ANY(roles))::int + ('INTERVIEWER' = ANY(roles))::int"
            " + ('DEPT_MANAGER' = ANY(roles))::int + ('PROBATION' = ANY(roles))::int)",
            name="roles_distinct",
        ),
        CheckConstraint(
            "CASE WHEN account_type = 'ADMIN' THEN cardinality(roles) = 0 "
            "ELSE cardinality(roles) >= 1"
            " AND NOT ('PROBATION' = ANY(roles) AND cardinality(roles) > 1) END",
            name="account_type_roles",
        ),
        CheckConstraint(
            "status <> 'ACTIVE' OR password_hash IS NOT NULL",
            name="active_requires_password",
        ),
    )
