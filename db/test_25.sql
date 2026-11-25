-- =====================================================================
-- KIỂM THỬ LƯỢC ĐỒ 25 BẢNG
-- Chạy sau schema_25.sql trên CSDL rỗng:
--   psql -v ON_ERROR_STOP=1 -f schema_25.sql -f test_25.sql
-- Mỗi ca chạy trong giao dịch con rồi hoàn tác, nên các ca độc lập.
-- Kết quả cuối: bảng tổng hợp ĐẠT / KHÔNG ĐẠT.
-- =====================================================================
\set QUIET on
SET client_min_messages = warning;

CREATE TEMP TABLE t_result (no serial, grp text, name text, expect text, ok boolean, detail text);

-- t(nhóm, tên ca, câu lệnh, 'fail' | 'ok')
CREATE FUNCTION pg_temp.t(p_grp text, p_name text, p_sql text, p_expect text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE err text := NULL;
BEGIN
  BEGIN
    EXECUTE 'DO $tq$BEGIN ' || p_sql || '; END$tq$';
    SET CONSTRAINTS ALL IMMEDIATE;
    RAISE EXCEPTION 'ROLLBACK_OK';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM <> 'ROLLBACK_OK' THEN err := SQLERRM; END IF;
  END;
  INSERT INTO t_result (grp, name, expect, ok, detail)
  VALUES (p_grp, p_name, p_expect,
          CASE WHEN p_expect = 'fail' THEN err IS NOT NULL ELSE err IS NULL END,
          coalesce(err, 'thành công'));
END $$;

-- c(nhóm, tên ca, biểu thức boolean): kiểm tra một điều kiện
CREATE FUNCTION pg_temp.c(p_grp text, p_name text, p_cond text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE r boolean; err text;
BEGIN
  BEGIN
    EXECUTE 'SELECT (' || p_cond || ')' INTO r;
  EXCEPTION WHEN OTHERS THEN err := SQLERRM; r := false;
  END;
  INSERT INTO t_result (grp, name, expect, ok, detail)
  VALUES (p_grp, p_name, 'true', coalesce(r,false), coalesce(err, r::text));
END $$;

-- ---------------------------------------------------------------------
-- DỮ LIỆU NỀN
-- ---------------------------------------------------------------------
BEGIN;
INSERT INTO departments (name) VALUES ('Phòng Công nghệ'), ('Phòng Kinh doanh');

INSERT INTO users (account_type, full_name, email, department_id) VALUES
 ('ADMIN',    'Admin Một',    'admin1@cty.vn', NULL),   -- 1
 ('EMPLOYEE', 'Nhân viên Hai','nv2@cty.vn', 1),         -- 2
 ('EMPLOYEE', 'Lan HR',       'lan.hr@cty.vn', 1),      -- 3
 ('EMPLOYEE', 'Minh PV',      'minh.pv@cty.vn', 1),     -- 4
 ('EMPLOYEE', 'Hùng QL',      'hung.ql@cty.vn', 1),     -- 5
 ('EMPLOYEE', 'An Thử việc',  'an.tv@cty.vn', 1),       -- 6
 ('EMPLOYEE', 'Bình PV',      'binh.pv@cty.vn', 1),     -- 7
 ('EMPLOYEE', 'Cũ Bị khóa',   'cu@cty.vn', 1);          -- 8
UPDATE users SET status = 'LOCKED' WHERE id = 8;

INSERT INTO user_roles (user_id, role) VALUES
 (3,'HR'), (4,'INTERVIEWER'), (5,'DEPT_MANAGER'), (6,'PROBATION'), (7,'INTERVIEWER');

INSERT INTO holidays VALUES ('2026-12-31', 'Nghỉ cuối năm');

INSERT INTO email_templates (code, subject, body, required_vars) VALUES
 ('INVITE', 'Mời phỏng vấn {ten_vi_tri}', 'Chào {ho_ten}, mời bạn phỏng vấn lúc {gio}. Link: {link}', '{ho_ten,gio,link,ten_vi_tri}'),
 ('RESCHEDULED', 'Lịch phỏng vấn đã thay đổi', 'Chào {ho_ten}, lịch mới: {gio}. Xác nhận: {link}', '{ho_ten,gio,link}');

-- Tin 1 (OPEN) và tin 2 (DRAFT)
INSERT INTO job_postings (title, department_id, description, requirements, headcount, deadline, created_by)
VALUES ('Lập trình viên Java', 1, 'Mô tả', 'Yêu cầu', 2, '2026-12-31', 3),
       ('Nhân viên kinh doanh', 2, 'Mô tả', 'Yêu cầu', 1, '2026-12-31', 3);
INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by) VALUES (1, 1, 70, 3), (2, 1, 60, 3);
INSERT INTO criteria (criteria_set_id, name, description, is_mandatory, weight) VALUES
 (1, 'Kinh nghiệm Java', 'Từ 2 năm kinh nghiệm Java', true, 60),
 (1, 'Tiếng Anh', 'Đọc hiểu tài liệu', false, 40),
 (2, 'Giao tiếp', 'Giao tiếp tốt', false, 100);
UPDATE job_postings SET status = 'OPEN', current_criteria_set_id = 1 WHERE id = 1;
UPDATE job_postings SET current_criteria_set_id = 2 WHERE id = 2;
INSERT INTO job_interviewers (job_id, user_id) VALUES (1, 4), (1, 7);

-- Ứng viên, hồ sơ tạm, hồ sơ ứng tuyển
INSERT INTO candidates (email, full_name, phone) VALUES
 ('uv1@gmail.com', 'Nguyễn Văn A', '0912345678'),
 ('uv2@gmail.com', 'Trần Thị B',   '0987654321');
INSERT INTO cv_submissions (candidate_id, cv_storage_key, cv_original_name, cv_mime_type, cv_size_bytes,
  cv_sha256, consent_at, consent_policy_ver, parse_status, parsed_data, expires_at)
VALUES
 (1, 'k1', 'cv_a.pdf', 'application/pdf', 200000, repeat('a',64), now(), 'v1', 'PARSED', '{"skills":["Java"]}', now() + interval '24 hours'),
 (2, 'k2', 'cv_b.pdf', 'application/pdf', 300000, repeat('b',64), now(), 'v1', 'PARSED', '{"skills":["Sales"]}', now() + interval '24 hours');
INSERT INTO applications (candidate_id, job_id, submission_id, criteria_set_id) VALUES
 (1, 1, 1, 1),   -- hồ sơ 1
 (2, 1, 2, 1);   -- hồ sơ 2

-- Buổi phỏng vấn của hồ sơ 1 (người phỏng vấn 4)
INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled, google_event_id, meet_link)
VALUES (1, 4, '2026-11-17 09:00+07', '2026-11-17 09:45+07', true, 'ev1', 'https://meet.google.com/abc');

