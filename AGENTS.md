# Hướng dẫn làm việc với HR_Chan

## Phạm vi và nguyên tắc

- Hướng dẫn này áp dụng cho toàn bộ repository. Đọc mã hiện có và `README.md` trước khi chỉnh sửa; yêu cầu trực tiếp của người dùng được ưu tiên.
- Giữ tên định danh trong mã theo quy ước của dự án.
- Giữ nguyên thay đổi có sẵn của người dùng; không reset, ghi đè hoặc xóa phần việc không liên quan.
- Không tự suy diễn nghiệp vụ tuyển dụng, onboarding hoặc thiết kế database. Không sinh CRUD, dữ liệu mẫu, model, trường dữ liệu hay quan hệ chỉ để minh họa.
- File hoặc thư mục giữ chỗ có thể để rỗng. Chỉ triển khai khi có yêu cầu nghiệp vụ cụ thể; hỏi lại nếu thiếu thông tin ảnh hưởng đến hợp đồng API hoặc cấu trúc dữ liệu.

## Quy trình phát triển bắt buộc (Engineering Workflow)

Mọi agent làm việc trong repository này **BẮT BUỘC** tuân thủ nghiêm ngặt chu trình 6 bước:
$$\text{Brainstorm} \longrightarrow \text{Spec} \longrightarrow \text{Plan} \longrightarrow \text{Test (Red)} \longrightarrow \text{Code (Green)} \longrightarrow \text{Test (Refactor \& Verify)}$$

Tuyệt đối không nhảy cóc, không viết code triển khai trước khi có spec và plan được người dùng duyệt, không viết code khi chưa có test thất bại.

1. **Brainstorm (Làm rõ & Khảo sát)**:
   - Đọc kỹ mã nguồn và tài liệu liên quan trước khi phản hồi.
   - Đặt câu hỏi làm rõ yêu cầu, luồng nghiệp vụ, tác nhân và ràng buộc; không tự suy đoán nghiệp vụ.
   - Trình bày các phương án kỹ thuật khả thi kèm ưu / nhược điểm để người dùng lựa chọn.
   - Kích hoạt kỹ năng `brainstorming`.
2. **Spec (Đặc tả kỹ thuật)**:
   - Soạn thảo spec chi tiết: phạm vi (in-scope / out-of-scope), API contract (Pydantic schemas, HTTP status codes), cấu trúc lưu trữ / model (nếu có), luồng xử lý qua các tầng (`router -> service -> repository`).
   - Trình bày spec thành các phần dễ theo dõi và **chờ người dùng xác nhận duyệt spec** trước khi bước tiếp.
3. **Plan (Lập kế hoạch triển khai)**:
   - Cắt nhỏ việc triển khai thành danh sách các nhiệm vụ nguyên tử (atomic tasks), chỉ rõ file tạo/sửa và tiêu chí hoàn thành từng bước.
   - Kích hoạt kỹ năng `writing-plans`. Trình bày plan và nhận sự đồng thuận từ người dùng.
4. **Test - Red (Viết test trước)**:
   - Viết bài test (pytest cho backend, test/typecheck cho frontend) phản ánh đúng hành vi kỳ vọng trong spec trước khi viết mã nguồn tính năng.
   - Chạy test và chứng minh test **FAIL (Red)** với lý do hợp lệ.
   - Kích hoạt kỹ năng `test-driven-development`.
5. **Code - Green (Triển khai mã tối thiểu)**:
   - Chỉ viết vừa đủ mã nguồn để bài test chuyển sang **PASS (Green)**.
   - Không tự ý thêm tính năng hoặc logic ngoài phạm vi kế hoạch đã duyệt.
6. **Test - Refactor & Verify (Kiểm chứng & Tối ưu)**:
   - Chạy kiểm tra tĩnh và kiểm thử đầy đủ: `uv run ruff check .`, `uv run pytest`, `npm run typecheck`, `npm run build`.
   - Refactor mã nguồn sạch sẽ, không làm hỏng test (no regression).
   - Kích hoạt kỹ năng `verification-before-completion` trước khi bàn giao cho người dùng.

## Backend

- Dùng Python 3.12+, FastAPI, Pydantic v2, pydantic-settings và `uv`.
- Tổ chức modular monolith theo tính năng tại `backend/src/app/modules/`.
- `router.py`: endpoint và xử lý HTTP; nhận dependency qua `Depends`.
- `schemas.py`: schema Pydantic cho request/response, tách biệt ORM model.
- `service.py`: quy tắc nghiệp vụ và điều phối các bước xử lý.
- `repository.py`: truy cập dữ liệu; chỉ thêm nội dung khi có nhu cầu lưu trữ đã xác định.
- `models.py`: SQLAlchemy ORM model; chỉ định nghĩa khi schema nghiệp vụ đã rõ.
- Router không truy vấn database hoặc gọi nhà cung cấp AI trực tiếp. Không tạo base repository hoặc generic CRUD framework nếu chưa có nhu cầu thực tế.
- Đăng ký router đã triển khai tại `backend/src/app/api/v1/router.py`. Không import router từ file đang để rỗng.
- Giữ application factory và lifespan trong `main.py`; quản lý session bất đồng bộ qua dependency, transaction ở service. Không tự commit hoặc chạy migration khi khởi động API.
- `/health` phải hoạt động mà không cần database hoặc dịch vụ AI.
- Cấu hình môi trường tại `core/config.py`; xử lý lỗi và logging tập trung trong `core/`.
- Tích hợp LLM, embedding và tìm kiếm vector thông qua các Protocol trong `integrations/`. Không chọn provider hay triển khai thuật toán gợi ý khi chưa có yêu cầu.

