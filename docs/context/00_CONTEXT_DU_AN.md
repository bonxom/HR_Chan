# 00. CONTEXT DỰ ÁN – HỆ THỐNG TUYỂN DỤNG VÀ THỬ VIỆC

> **Đọc file này trước khi làm bất cứ việc gì trong dự án.** Đây là nguồn sự thật (source of truth) cho mọi đoạn chat.
> **BẢN CHỐT CUỐI – 16/11/2026** (cập nhật cùng ngày: hệ thống con chỉ có 1 Admin, mục 4.10). Trưởng nhóm chốt toàn bộ thiết kế. Trưởng nhóm: Nguyễn Thành Vinh. Môn: Thiết kế và xây dựng phần mềm (ITSS, SoICT/HUST); quy trình theo tài liệu `quy-trinh-phat-trien-phan-mem.docx` (OOAD/RUP, 12 bước).
>
> Bộ context gồm 5 file:
> - `00_CONTEXT_DU_AN.md` – tổng quan, quyết định đã chốt, quy tắc thay đổi, trạng thái (file này)
> - `01_use_case_va_quy_tac_nghiep_vu.md` – use case, quan hệ, đặc tả rút gọn, BR01–BR62
> - `02_co_so_du_lieu.md` – bảng PostgreSQL, enum, ràng buộc, trigger, index
> - `03_glossary_va_nfr.md` – Glossary duy nhất + 42 NFR theo FURPS
> - `04_mo_hinh_mien_va_lop_phan_tich.md` – mô hình miền, lớp phân tích BCE
>
> ✅ **Bộ context 00–04 đã đồng bộ hoàn toàn** với đợt rút gọn 03/11 (mục 4.8) , quyết định bỏ trích dẫn 04/11 và quyết định 1 Admin 16/11 (mục 4.10): file 01 (61 use case, BR), 02 (25 bảng, sinh từ CSDL chạy thật), 03 (63 thuật ngữ, 42 NFR), 04 (25 lớp miền, lớp phân tích). Đây là nguồn sự thật cuối cùng. Các file gốc do nhóm giữ (.docx đặc tả, Glossary, thiết kế bước 8–12, ảnh biểu đồ, Excel danh sách UC) chưa được sửa trong các đoạn chat; nếu còn dùng, nhóm sửa theo bộ context này (danh sách điểm cần sửa ở mục 4.8 và các dấu ✎ trong file 01, 03, 04).

---

## 1. Quy tắc làm việc bắt buộc cho mọi đoạn chat

1. **Không tự ý thay đổi những gì đã chốt ở mục 4.** Một thay đổi có thể làm hỏng cả hệ thống (UC ↔ BR ↔ DB ↔ lớp đều liên kết với nhau).
2. **Trước khi đề xuất thay đổi**, phải làm phân tích ảnh hưởng: liệt kê mọi UC, BR, NFR, bảng DB, lớp, biểu đồ, tài liệu bị ảnh hưởng; trình bày cho trưởng nhóm duyệt, **chưa sửa khi chưa được đồng ý**.
3. **Khi đã được duyệt**: sửa theo thứ tự nguồn → dẫn xuất (đặc tả/BR → mô hình miền → DB → lớp → tài liệu), chạy lại kiểm tra (test DB, rà nhãn luồng), rồi **cập nhật file context này** (mục 8 Nhật ký thay đổi).
4. **Mã định danh không được dùng lại hay đánh lại**: UC giữ mã cũ; BR mới bắt đầu từ **BR63**; NFR mới từ **NFR44**. Mã đã xóa thì để trống, không tái sử dụng.
5. **Thuật ngữ** chỉ dùng đúng như Glossary (file 03, có điều chỉnh ở mục 4.8). Thuật ngữ mới phải thêm vào Glossary trước.
6. Biểu đồ vẽ theo **chuẩn Astah/UML**: không có tác nhân "Hệ thống"; biểu đồ phân rã không dùng tác nhân trừu tượng "Dịch vụ bên thứ 3" mà ghi đúng dịch vụ (Google Workspace, Dịch vụ Email, Dịch vụ AI); không thêm quan hệ không cần thiết; kiểm tra lại cú pháp RUP sau khi vẽ.
7. Đặc tả UC theo mẫu Bài tập 01 + quy trình: luồng chính / thay thế / ngoại lệ (nhãn "6a" theo bước), mỗi luồng rẽ phải ghi điểm quay lại; tiền/hậu điều kiện chỉ là trạng thái hệ thống, không nhắc UC khác; không dùng từ giao diện (nút, form, click…); có bảng Dữ liệu đầu vào / đầu ra.
8. **Thứ tự quy trình không đảo**: bước sau dùng sản phẩm bước trước (xem mục 6). Thầy đã phản biện việc làm DB trước thiết kế chi tiết; mọi bước tiếp theo phải đi đúng thứ tự.
9. Tài liệu cũ **đã lỗi thời ở các điểm mâu thuẫn** với file này: `hiring-onboarding-platform-v2 (1).md` (còn hợp đồng, Temporal, tick đi làm, kế hoạch ngày AI, MFA…), `ĐỀ XUẤT ĐỀ TÀI PROJECT III (bỏ).docx` (16 UC cũ). Khi mâu thuẫn, **file context này thắng**.
10. Khi giải thích cho trưởng nhóm, không dùng mã kiểu UC01, BR05 mà nói rõ tên chức năng / quy tắc.
11. **Quy ước trình bày báo cáo (trưởng nhóm chốt 04/11/2026):** dự án vẫn làm đầy đủ mọi phần, nhưng báo cáo **chỉ phân tích sâu luồng chính và các lớp quan trọng, phức tạp**. Chức năng phụ, lớp đơn giản/đơn lẻ, thuộc tính phụ **chỉ ghi chú bằng chữ hoặc bảng liệt kê**, không vẽ lên sơ đồ, để hình gọn và báo cáo không quá nhiều hình. Danh sách cụ thể ở mục 4.9.

---

## 2. Bài toán và phạm vi

Hệ thống web cho **một công ty**, là **hệ thống con của hệ thống quản trị nhân sự lớn hơn**, tự động hóa tuyển dụng đến hết thử việc: ứng viên gửi CV → AI phân tích, gợi ý vị trí → nộp hồ sơ (xác thực OTP) → AI chấm điểm theo tiêu chí → tự động mời phỏng vấn (điểm đạt ngưỡng) hoặc HR duyệt → phỏng vấn qua Google Meet → mời thử việc → ứng viên đồng ý → **Admin nhập email công ty, hệ thống tạo tài khoản** Nhân viên thử việc và đợt thử việc → quản lý bộ phận giao task, đánh giá, kết luận thử việc.

- Kiến trúc: backend + **AI Agent qua MCP server của công ty**, gọi dịch vụ ngoài (Email, Google Workspace Calendar/Meet, LLM).
- **Ngoài phạm vi**: ký hợp đồng lao động, điểm danh/chấm công, chatbot, rút hồ sơ, tài khoản ứng viên, kế hoạch ngày bằng AI; **(từ 03/11/2026)** tự tạo hộp thư Google, chuyển giao công việc khi khóa/gỡ vai trò, khóa khẩn cấp (vòng đời nhân viên nghỉ việc thuộc hệ thống lớn), nhận dạng chữ cho CV dạng ảnh, đổi người phỏng vấn như chức năng riêng.

---

## 3. Tác nhân và 5 nhóm chức năng

