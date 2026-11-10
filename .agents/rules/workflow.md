---
trigger: always_on
description: "Quy trình phát triển phần mềm bắt buộc: Brainstorm -> Spec -> Plan -> Test -> Code -> Test"
---

# Quy trình phát triển bắt buộc (Engineering Workflow)

Mọi agent làm việc trong repository này **BẮT BUỘC** tuân thủ nghiêm ngặt chu trình 6 bước:
`Brainstorm -> Spec -> Plan -> Test (Red) -> Code (Green) -> Test (Refactor & Verify)`

Tuyệt đối không nhảy cóc, không viết code triển khai trước khi có spec và plan được người dùng duyệt, không viết code khi chưa có test thất bại.

1. **Brainstorm (Làm rõ & Khảo sát)**:
   - Đọc kỹ mã nguồn và tài liệu liên quan trước khi phản hồi.
   - Đặt câu hỏi làm rõ yêu cầu, luồng nghiệp vụ, tác nhân và ràng buộc; không tự suy đoán nghiệp vụ.
   - Trình bày các phương án kỹ thuật khả thi kèm ưu / nhược điểm để người dùng lựa chọn.
   - Áp dụng skill `brainstorming`.
2. **Spec (Đặc tả kỹ thuật)**:
   - Soạn thảo spec chi tiết: phạm vi (in-scope / out-of-scope), API contract (Pydantic schemas, HTTP status codes), cấu trúc lưu trữ / model (nếu có), luồng xử lý qua các tầng (`router -> service -> repository`).
   - Trình bày spec rõ ràng và **chờ người dùng xác nhận duyệt spec** trước khi bước tiếp.
3. **Plan (Lập kế hoạch triển khai)**:
   - Cắt nhỏ việc triển khai thành danh sách các nhiệm vụ nguyên tử (atomic tasks), chỉ rõ file tạo/sửa và tiêu chí hoàn thành từng bước.
   - Áp dụng skill `writing-plans`. Trình bày plan và nhận sự đồng thuận từ người dùng.
4. **Test - Red (Viết test trước)**:
   - Viết bài test (pytest cho backend, test/typecheck cho frontend) phản ánh đúng hành vi kỳ vọng trong spec trước khi viết mã nguồn tính năng.
   - Chạy test và chứng minh test **FAIL (Red)** với lý do hợp lệ.
   - Áp dụng skill `test-driven-development`.
5. **Code - Green (Triển khai mã tối thiểu)**:
   - Chỉ viết vừa đủ mã nguồn để bài test chuyển sang **PASS (Green)**.
   - Không tự ý thêm tính năng hoặc logic ngoài phạm vi kế hoạch đã duyệt.
6. **Test - Refactor & Verify (Kiểm chứng & Tối ưu)**:
   - Chạy kiểm tra tĩnh và kiểm thử đầy đủ: `uv run ruff check .`, `uv run pytest`, `npm run typecheck`, `npm run build`.
   - Refactor mã nguồn sạch sẽ, không làm hỏng test (no regression).
   - Áp dụng skill `verification-before-completion` trước khi bàn giao cho người dùng.
