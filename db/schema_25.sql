-- =====================================================================
-- HỆ THỐNG TUYỂN DỤNG VÀ THỬ VIỆC – LƯỢC ĐỒ CSDL (PostgreSQL 16 + pgvector)
-- Phiên bản: 25 bảng (13/11/2026)
--   * Áp đợt rút gọn 03/11 (mục 4.8 file context 00):
--       - interviews: bỏ 4 cột proposed_slot*, thêm reschedule_note
--       - users: bỏ google_user_id (Admin nhập email công ty)
--       - cv_submissions: bỏ needs_hr_attention (không nhận dạng CV ảnh)
--       - xóa bảng handover_items + enum handover_status, handover_type
--       - audit_logs: bỏ hành động EMERGENCY_LOCK khỏi CHECK lý do
--   * Bỏ trích dẫn bằng chứng (04/11): application_scores bỏ
--     evidence_quote, evidence_verified; score NOT NULL
--   * 16/11: bỏ quy tắc "luôn còn ít nhất 2 Admin" (Admin thuộc hệ thống lớn):
--     xóa trigger kiểm tra số Admin
--   * 16/11 (sau): hệ thống con chỉ có 1 Admin: bỏ 3 cột cửa sổ đặt lại mật khẩu
--     Admin, thêm chỉ mục users_one_admin, CHECK lý do bỏ CREATE_ADMIN/RESET_ADMIN_PASSWORD
-- Cách dùng: psql -v ON_ERROR_STOP=1 -f schema_25.sql   (CSDL rỗng)
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------
-- 1. KIỂU LIỆT KÊ (16 enum)
-- ---------------------------------------------------------------------
CREATE TYPE account_status     AS ENUM ('ACTIVE','LOCKED','PENDING_ADMIN','DELETED');
CREATE TYPE account_type       AS ENUM ('EMPLOYEE','ADMIN');
CREATE TYPE business_role      AS ENUM ('HR','INTERVIEWER','DEPT_MANAGER','PROBATION');
CREATE TYPE job_status         AS ENUM ('DRAFT','OPEN','CLOSED');
CREATE TYPE scan_status        AS ENUM ('PENDING','CLEAN','INFECTED');
CREATE TYPE parse_status       AS ENUM ('PENDING','PARSED','PARTIAL','FAILED');
CREATE TYPE otp_purpose        AS ENUM ('APPLY','RESET_PASSWORD');
CREATE TYPE application_status AS ENUM (
  'SCORING','PENDING_HR_REVIEW','INTERVIEW_INVITED','INTERVIEW_CONFIRMED',
  'INTERVIEW_DECLINED','AWAITING_INTERVIEW_RESULT','INTERVIEW_PASSED',
  'INTERVIEW_FAILED','REJECTED','AWAITING_ACCOUNT','ON_PROBATION',
  'PROBATION_DECLINED','PROBATION_PASSED','PROBATION_FAILED');
CREATE TYPE ai_score_status    AS ENUM ('PENDING','SCORED','NEEDS_REVIEW','FAILED');
CREATE TYPE consent_source     AS ENUM ('NO_MATCH_SCREEN','THANK_YOU_LINK');
CREATE TYPE interview_status   AS ENUM ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED','CANCELLED','COMPLETED');
CREATE TYPE pass_fail          AS ENUM ('PASS','FAIL');
CREATE TYPE link_purpose       AS ENUM ('CONFIRM_INTERVIEW','PROBATION_OFFER','TALENT_POOL_CONSENT');
CREATE TYPE link_outcome       AS ENUM ('ACCEPTED','DECLINED','RESCHEDULE_REQUESTED','EXPIRED');
CREATE TYPE probation_status   AS ENUM ('ONGOING','PASSED','FAILED');
CREATE TYPE email_status       AS ENUM ('PENDING','SENT','FAILED');

-- ---------------------------------------------------------------------
-- 2. NHÓM TỔ CHỨC VÀ TÀI KHOẢN
-- ---------------------------------------------------------------------
CREATE TABLE departments (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       varchar(150) NOT NULL UNIQUE,
  is_active  boolean NOT NULL DEFAULT true
);

CREATE TABLE users (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_type             account_type NOT NULL,
  full_name                varchar(100) NOT NULL,
  email                    citext,
  department_id            bigint REFERENCES departments(id),
  status                   account_status NOT NULL DEFAULT 'ACTIVE',
  password_hash            text,
  password_changed_at      timestamptz,
  token_version            integer NOT NULL DEFAULT 0,
  change_pw_fail_count     smallint NOT NULL DEFAULT 0,
  change_pw_locked_until   timestamptz,
  login_fail_count         smallint NOT NULL DEFAULT 0,
  login_locked_until       timestamptz,
  last_login_at            timestamptz,
  created_by               bigint REFERENCES users(id),
  created_at               timestamptz NOT NULL DEFAULT now(),
  deleted_at               timestamptz,
  version                  integer NOT NULL DEFAULT 1,
  CONSTRAINT users_id_account_type_key UNIQUE (id, account_type),
  CONSTRAINT users_active_has_email CHECK (status = 'DELETED' OR email IS NOT NULL),
  CONSTRAINT users_admin_no_department CHECK (account_type = 'EMPLOYEE' OR department_id IS NULL),
  CONSTRAINT users_deleted_anonymized CHECK (
    ((status = 'DELETED') = (deleted_at IS NOT NULL))
    AND (status <> 'DELETED' OR (email IS NULL AND password_hash IS NULL))),
  CONSTRAINT users_email_format CHECK (email IS NULL OR email ~* '^[^@\s]+@[^@\s]+$')
);
CREATE UNIQUE INDEX users_email_uq ON users (email) WHERE email IS NOT NULL;
-- Hệ thống con chỉ có đúng 1 tài khoản Admin (do hệ thống nhân sự lớn cấp)
CREATE UNIQUE INDEX users_one_admin ON users (account_type) WHERE account_type = 'ADMIN' AND status <> 'DELETED';

CREATE TABLE user_roles (
  user_id       bigint NOT NULL,
  account_type  account_type NOT NULL DEFAULT 'EMPLOYEE' CHECK (account_type = 'EMPLOYEE'),
  role          business_role NOT NULL,
  granted_by    bigint REFERENCES users(id),
  granted_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, role),
  FOREIGN KEY (user_id, account_type) REFERENCES users(id, account_type)
);

-- ---------------------------------------------------------------------
-- 3. NHÓM CẤU HÌNH, THÔNG BÁO, NHẬT KÝ
-- ---------------------------------------------------------------------
CREATE TABLE system_settings (
  key            varchar(80) PRIMARY KEY,
  value          numeric,
  value_json     jsonb,
  default_value  numeric,
  min_value      numeric,
  max_value      numeric,
  unit           varchar(30),
  description    text,
  updated_by     bigint REFERENCES users(id),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT system_settings_one_value CHECK ((value IS NULL) <> (value_json IS NULL)),
  CONSTRAINT system_settings_in_range CHECK (
    value IS NULL OR (min_value IS NOT NULL AND max_value IS NOT NULL
      AND value BETWEEN min_value AND max_value
      AND default_value BETWEEN min_value AND max_value))
);

CREATE TABLE holidays (
  holiday_date  date PRIMARY KEY,
  name          varchar(150) NOT NULL
);

CREATE TABLE email_templates (
  code           varchar(50) PRIMARY KEY,
  subject        varchar(255) NOT NULL,
  body           text NOT NULL,
  required_vars  text[] NOT NULL DEFAULT '{}',
  updated_by     bigint REFERENCES users(id),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at  timestamptz NOT NULL DEFAULT now(),
  actor_id     bigint REFERENCES users(id),
  action       varchar(60) NOT NULL,
  target_type  varchar(40) NOT NULL,
  target_id    bigint,
  reason       text,
  before_data  jsonb,
  after_data   jsonb,
  ip           inet,
  CONSTRAINT audit_logs_reason_required CHECK (
    action NOT IN ('LOCK','UNLOCK','DELETE_ACCOUNT','REVOKE_ROLE')
    OR length(trim(coalesce(reason,''))) > 0)
);
CREATE INDEX audit_logs_target_idx ON audit_logs (target_type, target_id, occurred_at);
CREATE INDEX audit_logs_time_idx   ON audit_logs (occurred_at);

