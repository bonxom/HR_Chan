# 03. Glossary và yêu cầu phi chức năng (FURPS)

> **Bản chốt cuối 16/11/2026.** Bản Markdown của `Glossary_va_Dac_ta_bo_sung.docx` (28/10/2026), đã áp đợt rút gọn 03/11 và quyết định bỏ trích dẫn 04/11: Glossary còn **63 thuật ngữ** (xóa Công việc đang dở, Người nhận hợp lệ, Khóa khẩn cấp, Chờ chuyển giao, OCR, Trích dẫn bằng chứng, Cửa sổ đặt lại; đổi "Khung giờ đề xuất" thành "Ghi chú đổi lịch"); sửa NFR09, NFR16, NFR22, NFR29, NFR34, NFR37 (đánh dấu ✎); xóa NFR32 (16/11), còn **42 NFR**. Đây là Glossary duy nhất của dự án; không định nghĩa lại thuật ngữ ở tài liệu khác. Nếu nhóm còn dùng file .docx gốc, file đó phải sửa theo tài liệu này.

## Glossary

### A. Tác nhân và vai trò

| Thuật ngữ | Định nghĩa |
|---|---|
| Ứng viên | Người ngoài công ty gửi hồ sơ qua trang tuyển dụng; không có tài khoản, phản hồi qua đường dẫn trong email. |
| Bộ phận tuyển dụng | Tác nhân gồm hai vai trò HR và Người phỏng vấn; dùng chung tài khoản nhân viên, quyền theo vai trò được gán. |
| HR ✎ | Vai trò quản lý tin tuyển dụng, xét duyệt hồ sơ, quản lý lịch phỏng vấn, xem báo cáo. |
| Người phỏng vấn | Vai trò được chỉ định phỏng vấn một vị trí; xem hồ sơ của buổi được giao và nhập kết quả phỏng vấn. |
| Quản lý bộ phận | Vai trò hướng dẫn nhân viên thử việc của phòng ban: giao, đánh giá task và kết luận thử việc. |
| Nhân viên thử việc ✎ | Ứng viên đã nhận lời thử việc, được Admin cấp tài khoản bằng email công ty để nhận task, nộp bài. |
| Admin ✎ | Loại tài khoản riêng chỉ quản trị tài khoản nhân viên, phân quyền, nhật ký và cấu hình; không truy cập dữ liệu nghiệp vụ. Hệ thống con có đúng 1 tài khoản Admin, do hệ thống nhân sự lớn cấp. |
| Vai trò nghiệp vụ | Tập quyền gắn với công việc: HR, Người phỏng vấn, Quản lý bộ phận, Nhân viên thử việc. |
| Google Workspace ✎ | Hệ thống ngoài cung cấp lịch rảnh/bận và sự kiện lịch kèm Google Meet. Không dùng để tạo hộp thư. |
| Google Meet | Dịch vụ họp trực tuyến của Google Workspace, dùng để tổ chức phỏng vấn. |
| Dịch vụ Email | Hệ thống ngoài gửi email từ hệ thống đến ứng viên và nhân viên. |
| Dịch vụ AI | Mô hình ngôn ngữ của nhà cung cấp bên ngoài, được gọi qua AI Agent và MCP server của công ty để phân tích, chấm CV và gợi ý việc làm. |

### B. Thời gian và quy tắc chung

| Thuật ngữ | Định nghĩa |
|---|---|
| Ngày làm việc | Ngày nằm trong lịch làm việc của công ty, không tính cuối tuần và ngày nghỉ lễ đã cấu hình (UC5.13). |
| Giờ làm việc | Khoảng giờ làm việc của từng ngày trong tuần do Admin cấu hình; mọi buổi phỏng vấn phải nằm trong khoảng này. |
| Thời hạn phản hồi | Thời gian ứng viên được phản hồi một lời mời: đến hết giờ làm việc của ngày làm việc thứ 2 sau ngày gửi (mặc định); quá hạn được coi là từ chối (BR23, BR24). |
| Đường dẫn phản hồi | Đường dẫn riêng, chuỗi ngẫu nhiên, dùng một lần, có thời hạn, gửi trong email để ứng viên phản hồi mà không cần tài khoản. Gồm ba loại: xác nhận lịch phỏng vấn, phản hồi lời mời thử việc, đồng ý lưu hồ sơ. |
| OTP | Mã 6 chữ số dùng một lần gửi qua email để xác thực email khi nộp hồ sơ hoặc đặt lại mật khẩu. |
| Nhật ký | Bản ghi chỉ thêm, không sửa, không xóa về thao tác của người dùng: ai, lúc nào, làm gì, với đối tượng nào, vì sao. |
| Biên bản thay đổi | Bản ghi nhật ký của một thao tác quản trị, có giá trị trước và sau khi thay đổi. |

