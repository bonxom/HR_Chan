"""Create application and email outbox tables from context 02.

candidates, cv_submissions, otp_codes, applications, email_templates, email_outbox with
their enums, CHECK/UNIQUE/FK constraints, indexes and the two triggers
(``trg_template_required_vars``, ``trg_application_history``).

Mapping approved in context 00 §4.11: references to ``users`` are UUID FKs to
``accounts.id``; application history is written to ``audit_events``. Business IDs stay
BIGINT. No FK cascades: postings, CVs and candidates referenced by applications cannot
be deleted. Only additions; nothing existing is altered.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536

ENUMS = {
    "ai_score_status": ("PENDING", "SCORED", "NEEDS_REVIEW", "FAILED"),
    "application_status": (
        "SCORING",
        "PENDING_HR_REVIEW",
        "INTERVIEW_INVITED",
        "INTERVIEW_CONFIRMED",
        "INTERVIEW_DECLINED",
        "AWAITING_INTERVIEW_RESULT",
        "INTERVIEW_PASSED",
        "INTERVIEW_FAILED",
        "REJECTED",
        "AWAITING_ACCOUNT",
        "ON_PROBATION",
        "PROBATION_DECLINED",
        "PROBATION_PASSED",
        "PROBATION_FAILED",
    ),
    "email_status": ("PENDING", "SENT", "FAILED"),
    "otp_purpose": ("APPLY", "RESET_PASSWORD"),
    "parse_status": ("PENDING", "PARSED", "PARTIAL", "FAILED"),
    "scan_status": ("PENDING", "CLEAN", "INFECTED"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _citext() -> sa.types.TypeEngine:
    from app.db.types import CIText

    return CIText()


def _ck(sqltext: str, name: str) -> sa.CheckConstraint:
    # op.f giữ đúng tên của context 02; nếu không, naming convention "ck_%(table)s_..."
    # của Base.metadata (được alembic áp dụng) sẽ đổi tên ràng buộc.
    return sa.CheckConstraint(sqltext, name=op.f(name))


def _ts(nullable: bool = False, default: bool = False) -> dict:
    return {
        "type_": sa.DateTime(timezone=True),
        "nullable": nullable,
        **({"server_default": sa.text("now()")} if default else {}),
    }


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for name, values in ENUMS.items():
        literals = ", ".join(f"'{value}'" for value in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({literals})")

    op.create_table(
        "candidates",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("email", _citext(), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.CHAR(length=10), nullable=False),
        sa.Column("created_at", **_ts(default=True)),
        sa.Column("anonymized_at", **_ts(nullable=True)),
        sa.PrimaryKeyConstraint("id", name="candidates_pkey"),
        sa.UniqueConstraint("email", name="candidates_email_key"),
        _ck("phone ~ '^[0-9]{10}$'", name="candidates_phone_check"),
    )

    op.create_table(
        "cv_submissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("cv_storage_key", sa.String(length=100), nullable=False),
        sa.Column("cv_original_name", sa.String(length=255), nullable=False),
        sa.Column("cv_mime_type", sa.String(length=100), nullable=False),
        sa.Column("cv_size_bytes", sa.Integer(), nullable=False),
        sa.Column("cv_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("cv_scan_status", _enum("scan_status"), nullable=False),
        sa.Column("consent_at", **_ts()),
        sa.Column("consent_policy_ver", sa.String(length=20), nullable=False),
        sa.Column("parse_status", _enum("parse_status"), nullable=False),
        sa.Column("parsed_data", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
        sa.Column("suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("created_at", **_ts(default=True)),
        sa.Column("expires_at", **_ts()),
        sa.PrimaryKeyConstraint("id", name="cv_submissions_pkey"),
        sa.UniqueConstraint("cv_storage_key", name="cv_submissions_cv_storage_key_key"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"], name="cv_submissions_candidate_id_fkey"
        ),
        _ck(
            "cv_mime_type IN ('application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
            name="cv_submissions_cv_mime_type_check",
        ),
        _ck(
            "cv_size_bytes > 0 AND cv_size_bytes <= 5 * 1024 * 1024",
            name="cv_submissions_cv_size_bytes_check",
        ),
        _ck("expires_at > created_at", name="cv_submissions_expiry"),
        _ck(
            "parse_status IN ('PENDING', 'FAILED') OR parsed_data IS NOT NULL",
            name="cv_submissions_parsed_has_data",
        ),
        _ck(
            "suggestions IS NULL OR (jsonb_typeof(suggestions) = 'array'"
            " AND jsonb_array_length(suggestions) <= 10)",
            name="cv_submissions_suggestions_check",
        ),
    )
    op.create_index("cv_submissions_expiry_idx", "cv_submissions", ["expires_at"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("email", _citext(), nullable=False),
        sa.Column("purpose", _enum("otp_purpose"), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=True),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("created_at", **_ts(default=True)),
        sa.Column("expires_at", **_ts()),
        sa.Column("consumed_at", **_ts(nullable=True)),
        sa.Column("invalidated_at", **_ts(nullable=True)),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="otp_codes_pkey"),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.id"], name="otp_codes_job_id_fkey"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["cv_submissions.id"], name="otp_codes_submission_id_fkey"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.id"], name="otp_codes_user_id_fkey"),
        _ck("attempts >= 0 AND attempts <= 5", name="otp_codes_attempts_check"),
        _ck("expires_at > created_at", name="otp_codes_expiry"),
        _ck(
            "(purpose = 'APPLY'::otp_purpose AND submission_id IS NOT NULL"
            " AND job_id IS NOT NULL AND user_id IS NULL)"
            " OR (purpose = 'RESET_PASSWORD'::otp_purpose AND user_id IS NOT NULL"
            " AND submission_id IS NULL AND job_id IS NULL)",
            name="otp_codes_purpose_refs",
        ),
    )
    op.create_index(
        "otp_one_live_code",
        "otp_codes",
        ["email", "purpose"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND invalidated_at IS NULL"),
    )
    op.create_index("otp_rate_idx", "otp_codes", ["email", "purpose", "created_at"])

    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=False),
        sa.Column("status", _enum("application_status"), nullable=False),
        sa.Column("submitted_at", **_ts()),
        sa.Column("criteria_set_id", sa.BigInteger(), nullable=True),
        sa.Column("ai_status", _enum("ai_score_status"), nullable=False),
        sa.Column("ai_total_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_failure_reason", sa.Text(), nullable=True),
        sa.Column("hr_note", sa.Text(), nullable=True),
        sa.Column("email_issue", sa.String(length=100), nullable=True),
        sa.Column("review_due_at", **_ts(nullable=True)),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", **_ts(nullable=True)),
        sa.Column("reject_reason_code", sa.String(length=40), nullable=True),
        sa.Column("reject_reason_text", sa.Text(), nullable=True),
        sa.Column("updated_at", **_ts(default=True)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id", name="applications_pkey"),
        sa.UniqueConstraint("candidate_id", "job_id", name="applications_candidate_id_job_id_key"),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"], name="applications_candidate_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["criteria_set_id", "job_id"],
            ["criteria_sets.id", "criteria_sets.job_id"],
            name="applications_criteria_set_fk",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["accounts.id"], name="applications_decided_by_fkey"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.id"], name="applications_job_id_fkey"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["cv_submissions.id"], name="applications_submission_id_fkey"
        ),
        _ck(
            "ai_total_score >= 0 AND ai_total_score <= 100",
            name="applications_ai_total_score_check",
        ),
        _ck(
            "reject_reason_code IS DISTINCT FROM 'OTHER'"
            " OR length(trim(COALESCE(reject_reason_text, ''))) > 0",
            name="applications_other_reason_text",
        ),
        _ck(
            "reject_reason_text IS NULL OR char_length(reject_reason_text) <= 500",
            name="applications_reject_reason_text_check",
        ),
        _ck(
            "status <> 'REJECTED'::application_status OR (decided_by IS NOT NULL"
            " AND decided_at IS NOT NULL AND reject_reason_code IS NOT NULL)",
            name="applications_rejected_by_hr",
        ),
        _ck(
            "ai_status <> 'SCORED'::ai_score_status"
            " OR (ai_total_score IS NOT NULL AND criteria_set_id IS NOT NULL)",
            name="applications_scored_complete",
        ),
    )
    op.create_index("applications_job_idx", "applications", ["job_id", "status"])
    op.create_index("applications_status_idx", "applications", ["status", "submitted_at"])

    op.create_table(
        "email_templates",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("required_vars", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", **_ts(default=True)),
        sa.PrimaryKeyConstraint("code", name="email_templates_pkey"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["accounts.id"], name="email_templates_updated_by_fkey"
        ),
    )

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("template_code", sa.String(length=50), nullable=False),
        sa.Column("to_email", _citext(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", _enum("email_status"), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", **_ts(default=True)),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", **_ts(default=True)),
        sa.Column("sent_at", **_ts(nullable=True)),
        sa.PrimaryKeyConstraint("id", name="email_outbox_pkey"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="email_outbox_application_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["template_code"], ["email_templates.code"], name="email_outbox_template_code_fkey"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.id"], name="email_outbox_user_id_fkey"),
        _ck("attempts >= 0 AND attempts <= 4", name="email_outbox_attempts_check"),
        _ck(
            "status <> 'FAILED'::email_status OR (attempts >= 1 AND last_error IS NOT NULL)",
            name="email_outbox_failed_has_error",
        ),
        _ck(
            "status = 'SENT'::email_status OR sent_at IS NULL",
            name="email_outbox_sent_at_only_sent",
        ),
        _ck(
            "status <> 'SENT'::email_status OR (sent_at IS NOT NULL AND attempts >= 1)",
            name="email_outbox_sent_complete",
        ),
        _ck("(subject)::text !~ '[\\r\\n]'", name="email_outbox_subject_no_newline"),
        _ck(
            "to_email !~ '[\\r\\n]'::citext AND position('@' IN to_email) > 1",
            name="email_outbox_to_email_check",
        ),
    )
    op.create_index(
        "ix_email_outbox_application",
        "email_outbox",
        ["application_id"],
        postgresql_where=sa.text("application_id IS NOT NULL"),
    )
    op.create_index(
        "ix_email_outbox_due",
        "email_outbox",
        ["next_attempt_at"],
        postgresql_where=sa.text("status = 'PENDING'::email_status"),
    )

    # Mẫu email phải chứa đủ biến bắt buộc (BR46). Biến được tính là có mặt khi
    # placeholder {ten_bien} xuất hiện trong tiêu đề hoặc nội dung của mẫu.
    op.execute(
        """
        CREATE FUNCTION trg_template_required_vars() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            var text;
        BEGIN
            FOREACH var IN ARRAY COALESCE(NEW.required_vars, ARRAY[]::text[]) LOOP
                IF position('{' || var || '}' IN NEW.subject || E'\\n' || NEW.body) = 0 THEN
                    RAISE EXCEPTION 'email template % is missing required variable %',
                        NEW.code, var
                        USING ERRCODE = 'check_violation';
                END IF;
            END LOOP;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER email_templates_vars BEFORE INSERT OR UPDATE ON email_templates"
        " FOR EACH ROW EXECUTE FUNCTION trg_template_required_vars()"
    )

    # Lịch sử trạng thái hồ sơ ghi vào audit_events (ánh xạ audit_logs, 00 §4.11).
    # Người thực hiện lấy từ app.actor_id (SET LOCAL trong giao dịch); rỗng/không có
    # nghĩa là hệ thống hoặc ứng viên. Metadata chỉ có trạng thái, không dữ liệu cá nhân.
    op.execute(
        """
        CREATE FUNCTION trg_application_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            actor uuid := NULLIF(current_setting('app.actor_id', true), '')::uuid;
            previous text := NULL;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
                    RETURN NULL;
                END IF;
                previous := OLD.status::text;
            END IF;
            INSERT INTO audit_events
                (id, actor_id, action, outcome, timestamp, target_type, target_id, metadata)
            VALUES (
                gen_random_uuid(),
                actor,
                CASE WHEN TG_OP = 'INSERT' THEN 'application.created'
                     ELSE 'application.status_changed' END,
                'SUCCESS'::audit_outcome,
                now(),
                'application',
                NEW.id::text,
                jsonb_build_object(
                    'changes',
                    jsonb_build_object(
                        'status',
                        jsonb_build_object('before', previous, 'after', NEW.status::text)
                    )
                )
            );
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER applications_history AFTER INSERT OR UPDATE ON applications"
        " FOR EACH ROW EXECUTE FUNCTION trg_application_history()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER applications_history ON applications")
    op.execute("DROP FUNCTION trg_application_history()")
    op.execute("DROP TRIGGER email_templates_vars ON email_templates")
    op.execute("DROP FUNCTION trg_template_required_vars()")
    op.drop_table("email_outbox")
    op.drop_table("email_templates")
    op.drop_table("applications")
    op.drop_table("otp_codes")
    op.drop_table("cv_submissions")
    op.drop_table("candidates")
    for name in ENUMS:
        op.execute(f"DROP TYPE {name}")
    # citext được giữ lại: extension có thể đang được đối tượng khác dùng.