-- ---------------------------------------------------------------------
-- 4. NHÓM TIN TUYỂN DỤNG VÀ TIÊU CHÍ
-- ---------------------------------------------------------------------
CREATE TABLE job_postings (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  title                    varchar(200) NOT NULL,
  department_id            bigint NOT NULL REFERENCES departments(id),
  description              text CHECK (length(description) <= 5000),
  requirements             text CHECK (length(requirements) <= 5000),
  benefits                 text CHECK (length(benefits) <= 3000),
  embedding                vector(1536),
  headcount                integer CHECK (headcount > 0),
  work_mode                varchar(50),
  location                 varchar(200),
  deadline                 date,
  status                   job_status NOT NULL DEFAULT 'DRAFT',
  current_criteria_set_id  bigint,
  created_by               bigint NOT NULL REFERENCES users(id),
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  closed_at                timestamptz,
  version                  integer NOT NULL DEFAULT 1,
  CONSTRAINT job_closed_at CHECK ((status = 'CLOSED') = (closed_at IS NOT NULL)),
  CONSTRAINT job_open_complete CHECK (status <> 'OPEN' OR (description IS NOT NULL
    AND requirements IS NOT NULL AND headcount IS NOT NULL AND deadline IS NOT NULL
    AND current_criteria_set_id IS NOT NULL))
);
CREATE INDEX ix_job_postings_embedding ON job_postings
  USING hnsw (embedding vector_cosine_ops) WHERE status = 'OPEN';

CREATE TABLE criteria_sets (
  id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id                 bigint NOT NULL REFERENCES job_postings(id),
  version_no             integer NOT NULL CHECK (version_no >= 1),
  auto_invite_threshold  numeric(5,2) NOT NULL CHECK (auto_invite_threshold BETWEEN 0 AND 100),
  created_by             bigint NOT NULL REFERENCES users(id),
  created_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT criteria_sets_id_job_id_key UNIQUE (id, job_id),
  CONSTRAINT criteria_sets_job_id_version_no_key UNIQUE (job_id, version_no)
);