| Tác nhân | Loại | Ghi chú |
|---|---|---|
| Ứng viên | Người, chính | Không có tài khoản; phản hồi qua đường dẫn trong email |
| Bộ phận tuyển dụng | Người, chính | = vai trò **HR** + **Người phỏng vấn** |
| Quản lý bộ phận | Người, chính | Giao/đánh giá task, kết luận thử việc |
| Nhân viên thử việc | Người, chính | Email công ty do Admin nhập khi cấp tài khoản |
| Admin | Người, chính | Tài khoản loại riêng, không xem dữ liệu nghiệp vụ; cấp tài khoản thử việc |
| Dịch vụ AI | Hệ thống ngoài | LLM qua AI Agent/MCP |
| Google Workspace | Hệ thống ngoài | Lịch rảnh/bận, sự kiện + Meet (không còn tạo hộp thư) |
| Dịch vụ Email | Hệ thống ngoài | Gửi mọi email |

Biểu đồ UC **tổng quan**: tác nhân Agent/Dịch vụ AI tách riêng, các dịch vụ còn lại gộp "Dịch vụ bên thứ 3"; không có tác nhân trừu tượng "Nhân viên". Biểu đồ **phân rã**: ghi đúng từng dịch vụ.

| Nhóm | Mã UC | Số UC (sau 03/11) | File đặc tả |
|---|---|---|---|
| 1. Quản lý tuyển dụng | UC1.01–UC1.15 | 15 | Dac_ta_UC_Quan_ly_tuyen_dung.docx |
| 2. Ứng tuyển và gợi ý việc làm | UC2.01–UC2.13 | 13 | Dac_ta_UC_Ung_tuyen_goi_y_viec_lam.docx |
| 3. Phỏng vấn | UC3.01–UC3.10 (trống UC3.02, UC3.06) | 8 | Dac_ta_UC_Phong_van.docx |
| 4. Onboarding và thử việc | UC4.01–UC4.10 | 10 | Dac_ta_UC_Thu_viec.docx |
| 5. Quản trị hệ thống | UC5.01–UC5.18 (trống UC5.03, UC5.07, UC5.09) | 15 | Dac_ta_UC_Quan_tri_he_thong.docx |

Tổng **61 use case** (trước 03/11: 66; sau 03/11: 63; sau 16/11: 61). Đăng nhập là tiền điều kiện chung, không vẽ thành UC.

---

## 4. Quyết định đã chốt (KHÔNG thay đổi nếu chưa phân tích ảnh hưởng và được trưởng nhóm duyệt)

### 4.1 Ứng tuyển
- Ứng viên nhập họ tên, SĐT, email, CV (PDF/DOCX ≤ 5 MB, **có lớp chữ – không nhận dạng chữ từ ảnh**), đồng ý xử lý dữ liệu (NĐ 13/2023), CAPTCHA; **không có tài khoản**.
- Gửi CV tạo **hồ sơ tạm** → AI phân tích → gợi ý tối đa 5 vị trí kèm % phù hợp; dùng **pgvector lọc top-K rồi AI xếp hạng** (giữ nguyên sau 03/11). Không có vị trí phù hợp → đề nghị đồng ý lưu hồ sơ 12 tháng.
- Chọn vị trí → **OTP 6 số qua email** → tạo hồ sơ ứng tuyển. Không gửi email xác nhận nộp; chỉ lời cảm ơn trên màn hình.
- **Tổng điểm AI tính bằng code** theo trọng số; AI chỉ chấm từng tiêu chí (điểm 0–100 + nhận xét). **Bỏ trích dẫn bằng chứng và bước đối chiếu với CV (04/11)**; kết quả AI vẫn phải đúng cấu trúc, sai thì chuyển HR duyệt.
- Đạt ngưỡng + đạt mọi tiêu chí bắt buộc → **tự động mời phỏng vấn**; còn lại → Chờ HR duyệt. **Hệ thống không bao giờ tự từ chối** (BR08).
- **Bỏ chức năng rút hồ sơ.**

### 4.2 Thời hạn và phản hồi
- Mọi phản hồi của ứng viên (xác nhận lịch, lời mời thử việc, đồng ý lưu hồ sơ) có hạn **2 ngày làm việc** (không tính cuối tuần, ngày lễ; hết giờ làm việc ngày làm việc thứ 2); **quá hạn mặc định là từ chối** (BR23, BR24).
- Đường dẫn phản hồi: chuỗi ngẫu nhiên ≥128 bit, dùng một lần, có hạn.
- **Mọi email đi qua hộp thư đi `email_outbox`** (duyệt 29/10/2026): ghi cùng giao dịch với thao tác nghiệp vụ; tác vụ nền gửi, lỗi thì thử lại tối đa 3 lần cách 5 phút (tổng tối đa 4 lần gửi); hết lượt hoặc địa chỉ không tồn tại → FAILED, gắn cờ `email_issue` cho hồ sơ và báo Bộ phận tuyển dụng (BR11).

### 4.3 Phỏng vấn
- Thư mời có giờ + link Meet + đường dẫn xác nhận. Ứng viên: **Xác nhận / Yêu cầu đổi lịch (kèm ghi chú) / Từ chối** (sửa 03/11).
- **Yêu cầu đổi lịch** (thay "đề xuất 1–2 khung giờ"): ghi chú bắt buộc ≤ 500 ký tự (ví dụ khung giờ mong muốn); tối đa **2 lần** mỗi hồ sơ (đếm trong nhật ký); buổi chuyển "Yêu cầu đổi lịch", HR xếp lại trong 1 ngày làm việc, quá hạn nhắc HR. Hệ thống **không tự đổi lịch** (BR49, BR50 sửa nội dung).
- Buổi phỏng vấn sau hạn phản hồi ≥ 1 ngày làm việc (BR09). Không cho hai buổi trùng giờ của một người phỏng vấn (exclusion constraint).
- HR quản lý lịch: Xếp lại lịch, Hủy lịch. **Không còn chức năng Đổi người phỏng vấn**; muốn đổi người thì hủy rồi mời lại.
- Kết quả: Đạt / Không đạt / Vắng mặt (phiếu đánh giá mức 1–5 theo tiêu chí); kết quả không sửa được. Đạt → lời mời thử việc (1–180 ngày); Không đạt/vắng → thư cảm ơn kèm đề nghị lưu hồ sơ.

### 4.4 Thử việc
- Ứng viên đồng ý lời mời → hồ sơ **Chờ cấp tài khoản** (luồng chính, không còn là nhánh lỗi) → **Admin nhập email công ty** (đúng tên miền, duy nhất) → hệ thống tạo tài khoản Nhân viên thử việc + đợt thử việc, gửi hướng dẫn đặt mật khẩu lần đầu qua Quên mật khẩu → hồ sơ Đang thử việc. Hộp thư công ty do bộ phận IT/hệ thống lớn tạo bên ngoài (sửa 03/11).
- Task và bài nộp đánh giá **Đạt / Không đạt** (không chấm điểm số). UC tên "Đánh giá bài nộp".
- Kết luận thử việc Đạt/Không đạt, từ 5 ngày làm việc trước ngày kết thúc, phải đánh giá hết bài trước; Đạt → tài khoản "Chờ Admin xử lý"; Không đạt → tự khóa sau ngày kết thúc (BR44).

