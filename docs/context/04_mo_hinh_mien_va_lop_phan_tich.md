# 04. Mô hình miền và lớp phân tích

> **Bản chốt cuối 16/11/2026.** Sinh từ mã nguồn biểu đồ (28/10/2026), đã hợp nhất kết quả bước 8 (biểu đồ tuần tự) và áp đợt rút gọn 03/11 + bỏ trích dẫn 04/11: mô hình miền **25 lớp, khớp 25 bảng**; xóa HandoverItem, HandoverControl, HandoverForm, SlotProposalForm, ChangeInterviewerForm. Quy ước Astah: lớp đen trắng, biểu tượng robustness cho lớp phân tích. 16/11: đã vẽ lại toàn bộ biểu đồ mô hình miền và 11 biểu đồ lớp phân tích theo tài liệu này (Thiet_ke_he_thong_tong_hop.docx, mục 3–4); ảnh PT*.png bản 28/10 không dùng nữa.

## Mô hình miền (25 lớp thực thể, khớp 25 bảng)

Chia 4 vùng: Tài khoản, quản trị và dùng chung (Department, User, UserRole, OtpCode, AuditLog, SystemSetting, Holiday, EmailTemplate, EmailOutbox); Tin & hồ sơ (JobPosting, CriteriaSet, Criterion, JobInterviewer, Candidate, CvSubmission, Application, ApplicationScore); Phỏng vấn & phản hồi (Interview, InterviewResult, ProbationOffer, ResponseLink, TalentPoolConsent); Thử việc (Probation, ProbationTask, TaskSubmission). Mô hình miền bỏ cột kỹ thuật (id, hash, token, ip, embedding…).

Thuộc tính thay đổi so với bản 28/10:
- Interview: `proposedSlots : TimeSlot [0..2]` → `rescheduleNote : String [0..1]` (ghi chú đổi lịch, ≤ 500 ký tự; bắt buộc khi trạng thái Yêu cầu đổi lịch).
- ApplicationScore: bỏ `evidenceQuote`, `evidenceVerified`; `score` bắt buộc; giữ `aiComment`, `weightSnapshot`, `meetsMandatory`.
- User: bỏ `googleUserId`. CvSubmission: bỏ `needsHrAttention`.

Bản rút gọn để trình bày trong báo cáo: ERD tổng quan 10 đối tượng (Candidate, CvSubmission, Criterion, Application, JobPosting, ProbationOffer, Interview, Probation, ProbationTask, User); mô hình đầy đủ 25 lớp/bảng đặt ở phụ lục.

### Quan hệ giữa các lớp thực thể

| Lớp A | Loại | Lớp B | Bội số A | Bội số B | Nhãn |
|---|---|---|---|---|---|
| Department | association | User | 0..1 | 0..* | thuộc |
| User | composition | UserRole | 1 | 0..* |  |
| JobPosting | association | Department | 0..* | 1 |  |
| JobPosting | composition | CriteriaSet | 1 | 1..* | phiên bản |
| CriteriaSet | composition | Criterion | 1 | 1..* |  |
| JobPosting | association | User | 0..* | 0..* | người phỏng vấn |
| Candidate | composition | CvSubmission | 1 | 0..* |  |
| Candidate | association | Application | 1 | 0..* |  |
| JobPosting | association | Application | 1 | 0..* |  |
| Application | association | CvSubmission | 0..* | 1 |  |
| Application | association | CriteriaSet | 0..* | 1 | chấm theo |
| Application | composition | ApplicationScore | 1 | 0..* |  |
| ApplicationScore | association | Criterion | 0..* | 1 |  |
| Application | composition | Interview | 1 | 0..* |  |
| Interview | association | User | 0..* | 1 | interviewer |
| Interview | composition | InterviewResult | 1 | 0..1 |  |
| Application | composition | ProbationOffer | 1 | 0..1 |  |
| ProbationOffer | association | User | 0..* | 1 | manager |
| Application | composition | ResponseLink | 1 | 0..* |  |
| ResponseLink | association | Interview | 0..* | 0..1 |  |
| ResponseLink | association | ProbationOffer | 0..* | 0..1 |  |
| Application | association | Probation | 1 | 0..1 |  |
| Probation | association | User | 0..* | 1 | trainee |
| Probation | association | User | 0..* | 1 | manager |
| Probation | association | Department | 0..* | 1 |  |
| Probation | composition | ProbationTask | 1 | 0..* |  |
| ProbationTask | composition | TaskSubmission | 1 | 0..1 |  |
| Candidate | composition | TalentPoolConsent | 1 | 0..* |  |
| TalentPoolConsent | association | Application | 0..* | 0..1 | phát sinh từ |
| OtpCode | association | CvSubmission | 0..* | 0..1 |  |
| OtpCode | association | User | 0..* | 0..1 |  |
| OtpCode | association | JobPosting | 0..* | 0..1 | ứng tuyển vào |
| AuditLog | association | User | 0..* | 0..1 | actor |
| EmailOutbox | association | EmailTemplate | 0..* | 1 | soạn từ |
| EmailOutbox | association | Application | 0..* | 0..1 |  |
| EmailOutbox | association | User | 0..* | 0..1 |  |