### C. Tuyển dụng và hồ sơ

| Thuật ngữ | Định nghĩa |
|---|---|
| Tin tuyển dụng | Thông tin một vị trí cần tuyển (mô tả, yêu cầu, số lượng, hạn nộp) kèm bộ tiêu chí chấm điểm; trạng thái Nháp, Đang mở hoặc Đã đóng. |
| Bộ tiêu chí chấm điểm | Danh sách tiêu chí, trọng số, ngưỡng tự động mời và người phỏng vấn của một tin. |
| Tiêu chí bắt buộc | Tiêu chí ứng viên phải đáp ứng; không đạt thì hồ sơ chuyển HR duyệt dù tổng điểm cao. |
| Trọng số | Mức độ quan trọng của một tiêu chí, tính bằng %; tổng trọng số của bộ tiêu chí bằng 100%. |
| Phiên bản tiêu chí | Bản lưu của bộ tiêu chí tại một thời điểm; hồ sơ luôn được chấm theo phiên bản hiện hành lúc nộp. |
| Ngưỡng tự động mời phỏng vấn | Điểm tối thiểu (0–100) để hệ thống tự mời phỏng vấn mà không cần HR duyệt. |
| Hồ sơ tạm | Thông tin liên hệ và CV ứng viên đã gửi nhưng chưa nộp vào vị trí nào; bị xóa sau thời gian giữ (BR26). |
| Hồ sơ ứng tuyển | Hồ sơ của một ứng viên nộp vào một vị trí cụ thể, được tạo sau khi xác thực OTP; gồm thông tin liên hệ, CV, điểm AI và trạng thái. |
| Trạng thái hồ sơ | Một trong 14 trạng thái của hồ sơ ứng tuyển, từ Đang chấm điểm đến Đạt/Không đạt thử việc (BR07). |
| Chờ HR duyệt | Trạng thái của hồ sơ dưới ngưỡng, không đạt tiêu chí bắt buộc hoặc AI không chấm được, cần Bộ phận tuyển dụng quyết định. |
| Điểm AI | Tổng điểm (0–100) của hồ sơ, tính bằng code theo trọng số từ điểm từng tiêu chí do AI chấm. |
| Giải trình điểm AI ✎ | Điểm và nhận xét của AI cho từng tiêu chí. |
| Mức độ phù hợp | Tỉ lệ (%) AI đánh giá CV đáp ứng yêu cầu của một vị trí, dùng để gợi ý việc làm. |
| Ngưỡng gợi ý | Mức độ phù hợp tối thiểu để một vị trí được gợi ý cho ứng viên. |
| Đồng ý xử lý dữ liệu | Sự cho phép của ứng viên để công ty xử lý dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP. |
| Đồng ý lưu hồ sơ | Sự cho phép của ứng viên để công ty giữ hồ sơ 12 tháng và liên hệ khi có vị trí phù hợp. |
| Phễu tuyển dụng | Biểu đồ số ứng viên còn lại qua từng bước, từ gửi hồ sơ đến đạt thử việc. |
| Tỉ lệ chuyển đổi | Tỉ lệ số hồ sơ sang được bước sau so với bước trước trong phễu tuyển dụng. |

### D. Phỏng vấn