### 4.5 Tài khoản và quản trị
- **Admin là loại tài khoản riêng**, không có vai trò nghiệp vụ, không xem CV/điểm/kết quả (BR29). Chỉ Admin gán vai trò; nhân viên không tự chọn quyền.
- Vai trò nghiệp vụ: HR, Người phỏng vấn, Quản lý bộ phận, Nhân viên thử việc (độc lập).
- Mọi tài khoản dùng **email công ty**. Đổi mật khẩu phải nhập mật khẩu cũ; **chỉ Quên mật khẩu dùng OTP**. **(16/11) Hệ thống con có đúng 1 Admin do hệ thống nhân sự lớn cấp** – không tạo thêm Admin, không có cửa sổ đặt lại mật khẩu Admin; Admin không dùng Quên mật khẩu của hệ thống con – khôi phục mật khẩu Admin do hệ thống lớn xử lý (ngoài phạm vi); Admin vẫn Đổi mật khẩu; Admin không tự khóa, tự xóa mình – xem 4.10.
- **(sửa 03/11)** Khóa/gỡ vai trò **không kiểm tra và không chuyển giao công việc đang dở**; không có khóa khẩn cấp. Vẫn giữ: không khóa/gỡ **HR cuối cùng** đang hoạt động. Xóa tài khoản = ẩn danh hóa (chỉ tài khoản đã khóa).
- Mọi thao tác quản trị và xem hồ sơ ghi nhật ký chỉ-thêm (append-only).

### 4.5b Quyết định dữ liệu và thiết kế (chốt 30/10/2026)
- `response_links.invalidated_at`: link bị vô hiệu khi HR xếp lại lịch / gửi lời mời mới (BR51, BR55). CHECK không vừa vô hiệu vừa đã dùng; tác vụ quá hạn chỉ xét link `used_at IS NULL AND invalidated_at IS NULL` (tránh tự từ chối nhầm theo BR24).
- `job_postings`: CHECK độ dài mô tả, yêu cầu ≤ 5.000 ký tự, quyền lợi ≤ 3.000 ký tự (khớp đặc tả nhóm 1).
- `application_scores.weight_snapshot`: **giữ** làm ảnh chụp kiểm toán (điểm luôn tái lập được kể cả khi sau này bỏ ràng buộc bất biến của tiêu chí).
- Cột JSONB (attachments, evaluation, parsed_data, suggestions): **giữ**; lập luận 3NF trong Thiet_ke_buoc_8_12_ban_thu.docx (giá trị nguyên khối, không truy vấn/cập nhật từng phần). (4 cột `proposed_slot*` bỏ từ 03/11, xem 4.8.) Chỉ tách bảng nếu thầy yêu cầu 1NF chặt.
- Các cặp "Xem danh sách X + extend Tạo/Sửa/Xóa": **giữ** vì mỗi UC con mang quy tắc nghiệp vụ riêng (BR, trạng thái, nhật ký), không phải CRUD thuần.
- Mô hình miền có thêm quan hệ OtpCode – JobPosting ("ứng tuyển vào"). Các khóa ngoại "người thực hiện" (created_by, decided_by, reviewed_by…) là **tham chiếu kiểm toán**, không vẽ trên mô hình miền.
- Thiết kế: một lớp **InterviewScheduler** (core) dùng chung cho UC1.09, UC2.09, UC3.04; hệ thống ngoài qua «subsystem» thực hiện **IGoogleWorkspace, IEmailService, IAIAgent**; phụ thuộc vòng giữa module xử lý bằng sự kiện nội bộ `core.events`.
- Tác vụ định kỳ (quá hạn phản hồi, nhắc hạn, gửi outbox, khóa sau thử việc): **APScheduler** chạy trong tiến trình `worker` riêng (không chạy trong tiến trình API).
- Đặc tả UC2.03 bước 1–2: lọc sơ bộ tin gần nhất theo độ tương đồng ngữ nghĩa, rồi Dịch vụ AI xếp hạng (đặc tả không ghi tên công nghệ).

### 4.5c Quyết định sau bước 8 đợt 2 (31/10/2026, xem Thiet_ke_buoc_8_12_dot2.docx mục 5)
- `task_submissions` thêm `note` (≤1.000, UC4.09/4.10) và `revision` (1 = nộp lần đầu, >1 = đã cập nhật; quản lý đánh giá kèm revision đã xem, lệch thì báo bài đã thay – UC4.05 5a).
- `interviews.decline_reason` (≤500, UC3.01 4b); ứng viên từ chối thì buổi chuyển CANCELLED; CHECK chỉ có lý do khi CANCELLED.
- CHECK độ dài: criteria.description ≤1.000; applications.reject_reason_text ≤500; interview_results.comment ≤2.000; task_submissions.review_comment ≤2.000; probation_tasks.description ≤5.000, attachments ≤5 tệp.
- Phễu UC1.12 đếm "Gửi hồ sơ" từ `audit_logs` hành động CV_SUBMITTED (hồ sơ tạm bị xóa sau 24 giờ), không ghi dữ liệu cá nhân.
- BR42 đếm yêu cầu quên mật khẩu từ `audit_logs` PASSWORD_RESET_REQUESTED (IP + băm email), kể cả email không tồn tại.
- OTP và gửi thử mẫu email dùng `NotificationService.sendNow`: vẫn ghi email_outbox (giữ 4.2) nhưng gửi ngay, thử lại ngay 1 lần, ghi SENT/FAILED; worker không gửi lại.
- Bảo mật hộp thư đi: không giữ mã OTP/token dạng rõ trong `email_outbox.body` – thư OTP ghi body đã che; thư xếp hàng che giá trị bí mật khi chuyển SENT/FAILED.
- ~~UC3.08 kiểm tra phòng ban có Quản lý bộ phận đang hoạt động **trước** khi lưu kết luận Đạt (khớp UC3.09 ngoại lệ 1a).~~ **Bỏ 03/11** theo giả định ở 4.8C.
- Kiến trúc: OtpService đặt ở core; port `JobUsageQuery` (recruitment) và `AccountPrefillQuery` (accounts) do applications thực hiện; sự kiện `TraineeAccountCreated` (accounts → probation); recruitment được phụ thuộc accounts. UC2.10 trừu tượng hiện thực bằng lớp trừu tượng `ResponseHandler` (template method).

### 4.6 Bảo mật khi code
- Kiểm tra dữ liệu ở server; truy vấn tham số hóa/ORM; escape khi hiển thị (chống XSS); CV là dữ liệu, không phải chỉ dẫn cho AI (chống prompt injection); kiểm tra loại tệp thật + quét mã độc; chống email header injection (NFR13–NFR18).

### 4.7 Trạng thái hồ sơ (14, BR07)

| Tiếng Việt | Enum DB |
|---|---|
| Đang chấm điểm | SCORING |
| Chờ HR duyệt | PENDING_HR_REVIEW |
| Đã mời phỏng vấn | INTERVIEW_INVITED |
| Đã xác nhận lịch | INTERVIEW_CONFIRMED |
| Từ chối phỏng vấn | INTERVIEW_DECLINED |
| Chờ kết quả phỏng vấn | AWAITING_INTERVIEW_RESULT |
| Đạt phỏng vấn | INTERVIEW_PASSED |
| Không đạt phỏng vấn | INTERVIEW_FAILED |
| Đã từ chối | REJECTED |
| Chờ cấp tài khoản | AWAITING_ACCOUNT |
| Đang thử việc | ON_PROBATION |
| Từ chối thử việc | PROBATION_DECLINED |
| Đạt thử việc | PROBATION_PASSED |
| Không đạt thử việc | PROBATION_FAILED |

Từ 03/11: Đạt phỏng vấn → (đồng ý) **Chờ cấp tài khoản** → (Admin cấp) Đang thử việc. Vẫn 14 trạng thái.

### 4.8 Đợt rút gọn 03/11/2026 (trưởng nhóm duyệt; đã áp vào CSDL 13/11 và toàn bộ context 01–04 ngày 16/11)

Lý do: giảm độ phức tạp; hệ thống là hệ thống con của hệ thống nhân sự lớn (vòng đời nhân viên nghỉ việc nằm ngoài); không có môi trường Google Workspace để demo tạo hộp thư.

