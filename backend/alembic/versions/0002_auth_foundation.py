"""Create authentication, account, and audit tables."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ROLE_LITERALS = "'HR', 'INTERVIEWER', 'DEPT_MANAGER', 'PROBATION'"

ENUMS = {
    "account_type": ("ADMIN", "EMPLOYEE"),
    "account_status": (
        "PENDING_SETUP",
        "ACTIVE",
        "LOCKED",
        "PASSWORD_RESET_REQUIRED",
        "DISABLED",
    ),
    "password_link_purpose": ("INVITATION", "RECOVERY"),
    "audit_outcome": ("SUCCESS", "FAILURE"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    for name, values in ENUMS.items():
        literals = ", ".join(f"'{value}'" for value in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({literals})")

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("account_type", _enum("account_type"), nullable=False),
        sa.Column("roles", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", _enum("account_status"), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("email", name=op.f("uq_accounts_email")),
        sa.CheckConstraint(
            f"roles <@ ARRAY[{ROLE_LITERALS}]::text[]", name=op.f("ck_accounts_roles_known")
        ),
        sa.CheckConstraint(
            "array_position(roles, NULL) IS NULL", name=op.f("ck_accounts_roles_without_nulls")
        ),
        sa.CheckConstraint(
            "cardinality(roles) = 0 OR array_ndims(roles) = 1",
            name=op.f("ck_accounts_roles_one_dimensional"),
        ),
        sa.CheckConstraint(
            "cardinality(roles) = "
            "(('HR' = ANY(roles))::int + ('INTERVIEWER' = ANY(roles))::int"
            " + ('DEPT_MANAGER' = ANY(roles))::int + ('PROBATION' = ANY(roles))::int)",
            name=op.f("ck_accounts_roles_distinct"),
        ),
        sa.CheckConstraint(
            "CASE WHEN account_type = 'ADMIN' THEN cardinality(roles) = 0 "
            "ELSE cardinality(roles) >= 1"
            " AND NOT ('PROBATION' = ANY(roles) AND cardinality(roles) > 1) END",
            name=op.f("ck_accounts_account_type_roles"),
        ),
        sa.CheckConstraint(
            "status <> 'ACTIVE' OR password_hash IS NOT NULL",
            name=op.f("ck_accounts_active_requires_password"),
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_auth_sessions_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(
        "ix_auth_sessions_account_id_revoked_at",
        "auth_sessions",
        ["account_id", "revoked_at"],
    )

    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name=op.f("fk_auth_refresh_tokens_session_id_auth_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_refresh_tokens_token_hash")),
    )
    op.create_index("ix_auth_refresh_tokens_session_id", "auth_refresh_tokens", ["session_id"])

    op.create_table(
        "auth_password_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", _enum("password_link_purpose"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_auth_password_links_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_password_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_password_links_token_hash")),
    )
    op.create_index(
        "ix_auth_password_links_account_id_expires_at",
        "auth_password_links",
        ["account_id", "expires_at"],
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_auth_rate_limits")),
    )
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", _enum("audit_outcome"), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_timestamp_id", "audit_events", ["timestamp", "id"])
    op.create_index("ix_audit_events_action_timestamp", "audit_events", ["action", "timestamp"])
    op.create_index("ix_audit_events_actor_id_timestamp", "audit_events", ["actor_id", "timestamp"])
    op.create_index("ix_audit_events_target", "audit_events", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_target", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_action_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_timestamp_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_auth_rate_limits_expires_at", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_auth_password_links_account_id_expires_at", table_name="auth_password_links")
    op.drop_table("auth_password_links")
    op.drop_index("ix_auth_refresh_tokens_session_id", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_index("ix_auth_sessions_account_id_revoked_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("accounts")
    for name in ENUMS:
        op.execute(f"DROP TYPE {name}")
