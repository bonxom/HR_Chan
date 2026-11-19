"""Allow whole-posting deletion while retaining criterion history safeguards."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

FOREIGN_KEYS = (
    ("criteria_sets_job_id_fkey", "criteria_sets", "job_postings", "job_id"),
    ("criteria_criteria_set_id_fkey", "criteria", "criteria_sets", "criteria_set_id"),
    ("job_interviewers_job_id_fkey", "job_interviewers", "job_postings", "job_id"),
)


def _foreign_keys(ondelete: str | None) -> None:
    for name, source, target, column in FOREIGN_KEYS:
        op.drop_constraint(name, source, type_="foreignkey")
        op.create_foreign_key(name, source, target, [column], ["id"], ondelete=ondelete)


def upgrade() -> None:
    # Đổi quan hệ xóa, không xóa bản ghi đang có khi chạy migration.
    _foreign_keys("CASCADE")
    # Cascade chạy sau khi parent đã bị xóa: guard chỉ cho xóa set khi job không
    # còn tồn tại, rồi mới cho xóa criterion khi set không còn. UPDATE set vẫn cấm
    # để không thể chuyển lịch sử sang tin khác rồi lợi dụng cascade xóa nhầm.
    op.execute("""
        CREATE FUNCTION trg_criteria_set_delete_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'criteria sets are immutable; save a new version'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF EXISTS (SELECT 1 FROM job_postings WHERE id = OLD.job_id) THEN
                RAISE EXCEPTION 'criteria sets may only be deleted with their posting'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN OLD;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER criteria_set_delete_guard BEFORE UPDATE OR DELETE ON criteria_sets
        FOR EACH ROW EXECUTE FUNCTION trg_criteria_set_delete_guard()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_criteria_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF NOT EXISTS (SELECT 1 FROM criteria_sets WHERE id = OLD.criteria_set_id) THEN
                    RETURN OLD;
                END IF;
            END IF;
            RAISE EXCEPTION 'criteria are immutable; save a new criteria set version'
                USING ERRCODE = 'check_violation';
        END;
        $$
    """)


def downgrade() -> None:
    # Khôi phục quy tắc cũ; không thay revision hay nội dung migration0003.
    op.execute("DROP TRIGGER criteria_set_delete_guard ON criteria_sets")
    op.execute("DROP FUNCTION trg_criteria_set_delete_guard()")
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_criteria_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'criteria are immutable; save a new criteria set version'
                USING ERRCODE = 'check_violation';
        END;
        $$
    """)
    _foreign_keys(None)