-- Đợt thử việc (giả lập hồ sơ 2 đã qua phỏng vấn) và task
INSERT INTO probation_offers (application_id, start_date, duration_days, location, manager_id, created_by)
VALUES (2, '2026-12-01', 60, 'Hà Nội', 5, 4);
INSERT INTO probations (application_id, trainee_id, manager_id, department_id, start_date, end_date)
VALUES (2, 6, 5, 1, '2026-12-01', '2027-01-29');
INSERT INTO probation_tasks (probation_id, title, due_at, created_by) VALUES
 (1, 'Task 1', '2026-12-10 17:00+07', 5),
 (1, 'Task 2', '2026-12-20 17:00+07', 5);
INSERT INTO task_submissions (task_id, content_link) VALUES (1, 'https://git.cty.vn/an/task1');

INSERT INTO response_links (token_hash, purpose, application_id, interview_id, expires_at)
VALUES ('h-interview-1', 'CONFIRM_INTERVIEW', 1, 1, now() + interval '2 days');
INSERT INTO audit_logs (action, target_type, target_id) VALUES ('VIEW_APPLICATION', 'application', 1);
COMMIT;

-- ---------------------------------------------------------------------
-- A. CẤU TRÚC SAU ĐỢT RÚT GỌN
-- ---------------------------------------------------------------------
SELECT pg_temp.c('A. Cấu trúc', 'Có đúng 25 bảng',
  $$(SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE') = 25$$);
SELECT pg_temp.c('A. Cấu trúc', 'Không còn bảng chuyển giao công việc',
  $$to_regclass('public.handover_items') IS NULL$$);
SELECT pg_temp.c('A. Cấu trúc', 'Không còn 2 enum chuyển giao',
  $$NOT EXISTS (SELECT 1 FROM pg_type WHERE typname IN ('handover_status','handover_type'))$$);
SELECT pg_temp.c('A. Cấu trúc', 'Bảng phỏng vấn không còn 4 cột khung giờ đề xuất',
  $$NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interviews' AND column_name LIKE 'proposed_slot%')$$);
SELECT pg_temp.c('A. Cấu trúc', 'Bảng phỏng vấn có cột ghi chú đổi lịch ≤ 500',
  $$EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='interviews' AND column_name='reschedule_note' AND character_maximum_length=500)$$);
SELECT pg_temp.c('A. Cấu trúc', 'Người dùng không còn mã Google',
  $$NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='google_user_id')$$);
SELECT pg_temp.c('A. Cấu trúc', 'Hồ sơ tạm không còn cờ cần HR xem',
  $$NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cv_submissions' AND column_name='needs_hr_attention')$$);
SELECT pg_temp.c('A. Cấu trúc', 'Bảng điểm không còn 2 cột trích dẫn',
  $$NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='application_scores' AND column_name IN ('evidence_quote','evidence_verified'))$$);
SELECT pg_temp.c('A. Cấu trúc', 'Ràng buộc lý do nhật ký không còn khóa khẩn cấp',
  $$NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='audit_logs'::regclass AND pg_get_constraintdef(oid) LIKE '%EMERGENCY_LOCK%')$$);
SELECT pg_temp.c('A. Cấu trúc', 'Mọi khóa ngoại đều có bảng đích',
  $$NOT EXISTS (SELECT 1 FROM pg_constraint WHERE contype='f' AND confrelid = 0)$$);

-- ---------------------------------------------------------------------
-- B. TÀI KHOẢN VÀ VAI TRÒ
-- ---------------------------------------------------------------------
SELECT pg_temp.t('B. Tài khoản', 'Admin không được có phòng ban',
  $$UPDATE users SET department_id=1 WHERE id=1$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Email sai định dạng bị chặn',
  $$INSERT INTO users (account_type, full_name, email) VALUES ('EMPLOYEE','X','khong-co-a-cong')$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Email công ty trùng (khác hoa thường) bị chặn',
  $$INSERT INTO users (account_type, full_name, email, department_id) VALUES ('EMPLOYEE','X','LAN.HR@cty.vn',1)$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Tài khoản đang hoạt động phải có email',
  $$INSERT INTO users (account_type, full_name, email, department_id) VALUES ('EMPLOYEE','X',NULL,1)$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Không gán vai trò nghiệp vụ cho Admin',
  $$INSERT INTO user_roles (user_id, role) VALUES (1,'HR')$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Một người được nhiều vai trò (HR + Người phỏng vấn)',
  $$INSERT INTO user_roles (user_id, role) VALUES (3,'INTERVIEWER')$$, 'ok');
