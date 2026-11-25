"""Add mandatory floors, per-criterion scores and working-day deadlines."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("LOCK TABLE criteria IN ACCESS EXCLUSIVE MODE")
    op.add_column("criteria", sa.Column("min_score", sa.Numeric(5, 2)))
    # Historical mandatory criteria receive a floor of 50, including superseded versions.
    # PostgreSQL rolls the DDL and backfill back together if any statement fails.
    op.execute("ALTER TABLE criteria DISABLE TRIGGER criteria_immutable")
    op.execute("UPDATE criteria SET min_score = 50 WHERE is_mandatory")
    op.execute("ALTER TABLE criteria ENABLE TRIGGER criteria_immutable")
    op.create_check_constraint(
        op.f("criteria_min_score_mandatory"),
        "criteria",
        "(is_mandatory AND min_score IS NOT NULL AND min_score BETWEEN 0 AND 100)"
        " OR (NOT is_mandatory AND min_score IS NULL)",
    )
    op.create_table(
        "application_scores",
        sa.Column(
            "application_id", sa.BigInteger, sa.ForeignKey("applications.id"), primary_key=True
        ),
        sa.Column("criterion_id", sa.BigInteger, sa.ForeignKey("criteria.id"), primary_key=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("weight_snapshot", sa.Numeric(5, 2), nullable=False),
        sa.Column("ai_comment", sa.Text),
        sa.Column("meets_mandatory", sa.Boolean),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        sa.CheckConstraint("weight_snapshot > 0 AND weight_snapshot <= 100", name="weight_range"),
    )
    op.create_table(
        "holidays",
        sa.Column("holiday_date", sa.Date, primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
    )
    op.execute("""
        INSERT INTO system_settings
            (key, value, value_json, default_value, min_value, max_value, unit, description)
        VALUES
          ('working_hours', NULL, '{"start":"08:00","end":"17:30"}', NULL, NULL, NULL,
           NULL, 'Giờ làm việc thứ Hai – thứ Sáu'),
          ('response_deadline_days', 2, NULL, 2, 1, 5, 'ngày làm việc',
           'Hạn phản hồi của ứng viên'),
          ('hr_review_days', 5, NULL, 5, 1, 10, 'ngày làm việc', 'Hạn HR xét duyệt hồ sơ')
        ON CONFLICT (key) DO NOTHING
    """)
    op.execute("""
        CREATE FUNCTION working_deadline(p_from timestamptz, p_days integer)
        RETURNS timestamptz LANGUAGE plpgsql STABLE STRICT AS $$
        DECLARE
            tz constant text := 'Asia/Ho_Chi_Minh';
            d date := (p_from AT TIME ZONE tz)::date;
            n integer := 0;
            closing time;
        BEGIN
            IF p_days < 1 THEN RAISE EXCEPTION 'p_days phải >= 1'; END IF;
            SELECT (value_json->>'end')::time INTO closing
                FROM system_settings WHERE key = 'working_hours';
            WHILE n < p_days LOOP
                d := d + 1;
                IF extract(isodow FROM d) < 6
                   AND NOT EXISTS (SELECT 1 FROM holidays WHERE holiday_date = d) THEN
                    n := n + 1;
                END IF;
            END LOOP;
            RETURN (d + coalesce(closing, time '17:30')) AT TIME ZONE tz;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION working_deadline(timestamptz, integer)")
    op.drop_table("holidays")
    op.drop_table("application_scores")
    op.drop_constraint(op.f("criteria_min_score_mandatory"), "criteria", type_="check")
    op.drop_column("criteria", "min_score")
    # Keep operator settings, including keys which existed before this upgrade.