## Frontend

- Dùng React, TypeScript, Vite, React Router, TanStack Query và npm; giữ `package-lock.json` đồng bộ khi đổi dependency.
- Theo cách tổ chức của `~/Code/tendoo/Viettel/FE/merchant-cms`. Đường dẫn này chỉ là nguồn tham chiếu nếu có trên máy; không phụ thuộc nó để build và không sao chép cấu hình bí mật hoặc nghiệp vụ của dự án đó.
- `src/App.tsx`: ghép các provider và router của ứng dụng.
- `src/routes/`: tập hợp route; từng feature đặt route của mình trong `routes.tsx` khi triển khai.
- `src/features/`: tổ chức theo nghiệp vụ; trang, component, hook, service và type riêng thuộc feature tương ứng.
- `src/shared/`: component, UI, layout, provider, hook, service, type, utility và hằng số dùng chung.
- `src/configs/`: cấu hình ứng dụng và biến môi trường.
- `src/styles/`: CSS dùng chung; `src/assets/`: tài nguyên import vào mã; `public/`: tài nguyên tĩnh phục vụ trực tiếp.
- `src/stores/`: dành cho trạng thái dùng chung phía client; không thêm thư viện state chỉ để lấp thư mục.
- `src/helper/`: hàm hỗ trợ; tránh tạo tiện ích trùng với `shared/utils`.
- Dùng alias `@/` trỏ tới `src/`, đồng bộ giữa TypeScript và Vite.
- Giữ HTTP client dùng chung tại `shared/services`, URL backend lấy từ cấu hình môi trường. Dùng TanStack Query cho dữ liệu máy chủ.
- Không quay lại cách phân chia cũ với `src/app`, `src/pages`, `src/components`, `src/hooks`, `src/lib` và `src/types` ở cấp gốc.

## Database và trạng thái bộ khung

- PostgreSQL/pgvector là lựa chọn cục bộ mặc định; Docker Compose hiện chỉ chạy database.
- Các file trong module backend `jobs` và `frontend/src/features/jobs/api.ts` đang cố ý để rỗng. Không thêm lại code mẫu Job.
- Migration `0001` hiện chỉ bật extension `vector`, không tạo bảng nghiệp vụ. Schema mới phải xuất phát từ yêu cầu cụ thể.
- Database từng chạy scaffold cũ có thể còn bảng `jobs`. Không tự xóa bảng, reset volume hoặc chạy migration phá hủy dữ liệu để làm khớp bộ khung.
- Trước khi thay đổi migration, kiểm tra lịch sử và khả năng migration đã được áp dụng. Không sửa lịch sử đã dùng chung; thêm migration mới khi cần thay đổi schema đã triển khai.
- Review nội dung Alembic autogenerate trước khi áp dụng. Không mặc định rằng database cục bộ là database dùng một lần.

## Lệnh phát triển và kiểm tra

Tại thư mục gốc:

```sh
docker compose up -d --wait db
```

Nếu cổng 5432 đã được sử dụng, có thể đặt `POSTGRES_PORT=55432` khi chạy Compose và sửa cổng tương ứng trong `backend/.env`. Không dừng dịch vụ khác chỉ để lấy cổng.

Trong `backend/`:

```sh
uv sync
uv run uvicorn app.main:app --reload
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Chỉ chạy `uv run alembic upgrade head` sau khi xác định đúng database đích và kiểm tra migration. Kiểm thử database yêu cầu `TEST_DATABASE_URL` trỏ tới database kiểm thử riêng đã được migrate; nếu không đặt, bài kiểm thử đó được bỏ qua.

Trong `frontend/`:

```sh
npm install
npm run dev
npm run typecheck
npm run build
```

- Dùng `uv sync --frozen` và `npm ci` khi cần cài đúng phiên bản từ lockfile.
- Kiểm tra phù hợp với thay đổi: backend chạy Ruff và pytest; frontend chạy build có kiểm tra TypeScript. Chỉnh tài liệu thuần túy không cần chạy lại toàn bộ test.
- Chỉ thêm test cho hành vi thực tế cần bảo vệ; không tạo nghiệp vụ mẫu để phục vụ test.
- Báo chính xác lệnh đã chạy, lỗi, cảnh báo và bài test bỏ qua. Không trình bày kết quả cũ như kết quả vừa kiểm tra.

## Cấu hình và bàn giao

- Không đưa secret, token, dữ liệu cá nhân hoặc `.env` thật vào Git, log hay tài liệu. `.env.example` chỉ chứa giá trị mẫu an toàn.
- Biến `VITE_*` công khai trong frontend; không dùng để giữ bí mật.
- Không tự commit, push hoặc triển khai khi chưa được yêu cầu.
- Khi đổi cấu trúc hoặc cách chạy, cập nhật README tiếng Việt và chú thích chức năng thư mục tương ứng.
- Khi bàn giao, nêu ngắn gọn phần đã đổi, cách kiểm chứng và phần còn chưa triển khai.

<!-- postman-cli:installation:start -->
Postman CLI đã được cài trên thiết bị và có thể dùng cho công việc phát triển, kiểm tra API.
<!-- postman-cli:installation:end -->