SELECT pg_temp.t('B. Tài khoản', 'Nhân viên thử việc không được thêm vai trò khác',
  $$INSERT INTO user_roles (user_id, role) VALUES (6,'HR')$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Người đã có vai trò khác không được gán vai trò thử việc',
  $$INSERT INTO user_roles (user_id, role) VALUES (4,'PROBATION')$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Cấp tài khoản thử việc: Admin nhập email công ty, hệ thống tạo tài khoản + vai trò',
  $$WITH u AS (INSERT INTO users (account_type, full_name, email, department_id, created_by)
               VALUES ('EMPLOYEE','Trần Thị B','tran.b@cty.vn',1,1) RETURNING id)
    INSERT INTO user_roles (user_id, role, granted_by) SELECT id, 'PROBATION', 1 FROM u$$, 'ok');
SELECT pg_temp.c('B. Tài khoản', 'Không còn trigger bắt buộc 2 Admin (Admin thuộc hệ thống lớn, 16/11)',
  $$NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='users_min_two_admins')$$);
SELECT pg_temp.t('B. Tài khoản', 'Không tạo được tài khoản Admin thứ hai (hệ thống con chỉ 1 Admin)',
  $$INSERT INTO users (account_type, full_name, email) VALUES ('ADMIN','Admin Hai','admin2@cty.vn')$$, 'fail');
SELECT pg_temp.c('B. Tài khoản', 'Bảng người dùng không còn 3 cột cửa sổ đặt lại mật khẩu Admin',
  $$NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name IN ('reset_opened_by','reset_window_expires_at','first_password_deadline'))$$);
SELECT pg_temp.t('B. Tài khoản', 'Không xóa tài khoản chưa khóa',
  $$UPDATE users SET status='DELETED', deleted_at=now(), email=NULL, password_hash=NULL WHERE id=7$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Xóa tài khoản đã khóa = ẩn danh hóa',
  $$UPDATE users SET status='DELETED', deleted_at=now(), email=NULL, password_hash=NULL WHERE id=8$$, 'ok');
SELECT pg_temp.t('B. Tài khoản', 'Xóa mà còn giữ email bị chặn',
  $$UPDATE users SET status='DELETED', deleted_at=now() WHERE id=8$$, 'fail');
SELECT pg_temp.t('B. Tài khoản', 'Tài khoản đã xóa không khôi phục được',
  $$UPDATE users SET status='DELETED', deleted_at=now(), email=NULL, password_hash=NULL WHERE id=8;
    UPDATE users SET status='ACTIVE', deleted_at=NULL, email='cu2@cty.vn' WHERE id=8$$, 'fail');
SELECT pg_temp.c('B. Tài khoản', 'Ràng buộc lý do nhật ký không còn tạo / đặt lại mật khẩu Admin',
  $$NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='audit_logs'::regclass AND pg_get_constraintdef(oid) LIKE '%ADMIN%')$$);

-- ---------------------------------------------------------------------
-- C. CẤU HÌNH, MẪU EMAIL, NHẬT KÝ
-- ---------------------------------------------------------------------
SELECT pg_temp.t('C. Cấu hình', 'Tham số ngoài khoảng cho phép bị chặn',
  $$UPDATE system_settings SET value=9 WHERE key='response_deadline_days'$$, 'fail');
SELECT pg_temp.t('C. Cấu hình', 'Tham số trong khoảng được sửa',
  $$UPDATE system_settings SET value=3 WHERE key='response_deadline_days'$$, 'ok');
SELECT pg_temp.t('C. Cấu hình', 'Không vừa có giá trị số vừa có JSON',
  $$INSERT INTO system_settings (key, value, value_json, default_value, min_value, max_value) VALUES ('x',1,'{}',1,0,2)$$, 'fail');
SELECT pg_temp.t('C. Mẫu email', 'Mẫu thiếu biến bắt buộc bị chặn',
  $$UPDATE email_templates SET body='Chào bạn, mời phỏng vấn' WHERE code='INVITE'$$, 'fail');
SELECT pg_temp.t('C. Mẫu email', 'Mẫu đủ biến bắt buộc được lưu',
  $$UPDATE email_templates SET body='Xin chào {ho_ten}: {gio} – {link}' WHERE code='INVITE'$$, 'ok');
SELECT pg_temp.t('C. Nhật ký', 'Không sửa nhật ký',
  $$UPDATE audit_logs SET action='X' WHERE id=1$$, 'fail');
SELECT pg_temp.t('C. Nhật ký', 'Không xóa nhật ký',
  $$DELETE FROM audit_logs WHERE id=1$$, 'fail');
SELECT pg_temp.t('C. Nhật ký', 'Khóa tài khoản phải có lý do',
  $$INSERT INTO audit_logs (actor_id, action, target_type, target_id) VALUES (1,'LOCK','user',7)$$, 'fail');
SELECT pg_temp.t('C. Nhật ký', 'Khóa tài khoản có lý do được ghi',
  $$INSERT INTO audit_logs (actor_id, action, target_type, target_id, reason) VALUES (1,'LOCK','user',7,'Nghỉ việc')$$, 'ok');
SELECT pg_temp.t('C. Nhật ký', 'Gỡ vai trò phải có lý do (khoảng trắng không tính)',
  $$INSERT INTO audit_logs (actor_id, action, target_type, target_id, reason) VALUES (1,'REVOKE_ROLE','user',7,'   ')$$, 'fail');