| Thuật ngữ | Định nghĩa |
|---|---|
| Buổi phỏng vấn | Một lần hẹn phỏng vấn của một hồ sơ: người phỏng vấn, giờ, link Google Meet, trạng thái. |
| Ghi chú đổi lịch ✎ | Ghi chú bắt buộc (tối đa 500 ký tự) ứng viên gửi khi yêu cầu đổi lịch, ví dụ khung giờ mong muốn; tối đa 2 lần mỗi hồ sơ. Thay cho "Khung giờ đề xuất" (03/11). |
| Yêu cầu đổi lịch ✎ | Trạng thái buổi phỏng vấn khi ứng viên yêu cầu đổi lịch kèm ghi chú, chờ HR xếp lại trong 1 ngày làm việc; hệ thống không tự đổi lịch. |
| Cần cập nhật lịch thủ công | Đánh dấu khi Google Workspace lỗi, HR phải sửa sự kiện trên lịch bằng tay. |
| Phiếu đánh giá phỏng vấn | Đánh giá từng tiêu chí của tin theo mức 1–5 kèm ghi chú và nhận xét chung. |
| Vắng mặt | Ứng viên không tham dự buổi đã xác nhận; được ghi nhận như Không đạt phỏng vấn. |
| Lời mời thử việc | Thư gửi ứng viên đạt phỏng vấn: ngày bắt đầu, thời gian thử việc, địa điểm, quản lý, đường dẫn phản hồi. |

### E. Thử việc

| Thuật ngữ | Định nghĩa |
|---|---|
| Thời gian thử việc | Số ngày thử việc (1–180), tối đa theo Điều 25 Bộ luật Lao động 2019. |
| Hộp thư công ty ✎ | Email thuộc tên miền công ty, do bộ phận IT / hệ thống nhân sự lớn tạo bên ngoài hệ thống; với nhân viên thử việc, Admin nhập địa chỉ này khi cấp tài khoản. |
| Đợt thử việc | Khoảng thời gian thử việc của một nhân viên: ngày bắt đầu, ngày kết thúc, quản lý phụ trách, kết luận. |
| Task thử việc | Công việc quản lý bộ phận giao cho nhân viên thử việc, có hạn nộp. |
| Bài nộp | Đường dẫn hoặc tệp nhân viên nộp cho một task; mỗi task có một bài nộp. |
| Nộp muộn | Nhãn gắn cho bài nộp sau hạn nộp của task. |
| Đánh giá bài nộp | Kết quả Đạt / Không đạt kèm nhận xét của quản lý cho một bài nộp; không sửa được sau khi lưu. |
| Tổng hợp kết quả thử việc | Thống kê các task của đợt: Đạt, Không đạt, chờ đánh giá, chưa nộp, nộp muộn, tỉ lệ Đạt. |
| Kết luận thử việc | Quyết định cuối cùng Đạt / Không đạt của quản lý bộ phận cho đợt thử việc. |

### F. Tài khoản và quản trị

| Thuật ngữ | Định nghĩa |
|---|---|
| Chờ cấp tài khoản ✎ | Trạng thái hồ sơ đã nhận lời thử việc, chờ Admin nhập email công ty để hệ thống tạo tài khoản Nhân viên thử việc và đợt thử việc (bước của luồng chính, không phải nhánh lỗi). |
| Chờ Admin xử lý | Trạng thái tài khoản Nhân viên thử việc đã đạt, chờ Admin gán vai trò mới hoặc khóa. |
| Ẩn danh hóa | Xóa thông tin cá nhân nhưng giữ mã tài khoản để lịch sử vẫn truy vết được. |
| Phiên đăng nhập | Khoảng thời gian người dùng đã đăng nhập; hết hạn sau thời gian không thao tác. |
| Xóa mềm | Ẩn bản ghi khỏi giao diện nhưng vẫn giữ trong cơ sở dữ liệu để truy vết. |

### G. Kỹ thuật và mô hình hóa

| Thuật ngữ | Định nghĩa |
|---|---|
| Hộp thư đi (email outbox) | Bảng lưu email chờ gửi; email được ghi cùng giao dịch với thao tác nghiệp vụ, rồi tác vụ nền gửi và thử lại theo BR11. Không mất email khi Dịch vụ Email lỗi và không gửi email cho thao tác đã bị hủy. |
| Schema kết quả | Cấu trúc dữ liệu cố định mà AI phải trả về để hệ thống kiểm tra được. |
| CAPTCHA | Kiểm tra phân biệt người thật với chương trình tự động. |
| Prompt injection | Kỹ thuật chèn câu lệnh vào dữ liệu (ví dụ CV) để điều khiển AI làm sai. |
| Extension point | Vị trí trong luồng của use case cơ sở nơi use case mở rộng («extend») được chèn vào. |