**A. Đề xuất giờ khác → Yêu cầu đổi lịch kèm ghi chú**
- UC: **xóa UC3.02** Đề xuất khung giờ khác (và quan hệ extend vào UC3.01). UC3.01 Xác nhận lịch: lựa chọn thứ 3 là "Yêu cầu đổi lịch" kèm ghi chú bắt buộc ≤500; buổi → RESCHEDULE_REQUESTED, link dùng với outcome RESCHEDULE_REQUESTED, báo HR; ngoại lệ "đã yêu cầu đủ 2 lần" → chỉ còn Xác nhận / Từ chối. UC3.04 Xếp lại lịch: bỏ "ưu tiên khung ứng viên đề xuất" và "chọn đúng khung đề xuất thì chuyển thẳng Đã xác nhận"; HR xem ghi chú, chọn giờ, gửi link mới.
- BR: **BR49 sửa** → "Ứng viên có thể yêu cầu đổi lịch kèm ghi chú bắt buộc tối đa 500 ký tự; mỗi hồ sơ tối đa 2 lần (đếm trong nhật ký)". **BR50 sửa** → "Yêu cầu đổi lịch chuyển buổi sang Yêu cầu đổi lịch; HR phải xếp lại trong 1 ngày làm việc, quá hạn hệ thống nhắc HR. Hệ thống không tự đổi lịch." BR48 sửa chữ "đề xuất lại" → "yêu cầu đổi lịch".
- DB `interviews`: bỏ 4 cột `proposed_slot1_start/end`, `proposed_slot2_start/end` và CHECK check2–check6; thêm `reschedule_note varchar(500)`; CHECK check7 đổi thành `status <> 'RESCHEDULE_REQUESTED' OR reschedule_note IS NOT NULL`. Giữ enum `RESCHEDULE_REQUESTED` (interview_status, link_outcome), exclusion constraint và index `interviews_one_active`.
- NFR34, NFR37: bỏ UC3.02 khỏi danh sách. Glossary: "Khung giờ đề xuất" → **"Ghi chú đổi lịch"**; sửa định nghĩa "Yêu cầu đổi lịch" (ứng viên yêu cầu kèm ghi chú, chờ HR xếp lại).
- Mô hình miền Interview: `proposedSlots : TimeSlot [0..2]` → `rescheduleNote`. Lớp phân tích: bỏ SlotProposalForm; InterviewResponseControl chỉ ghi yêu cầu, không tự đổi lịch.

**B. Bỏ tự tạo hộp thư Google; Admin nhập email công ty, hệ thống tạo tài khoản**
- UC2.12 Cấp tài khoản thử việc (giữ mã, giữ ở nhóm 2): tác nhân **Admin (chính), Dịch vụ Email (phụ)**; bỏ Google Workspace. Tiền điều kiện: hồ sơ Chờ cấp tài khoản. Luồng: Admin xem danh sách hồ sơ Chờ cấp tài khoản (họ tên, vị trí, phòng ban, ngày bắt đầu – không có CV/điểm, khớp BR29) → nhập email công ty → kiểm tra tên miền, duy nhất (BR39) → tạo tài khoản PROBATION + đợt thử việc → gửi hướng dẫn đặt mật khẩu lần đầu qua Quên mật khẩu → hồ sơ Đang thử việc, báo HR và quản lý. **Bỏ quan hệ extend UC2.12 → UC2.11.**
- UC2.11 Phản hồi lời mời thử việc: hậu điều kiện → hồ sơ Chờ cấp tài khoản (hoặc Từ chối thử việc); báo Admin.
- BR30 sửa: "Vai trò Nhân viên thử việc chỉ được cấp qua chức năng Cấp tài khoản thử việc cho hồ sơ Chờ cấp tài khoản; Admin chỉ gỡ vai trò này sau khi có kết luận thử việc." BR56 sửa: đợt thử việc tạo khi Admin cấp tài khoản.
- NFR22: bỏ "mật khẩu tạm của hộp thư buộc đổi ở lần đăng nhập đầu". NFR29: bỏ "tài khoản dịch vụ tạo hộp thư chỉ có quyền tạo người dùng" (giữ phần 2FA email Admin).
- DB: bỏ cột `users.google_user_id`. IGoogleWorkspace bỏ thao tác tạo người dùng (chỉ còn lịch rảnh/bận, sự kiện, Meet). Glossary sửa: Google Workspace, Hộp thư công ty, Nhân viên thử việc, Chờ cấp tài khoản.
- Rủi ro chấp nhận: Admin cấp chậm làm nhân viên mất ngày thử việc (ngày kết thúc tính cứng) – nên có nhắc Admin (đề xuất dùng tác vụ nhắc sẵn có, cần duyệt nếu thêm BR).

**C. Bỏ toàn bộ chuyển giao công việc và khóa khẩn cấp**
- UC: **xóa UC5.09** Chuyển giao công việc (và 2 quan hệ extend từ UC5.05, UC5.08). UC5.05 Khóa/mở khóa: bỏ điểm mở rộng "Kiểm tra công việc đang dở" và nhánh khóa khẩn cấp. UC5.08 Phân quyền: bỏ điểm mở rộng, bỏ hậu điều kiện "công việc dở đã chuyển giao". UC5.06 Xóa tài khoản: bỏ điều kiện "không còn công việc Chờ chuyển giao". Bộ phận tuyển dụng không còn liên kết tới nhóm Quản trị (trừ Đổi/Quên mật khẩu).
- BR: **BR32 sửa** → "Không được khóa hoặc gỡ vai trò HR của HR cuối cùng đang hoạt động. Khóa/gỡ vai trò không kiểm tra công việc đang dở." **Xóa BR33, BR34, BR35** (để trống). BR36 bỏ câu "công việc đã chuyển giao không tự quay về". BR37 bỏ điều kiện "không còn công việc Chờ chuyển giao". BR38 bỏ trường "công việc chuyển giao" trong biên bản. BR56 bỏ câu "khi quản lý bị khóa… chuyển giao theo BR32–BR35".
- DB: **xóa bảng `handover_items`**, enum `handover_status`, `handover_type`; bỏ 'EMERGENCY_LOCK' khỏi CHECK `audit_logs_check`. **26 → 25 bảng.**
- Glossary xóa: Công việc đang dở, Người nhận hợp lệ, Khóa khẩn cấp, Chờ chuyển giao. Mô hình miền xóa HandoverItem + 3 quan hệ (**25 lớp**). Lớp phân tích xóa HandoverControl, HandoverForm; nhóm 5 bỏ GoogleWorkspaceInterface và entity HandoverItem, Interview, Application.
- **Giả định phạm vi (duyệt 03/11 tối):** Người phỏng vấn và Quản lý bộ phận **luôn hoạt động bình thường** trong suốt quy trình; hệ thống **không xử lý** trường hợp họ bị khóa hoặc mất vai trò giữa chừng (thuộc hệ thống nhân sự lớn). Dự án tập trung vào luồng chính.
- Hệ quả khi sửa đặc tả: bỏ các luồng ngoại lệ chỉ phục vụ trường hợp "người phỏng vấn / quản lý không còn hoạt động / chờ chuyển giao" (ví dụ dấu "người phỏng vấn chờ chuyển giao" trên lịch, "người nhận vừa bị khóa"). Giữ các kiểm tra quyền thông thường (đúng vai trò, đúng buổi được giao, đúng đợt phụ trách).
- Bỏ thêm (duyệt 03/11 tối): bước kiểm tra phòng ban còn Quản lý bộ phận đang hoạt động trước khi lưu kết quả phỏng vấn Đạt (UC3.08) và ngoại lệ 1a tương ứng của Gửi lời mời thử việc (UC3.09). BR53 sửa: quản lý phụ trách chỉ cần cùng phòng ban với tin (bỏ "đang hoạt động").