-- ---------------------------------------------------------------------
-- D. TIN TUYỂN DỤNG VÀ TIÊU CHÍ
-- ---------------------------------------------------------------------
SELECT pg_temp.t('D. Tin & tiêu chí', 'Mở tin khi chưa có bộ tiêu chí bị chặn',
  $$INSERT INTO job_postings (title, department_id, description, requirements, headcount, deadline, status, created_by)
    VALUES ('X',1,'a','b',1,'2026-12-31','OPEN',3)$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Mô tả tin quá 5.000 ký tự bị chặn',
  $$UPDATE job_postings SET description=repeat('x',5001) WHERE id=2$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Đóng tin phải ghi thời điểm đóng',
  $$UPDATE job_postings SET status='CLOSED' WHERE id=2$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Không gắn bộ tiêu chí của tin khác',
  $$UPDATE job_postings SET current_criteria_set_id=2 WHERE id=1$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Tổng trọng số khác 100 bị chặn',
  $$INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by) VALUES (1,2,70,3);
    INSERT INTO criteria (criteria_set_id, name, description, weight)
    SELECT id, 'A', 'a', 50 FROM criteria_sets WHERE job_id=1 AND version_no=2;
    INSERT INTO criteria (criteria_set_id, name, description, weight)
    SELECT id, 'B', 'b', 40 FROM criteria_sets WHERE job_id=1 AND version_no=2$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Lưu phiên bản mới (tổng 100) và gắn làm bộ đang áp dụng',
  $$INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by) VALUES (1,2,75,3);
    INSERT INTO criteria (criteria_set_id, name, description, is_mandatory, weight)
    SELECT id, 'A', 'a', true, 70 FROM criteria_sets WHERE job_id=1 AND version_no=2;
    INSERT INTO criteria (criteria_set_id, name, description, weight)
    SELECT id, 'B', 'b', 30 FROM criteria_sets WHERE job_id=1 AND version_no=2;
    UPDATE job_postings SET current_criteria_set_id=(SELECT id FROM criteria_sets WHERE job_id=1 AND version_no=2), version=version+1 WHERE id=1$$, 'ok');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Không sửa tiêu chí đã lưu',
  $$UPDATE criteria SET weight=50 WHERE id=1$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Không xóa tiêu chí đã lưu',
  $$DELETE FROM criteria WHERE id=1$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Số phiên bản trùng trong một tin bị chặn',
  $$INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by) VALUES (1,1,70,3)$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Ngưỡng tự động mời > 100 bị chặn',
  $$INSERT INTO criteria_sets (job_id, version_no, auto_invite_threshold, created_by) VALUES (1,9,101,3)$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Trọng số 0 bị chặn',
  $$INSERT INTO criteria (criteria_set_id, name, description, weight) VALUES (1,'Z','z',0)$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Mô tả tiêu chí quá 1.000 ký tự bị chặn',
  $$INSERT INTO criteria (criteria_set_id, name, description, weight) VALUES (1,'Z',repeat('x',1001),10)$$, 'fail');
SELECT pg_temp.t('D. Tin & tiêu chí', 'Gán trùng người phỏng vấn cho cùng tin bị chặn',
  $$INSERT INTO job_interviewers (job_id, user_id) VALUES (1,4)$$, 'fail');

-- ---------------------------------------------------------------------
-- E. ỨNG VIÊN, HỒ SƠ TẠM, OTP
-- ---------------------------------------------------------------------
SELECT pg_temp.t('E. Ứng viên & CV', 'Số điện thoại không đủ 10 chữ số bị chặn',
  $$INSERT INTO candidates (email, full_name, phone) VALUES ('x@gmail.com','X','091234567')$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'Email ứng viên trùng (khác hoa thường) bị chặn',
  $$INSERT INTO candidates (email, full_name, phone) VALUES ('UV1@gmail.com','X','0912345678')$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'CV dạng ảnh (PNG) bị chặn',
  $$INSERT INTO cv_submissions (candidate_id, cv_storage_key, cv_original_name, cv_mime_type, cv_size_bytes, cv_sha256, consent_at, consent_policy_ver, expires_at)
    VALUES (1,'k9','a.png','image/png',1000,repeat('c',64),now(),'v1',now()+interval '1 day')$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'CV DOCX được nhận',
  $$INSERT INTO cv_submissions (candidate_id, cv_storage_key, cv_original_name, cv_mime_type, cv_size_bytes, cv_sha256, consent_at, consent_policy_ver, expires_at)
    VALUES (1,'k9','a.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',1000,repeat('c',64),now(),'v1',now()+interval '1 day')$$, 'ok');
SELECT pg_temp.t('E. Ứng viên & CV', 'CV quá 5MB bị chặn',
  $$INSERT INTO cv_submissions (candidate_id, cv_storage_key, cv_original_name, cv_mime_type, cv_size_bytes, cv_sha256, consent_at, consent_policy_ver, expires_at)
    VALUES (1,'k9','a.pdf','application/pdf',5*1024*1024+1,repeat('c',64),now(),'v1',now()+interval '1 day')$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'Đã phân tích mà không có dữ liệu trích xuất bị chặn',
  $$UPDATE cv_submissions SET parse_status='PARSED', parsed_data=NULL WHERE id=1$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'CV không đọc được (FAILED) không cần dữ liệu',
  $$UPDATE cv_submissions SET parse_status='FAILED', parsed_data=NULL WHERE id=1$$, 'ok');
SELECT pg_temp.t('E. Ứng viên & CV', 'Gợi ý quá 10 vị trí bị chặn',
  $$UPDATE cv_submissions SET suggestions=(SELECT jsonb_agg(g) FROM generate_series(1,11) g) WHERE id=1$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'Lưu vector 1536 chiều của CV',
  $$UPDATE cv_submissions SET embedding=(SELECT array_agg(0.01)::vector(1536) FROM generate_series(1,1536)) WHERE id=1$$, 'ok');
SELECT pg_temp.t('E. Ứng viên & CV', 'Vector sai số chiều bị chặn',
  $$UPDATE cv_submissions SET embedding='[1,2,3]' WHERE id=1$$, 'fail');
