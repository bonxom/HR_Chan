"""Record explicit talent-pool consent and response settings."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE consent_source AS ENUM ('NO_MATCH_SCREEN','THANK_YOU_LINK')")
    op.execute("""
        CREATE TABLE talent_pool_consents (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            candidate_id bigint NOT NULL REFERENCES candidates(id),
            application_id bigint REFERENCES applications(id),
            source consent_source NOT NULL,
            policy_ver varchar(20) NOT NULL,
            consented_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            CONSTRAINT talent_pool_expiry CHECK (expires_at > consented_at)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX talent_pool_one_active ON talent_pool_consents(candidate_id)"
        " WHERE revoked_at IS NULL"
    )
    op.execute("""
        INSERT INTO system_settings(key,value,default_value,min_value,max_value,unit,description)
        VALUES
            ('talent_pool_months',12,12,1,24,'tháng','Thời hạn lưu hồ sơ'),
            ('max_reschedule_requests',2,2,0,5,'lần','Số yêu cầu đổi lịch tối đa'),
            ('reschedule_handle_days',1,1,1,3,'ngày làm việc','Hạn xử lý đổi lịch')
        ON CONFLICT(key) DO NOTHING
    """)


def downgrade():
    op.drop_table("talent_pool_consents")
    op.execute("DROP TYPE consent_source")
