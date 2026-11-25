# 02. Cơ sở dữ liệu và thiết kế

> Sinh tự động từ CSDL đang chạy (schema_25.sql bản 16/11/2026, PostgreSQL 16 + pgvector): **25 bảng**, 16 enum; kiểm thử **130/130 đạt** (test_25.sql). Đã áp đợt rút gọn 03/11 (mục 4.8 file 00), bỏ trích dẫn bằng chứng 04/11 và bỏ quy tắc luôn ≥ 2 Admin 16/11. Không sửa tay; muốn đổi schema thì sửa schema_25.sql, chạy lại test_25.sql rồi sinh lại tài liệu này (gen_ctx02.sh).

## Kiểu enum

| Enum | Giá trị |
|---|---|
| account_status | ACTIVE, LOCKED, PENDING_ADMIN, DELETED |
| account_type | EMPLOYEE, ADMIN |
| ai_score_status | PENDING, SCORED, NEEDS_REVIEW, FAILED |
| application_status | SCORING, PENDING_HR_REVIEW, INTERVIEW_INVITED, INTERVIEW_CONFIRMED, INTERVIEW_DECLINED, AWAITING_INTERVIEW_RESULT, INTERVIEW_PASSED, INTERVIEW_FAILED, REJECTED, AWAITING_ACCOUNT, ON_PROBATION, PROBATION_DECLINED, PROBATION_PASSED, PROBATION_FAILED |
| business_role | HR, INTERVIEWER, DEPT_MANAGER, PROBATION |
| consent_source | NO_MATCH_SCREEN, THANK_YOU_LINK |
| email_status | PENDING, SENT, FAILED |
| interview_status | SCHEDULED, CONFIRMED, RESCHEDULE_REQUESTED, CANCELLED, COMPLETED |
| job_status | DRAFT, OPEN, CLOSED |
| link_outcome | ACCEPTED, DECLINED, RESCHEDULE_REQUESTED, EXPIRED |
| link_purpose | CONFIRM_INTERVIEW, PROBATION_OFFER, TALENT_POOL_CONSENT |
| otp_purpose | APPLY, RESET_PASSWORD |
| parse_status | PENDING, PARSED, PARTIAL, FAILED |
| pass_fail | PASS, FAIL |
| probation_status | ONGOING, PASSED, FAILED |
| scan_status | PENDING, CLEAN, INFECTED |

## Hàm trong CSDL (không kể hàm của extension)

- `trg_application_history`: Ghi nhật ký mỗi lần đổi trạng thái hồ sơ, người thực hiện lấy từ app.actor_id
- `trg_audit_append_only`: Chặn sửa/xóa nhật ký
- `trg_criteria_immutable`: Chặn sửa/xóa tiêu chí đã lưu (sửa = phiên bản mới)
- `trg_criteria_weight_sum`: Tổng trọng số một bộ tiêu chí = 100, kiểm tra cuối giao dịch
- `trg_probation_role_exclusive`: Vai trò Nhân viên thử việc không đi cùng vai trò khác
- `trg_submission_locked`: Bài nộp đã đánh giá thì khóa; cập nhật phải tăng revision
- `trg_template_required_vars`: Mẫu email phải chứa đủ biến bắt buộc
- `trg_user_delete_guard`: Chỉ xóa tài khoản đã khóa; đã xóa không khôi phục
- `working_deadline`: Hết giờ làm việc của ngày làm việc thứ n sau thời điểm cho trước (bỏ cuối tuần, ngày lễ)

## Bảng `departments`

Phòng ban của công ty; dùng cho tin tuyển dụng, nhân viên, thử việc

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| name | character varying(150) | NOT NULL | Tên phòng ban |
| is_active | boolean | NOT NULL | Còn hoạt động hay không |

Ràng buộc:

- `departments_pkey` (PK): `PRIMARY KEY (id)`
- `departments_name_key` (UNIQUE): `UNIQUE (name)`

## Bảng `users`

Tài khoản nội bộ (HR, người phỏng vấn, quản lý bộ phận, nhân viên thử việc, Admin). Ứng viên không có tài khoản. Có đúng 1 tài khoản Admin do hệ thống nhân sự lớn cấp. Xóa = ẩn danh hóa

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| account_type | account_type | NOT NULL | EMPLOYEE hoặc ADMIN; Admin là loại riêng, không có vai trò nghiệp vụ; chỉ 1 Admin |
| full_name | character varying(100) | NOT NULL | Họ tên |
| email | citext | NULL | Email công ty, duy nhất (Admin nhập khi cấp tài khoản thử việc); NULL sau khi xóa |
| department_id | bigint | NULL | Phòng ban; Admin không có phòng ban |
| status | account_status | NOT NULL | ACTIVE, LOCKED, PENDING_ADMIN (thử việc đạt, chờ Admin xử lý), DELETED |
| password_hash | text | NULL | Mật khẩu đã băm; NULL = chưa đặt mật khẩu lần đầu |
| password_changed_at | timestamp with time zone | NULL | Lần đổi mật khẩu gần nhất |
| token_version | integer | NOT NULL | Tăng khi khóa, đổi mật khẩu để vô hiệu mọi phiên đăng nhập cũ |
| change_pw_fail_count | smallint | NOT NULL | Số lần nhập sai mật khẩu cũ khi đổi mật khẩu |
| change_pw_locked_until | timestamp with time zone | NULL | Khóa chức năng đổi mật khẩu đến thời điểm này |
| login_fail_count | smallint | NOT NULL | Số lần đăng nhập sai liên tiếp |
| login_locked_until | timestamp with time zone | NULL | Khóa đăng nhập tạm đến thời điểm này |
| last_login_at | timestamp with time zone | NULL | Lần đăng nhập gần nhất |
| created_by | bigint | NULL | Admin tạo tài khoản |
| created_at | timestamp with time zone | NOT NULL | Thời điểm tạo |
| deleted_at | timestamp with time zone | NULL | Thời điểm xóa (ẩn danh hóa) |
| version | integer | NOT NULL | Số phiên bản dòng, chống hai Admin sửa cùng lúc |

Ràng buộc:

- `users_active_has_email` (CHECK): `CHECK (((status = 'DELETED'::account_status) OR (email IS NOT NULL)))`
- `users_admin_no_department` (CHECK): `CHECK (((account_type = 'EMPLOYEE'::account_type) OR (department_id IS NULL)))`
- `users_deleted_anonymized` (CHECK): `CHECK ((((status = 'DELETED'::account_status) = (deleted_at IS NOT NULL)) AND ((status <> 'DELETED'::account_status) OR ((email IS NULL) AND (password_hash IS NULL)))))`
- `users_email_format` (CHECK): `CHECK (((email IS NULL) OR (email ~* '^[^@\s]+@[^@\s]+$'::citext)))`
- `users_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `users_department_id_fkey` (FK): `FOREIGN KEY (department_id) REFERENCES departments(id)`
- `users_pkey` (PK): `PRIMARY KEY (id)`
- `users_id_account_type_key` (UNIQUE): `UNIQUE (id, account_type)`

Index:

- `CREATE UNIQUE INDEX users_email_uq ON public.users USING btree (email) WHERE (email IS NOT NULL)`
- `CREATE UNIQUE INDEX users_one_admin ON public.users USING btree (account_type) WHERE ((account_type = 'ADMIN'::account_type) AND (status <> 'DELETED'::account_status))`

Trigger:

- `users_delete_guard` (BEFORE UPDATE) → trg_user_delete_guard

## Bảng `user_roles`

Vai trò nghiệp vụ của tài khoản nhân viên; một người có thể nhiều vai trò, trừ PROBATION

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| user_id | bigint | NOT NULL | Tài khoản được gán vai trò |
| account_type | account_type | NOT NULL | Luôn là EMPLOYEE; cùng user_id tạo khóa ngoại chặn gán vai trò cho Admin |
| role | business_role | NOT NULL | HR, INTERVIEWER, DEPT_MANAGER, PROBATION |
| granted_by | bigint | NULL | Admin gán vai trò |
| granted_at | timestamp with time zone | NOT NULL | Thời điểm gán |

Ràng buộc:

- `user_roles_account_type_check` (CHECK): `CHECK ((account_type = 'EMPLOYEE'::account_type))`
- `user_roles_granted_by_fkey` (FK): `FOREIGN KEY (granted_by) REFERENCES users(id)`
- `user_roles_user_id_account_type_fkey` (FK): `FOREIGN KEY (user_id, account_type) REFERENCES users(id, account_type)`
- `user_roles_pkey` (PK): `PRIMARY KEY (user_id, role)`

Trigger:

- `user_roles_probation_exclusive` (BEFORE INSERT,UPDATE) → trg_probation_role_exclusive

## Bảng `system_settings`

Tham số cấu hình: thời hạn, ngưỡng, giờ làm việc; giá trị số có khoảng cho phép

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| key | character varying(80) | NOT NULL | Mã tham số, ví dụ response_deadline_days, otp_ttl_minutes, working_hours |
| value | numeric | NULL | Giá trị số hiện tại |
| value_json | jsonb | NULL | Giá trị dạng JSON cho tham số có cấu trúc (giờ làm việc) |
| default_value | numeric | NULL | Giá trị mặc định để khôi phục |
| min_value | numeric | NULL | Giá trị nhỏ nhất cho phép |
| max_value | numeric | NULL | Giá trị lớn nhất cho phép |
| unit | character varying(30) | NULL | Đơn vị: phút, giờ, ngày làm việc, điểm |
| description | text | NULL | Mô tả tham số |
| updated_by | bigint | NULL | Admin sửa gần nhất |
| updated_at | timestamp with time zone | NOT NULL | Thời điểm sửa gần nhất |

Ràng buộc:

- `system_settings_in_range` (CHECK): `CHECK (((value IS NULL) OR ((min_value IS NOT NULL) AND (max_value IS NOT NULL) AND ((value >= min_value) AND (value <= max_value)) AND ((default_value >= min_value) AND (default_value <= max_value)))))`
- `system_settings_one_value` (CHECK): `CHECK (((value IS NULL) <> (value_json IS NULL)))`
- `system_settings_updated_by_fkey` (FK): `FOREIGN KEY (updated_by) REFERENCES users(id)`
- `system_settings_pkey` (PK): `PRIMARY KEY (key)`

## Bảng `holidays`

Ngày nghỉ lễ; không tính khi xếp lịch và tính hạn theo ngày làm việc

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| holiday_date | date | NOT NULL | Ngày nghỉ |
| name | character varying(150) | NOT NULL | Tên ngày nghỉ |

Ràng buộc:

- `holidays_pkey` (PK): `PRIMARY KEY (holiday_date)`

## Bảng `email_templates`

Mẫu email hệ thống gửi; phải giữ đủ biến bắt buộc

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| code | character varying(50) | NOT NULL | Mã mẫu, ví dụ OTP, INVITE, RESCHEDULED, THANK_YOU |
| subject | character varying(255) | NOT NULL | Tiêu đề email |
| body | text | NOT NULL | Nội dung, chứa biến dạng {ten_bien} |
| required_vars | text[] | NOT NULL | Danh sách biến bắt buộc phải có trong mẫu |
| updated_by | bigint | NULL | Admin sửa gần nhất |
| updated_at | timestamp with time zone | NOT NULL | Thời điểm sửa gần nhất |

Ràng buộc:

- `email_templates_updated_by_fkey` (FK): `FOREIGN KEY (updated_by) REFERENCES users(id)`
- `email_templates_pkey` (PK): `PRIMARY KEY (code)`

Trigger:

- `email_templates_vars` (BEFORE INSERT,UPDATE) → trg_template_required_vars

## Bảng `email_outbox`

Hộp thư đi: email ghi cùng giao dịch với thao tác nghiệp vụ; tác vụ nền gửi, thử lại tối đa 3 lần cách 5 phút

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| template_code | character varying(50) | NOT NULL | Mẫu email đã dùng để soạn |
| to_email | citext | NOT NULL | Người nhận; không chứa ký tự xuống dòng |
| subject | character varying(255) | NOT NULL | Tiêu đề đã điền biến; không chứa ký tự xuống dòng |
| body | text | NOT NULL | Nội dung đã điền biến (giá trị đã escape; mã OTP/token được che) |
| application_id | bigint | NULL | Hồ sơ liên quan (để gắn cờ lỗi email khi gửi thất bại) |
| user_id | bigint | NULL | Tài khoản nhân viên liên quan |
| status | email_status | NOT NULL | PENDING chờ gửi, SENT đã gửi, FAILED hết lượt thử hoặc địa chỉ không tồn tại |
| attempts | smallint | NOT NULL | Số lần đã gửi, gồm lần đầu; tối đa 4 |
| next_attempt_at | timestamp with time zone | NOT NULL | Thời điểm được gửi hoặc thử lại tiếp theo |
| last_error | text | NULL | Lỗi của lần gửi gần nhất |
| created_at | timestamp with time zone | NOT NULL | Thời điểm tạo |
| sent_at | timestamp with time zone | NULL | Thời điểm gửi thành công |

Ràng buộc:

- `email_outbox_attempts_check` (CHECK): `CHECK (((attempts >= 0) AND (attempts <= 4)))`
- `email_outbox_failed_has_error` (CHECK): `CHECK (((status <> 'FAILED'::email_status) OR ((attempts >= 1) AND (last_error IS NOT NULL))))`
- `email_outbox_sent_at_only_sent` (CHECK): `CHECK (((status = 'SENT'::email_status) OR (sent_at IS NULL)))`
- `email_outbox_sent_complete` (CHECK): `CHECK (((status <> 'SENT'::email_status) OR ((sent_at IS NOT NULL) AND (attempts >= 1))))`
- `email_outbox_subject_no_newline` (CHECK): `CHECK (((subject)::text !~ '[\r\n]'::text))`
- `email_outbox_to_email_check` (CHECK): `CHECK (((to_email !~ '[\r\n]'::citext) AND (POSITION(('@'::text) IN (to_email)) > 1)))`
- `email_outbox_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `email_outbox_template_code_fkey` (FK): `FOREIGN KEY (template_code) REFERENCES email_templates(code)`
- `email_outbox_user_id_fkey` (FK): `FOREIGN KEY (user_id) REFERENCES users(id)`
- `email_outbox_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE INDEX ix_email_outbox_application ON public.email_outbox USING btree (application_id) WHERE (application_id IS NOT NULL)`
- `CREATE INDEX ix_email_outbox_due ON public.email_outbox USING btree (next_attempt_at) WHERE (status = 'PENDING'::email_status)`

