# 01. Use case, đặc tả rút gọn và quy tắc nghiệp vụ

> **Bản chốt cuối 16/11/2026.** Sinh từ dữ liệu đặc tả bản 28/10/2026, rồi áp đợt rút gọn 03/11 (mục 4.8 file 00), quyết định bỏ trích dẫn bằng chứng 04/11 và quyết định 16/11 hệ thống con chỉ có 1 Admin do hệ thống nhân sự lớn cấp (mục 4.10) trực tiếp vào bản rút gọn này. Tổng **61 use case**; mã đã xóa (UC3.02, UC3.06, UC5.03, UC5.07, UC5.09, BR33–BR35, BR43) để trống, không dùng lại. Số bước ghi trong ngoặc là của bản 28/10; với các use case có sửa (đánh dấu ✎), luồng tương ứng đã bỏ nên số luồng thực tế có thể ít hơn. Nếu nhóm còn dùng 5 file `Dac_ta_UC_*.docx`, các file đó phải sửa theo tài liệu này.

## Nhóm 1 – Quản lý tuyển dụng (15 use case)

### Danh sách use case

| Mã | Use case | Mô tả ngắn | Tác nhân | Độ phức tạp |
|---|---|---|---|---|
| UC1.01 | Xem danh sách tin tuyển dụng | Xem, tìm kiếm, lọc tin; chọn thao tác trên tin | Bộ phận tuyển dụng | Đơn giản |
| UC1.02 | Tạo tin tuyển dụng | Tạo tin mới kèm bộ tiêu chí, đăng hoặc lưu nháp | Bộ phận tuyển dụng | Trung bình |
| UC1.03 | Cập nhật tin tuyển dụng | Sửa tin Nháp hoặc Đang mở, lưu lịch sử | Bộ phận tuyển dụng | Đơn giản |
| UC1.04 | Đóng tin tuyển dụng | Ngừng nhận hồ sơ cho vị trí | Bộ phận tuyển dụng | Đơn giản |
| UC1.05 | Thiết lập tiêu chí chấm điểm | Tiêu chí, trọng số, ngưỡng tự động mời, người phỏng vấn | Bộ phận tuyển dụng | Trung bình |
| UC1.06 | Xem danh sách hồ sơ ứng tuyển | Tra cứu mọi hồ sơ và trạng thái | Bộ phận tuyển dụng | Đơn giản |
| UC1.07 | Xét duyệt hồ sơ | Xét hồ sơ dưới ngưỡng, ra quyết định | Bộ phận tuyển dụng | Trung bình |
| UC1.08 ✎ | Xem chi tiết hồ sơ và giải trình điểm AI | CV, điểm và nhận xét của AI cho từng tiêu chí | Bộ phận tuyển dụng | Đơn giản |
| UC1.09 | Mời phỏng vấn | Tìm giờ trống, tạo lịch và link Meet, gửi thư mời | Bộ phận tuyển dụng; Google Workspace, Dịch vụ Email | Phức tạp |
| UC1.10 | Từ chối hồ sơ | Ghi lý do nội bộ, gửi thư cảm ơn, xin lưu hồ sơ | Bộ phận tuyển dụng; Dịch vụ Email | Trung bình |
| UC1.11 | Xem báo cáo (trừu tượng) | Hành vi chung của các báo cáo | Bộ phận tuyển dụng | Đơn giản |
| UC1.12 | Xem phễu tuyển dụng | Số ứng viên qua từng bước, tỉ lệ chuyển đổi | Bộ phận tuyển dụng | Trung bình |
| UC1.13 | Xem thống kê sàng lọc AI | Phân bố điểm AI, mức khớp giữa AI và người | Bộ phận tuyển dụng | Trung bình |
| UC1.14 | Xem thống kê thử việc | Tỉ lệ Đạt/Không đạt thử việc, task đạt | Bộ phận tuyển dụng | Đơn giản |
| UC1.15 | Xuất báo cáo | Tải báo cáo dạng Excel hoặc PDF | Bộ phận tuyển dụng | Đơn giản |

### Quan hệ giữa use case

| Quan hệ | Từ | Đến | Ý nghĩa / điều kiện |
|---|---|---|---|
| «extend» | UC1.03 Cập nhật tin tuyển dụng | UC1.01 Xem danh sách tin tuyển dụng | Điểm mở rộng "Chọn thao tác trên tin"; khi chọn Cập nhật |
| «extend» | UC1.04 Đóng tin tuyển dụng | UC1.01 | Điểm mở rộng "Chọn thao tác trên tin"; khi chọn Đóng tin |
| «extend» | UC1.02 Tạo tin tuyển dụng | UC1.01 | Điểm mở rộng "Chọn thao tác trên tin"; khi chọn Tạo tin mới |
| «include» | UC1.02 Tạo tin tuyển dụng | UC1.05 Thiết lập tiêu chí chấm điểm | Tạo tin luôn phải có bộ tiêu chí |
| «include» | UC1.07 Xét duyệt hồ sơ | UC1.08 Xem chi tiết hồ sơ và giải trình điểm AI | Xét duyệt luôn phải xem chi tiết hồ sơ |
| «extend» | UC1.09 Mời phỏng vấn | UC1.07 | Điểm mở rộng "Ra quyết định"; [HR duyệt đạt] |
| «extend» | UC1.10 Từ chối hồ sơ | UC1.07 | Điểm mở rộng "Ra quyết định"; [HR không duyệt] |
| Generalization | UC1.12, UC1.13, UC1.14 | UC1.11 Xem báo cáo | Các báo cáo cụ thể kế thừa hành vi chung |
| «extend» | UC1.15 Xuất báo cáo | UC1.11 | Điểm mở rộng "Xuất dữ liệu"; khi chọn Xuất |

### Đặc tả rút gọn