**D. Bỏ nhận dạng chữ cho CV dạng ảnh**
- UC2.01, UC2.02: bỏ luồng thay thế "CV là ảnh scan"; CV không trích được chữ → báo "CV không đọc được", ứng viên gửi lại. Glossary xóa OCR.
- DB: bỏ cột `cv_submissions.needs_hr_attention`; giữ `parse_status` PARTIAL (CV có chữ vẫn có thể trích một phần). **pgvector giữ nguyên.**

**E. Bỏ Đổi người phỏng vấn**
- UC: **xóa UC3.06** (và extend vào UC3.03). Đổi người = Hủy lịch rồi mời lại. Thao tác đổi người trong lớp thiết kế cũng xóa (không còn chuyển giao dùng tới).
- NFR34 bỏ "đổi người"; lớp phân tích bỏ ChangeInterviewerForm; InterviewManagementControl chỉ còn xếp lại, hủy.

**Tổng ảnh hưởng:** 66 → **63 UC**; 26 → **25 bảng / 25 lớp miền**; BR: sửa BR30, BR32, BR36, BR37, BR38, BR48, BR49, BR50, BR53, BR56; xóa BR33–BR35; Glossary 70 → 65 thuật ngữ (còn 64 sau khi bỏ "Trích dẫn bằng chứng" 04/11); NFR sửa NFR22, NFR29, NFR34, NFR37; biểu đồ tuần tự 36 → 33 (xóa UC3.02, UC3.06, UC5.09; vẽ lại UC2.12; sửa UC2.11, UC3.01, UC3.04, UC3.08, UC3.09, UC5.05, UC5.08, UC2.01/UC2.02); biểu đồ UC: tổng quan rà lại, phân rã nhóm 2, 3, 5 vẽ lại; biểu đồ trạng thái Buổi phỏng vấn, Hồ sơ; biểu đồ lớp chi tiết bỏ các lát chuyển giao, đổi người, đề xuất khung.

**Thứ tự áp dụng (4.8):** đặc tả 5 file .docx → mô hình miền → schema_25.sql + test → lớp phân tích → biểu đồ tuần tự → kiến trúc/lớp chi tiết/trạng thái → biểu đồ UC + Danh sách UC → sinh lại file 01–04 → cập nhật nhật ký. **Trạng thái 16/11:** CSDL (13/11) và context 01–04 (16/11) đã áp; vì file .docx gốc không có trong các đoạn chat, context được sửa trực tiếp và trở thành nguồn để nhóm sửa file gốc.

### 4.9 Phạm vi trình bày trong báo cáo (quy ước 04/11/2026; danh sách là đề xuất, trưởng nhóm có thể điều chỉnh)

Dự án (đặc tả, CSDL, thiết kế, code) vẫn làm đầy đủ 61 UC / 25 bảng. Chỉ **cách trình bày trong báo cáo** được rút gọn.

**Luồng chính – phân tích sâu (đặc tả đầy đủ, biểu đồ tuần tự, lớp chi tiết):**
Tạo tin tuyển dụng kèm tiêu chí → Gửi hồ sơ và Phân tích CV → Gợi ý việc làm AI → Nộp hồ sơ (kèm Xác thực OTP) → Chấm điểm CV → Tự động mời phỏng vấn / Xét duyệt hồ sơ + Mời phỏng vấn → Xác nhận lịch phỏng vấn (kèm yêu cầu đổi lịch) → Nhập kết quả phỏng vấn + Gửi lời mời thử việc → Phản hồi lời mời thử việc → Cấp tài khoản thử việc → Giao task → Nộp bài → Đánh giá bài nộp → Kết luận thử việc.

**Chức năng phụ – chỉ bảng liệt kê (tên, tác nhân, mô tả 1 dòng):** xem danh sách tin/hồ sơ/lịch/task, cập nhật/đóng tin, xem chi tiết hồ sơ, từ chối hồ sơ, gửi thư cảm ơn, báo cáo thống kê và xuất báo cáo, xếp lại/hủy lịch, xem hồ sơ được giao, gửi lại OTP, đồng ý lưu hồ sơ, xem chi tiết vị trí, cập nhật/xóa task, cập nhật bài nộp, xem tổng hợp thử việc, toàn bộ nhóm Quản trị hệ thống (tài khoản, phân quyền, nhật ký, cấu hình, mẫu email, mật khẩu).

**Lớp quan trọng – vẽ và mô tả chi tiết:** Application, Interview, CvSubmission, JobPosting + Criterion, Probation + ProbationTask; control/service: chấm điểm CV (AI chấm điểm + nhận xét từng tiêu chí, tổng điểm bằng code), gợi ý việc làm, InterviewScheduler (dùng chung cho mời tự động, HR mời, xếp lại), ResponseHandler (đường dẫn phản hồi, quá hạn = từ chối), cấp tài khoản thử việc, kết luận thử việc; 3 subsystem IAIAgent, IGoogleWorkspace, IEmailService.
**Lớp phụ – chỉ ghi chú/bảng:** Department, UserRole, OtpCode, AuditLog, SystemSetting, Holiday, EmailTemplate, EmailOutbox, TalentPoolConsent, ResponseLink, InterviewResult, TaskSubmission, CriteriaSet, ApplicationScore; các boundary danh sách/form đơn giản.

**Sơ đồ dự kiến trong báo cáo:**
- Use case: 1 biểu đồ tổng quan + 1 biểu đồ phân rã luồng chính; chức năng phụ ở bảng.
- Mô hình miền / ERD: bản rút gọn 10 đối tượng (ERD_tong_quan_rut_gon); ghi chú dưới hình: "mô hình đầy đủ 25 lớp/bảng ở phụ lục".
- Biểu đồ tuần tự: chỉ các UC luồng chính phức tạp (khoảng 9); còn lại ghi "theo mẫu chuẩn".
- Biểu đồ trạng thái: Hồ sơ ứng tuyển (14 trạng thái) và Buổi phỏng vấn.
- CSDL: ERD rút gọn + bảng liệt kê 25 bảng (tên, mục đích 1 dòng); DDL đầy đủ ở phụ lục.
- Thuộc tính phụ (id, thời điểm tạo/sửa, version, cột kỹ thuật) không vẽ, ghi chú chung một lần.

### 4.10 Quyết định 16/11/2026: hệ thống con chỉ có 1 Admin (trưởng nhóm duyệt)

Tài khoản Admin thuộc hệ thống nhân sự lớn ở bên trên. Hệ thống con có **đúng 1 tài khoản Admin**, do hệ thống lớn cấp khi triển khai; hệ thống con không tạo thêm Admin và không có cơ chế đặt lại mật khẩu riêng cho Admin. Quyết định đưa ra hai bước trong ngày: (1) bỏ quy tắc "luôn còn ≥ 2 Admin"; (2) bỏ luôn tạo Admin, đặt lại mật khẩu Admin và thủ tục khôi phục Admin.