## Bảng `audit_logs`

Nhật ký: thao tác quản trị, xem hồ sơ, quyết định, đổi trạng thái hồ sơ, yêu cầu đổi lịch. Không sửa, không xóa

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| occurred_at | timestamp with time zone | NOT NULL | Thời điểm xảy ra |
| actor_id | bigint | NULL | Người thực hiện; NULL = hệ thống tự động hoặc ứng viên |
| action | character varying(60) | NOT NULL | Loại thao tác: LOCK, UNLOCK, GRANT_ROLE, REVOKE_ROLE, APPLICATION_STATUS, VIEW_APPLICATION, RESCHEDULE_REQUESTED... |
| target_type | character varying(40) | NOT NULL | Loại đối tượng bị tác động: user, application, interview, job, setting... |
| target_id | bigint | NULL | Mã đối tượng bị tác động |
| reason | text | NULL | Lý do; bắt buộc với khóa, mở khóa, xóa, gỡ vai trò, tạo Admin, đặt lại mật khẩu Admin |
| before_data | jsonb | NULL | Dữ liệu trước thay đổi |
| after_data | jsonb | NULL | Dữ liệu sau thay đổi |
| ip | inet | NULL | Địa chỉ IP người thực hiện |

Ràng buộc:

- `audit_logs_reason_required` (CHECK): `CHECK ((((action)::text <> ALL ((ARRAY['LOCK'::character varying, 'UNLOCK'::character varying, 'DELETE_ACCOUNT'::character varying, 'REVOKE_ROLE'::character varying])::text[])) OR (length(TRIM(BOTH FROM COALESCE(reason, ''::text))) > 0)))`
- `audit_logs_actor_id_fkey` (FK): `FOREIGN KEY (actor_id) REFERENCES users(id)`
- `audit_logs_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE INDEX audit_logs_target_idx ON public.audit_logs USING btree (target_type, target_id, occurred_at)`
- `CREATE INDEX audit_logs_time_idx ON public.audit_logs USING btree (occurred_at)`

Trigger:

- `audit_logs_no_change` (BEFORE DELETE,UPDATE) → trg_audit_append_only

## Bảng `job_postings`

Tin tuyển dụng; chỉ tin OPEN hiển thị cho ứng viên và dùng để gợi ý việc làm

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| title | character varying(200) | NOT NULL | Tên vị trí |
| department_id | bigint | NOT NULL | Phòng ban tuyển |
| description | text | NULL | Mô tả công việc (≤ 5.000 ký tự) |
| requirements | text | NULL | Yêu cầu ứng viên (≤ 5.000 ký tự) |
| benefits | text | NULL | Quyền lợi (≤ 3.000 ký tự) |
| embedding | vector(1536) | NULL | Vector ngữ nghĩa của tin (pgvector), tính lại khi nội dung tin thay đổi |
| headcount | integer | NULL | Số lượng cần tuyển |
| work_mode | character varying(50) | NULL | Hình thức làm việc |
| location | character varying(200) | NULL | Địa điểm làm việc |
| deadline | date | NULL | Hạn nộp hồ sơ |
| status | job_status | NOT NULL | DRAFT (nháp), OPEN (đang mở), CLOSED (đã đóng) |
| current_criteria_set_id | bigint | NULL | Phiên bản bộ tiêu chí đang áp dụng; bắt buộc khi OPEN |
| created_by | bigint | NOT NULL | HR tạo tin |
| created_at | timestamp with time zone | NOT NULL | Thời điểm tạo |
| updated_at | timestamp with time zone | NOT NULL | Thời điểm sửa gần nhất |
| closed_at | timestamp with time zone | NULL | Thời điểm đóng tin |
| version | integer | NOT NULL | Số phiên bản dòng, chống hai HR sửa cùng lúc |

Ràng buộc:

- `job_closed_at` (CHECK): `CHECK (((status = 'CLOSED'::job_status) = (closed_at IS NOT NULL)))`
- `job_open_complete` (CHECK): `CHECK (((status <> 'OPEN'::job_status) OR ((description IS NOT NULL) AND (requirements IS NOT NULL) AND (headcount IS NOT NULL) AND (deadline IS NOT NULL) AND (current_criteria_set_id IS NOT NULL))))`
- `job_postings_benefits_check` (CHECK): `CHECK ((length(benefits) <= 3000))`
- `job_postings_description_check` (CHECK): `CHECK ((length(description) <= 5000))`
- `job_postings_headcount_check` (CHECK): `CHECK ((headcount > 0))`
- `job_postings_requirements_check` (CHECK): `CHECK ((length(requirements) <= 5000))`
- `job_current_criteria_fk` (FK): `FOREIGN KEY (current_criteria_set_id, id) REFERENCES criteria_sets(id, job_id) DEFERRABLE INITIALLY DEFERRED`
- `job_postings_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `job_postings_department_id_fkey` (FK): `FOREIGN KEY (department_id) REFERENCES departments(id)`
- `job_postings_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE INDEX ix_job_postings_embedding ON public.job_postings USING hnsw (embedding vector_cosine_ops) WHERE (status = 'OPEN'::job_status)`

## Bảng `criteria_sets`

Phiên bản bộ tiêu chí chấm CV của một tin; mỗi lần lưu tạo phiên bản mới

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| job_id | bigint | NOT NULL | Tin tuyển dụng |
| version_no | integer | NOT NULL | Số phiên bản 1, 2, 3... |
| auto_invite_threshold | numeric(5,2) | NOT NULL | Ngưỡng điểm tự động mời phỏng vấn, 0–100 |
| created_by | bigint | NOT NULL | HR lưu phiên bản |
| created_at | timestamp with time zone | NOT NULL | Thời điểm lưu |

Ràng buộc:

- `criteria_sets_auto_invite_threshold_check` (CHECK): `CHECK (((auto_invite_threshold >= (0)::numeric) AND (auto_invite_threshold <= (100)::numeric)))`
- `criteria_sets_version_no_check` (CHECK): `CHECK ((version_no >= 1))`
- `criteria_sets_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `criteria_sets_job_id_fkey` (FK): `FOREIGN KEY (job_id) REFERENCES job_postings(id)`
- `criteria_sets_pkey` (PK): `PRIMARY KEY (id)`
- `criteria_sets_id_job_id_key` (UNIQUE): `UNIQUE (id, job_id)`
- `criteria_sets_job_id_version_no_key` (UNIQUE): `UNIQUE (job_id, version_no)`

## Bảng `criteria`

Từng tiêu chí trong một bộ tiêu chí; tổng trọng số phải bằng 100; không sửa sau khi lưu

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| criteria_set_id | bigint | NOT NULL | Bộ tiêu chí chứa tiêu chí này |
| name | character varying(150) | NOT NULL | Tên tiêu chí |
| description | text | NOT NULL | Yêu cầu cụ thể (≤ 1.000 ký tự), ví dụ "Từ 2 năm kinh nghiệm Java" |
| is_mandatory | boolean | NOT NULL | Tiêu chí bắt buộc: không đạt thì chuyển HR duyệt dù tổng điểm cao |
| weight | numeric(5,2) | NOT NULL | Trọng số (%) |

Ràng buộc:

- `criteria_description_check` (CHECK): `CHECK ((char_length(description) <= 1000))`
- `criteria_weight_check` (CHECK): `CHECK (((weight > (0)::numeric) AND (weight <= (100)::numeric)))`
- `criteria_criteria_set_id_fkey` (FK): `FOREIGN KEY (criteria_set_id) REFERENCES criteria_sets(id)`
- `criteria_pkey` (PK): `PRIMARY KEY (id)`
- `criteria_criteria_set_id_name_key` (UNIQUE): `UNIQUE (criteria_set_id, name)`
- `criteria_weight_sum` (TRIGGER): `TRIGGER DEFERRABLE INITIALLY DEFERRED`

Trigger:

- `criteria_immutable` (BEFORE DELETE,UPDATE) → trg_criteria_immutable
- `criteria_weight_sum` (AFTER INSERT) → trg_criteria_weight_sum

## Bảng `job_interviewers`

Người phỏng vấn được chỉ định cho từng tin

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| job_id | bigint | NOT NULL | Tin tuyển dụng |
| user_id | bigint | NOT NULL | Nhân viên có vai trò INTERVIEWER |
| assigned_at | timestamp with time zone | NOT NULL | Thời điểm chỉ định |

Ràng buộc:

- `job_interviewers_job_id_fkey` (FK): `FOREIGN KEY (job_id) REFERENCES job_postings(id)`
- `job_interviewers_user_id_fkey` (FK): `FOREIGN KEY (user_id) REFERENCES users(id)`
- `job_interviewers_pkey` (PK): `PRIMARY KEY (job_id, user_id)`

## Bảng `candidates`

Ứng viên (không có tài khoản), định danh bằng email đã xác thực OTP

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| email | citext | NOT NULL | Email cá nhân, duy nhất |
| full_name | character varying(100) | NOT NULL | Họ tên (tối đa 100 ký tự) |
| phone | character(10) | NOT NULL | Số điện thoại 10 chữ số |
| created_at | timestamp with time zone | NOT NULL | Lần đầu gửi hồ sơ |
| anonymized_at | timestamp with time zone | NULL | Thời điểm ẩn danh hóa khi hết thời hạn lưu hoặc rút đồng ý |

Ràng buộc:

- `candidates_phone_check` (CHECK): `CHECK ((phone ~ '^[0-9]{10}$'::text))`
- `candidates_pkey` (PK): `PRIMARY KEY (id)`
- `candidates_email_key` (UNIQUE): `UNIQUE (email)`

## Bảng `cv_submissions`

Một lần gửi hồ sơ: file CV (PDF/DOCX có lớp chữ), đồng ý xử lý dữ liệu, dữ liệu AI trích xuất, gợi ý việc làm. Không nộp vào tin nào trong 24 giờ thì xóa

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| candidate_id | bigint | NOT NULL | Ứng viên gửi |
| cv_storage_key | character varying(100) | NOT NULL | Tên file ngẫu nhiên trong kho lưu trữ |
| cv_original_name | character varying(255) | NOT NULL | Tên file gốc |
| cv_mime_type | character varying(100) | NOT NULL | Chỉ PDF hoặc DOCX |
| cv_size_bytes | integer | NOT NULL | Dung lượng, tối đa 5MB |
| cv_sha256 | character(64) | NOT NULL | Mã băm file để phát hiện trùng |
| cv_scan_status | scan_status | NOT NULL | Kết quả quét mã độc |
| consent_at | timestamp with time zone | NOT NULL | Thời điểm đồng ý xử lý dữ liệu (bắt buộc) |
| consent_policy_ver | character varying(20) | NOT NULL | Phiên bản chính sách dữ liệu đã hiển thị |
| parse_status | parse_status | NOT NULL | Trạng thái AI phân tích CV; FAILED = CV không đọc được, ứng viên gửi lại |
| parsed_data | jsonb | NULL | Dữ liệu AI trích xuất: học vấn, kinh nghiệm, kỹ năng... |
| embedding | vector(1536) | NULL | Vector ngữ nghĩa của CV, dùng lọc top-K tin phù hợp trước khi AI xếp hạng |
| suggestions | jsonb | NULL | Danh sách vị trí gợi ý: [{job_id, match_percent, reason}] |
| ip | inet | NULL | IP người gửi, dùng giới hạn tần suất |
| created_at | timestamp with time zone | NOT NULL | Thời điểm gửi |
| expires_at | timestamp with time zone | NOT NULL | Hạn xóa nếu chưa nộp vào tin nào (24 giờ) |