JobPosting – User (người phỏng vấn) là n–n qua lớp liên kết JobInterviewer. Đã xóa 3 quan hệ của HandoverItem (03/11). Các khóa ngoại "người thực hiện" (created_by, decided_by, reviewed_by…) là tham chiếu kiểm toán, không vẽ trên mô hình miền.

## Lớp phân tích theo nhóm (BCE)

### Nhóm 1 – Quản lý tuyển dụng

Boundary: JobListScreen, JobForm, CriteriaForm, ApplicationListScreen, ApplicationDetailScreen, ReviewDecisionForm, InterviewInviteForm, RejectForm, ReportScreen (trừu tượng), FunnelReportScreen, AiScreeningReportScreen, ProbationReportScreen, ExportDialog; giao tiếp hệ thống ngoài: GoogleWorkspaceInterface, EmailServiceInterface.

| Control | Use case | Trách nhiệm |
|---|---|---|
| JobPostingControl | UC1.01–1.04 | tạo, cập nhật, đóng tin; kiểm tra BR tin |
| CriteriaControl | UC1.05 | kiểm tra tổng trọng số; tạo phiên bản bộ tiêu chí |
| ApplicationReviewControl | UC1.06–1.08, 1.10 | tra cứu, xem chi tiết (điểm + nhận xét AI từng tiêu chí); ghi quyết định, từ chối |
| InterviewInvitationControl | UC1.09 | tìm khung trống theo BR09; tạo lịch, gửi thư mời |
| ReportControl | UC1.11–1.14 | tổng hợp số liệu phễu, AI, thử việc |
| ReportExportControl | UC1.15 | xuất Excel / PDF |

Entity: JobPosting, CriteriaSet, Criterion, JobInterviewer, User, Department, Candidate, CvSubmission, Application, ApplicationScore, Interview, ResponseLink, Probation, ProbationTask, TaskSubmission, EmailTemplate, AuditLog, Holiday, InterviewResult, SystemSetting, TalentPoolConsent.

Ảnh biểu đồ: PT1a.png (Tin tuyển dụng và tiêu chí (UC1.01–1.05)), PT1b.png (Xét duyệt hồ sơ (UC1.06–1.10)), PT1c.png (Báo cáo (UC1.11–1.15)).

### Nhóm 2 – Ứng tuyển và gợi ý việc làm

Boundary: CvUploadForm, JobSuggestionScreen, JobDetailScreen, ApplyForm, OtpForm, ResponsePage (trừu tượng), ProbationOfferResponsePage, TalentConsentPage, TraineeAccountForm (Admin xem hồ sơ Chờ cấp tài khoản, nhập email công ty); giao tiếp hệ thống ngoài: AIAgentInterface, EmailServiceInterface, GoogleWorkspaceInterface (chỉ cho UC2.09).