SELECT pg_temp.t('E. Ứng viên & CV', 'Tìm tin gần nhất theo độ tương đồng (pgvector)',
  $$UPDATE job_postings SET embedding=(SELECT array_agg(0.02)::vector(1536) FROM generate_series(1,1536)) WHERE id=1;
    PERFORM 1 FROM job_postings WHERE status='OPEN'
      ORDER BY embedding <=> (SELECT array_agg(0.01)::vector(1536) FROM generate_series(1,1536)) LIMIT 5$$, 'ok');
SELECT pg_temp.t('E. OTP', 'OTP nộp hồ sơ thiếu tin tuyển dụng bị chặn',
  $$INSERT INTO otp_codes (email, purpose, code_hash, submission_id, expires_at) VALUES ('uv1@gmail.com','APPLY','h',1,now()+interval '5 min')$$, 'fail');
SELECT pg_temp.t('E. OTP', 'OTP quên mật khẩu không gắn hồ sơ',
  $$INSERT INTO otp_codes (email, purpose, code_hash, user_id, submission_id, expires_at) VALUES ('lan.hr@cty.vn','RESET_PASSWORD','h',3,1,now()+interval '5 min')$$, 'fail');
SELECT pg_temp.t('E. OTP', 'Hai mã còn hiệu lực cùng email, cùng mục đích bị chặn',
  $$INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, expires_at) VALUES ('uv1@gmail.com','APPLY','h1',1,1,now()+interval '5 min');
    INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, expires_at) VALUES ('uv1@gmail.com','APPLY','h2',1,1,now()+interval '5 min')$$, 'fail');
SELECT pg_temp.t('E. OTP', 'Gửi lại mã: hủy mã cũ rồi tạo mã mới',
  $$INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, expires_at) VALUES ('uv1@gmail.com','APPLY','h1',1,1,now()+interval '5 min');
    UPDATE otp_codes SET invalidated_at=now() WHERE email='uv1@gmail.com';
    INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, expires_at) VALUES ('uv1@gmail.com','APPLY','h2',1,1,now()+interval '5 min')$$, 'ok');
SELECT pg_temp.t('E. OTP', 'Nhập sai quá 5 lần bị chặn',
  $$INSERT INTO otp_codes (email, purpose, code_hash, submission_id, job_id, attempts, expires_at) VALUES ('uv1@gmail.com','APPLY','h',1,1,6,now()+interval '5 min')$$, 'fail');

-- ---------------------------------------------------------------------
-- F. HỒ SƠ ỨNG TUYỂN VÀ CHẤM ĐIỂM
-- ---------------------------------------------------------------------
SELECT pg_temp.t('F. Hồ sơ', 'Một ứng viên nộp 2 lần vào cùng tin bị chặn',
  $$INSERT INTO applications (candidate_id, job_id, submission_id) VALUES (1,1,1)$$, 'fail');
SELECT pg_temp.t('F. Hồ sơ', 'Đã chấm mà thiếu tổng điểm bị chặn',
  $$UPDATE applications SET ai_status='SCORED' WHERE id=1$$, 'fail');
SELECT pg_temp.t('F. Hồ sơ', 'Chấm theo bộ tiêu chí của tin khác bị chặn',
  $$UPDATE applications SET criteria_set_id=2 WHERE id=1$$, 'fail');
SELECT pg_temp.t('F. Hồ sơ', 'Từ chối hồ sơ phải có HR quyết định và lý do',
  $$UPDATE applications SET status='REJECTED' WHERE id=1$$, 'fail');
SELECT pg_temp.t('F. Hồ sơ', 'Lý do "Khác" phải có mô tả',
  $$UPDATE applications SET status='REJECTED', decided_by=3, decided_at=now(), reject_reason_code='OTHER' WHERE id=1$$, 'fail');
SELECT pg_temp.t('F. Hồ sơ', 'HR từ chối hồ sơ đủ thông tin',
  $$UPDATE applications SET status='REJECTED', decided_by=3, decided_at=now(), reject_reason_code='OTHER', reject_reason_text='Không phù hợp văn hóa' WHERE id=1$$, 'ok');
SELECT pg_temp.t('F. Chấm điểm', 'Lưu điểm từng tiêu chí + tổng điểm (luồng Chấm điểm CV)',
  $$INSERT INTO application_scores (application_id, criterion_id, score, weight_snapshot, ai_comment, meets_mandatory)
    VALUES (1,1,80,60,'3 năm Java',true), (1,2,70,40,'Đọc hiểu tốt',NULL);
    UPDATE applications SET ai_status='SCORED', ai_total_score=76 WHERE id=1$$, 'ok');
SELECT pg_temp.t('F. Chấm điểm', 'Điểm tiêu chí bắt buộc phải có (không NULL)',
  $$INSERT INTO application_scores (application_id, criterion_id, score, weight_snapshot) VALUES (1,1,NULL,60)$$, 'fail');
SELECT pg_temp.t('F. Chấm điểm', 'Điểm > 100 bị chặn',
  $$INSERT INTO application_scores (application_id, criterion_id, score, weight_snapshot) VALUES (1,1,101,60)$$, 'fail');
SELECT pg_temp.t('F. Chấm điểm', 'Một tiêu chí chỉ có một điểm cho mỗi hồ sơ',
  $$INSERT INTO application_scores (application_id, criterion_id, score, weight_snapshot) VALUES (1,1,80,60);
    INSERT INTO application_scores (application_id, criterion_id, score, weight_snapshot) VALUES (1,1,90,60)$$, 'fail');
SELECT pg_temp.t('F. Lịch sử', 'Đổi trạng thái hồ sơ tự ghi nhật ký kèm người thực hiện',
  $$PERFORM set_config('app.actor_id','3',true);
    UPDATE applications SET status='PENDING_HR_REVIEW' WHERE id=2;
    IF NOT EXISTS (SELECT 1 FROM audit_logs WHERE action='APPLICATION_STATUS' AND target_id=2 AND actor_id=3
                   AND before_data->>'status'='SCORING' AND after_data->>'status'='PENDING_HR_REVIEW') THEN
      RAISE EXCEPTION 'không thấy nhật ký trạng thái';
    END IF$$, 'ok');