ALTER TABLE job_postings ADD CONSTRAINT job_current_criteria_fk
  FOREIGN KEY (current_criteria_set_id, id) REFERENCES criteria_sets(id, job_id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE criteria (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  criteria_set_id  bigint NOT NULL REFERENCES criteria_sets(id),
  name             varchar(150) NOT NULL,
  description      text NOT NULL CHECK (char_length(description) <= 1000),
  is_mandatory     boolean NOT NULL DEFAULT false,
  weight           numeric(5,2) NOT NULL CHECK (weight > 0 AND weight <= 100),
  CONSTRAINT criteria_criteria_set_id_name_key UNIQUE (criteria_set_id, name)
);

CREATE TABLE job_interviewers (
  job_id       bigint NOT NULL REFERENCES job_postings(id),
  user_id      bigint NOT NULL REFERENCES users(id),
  assigned_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (job_id, user_id)
);

-- ---------------------------------------------------------------------
-- 5. NHÓM ỨNG VIÊN VÀ HỒ SƠ
-- ---------------------------------------------------------------------
CREATE TABLE candidates (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email          citext NOT NULL UNIQUE,
  full_name      varchar(100) NOT NULL,
  phone          char(10) NOT NULL CHECK (phone ~ '^[0-9]{10}$'),
  created_at     timestamptz NOT NULL DEFAULT now(),
  anonymized_at  timestamptz
);

CREATE TABLE cv_submissions (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  candidate_id        bigint NOT NULL REFERENCES candidates(id),
  cv_storage_key      varchar(100) NOT NULL UNIQUE,
  cv_original_name    varchar(255) NOT NULL,
  cv_mime_type        varchar(100) NOT NULL CHECK (cv_mime_type IN (
                        'application/pdf',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
  cv_size_bytes       integer NOT NULL CHECK (cv_size_bytes > 0 AND cv_size_bytes <= 5*1024*1024),
  cv_sha256           char(64) NOT NULL,
  cv_scan_status      scan_status NOT NULL DEFAULT 'PENDING',
  consent_at          timestamptz NOT NULL,
  consent_policy_ver  varchar(20) NOT NULL,
  parse_status        parse_status NOT NULL DEFAULT 'PENDING',
  parsed_data         jsonb,
  embedding           vector(1536),
  suggestions         jsonb,
  ip                  inet,
  created_at          timestamptz NOT NULL DEFAULT now(),
  expires_at          timestamptz NOT NULL,
  CONSTRAINT cv_submissions_expiry CHECK (expires_at > created_at),
  CONSTRAINT cv_submissions_parsed_has_data CHECK (
    parse_status IN ('PENDING','FAILED') OR parsed_data IS NOT NULL),
  CONSTRAINT cv_submissions_suggestions_check CHECK (suggestions IS NULL OR (
    jsonb_typeof(suggestions) = 'array' AND jsonb_array_length(suggestions) <= 10))
);
CREATE INDEX cv_submissions_expiry_idx ON cv_submissions (expires_at);

CREATE TABLE otp_codes (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email           citext NOT NULL,
  purpose         otp_purpose NOT NULL,
  code_hash       text NOT NULL,
  submission_id   bigint REFERENCES cv_submissions(id),
  job_id          bigint REFERENCES job_postings(id),
  user_id         bigint REFERENCES users(id),
  attempts        smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL,
  consumed_at     timestamptz,
  invalidated_at  timestamptz,
  ip              inet,
  CONSTRAINT otp_codes_expiry CHECK (expires_at > created_at),
  CONSTRAINT otp_codes_purpose_refs CHECK (
    (purpose = 'APPLY' AND submission_id IS NOT NULL AND job_id IS NOT NULL AND user_id IS NULL)
    OR (purpose = 'RESET_PASSWORD' AND user_id IS NOT NULL AND submission_id IS NULL AND job_id IS NULL))
);
CREATE UNIQUE INDEX otp_one_live_code ON otp_codes (email, purpose)
  WHERE consumed_at IS NULL AND invalidated_at IS NULL;
CREATE INDEX otp_rate_idx ON otp_codes (email, purpose, created_at);

CREATE TABLE applications (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  candidate_id        bigint NOT NULL REFERENCES candidates(id),
  job_id              bigint NOT NULL REFERENCES job_postings(id),
  submission_id       bigint NOT NULL REFERENCES cv_submissions(id),
  status              application_status NOT NULL DEFAULT 'SCORING',
  submitted_at        timestamptz NOT NULL DEFAULT now(),
  criteria_set_id     bigint,
  ai_status           ai_score_status NOT NULL DEFAULT 'PENDING',
  ai_total_score      numeric(5,2) CHECK (ai_total_score BETWEEN 0 AND 100),
  ai_failure_reason   text,
  hr_note             text,
  email_issue         varchar(100),
  review_due_at       timestamptz,
  decided_by          bigint REFERENCES users(id),
  decided_at          timestamptz,
  reject_reason_code  varchar(40),
  reject_reason_text  text CHECK (reject_reason_text IS NULL OR char_length(reject_reason_text) <= 500),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  version             integer NOT NULL DEFAULT 1,
  CONSTRAINT applications_candidate_id_job_id_key UNIQUE (candidate_id, job_id),
  CONSTRAINT applications_criteria_set_fk FOREIGN KEY (criteria_set_id, job_id)
    REFERENCES criteria_sets(id, job_id),
  CONSTRAINT applications_scored_complete CHECK (
    ai_status <> 'SCORED' OR (ai_total_score IS NOT NULL AND criteria_set_id IS NOT NULL)),
  CONSTRAINT applications_rejected_by_hr CHECK (
    status <> 'REJECTED' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL AND reject_reason_code IS NOT NULL)),
  CONSTRAINT applications_other_reason_text CHECK (
    reject_reason_code IS DISTINCT FROM 'OTHER' OR length(trim(coalesce(reject_reason_text,''))) > 0)
);
CREATE INDEX applications_job_idx    ON applications (job_id, status);
CREATE INDEX applications_status_idx ON applications (status, submitted_at);

CREATE TABLE application_scores (
  application_id   bigint NOT NULL REFERENCES applications(id),
  criterion_id     bigint NOT NULL REFERENCES criteria(id),
  score            numeric(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
  weight_snapshot  numeric(5,2) NOT NULL CHECK (weight_snapshot > 0 AND weight_snapshot <= 100),
  ai_comment       text,
  meets_mandatory  boolean,
  PRIMARY KEY (application_id, criterion_id)
);

CREATE TABLE talent_pool_consents (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  candidate_id    bigint NOT NULL REFERENCES candidates(id),
  application_id  bigint REFERENCES applications(id),
  source          consent_source NOT NULL,
  policy_ver      varchar(20) NOT NULL,
  consented_at    timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL,
  revoked_at      timestamptz,
  CONSTRAINT talent_pool_expiry CHECK (expires_at > consented_at)
);
CREATE UNIQUE INDEX talent_pool_one_active ON talent_pool_consents (candidate_id) WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------
-- 6. NHÓM PHỎNG VẤN
-- ---------------------------------------------------------------------
CREATE TABLE interviews (
  id                         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id             bigint NOT NULL REFERENCES applications(id),
  interviewer_id             bigint NOT NULL REFERENCES users(id),
  start_at                   timestamptz NOT NULL,
  end_at                     timestamptz NOT NULL,
  status                     interview_status NOT NULL DEFAULT 'SCHEDULED',
  google_event_id            varchar(200),
  meet_link                  varchar(300),
  auto_scheduled             boolean NOT NULL,
  reschedule_note            varchar(500),
  needs_manual_calendar_fix  boolean NOT NULL DEFAULT false,
  decline_reason             varchar(500),
  created_by                 bigint REFERENCES users(id),
  created_at                 timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT interviews_time_order CHECK (end_at > start_at),
  CONSTRAINT interviews_creator_required CHECK (auto_scheduled OR created_by IS NOT NULL),
  CONSTRAINT interviews_reschedule_note_required CHECK (
    status <> 'RESCHEDULE_REQUESTED' OR length(trim(coalesce(reschedule_note,''))) > 0),
  CONSTRAINT interviews_decline_only_cancelled CHECK (decline_reason IS NULL OR status = 'CANCELLED'),
  CONSTRAINT interviews_no_overlap EXCLUDE USING gist (
    interviewer_id WITH =, tstzrange(start_at, end_at) WITH &&)
    WHERE (status IN ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED'))
);
CREATE UNIQUE INDEX interviews_one_active ON interviews (application_id)
  WHERE status IN ('SCHEDULED','CONFIRMED','RESCHEDULE_REQUESTED');

CREATE TABLE interview_results (
  interview_id  bigint PRIMARY KEY REFERENCES interviews(id),
  result        pass_fail,
  no_show       boolean NOT NULL DEFAULT false,
  evaluation    jsonb,
  comment       text CHECK (comment IS NULL OR char_length(comment) <= 2000),
  entered_by    bigint NOT NULL REFERENCES users(id),
  entered_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT interview_results_noshow_xor CHECK (no_show = (result IS NULL))
);

-- ---------------------------------------------------------------------
-- 7. NHÓM THỬ VIỆC
-- ---------------------------------------------------------------------
CREATE TABLE probation_offers (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id  bigint NOT NULL UNIQUE REFERENCES applications(id),
  start_date      date NOT NULL,
  duration_days   smallint NOT NULL CHECK (duration_days BETWEEN 1 AND 180),
  location        varchar(200) NOT NULL,
  manager_id      bigint NOT NULL REFERENCES users(id),
  created_by      bigint NOT NULL REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  decline_reason  varchar(500)
);

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
CREATE INDEX response_links_expiry_idx ON response_links (expires_at)
  WHERE used_at IS NULL AND invalidated_at IS NULL;

CREATE TABLE probations (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id   bigint NOT NULL UNIQUE REFERENCES applications(id),
  trainee_id       bigint NOT NULL REFERENCES users(id),
  manager_id       bigint NOT NULL REFERENCES users(id),
  department_id    bigint NOT NULL REFERENCES departments(id),
  start_date       date NOT NULL,
  end_date         date NOT NULL,
  status           probation_status NOT NULL DEFAULT 'ONGOING',
  concluded_by     bigint REFERENCES users(id),
  concluded_at     timestamptz,
  conclusion_note  text,
  CONSTRAINT probations_dates CHECK (end_date >= start_date),
  CONSTRAINT probations_trainee_not_manager CHECK (trainee_id <> manager_id),
  CONSTRAINT probations_concluded_pair CHECK ((status = 'ONGOING') = (concluded_at IS NULL)),
  CONSTRAINT probations_concluded_by CHECK (status = 'ONGOING' OR concluded_by IS NOT NULL)
);

CREATE TABLE probation_tasks (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  probation_id  bigint NOT NULL REFERENCES probations(id),
  title         varchar(200) NOT NULL,
  description   text CHECK (description IS NULL OR char_length(description) <= 5000),
  attachments   jsonb NOT NULL DEFAULT '[]' CHECK (
                  jsonb_typeof(attachments) = 'array' AND jsonb_array_length(attachments) <= 5),
  due_at        timestamptz NOT NULL,
  created_by    bigint NOT NULL REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);
CREATE INDEX probation_tasks_probation_idx ON probation_tasks (probation_id) WHERE deleted_at IS NULL;

CREATE TABLE task_submissions (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  task_id         bigint NOT NULL UNIQUE REFERENCES probation_tasks(id),
  content_link    varchar(500),
  storage_key     varchar(100) UNIQUE,
  submitted_at    timestamptz NOT NULL DEFAULT now(),
  result          pass_fail,
  review_comment  text CHECK (review_comment IS NULL OR char_length(review_comment) <= 2000),
  reviewed_by     bigint REFERENCES users(id),
  reviewed_at     timestamptz,
  note            varchar(1000),
  revision        smallint NOT NULL DEFAULT 1 CHECK (revision >= 1),
  CONSTRAINT task_submissions_has_content CHECK (content_link IS NOT NULL OR storage_key IS NOT NULL),
  CONSTRAINT task_submissions_review_triple CHECK (
    (result IS NULL) = (reviewed_at IS NULL) AND (result IS NULL) = (reviewed_by IS NULL))
);

CREATE TABLE email_outbox (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  template_code    varchar(50) NOT NULL REFERENCES email_templates(code),
  to_email         citext NOT NULL,
  subject          varchar(255) NOT NULL,
  body             text NOT NULL,
  application_id   bigint REFERENCES applications(id),
  user_id          bigint REFERENCES users(id),
  status           email_status NOT NULL DEFAULT 'PENDING',
  attempts         smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 4),
  next_attempt_at  timestamptz NOT NULL DEFAULT now(),
  last_error       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  sent_at          timestamptz,
  CONSTRAINT email_outbox_sent_complete CHECK (status <> 'SENT' OR (sent_at IS NOT NULL AND attempts >= 1)),
  CONSTRAINT email_outbox_sent_at_only_sent CHECK (status = 'SENT' OR sent_at IS NULL),
  CONSTRAINT email_outbox_failed_has_error CHECK (status <> 'FAILED' OR (attempts >= 1 AND last_error IS NOT NULL)),
  CONSTRAINT email_outbox_subject_no_newline CHECK (subject !~ '[\r\n]'),
  CONSTRAINT email_outbox_to_email_check CHECK (to_email !~ '[\r\n]' AND position('@' in to_email) > 1)
);
CREATE INDEX ix_email_outbox_due ON email_outbox (next_attempt_at) WHERE status = 'PENDING';
CREATE INDEX ix_email_outbox_application ON email_outbox (application_id) WHERE application_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 8. HÀM VÀ TRIGGER
-- ---------------------------------------------------------------------

-- 8.1 Hạn theo ngày làm việc: hết giờ làm việc của ngày làm việc thứ n
--     tính từ ngày sau p_from (bỏ thứ Bảy, Chủ nhật, ngày lễ).
--     Giờ làm việc lấy từ system_settings 'working_hours' {"end":"17:30"}.
CREATE FUNCTION working_deadline(p_from timestamptz, p_days integer)
RETURNS timestamptz LANGUAGE plpgsql STABLE AS $$
DECLARE
  tz      text := 'Asia/Ho_Chi_Minh';
  d       date := (p_from AT TIME ZONE tz)::date;
  n       integer := 0;
  end_hm  time;
BEGIN
  IF p_days < 1 THEN RAISE EXCEPTION 'p_days phải >= 1'; END IF;
  SELECT coalesce((value_json->>'end')::time, '17:30') INTO end_hm
    FROM system_settings WHERE key = 'working_hours';
  end_hm := coalesce(end_hm, '17:30');
  WHILE n < p_days LOOP
    d := d + 1;
    IF extract(isodow FROM d) < 6
       AND NOT EXISTS (SELECT 1 FROM holidays WHERE holiday_date = d) THEN
      n := n + 1;
    END IF;
  END LOOP;
  RETURN (d + end_hm) AT TIME ZONE tz;
END $$;

-- 8.2 Nhật ký chỉ thêm, không sửa, không xóa
CREATE FUNCTION trg_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs chỉ được thêm, không được sửa hoặc xóa';
END $$;
CREATE TRIGGER audit_logs_no_change BEFORE UPDATE OR DELETE ON audit_logs
  FOR EACH ROW EXECUTE FUNCTION trg_audit_append_only();

-- 8.3 Tiêu chí bất biến sau khi lưu (sửa = tạo phiên bản mới)
CREATE FUNCTION trg_criteria_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Tiêu chí không sửa/xóa được; hãy tạo phiên bản bộ tiêu chí mới';
END $$;
CREATE TRIGGER criteria_immutable BEFORE UPDATE OR DELETE ON criteria
  FOR EACH ROW EXECUTE FUNCTION trg_criteria_immutable();

-- 8.4 Tổng trọng số của một bộ tiêu chí = 100 (kiểm tra cuối giao dịch)
CREATE FUNCTION trg_criteria_weight_sum() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s numeric;
BEGIN
  SELECT coalesce(sum(weight),0) INTO s FROM criteria WHERE criteria_set_id = NEW.criteria_set_id;
  IF s <> 100 THEN
    RAISE EXCEPTION 'Tổng trọng số bộ tiêu chí % là %, phải bằng 100', NEW.criteria_set_id, s;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER criteria_weight_sum AFTER INSERT ON criteria
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_criteria_weight_sum();

-- 8.5 Lịch sử trạng thái hồ sơ: mỗi lần đổi trạng thái ghi một dòng nhật ký.
--     Người thực hiện lấy từ biến phiên app.actor_id (NULL = hệ thống).
CREATE FUNCTION trg_application_history() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor bigint := nullif(current_setting('app.actor_id', true), '')::bigint;
BEGIN
  IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO audit_logs (actor_id, action, target_type, target_id, before_data, after_data)
    VALUES (actor, 'APPLICATION_STATUS', 'application', NEW.id,
            CASE WHEN TG_OP = 'UPDATE' THEN jsonb_build_object('status', OLD.status) END,
            jsonb_build_object('status', NEW.status));
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER applications_history AFTER INSERT OR UPDATE ON applications
  FOR EACH ROW EXECUTE FUNCTION trg_application_history();

-- 8.6 Xóa tài khoản = ẩn danh hóa; chỉ xóa tài khoản đã khóa; đã xóa thì không khôi phục
CREATE FUNCTION trg_user_delete_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'DELETED' AND NEW.status <> 'DELETED' THEN
    RAISE EXCEPTION 'Tài khoản đã xóa không khôi phục được';
  END IF;
  IF NEW.status = 'DELETED' AND OLD.status <> 'DELETED' AND OLD.status <> 'LOCKED' THEN
    RAISE EXCEPTION 'Chỉ xóa được tài khoản đang bị khóa';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER users_delete_guard BEFORE UPDATE OF status ON users
  FOR EACH ROW EXECUTE FUNCTION trg_user_delete_guard();

-- 8.7 Vai trò Nhân viên thử việc không đi cùng vai trò khác
CREATE FUNCTION trg_probation_role_exclusive() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.role = 'PROBATION' AND EXISTS (
       SELECT 1 FROM user_roles WHERE user_id = NEW.user_id AND role <> 'PROBATION') THEN
    RAISE EXCEPTION 'Nhân viên thử việc không được có vai trò khác';
  END IF;
  IF NEW.role <> 'PROBATION' AND EXISTS (
       SELECT 1 FROM user_roles WHERE user_id = NEW.user_id AND role = 'PROBATION') THEN
    RAISE EXCEPTION 'Tài khoản thử việc không được gán thêm vai trò khác';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER user_roles_probation_exclusive BEFORE INSERT OR UPDATE ON user_roles
  FOR EACH ROW EXECUTE FUNCTION trg_probation_role_exclusive();

-- 8.8 Bài nộp đã đánh giá thì khóa (không sửa nội dung, không chấm lại)
CREATE FUNCTION trg_submission_locked() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.result IS NOT NULL THEN
    RAISE EXCEPTION 'Bài nộp đã được đánh giá, không sửa được';
  END IF;
  IF NEW.result IS NULL AND (NEW.content_link IS DISTINCT FROM OLD.content_link
       OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
       OR NEW.note IS DISTINCT FROM OLD.note)
     AND NEW.revision <= OLD.revision THEN
    RAISE EXCEPTION 'Cập nhật bài nộp phải tăng revision';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER task_submissions_locked BEFORE UPDATE ON task_submissions
  FOR EACH ROW EXECUTE FUNCTION trg_submission_locked();

-- 8.9 Mẫu email phải chứa đủ biến bắt buộc {ten_bien}
CREATE FUNCTION trg_template_required_vars() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v text;
BEGIN
  FOREACH v IN ARRAY NEW.required_vars LOOP
    IF position('{' || v || '}' IN NEW.body) = 0 AND position('{' || v || '}' IN NEW.subject) = 0 THEN
      RAISE EXCEPTION 'Mẫu email % thiếu biến bắt buộc {%}', NEW.code, v;
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER email_templates_vars BEFORE INSERT OR UPDATE ON email_templates
  FOR EACH ROW EXECUTE FUNCTION trg_template_required_vars();

-- ---------------------------------------------------------------------
-- 9. GHI CHÚ BẢNG VÀ CỘT (dùng để sinh tài liệu)
-- ---------------------------------------------------------------------
COMMENT ON FUNCTION working_deadline(timestamptz, integer) IS 'Hết giờ làm việc của ngày làm việc thứ n sau thời điểm cho trước (bỏ cuối tuần, ngày lễ)';
COMMENT ON FUNCTION trg_audit_append_only() IS 'Chặn sửa/xóa nhật ký';
COMMENT ON FUNCTION trg_criteria_immutable() IS 'Chặn sửa/xóa tiêu chí đã lưu (sửa = phiên bản mới)';
COMMENT ON FUNCTION trg_criteria_weight_sum() IS 'Tổng trọng số một bộ tiêu chí = 100, kiểm tra cuối giao dịch';
COMMENT ON FUNCTION trg_application_history() IS 'Ghi nhật ký mỗi lần đổi trạng thái hồ sơ, người thực hiện lấy từ app.actor_id';
COMMENT ON FUNCTION trg_user_delete_guard() IS 'Chỉ xóa tài khoản đã khóa; đã xóa không khôi phục';
COMMENT ON FUNCTION trg_probation_role_exclusive() IS 'Vai trò Nhân viên thử việc không đi cùng vai trò khác';
COMMENT ON FUNCTION trg_submission_locked() IS 'Bài nộp đã đánh giá thì khóa; cập nhật phải tăng revision';
COMMENT ON FUNCTION trg_template_required_vars() IS 'Mẫu email phải chứa đủ biến bắt buộc';

COMMENT ON TABLE departments IS 'Phòng ban của công ty; dùng cho tin tuyển dụng, nhân viên, thử việc';
COMMENT ON COLUMN departments.name IS 'Tên phòng ban';
COMMENT ON COLUMN departments.is_active IS 'Còn hoạt động hay không';

COMMENT ON TABLE users IS 'Tài khoản nội bộ (HR, người phỏng vấn, quản lý bộ phận, nhân viên thử việc, Admin). Ứng viên không có tài khoản. Có đúng 1 tài khoản Admin do hệ thống nhân sự lớn cấp. Xóa = ẩn danh hóa';
COMMENT ON COLUMN users.account_type IS 'EMPLOYEE hoặc ADMIN; Admin là loại riêng, không có vai trò nghiệp vụ; chỉ 1 Admin';
COMMENT ON COLUMN users.full_name IS 'Họ tên';
COMMENT ON COLUMN users.email IS 'Email công ty, duy nhất (Admin nhập khi cấp tài khoản thử việc); NULL sau khi xóa';
COMMENT ON COLUMN users.department_id IS 'Phòng ban; Admin không có phòng ban';
COMMENT ON COLUMN users.status IS 'ACTIVE, LOCKED, PENDING_ADMIN (thử việc đạt, chờ Admin xử lý), DELETED';
COMMENT ON COLUMN users.password_hash IS 'Mật khẩu đã băm; NULL = chưa đặt mật khẩu lần đầu';
COMMENT ON COLUMN users.password_changed_at IS 'Lần đổi mật khẩu gần nhất';
COMMENT ON COLUMN users.token_version IS 'Tăng khi khóa, đổi mật khẩu để vô hiệu mọi phiên đăng nhập cũ';
COMMENT ON COLUMN users.change_pw_fail_count IS 'Số lần nhập sai mật khẩu cũ khi đổi mật khẩu';
COMMENT ON COLUMN users.change_pw_locked_until IS 'Khóa chức năng đổi mật khẩu đến thời điểm này';
COMMENT ON COLUMN users.login_fail_count IS 'Số lần đăng nhập sai liên tiếp';
COMMENT ON COLUMN users.login_locked_until IS 'Khóa đăng nhập tạm đến thời điểm này';
COMMENT ON COLUMN users.last_login_at IS 'Lần đăng nhập gần nhất';
COMMENT ON COLUMN users.created_by IS 'Admin tạo tài khoản';
COMMENT ON COLUMN users.created_at IS 'Thời điểm tạo';
COMMENT ON COLUMN users.deleted_at IS 'Thời điểm xóa (ẩn danh hóa)';
COMMENT ON COLUMN users.version IS 'Số phiên bản dòng, chống hai Admin sửa cùng lúc';

COMMENT ON TABLE user_roles IS 'Vai trò nghiệp vụ của tài khoản nhân viên; một người có thể nhiều vai trò, trừ PROBATION';
COMMENT ON COLUMN user_roles.user_id IS 'Tài khoản được gán vai trò';
COMMENT ON COLUMN user_roles.account_type IS 'Luôn là EMPLOYEE; cùng user_id tạo khóa ngoại chặn gán vai trò cho Admin';
COMMENT ON COLUMN user_roles.role IS 'HR, INTERVIEWER, DEPT_MANAGER, PROBATION';
COMMENT ON COLUMN user_roles.granted_by IS 'Admin gán vai trò';
COMMENT ON COLUMN user_roles.granted_at IS 'Thời điểm gán';

COMMENT ON TABLE system_settings IS 'Tham số cấu hình: thời hạn, ngưỡng, giờ làm việc; giá trị số có khoảng cho phép';
COMMENT ON COLUMN system_settings.key IS 'Mã tham số, ví dụ response_deadline_days, otp_ttl_minutes, working_hours';
COMMENT ON COLUMN system_settings.value IS 'Giá trị số hiện tại';
COMMENT ON COLUMN system_settings.value_json IS 'Giá trị dạng JSON cho tham số có cấu trúc (giờ làm việc)';
COMMENT ON COLUMN system_settings.default_value IS 'Giá trị mặc định để khôi phục';
COMMENT ON COLUMN system_settings.min_value IS 'Giá trị nhỏ nhất cho phép';
COMMENT ON COLUMN system_settings.max_value IS 'Giá trị lớn nhất cho phép';
COMMENT ON COLUMN system_settings.unit IS 'Đơn vị: phút, giờ, ngày làm việc, điểm';
COMMENT ON COLUMN system_settings.description IS 'Mô tả tham số';
COMMENT ON COLUMN system_settings.updated_by IS 'Admin sửa gần nhất';
COMMENT ON COLUMN system_settings.updated_at IS 'Thời điểm sửa gần nhất';

COMMENT ON TABLE holidays IS 'Ngày nghỉ lễ; không tính khi xếp lịch và tính hạn theo ngày làm việc';
COMMENT ON COLUMN holidays.holiday_date IS 'Ngày nghỉ';
COMMENT ON COLUMN holidays.name IS 'Tên ngày nghỉ';

COMMENT ON TABLE email_templates IS 'Mẫu email hệ thống gửi; phải giữ đủ biến bắt buộc';
COMMENT ON COLUMN email_templates.code IS 'Mã mẫu, ví dụ OTP, INVITE, RESCHEDULED, THANK_YOU';
COMMENT ON COLUMN email_templates.subject IS 'Tiêu đề email';
COMMENT ON COLUMN email_templates.body IS 'Nội dung, chứa biến dạng {ten_bien}';
COMMENT ON COLUMN email_templates.required_vars IS 'Danh sách biến bắt buộc phải có trong mẫu';
COMMENT ON COLUMN email_templates.updated_by IS 'Admin sửa gần nhất';
COMMENT ON COLUMN email_templates.updated_at IS 'Thời điểm sửa gần nhất';

COMMENT ON TABLE audit_logs IS 'Nhật ký: thao tác quản trị, xem hồ sơ, quyết định, đổi trạng thái hồ sơ, yêu cầu đổi lịch. Không sửa, không xóa';
COMMENT ON COLUMN audit_logs.occurred_at IS 'Thời điểm xảy ra';
COMMENT ON COLUMN audit_logs.actor_id IS 'Người thực hiện; NULL = hệ thống tự động hoặc ứng viên';
COMMENT ON COLUMN audit_logs.action IS 'Loại thao tác: LOCK, UNLOCK, GRANT_ROLE, REVOKE_ROLE, APPLICATION_STATUS, VIEW_APPLICATION, RESCHEDULE_REQUESTED...';
COMMENT ON COLUMN audit_logs.target_type IS 'Loại đối tượng bị tác động: user, application, interview, job, setting...';
COMMENT ON COLUMN audit_logs.target_id IS 'Mã đối tượng bị tác động';
COMMENT ON COLUMN audit_logs.reason IS 'Lý do; bắt buộc với khóa, mở khóa, xóa, gỡ vai trò, tạo Admin, đặt lại mật khẩu Admin';
COMMENT ON COLUMN audit_logs.before_data IS 'Dữ liệu trước thay đổi';
COMMENT ON COLUMN audit_logs.after_data IS 'Dữ liệu sau thay đổi';
COMMENT ON COLUMN audit_logs.ip IS 'Địa chỉ IP người thực hiện';

COMMENT ON TABLE job_postings IS 'Tin tuyển dụng; chỉ tin OPEN hiển thị cho ứng viên và dùng để gợi ý việc làm';
COMMENT ON COLUMN job_postings.title IS 'Tên vị trí';
COMMENT ON COLUMN job_postings.department_id IS 'Phòng ban tuyển';
COMMENT ON COLUMN job_postings.description IS 'Mô tả công việc (≤ 5.000 ký tự)';
COMMENT ON COLUMN job_postings.requirements IS 'Yêu cầu ứng viên (≤ 5.000 ký tự)';
COMMENT ON COLUMN job_postings.benefits IS 'Quyền lợi (≤ 3.000 ký tự)';
COMMENT ON COLUMN job_postings.embedding IS 'Vector ngữ nghĩa của tin (pgvector), tính lại khi nội dung tin thay đổi';
COMMENT ON COLUMN job_postings.headcount IS 'Số lượng cần tuyển';
COMMENT ON COLUMN job_postings.work_mode IS 'Hình thức làm việc';
COMMENT ON COLUMN job_postings.location IS 'Địa điểm làm việc';
COMMENT ON COLUMN job_postings.deadline IS 'Hạn nộp hồ sơ';
COMMENT ON COLUMN job_postings.status IS 'DRAFT (nháp), OPEN (đang mở), CLOSED (đã đóng)';
COMMENT ON COLUMN job_postings.current_criteria_set_id IS 'Phiên bản bộ tiêu chí đang áp dụng; bắt buộc khi OPEN';
COMMENT ON COLUMN job_postings.created_by IS 'HR tạo tin';
COMMENT ON COLUMN job_postings.created_at IS 'Thời điểm tạo';
COMMENT ON COLUMN job_postings.updated_at IS 'Thời điểm sửa gần nhất';
COMMENT ON COLUMN job_postings.closed_at IS 'Thời điểm đóng tin';
COMMENT ON COLUMN job_postings.version IS 'Số phiên bản dòng, chống hai HR sửa cùng lúc';

COMMENT ON TABLE criteria_sets IS 'Phiên bản bộ tiêu chí chấm CV của một tin; mỗi lần lưu tạo phiên bản mới';
COMMENT ON COLUMN criteria_sets.job_id IS 'Tin tuyển dụng';
COMMENT ON COLUMN criteria_sets.version_no IS 'Số phiên bản 1, 2, 3...';
COMMENT ON COLUMN criteria_sets.auto_invite_threshold IS 'Ngưỡng điểm tự động mời phỏng vấn, 0–100';
COMMENT ON COLUMN criteria_sets.created_by IS 'HR lưu phiên bản';
COMMENT ON COLUMN criteria_sets.created_at IS 'Thời điểm lưu';

COMMENT ON TABLE criteria IS 'Từng tiêu chí trong một bộ tiêu chí; tổng trọng số phải bằng 100; không sửa sau khi lưu';
COMMENT ON COLUMN criteria.criteria_set_id IS 'Bộ tiêu chí chứa tiêu chí này';
COMMENT ON COLUMN criteria.name IS 'Tên tiêu chí';
COMMENT ON COLUMN criteria.description IS 'Yêu cầu cụ thể (≤ 1.000 ký tự), ví dụ "Từ 2 năm kinh nghiệm Java"';
COMMENT ON COLUMN criteria.is_mandatory IS 'Tiêu chí bắt buộc: không đạt thì chuyển HR duyệt dù tổng điểm cao';
COMMENT ON COLUMN criteria.weight IS 'Trọng số (%)';

COMMENT ON TABLE job_interviewers IS 'Người phỏng vấn được chỉ định cho từng tin';
COMMENT ON COLUMN job_interviewers.job_id IS 'Tin tuyển dụng';
COMMENT ON COLUMN job_interviewers.user_id IS 'Nhân viên có vai trò INTERVIEWER';
COMMENT ON COLUMN job_interviewers.assigned_at IS 'Thời điểm chỉ định';

COMMENT ON TABLE candidates IS 'Ứng viên (không có tài khoản), định danh bằng email đã xác thực OTP';
COMMENT ON COLUMN candidates.email IS 'Email cá nhân, duy nhất';
COMMENT ON COLUMN candidates.full_name IS 'Họ tên (tối đa 100 ký tự)';
COMMENT ON COLUMN candidates.phone IS 'Số điện thoại 10 chữ số';
COMMENT ON COLUMN candidates.created_at IS 'Lần đầu gửi hồ sơ';
COMMENT ON COLUMN candidates.anonymized_at IS 'Thời điểm ẩn danh hóa khi hết thời hạn lưu hoặc rút đồng ý';

COMMENT ON TABLE cv_submissions IS 'Một lần gửi hồ sơ: file CV (PDF/DOCX có lớp chữ), đồng ý xử lý dữ liệu, dữ liệu AI trích xuất, gợi ý việc làm. Không nộp vào tin nào trong 24 giờ thì xóa';
COMMENT ON COLUMN cv_submissions.candidate_id IS 'Ứng viên gửi';
COMMENT ON COLUMN cv_submissions.cv_storage_key IS 'Tên file ngẫu nhiên trong kho lưu trữ';
COMMENT ON COLUMN cv_submissions.cv_original_name IS 'Tên file gốc';
COMMENT ON COLUMN cv_submissions.cv_mime_type IS 'Chỉ PDF hoặc DOCX';
COMMENT ON COLUMN cv_submissions.cv_size_bytes IS 'Dung lượng, tối đa 5MB';
COMMENT ON COLUMN cv_submissions.cv_sha256 IS 'Mã băm file để phát hiện trùng';
COMMENT ON COLUMN cv_submissions.cv_scan_status IS 'Kết quả quét mã độc';
COMMENT ON COLUMN cv_submissions.consent_at IS 'Thời điểm đồng ý xử lý dữ liệu (bắt buộc)';
COMMENT ON COLUMN cv_submissions.consent_policy_ver IS 'Phiên bản chính sách dữ liệu đã hiển thị';
COMMENT ON COLUMN cv_submissions.parse_status IS 'Trạng thái AI phân tích CV; FAILED = CV không đọc được, ứng viên gửi lại';
COMMENT ON COLUMN cv_submissions.parsed_data IS 'Dữ liệu AI trích xuất: học vấn, kinh nghiệm, kỹ năng...';
COMMENT ON COLUMN cv_submissions.embedding IS 'Vector ngữ nghĩa của CV, dùng lọc top-K tin phù hợp trước khi AI xếp hạng';
COMMENT ON COLUMN cv_submissions.suggestions IS 'Danh sách vị trí gợi ý: [{job_id, match_percent, reason}]';
COMMENT ON COLUMN cv_submissions.ip IS 'IP người gửi, dùng giới hạn tần suất';
COMMENT ON COLUMN cv_submissions.created_at IS 'Thời điểm gửi';
COMMENT ON COLUMN cv_submissions.expires_at IS 'Hạn xóa nếu chưa nộp vào tin nào (24 giờ)';

COMMENT ON TABLE otp_codes IS 'Mã OTP gửi qua email, dùng cho nộp hồ sơ và quên mật khẩu; mỗi mã gắn một mục đích';
COMMENT ON COLUMN otp_codes.email IS 'Email nhận mã';
COMMENT ON COLUMN otp_codes.purpose IS 'APPLY (nộp hồ sơ) hoặc RESET_PASSWORD (quên mật khẩu)';
COMMENT ON COLUMN otp_codes.code_hash IS 'Mã đã băm, không lưu mã gốc';
COMMENT ON COLUMN otp_codes.submission_id IS 'Lần gửi hồ sơ (khi APPLY)';
COMMENT ON COLUMN otp_codes.job_id IS 'Tin đang nộp (khi APPLY)';
COMMENT ON COLUMN otp_codes.user_id IS 'Tài khoản đặt lại mật khẩu (khi RESET_PASSWORD)';
COMMENT ON COLUMN otp_codes.attempts IS 'Số lần nhập sai, tối đa 5';
COMMENT ON COLUMN otp_codes.created_at IS 'Thời điểm gửi';
COMMENT ON COLUMN otp_codes.expires_at IS 'Hết hạn (mặc định 5 phút)';
COMMENT ON COLUMN otp_codes.consumed_at IS 'Thời điểm dùng thành công';
COMMENT ON COLUMN otp_codes.invalidated_at IS 'Bị hủy do gửi lại mã mới';
COMMENT ON COLUMN otp_codes.ip IS 'IP yêu cầu mã';

COMMENT ON TABLE applications IS 'Hồ sơ ứng tuyển: một ứng viên nộp vào một tin sau khi xác thực OTP; 14 trạng thái';
COMMENT ON COLUMN applications.candidate_id IS 'Ứng viên';
COMMENT ON COLUMN applications.job_id IS 'Tin tuyển dụng';
COMMENT ON COLUMN applications.submission_id IS 'Lần gửi hồ sơ chứa CV dùng để nộp';
COMMENT ON COLUMN applications.status IS 'Trạng thái hồ sơ (14 trạng thái)';
COMMENT ON COLUMN applications.submitted_at IS 'Thời điểm nộp = lúc OTP hợp lệ';
COMMENT ON COLUMN applications.criteria_set_id IS 'Phiên bản tiêu chí đã dùng để chấm';
COMMENT ON COLUMN applications.ai_status IS 'Trạng thái chấm AI: PENDING, SCORED, NEEDS_REVIEW, FAILED';
COMMENT ON COLUMN applications.ai_total_score IS 'Tổng điểm 0–100, do code tính theo trọng số';
COMMENT ON COLUMN applications.ai_failure_reason IS 'Lý do AI không chấm được';
COMMENT ON COLUMN applications.hr_note IS 'Ghi chú cho HR, ví dụ "Đạt ngưỡng – cần mời thủ công"';
COMMENT ON COLUMN applications.email_issue IS 'Lỗi gửi email gần nhất';
COMMENT ON COLUMN applications.review_due_at IS 'Hạn HR xét duyệt (5 ngày làm việc)';
COMMENT ON COLUMN applications.decided_by IS 'HR ra quyết định duyệt / từ chối';
COMMENT ON COLUMN applications.decided_at IS 'Thời điểm ra quyết định';
COMMENT ON COLUMN applications.reject_reason_code IS 'Mã lý do từ chối nội bộ';
COMMENT ON COLUMN applications.reject_reason_text IS 'Mô tả lý do khi chọn Khác (≤ 500 ký tự)';
COMMENT ON COLUMN applications.updated_at IS 'Thời điểm cập nhật gần nhất';
COMMENT ON COLUMN applications.version IS 'Số phiên bản dòng, chống hai HR xử lý cùng lúc';

COMMENT ON TABLE application_scores IS 'Điểm và nhận xét của AI theo từng tiêu chí của một hồ sơ';
COMMENT ON COLUMN application_scores.application_id IS 'Hồ sơ';
COMMENT ON COLUMN application_scores.criterion_id IS 'Tiêu chí';
COMMENT ON COLUMN application_scores.score IS 'Điểm 0–100 do AI chấm';
COMMENT ON COLUMN application_scores.weight_snapshot IS 'Trọng số lúc chấm, giúp điểm luôn tái lập được';
COMMENT ON COLUMN application_scores.ai_comment IS 'Nhận xét của AI cho tiêu chí';
COMMENT ON COLUMN application_scores.meets_mandatory IS 'Đạt tiêu chí bắt buộc hay không (NULL nếu không phải tiêu chí bắt buộc)';

COMMENT ON TABLE talent_pool_consents IS 'Đồng ý lưu hồ sơ cho đợt tuyển sau, thời hạn 12 tháng';
COMMENT ON COLUMN talent_pool_consents.candidate_id IS 'Ứng viên';
COMMENT ON COLUMN talent_pool_consents.application_id IS 'Hồ sơ liên quan (nếu đồng ý từ thư cảm ơn)';
COMMENT ON COLUMN talent_pool_consents.source IS 'Nguồn: màn hình chưa có vị trí phù hợp hoặc link trong thư cảm ơn';
COMMENT ON COLUMN talent_pool_consents.policy_ver IS 'Phiên bản nội dung đồng ý đã hiển thị';
COMMENT ON COLUMN talent_pool_consents.consented_at IS 'Thời điểm đồng ý';
COMMENT ON COLUMN talent_pool_consents.expires_at IS 'Hết hạn lưu';
COMMENT ON COLUMN talent_pool_consents.revoked_at IS 'Thời điểm ứng viên rút lại đồng ý';

COMMENT ON TABLE interviews IS 'Buổi phỏng vấn: lịch, link Meet, ghi chú đổi lịch. Một người phỏng vấn không có 2 buổi trùng giờ; một hồ sơ chỉ có 1 buổi đang hiệu lực';
COMMENT ON COLUMN interviews.application_id IS 'Hồ sơ được phỏng vấn';
COMMENT ON COLUMN interviews.interviewer_id IS 'Người phỏng vấn';
COMMENT ON COLUMN interviews.start_at IS 'Giờ bắt đầu';
COMMENT ON COLUMN interviews.end_at IS 'Giờ kết thúc';
COMMENT ON COLUMN interviews.status IS 'SCHEDULED, CONFIRMED, RESCHEDULE_REQUESTED, CANCELLED, COMPLETED';
COMMENT ON COLUMN interviews.google_event_id IS 'Mã sự kiện trên Google Calendar';
COMMENT ON COLUMN interviews.meet_link IS 'Link Google Meet';
COMMENT ON COLUMN interviews.auto_scheduled IS 'TRUE = hệ thống tự mời; FALSE = HR mời';
COMMENT ON COLUMN interviews.reschedule_note IS 'Ghi chú đổi lịch của ứng viên (≤ 500 ký tự); bắt buộc khi RESCHEDULE_REQUESTED, xóa khi HR xếp lại. Số lần yêu cầu (tối đa 2) đếm trong audit_logs';
COMMENT ON COLUMN interviews.needs_manual_calendar_fix IS 'Google lỗi, HR cần cập nhật lịch thủ công';
COMMENT ON COLUMN interviews.decline_reason IS 'Lý do ứng viên từ chối phỏng vấn (≤ 500 ký tự); chỉ có khi buổi đã hủy';
COMMENT ON COLUMN interviews.created_by IS 'HR tạo lịch; NULL khi tự động';
COMMENT ON COLUMN interviews.created_at IS 'Thời điểm tạo';

COMMENT ON TABLE interview_results IS 'Kết quả và phiếu đánh giá của buổi phỏng vấn; không sửa sau khi lưu';
COMMENT ON COLUMN interview_results.interview_id IS 'Buổi phỏng vấn';
COMMENT ON COLUMN interview_results.result IS 'PASS / FAIL; NULL khi ứng viên vắng mặt';
COMMENT ON COLUMN interview_results.no_show IS 'Ứng viên vắng mặt';
COMMENT ON COLUMN interview_results.evaluation IS 'Phiếu đánh giá mức 1–5 theo tiêu chí (JSON)';
COMMENT ON COLUMN interview_results.comment IS 'Nhận xét chung (≤ 2.000 ký tự)';
COMMENT ON COLUMN interview_results.entered_by IS 'Người phỏng vấn nhập kết quả';
COMMENT ON COLUMN interview_results.entered_at IS 'Thời điểm nhập';

COMMENT ON TABLE probation_offers IS 'Lời mời thử việc gửi ứng viên đạt phỏng vấn';
COMMENT ON COLUMN probation_offers.application_id IS 'Hồ sơ đạt phỏng vấn';
COMMENT ON COLUMN probation_offers.start_date IS 'Ngày bắt đầu thử việc';
COMMENT ON COLUMN probation_offers.duration_days IS 'Thời gian thử việc (1–180 ngày)';
COMMENT ON COLUMN probation_offers.location IS 'Địa điểm làm việc';
COMMENT ON COLUMN probation_offers.manager_id IS 'Quản lý bộ phận phụ trách (cùng phòng ban với tin)';
COMMENT ON COLUMN probation_offers.created_by IS 'Người phỏng vấn / HR tạo lời mời';
COMMENT ON COLUMN probation_offers.created_at IS 'Thời điểm tạo';
COMMENT ON COLUMN probation_offers.decline_reason IS 'Lý do ứng viên từ chối (≤ 500 ký tự)';

COMMENT ON TABLE response_links IS 'Link phản hồi gửi ứng viên qua email: dùng 1 lần, hạn 2 ngày làm việc, quá hạn mặc định từ chối';
COMMENT ON COLUMN response_links.token_hash IS 'Mã băm của chuỗi ngẫu nhiên trong link';
COMMENT ON COLUMN response_links.purpose IS 'Xác nhận lịch phỏng vấn, lời mời thử việc, đồng ý lưu hồ sơ';
COMMENT ON COLUMN response_links.application_id IS 'Hồ sơ liên quan';
COMMENT ON COLUMN response_links.interview_id IS 'Buổi phỏng vấn (khi xác nhận lịch)';
COMMENT ON COLUMN response_links.offer_id IS 'Lời mời thử việc (khi phản hồi lời mời)';
COMMENT ON COLUMN response_links.created_at IS 'Thời điểm gửi';
COMMENT ON COLUMN response_links.expires_at IS 'Hạn phản hồi: hết giờ làm việc ngày làm việc thứ 2';
COMMENT ON COLUMN response_links.used_at IS 'Thời điểm ứng viên phản hồi hoặc hệ thống xử lý quá hạn';
COMMENT ON COLUMN response_links.outcome IS 'ACCEPTED, DECLINED, RESCHEDULE_REQUESTED (chỉ với lịch phỏng vấn), EXPIRED';
COMMENT ON COLUMN response_links.invalidated_at IS 'Bị vô hiệu do HR xếp lại hoặc hủy lịch; không được dùng và không bị xử lý quá hạn';

COMMENT ON TABLE probations IS 'Đợt thử việc, tạo khi Admin cấp tài khoản thử việc; kết luận Đạt / Không đạt';
COMMENT ON COLUMN probations.application_id IS 'Hồ sơ gốc';
COMMENT ON COLUMN probations.trainee_id IS 'Tài khoản nhân viên thử việc';
COMMENT ON COLUMN probations.manager_id IS 'Quản lý bộ phận phụ trách';
COMMENT ON COLUMN probations.department_id IS 'Phòng ban';
COMMENT ON COLUMN probations.start_date IS 'Ngày bắt đầu';
COMMENT ON COLUMN probations.end_date IS 'Ngày kết thúc';
COMMENT ON COLUMN probations.status IS 'ONGOING, PASSED, FAILED';
COMMENT ON COLUMN probations.concluded_by IS 'Quản lý kết luận';
COMMENT ON COLUMN probations.concluded_at IS 'Thời điểm kết luận';
COMMENT ON COLUMN probations.conclusion_note IS 'Nhận xét kết luận';

COMMENT ON TABLE probation_tasks IS 'Task thử việc do quản lý bộ phận giao';
COMMENT ON COLUMN probation_tasks.probation_id IS 'Đợt thử việc';
COMMENT ON COLUMN probation_tasks.title IS 'Tên task';
COMMENT ON COLUMN probation_tasks.description IS 'Mô tả yêu cầu (≤ 5.000 ký tự)';
COMMENT ON COLUMN probation_tasks.attachments IS 'Tài liệu đính kèm (≤ 5 tệp): [{storage_key, file_name, size_bytes}]';
COMMENT ON COLUMN probation_tasks.due_at IS 'Hạn nộp';
COMMENT ON COLUMN probation_tasks.created_by IS 'Quản lý giao task';
COMMENT ON COLUMN probation_tasks.created_at IS 'Thời điểm giao';
COMMENT ON COLUMN probation_tasks.deleted_at IS 'Thời điểm xóa task (xóa mềm)';

COMMENT ON TABLE task_submissions IS 'Bài nộp của task (mỗi task 1 bài, sửa được khi chưa đánh giá); đánh giá Đạt / Không đạt';
COMMENT ON COLUMN task_submissions.task_id IS 'Task';
COMMENT ON COLUMN task_submissions.content_link IS 'Link bài làm';
COMMENT ON COLUMN task_submissions.storage_key IS 'File bài làm trong kho lưu trữ';
COMMENT ON COLUMN task_submissions.submitted_at IS 'Thời điểm nộp (lần nộp hoặc cập nhật gần nhất)';
COMMENT ON COLUMN task_submissions.result IS 'PASS / FAIL; NULL = chưa đánh giá';
COMMENT ON COLUMN task_submissions.review_comment IS 'Nhận xét của quản lý (≤ 2.000 ký tự)';
COMMENT ON COLUMN task_submissions.reviewed_by IS 'Quản lý đánh giá';
COMMENT ON COLUMN task_submissions.reviewed_at IS 'Thời điểm đánh giá';
COMMENT ON COLUMN task_submissions.note IS 'Ghi chú của nhân viên cho quản lý (≤ 1.000 ký tự)';
COMMENT ON COLUMN task_submissions.revision IS 'Lần nộp: 1 = lần đầu, > 1 = đã cập nhật; chống ghi đè khi quản lý đang đánh giá';

COMMENT ON TABLE email_outbox IS 'Hộp thư đi: email ghi cùng giao dịch với thao tác nghiệp vụ; tác vụ nền gửi, thử lại tối đa 3 lần cách 5 phút';
COMMENT ON COLUMN email_outbox.template_code IS 'Mẫu email đã dùng để soạn';
COMMENT ON COLUMN email_outbox.to_email IS 'Người nhận; không chứa ký tự xuống dòng';
COMMENT ON COLUMN email_outbox.subject IS 'Tiêu đề đã điền biến; không chứa ký tự xuống dòng';
COMMENT ON COLUMN email_outbox.body IS 'Nội dung đã điền biến (giá trị đã escape; mã OTP/token được che)';
COMMENT ON COLUMN email_outbox.application_id IS 'Hồ sơ liên quan (để gắn cờ lỗi email khi gửi thất bại)';
COMMENT ON COLUMN email_outbox.user_id IS 'Tài khoản nhân viên liên quan';
COMMENT ON COLUMN email_outbox.status IS 'PENDING chờ gửi, SENT đã gửi, FAILED hết lượt thử hoặc địa chỉ không tồn tại';
COMMENT ON COLUMN email_outbox.attempts IS 'Số lần đã gửi, gồm lần đầu; tối đa 4';
COMMENT ON COLUMN email_outbox.next_attempt_at IS 'Thời điểm được gửi hoặc thử lại tiếp theo';
COMMENT ON COLUMN email_outbox.last_error IS 'Lỗi của lần gửi gần nhất';
COMMENT ON COLUMN email_outbox.created_at IS 'Thời điểm tạo';
COMMENT ON COLUMN email_outbox.sent_at IS 'Thời điểm gửi thành công';

-- ---------------------------------------------------------------------
-- 10. DỮ LIỆU CẤU HÌNH BAN ĐẦU
-- ---------------------------------------------------------------------
INSERT INTO system_settings (key, value, value_json, default_value, min_value, max_value, unit, description) VALUES
 ('working_hours', NULL, '{"start":"08:00","end":"17:30"}', NULL, NULL, NULL, NULL, 'Giờ làm việc thứ Hai – thứ Sáu'),
 ('response_deadline_days', 2, NULL, 2, 1, 5, 'ngày làm việc', 'Hạn phản hồi của ứng viên'),
 ('hr_review_days', 5, NULL, 5, 1, 10, 'ngày làm việc', 'Hạn HR xét duyệt hồ sơ'),
 ('reschedule_handle_days', 1, NULL, 1, 1, 3, 'ngày làm việc', 'Hạn HR xếp lại lịch khi ứng viên yêu cầu đổi'),
 ('max_reschedule_requests', 2, NULL, 2, 0, 5, 'lần', 'Số lần tối đa ứng viên được yêu cầu đổi lịch'),
 ('otp_ttl_minutes', 5, NULL, 5, 1, 15, 'phút', 'Thời gian hiệu lực mã OTP'),
 ('talent_pool_months', 12, NULL, 12, 1, 24, 'tháng', 'Thời hạn lưu hồ sơ khi ứng viên đồng ý'),
 ('cv_draft_ttl_hours', 24, NULL, 24, 1, 72, 'giờ', 'Hạn xóa hồ sơ tạm chưa nộp vào tin nào');

COMMIT;