| Control | Use case | Trách nhiệm |
|---|---|---|
| CvSubmissionControl | UC2.01, 2.02 | kiểm tra tệp (PDF/DOCX có lớp chữ), lưu CV; yêu cầu phân tích CV |
| JobSuggestionControl | UC2.03, 2.04 | lọc tin gần nhất theo độ tương đồng ngữ nghĩa rồi AI xếp hạng; lấy chi tiết vị trí |
| ApplicationSubmitControl | UC2.05 | tạo hồ sơ ứng tuyển; chống nộp trùng |
| OtpControl | UC2.06, 2.07 | sinh, gửi, kiểm tra OTP; giới hạn số lần gửi lại |
| CvScoringControl | UC2.08 | AI chấm điểm + nhận xét từng tiêu chí; kiểm tra đúng schema; tính tổng điểm bằng code; phân loại hồ sơ |
| AutoInterviewControl | UC2.09 | tự chọn giờ, tạo lịch Meet; gửi thư mời |
| ResponseControl | UC2.10 | xác thực link, ghi kết quả (chung) |
| ProbationOfferResponseControl | UC2.11 | ghi Đồng ý (→ Chờ cấp tài khoản, báo Admin) / Từ chối thử việc |
| TraineeAccountControl | UC2.12 | kiểm tra email công ty (tên miền, duy nhất); tạo tài khoản Nhân viên thử việc và đợt thử việc; gửi hướng dẫn đặt mật khẩu |
| TalentConsentControl | UC2.13 | lưu đồng ý 12 tháng |

Entity: Candidate, CvSubmission, OtpCode, JobPosting, CriteriaSet, Criterion, Application, ApplicationScore, Interview, ResponseLink, ProbationOffer, User, UserRole, Probation, TalentPoolConsent, EmailTemplate, Holiday, JobInterviewer, AuditLog.

Ảnh biểu đồ: PT2a.png (Gửi CV, gợi ý việc làm, nộp hồ sơ (UC2.01–2.09)), PT2b.png (Trao đổi thông tin qua link và cấp tài khoản (UC2.10–2.13)).

### Nhóm 3 – Phỏng vấn

Boundary: InterviewConfirmPage (Xác nhận / Yêu cầu đổi lịch kèm ghi chú / Từ chối), InterviewCalendarScreen, RescheduleForm (hiển thị ghi chú đổi lịch), CancelInterviewDialog, AssignedInterviewScreen, InterviewResultForm, ProbationOfferForm; giao tiếp hệ thống ngoài: GoogleWorkspaceInterface, EmailServiceInterface.

| Control | Use case | Trách nhiệm |
|---|---|---|
| InterviewResponseControl | UC3.01 | xác nhận / từ chối lịch; ghi yêu cầu đổi lịch kèm ghi chú, kiểm tra tối đa 2 lần (BR49, BR50); không tự đổi lịch |
| InterviewManagementControl | UC3.03–3.05 | xếp lại, hủy lịch; đồng bộ lịch Google |
| InterviewResultControl | UC3.07, 3.08 | kiểm tra quyền, lưu kết quả; gọi lời mời / thư cảm ơn |
| ProbationOfferControl | UC3.09 | kiểm tra BR53 (quản lý cùng phòng ban với tin), tạo lời mời |
| ThankYouMailControl | UC3.10 | gửi thư cảm ơn, link lưu hồ sơ |
| InterviewDeadlineJob | BR24, BR50, BR52 | quá hạn phản hồi (BR24); nhắc HR xếp lại quá 1 ngày làm việc (BR50); chuyển Chờ kết quả, nhắc nhập (BR52) |

Entity: Interview, InterviewResult, Application, Candidate, ResponseLink, ProbationOffer, User, JobPosting, JobInterviewer, Criterion, ApplicationScore, TalentPoolConsent, AuditLog, EmailTemplate, Holiday.

Ảnh biểu đồ: PT3a.png (Phản hồi lịch và quản lý lịch (UC3.01, 3.03–3.05)), PT3b.png (Kết quả phỏng vấn (UC3.07–3.10)).

### Nhóm 4 – Onboarding và thử việc

Boundary: ProbationListScreen, TaskForm, DeleteTaskDialog, SubmissionReviewForm, ProbationSummaryScreen, ConclusionForm, MyTaskScreen, SubmissionForm; giao tiếp hệ thống ngoài: EmailServiceInterface.