Ràng buộc:

- `cv_submissions_cv_mime_type_check` (CHECK): `CHECK (((cv_mime_type)::text = ANY ((ARRAY['application/pdf'::character varying, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'::character varying])::text[])))`
- `cv_submissions_cv_size_bytes_check` (CHECK): `CHECK (((cv_size_bytes > 0) AND (cv_size_bytes <= ((5 * 1024) * 1024))))`
- `cv_submissions_expiry` (CHECK): `CHECK ((expires_at > created_at))`
- `cv_submissions_parsed_has_data` (CHECK): `CHECK (((parse_status = ANY (ARRAY['PENDING'::parse_status, 'FAILED'::parse_status])) OR (parsed_data IS NOT NULL)))`
- `cv_submissions_suggestions_check` (CHECK): `CHECK (((suggestions IS NULL) OR ((jsonb_typeof(suggestions) = 'array'::text) AND (jsonb_array_length(suggestions) <= 10))))`
- `cv_submissions_candidate_id_fkey` (FK): `FOREIGN KEY (candidate_id) REFERENCES candidates(id)`
- `cv_submissions_pkey` (PK): `PRIMARY KEY (id)`
- `cv_submissions_cv_storage_key_key` (UNIQUE): `UNIQUE (cv_storage_key)`

Index:

- `CREATE INDEX cv_submissions_expiry_idx ON public.cv_submissions USING btree (expires_at)`

## Bảng `otp_codes`

Mã OTP gửi qua email, dùng cho nộp hồ sơ và quên mật khẩu; mỗi mã gắn một mục đích

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| email | citext | NOT NULL | Email nhận mã |
| purpose | otp_purpose | NOT NULL | APPLY (nộp hồ sơ) hoặc RESET_PASSWORD (quên mật khẩu) |
| code_hash | text | NOT NULL | Mã đã băm, không lưu mã gốc |
| submission_id | bigint | NULL | Lần gửi hồ sơ (khi APPLY) |
| job_id | bigint | NULL | Tin đang nộp (khi APPLY) |
| user_id | bigint | NULL | Tài khoản đặt lại mật khẩu (khi RESET_PASSWORD) |
| attempts | smallint | NOT NULL | Số lần nhập sai, tối đa 5 |
| created_at | timestamp with time zone | NOT NULL | Thời điểm gửi |
| expires_at | timestamp with time zone | NOT NULL | Hết hạn (mặc định 5 phút) |
| consumed_at | timestamp with time zone | NULL | Thời điểm dùng thành công |
| invalidated_at | timestamp with time zone | NULL | Bị hủy do gửi lại mã mới |
| ip | inet | NULL | IP yêu cầu mã |

Ràng buộc:

- `otp_codes_attempts_check` (CHECK): `CHECK (((attempts >= 0) AND (attempts <= 5)))`
- `otp_codes_expiry` (CHECK): `CHECK ((expires_at > created_at))`
- `otp_codes_purpose_refs` (CHECK): `CHECK ((((purpose = 'APPLY'::otp_purpose) AND (submission_id IS NOT NULL) AND (job_id IS NOT NULL) AND (user_id IS NULL)) OR ((purpose = 'RESET_PASSWORD'::otp_purpose) AND (user_id IS NOT NULL) AND (submission_id IS NULL) AND (job_id IS NULL))))`
- `otp_codes_job_id_fkey` (FK): `FOREIGN KEY (job_id) REFERENCES job_postings(id)`
- `otp_codes_submission_id_fkey` (FK): `FOREIGN KEY (submission_id) REFERENCES cv_submissions(id)`
- `otp_codes_user_id_fkey` (FK): `FOREIGN KEY (user_id) REFERENCES users(id)`
- `otp_codes_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE UNIQUE INDEX otp_one_live_code ON public.otp_codes USING btree (email, purpose) WHERE ((consumed_at IS NULL) AND (invalidated_at IS NULL))`
- `CREATE INDEX otp_rate_idx ON public.otp_codes USING btree (email, purpose, created_at)`

## Bảng `applications`

Hồ sơ ứng tuyển: một ứng viên nộp vào một tin sau khi xác thực OTP; 14 trạng thái

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| candidate_id | bigint | NOT NULL | Ứng viên |
| job_id | bigint | NOT NULL | Tin tuyển dụng |
| submission_id | bigint | NOT NULL | Lần gửi hồ sơ chứa CV dùng để nộp |
| status | application_status | NOT NULL | Trạng thái hồ sơ (14 trạng thái) |
| submitted_at | timestamp with time zone | NOT NULL | Thời điểm nộp = lúc OTP hợp lệ |
| criteria_set_id | bigint | NULL | Phiên bản tiêu chí đã dùng để chấm |
| ai_status | ai_score_status | NOT NULL | Trạng thái chấm AI: PENDING, SCORED, NEEDS_REVIEW, FAILED |
| ai_total_score | numeric(5,2) | NULL | Tổng điểm 0–100, do code tính theo trọng số |
| ai_failure_reason | text | NULL | Lý do AI không chấm được |
| hr_note | text | NULL | Ghi chú cho HR, ví dụ "Đạt ngưỡng – cần mời thủ công" |
| email_issue | character varying(100) | NULL | Lỗi gửi email gần nhất |
| review_due_at | timestamp with time zone | NULL | Hạn HR xét duyệt (5 ngày làm việc) |
| decided_by | bigint | NULL | HR ra quyết định duyệt / từ chối |
| decided_at | timestamp with time zone | NULL | Thời điểm ra quyết định |
| reject_reason_code | character varying(40) | NULL | Mã lý do từ chối nội bộ |
| reject_reason_text | text | NULL | Mô tả lý do khi chọn Khác (≤ 500 ký tự) |
| updated_at | timestamp with time zone | NOT NULL | Thời điểm cập nhật gần nhất |
| version | integer | NOT NULL | Số phiên bản dòng, chống hai HR xử lý cùng lúc |

Ràng buộc:

- `applications_ai_total_score_check` (CHECK): `CHECK (((ai_total_score >= (0)::numeric) AND (ai_total_score <= (100)::numeric)))`
- `applications_other_reason_text` (CHECK): `CHECK ((((reject_reason_code)::text IS DISTINCT FROM 'OTHER'::text) OR (length(TRIM(BOTH FROM COALESCE(reject_reason_text, ''::text))) > 0)))`
- `applications_reject_reason_text_check` (CHECK): `CHECK (((reject_reason_text IS NULL) OR (char_length(reject_reason_text) <= 500)))`
- `applications_rejected_by_hr` (CHECK): `CHECK (((status <> 'REJECTED'::application_status) OR ((decided_by IS NOT NULL) AND (decided_at IS NOT NULL) AND (reject_reason_code IS NOT NULL))))`
- `applications_scored_complete` (CHECK): `CHECK (((ai_status <> 'SCORED'::ai_score_status) OR ((ai_total_score IS NOT NULL) AND (criteria_set_id IS NOT NULL))))`
- `applications_candidate_id_fkey` (FK): `FOREIGN KEY (candidate_id) REFERENCES candidates(id)`
- `applications_criteria_set_fk` (FK): `FOREIGN KEY (criteria_set_id, job_id) REFERENCES criteria_sets(id, job_id)`
- `applications_decided_by_fkey` (FK): `FOREIGN KEY (decided_by) REFERENCES users(id)`
- `applications_job_id_fkey` (FK): `FOREIGN KEY (job_id) REFERENCES job_postings(id)`
- `applications_submission_id_fkey` (FK): `FOREIGN KEY (submission_id) REFERENCES cv_submissions(id)`
- `applications_pkey` (PK): `PRIMARY KEY (id)`
- `applications_candidate_id_job_id_key` (UNIQUE): `UNIQUE (candidate_id, job_id)`

Index:

- `CREATE INDEX applications_job_idx ON public.applications USING btree (job_id, status)`
- `CREATE INDEX applications_status_idx ON public.applications USING btree (status, submitted_at)`

Trigger:

- `applications_history` (AFTER INSERT,UPDATE) → trg_application_history

## Bảng `application_scores`

Điểm và nhận xét của AI theo từng tiêu chí của một hồ sơ

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| application_id | bigint | NOT NULL | Hồ sơ |
| criterion_id | bigint | NOT NULL | Tiêu chí |
| score | numeric(5,2) | NOT NULL | Điểm 0–100 do AI chấm |
| weight_snapshot | numeric(5,2) | NOT NULL | Trọng số lúc chấm, giúp điểm luôn tái lập được |
| ai_comment | text | NULL | Nhận xét của AI cho tiêu chí |
| meets_mandatory | boolean | NULL | Đạt tiêu chí bắt buộc hay không (NULL nếu không phải tiêu chí bắt buộc) |

Ràng buộc:

- `application_scores_score_check` (CHECK): `CHECK (((score >= (0)::numeric) AND (score <= (100)::numeric)))`
- `application_scores_weight_snapshot_check` (CHECK): `CHECK (((weight_snapshot > (0)::numeric) AND (weight_snapshot <= (100)::numeric)))`
- `application_scores_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `application_scores_criterion_id_fkey` (FK): `FOREIGN KEY (criterion_id) REFERENCES criteria(id)`
- `application_scores_pkey` (PK): `PRIMARY KEY (application_id, criterion_id)`

## Bảng `talent_pool_consents`

Đồng ý lưu hồ sơ cho đợt tuyển sau, thời hạn 12 tháng

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| candidate_id | bigint | NOT NULL | Ứng viên |
| application_id | bigint | NULL | Hồ sơ liên quan (nếu đồng ý từ thư cảm ơn) |
| source | consent_source | NOT NULL | Nguồn: màn hình chưa có vị trí phù hợp hoặc link trong thư cảm ơn |
| policy_ver | character varying(20) | NOT NULL | Phiên bản nội dung đồng ý đã hiển thị |
| consented_at | timestamp with time zone | NOT NULL | Thời điểm đồng ý |
| expires_at | timestamp with time zone | NOT NULL | Hết hạn lưu |
| revoked_at | timestamp with time zone | NULL | Thời điểm ứng viên rút lại đồng ý |

Ràng buộc:

- `talent_pool_expiry` (CHECK): `CHECK ((expires_at > consented_at))`
- `talent_pool_consents_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `talent_pool_consents_candidate_id_fkey` (FK): `FOREIGN KEY (candidate_id) REFERENCES candidates(id)`
- `talent_pool_consents_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE UNIQUE INDEX talent_pool_one_active ON public.talent_pool_consents USING btree (candidate_id) WHERE (revoked_at IS NULL)`

## Bảng `interviews`

Buổi phỏng vấn: lịch, link Meet, ghi chú đổi lịch. Một người phỏng vấn không có 2 buổi trùng giờ; một hồ sơ chỉ có 1 buổi đang hiệu lực

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| application_id | bigint | NOT NULL | Hồ sơ được phỏng vấn |
| interviewer_id | bigint | NOT NULL | Người phỏng vấn |
| start_at | timestamp with time zone | NOT NULL | Giờ bắt đầu |
| end_at | timestamp with time zone | NOT NULL | Giờ kết thúc |
| status | interview_status | NOT NULL | SCHEDULED, CONFIRMED, RESCHEDULE_REQUESTED, CANCELLED, COMPLETED |
| google_event_id | character varying(200) | NULL | Mã sự kiện trên Google Calendar |
| meet_link | character varying(300) | NULL | Link Google Meet |
| auto_scheduled | boolean | NOT NULL | TRUE = hệ thống tự mời; FALSE = HR mời |
| reschedule_note | character varying(500) | NULL | Ghi chú đổi lịch của ứng viên (≤ 500 ký tự); bắt buộc khi RESCHEDULE_REQUESTED, xóa khi HR xếp lại. Số lần yêu cầu (tối đa 2) đếm trong audit_logs |
| needs_manual_calendar_fix | boolean | NOT NULL | Google lỗi, HR cần cập nhật lịch thủ công |
| decline_reason | character varying(500) | NULL | Lý do ứng viên từ chối phỏng vấn (≤ 500 ký tự); chỉ có khi buổi đã hủy |
| created_by | bigint | NULL | HR tạo lịch; NULL khi tự động |
| created_at | timestamp with time zone | NOT NULL | Thời điểm tạo |

Ràng buộc:

- `interviews_creator_required` (CHECK): `CHECK ((auto_scheduled OR (created_by IS NOT NULL)))`
- `interviews_decline_only_cancelled` (CHECK): `CHECK (((decline_reason IS NULL) OR (status = 'CANCELLED'::interview_status)))`
- `interviews_reschedule_note_required` (CHECK): `CHECK (((status <> 'RESCHEDULE_REQUESTED'::interview_status) OR (length(TRIM(BOTH FROM COALESCE(reschedule_note, ''::character varying))) > 0)))`
- `interviews_time_order` (CHECK): `CHECK ((end_at > start_at))`
- `interviews_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `interviews_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `interviews_interviewer_id_fkey` (FK): `FOREIGN KEY (interviewer_id) REFERENCES users(id)`
- `interviews_pkey` (PK): `PRIMARY KEY (id)`
- `interviews_no_overlap` (EXCLUDE): `EXCLUDE USING gist (interviewer_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE ((status = ANY (ARRAY['SCHEDULED'::interview_status, 'CONFIRMED'::interview_status, 'RESCHEDULE_REQUESTED'::interview_status])))`

Index:

- `CREATE UNIQUE INDEX interviews_one_active ON public.interviews USING btree (application_id) WHERE (status = ANY (ARRAY['SCHEDULED'::interview_status, 'CONFIRMED'::interview_status, 'RESCHEDULE_REQUESTED'::interview_status]))`

## Bảng `interview_results`

Kết quả và phiếu đánh giá của buổi phỏng vấn; không sửa sau khi lưu

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| interview_id | bigint | NOT NULL | Buổi phỏng vấn |
| result | pass_fail | NULL | PASS / FAIL; NULL khi ứng viên vắng mặt |
| no_show | boolean | NOT NULL | Ứng viên vắng mặt |
| evaluation | jsonb | NULL | Phiếu đánh giá mức 1–5 theo tiêu chí (JSON) |
| comment | text | NULL | Nhận xét chung (≤ 2.000 ký tự) |
| entered_by | bigint | NOT NULL | Người phỏng vấn nhập kết quả |
| entered_at | timestamp with time zone | NOT NULL | Thời điểm nhập |

Ràng buộc:

- `interview_results_comment_check` (CHECK): `CHECK (((comment IS NULL) OR (char_length(comment) <= 2000)))`
- `interview_results_noshow_xor` (CHECK): `CHECK ((no_show = (result IS NULL)))`
- `interview_results_entered_by_fkey` (FK): `FOREIGN KEY (entered_by) REFERENCES users(id)`
- `interview_results_interview_id_fkey` (FK): `FOREIGN KEY (interview_id) REFERENCES interviews(id)`
- `interview_results_pkey` (PK): `PRIMARY KEY (interview_id)`

## Bảng `probation_offers`

Lời mời thử việc gửi ứng viên đạt phỏng vấn

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| application_id | bigint | NOT NULL | Hồ sơ đạt phỏng vấn |
| start_date | date | NOT NULL | Ngày bắt đầu thử việc |
| duration_days | smallint | NOT NULL | Thời gian thử việc (1–180 ngày) |
| location | character varying(200) | NOT NULL | Địa điểm làm việc |
| manager_id | bigint | NOT NULL | Quản lý bộ phận phụ trách (cùng phòng ban với tin) |
| created_by | bigint | NOT NULL | Người phỏng vấn / HR tạo lời mời |
| created_at | timestamp with time zone | NOT NULL | Thời điểm tạo |
| decline_reason | character varying(500) | NULL | Lý do ứng viên từ chối (≤ 500 ký tự) |

Ràng buộc:

- `probation_offers_duration_days_check` (CHECK): `CHECK (((duration_days >= 1) AND (duration_days <= 180)))`
- `probation_offers_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `probation_offers_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `probation_offers_manager_id_fkey` (FK): `FOREIGN KEY (manager_id) REFERENCES users(id)`
- `probation_offers_pkey` (PK): `PRIMARY KEY (id)`
- `probation_offers_application_id_key` (UNIQUE): `UNIQUE (application_id)`

## Bảng `response_links`

Link phản hồi gửi ứng viên qua email: dùng 1 lần, hạn 2 ngày làm việc, quá hạn mặc định từ chối

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| token_hash | text | NOT NULL | Mã băm của chuỗi ngẫu nhiên trong link |
| purpose | link_purpose | NOT NULL | Xác nhận lịch phỏng vấn, lời mời thử việc, đồng ý lưu hồ sơ |
| application_id | bigint | NOT NULL | Hồ sơ liên quan |
| interview_id | bigint | NULL | Buổi phỏng vấn (khi xác nhận lịch) |
| offer_id | bigint | NULL | Lời mời thử việc (khi phản hồi lời mời) |
| created_at | timestamp with time zone | NOT NULL | Thời điểm gửi |
| expires_at | timestamp with time zone | NOT NULL | Hạn phản hồi: hết giờ làm việc ngày làm việc thứ 2 |
| used_at | timestamp with time zone | NULL | Thời điểm ứng viên phản hồi hoặc hệ thống xử lý quá hạn |
| outcome | link_outcome | NULL | ACCEPTED, DECLINED, RESCHEDULE_REQUESTED (chỉ với lịch phỏng vấn), EXPIRED |
| invalidated_at | timestamp with time zone | NULL | Bị vô hiệu do HR xếp lại hoặc hủy lịch; không được dùng và không bị xử lý quá hạn |

Ràng buộc:

- `response_links_expiry` (CHECK): `CHECK ((expires_at > created_at))`
- `response_links_not_used_and_invalid` (CHECK): `CHECK (((invalidated_at IS NULL) OR (used_at IS NULL)))`
- `response_links_purpose_refs` (CHECK): `CHECK ((((purpose = 'CONFIRM_INTERVIEW'::link_purpose) AND (interview_id IS NOT NULL) AND (offer_id IS NULL)) OR ((purpose = 'PROBATION_OFFER'::link_purpose) AND (offer_id IS NOT NULL) AND (interview_id IS NULL)) OR ((purpose = 'TALENT_POOL_CONSENT'::link_purpose) AND (interview_id IS NULL) AND (offer_id IS NULL))))`
- `response_links_reschedule_only_interview` (CHECK): `CHECK (((outcome IS DISTINCT FROM 'RESCHEDULE_REQUESTED'::link_outcome) OR (purpose = 'CONFIRM_INTERVIEW'::link_purpose)))`
- `response_links_used_pair` (CHECK): `CHECK (((used_at IS NULL) = (outcome IS NULL)))`
- `response_links_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `response_links_interview_id_fkey` (FK): `FOREIGN KEY (interview_id) REFERENCES interviews(id)`
- `response_links_offer_id_fkey` (FK): `FOREIGN KEY (offer_id) REFERENCES probation_offers(id)`
- `response_links_pkey` (PK): `PRIMARY KEY (id)`
- `response_links_token_hash_key` (UNIQUE): `UNIQUE (token_hash)`

Index:

- `CREATE INDEX response_links_expiry_idx ON public.response_links USING btree (expires_at) WHERE ((used_at IS NULL) AND (invalidated_at IS NULL))`

## Bảng `probations`

Đợt thử việc, tạo khi Admin cấp tài khoản thử việc; kết luận Đạt / Không đạt

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| application_id | bigint | NOT NULL | Hồ sơ gốc |
| trainee_id | bigint | NOT NULL | Tài khoản nhân viên thử việc |
| manager_id | bigint | NOT NULL | Quản lý bộ phận phụ trách |
| department_id | bigint | NOT NULL | Phòng ban |
| start_date | date | NOT NULL | Ngày bắt đầu |
| end_date | date | NOT NULL | Ngày kết thúc |
| status | probation_status | NOT NULL | ONGOING, PASSED, FAILED |
| concluded_by | bigint | NULL | Quản lý kết luận |
| concluded_at | timestamp with time zone | NULL | Thời điểm kết luận |
| conclusion_note | text | NULL | Nhận xét kết luận |

Ràng buộc:

- `probations_concluded_by` (CHECK): `CHECK (((status = 'ONGOING'::probation_status) OR (concluded_by IS NOT NULL)))`
- `probations_concluded_pair` (CHECK): `CHECK (((status = 'ONGOING'::probation_status) = (concluded_at IS NULL)))`
- `probations_dates` (CHECK): `CHECK ((end_date >= start_date))`
- `probations_trainee_not_manager` (CHECK): `CHECK ((trainee_id <> manager_id))`
- `probations_application_id_fkey` (FK): `FOREIGN KEY (application_id) REFERENCES applications(id)`
- `probations_concluded_by_fkey` (FK): `FOREIGN KEY (concluded_by) REFERENCES users(id)`
- `probations_department_id_fkey` (FK): `FOREIGN KEY (department_id) REFERENCES departments(id)`
- `probations_manager_id_fkey` (FK): `FOREIGN KEY (manager_id) REFERENCES users(id)`
- `probations_trainee_id_fkey` (FK): `FOREIGN KEY (trainee_id) REFERENCES users(id)`
- `probations_pkey` (PK): `PRIMARY KEY (id)`
- `probations_application_id_key` (UNIQUE): `UNIQUE (application_id)`

## Bảng `probation_tasks`

Task thử việc do quản lý bộ phận giao

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| probation_id | bigint | NOT NULL | Đợt thử việc |
| title | character varying(200) | NOT NULL | Tên task |
| description | text | NULL | Mô tả yêu cầu (≤ 5.000 ký tự) |
| attachments | jsonb | NOT NULL | Tài liệu đính kèm (≤ 5 tệp): [{storage_key, file_name, size_bytes}] |
| due_at | timestamp with time zone | NOT NULL | Hạn nộp |
| created_by | bigint | NOT NULL | Quản lý giao task |
| created_at | timestamp with time zone | NOT NULL | Thời điểm giao |
| deleted_at | timestamp with time zone | NULL | Thời điểm xóa task (xóa mềm) |

Ràng buộc:

- `probation_tasks_attachments_check` (CHECK): `CHECK (((jsonb_typeof(attachments) = 'array'::text) AND (jsonb_array_length(attachments) <= 5)))`
- `probation_tasks_description_check` (CHECK): `CHECK (((description IS NULL) OR (char_length(description) <= 5000)))`
- `probation_tasks_created_by_fkey` (FK): `FOREIGN KEY (created_by) REFERENCES users(id)`
- `probation_tasks_probation_id_fkey` (FK): `FOREIGN KEY (probation_id) REFERENCES probations(id)`
- `probation_tasks_pkey` (PK): `PRIMARY KEY (id)`

Index:

- `CREATE INDEX probation_tasks_probation_idx ON public.probation_tasks USING btree (probation_id) WHERE (deleted_at IS NULL)`

## Bảng `task_submissions`

Bài nộp của task (mỗi task 1 bài, sửa được khi chưa đánh giá); đánh giá Đạt / Không đạt

| Cột | Kiểu | Null | Ghi chú |
|---|---|---|---|
| id | bigint | NOT NULL |  |
| task_id | bigint | NOT NULL | Task |
| content_link | character varying(500) | NULL | Link bài làm |
| storage_key | character varying(100) | NULL | File bài làm trong kho lưu trữ |
| submitted_at | timestamp with time zone | NOT NULL | Thời điểm nộp (lần nộp hoặc cập nhật gần nhất) |
| result | pass_fail | NULL | PASS / FAIL; NULL = chưa đánh giá |
| review_comment | text | NULL | Nhận xét của quản lý (≤ 2.000 ký tự) |
| reviewed_by | bigint | NULL | Quản lý đánh giá |
| reviewed_at | timestamp with time zone | NULL | Thời điểm đánh giá |
| note | character varying(1000) | NULL | Ghi chú của nhân viên cho quản lý (≤ 1.000 ký tự) |
| revision | smallint | NOT NULL | Lần nộp: 1 = lần đầu, > 1 = đã cập nhật; chống ghi đè khi quản lý đang đánh giá |

Ràng buộc:

- `task_submissions_has_content` (CHECK): `CHECK (((content_link IS NOT NULL) OR (storage_key IS NOT NULL)))`
- `task_submissions_review_comment_check` (CHECK): `CHECK (((review_comment IS NULL) OR (char_length(review_comment) <= 2000)))`
- `task_submissions_review_triple` (CHECK): `CHECK ((((result IS NULL) = (reviewed_at IS NULL)) AND ((result IS NULL) = (reviewed_by IS NULL))))`
- `task_submissions_revision_check` (CHECK): `CHECK ((revision >= 1))`
- `task_submissions_reviewed_by_fkey` (FK): `FOREIGN KEY (reviewed_by) REFERENCES users(id)`
- `task_submissions_task_id_fkey` (FK): `FOREIGN KEY (task_id) REFERENCES probation_tasks(id)`
- `task_submissions_pkey` (PK): `PRIMARY KEY (id)`
- `task_submissions_storage_key_key` (UNIQUE): `UNIQUE (storage_key)`
- `task_submissions_task_id_key` (UNIQUE): `UNIQUE (task_id)`

Trigger:

- `task_submissions_locked` (BEFORE UPDATE) → trg_submission_locked