SELECT pg_temp.t('F. Lịch sử', 'Sửa hồ sơ mà không đổi trạng thái thì không ghi nhật ký',
  $$UPDATE applications SET hr_note='ghi chú' WHERE id=2;
    IF (SELECT count(*) FROM audit_logs WHERE action='APPLICATION_STATUS' AND target_id=2) <> 1 THEN
      RAISE EXCEPTION 'ghi thừa nhật ký';
    END IF$$, 'ok');
SELECT pg_temp.t('F. Lưu hồ sơ', 'Hai đồng ý lưu hồ sơ còn hiệu lực cùng ứng viên bị chặn',
  $$INSERT INTO talent_pool_consents (candidate_id, source, policy_ver, expires_at) VALUES (1,'NO_MATCH_SCREEN','v1',now()+interval '12 months');
    INSERT INTO talent_pool_consents (candidate_id, source, policy_ver, expires_at) VALUES (1,'THANK_YOU_LINK','v1',now()+interval '12 months')$$, 'fail');

-- ---------------------------------------------------------------------
-- G. PHỎNG VẤN (gồm luồng Yêu cầu đổi lịch và Xếp lại lịch)
-- ---------------------------------------------------------------------
SELECT pg_temp.t('G. Phỏng vấn', 'Giờ kết thúc trước giờ bắt đầu bị chặn',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,7,'2026-11-18 10:00+07','2026-11-18 09:00+07',true)$$, 'fail');
SELECT pg_temp.t('G. Phỏng vấn', 'HR mời thủ công phải ghi người tạo',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,7,'2026-11-18 09:00+07','2026-11-18 09:45+07',false)$$, 'fail');
SELECT pg_temp.t('G. Phỏng vấn', 'Người phỏng vấn bị xếp trùng giờ bị chặn',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,4,'2026-11-17 09:30+07','2026-11-17 10:15+07',true)$$, 'fail');
SELECT pg_temp.t('G. Phỏng vấn', 'Người phỏng vấn khác cùng giờ thì được',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,7,'2026-11-17 09:00+07','2026-11-17 09:45+07',true)$$, 'ok');
SELECT pg_temp.t('G. Phỏng vấn', 'Buổi đã hủy không chiếm giờ',
  $$UPDATE interviews SET status='CANCELLED' WHERE id=1;
    INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,4,'2026-11-17 09:00+07','2026-11-17 09:45+07',true)$$, 'ok');
