# Hướng dẫn nhanh Prototype

Cách chạy và trải nghiệm prototype HR_Chan hiện tại: backend FastAPI đã có xác thực,
quản trị tài khoản và nhật ký kiểm toán; frontend React với các màn hình nghiệp vụ
vẫn dùng dữ liệu minh họa.

Tài liệu chi tiết: [xác thực](authentication.md),
[phát triển cục bộ](local-development.md), [kiến trúc](../architecture/overview.md).

## Yêu cầu

Python 3.12+ với `uv`, Node.js 22.12+ với `pnpm`, Docker và `openssl`.

## 1. Khởi động database và hộp thư

Từ thư mục gốc của repository:

```sh
POSTGRES_PORT=55432 docker compose up -d --wait db
docker compose --profile mail up -d
```

Dùng cổng 55432 khi 5432 đã bị chiếm; nếu không thì bỏ `POSTGRES_PORT`.
Mailpit bắt toàn bộ email của hệ thống ngay trên máy.

| URL | Mục đích |
| --- | --- |
| `http://localhost:5173` | Ứng dụng web (cổng ứng viên `/`, workspace `/app`) |
| `http://localhost:8000/docs` | Tài liệu API |
| `http://localhost:8000/health` | Kiểm tra sống (không cần database hay secret) |
| `http://127.0.0.1:8025` | Hộp thư Mailpit (link lời mời, khôi phục, đặt lại) |

## 2. Cấu hình backend

Tạo `backend/.env` từ `backend/.env.example`, đặt `DATABASE_URL` khớp cổng Compose
rồi sinh hai secret bắt buộc:

```sh
cd backend
printf 'JWT_SECRET=%s\nLIMITER_SECRET=%s\n' \
  "$(openssl rand -base64 48)" "$(openssl rand -base64 48)" >> .env
```

Các cờ phục vụ prototype (giữ `false` khi có dữ liệu thật):

```dotenv
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:55432/hr_chan
FRONTEND_URL=http://localhost:5173
TRUSTED_ORIGINS=["http://localhost:5173"]
CORS_ORIGINS=["http://localhost:5173"]
DEV_SEED_ENABLED=true
DEV_LOGIN_ENABLED=true
SMTP_HOST=localhost
SMTP_PORT=1025
```

API đọc `backend/.env` bất kể thư mục làm việc hiện tại, và chỉ nạp lại khi tiến
trình khởi động lại.

## 3. Chuẩn bị database và tài khoản demo

```sh
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed-dev-accounts
```

`seed-dev-accounts` tạo (hoặc khôi phục) năm tài khoản `dev.*` với mật khẩu dùng
chung `dev-only-password` và trạng thái `ACTIVE`.

## 4. Chạy hai ứng dụng

```sh
# terminal 1
cd backend && uv run uvicorn app.main:app --reload

# terminal 2
cd frontend && pnpm install --frozen-lockfile && pnpm run dev
```

Mở `http://localhost:5173/login`. Nếu cổng 8000/5173 đã bị chiếm, chạy backend với
`--port 8001`, frontend bằng `VITE_PROXY_TARGET=http://127.0.0.1:8001 pnpm dev
--port 5174`, và trỏ `FRONTEND_URL`/`TRUSTED_ORIGINS` sang cổng frontend mới.

## 5. Đăng nhập

Trang đăng nhập hiển thị khối **Đăng nhập nhanh (chỉ môi trường dev)**. Các nút mở
session thật qua `/auth/dev-login` mà không cần mật khẩu, nên đổi mật khẩu tài
khoản fixture cũng không làm hỏng nút.

| Nút | Tài khoản | Đi tới |
| --- | --- | --- |
| Admin | `dev.admin@sis.hust.edu.vn` | `/app/admin/users` |
| HR | `dev.hr@sis.hust.edu.vn` | `/app/hr` |
| Interviewer | `dev.interviewer@sis.hust.edu.vn` | `/app/interviewer` |
| Manager | `dev.manager@sis.hust.edu.vn` | `/app/manager` |
| Trainee | `dev.trainee@sis.hust.edu.vn` | `/app/trainee` |

Vẫn đăng nhập bằng email/mật khẩu được: thử `dev.hr@sis.hust.edu.vn` /
`dev-only-password`, hoặc tự tạo Admin bằng
`uv run python -m app.cli bootstrap-admin --email admin@sis.hust.edu.vn --name 'Initial Administrator'`
rồi hoàn tất lời mời trong Mailpit.

## 6. Những luồng nên thử

- **Phiên đăng nhập:** đăng nhập, mở tab thứ hai, reload cả hai, rồi đăng xuất ở một
  tab — tab còn lại quay về `/login`. Access token chỉ nằm trong bộ nhớ.
- **Phân quyền theo vai trò:** đăng nhập Trainee hoặc Interviewer rồi mở `/app/hr`
  bằng URL; workspace hiển thị bảng từ chối truy cập thay vì nội dung mục đó.
- **Quản trị tài khoản:** với Admin, tạo nhân viên, thay thế toàn bộ vai trò, khóa
  kèm lý do, mở khóa, vô hiệu hóa. Nút tự khóa/tự vô hiệu hóa bị vô hiệu trong UI.
  Khi gửi email thất bại, chỉ tài khoản `PENDING_SETUP`/chờ đặt lại mới có nút gửi lại.
- **Vòng đời mật khẩu:** yêu cầu khôi phục ở `/forgot-password`, mở email mới nhất
  trong Mailpit, đặt mật khẩu mới ở `/set-password`, rồi đăng nhập lại. Tài khoản
  đang khóa phải mở khóa trước; link đã dùng hoặc hết hạn báo lỗi an toàn.
- **Đổi mật khẩu:** `/app/account` chỉ giữ phiên hiện tại và thu hồi các thiết bị khác.
- **Nhật ký kiểm toán:** `/app/admin/logs` liệt kê metadata thật (`auth.login.*`,
  `account.*`, `auth.dev_login`, ...) với bộ lọc hành động/actor/đối tượng và phân
  trang bằng cursor. Không có nội dung CV hay đánh giá.

## 7. Kiểm chứng prototype

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
TEST_DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:55432/hr_chan_test uv run pytest

cd ../frontend
pnpm run typecheck
pnpm test
pnpm run build
```

Test trình duyệt là tùy chọn, cần backend đang chạy, Mailpit và database riêng; xem
[mục kiểm chứng trong hướng dẫn xác thực](authentication.md#verification).

## Giới hạn

- Cổng ứng viên và các workspace nghiệp vụ (HR, phỏng vấn, thử việc, báo cáo) dùng
  dữ liệu minh họa đóng gói trong ứng dụng. Đây là dữ liệu demo, không phải bản ghi
  được API bảo vệ; chỉ xác thực, tài khoản và kiểm toán nói chuyện với backend.
- Các màn hình bàn giao công việc và cấu hình hệ thống cố ý không được định tuyến.
- Đăng nhập nhanh chỉ dành cho dev: khối nút không có trong bản build production và
  route backend trả `404` nếu `DEV_LOGIN_ENABLED` không bật.
- Không có đăng ký công khai, đổi email/loại tài khoản, phục hồi tài khoản đã vô hiệu
  hóa, MFA/SSO, hay gửi email thật.