## Supplementary Specification (42 NFR; NFR32 đã xóa 16/11)

### Functionality (chức năng chung, bảo mật, tuân thủ)

| Mã | Yêu cầu | Use case liên quan | Cách kiểm tra |
|---|---|---|---|
| NFR05 | Chỉ tài khoản có vai trò HR truy cập được nhóm chức năng này; vai trò Người phỏng vấn chỉ xem hồ sơ được giao (nhóm Phỏng vấn); tài khoản Admin không truy cập dữ liệu nghiệp vụ (BR29). | Nhóm 1, UC3.07 | Đăng nhập bằng vai trò khác, kiểm tra bị từ chối |
| NFR06 | Ghi nhật ký mọi lần xem hồ sơ và mọi quyết định xét duyệt. | UC1.06–UC1.08, UC3.07 | Thực hiện thao tác, kiểm tra bảng nhật ký |
| NFR07 | CV được mã hóa khi lưu trữ; mọi kết nối dùng HTTPS. | UC2.01, mọi UC | Kiểm tra cấu hình lưu trữ và chứng chỉ |
| NFR08 | Xử lý dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP; chỉ lưu hồ sơ cho đợt sau khi ứng viên đồng ý. | UC2.01, UC2.03, UC2.13 | Rà soát luồng đồng ý và dữ liệu lưu |
| NFR13 | Mọi dữ liệu nhập được kiểm tra định dạng và độ dài ở phía server, kể cả khi phía client đã kiểm tra. | Mọi UC | Gửi request bỏ qua giao diện; dữ liệu sai phải bị từ chối |
| NFR14 | Mọi truy vấn CSDL dùng tham số hóa hoặc ORM; không nối chuỗi SQL. | Mọi UC | Rà soát mã nguồn; nhập ' OR 1=1 -- vào các ô nhập |
| NFR15 | Mọi dữ liệu do người dùng nhập được escape khi hiển thị trên web và trong email; dữ liệu lưu nguyên văn. | Mọi UC | Nhập <script>alert(1)</script> vào họ tên, lý do từ chối thử việc; không được thực thi |
| NFR16 ✎ | Nội dung CV được xử lý như dữ liệu, không như chỉ dẫn cho AI; kết quả AI phải đúng schema, sai schema thì hồ sơ chuyển HR duyệt. | UC2.01, UC2.02, UC2.08, UC4.02, UC4.09 | Nộp CV chứa câu lệnh điều khiển AI; điểm không thay đổi bất thường |
| NFR17 | File CV được kiểm tra loại thật theo nội dung, quét virus, lưu ngoài thư mục web với tên ngẫu nhiên. | UC2.01, UC4.02, UC4.09 | Tải lên file .exe đổi đuôi thành .pdf; phải bị từ chối |
| NFR18 | Dữ liệu đưa vào email được loại bỏ ký tự xuống dòng ở phần header. | Mọi UC có gửi email | Nhập họ tên chứa \r\nBcc:; email không có thêm người nhận |
| NFR22 ✎ | Link phản hồi dùng chuỗi ngẫu nhiên tối thiểu 128 bit; OTP lưu dạng băm. | UC2.06, UC2.10 | Kiểm tra mã nguồn và dữ liệu lưu trữ |
| NFR23 | Thu thập đồng ý trước khi xử lý dữ liệu; xóa hồ sơ tạm sau 24 giờ; xóa hồ sơ lưu khi hết 12 tháng hoặc khi ứng viên rút đồng ý. | UC2.01, UC2.13 | Kiểm tra tác vụ xóa định kỳ và luồng rút đồng ý |
| NFR26 | Phân quyền theo vai trò được kiểm tra ở server cho mọi API; tài khoản Admin bị từ chối khi gọi API dữ liệu nghiệp vụ. | Mọi UC | Gọi API hồ sơ bằng tài khoản Admin và tài khoản thiếu vai trò; phải bị từ chối |
| NFR27 | Mật khẩu lưu bằng bcrypt hoặc argon2; phiên hết hạn sau 30 phút không thao tác (cấu hình được); đăng nhập sai 5 lần khóa tạm 15 phút. | UC5.17, UC5.18 | Kiểm tra CSDL; để phiên rảnh 30 phút; đăng nhập sai 5 lần |
| NFR28 | Khóa tài khoản và đổi mật khẩu thu hồi mọi phiên trong ≤ 1 phút. | UC5.05, UC5.17 | Khóa tài khoản đang đăng nhập ở trình duyệt khác; thao tác kế tiếp bị từ chối |
| NFR29 ✎ | Email Admin bật xác thực hai lớp ở Google Workspace. | UC5.17 | Rà soát cấu hình Google Workspace |
| NFR30 | Mọi thao tác quản trị và mọi lần xem hồ sơ được ghi nhật ký; nhật ký chỉ cho phép thêm, không sửa, không xóa. | UC5.10, UC5.11 | Thử cập nhật bản ghi nhật ký qua API và CSDL bằng quyền ứng dụng |
| NFR36 | Người chỉ có vai trò Người phỏng vấn chỉ xem được hồ sơ của buổi được giao cho mình. | UC3.07, UC3.08 | Mở hồ sơ của buổi khác bằng URL trực tiếp; phải bị từ chối |
| NFR40 | Quản lý chỉ truy cập đợt thử việc mình phụ trách; nhân viên chỉ truy cập task và kết quả của chính mình. | UC4.01–UC4.10 | Mở task của người khác bằng URL trực tiếp; phải bị từ chối |
| NFR41 | Tệp đính kèm và bài nộp không truy cập công khai; chỉ tải qua đường dẫn ký có thời hạn ≤ 15 phút. | UC4.05, UC4.08 | Dùng lại đường dẫn tải sau 15 phút; phải bị từ chối |