SELECT pg_temp.t('G. Phỏng vấn', 'Một hồ sơ chỉ có một buổi đang hiệu lực',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (1,7,'2026-11-19 09:00+07','2026-11-19 09:45+07',true)$$, 'fail');
SELECT pg_temp.t('G. Đổi lịch', 'Yêu cầu đổi lịch mà không ghi chú bị chặn',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED' WHERE id=1$$, 'fail');
SELECT pg_temp.t('G. Đổi lịch', 'Ghi chú toàn khoảng trắng bị chặn',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED', reschedule_note='   ' WHERE id=1$$, 'fail');
SELECT pg_temp.t('G. Đổi lịch', 'Ghi chú quá 500 ký tự bị chặn',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED', reschedule_note=repeat('x',501) WHERE id=1$$, 'fail');
SELECT pg_temp.t('G. Đổi lịch', 'Ứng viên yêu cầu đổi lịch kèm ghi chú (link dùng, ghi nhật ký)',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED', reschedule_note='Em có lịch thi sáng thứ 3, xin dời sang chiều' WHERE id=1;
    UPDATE response_links SET used_at=now(), outcome='RESCHEDULE_REQUESTED' WHERE token_hash='h-interview-1';
    INSERT INTO audit_logs (action, target_type, target_id, after_data) VALUES ('RESCHEDULE_REQUESTED','interview',1,'{"application_id":1}')$$, 'ok');
SELECT pg_temp.t('G. Đổi lịch', 'Buổi đang chờ đổi lịch vẫn giữ giờ của người phỏng vấn',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED', reschedule_note='xin dời' WHERE id=1;
    INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,4,'2026-11-17 09:00+07','2026-11-17 09:45+07',true)$$, 'fail');
SELECT pg_temp.t('G. Xếp lại', 'HR xếp lại: đổi giờ, xóa ghi chú, hủy link cũ, cấp link mới, đưa email vào hộp thư đi',
  $$UPDATE interviews SET status='RESCHEDULE_REQUESTED', reschedule_note='xin dời sang chiều' WHERE id=1;
    UPDATE interviews SET start_at='2026-11-17 14:00+07', end_at='2026-11-17 14:45+07', status='SCHEDULED', reschedule_note=NULL WHERE id=1;
    UPDATE response_links SET invalidated_at=now() WHERE interview_id=1 AND used_at IS NULL AND invalidated_at IS NULL;
    INSERT INTO response_links (token_hash, purpose, application_id, interview_id, expires_at) VALUES ('h-interview-1b','CONFIRM_INTERVIEW',1,1,working_deadline(now(),2));
    UPDATE applications SET status='INTERVIEW_INVITED' WHERE id=1;
    INSERT INTO email_outbox (template_code, to_email, subject, body, application_id) VALUES ('RESCHEDULED','uv1@gmail.com','Lịch phỏng vấn đã thay đổi','Chào A, lịch mới: 14:00 17/11',1);
    INSERT INTO audit_logs (actor_id, action, target_type, target_id) VALUES (3,'RESCHEDULE_INTERVIEW','interview',1)$$, 'ok');
SELECT pg_temp.t('G. Xếp lại', 'Xếp lại vào giờ người phỏng vấn đã bận bị chặn',
  $$INSERT INTO interviews (application_id, interviewer_id, start_at, end_at, auto_scheduled) VALUES (2,4,'2026-11-17 14:00+07','2026-11-17 14:45+07',true);
    UPDATE interviews SET start_at='2026-11-17 14:00+07', end_at='2026-11-17 14:45+07' WHERE id=1$$, 'fail');
SELECT pg_temp.t('G. Phỏng vấn', 'Lý do từ chối chỉ có khi buổi đã hủy',
  $$UPDATE interviews SET decline_reason='Bận' WHERE id=1$$, 'fail');
SELECT pg_temp.t('G. Phỏng vấn', 'Ứng viên từ chối: buổi hủy kèm lý do',
  $$UPDATE interviews SET status='CANCELLED', decline_reason='Đã nhận việc nơi khác' WHERE id=1$$, 'ok');
SELECT pg_temp.t('G. Kết quả', 'Vắng mặt thì không có kết quả Đạt/Không đạt',
  $$INSERT INTO interview_results (interview_id, result, no_show, entered_by) VALUES (1,'PASS',true,4)$$, 'fail');
SELECT pg_temp.t('G. Kết quả', 'Có mặt thì phải có kết quả',
  $$INSERT INTO interview_results (interview_id, result, no_show, entered_by) VALUES (1,NULL,false,4)$$, 'fail');
SELECT pg_temp.t('G. Kết quả', 'Nhận xét quá 2.000 ký tự bị chặn',
  $$INSERT INTO interview_results (interview_id, result, entered_by, comment) VALUES (1,'PASS',4,repeat('x',2001))$$, 'fail');
SELECT pg_temp.t('G. Kết quả', 'Nhập kết quả Đạt kèm phiếu đánh giá',
  $$UPDATE interviews SET status='COMPLETED' WHERE id=1;
    INSERT INTO interview_results (interview_id, result, entered_by, evaluation) VALUES (1,'PASS',4,'{"Java":4,"Giao tiếp":5}')$$, 'ok');

-- ---------------------------------------------------------------------
-- H. ĐƯỜNG DẪN PHẢN HỒI
-- ---------------------------------------------------------------------
SELECT pg_temp.t('H. Link phản hồi', 'Link xác nhận lịch phải gắn buổi phỏng vấn',
  $$INSERT INTO response_links (token_hash, purpose, application_id, expires_at) VALUES ('x','CONFIRM_INTERVIEW',1,now()+interval '2 days')$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', 'Link lời mời thử việc phải gắn lời mời',
  $$INSERT INTO response_links (token_hash, purpose, application_id, interview_id, expires_at) VALUES ('x','PROBATION_OFFER',2,1,now()+interval '2 days')$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', 'Đã dùng phải có kết quả',
  $$UPDATE response_links SET used_at=now() WHERE token_hash='h-interview-1'$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', 'Link đã vô hiệu thì không dùng được',
  $$UPDATE response_links SET invalidated_at=now() WHERE token_hash='h-interview-1';
    UPDATE response_links SET used_at=now(), outcome='ACCEPTED' WHERE token_hash='h-interview-1'$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', '"Yêu cầu đổi lịch" chỉ dùng cho link lịch phỏng vấn',
  $$INSERT INTO response_links (token_hash, purpose, application_id, offer_id, expires_at, used_at, outcome) VALUES ('x','PROBATION_OFFER',2,1,now()+interval '2 days',now(),'RESCHEDULE_REQUESTED')$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', 'Mã băm link trùng bị chặn',
  $$INSERT INTO response_links (token_hash, purpose, application_id, interview_id, expires_at) VALUES ('h-interview-1','CONFIRM_INTERVIEW',1,1,now()+interval '2 days')$$, 'fail');
SELECT pg_temp.t('H. Link phản hồi', 'Quá hạn: hệ thống ghi EXPIRED (mặc định từ chối)',
  $$UPDATE response_links SET used_at=now(), outcome='EXPIRED' WHERE token_hash='h-interview-1'$$, 'ok');

-- ---------------------------------------------------------------------
-- I. THỬ VIỆC
-- ---------------------------------------------------------------------
SELECT pg_temp.t('I. Thử việc', 'Thời gian thử việc > 180 ngày bị chặn',
  $$INSERT INTO probation_offers (application_id, start_date, duration_days, location, manager_id, created_by) VALUES (1,'2026-12-01',181,'HN',5,4)$$, 'fail');
SELECT pg_temp.t('I. Thử việc', 'Một hồ sơ chỉ có một lời mời thử việc',
  $$INSERT INTO probation_offers (application_id, start_date, duration_days, location, manager_id, created_by) VALUES (2,'2026-12-01',60,'HN',5,4)$$, 'fail');
SELECT pg_temp.t('I. Thử việc', 'Nhân viên thử việc không tự quản lý mình',
  $$INSERT INTO probations (application_id, trainee_id, manager_id, department_id, start_date, end_date) VALUES (1,5,5,1,'2026-12-01','2027-01-29')$$, 'fail');
SELECT pg_temp.t('I. Thử việc', 'Ngày kết thúc trước ngày bắt đầu bị chặn',
  $$INSERT INTO probations (application_id, trainee_id, manager_id, department_id, start_date, end_date) VALUES (1,6,5,1,'2026-12-01','2026-11-01')$$, 'fail');
SELECT pg_temp.t('I. Thử việc', 'Kết luận phải ghi người và thời điểm kết luận',
  $$UPDATE probations SET status='PASSED' WHERE id=1$$, 'fail');
SELECT pg_temp.t('I. Thử việc', 'Quản lý kết luận Đạt; tài khoản chuyển Chờ Admin xử lý',
  $$UPDATE probations SET status='PASSED', concluded_by=5, concluded_at=now(), conclusion_note='Hoàn thành tốt' WHERE id=1;
    UPDATE users SET status='PENDING_ADMIN' WHERE id=6;
    UPDATE applications SET status='PROBATION_PASSED' WHERE id=2$$, 'ok');
SELECT pg_temp.t('I. Task', 'Quá 5 tệp đính kèm bị chặn',
  $$UPDATE probation_tasks SET attachments=(SELECT jsonb_agg(g) FROM generate_series(1,6) g) WHERE id=1$$, 'fail');
SELECT pg_temp.t('I. Bài nộp', 'Bài nộp phải có link hoặc file',
  $$INSERT INTO task_submissions (task_id) VALUES (2)$$, 'fail');
SELECT pg_temp.t('I. Bài nộp', 'Mỗi task chỉ có một bài nộp',
  $$INSERT INTO task_submissions (task_id, content_link) VALUES (1,'https://x')$$, 'fail');
SELECT pg_temp.t('I. Bài nộp', 'Cập nhật bài nộp mà không tăng lần nộp bị chặn',
  $$UPDATE task_submissions SET content_link='https://git.cty.vn/an/task1-v2' WHERE task_id=1$$, 'fail');
SELECT pg_temp.t('I. Bài nộp', 'Cập nhật bài nộp và tăng lần nộp',
  $$UPDATE task_submissions SET content_link='https://git.cty.vn/an/task1-v2', revision=revision+1, submitted_at=now() WHERE task_id=1$$, 'ok');
SELECT pg_temp.t('I. Bài nộp', 'Đánh giá phải ghi người và thời điểm',
  $$UPDATE task_submissions SET result='PASS' WHERE task_id=1$$, 'fail');
SELECT pg_temp.t('I. Bài nộp', 'Quản lý đánh giá Đạt',
  $$UPDATE task_submissions SET result='PASS', reviewed_by=5, reviewed_at=now(), review_comment='Tốt' WHERE task_id=1$$, 'ok');
SELECT pg_temp.t('I. Bài nộp', 'Bài đã đánh giá thì không sửa được',
  $$UPDATE task_submissions SET result='PASS', reviewed_by=5, reviewed_at=now() WHERE task_id=1;
    UPDATE task_submissions SET content_link='https://khac', revision=revision+1 WHERE task_id=1$$, 'fail');

-- ---------------------------------------------------------------------
-- J. HỘP THƯ ĐI
-- ---------------------------------------------------------------------
SELECT pg_temp.t('J. Hộp thư đi', 'Tiêu đề có ký tự xuống dòng bị chặn (chống chèn header)',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body) VALUES ('INVITE','uv1@gmail.com',E'Mời\nBcc: x@y.z','b')$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Người nhận có ký tự xuống dòng bị chặn',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body) VALUES ('INVITE',E'uv1@gmail.com\nBcc:x@y.z','s','b')$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Mẫu email không tồn tại bị chặn',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body) VALUES ('KHONG_CO','uv1@gmail.com','s','b')$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Đã gửi phải có thời điểm gửi',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body, status, attempts) VALUES ('INVITE','uv1@gmail.com','s','b','SENT',1)$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Thất bại phải ghi lỗi',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body, status, attempts) VALUES ('INVITE','uv1@gmail.com','s','b','FAILED',4)$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Quá 4 lần gửi bị chặn',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body, attempts) VALUES ('INVITE','uv1@gmail.com','s','b',5)$$, 'fail');
SELECT pg_temp.t('J. Hộp thư đi', 'Gửi thành công ở lần thử thứ 2',
  $$INSERT INTO email_outbox (template_code, to_email, subject, body, status, attempts, sent_at) VALUES ('INVITE','uv1@gmail.com','s','b','SENT',2,now())$$, 'ok');