- **Xóa:** UC5.03 Tạo tài khoản Admin, UC5.07 Đặt lại mật khẩu Admin (và 2 «extend» vào UC5.01) → **61 use case**; BR43 (cửa sổ 30 phút, 72 giờ đầu); NFR32 (thủ tục khôi phục Admin) → **42 NFR**; thuật ngữ "Cửa sổ đặt lại" → **63 thuật ngữ**; boundary AdminAccountForm, AdminResetWindowDialog.
- **Sửa:** BR31 (đúng 1 Admin do hệ thống lớn cấp; Admin không tự khóa, tự xóa mình; bỏ "≥ 2 Admin" và cảnh báo 1 Admin); BR38 (bỏ lý do bắt buộc cho tạo / đặt lại mật khẩu Admin); UC5.18 Quên mật khẩu: bỏ Admin khỏi tác nhân – khôi phục mật khẩu Admin do hệ thống lớn xử lý, ngoài phạm vi dự án; BR42 không gửi OTP cho tài khoản Admin; AccountControl chỉ quản lý tài khoản nhân viên; NFR29 gắn với Đổi mật khẩu.
- **CSDL:** xóa trigger users_min_two_admins (còn 8 trigger); bảng users bỏ 3 cột reset_opened_by, reset_window_expires_at, first_password_deadline và 3 CHECK đi kèm (users còn 18 cột); thêm chỉ mục duy nhất users_one_admin (tối đa 1 Admin chưa xóa); CHECK lý do của audit_logs bỏ CREATE_ADMIN, RESET_ADMIN_PASSWORD. Còn 25 bảng, 241 cột, 51 khóa ngoại, 63 CHECK; test_25.sql **130/130**.
- **Giữ:** Admin vẫn cấp tài khoản thử việc, tạo / sửa / khóa / xóa tài khoản nhân viên, phân quyền, nhật ký, cấu hình; không khóa HR cuối cùng (BR32); Admin không xem dữ liệu nghiệp vụ (BR29).
- **Ngoài phạm vi:** mọi việc khôi phục mật khẩu, khóa hay cấp lại tài khoản Admin do hệ thống nhân sự lớn quyết định (trưởng nhóm chốt 16/11). Admin chỉ dùng Đổi mật khẩu trong hệ thống con.
- **Đã cập nhật:** file 00, 01, 02 (sinh lại), 03, 04; schema_25.sql, test_25.sql, ERD nhóm 1; báo cáo CSDL trên Claude Docs. File .docx gốc của nhóm (đặc tả nhóm 5, Glossary, ảnh PT5a, ảnh phân rã UC nhóm 5) cần sửa theo nếu còn dùng.

---

## 5. Công nghệ (đã chốt)

- Backend: Python 3.12+, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x async, asyncpg, Alembic.
- CSDL: PostgreSQL 16 + pgvector (Docker Compose). Chọn PostgreSQL thay MongoDB vì dữ liệu quan hệ chặt, cần ràng buộc/transaction.
- Frontend: Node.js 22.12+, npm, React, TypeScript, Vite, React Router, TanStack Query.
- Kiểm thử/chất lượng: pytest, HTTPX, Ruff.
- Tác vụ định kỳ: APScheduler trong tiến trình worker (chốt 30/10/2026).
- Chưa chốt: số chiều embedding (đang đặt 1536, phải bằng model embedding được chọn).

---

## 6. Trạng thái theo quy trình 12 bước

| Bước | Sản phẩm | Trạng thái |
|---|---|---|
| 1. Mô tả yêu cầu | Báo cáo đề xuất (De_xuat_de_tai.docx) | Có; chưa có phần yêu cầu thẩm định (tiêu chí nghiệm thu); phạm vi theo mục 2 file này |
| 2–4. Actor, UC, biểu đồ UC | Danh sách chuẩn: file 01 (61 UC); biểu đồ tổng quan + 5 phân rã vẽ lại khớp file 01 (16/11, Thiet_ke_he_thong_tong_hop.docx mục 2) | **Chốt.** Danh_sach_UC.xlsx của nhóm cần khớp file 01 |
| 5. Đặc tả UC | Bản rút gọn chuẩn: file 01 (✎ = use case có sửa); 5 file Dac_ta_UC_*.docx của nhóm | **Chốt** theo file 01 |
| 6. Glossary + Supplementary Spec | File 03 (63 thuật ngữ, 42 NFR FURPS) | **Chốt** |
| 7. Lớp phân tích | File 04 (BCE theo 5 nhóm); 11 biểu đồ vẽ lại theo file 04 (16/11, tài liệu tổng hợp mục 4); mô hình miền 25 lớp + bản luồng chính (mục 3) | **Chốt** |
| 8. Biểu đồ tuần tự + hợp nhất lớp phân tích | 16 biểu đồ tuần tự luồng chính kiểu Astah (4 tiêu biểu + 12 vẽ 16/11; tài liệu tổng hợp mục 6, bảng truy vết mục 9); 33 biểu đồ của nhóm bản 29–31/10 không dùng nữa | **Chốt** |
| 9. Kiến trúc (SAD, package, subsystem «I…») | Phân tầng + 8 module, sự kiện nội bộ, 3 subsystem IGoogleWorkspace, IEmailService, IAIAgent (file 04, mục quy ước) | **Chốt** |
| 10. Thiết kế giao diện (STD, wireframe, screen spec) | Bản thử: quy chuẩn GUI, 5 sơ đồ chuyển màn hình, đặc tả 3 interface | Bản thử; chưa có wireframe, screen spec |
| 11. Lớp chi tiết + State machine | Biểu đồ lớp thiết kế + lớp chi tiết 4 use case tiêu biểu (Thiet_ke_4_UC_tieu_bieu.docx); 2 biểu đồ trạng thái Hồ sơ ứng tuyển, Buổi phỏng vấn vẽ lại theo BR 16/11 (tài liệu tổng hợp mục 5) | **Chốt 16/11** (trưởng nhóm) |
| 12. CSDL | schema_25.sql (25 bảng), test_25.sql 130/130, ERD IE 5 ảnh, file 02, báo cáo CSDL trên Claude Docs | **Chốt 16/11**, gồm các bổ sung 13/11 (mục 8) |

Mô hình miền (25 lớp, file 04) đã vẽ để trả lời phản biện "vì sao có 25 bảng": đặc tả → mô hình miền → ánh xạ lớp → bảng.

---

## 7. Vấn đề mở

**Đã giải quyết 30/10/2026** (trưởng nhóm giao quyết định, chi tiết ở 4.5b): #1 email_outbox (29/10); #2 CHECK độ dài; #3 InterviewScheduler; #4 interface I…; #5, #14 giữ JSONB/proposed_slot* có lập luận 3NF (proposed_slot* bỏ 03/11); #6 giữ cặp Xem danh sách + extend; #8 (phần tác vụ định kỳ) APScheduler; #10 invalidated_at; #11 câu chữ UC2.03; #12 giữ weight_snapshot; #13 quan hệ OtpCode – JobPosting.

**Bản chốt 16/11: không còn vấn đề mở về quyết định thiết kế.** Ghi nhận còn lại, không làm thay đổi thiết kế đã chốt:
1. Số chiều embedding giữ 1536; nếu chọn model embedding khác thì chỉ sửa `vector(n)` và index HNSW.
2. Bước 1 chưa có phần yêu cầu thẩm định (tiêu chí nghiệm thu); bước 10 chưa có wireframe và screen specification.
3. File gốc của nhóm (.docx đặc tả, Glossary, thiết kế bước 8–12, Danh_sach_UC.xlsx, DBML) chưa được sửa trong đoạn chat; nếu dùng, sửa theo context này. Ảnh use case, lớp phân tích, trạng thái, tuần tự cũ của nhóm được thay bằng bộ vẽ lại 16/11 trong Thiet_ke_he_thong_tong_hop.docx.
4. Không thêm nhắc Admin khi hồ sơ ở Chờ cấp tài khoản quá lâu (không thêm BR mới); rủi ro đã ghi ở 4.8B.
5. Thân các trigger trong schema_25.sql được viết lại từ mô tả (bản gốc 31/10 không có trong Project); còn 8 trigger sau khi bỏ trigger kiểm tra 2 Admin (16/11); đã kiểm thử 130/130.

---

## 8. Nhật ký thay đổi lớn

