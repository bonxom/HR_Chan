"""Interview and single-use response persistence."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
CREATE TYPE interview_status AS ENUM (
'SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED','CANCELLED','COMPLETED')
    """)
    op.execute("""
CREATE TYPE link_purpose AS ENUM ('CONFIRM_INTERVIEW','PROBATION_OFFER','TALENT_POOL_CONSENT')
    """)
    op.execute("""
CREATE TYPE link_outcome AS ENUM ('ACCEPTED','DECLINED','RESCHEDULE_REQUESTED','EXPIRED')
    """)
    op.execute("""
CREATE TABLE interviews (
  id                         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id             bigint NOT NULL REFERENCES applications(id),
  interviewer_id             uuid NOT NULL REFERENCES accounts(id),
  start_at                   timestamptz NOT NULL,
  end_at                     timestamptz NOT NULL,
  status                     interview_status NOT NULL DEFAULT 'SCHEDULED',
  google_event_id            varchar(200),
  meet_link                  varchar(300),
  auto_scheduled             boolean NOT NULL,
  reschedule_note            varchar(500),
  needs_manual_calendar_fix  boolean NOT NULL DEFAULT false,
  decline_reason             varchar(500),
  created_by                 uuid REFERENCES accounts(id),
  created_at                 timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT interviews_time_order CHECK (end_at > start_at),
  CONSTRAINT interviews_creator_required CHECK (auto_scheduled OR created_by IS NOT NULL),
  CONSTRAINT interviews_reschedule_note_required CHECK (
    status <> 'RESCHEDULE_REQUESTED' OR length(trim(coalesce(reschedule_note,''))) > 0),
  CONSTRAINT interviews_decline_only_cancelled CHECK (
    decline_reason IS NULL OR status = 'CANCELLED'),
  CONSTRAINT interviews_no_overlap EXCLUDE USING gist (
    interviewer_id WITH =, tstzrange(start_at, end_at) WITH &&)
    WHERE (status IN ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED'))
);
    """)
    op.execute("""
CREATE TABLE probation_offers (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id  bigint NOT NULL UNIQUE REFERENCES applications(id),
  start_date      date NOT NULL,
  duration_days   smallint NOT NULL CHECK (duration_days BETWEEN 1 AND 180),
  location        varchar(200) NOT NULL,
  manager_id      uuid NOT NULL REFERENCES accounts(id),
  created_by      uuid NOT NULL REFERENCES accounts(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  decline_reason  varchar(500)
);
    """)
    op.execute("""
CREATE TABLE response_links (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  token_hash      text NOT NULL UNIQUE,
  purpose         link_purpose NOT NULL,
  application_id  bigint NOT NULL REFERENCES applications(id),
  interview_id    bigint REFERENCES interviews(id),
  offer_id        bigint REFERENCES probation_offers(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL,
  used_at         timestamptz,
  outcome         link_outcome,
  invalidated_at  timestamptz,
  CONSTRAINT response_links_expiry CHECK (expires_at > created_at),
  CONSTRAINT response_links_used_pair CHECK ((used_at IS NULL) = (outcome IS NULL)),
  CONSTRAINT response_links_not_used_and_invalid CHECK (invalidated_at IS NULL OR used_at IS NULL),
  CONSTRAINT response_links_purpose_refs CHECK (
    (purpose = 'CONFIRM_INTERVIEW'   AND interview_id IS NOT NULL AND offer_id IS NULL)
    OR (purpose = 'PROBATION_OFFER'  AND offer_id IS NOT NULL AND interview_id IS NULL)
    OR (purpose = 'TALENT_POOL_CONSENT' AND interview_id IS NULL AND offer_id IS NULL)),
  CONSTRAINT response_links_reschedule_only_interview CHECK (
    outcome IS DISTINCT FROM 'RESCHEDULE_REQUESTED' OR purpose = 'CONFIRM_INTERVIEW')
);
    """)
    op.execute("""
CREATE UNIQUE INDEX interviews_one_active ON interviews (application_id)
  WHERE status IN ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED');
    """)
    op.execute("""
CREATE INDEX response_links_expiry_idx ON response_links (expires_at)
  WHERE used_at IS NULL AND invalidated_at IS NULL;
    """)


def downgrade():
    for table in ("response_links", "probation_offers", "interviews"):
        op.drop_table(table)
    for enum in ("link_outcome", "link_purpose", "interview_status"):
        op.execute(f"DROP TYPE {enum}")