### Usability (khả năng sử dụng)

| Mã | Yêu cầu | Use case liên quan | Cách kiểm tra |
|---|---|---|---|
| NFR09 ✎ | Mọi điểm AI hiển thị kèm điểm và nhận xét của từng tiêu chí. | UC1.08, UC3.07 | Kiểm tra ngẫu nhiên 20 hồ sơ |
| NFR11 | Giao diện tiếng Việt; lỗi nhập liệu báo tại đúng trường; ra quyết định xét duyệt trong ≤ 3 thao tác sau khi xem chi tiết. | Mọi UC của Bộ phận tuyển dụng | Kiểm thử với người dùng |
| NFR24 | Trang ứng tuyển dùng tốt trên điện thoại (màn hình từ 360px); form gửi hồ sơ không quá 5 trường nhập. | UC2.01–UC2.05 | Kiểm thử trên điện thoại Android và iOS |
| NFR37 ✎ | Trang xác nhận lịch dùng tốt trên điện thoại (từ 360px), hiển thị giờ theo múi giờ Việt Nam, tải trong ≤ 2 giây. | UC3.01 | Kiểm thử trên điện thoại Android và iOS |

### Reliability (độ tin cậy)

| Mã | Yêu cầu | Use case liên quan | Cách kiểm tra |
|---|---|---|---|
| NFR03 | Lỗi Google Workspace hoặc dịch vụ email không làm mất quyết định của HR; email gửi qua hàng đợi, thử lại theo BR11. | UC1.09, UC1.10 | Giả lập dịch vụ ngoài lỗi, kiểm tra trạng thái hồ sơ và hàng đợi |
| NFR04 | Mọi lời gọi dịch vụ ngoài có thời gian chờ tối đa 10 giây. | Mọi UC gọi Google Workspace, Dịch vụ Email, Dịch vụ AI | Giả lập dịch vụ phản hồi chậm |
| NFR10 | Phát hiện xung đột khi hai người sửa cùng tin hoặc xử lý cùng hồ sơ. | UC1.03, UC1.07 | Mở cùng tin trên hai phiên, lưu lần lượt |
| NFR21 | Chấm điểm và tự động mời chạy qua hàng đợi nền; lỗi dịch vụ AI, Google hoặc email không làm mất hồ sơ đã nộp. | UC2.05, UC2.08, UC2.09 | Giả lập dịch vụ ngoài lỗi; hồ sơ phải chuyển Chờ HR duyệt |
| NFR31 | Thay đổi cấu hình có hiệu lực trong ≤ 1 phút trên mọi máy chủ. | UC5.12–UC5.16 | Đổi thời hạn OTP, gửi OTP mới sau 1 phút |
| NFR33 | Tác vụ định kỳ xử lý lời mời quá hạn phản hồi chạy ít nhất 15 phút một lần; hồ sơ được chuyển trạng thái trong ≤ 15 phút sau khi hết hạn. | UC2.10, UC2.11, UC2.13, UC3.01 | Tạo lời mời có thời hạn ngắn trên môi trường thử, kiểm tra trạng thái và lịch sau khi hết hạn |
| NFR34 ✎ | Mọi thay đổi lịch (xác nhận, đổi giờ, hủy) đồng bộ lên Google Calendar trong ≤ 1 phút; lỗi đồng bộ được đánh dấu để xử lý thủ công. | UC3.01, UC3.03–UC3.05 | Đổi giờ trên hệ thống, kiểm tra sự kiện Google sau 1 phút; giả lập Google lỗi |
| NFR35 | Không thể lưu hai buổi phỏng vấn trùng giờ của cùng một người phỏng vấn, kể cả khi hai yêu cầu đến cùng lúc. | UC1.09, UC2.09, UC3.04 | Gửi đồng thời hai yêu cầu xếp cùng giờ; chỉ một yêu cầu thành công |
| NFR38 | Tác vụ định kỳ chuyển hồ sơ sang Chờ kết quả phỏng vấn, xử lý quá hạn phản hồi và nhắc nhập kết quả chạy ít nhất 15 phút một lần. | UC3.08 | Tạo buổi phỏng vấn đã qua giờ trên môi trường thử, kiểm tra trạng thái sau 15 phút |
| NFR42 | Việc khóa bài nộp sau khi đánh giá và khóa đợt sau khi kết luận được thực thi ở cơ sở dữ liệu, không chỉ ở giao diện. | UC4.05, UC4.07 | Gọi API sửa bài đã đánh giá; phải bị từ chối |
| NFR43 | Tác vụ nhắc hạn nộp và nhắc kết luận chạy mỗi ngày làm việc lúc đầu giờ làm việc; không gửi trùng nhắc trong cùng ngày. | UC4.08, UC4.07 | Chạy tác vụ hai lần trong ngày trên môi trường thử; chỉ một email |