-- ---------------------------------------------------------------------
-- K. HÀM HẠN THEO NGÀY LÀM VIỆC
-- ---------------------------------------------------------------------
SELECT pg_temp.c('K. Ngày làm việc', 'Gửi thứ Sáu 13/11 → hạn 17:30 thứ Ba 17/11 (bỏ cuối tuần)',
  $$working_deadline('2026-11-13 10:00+07', 2) = '2026-11-17 17:30+07'$$);
SELECT pg_temp.c('K. Ngày làm việc', 'Gửi thứ Hai 16/11 → hạn 17:30 thứ Tư 18/11',
  $$working_deadline('2026-11-16 08:00+07', 2) = '2026-11-18 17:30+07'$$);
SELECT pg_temp.c('K. Ngày làm việc', 'Bỏ ngày lễ 31/12: gửi 30/12 → hạn 17:30 thứ Hai 04/01',
  $$working_deadline('2026-12-30 09:00+07', 2) = '2027-01-04 17:30+07'$$);
SELECT pg_temp.c('K. Ngày làm việc', 'Hạn HR duyệt 5 ngày làm việc từ thứ Sáu 13/11 → thứ Sáu 20/11',
  $$working_deadline('2026-11-13 10:00+07', 5) = '2026-11-20 17:30+07'$$);

-- ---------------------------------------------------------------------
-- KẾT QUẢ
-- ---------------------------------------------------------------------
\set QUIET off
\pset footer off
SELECT grp AS "Nhóm", count(*) AS "Số ca", count(*) FILTER (WHERE ok) AS "Đạt"
FROM t_result GROUP BY grp ORDER BY min(no);
SELECT no, grp, name, expect, detail FROM t_result WHERE NOT ok ORDER BY no;
SELECT count(*) FILTER (WHERE ok) || '/' || count(*) AS "TỔNG ĐẠT" FROM t_result;