- 15–19/10: chốt bài toán sau tư vấn chuyên gia; bỏ hợp đồng, chấm công, chatbot; 5 nhóm chức năng.
- 21–22/10: đặc tả nhóm 1, 2, 5; bỏ rút hồ sơ; hạn phản hồi 2 ngày làm việc.
- 22–26/10: DB 34 bảng → rút gọn 25 bảng; DBML; báo cáo DB.
- 27/10: đặc tả nhóm 3, 4 (BR48–BR62, NFR34–NFR43); biểu đồ lớp nháp; chốt stack Python/FastAPI; thêm pgvector (embedding ở cv_submissions, job_postings, index HNSW).
- 28/10: bảo vệ – thầy phản biện DB có trước thiết kế; vẽ mô hình miền + lớp phân tích kiểu Astah; sửa bước 5 (66 đặc tả) và bước 6 (Glossary + Supplementary Spec chung). Biểu đồ UC **không đổi**.
- 29/10: **duyệt thêm bảng `email_outbox`** (BR11). Ảnh hưởng đã xử lý: schema (bảng + enum email_status + 2 index + CHECK chống header injection NFR18), test 58/58, DBML, mô hình miền (lớp EmailOutbox, MH0/MH1 – 26 lớp), Glossary (+"Hộp thư đi"), context 02/03/04. Không đổi: UC, BR, NFR, biểu đồ UC, lớp phân tích. Còn lại: cập nhật báo cáo DB (Claude Docs).
- 29/10 (tối): **bản thử bước 8–12** (Thiet_ke_buoc_8_12_ban_thu.docx): 11 biểu đồ tuần tự, hợp nhất 16 liên kết vào lớp phân tích, kiến trúc package, 5 sơ đồ chuyển màn hình, 6 biểu đồ trạng thái, 5 biểu đồ lớp thiết kế, ERD IE 26 bảng, lập luận 3NF. Không đổi UC/BR/NFR/DB; phát hiện mới ghi ở vấn đề mở 10–14.
- 30/10: **giải quyết vấn đề mở** (trưởng nhóm giao quyết định). Đổi: schema (`response_links.invalidated_at` + CHECK + index quá hạn; CHECK độ dài job_postings), test 62/62, DBML, ERD, biểu đồ trạng thái ResponseLink; đặc tả UC2.03 bước 1–2; mô hình miền + quan hệ OtpCode – JobPosting (MH0, MH1, bản Astah). Chốt: InterviewScheduler, interface I…, core.events, APScheduler/worker, giữ weight_snapshot/JSONB/proposed_slot*, giữ cặp Xem danh sách + extend. Không đổi: danh sách UC, BR, NFR, biểu đồ UC, Glossary.
- 31/10: **bước 8 đợt 2** – 25 biểu đồ tuần tự UC Trung bình (S12–S36), hợp nhất 44 liên kết vào lớp phân tích, 11 biểu đồ lớp thiết kế phủ 8 module, cập nhật kiến trúc (OTP về core, 2 port, sự kiện TraineeAccountCreated, ResponseHandler). Đối chiếu DB: thêm task_submissions.note, revision; interviews.decline_reason; CHECK độ dài 6 trường; test 73/73; DBML, ERD, mô hình miền (TaskSubmission, Interview). Quyết định thiết kế ghi ở 4.5c. Không đổi: danh sách UC, BR, NFR, đặc tả, biểu đồ UC, Glossary, số bảng (26).
- 31/10 (chiều): **biểu đồ lớp chi tiết chia nhỏ** – 37 biểu đồ (Bieu_do_lop_chi_tiet.docx) sinh từ cùng dữ liệu với 11 biểu đồ module; thêm kiểu liệt kê tầng ứng dụng (Decision, RejectReason, Classification, LockKind, FunnelStep); operation truy vấn mức lớp ghi static. Không đổi UC, BR, NFR, DB.
- 03/11: **trưởng nhóm duyệt đợt rút gọn** (phân tích từ tài liệu Luong_he_thong_tu_dau_den_cuoi.docx, phần 4): (A) đề xuất khung giờ → yêu cầu đổi lịch kèm ghi chú, tối đa 2 lần, HR xếp lại; (B) bỏ tự tạo hộp thư Google, Admin nhập email công ty và hệ thống tạo tài khoản thử việc; (C) bỏ chuyển giao công việc và khóa khẩn cấp (hệ thống con của hệ thống nhân sự lớn); giả định Người phỏng vấn và Quản lý bộ phận luôn hoạt động, không xử lý trường hợp họ bị khóa giữa chừng – tập trung luồng chính; bỏ kiểm tra quản lý đang hoạt động khi lưu kết quả Đạt và khi gửi lời mời thử việc; (D) bỏ nhận dạng chữ CV ảnh, giữ pgvector; (E) bỏ Đổi người phỏng vấn. Chi tiết ở 4.8. **Trạng thái: mới ghi vào file 00; chưa áp dụng vào file gốc và file 01–04** (vấn đề mở #7). Tối 03/11: thêm giả định người phỏng vấn/quản lý luôn hoạt động; bỏ kiểm tra quản lý đang hoạt động khi lưu kết quả Đạt.
- 04/11: **chốt quy ước trình bày báo cáo** (quy tắc 11, mục 4.9): làm đầy đủ nhưng báo cáo chỉ phân tích sâu luồng chính và lớp quan trọng; phụ thì ghi chú/bảng. Vẽ ERD tổng quan rút gọn 10 đối tượng (ERD_tong_quan_rut_gon.png/.svg). Không đổi UC, BR, DB.
- 04/11 (sáng): **chốt 4 use case tiêu biểu cho báo cáo tiến độ** (mỗi chủ đề một use case lá): Thiết lập tiêu chí chấm điểm (sắp xếp người phỏng vấn), Chấm điểm CV (lọc CV), Tự động mời phỏng vấn (mời phỏng vấn), Xếp lại lịch phỏng vấn (quản lý lịch). Bản nháp thiết kế: Thiet_ke_4_UC_tieu_bieu.docx (4 biểu đồ tuần tự, lớp thiết kế, 4 lớp chi tiết, trích xuất CSDL). Báo cáo mẫu (Claude Docs) để dành cho báo cáo cuối, chưa sửa.
- 04/11 (chiều): **trưởng nhóm bỏ trích dẫn bằng chứng của AI** – AI chỉ chấm điểm + nhận xét từng tiêu chí, không đối chiếu trích dẫn với CV. Ảnh hưởng (chưa áp vào file gốc): đặc tả Chấm điểm CV (bỏ bước đối chiếu và ngoại lệ trích dẫn), Xem chi tiết hồ sơ và giải trình điểm AI, Xem hồ sơ ứng viên được giao (bỏ hiển thị trích dẫn); NFR09 (bỏ "trích dẫn từ CV"), NFR16 (giữ "đúng schema", bỏ "trích dẫn kiểm chứng được"); Glossary xóa "Trích dẫn bằng chứng", sửa "Giải trình điểm AI" = điểm + nhận xét từng tiêu chí; DB application_scores bỏ evidence_quote, evidence_verified, score NOT NULL; lớp CvScoringService bỏ verifyEvidence. Đã cập nhật: Thiet_ke_4_UC_tieu_bieu.docx, slide Lọc CV.
- 13/11: **thiết kế lại CSDL theo 4.8 + bỏ trích dẫn** (trưởng nhóm giao "thiết kế nốt CSDL"; làm trước khi sửa đặc tả – lệch thứ tự ở cuối 4.8, CSDL vẫn chỉ chốt sau bước 11). Dựng lại schema_25.sql từ file 02 (file gốc không có trong Project): **25 bảng, 16 enum, 52 FK, 66 CHECK, 1 EXCLUDE, 9 trigger + working_deadline**; chạy thật trên PostgreSQL 16.15 + pgvector 0.8.0; test_25.sql **131/131** (88 ca vi phạm đều bị chặn đúng ràng buộc). Thay đổi theo quyết định đã duyệt: interviews bỏ proposed_slot* + 5 CHECK, thêm reschedule_note; xóa handover_items + 2 enum; audit_logs bỏ EMERGENCY_LOCK; users bỏ google_user_id; cv_submissions bỏ needs_hr_attention; application_scores bỏ evidence_quote, evidence_verified, score NOT NULL. **Bổ sung chờ duyệt** (không đổi quyết định): CHECK outcome RESCHEDULE_REQUESTED chỉ với link CONFIRM_INTERVIEW; reschedule_note không toàn khoảng trắng; trigger bài nộp phải tăng revision khi cập nhật; CHECK weight_snapshot 0–100, version_no ≥ 1; index probation_tasks; đổi tên ràng buộc checkN → tên có nghĩa; seed 8 tham số (thêm reschedule_handle_days = 1, max_reschedule_requests = 2). ERD IE 5 ảnh (tổng thể + 4 nhóm), sinh lại file 02, viết lại báo cáo DB trên Claude Docs. Không đổi: UC, BR, NFR, Glossary, đặc tả, lớp.
- 16/11: **trưởng nhóm chốt toàn bộ thiết kế, không thay đổi thêm.** Đồng bộ context 01 (đánh dấu ✎ 14 use case có sửa; xóa UC3.02, UC3.06, UC5.09 và 5 quan hệ đi kèm; sửa BR30, BR32, BR36–BR38, BR48–BR50, BR53, BR56; BR33–BR35 để trống), 03 (Glossary 64 thuật ngữ; sửa NFR09, NFR16, NFR22, NFR29, NFR34, NFR37), 04 (25 lớp miền; bỏ lớp và quan hệ chuyển giao, SlotProposalForm, ChangeInterviewerForm; thêm TraineeAccountForm cho Admin; quy ước thiết kế chuyển sang đã chốt). Chấp nhận các bổ sung CSDL 13/11. Sửa biểu đồ tuần tự Thiết lập tiêu chí: `findActiveByRole` → `findByRole` (khớp giả định người phỏng vấn luôn hoạt động). Đóng gói bộ tài liệu cuối (mục 9).
- 16/11 (sau khi chốt): **trưởng nhóm bỏ quy tắc "luôn còn ≥ 2 Admin hoạt động"** vì Admin thuộc hệ thống lớn; chọn phạm vi tối thiểu (giữ Tạo tài khoản Admin, Đặt lại mật khẩu Admin). Sửa BR31 (file 01), AccountControl (file 04), mục 4.5, thêm mục 4.10; CSDL xóa trigger users_min_two_admins (còn 8 trigger), test 131/131 (thay 2 ca 2 Admin bằng 1 ca kiểm tra cấu trúc + 1 ca khóa được Admin khi chỉ còn 1); sinh lại file 02; sửa báo cáo CSDL trên Claude Docs; đóng gói lại.
- 16/11 (tiếp): **trưởng nhóm quyết định hệ thống con chỉ có 1 Admin** (do hệ thống lớn cấp): xóa UC5.03, UC5.07 (61 UC), BR43, NFR32 (42 NFR), thuật ngữ Cửa sổ đặt lại (63 thuật ngữ); sửa BR31, BR38, UC5.18, NFR29, AccountControl; CSDL bỏ 3 cột Admin ở users + 3 CHECK, thêm chỉ mục users_one_admin, CHECK lý do bỏ CREATE_ADMIN/RESET_ADMIN_PASSWORD; test 130/130; sinh lại file 02, ERD; sửa báo cáo CSDL; đóng gói lại. Chi tiết mục 4.10.
- 16/11 (tiếp): **trưởng nhóm chốt khôi phục mật khẩu Admin do hệ thống lớn quyết định, ngoài phạm vi.** UC5.18 bỏ Admin khỏi tác nhân; BR42 không gửi OTP cho tài khoản Admin; ghi chú BR43, NFR29, PasswordControl sửa theo. Không đổi CSDL, số UC, số NFR.

- 16/11 (cuối ngày): **hoàn thiện bộ biểu đồ thống nhất để nộp** (trưởng nhóm yêu cầu "làm đầy đủ để có thiết kế thống nhất"). Không đổi quyết định, UC, BR, CSDL. Vẽ mới từ context 00–04: biểu đồ UC tổng quan + 5 phân rã, mô hình miền (đầy đủ 25 lớp + bản luồng chính), 11 biểu đồ lớp phân tích, 2 biểu đồ trạng thái, 12 biểu đồ tuần tự luồng chính (Gửi hồ sơ + Phân tích CV, Gợi ý việc làm, Nộp hồ sơ + OTP, Xét duyệt + Mời phỏng vấn, Xác nhận lịch, Nhập kết quả + Lời mời thử việc, Phản hồi lời mời thử việc, Cấp tài khoản thử việc, Giao task, Nộp bài, Đánh giá bài nộp, Kết luận thử việc). Tên lớp thiết kế mới theo quy ước …Control → …Service, phản hồi qua link → …Handler kế thừa ResponseHandler, mỗi entity một Repository. Gom thành Thiet_ke_he_thong_tong_hop.docx/.pdf (47 hình, có bảng truy vết UC → control → service → bảng). Chạy lại test CSDL trên DB mới: 130/130.
- 16/11 (chiều): **trưởng nhóm yêu cầu hình giống Astah, không dùng đường cong.** Vẽ lại use case, lớp phân tích, mô hình miền, trạng thái: đường nối thẳng hoặc gấp khúc vuông góc; trạng thái Đã mời phỏng vấn dùng ngăn chuyển tiếp nội bộ thay vòng tự lặp. Không đổi nội dung thiết kế.

---

## 9. Danh mục tài liệu bàn giao (bản chốt 16/11)

| Thư mục trong gói | Tài liệu | Nội dung |
|---|---|---|
| 0_Tai_lieu_tong_hop | Thiet_ke_he_thong_tong_hop.docx / .pdf | **Tài liệu nộp giáo viên**: use case, mô hình miền, lớp phân tích, trạng thái, 16 tuần tự luồng chính, thiết kế lớp, ERD, truy vết |
| 0_Tai_lieu_tong_hop/hinh, ma_nguon_bieu_do | 47 ảnh PNG + script sinh hình | Vẽ lại khi có thay đổi |
| 1_Context | 00–04 (.md) | Nguồn sự thật: quyết định, use case + BR, CSDL, Glossary + NFR, mô hình miền + lớp phân tích |
| 2_Thiet_ke_4_use_case | Thiet_ke_4_UC_tieu_bieu.docx / .pdf + ảnh | Biểu đồ tuần tự, lớp thiết kế, lớp chi tiết, trích xuất CSDL cho Thiết lập tiêu chí, Chấm điểm CV, Tự động mời phỏng vấn, Xếp lại lịch (kiểu Astah) |
| 3_Co_so_du_lieu | schema_25.sql, test_25.sql, kết quả test, 5 ERD (PNG + SVG), công cụ sinh lại | CSDL 25 bảng chạy thật trên PostgreSQL 16 + pgvector |
| 4_Mo_hinh_du_lieu_tong_quan | So_sanh_ERD_cu_moi.docx, ERD tổng quan rút gọn | ERD kiểu Chen 10 đối tượng để đưa vào thân báo cáo |
| Trực tuyến (Claude Docs) | Báo cáo thiết kế CSDL; Đặc tả thực thể – ERD tổng quan | Bản đọc trên web, chia sẻ được |

Không thuộc bộ chốt: Thiet_ke_4_chuc_nang.docx (bản Mermaid cũ), Báo cáo mẫu và bộ slide tiến độ (bản nháp dừng ngày 04/11).