### Performance (hiệu năng)

| Mã | Yêu cầu | Use case liên quan | Cách kiểm tra |
|---|---|---|---|
| NFR01 | Danh sách tin và hồ sơ hiển thị trong ≤ 2 giây với 10.000 hồ sơ. | UC1.01, UC1.06 | Kiểm thử tải với 10.000 hồ sơ mẫu, đo thời gian phản hồi |
| NFR02 | Báo cáo 12 tháng hiển thị trong ≤ 5 giây; xuất file trong ≤ 10 giây. | UC1.11–UC1.15 | Đo thời gian với dữ liệu 12 tháng |
| NFR19 | Từ lúc gửi hồ sơ đến khi hiển thị gợi ý việc làm ≤ 15 giây. | UC2.01–UC2.03 | Đo với CV 2 trang và 20 tin đang mở |
| NFR20 | Email OTP đến hộp thư trong ≤ 30 giây; hồ sơ đạt ngưỡng nhận thư mời phỏng vấn trong ≤ 10 phút sau khi nộp. | UC2.06, UC2.09 | Đo thời gian trên môi trường thử nghiệm |
| NFR39 | Tải tệp bài nộp 20 MB hoàn tất trong ≤ 30 giây với đường truyền 10 Mbps; có thanh tiến trình. | UC4.09, UC4.10 | Tải tệp 20 MB trên môi trường thử |

### Supportability (hỗ trợ, vận hành, ràng buộc)

| Mã | Yêu cầu | Use case liên quan | Cách kiểm tra |
|---|---|---|---|
| NFR12 | Chạy trên Chrome, Edge, Firefox phiên bản mới nhất, màn hình từ 1280px. | Mọi UC | Kiểm thử trên từng trình duyệt |
| NFR25 | Chỉ gọi dịch vụ AI sau khi dữ liệu nhập hợp lệ và CAPTCHA đúng; giới hạn độ dài văn bản CV gửi cho AI. | UC2.01–UC2.03, UC2.08 | Gửi dữ liệu sai; kiểm tra không có lời gọi AI |
