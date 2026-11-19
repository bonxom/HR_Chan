"""Create recruitment job-posting tables: departments, settings, jobs, criteria.

Column sets, CHECK constraints and triggers follow docs/context/02_co_so_du_lieu.md.
Actor columns reference ``accounts.id`` (UUID) because the authentication module
implemented accounts instead of the context's bigint ``users`` table.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    # Tạo danh mục/cấu hình trước, rồi mới tạo tin và các bảng tiêu chí tham chiếu.
    # Ràng buộc/trigger trong migration là lớp bảo vệ ngoài validation của API.
    op.execute("CREATE TYPE job_status AS ENUM ('DRAFT', 'OPEN', 'CLOSED')")
    job_status = postgresql.ENUM("DRAFT", "OPEN", "CLOSED", name="job_status", create_type=False)

    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="departments_pkey"),
        sa.UniqueConstraint("name", name="departments_name_key"),
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("value_json", postgresql.JSONB(), nullable=True),
        sa.Column("default_value", sa.Numeric(), nullable=True),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="system_settings_pkey"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["accounts.id"], name="system_settings_updated_by_fkey"
        ),
        sa.CheckConstraint(
            "(value IS NULL) OR ((min_value IS NOT NULL) AND (max_value IS NOT NULL)"
            " AND (value >= min_value AND value <= max_value)"
            " AND (default_value >= min_value AND default_value <= max_value))",
            name="system_settings_in_range",
        ),
        sa.CheckConstraint(
            "(value IS NULL) <> (value_json IS NULL)", name="system_settings_one_value"
        ),
    )

    op.create_table(
        "job_postings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
        sa.Column("headcount", sa.Integer(), nullable=True),
        sa.Column("work_mode", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("status", job_status, server_default="DRAFT", nullable=False),
        sa.Column("current_criteria_set_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id", name="job_postings_pkey"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], name="job_postings_department_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["accounts.id"], name="job_postings_created_by_fkey"
        ),
        sa.CheckConstraint(
            "(status = 'CLOSED'::job_status) = (closed_at IS NOT NULL)", name="job_closed_at"
        ),
        sa.CheckConstraint(
            "(status <> 'OPEN'::job_status) OR ((description IS NOT NULL)"
            " AND (requirements IS NOT NULL) AND (headcount IS NOT NULL)"
            " AND (deadline IS NOT NULL) AND (current_criteria_set_id IS NOT NULL))",
            name="job_open_complete",
        ),
        sa.CheckConstraint("length(benefits) <= 3000", name="job_postings_benefits_check"),
        sa.CheckConstraint("length(description) <= 5000", name="job_postings_description_check"),
        sa.CheckConstraint("headcount > 0", name="job_postings_headcount_check"),
        sa.CheckConstraint("length(requirements) <= 5000", name="job_postings_requirements_check"),
    )
    op.execute(
        "CREATE INDEX ix_job_postings_embedding ON job_postings"
        " USING hnsw (embedding vector_cosine_ops) WHERE (status = 'OPEN'::job_status)"
    )
    op.create_index("ix_job_postings_status_created", "job_postings", ["status", "created_at"])

    op.create_table(
        "criteria_sets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("auto_invite_threshold", sa.Numeric(5, 2), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="criteria_sets_pkey"),
        sa.UniqueConstraint("id", "job_id", name="criteria_sets_id_job_id_key"),
        sa.UniqueConstraint("job_id", "version_no", name="criteria_sets_job_id_version_no_key"),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.id"], name="criteria_sets_job_id_fkey"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["accounts.id"], name="criteria_sets_created_by_fkey"
        ),
        sa.CheckConstraint(
            "auto_invite_threshold >= 0 AND auto_invite_threshold <= 100",
            name="criteria_sets_auto_invite_threshold_check",
        ),
        sa.CheckConstraint("version_no >= 1", name="criteria_sets_version_no_check"),
    )
    op.create_foreign_key(
        "job_current_criteria_fk",
        "job_postings",
        "criteria_sets",
        ["current_criteria_set_id", "id"],
        ["id", "job_id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "criteria",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("criteria_set_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="criteria_pkey"),
        sa.UniqueConstraint("criteria_set_id", "name", name="criteria_criteria_set_id_name_key"),
        sa.ForeignKeyConstraint(
            ["criteria_set_id"], ["criteria_sets.id"], name="criteria_criteria_set_id_fkey"
        ),
        sa.CheckConstraint("char_length(description) <= 1000", name="criteria_description_check"),
        sa.CheckConstraint("weight > 0 AND weight <= 100", name="criteria_weight_check"),
    )

    op.create_table(
        "job_interviewers",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.PrimaryKeyConstraint("job_id", "user_id", name="job_interviewers_pkey"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["job_postings.id"], name="job_interviewers_job_id_fkey"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.id"], name="job_interviewers_user_id_fkey"),
    )

    op.execute(
        """
        CREATE FUNCTION trg_criteria_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'criteria are immutable; save a new criteria set version'
                USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER criteria_immutable BEFORE UPDATE OR DELETE ON criteria"
        " FOR EACH ROW EXECUTE FUNCTION trg_criteria_immutable()"
    )
    op.execute(
        """
        CREATE FUNCTION trg_criteria_weight_sum() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            total numeric;
        BEGIN
            SELECT COALESCE(SUM(weight), 0) INTO total
            FROM criteria WHERE criteria_set_id = NEW.criteria_set_id;
            IF total <> 100 THEN
                RAISE EXCEPTION 'criteria weights of set % sum to %, expected 100',
                    NEW.criteria_set_id, total
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER criteria_weight_sum AFTER INSERT ON criteria"
        " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_criteria_weight_sum()"
    )

    op.execute(
        "INSERT INTO system_settings"
        " (key, value, default_value, min_value, max_value, unit, description)"
        " VALUES ('auto_invite_threshold', 70, 70, 0, 100, 'điểm',"
        " 'Ngưỡng tự động mời phỏng vấn mặc định cho bộ tiêu chí mới')"
    )


# Gỡ trigger/FK vòng trước khi gỡ bảng để không vướng quan hệ phụ thuộc.
def downgrade() -> None:
    op.execute("DROP TRIGGER criteria_weight_sum ON criteria")
    op.execute("DROP TRIGGER criteria_immutable ON criteria")
    op.execute("DROP FUNCTION trg_criteria_weight_sum()")
    op.execute("DROP FUNCTION trg_criteria_immutable()")
    op.drop_table("job_interviewers")
    op.drop_constraint("job_current_criteria_fk", "job_postings", type_="foreignkey")
    op.drop_table("criteria")
    op.drop_table("criteria_sets")
    op.drop_index("ix_job_postings_status_created", table_name="job_postings")
    op.execute("DROP INDEX ix_job_postings_embedding")
    op.drop_table("job_postings")
    op.drop_table("system_settings")
    op.drop_table("departments")
    op.execute("DROP TYPE job_status")