- **UC1.01 Xem danh sách tin tuyển dụng** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Bộ phận tuyển dụng đã đăng nhập vào hệ thống. Hậu điều kiện: Danh sách tin được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 6: Chọn thao tác trên tin. (6 bước chính, 4 luồng thay thế, 3 ngoại lệ)
- **UC1.02 Tạo tin tuyển dụng** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR. Hậu điều kiện: Tin mới được lưu ở trạng thái Đang mở (hoặc Nháp). Tin Đang mở được hiển thị trên trang tuyển dụng và đưa vào nguồn dữ liệu của chức năng Gợi ý việc làm AI. (8 bước chính, 3 luồng thay thế, 4 ngoại lệ)
- **UC1.03 Cập nhật tin tuyển dụng** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR; tin tồn tại và ở trạng thái Nháp hoặc Đang mở. Hậu điều kiện: Thông tin tin được cập nhật; lịch sử chỉnh sửa được lưu. (7 bước chính, 3 luồng thay thế, 3 ngoại lệ)
- **UC1.04 Đóng tin tuyển dụng** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR; tin ở trạng thái Đang mở. Hậu điều kiện: Tin ở trạng thái Đã đóng, ứng viên không thể nộp hồ sơ mới. Hồ sơ Chờ HR duyệt và lịch phỏng vấn đã tạo vẫn được xử lý bình thường. (5 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC1.05 Thiết lập tiêu chí chấm điểm** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR; tin ở trạng thái Nháp hoặc Đang mở, hoặc tin đang được tạo mới. Hậu điều kiện: Bộ tiêu chí phiên bản mới được lưu và dùng để chấm các hồ sơ nộp sau thời điểm lưu. (8 bước chính, 4 luồng thay thế, 4 ngoại lệ)
- **UC1.06 Xem danh sách hồ sơ ứng tuyển** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Bộ phận tuyển dụng đã đăng nhập vào hệ thống. Hậu điều kiện: Danh sách và tóm tắt hồ sơ được hiển thị. Dữ liệu hồ sơ không thay đổi; lượt truy cập được ghi nhật ký. (6 bước chính, 2 luồng thay thế, 3 ngoại lệ)
- **UC1.07 Xét duyệt hồ sơ** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Có ít nhất một hồ sơ ở trạng thái Chờ HR duyệt (BR06). Hậu điều kiện: Hồ sơ chuyển sang Đã mời phỏng vấn hoặc Đã từ chối; quyết định và người duyệt được lưu vết. Điểm mở rộng: bước 5: Ra quyết định. (7 bước chính, 5 luồng thay thế, 3 ngoại lệ)
- **UC1.08 Xem chi tiết hồ sơ và giải trình điểm AI ✎** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR; đã chọn một hồ sơ ứng tuyển. Điểm AI của hồ sơ đã được tính khi ứng viên nộp hồ sơ. Hậu điều kiện: Hồ sơ không thay đổi; lượt truy cập được ghi nhật ký. Giải trình điểm = điểm và nhận xét của AI cho từng tiêu chí (không còn trích dẫn bằng chứng, 04/11). (5 bước chính, 2 luồng thay thế, 1 ngoại lệ)
- **UC1.09 Mời phỏng vấn** — Tác nhân: Bộ phận tuyển dụng (chính); Google Workspace, Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ ở trạng thái Chờ HR duyệt và Bộ phận tuyển dụng đã kết luận Duyệt đạt. Hậu điều kiện: Sự kiện phỏng vấn có link Meet được tạo trên lịch người phỏng vấn; ứng viên nhận thư mời; hồ sơ ở trạng thái Đã mời phỏng vấn và chờ ứng viên xác nhận. (11 bước chính, 3 luồng thay thế, 5 ngoại lệ)
- **UC1.10 Từ chối hồ sơ** — Tác nhân: Bộ phận tuyển dụng (chính); Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ ở trạng thái Chờ HR duyệt và Bộ phận tuyển dụng đã kết luận Không duyệt. Hậu điều kiện: Hồ sơ ở trạng thái Đã từ chối; ứng viên nhận thư cảm ơn và có thể đồng ý lưu hồ sơ qua đường dẫn trong thư trong thời hạn phản hồi. (6 bước chính, 2 luồng thay thế, 3 ngoại lệ)
- **UC1.11 Xem báo cáo (use case trừu tượng)** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Bộ phận tuyển dụng đã đăng nhập vào hệ thống. Hậu điều kiện: Báo cáo được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 5: Xuất dữ liệu. (5 bước chính, 2 luồng thay thế, 2 ngoại lệ)
- **UC1.12 Xem phễu tuyển dụng** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR. Hậu điều kiện: Báo cáo phễu được hiển thị. Dữ liệu không thay đổi. (4 bước chính, 1 luồng thay thế, 1 ngoại lệ)
- **UC1.13 Xem thống kê sàng lọc AI** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR. Hậu điều kiện: Thống kê sàng lọc AI được hiển thị. Dữ liệu không thay đổi. (4 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC1.14 Xem thống kê thử việc** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR. Hậu điều kiện: Thống kê thử việc được hiển thị. Dữ liệu không thay đổi. (3 bước chính, 1 luồng thay thế, 1 ngoại lệ)
- **UC1.15 Xuất báo cáo** — Tác nhân: Bộ phận tuyển dụng. Tiền điều kiện: Đang hiển thị một báo cáo có dữ liệu cho người dùng có vai trò HR. Hậu điều kiện: File báo cáo được tải về; nhật ký xuất được ghi. (5 bước chính, 1 luồng thay thế, 2 ngoại lệ)

## Nhóm 2 – Ứng tuyển và gợi ý việc làm (13 use case)

### Danh sách use case

| Mã | Use case | Mô tả ngắn | Tác nhân | Độ phức tạp |
|---|---|---|---|---|
| UC2.01 ✎ | Gửi hồ sơ | Nhập thông tin, tải CV (PDF/DOCX có lớp chữ), đồng ý xử lý dữ liệu | Ứng viên | Trung bình |
| UC2.02 ✎ | Phân tích CV | AI trích xuất CV thành dữ liệu có cấu trúc | Dịch vụ AI | Phức tạp |
| UC2.03 | Gợi ý việc làm AI | So khớp CV với tin đang mở, hiển thị % phù hợp | Ứng viên; Dịch vụ AI | Phức tạp |
| UC2.04 | Xem chi tiết vị trí | Xem đầy đủ thông tin vị trí | Ứng viên | Đơn giản |
| UC2.05 | Nộp hồ sơ | Chọn vị trí, xác thực OTP, tạo hồ sơ ứng tuyển | Ứng viên | Trung bình |
| UC2.06 | Xác thực OTP | Gửi và kiểm tra mã OTP qua email | Dịch vụ Email | Trung bình |
| UC2.07 | Gửi lại mã OTP | Gửi mã mới khi chưa nhận hoặc hết hạn | Dịch vụ Email | Đơn giản |
| UC2.08 ✎ | Chấm điểm CV | AI chấm điểm và nhận xét từng tiêu chí; code tính tổng; phân loại hồ sơ | Dịch vụ AI | Phức tạp |
| UC2.09 | Tự động mời phỏng vấn | Tự chọn giờ, tạo lịch Meet, gửi thư mời | Google Workspace; Dịch vụ Email | Phức tạp |
| UC2.10 | Trao đổi thông tin (trừu tượng) | Hành vi chung khi phản hồi qua link email | Ứng viên | Trung bình |
| UC2.11 ✎ | Phản hồi lời mời thử việc | Đồng ý hoặc từ chối thử việc | Ứng viên | Đơn giản |
| UC2.12 ✎ | Cấp tài khoản thử việc | Admin nhập email công ty; hệ thống tạo tài khoản và đợt thử việc, gửi hướng dẫn | Admin; Dịch vụ Email | Phức tạp |
| UC2.13 | Đồng ý lưu hồ sơ | Cho phép lưu hồ sơ 12 tháng | Ứng viên | Đơn giản |

### Quan hệ giữa use case

| Quan hệ | Từ | Đến | Ý nghĩa / điều kiện |
|---|---|---|---|
| «include» | UC2.01 Gửi hồ sơ | UC2.02 Phân tích CV | Gửi hồ sơ luôn phân tích CV |
| «extend» | UC2.04 Xem chi tiết vị trí | UC2.03 Gợi ý việc làm AI | Điểm mở rộng "Chọn vị trí"; khi ứng viên chọn xem chi tiết |
| «include» | UC2.05 Nộp hồ sơ | UC2.06 Xác thực OTP | Nộp hồ sơ luôn phải xác thực email |
| «extend» | UC2.07 Gửi lại mã OTP | UC2.06 | Điểm mở rộng "Nhập mã"; [chưa nhận được mã hoặc mã hết hạn] |
| «include» | UC2.05 Nộp hồ sơ | UC2.08 Chấm điểm CV | Mọi hồ sơ đã nộp đều được chấm (chạy nền) |
| «extend» | UC2.09 Tự động mời phỏng vấn | UC2.08 | Điểm mở rộng "Phân loại hồ sơ"; [đạt ngưỡng và đạt tiêu chí bắt buộc] |
| Generalization | UC2.11, UC2.13 | UC2.10 Trao đổi thông tin | Các phản hồi cụ thể kế thừa hành vi chung |

Đã bỏ (03/11): «extend» UC2.12 → UC2.11. Cấp tài khoản thử việc là use case độc lập của Admin, bắt đầu từ hồ sơ Chờ cấp tài khoản.

### Đặc tả rút gọn

- **UC2.01 Gửi hồ sơ ✎** — Tác nhân: Ứng viên. Tiền điều kiện: Ứng viên truy cập trang tuyển dụng của công ty. Hậu điều kiện: Hồ sơ tạm gồm thông tin liên hệ, CV và dữ liệu trích xuất được lưu. Chưa có hồ sơ ứng tuyển nào được tạo. Đã bỏ luồng "CV là ảnh scan": CV không trích được chữ thì hệ thống báo "CV không đọc được" để ứng viên gửi lại. (8 bước chính, 2 luồng thay thế, 7 ngoại lệ – bản 28/10)
- **UC2.02 Phân tích CV ✎** — Tác nhân: Dịch vụ AI (phụ). Tiền điều kiện: CV hợp lệ của hồ sơ tạm đã được lưu. Hậu điều kiện: Hồ sơ tạm có dữ liệu CV có cấu trúc, hoặc được đánh dấu "chưa phân tích". Không nhận dạng chữ từ ảnh. (5 bước chính, 1 luồng thay thế, 3 ngoại lệ – bản 28/10)
- **UC2.03 Gợi ý việc làm AI** — Tác nhân: Ứng viên (chính); Dịch vụ AI (phụ). Tiền điều kiện: Ứng viên vừa gửi hồ sơ thành công trong phiên làm việc hiện tại; hồ sơ tạm còn hạn (BR26). Hậu điều kiện: Ứng viên xem được danh sách vị trí, hoặc hồ sơ được lưu cho đợt tuyển sau nếu ứng viên đồng ý. Chưa có hồ sơ ứng tuyển nào được tạo. Điểm mở rộng: bước 5: Chọn vị trí. (6 bước chính, 4 luồng thay thế, 3 ngoại lệ)
- **UC2.04 Xem chi tiết vị trí** — Tác nhân: Ứng viên (thông qua UC2.03). Tiền điều kiện: Ứng viên đang xem danh sách vị trí được gợi ý; vị trí được chọn ở trạng thái Đang mở. Hậu điều kiện: Dữ liệu không thay đổi. (3 bước chính, 1 luồng thay thế, 1 ngoại lệ)
- **UC2.05 Nộp hồ sơ** — Tác nhân: Ứng viên. Tiền điều kiện: Ứng viên có hồ sơ tạm còn hạn (BR26) và đã chọn một vị trí Đang mở. Hậu điều kiện: Hồ sơ ứng tuyển được tạo ở trạng thái Đang chấm điểm; sau khi chấm, hồ sơ chuyển sang Đã mời phỏng vấn hoặc Chờ HR duyệt. Hồ sơ tạm không còn bị xóa theo BR26. (8 bước chính, 2 luồng thay thế, 4 ngoại lệ)
- **UC2.06 Xác thực OTP** — Tác nhân: Dịch vụ Email (phụ). Tiền điều kiện: Có địa chỉ email cần xác thực và mục đích xác thực (nộp hồ sơ hoặc đặt lại mật khẩu). Hậu điều kiện: Email được xác thực (thành công) hoặc chưa xác thực (thất bại). Điểm mở rộng: bước 4: Nhập mã. (7 bước chính, 1 luồng thay thế, 6 ngoại lệ)
- **UC2.07 Gửi lại mã OTP** — Tác nhân: Dịch vụ Email (phụ). Tiền điều kiện: Đang có một mã OTP chờ nhập cho email và mục đích xác thực. Hậu điều kiện: Mã cũ hết hiệu lực; mã mới đã được gửi. (6 bước chính, 0 luồng thay thế, 3 ngoại lệ)
- **UC2.08 Chấm điểm CV ✎** — Tác nhân: Dịch vụ AI (phụ). Tiền điều kiện: Hồ sơ ứng tuyển vừa được tạo ở trạng thái Đang chấm điểm sau khi xác thực OTP thành công (BR19). Hậu điều kiện: Hồ sơ có điểm và nhận xét từng tiêu chí, tổng điểm do code tính (nếu chấm được); trạng thái là Đã mời phỏng vấn (qua UC2.09) hoặc Chờ HR duyệt. Đã bỏ bước đối chiếu trích dẫn với CV và ngoại lệ trích dẫn không có trong CV (04/11); kết quả AI vẫn phải đúng cấu trúc, sai thì chuyển HR duyệt. Điểm mở rộng: bước 7: Phân loại hồ sơ. (7 bước chính, 2 luồng thay thế, 3 ngoại lệ – bản 28/10)
- **UC2.09 Tự động mời phỏng vấn** — Tác nhân: Google Workspace, Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ đã được chấm, tổng điểm từ ngưỡng tự động mời trở lên và đạt mọi tiêu chí bắt buộc. Hậu điều kiện: Sự kiện phỏng vấn có link Meet được tạo; ứng viên nhận thư mời; hồ sơ ở trạng thái Đã mời phỏng vấn, chờ ứng viên xác nhận trong thời hạn phản hồi; quá hạn thì xử lý theo BR24. (9 bước chính, 0 luồng thay thế, 5 ngoại lệ)
- **UC2.10 Trao đổi thông tin (use case trừu tượng)** — Tác nhân: Ứng viên. Tiền điều kiện: Ứng viên đã nhận email có link phản hồi. Hậu điều kiện: Phản hồi của ứng viên được ghi nhận. (6 bước chính, 1 luồng thay thế, 4 ngoại lệ)
- **UC2.11 Phản hồi lời mời thử việc ✎** — Tác nhân: Ứng viên (kế thừa UC2.10). Tiền điều kiện: Hồ sơ ở trạng thái Đạt phỏng vấn, có lời mời thử việc còn trong thời hạn phản hồi (BR23). Hậu điều kiện: Hồ sơ ở trạng thái Chờ cấp tài khoản (Admin được thông báo), hoặc ở trạng thái Từ chối thử việc. Không còn điểm mở rộng "Ghi nhận phản hồi". (6 bước chính, 1 luồng thay thế, 3 ngoại lệ – bản 28/10)
- **UC2.12 Cấp tài khoản thử việc ✎** — Tác nhân: Admin (chính); Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ ở trạng thái Chờ cấp tài khoản. Luồng chính: Admin xem danh sách hồ sơ Chờ cấp tài khoản (họ tên, vị trí, phòng ban, ngày bắt đầu; không có CV, điểm – BR29) → nhập email công ty → hệ thống kiểm tra đúng tên miền và duy nhất (BR39) → tạo tài khoản vai trò Nhân viên thử việc và đợt thử việc → gửi hướng dẫn đặt mật khẩu lần đầu qua Quên mật khẩu → hồ sơ Đang thử việc, báo HR và quản lý bộ phận. Hậu điều kiện: Ứng viên có tài khoản Nhân viên thử việc (chưa có mật khẩu) và đợt thử việc đang diễn ra; hồ sơ ở trạng thái Đang thử việc. Hộp thư công ty do bộ phận IT / hệ thống nhân sự lớn tạo bên ngoài hệ thống. (đặc tả viết lại 03/11)
- **UC2.13 Đồng ý lưu hồ sơ** — Tác nhân: Ứng viên (kế thừa UC2.10). Tiền điều kiện: Ứng viên có đường dẫn đồng ý lưu hồ sơ còn trong thời hạn phản hồi. Hậu điều kiện: Hồ sơ được lưu 12 tháng và có thể được dùng khi công ty mở vị trí phù hợp. (5 bước chính, 2 luồng thay thế, 1 ngoại lệ)

## Nhóm 3 – Phỏng vấn (8 use case)

### Danh sách use case

| Mã | Use case | Mô tả ngắn | Tác nhân | Độ phức tạp |
|---|---|---|---|---|
| UC3.01 ✎ | Xác nhận lịch phỏng vấn | Xác nhận, yêu cầu đổi lịch (kèm ghi chú) hoặc từ chối lịch qua link | Ứng viên; Google Workspace | Trung bình |
| UC3.02 | *(đã xóa 03/11 – thay bằng lựa chọn Yêu cầu đổi lịch trong UC3.01)* | | | |
| UC3.03 | Xem lịch phỏng vấn | Xem, lọc lịch; chọn thao tác | Bộ phận tuyển dụng (HR) | Đơn giản |
| UC3.04 ✎ | Xếp lại lịch phỏng vấn | Xem ghi chú đổi lịch, chọn giờ mới, gửi link xác nhận mới | Bộ phận tuyển dụng; Google Workspace, Dịch vụ Email | Phức tạp |
| UC3.05 | Hủy lịch phỏng vấn | Hủy buổi, hồ sơ về Chờ HR duyệt | Bộ phận tuyển dụng; Google Workspace, Dịch vụ Email | Trung bình |
| UC3.06 | *(đã xóa 03/11 – đổi người phỏng vấn = Hủy lịch rồi mời lại)* | | | |
| UC3.07 ✎ | Xem hồ sơ ứng viên được giao | Hồ sơ, CV, điểm và nhận xét AI của buổi được giao | Bộ phận tuyển dụng (Người phỏng vấn) | Đơn giản |
| UC3.08 ✎ | Nhập kết quả phỏng vấn | Phiếu đánh giá, kết luận, vắng mặt | Bộ phận tuyển dụng (Người phỏng vấn, HR) | Trung bình |
| UC3.09 ✎ | Gửi lời mời thử việc | Nhập thông tin thử việc, gửi link phản hồi | Bộ phận tuyển dụng; Dịch vụ Email | Trung bình |
| UC3.10 | Gửi thư cảm ơn | Thư cảm ơn kèm link đồng ý lưu hồ sơ | Dịch vụ Email | Đơn giản |

### Quan hệ giữa use case

| Quan hệ | Từ | Đến | Ý nghĩa / điều kiện |
|---|---|---|---|
| «extend» | UC3.04, UC3.05 | UC3.03 Xem lịch phỏng vấn | Điểm mở rộng "Chọn thao tác trên lịch"; theo thao tác HR chọn |
| «extend» | UC3.09 Gửi lời mời thử việc | UC3.08 Nhập kết quả phỏng vấn | Điểm mở rộng "Kết quả phỏng vấn"; [Đạt] |
| «extend» | UC3.10 Gửi thư cảm ơn | UC3.08 | Điểm mở rộng "Kết quả phỏng vấn"; [Không đạt / vắng mặt] |

Đã bỏ (03/11): «extend» UC3.02 → UC3.01; «extend» UC3.06 → UC3.03.

### Đặc tả rút gọn

- **UC3.01 Xác nhận lịch phỏng vấn ✎** — Tác nhân: Ứng viên (chính); Google Workspace (phụ). Tiền điều kiện: Hồ sơ ở trạng thái Đã mời phỏng vấn; ứng viên có đường dẫn xác nhận lịch còn hiệu lực. Ba lựa chọn: Xác nhận / Yêu cầu đổi lịch (ghi chú bắt buộc ≤ 500 ký tự, ví dụ khung giờ mong muốn) / Từ chối (kèm lý do). Yêu cầu đổi lịch: buổi chuyển Yêu cầu đổi lịch, link dùng với kết quả "Yêu cầu đổi lịch", báo HR. Ngoại lệ: hồ sơ đã yêu cầu đủ 2 lần (BR49) thì chỉ còn Xác nhận / Từ chối. Hậu điều kiện: Buổi phỏng vấn được xác nhận, hoặc ở trạng thái Yêu cầu đổi lịch kèm ghi chú, hoặc hồ sơ ở trạng thái Từ chối phỏng vấn; link đã dùng. Không còn điểm mở rộng "Phản hồi lịch". (8 bước chính, 2 luồng thay thế, 5 ngoại lệ – bản 28/10)
- **UC3.03 Xem lịch phỏng vấn** — Tác nhân: Bộ phận tuyển dụng (vai trò HR). Tiền điều kiện: Người dùng đã đăng nhập với vai trò HR. Hậu điều kiện: Lịch được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 6: Chọn thao tác trên lịch. (6 bước chính, 4 luồng thay thế, 2 ngoại lệ)
- **UC3.04 Xếp lại lịch phỏng vấn ✎** — Tác nhân: Bộ phận tuyển dụng (vai trò HR, chính); Google Workspace, Dịch vụ Email (phụ). Tiền điều kiện: Người dùng có vai trò HR; buổi phỏng vấn ở trạng thái Đã lên lịch, Đã xác nhận hoặc Yêu cầu đổi lịch; hồ sơ chưa có kết quả phỏng vấn. HR xem ghi chú đổi lịch của ứng viên, chọn một trong các khung trống hệ thống gợi ý; hệ thống kiểm tra lại khung lúc lưu, cập nhật sự kiện Google, vô hiệu link cũ, cấp link mới, gửi email lịch mới. Đã bỏ "ưu tiên khung ứng viên đề xuất" và "chọn đúng khung đề xuất thì chuyển thẳng Đã xác nhận". Hậu điều kiện: Buổi phỏng vấn có thời gian mới, trạng thái Đã lên lịch, ghi chú đổi lịch được xóa; ứng viên nhận email lịch mới; link cũ hết hiệu lực. (11 bước chính, 3 luồng thay thế, 4 ngoại lệ – bản 28/10)
- **UC3.05 Hủy lịch phỏng vấn** — Tác nhân: Bộ phận tuyển dụng (vai trò HR, chính); Google Workspace, Dịch vụ Email (phụ). Tiền điều kiện: Người dùng có vai trò HR; buổi phỏng vấn chưa diễn ra và chưa có kết quả. Hậu điều kiện: Buổi phỏng vấn đã hủy; hồ sơ ở trạng thái Chờ HR duyệt kèm ghi chú lý do hủy. (9 bước chính, 1 luồng thay thế, 4 ngoại lệ)
- **UC3.07 Xem hồ sơ ứng viên được giao ✎** — Tác nhân: Bộ phận tuyển dụng (vai trò Người phỏng vấn). Tiền điều kiện: Đã đăng nhập với vai trò Người phỏng vấn. Hậu điều kiện: Dữ liệu không thay đổi; lượt xem được ghi nhật ký. Hiển thị điểm và nhận xét AI từng tiêu chí (không còn trích dẫn). (5 bước chính, 2 luồng thay thế, 2 ngoại lệ)
- **UC3.08 Nhập kết quả phỏng vấn ✎** — Tác nhân: Bộ phận tuyển dụng (vai trò Người phỏng vấn hoặc HR). Tiền điều kiện: Người dùng là người phỏng vấn được giao hoặc HR; đã qua giờ bắt đầu buổi phỏng vấn; buổi chưa có kết quả. Hậu điều kiện: Buổi phỏng vấn có kết quả; hồ sơ ở trạng thái Đạt hoặc Không đạt phỏng vấn; ứng viên nhận thư mời thử việc hoặc thư cảm ơn. Đã bỏ bước kiểm tra phòng ban còn Quản lý bộ phận đang hoạt động trước khi lưu kết quả Đạt (giả định 03/11). Điểm mở rộng: bước 7: Kết quả phỏng vấn. (7 bước chính, 3 luồng thay thế, 5 ngoại lệ – bản 28/10)
- **UC3.09 Gửi lời mời thử việc ✎** — Tác nhân: Bộ phận tuyển dụng (chính); Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ vừa được kết luận Đạt phỏng vấn và chưa có lời mời thử việc. Hậu điều kiện: Lời mời thử việc được tạo và gửi; hồ sơ chờ ứng viên phản hồi trong 2 ngày làm việc. Đã bỏ ngoại lệ 1a "phòng ban không còn quản lý đang hoạt động". (8 bước chính, 1 luồng thay thế, 4 ngoại lệ – bản 28/10)
- **UC3.10 Gửi thư cảm ơn** — Tác nhân: Dịch vụ Email (phụ). Tiền điều kiện: Hồ sơ vừa được kết luận Không đạt phỏng vấn hoặc ứng viên vắng mặt. Hậu điều kiện: Ứng viên nhận thư cảm ơn kèm đường dẫn đồng ý lưu hồ sơ (nếu chưa đồng ý trước đó). (5 bước chính, 1 luồng thay thế, 1 ngoại lệ)

## Nhóm 4 – Onboarding và thử việc (10 use case)

### Danh sách use case

| Mã | Use case | Mô tả ngắn | Tác nhân | Độ phức tạp |
|---|---|---|---|---|
| UC4.01 | Xem danh sách task thử việc | Đợt thử việc, task của từng nhân viên; chọn thao tác | Quản lý bộ phận | Đơn giản |
| UC4.02 | Giao task | Tạo task với mô tả, tệp, hạn nộp | Quản lý bộ phận; Dịch vụ Email | Trung bình |
| UC4.03 | Cập nhật task | Sửa task chưa được đánh giá | Quản lý bộ phận; Dịch vụ Email | Trung bình |
| UC4.04 | Xóa task | Xóa mềm task chưa có bài nộp | Quản lý bộ phận | Đơn giản |
| UC4.05 | Đánh giá bài nộp | Đạt / Không đạt kèm nhận xét | Quản lý bộ phận; Dịch vụ Email | Trung bình |
| UC4.06 | Xem tổng hợp kết quả thử việc | Số task, Đạt, Không đạt, chưa nộp, nộp muộn | Quản lý bộ phận, Nhân viên thử việc | Đơn giản |
| UC4.07 | Kết luận thử việc | Kết luận Đạt / Không đạt, xử lý tài khoản | Quản lý bộ phận; Dịch vụ Email | Phức tạp |
| UC4.08 | Xem task được giao | Task, hạn nộp, kết quả của mình | Nhân viên thử việc | Đơn giản |
| UC4.09 | Nộp bài | Nộp link hoặc tệp | Nhân viên thử việc; Dịch vụ Email | Trung bình |
| UC4.10 | Cập nhật bài nộp | Thay bài khi chưa được đánh giá | Nhân viên thử việc | Đơn giản |

### Quan hệ giữa use case

| Quan hệ | Từ | Đến | Ý nghĩa / điều kiện |
|---|---|---|---|
| «extend» | UC4.02, UC4.03, UC4.04 | UC4.01 Xem danh sách task thử việc | Điểm mở rộng "Chọn thao tác trên task"; theo thao tác quản lý chọn |
| «include» | UC4.07 Kết luận thử việc | UC4.06 Xem tổng hợp kết quả thử việc | Kết luận luôn dựa trên tổng hợp kết quả |
| «extend» | UC4.09 Nộp bài | UC4.08 Xem task được giao | Điểm mở rộng "Chọn thao tác trên task"; task chưa có bài nộp |
| «extend» | UC4.10 Cập nhật bài nộp | UC4.08 | Điểm mở rộng "Chọn thao tác trên task"; [bài chưa được đánh giá] |

### Đặc tả rút gọn

- **UC4.01 Xem danh sách task thử việc** — Tác nhân: Quản lý bộ phận. Tiền điều kiện: Đã đăng nhập với vai trò Quản lý bộ phận. Hậu điều kiện: Danh sách được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 6: Chọn thao tác trên task. (6 bước chính, 5 luồng thay thế, 2 ngoại lệ)
- **UC4.02 Giao task** — Tác nhân: Quản lý bộ phận (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng là Quản lý bộ phận phụ trách đợt thử việc; đợt đang diễn ra. Hậu điều kiện: Task mới được tạo; nhân viên thử việc nhận thông báo. (8 bước chính, 1 luồng thay thế, 4 ngoại lệ)
- **UC4.03 Cập nhật task** — Tác nhân: Quản lý bộ phận (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng là Quản lý bộ phận phụ trách đợt; task chưa có kết quả đánh giá. Hậu điều kiện: Task được cập nhật; nhân viên nhận thông báo. (8 bước chính, 2 luồng thay thế, 3 ngoại lệ)
- **UC4.04 Xóa task** — Tác nhân: Quản lý bộ phận. Tiền điều kiện: Người dùng là Quản lý bộ phận phụ trách đợt; task chưa có bài nộp. Hậu điều kiện: Task bị xóa mềm, không tính vào tổng hợp kết quả. (5 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC4.05 Đánh giá bài nộp** — Tác nhân: Quản lý bộ phận (chính); Dịch vụ Email (phụ). Tiền điều kiện: Đã đăng nhập với vai trò Quản lý bộ phận; task có bài nộp chưa được đánh giá; đợt thử việc chưa kết luận. Hậu điều kiện: Bài nộp có kết quả Đạt / Không đạt, không sửa được nữa. (8 bước chính, 1 luồng thay thế, 4 ngoại lệ)
- **UC4.06 Xem tổng hợp kết quả thử việc** — Tác nhân: Quản lý bộ phận, Nhân viên thử việc. Tiền điều kiện: Người dùng đã đăng nhập; là Quản lý bộ phận phụ trách đợt hoặc là Nhân viên thử việc của đợt. Hậu điều kiện: Tổng hợp được hiển thị. Dữ liệu không thay đổi. (3 bước chính, 2 luồng thay thế, 2 ngoại lệ)
- **UC4.07 Kết luận thử việc** — Tác nhân: Quản lý bộ phận (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng là Quản lý bộ phận phụ trách đợt; đợt đang diễn ra; đã đến ngày kết thúc hoặc trong 5 ngày làm việc trước đó (BR60). Hậu điều kiện: Đợt thử việc có kết luận không sửa được; tài khoản nhân viên được xử lý theo BR44. (10 bước chính, 1 luồng thay thế, 5 ngoại lệ)
- **UC4.08 Xem task được giao** — Tác nhân: Nhân viên thử việc. Tiền điều kiện: Đã đăng nhập bằng tài khoản Nhân viên thử việc; đợt thử việc đang diễn ra hoặc đã kết luận nhưng tài khoản chưa bị khóa. Hậu điều kiện: Danh sách task được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 4: Chọn thao tác trên task. (4 bước chính, 3 luồng thay thế, 2 ngoại lệ)
- **UC4.09 Nộp bài** — Tác nhân: Nhân viên thử việc (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng là Nhân viên thử việc của đợt; task chưa có bài nộp; đợt chưa kết luận. Hậu điều kiện: Task có bài nộp chờ đánh giá; quản lý nhận thông báo. (8 bước chính, 2 luồng thay thế, 4 ngoại lệ)
- **UC4.10 Cập nhật bài nộp** — Tác nhân: Nhân viên thử việc. Tiền điều kiện: Người dùng là Nhân viên thử việc của đợt; bài nộp chưa được đánh giá; đợt chưa kết luận. Hậu điều kiện: Bài nộp được thay; vẫn chờ đánh giá. (6 bước chính, 1 luồng thay thế, 3 ngoại lệ)

## Nhóm 5 – Quản trị hệ thống (15 use case)

### Danh sách use case

| Mã | Use case | Mô tả ngắn | Tác nhân | Độ phức tạp |
|---|---|---|---|---|
| UC5.01 | Xem danh sách tài khoản | Tìm, lọc tài khoản; chọn thao tác | Admin | Đơn giản |
| UC5.02 | Tạo tài khoản nhân viên | Tạo tài khoản, gán vai trò, gửi thông báo | Admin; Dịch vụ Email | Trung bình |
| UC5.03 | *(đã xóa 16/11 – hệ thống con chỉ có 1 Admin do hệ thống nhân sự lớn cấp)* | | | |
| UC5.04 | Cập nhật thông tin tài khoản | Sửa họ tên, email, phòng ban | Admin | Đơn giản |
| UC5.05 ✎ | Khóa / mở khóa tài khoản | Khóa, mở khóa kèm lý do | Admin; Dịch vụ Email | Phức tạp |
| UC5.06 ✎ | Xóa tài khoản | Ẩn danh hóa tài khoản đã khóa | Admin | Trung bình |
| UC5.07 | *(đã xóa 16/11 – không còn Admin khác để mở cửa sổ đặt lại)* | | | |
| UC5.08 ✎ | Phân quyền | Gán, gỡ vai trò nghiệp vụ | Admin | Trung bình |
| UC5.09 | *(đã xóa 03/11 – bỏ chuyển giao công việc; vòng đời nhân viên thuộc hệ thống nhân sự lớn)* | | | |
| UC5.10 | Xem nhật ký hoạt động | Xem nhật ký và biên bản thay đổi | Admin | Đơn giản |
| UC5.11 | Xuất nhật ký | Tải nhật ký dạng Excel/PDF | Admin | Đơn giản |
| UC5.12 | Cấu hình hệ thống (trừu tượng) | Hành vi chung của các nhóm cấu hình | Admin | Đơn giản |
| UC5.13 | Cấu hình lịch làm việc | Giờ làm việc, ngày nghỉ, tham số xếp lịch | Admin | Đơn giản |
| UC5.14 | Quản lý mẫu email | Sửa, xem trước, gửi thử mẫu email | Admin; Dịch vụ Email | Trung bình |
| UC5.15 | Cấu hình thời hạn | OTP, link, lưu trữ, phiên đăng nhập | Admin | Đơn giản |
| UC5.16 | Cấu hình ngưỡng AI | Ngưỡng mời phỏng vấn, ngưỡng gợi ý | Admin | Đơn giản |
| UC5.17 | Đổi mật khẩu | Đổi mật khẩu bằng mật khẩu hiện tại | Mọi tác nhân nội bộ; Dịch vụ Email | Đơn giản |
| UC5.18 ✎ | Quên mật khẩu | Đặt lại hoặc đặt lần đầu qua OTP (trừ Admin) | Bộ phận tuyển dụng, Quản lý bộ phận, Nhân viên thử việc; Dịch vụ Email | Trung bình |
| UC2.06* | Xác thực OTP (dùng lại) | Đặc tả tại tài liệu nhóm 2 | Dịch vụ Email | Trung bình |

### Quan hệ giữa use case

| Quan hệ | Từ | Đến | Ý nghĩa / điều kiện |
|---|---|---|---|
| «extend» | UC5.02, UC5.04, UC5.05, UC5.06 | UC5.01 Xem danh sách tài khoản | Điểm mở rộng "Chọn thao tác trên tài khoản"; theo thao tác Admin chọn (UC5.06 thêm điều kiện [tài khoản đã khóa]) |
| «include» | UC5.02 Tạo tài khoản nhân viên | UC5.08 Phân quyền | Tài khoản nhân viên luôn phải có vai trò |
| «extend» | UC5.11 Xuất nhật ký | UC5.10 Xem nhật ký hoạt động | Điểm mở rộng "Xuất dữ liệu" |
| Generalization | UC5.13, UC5.14, UC5.15, UC5.16 | UC5.12 Cấu hình hệ thống | Các nhóm cấu hình kế thừa hành vi chung |
| «include» | UC5.18 Quên mật khẩu | UC2.06 Xác thực OTP | Dùng lại UC của nhóm 2 (cùng phần tử trong model) |

Đã bỏ (03/11): 2 «extend» UC5.09 → UC5.05 và UC5.09 → UC5.08. Đã bỏ (16/11): «extend» UC5.03 → UC5.01 và UC5.07 → UC5.01. Bộ phận tuyển dụng không còn liên kết tới nhóm Quản trị, trừ Đổi / Quên mật khẩu.

### Đặc tả rút gọn

- **UC5.01 Xem danh sách tài khoản** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Danh sách tài khoản được hiển thị. Dữ liệu không thay đổi. Điểm mở rộng: bước 6: Chọn thao tác trên tài khoản. (6 bước chính, 7 luồng thay thế, 2 ngoại lệ)
- **UC5.02 Tạo tài khoản nhân viên** — Tác nhân: Admin (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Tài khoản nhân viên được tạo ở trạng thái Hoạt động với vai trò đã gán, chưa có mật khẩu. (10 bước chính, 2 luồng thay thế, 5 ngoại lệ)
- **UC5.04 Cập nhật thông tin tài khoản** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin; tài khoản cần sửa chưa bị xóa. Hậu điều kiện: Thông tin tài khoản được cập nhật; biên bản được lưu. (7 bước chính, 2 luồng thay thế, 2 ngoại lệ)
- **UC5.05 Khóa / mở khóa tài khoản ✎** — Tác nhân: Admin (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin; tài khoản được chọn khác tài khoản của chính mình và chưa bị xóa. Hậu điều kiện: Tài khoản bị khóa hoặc được mở khóa; biên bản được lưu. Đã bỏ điểm mở rộng "Kiểm tra công việc đang dở" và nhánh khóa khẩn cấp (03/11); vẫn chặn khóa HR cuối cùng đang hoạt động và Admin tự khóa mình (BR31); bỏ ngoại lệ "còn dưới 2 Admin" (16/11). (9 bước chính, 4 luồng thay thế, 5 ngoại lệ – bản 28/10)
- **UC5.06 Xóa tài khoản ✎** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin; tài khoản được chọn đã khóa và không phải tài khoản của chính mình. Hậu điều kiện: Thông tin cá nhân của tài khoản bị xóa; mã tài khoản và lịch sử thao tác được giữ nguyên; biên bản được lưu. Đã bỏ điều kiện "không còn công việc Chờ chuyển giao". (8 bước chính, 1 luồng thay thế, 4 ngoại lệ – bản 28/10)
- **UC5.08 Phân quyền ✎** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin; tài khoản được phân quyền là tài khoản nhân viên (đã có hoặc đang được tạo). Hậu điều kiện: Vai trò của tài khoản được cập nhật; biên bản được lưu. Đã bỏ điểm mở rộng "Kiểm tra công việc đang dở" và hậu điều kiện "công việc dở đã chuyển giao" (03/11). (8 bước chính, 3 luồng thay thế, 5 ngoại lệ – bản 28/10)
- **UC5.10 Xem nhật ký hoạt động** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Nhật ký được hiển thị; không sửa, không xóa được (BR38). Điểm mở rộng: bước 6: Xuất dữ liệu. (6 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC5.11 Xuất nhật ký** — Tác nhân: Admin. Tiền điều kiện: Đang hiển thị nhật ký có dữ liệu cho người dùng có tài khoản Admin. Hậu điều kiện: File nhật ký được tải về; thao tác xuất được ghi nhật ký. (5 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC5.12 Cấu hình hệ thống (use case trừu tượng)** — Tác nhân: Admin. Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Cấu hình mới có hiệu lực cho các thao tác sau; biên bản được lưu. (7 bước chính, 2 luồng thay thế, 2 ngoại lệ)
- **UC5.13 Cấu hình lịch làm việc** — Tác nhân: Admin (kế thừa UC5.12). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Lịch làm việc mới có hiệu lực cho các thao tác sau; biên bản được lưu. (3 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC5.14 Quản lý mẫu email** — Tác nhân: Admin (kế thừa UC5.12); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Mẫu email mới được dùng cho các email gửi sau; biên bản được lưu. (6 bước chính, 1 luồng thay thế, 2 ngoại lệ)
- **UC5.15 Cấu hình thời hạn** — Tác nhân: Admin (kế thừa UC5.12). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Thời hạn mới áp dụng cho các thao tác sau; OTP và đường dẫn đã phát hành giữ nguyên thời hạn cũ. (3 bước chính, 0 luồng thay thế, 1 ngoại lệ)
- **UC5.16 Cấu hình ngưỡng AI** — Tác nhân: Admin (kế thừa UC5.12). Tiền điều kiện: Người dùng đã đăng nhập bằng tài khoản Admin. Hậu điều kiện: Ngưỡng mới áp dụng cho tin tạo mới và lần gợi ý việc làm sau; biên bản được lưu. (3 bước chính, 1 luồng thay thế, 1 ngoại lệ)
- **UC5.17 Đổi mật khẩu** — Tác nhân: Bộ phận tuyển dụng, Quản lý bộ phận, Nhân viên thử việc, Admin (chính); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng đã đăng nhập. Hậu điều kiện: Mật khẩu mới có hiệu lực; các phiên khác đã kết thúc; người dùng được thông báo. (9 bước chính, 1 luồng thay thế, 4 ngoại lệ)
- **UC5.18 Quên mật khẩu ✎** — Tác nhân: Bộ phận tuyển dụng, Quản lý bộ phận, Nhân viên thử việc (chính; Admin không dùng – khôi phục mật khẩu Admin do hệ thống nhân sự lớn xử lý, 16/11); Dịch vụ Email (phụ). Tiền điều kiện: Người dùng chưa đăng nhập. Hậu điều kiện: Mật khẩu mới có hiệu lực; mọi phiên cũ đã kết thúc; người dùng được thông báo. (11 bước chính, 2 luồng thay thế, 6 ngoại lệ)

## Quy tắc nghiệp vụ BR01–BR62 (đầy đủ, sau 03–04/11)

Các quy tắc có sửa đánh dấu ✎; BR33–BR35 đã xóa, để trống.

| Mã | Quy tắc |
|---|---|
| BR01 | Tin tuyển dụng có 3 trạng thái: Nháp, Đang mở, Đã đóng. Chỉ tin Đang mở được hiển thị cho ứng viên, nhận hồ sơ và dùng cho gợi ý việc làm. |
| BR02 | Tin chỉ được chuyển sang Đang mở khi đủ trường bắt buộc, hạn nộp không trước ngày hiện tại và có bộ tiêu chí hợp lệ (BR04). |
| BR03 | Tin tự chuyển sang Đã đóng khi quá hạn nộp. Tin Đã đóng không được sửa hay mở lại; muốn tuyển tiếp phải tạo tin mới. |
| BR04 | Bộ tiêu chí hợp lệ: có ít nhất 1 tiêu chí; mỗi trọng số lớn hơn 0 và tổng bằng 100%; ngưỡng tự động mời phỏng vấn trong khoảng 0–100 (mặc định lấy từ cấu hình hệ thống); có ít nhất 1 người phỏng vấn. |
| BR05 | Mỗi lần lưu bộ tiêu chí tạo một phiên bản mới, chỉ áp dụng cho hồ sơ nộp sau đó. Hồ sơ đã chấm giữ nguyên điểm và phiên bản tiêu chí đã dùng. |
| BR06 | Hồ sơ có điểm từ ngưỡng trở lên và đạt mọi tiêu chí bắt buộc được hệ thống tự động mời phỏng vấn (UC2.09); nếu tự động mời thất bại, hồ sơ chuyển Chờ HR duyệt với ghi chú "Đạt ngưỡng – cần mời thủ công". Hồ sơ dưới ngưỡng, không đạt tiêu chí bắt buộc hoặc AI không chấm được chuyển sang Chờ HR duyệt. |
| BR07 | Trạng thái hồ sơ: Đang chấm điểm, Chờ HR duyệt, Đã mời phỏng vấn, Đã xác nhận lịch, Từ chối phỏng vấn, Chờ kết quả phỏng vấn, Đạt phỏng vấn, Không đạt phỏng vấn, Đã từ chối, Chờ cấp tài khoản, Đang thử việc, Từ chối thử việc, Đạt thử việc, Không đạt thử việc. |
| BR08 | Hệ thống không tự động từ chối hồ sơ. Mọi quyết định từ chối do Bộ phận tuyển dụng thực hiện và được lưu vết (người, thời điểm, lý do). |
| BR09 | Thời gian phỏng vấn phải nằm trong giờ làm việc của công ty (cấu hình hệ thống), sau hạn phản hồi của ứng viên (BR23) ít nhất 1 ngày làm việc và người phỏng vấn không bận trên Google Calendar. |
| BR10 | Thư từ chối không nêu điểm số hay lý do nội bộ, có link để ứng viên đồng ý lưu hồ sơ cho đợt tuyển sau. |
| BR11 | Email gửi thất bại được thử lại tối đa 3 lần, cách nhau 5 phút; sau đó hồ sơ được gắn cờ lỗi và Bộ phận tuyển dụng nhận thông báo. |
| BR12 | Báo cáo và file xuất chỉ chứa số liệu tổng hợp, không chứa thông tin cá nhân của ứng viên. |
| BR13 | Khoảng thời gian báo cáo tối đa 12 tháng, mặc định 30 ngày gần nhất. |
| BR14 | File CV dạng PDF hoặc DOCX, dung lượng tối đa 5MB. |
| BR15 | Họ tên không trống, tối đa 100 ký tự; email đúng định dạng; số điện thoại 10 chữ số; bắt buộc tick đồng ý xử lý dữ liệu cá nhân. |
| BR16 | Mã OTP 6 chữ số, hiệu lực 5 phút, lưu dạng băm; nhập sai tối đa 5 lần thì khóa 15 phút; gửi lại sau 60 giây, tối đa 3 lần mỗi giờ; mỗi mã gắn với một mục đích (nộp hồ sơ, đặt lại mật khẩu) và không dùng được cho mục đích khác. |
| BR17 | Mỗi email chỉ được nộp một lần vào một tin tuyển dụng. |
| BR18 | Chỉ gợi ý tin Đang mở, tối đa 5 vị trí, mức độ phù hợp từ ngưỡng gợi ý trở lên (cấu hình hệ thống). |
| BR19 | Chỉ chấm điểm CV sau khi OTP hợp lệ và hồ sơ ứng tuyển đã được tạo. |
| BR20 | Link phản hồi trong email là chuỗi ngẫu nhiên, chỉ dùng được một lần, hiệu lực bằng thời hạn phản hồi (BR23). |
| BR21 | Hồ sơ chỉ được lưu cho đợt tuyển sau khi ứng viên đồng ý; thời hạn lưu 12 tháng; ứng viên có quyền rút lại đồng ý. |
| BR22 | Có CAPTCHA; mỗi địa chỉ IP gửi hồ sơ tối đa 10 lần mỗi giờ. |
| BR23 | Thời hạn phản hồi của ứng viên cho mọi lời mời (xác nhận lịch phỏng vấn, lời mời thử việc, đồng ý lưu hồ sơ) là 2 ngày làm việc: hết giờ làm việc của ngày làm việc thứ 2 sau ngày gửi email, không tính ngày nghỉ cuối tuần và ngày nghỉ lễ theo lịch làm việc của công ty (UC5.13). Ví dụ gửi chiều thứ Sáu thì hạn là hết giờ làm việc thứ Ba. Số ngày cấu hình được. Quá hạn mà không phản hồi thì mặc định là từ chối; hệ thống không chờ thêm phản hồi của ứng viên. Email ghi rõ ngày giờ hết hạn. |
| BR24 | Khi quá hạn phản hồi, hệ thống tự động: lời mời phỏng vấn → hồ sơ Từ chối phỏng vấn và hủy sự kiện lịch; lời mời thử việc → Từ chối thử việc; đồng ý lưu hồ sơ → không lưu. Hệ thống vô hiệu link, ghi lý do "Không phản hồi trong thời hạn", thông báo Bộ phận tuyển dụng và gửi email thông báo cho ứng viên. |
| BR25 | Hồ sơ Chờ HR duyệt phải được xét duyệt trong 5 ngày làm việc; quá hạn hệ thống nhắc Bộ phận tuyển dụng. |
| BR26 | Hồ sơ tạm (đã gửi nhưng chưa nộp) bị xóa sau 24 giờ, trừ khi ứng viên đồng ý lưu hồ sơ. |
| BR27 | Chỉ Admin được gán hoặc gỡ vai trò. Không có chức năng tự đăng ký; nhân viên chỉ xem được vai trò của mình. Quyền được kiểm tra ở phía server cho mọi API. |
| BR28 | Vai trò nghiệp vụ: HR, Người phỏng vấn, Quản lý bộ phận, Nhân viên thử việc. Một tài khoản nhân viên có thể giữ nhiều vai trò, trừ Nhân viên thử việc là vai trò độc lập. Tác nhân Bộ phận tuyển dụng tương ứng vai trò HR và Người phỏng vấn. |
| BR29 | Tài khoản Admin là loại riêng: không giữ vai trò nghiệp vụ, không xem dữ liệu nghiệp vụ (CV, điểm AI, kết quả phỏng vấn). Tài khoản nhân viên không bao giờ có vai trò Admin; một người cần cả hai thì dùng hai tài khoản với hai email khác nhau. |
| BR30 ✎ | Vai trò Nhân viên thử việc chỉ được cấp qua chức năng Cấp tài khoản thử việc (UC2.12) cho hồ sơ ở trạng thái Chờ cấp tài khoản; Admin chỉ gỡ vai trò này sau khi có kết luận thử việc. |
| BR31 ✎ | Hệ thống con có đúng 1 tài khoản Admin, do hệ thống nhân sự lớn cấp khi triển khai; hệ thống con không tạo thêm Admin. Admin không tự khóa, tự xóa mình. (16/11: bỏ yêu cầu luôn còn ít nhất 2 Admin và cảnh báo khi chỉ có 1 Admin.) |
| BR32 ✎ | Không được khóa hoặc gỡ vai trò HR của HR cuối cùng đang hoạt động; áp dụng BR31 với Admin. Khóa hoặc gỡ vai trò không kiểm tra và không chuyển giao công việc đang dở. |
| BR33 | *(đã xóa 03/11)* |
| BR34 | *(đã xóa 03/11)* |
| BR35 | *(đã xóa 03/11)* |
| BR36 ✎ | Khóa tài khoản, đổi hoặc đặt lại mật khẩu, đổi email: kết thúc phiên đăng nhập liên quan. Mở khóa: mật khẩu cũ bị vô hiệu, người dùng đặt mật khẩu mới qua Quên mật khẩu. |
| BR37 ✎ | Chỉ xóa được tài khoản đã khóa. Xóa là ẩn danh hóa thông tin cá nhân, giữ mã tài khoản; không hoàn tác. |
| BR38 ✎ | Bắt buộc nhập lý do khi khóa, mở khóa, xóa, gỡ vai trò. Mỗi thao tác tạo biên bản: mã, loại thao tác, tài khoản bị tác động, người thực hiện, thời điểm, lý do, vai trò trước/sau. Biên bản và nhật ký không sửa, không xóa được. |
| BR39 | Email của mọi tài khoản (kể cả Nhân viên thử việc và Admin) phải thuộc tên miền công ty và duy nhất. Tên miền cấu hình khi triển khai. |
| BR40 | Mật khẩu tối thiểu 8 ký tự, có cả chữ và số, khác mật khẩu hiện tại; lưu dạng băm (bcrypt hoặc argon2). |
| BR41 | Đổi mật khẩu bắt buộc nhập mật khẩu hiện tại, không dùng OTP; sai 5 lần thì khóa chức năng 15 phút. Quên mật khẩu là cách duy nhất dùng OTP; tài khoản mới đặt mật khẩu lần đầu qua Quên mật khẩu. |
| BR42 ✎ | Quên mật khẩu luôn hiển thị cùng một câu thông báo; không gửi OTP cho email không tồn tại, tài khoản đã xóa, đang khóa hoặc tài khoản Admin. Tối đa 5 yêu cầu mỗi giờ cho một email và 20 yêu cầu mỗi giờ cho một IP. Mã OTP gắn với mục đích sử dụng. |
| BR43 | *(đã xóa 16/11 – khôi phục mật khẩu Admin do hệ thống nhân sự lớn xử lý; không còn cửa sổ đặt lại 30 phút và 72 giờ đầu)* |
| BR44 | Tài khoản Nhân viên thử việc kết luận Không đạt bị tự khóa sau ngày kết thúc thử việc. Kết luận Đạt chuyển sang "Chờ Admin xử lý": Admin gán vai trò nghiệp vụ hoặc khóa với lý do "Hoàn thành thử việc". |
| BR45 | Thay đổi cấu hình chỉ áp dụng cho thao tác phát sinh sau thời điểm lưu. |
| BR46 | Mẫu email phải giữ đủ biến bắt buộc của từng loại; giá trị của biến được escape khi gửi (NFR15, NFR18). |
| BR47 | Các giá trị số trong BR09, BR16, BR18, BR21, BR23, BR25, BR26 là giá trị mặc định; Admin thay đổi được trong khoảng cho phép hiển thị ở UC5.13–UC5.16. |
| BR48 ✎ | Ứng viên phản hồi lời mời phỏng vấn (xác nhận, yêu cầu đổi lịch, từ chối) trong thời hạn BR23; quá hạn thì hồ sơ tự chuyển Từ chối phỏng vấn và sự kiện lịch bị hủy (BR24). |
| BR49 ✎ | Ứng viên có thể yêu cầu đổi lịch kèm ghi chú bắt buộc tối đa 500 ký tự (ví dụ khung giờ mong muốn); mỗi hồ sơ tối đa 2 lần (đếm trong nhật ký). |
| BR50 ✎ | Yêu cầu đổi lịch chuyển buổi phỏng vấn sang trạng thái Yêu cầu đổi lịch; HR phải xếp lại trong 1 ngày làm việc, quá hạn hệ thống nhắc HR. Hệ thống không tự đổi lịch. |
| BR51 | Mỗi lần HR xếp lại lịch, link xác nhận cũ hết hiệu lực và ứng viên nhận link mới với thời hạn phản hồi mới. |
| BR52 | Khi qua giờ bắt đầu buổi đã xác nhận, hồ sơ chuyển Chờ kết quả phỏng vấn. Chỉ người phỏng vấn được giao hoặc HR nhập kết quả, sau giờ bắt đầu, trong 2 ngày làm việc (quá hạn nhắc HR). Kết quả đã lưu không sửa được. |
| BR53 ✎ | Lời mời thử việc: ngày bắt đầu là ngày làm việc, sau hạn phản hồi ít nhất 1 ngày làm việc; thời gian thử việc 1–180 ngày, HR chịu trách nhiệm áp đúng mức tối đa theo vị trí (Điều 25 Bộ luật Lao động 2019); quản lý bộ phận phụ trách cùng phòng ban với tin. |
| BR54 | Ứng viên vắng mặt: ghi nhận vắng mặt, hồ sơ Không đạt phỏng vấn, gửi thư cảm ơn; hệ thống không tự xếp lại lịch. |
| BR55 | Hủy lịch phỏng vấn bắt buộc có lý do; hồ sơ trở về Chờ HR duyệt để HR quyết định mời lại hoặc từ chối. |
| BR56 ✎ | Đợt thử việc được tạo khi Admin cấp tài khoản thử việc cho hồ sơ Chờ cấp tài khoản; ngày kết thúc = ngày bắt đầu + thời gian thử việc trong lời mời. Quản lý phụ trách là quản lý trong lời mời. |
| BR57 | Task: tiêu đề bắt buộc tối đa 200 ký tự, mô tả tối đa 5.000 ký tự, tối đa 5 tệp đính kèm mỗi tệp ≤ 10 MB; hạn nộp không ở quá khứ và không sau ngày kết thúc thử việc. Chỉ giao task khi đợt đang diễn ra. |
| BR58 | Task chỉ được cập nhật khi chưa có kết quả đánh giá và chỉ được xóa khi chưa có bài nộp (xóa mềm, bắt buộc lý do). Bài nộp đã đánh giá bị khóa, không sửa được. |
| BR59 | Đánh giá bài nộp chỉ có Đạt hoặc Không đạt; Không đạt bắt buộc có nhận xét. Mỗi task có một bài nộp và một lần đánh giá. |
| BR60 | Quản lý được kết luận từ 5 ngày làm việc trước ngày kết thúc thử việc; mọi bài nộp phải được đánh giá trước. Từ 3 ngày làm việc trước ngày kết thúc, hệ thống nhắc quản lý hằng ngày; quá ngày kết thúc chưa kết luận thì nhắc cả HR. |
| BR61 | Kết luận thử việc chỉ có Đạt hoặc Không đạt, bắt buộc nhận xét, không sửa được sau khi lưu; mọi task và bài nộp của đợt bị khóa. |
| BR62 | Bài nộp là link https hoặc tệp (≤ 20 MB, định dạng cho phép: pdf, docx, xlsx, pptx, zip, png, jpg); nộp sau hạn vẫn được nhận nhưng gắn nhãn Nộp muộn. Hệ thống nhắc nhân viên 1 ngày làm việc trước hạn nộp. |