| Control | Use case | Trách nhiệm |
|---|---|---|
| TaskManagementControl | UC4.01–4.04 | giao, cập nhật, xóa task (BR57, BR58) |
| SubmissionReviewControl | UC4.05 | đánh giá, khóa bài nộp |
| ProbationSummaryControl | UC4.06 | tính tổng hợp kết quả |
| ProbationConclusionControl | UC4.07 | kiểm tra BR60, lưu kết luận; xử lý tài khoản (BR44) |
| TraineeTaskControl | UC4.08–4.10 | xem task, nộp, cập nhật bài |
| ProbationReminderJob | BR60, BR62 | nhắc hạn nộp, nhắc kết luận |

Entity: Probation, ProbationTask, TaskSubmission, User, AuditLog.

Ảnh biểu đồ: PT4.png (Toàn nhóm (UC4.01–4.10)).

### Nhóm 5 – Quản trị hệ thống

Boundary: AccountListScreen, EmployeeAccountForm, AccountEditForm, LockAccountDialog, DeleteAccountDialog, RoleAssignmentForm, AuditLogScreen, ExportDialog, ConfigScreen (trừu tượng), WorkingCalendarConfigScreen, EmailTemplateScreen, TimeLimitConfigScreen, AiThresholdConfigScreen, ChangePasswordForm, ForgotPasswordForm; giao tiếp hệ thống ngoài: EmailServiceInterface.

| Control | Use case | Trách nhiệm |
|---|---|---|
| AccountControl | UC5.01, 5.02, 5.04–5.06 | tạo, sửa, khóa, mở khóa, xóa tài khoản nhân viên; kiểm tra HR cuối, tự khóa (16/11: bỏ tạo Admin, đặt lại mật khẩu Admin, kiểm tra "Admin cuối") |
| RoleControl | UC5.08 | gán, gỡ vai trò; chặn gỡ vai trò HR của HR cuối cùng |
| AuditLogControl | UC5.10, 5.11 | truy vấn, xuất nhật ký |
| ConfigControl | UC5.12–5.16 | kiểm tra khoảng giá trị, lưu; quản lý mẫu email |
| PasswordControl | UC5.17, 5.18 | đổi mật khẩu bằng mật khẩu cũ; quên mật khẩu qua OTP (không áp dụng cho Admin – do hệ thống lớn xử lý) |
| OtpControl | UC2.06 (dùng lại) | sinh, kiểm tra OTP |

Entity: User, UserRole, Department, AuditLog, SystemSetting, Holiday, EmailTemplate, OtpCode.

Ảnh biểu đồ: PT5a.png (Tài khoản, phân quyền (UC5.01–5.08)), PT5b.png (Nhật ký và cấu hình (UC5.10–5.16)), PT5c.png (Mật khẩu (UC5.17–5.18)).

## Quy ước thiết kế chi tiết (đã chốt)

- Backend FastAPI phân tầng: router (APIRouter) → service → repository (SQLAlchemy 2.x AsyncSession, asyncpg) → ORM model; schema vào/ra là Pydantic v2 (*In / *Out); cấu hình qua pydantic-settings.
- Hệ thống ngoài là «subsystem» qua interface tên bắt đầu bằng I: **IGoogleWorkspace** (chỉ lịch rảnh/bận, sự kiện, Meet), **IEmailService**, **IAIAgent**.
- Phương thức ghi theo cú pháp UML `name(param: Type): ReturnType`; operation lấy từ message trong biểu đồ tuần tự (bước 8).
- Một lớp **InterviewScheduler** (core) dùng chung cho Mời phỏng vấn, Tự động mời phỏng vấn và Xếp lại lịch.
- Gửi email theo BR11 qua bảng email_outbox: dịch vụ thông báo ghi email vào outbox trong cùng giao dịch; tác vụ nền (APScheduler trong tiến trình worker) gửi và thử lại.
- Lớp chấm điểm CV không còn thao tác đối chiếu trích dẫn; tổng điểm tính bằng code.
- Phụ thuộc vòng giữa module xử lý bằng sự kiện nội bộ `core.events`; đường dẫn phản hồi hiện thực bằng lớp trừu tượng `ResponseHandler` (template method).
