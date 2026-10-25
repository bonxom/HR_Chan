# HR_Chan

Bộ khung nền tảng tuyển dụng và hội nhập nhân viên mới (onboarding) có hỗ trợ AI.
Dự án tổ chức theo monorepo gồm backend FastAPI và frontend React, ưu tiên cấu trúc
dễ bảo trì và phát triển MVP. Các luồng nghiệp vụ đầy đủ chưa được triển khai.

## Công nghệ và yêu cầu môi trường

- Backend: Python 3.12+, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x bất đồng bộ, asyncpg và Alembic.
- Cơ sở dữ liệu: PostgreSQL và pgvector, chạy cục bộ bằng Docker Compose.
- Frontend: Node.js 22.12+, npm, React, TypeScript, Vite, React Router và TanStack Query.
- Kiểm thử và chất lượng mã: pytest, HTTPX và Ruff.

## Chạy dự án trên máy cá nhân

Tại thư mục gốc của repository:

```sh
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up -d --wait db
```

Mở terminal riêng cho backend:

```sh
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Mở terminal riêng cho frontend:

```sh
cd frontend
npm install
npm run dev
```

| Địa chỉ | Chức năng |
| --- | --- |
| http://localhost:5173 | Giao diện web |
| http://localhost:8000/docs | Tài liệu API tương tác Swagger UI |
| http://localhost:8000/health | Kiểm tra API đang hoạt động; không cần cơ sở dữ liệu hoặc dịch vụ AI |

Hiện chỉ có endpoint `/health`. Các file trong module `jobs` để rỗng, chưa có
endpoint, schema, ORM model hoặc repository nghiệp vụ. Migration chỉ bật pgvector,
không định nghĩa bảng nghiệp vụ.

### Khi cổng PostgreSQL 5432 đã được sử dụng

Chạy cơ sở dữ liệu trên cổng khác:

```sh
POSTGRES_PORT=55432 docker compose up -d --wait db
```

Đồng thời sửa `DATABASE_URL` trong `backend/.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:55432/hr_chan
```

Để giữ cấu hình cổng cho các lần chạy sau, tạo `.env` tại thư mục gốc với nội dung
`POSTGRES_PORT=55432`. Biến `POSTGRES_PASSWORD` của Compose, nếu thay đổi, phải khớp
với mật khẩu trong `DATABASE_URL`. Đổi biến này không tự đặt lại mật khẩu của cơ sở
dữ liệu đã tồn tại trong volume. Mật khẩu ví dụ chỉ dành cho môi trường cục bộ.

### Các tệp môi trường

| Tệp | Mục đích |
| --- | --- |
| `.env` tại thư mục gốc (tùy chọn) | Ghi đè cổng hoặc mật khẩu cho Docker Compose |
| `backend/.env` | Tên API, URL cơ sở dữ liệu, danh sách CORS và mức logging |
| `frontend/.env` | `VITE_API_BASE_URL`: địa chỉ backend mà trình duyệt gọi đến |
| Các tệp `.env.example` | Cấu hình mẫu an toàn để sao chép khi cài đặt |

`CORS_ORIGINS` nhận mảng JSON, ví dụ `["http://localhost:5173"]`. Biến `VITE_*` được
đưa vào mã frontend khi build và có thể được người dùng đọc; không dùng để lưu bí
mật. Các tệp `.env` thật đã được loại khỏi Git.

## Kiến trúc và cách phân chia trách nhiệm

Backend dùng **modular monolith theo tính năng**: một ứng dụng backend, một cơ sở dữ
liệu và các module có ranh giới nghiệp vụ rõ ràng. Router của các module được đăng
ký tập trung dưới `/api/v1`.

Luồng xử lý dự kiến khi triển khai nghiệp vụ:

```text
HTTP request → router → service → repository → PostgreSQL
```

| Tệp trong module backend | Trách nhiệm |
| --- | --- |
| `router.py` | Khai báo endpoint, xử lý HTTP và nhận service qua `Depends`; không truy vấn cơ sở dữ liệu hoặc gọi AI trực tiếp |
| `schemas.py` | Khai báo Pydantic schema cho dữ liệu đầu vào và đầu ra |
| `service.py` | Thực thi quy tắc nghiệp vụ, điều phối repository và các tích hợp cần thiết |
| `repository.py` | Thực hiện thao tác lưu trữ bằng SQLAlchemy; chỉ thêm khi cần |
| `models.py` | Khai báo ORM model ánh xạ bảng cơ sở dữ liệu; tách biệt với schema Pydantic |
| `__init__.py` | Đánh dấu thư mục là Python package |

Các file Python trong module `jobs` để rỗng và chưa được đăng ký router. Các module
`auth`, `candidates`, `applications` và `recommendations` mới có bộ khung, chưa cung
cấp endpoint nghiệp vụ. Xác thực, phân quyền và quy trình onboarding chưa được triển
khai. Cấu trúc bảng sẽ được thiết kế khi có yêu cầu nghiệp vụ cụ thể.

### Vòng đời ứng dụng và cơ sở dữ liệu

`main.py` dùng application factory và FastAPI lifespan để quản lý async engine,
đồng thời giải phóng tài nguyên khi dừng ứng dụng. Dependency cấp một session cho
mỗi request. Service chịu trách nhiệm về transaction; khi bổ sung thao tác ghi,
có thể dùng `async with session.begin()`. Ứng dụng không tự commit hoặc tự chạy
migration khi khởi động.

Cấu hình được đọc và kiểm tra kiểu bằng pydantic-settings. Lỗi nghiệp vụ có cấu
trúc `error.code` và `error.message`; lỗi không dự kiến trả về thông báo 500 chung
và được ghi log. Lỗi kiểm tra đầu vào giữ định dạng 422 mặc định của FastAPI. Log
ứng dụng dùng JSON; Uvicorn giữ định dạng log máy chủ mặc định.

### Tích hợp AI

Các client LLM, embedding và tìm kiếm vector được định nghĩa bằng `Protocol`,
không phụ thuộc nhà cung cấp cụ thể. `RecommendationService` nhận các client này
để chuẩn bị cho luồng:

```text
Viết lại truy vấn → Tạo embedding → Tìm kiếm tương đồng vector → Xếp hạng theo nghiệp vụ
```

PostgreSQL/pgvector là kho vector cục bộ mặc định; migration đầu tiên bật extension
`vector`. Adapter thực tế, bảng vector, số chiều, thước đo khoảng cách, chỉ mục và
thuật toán gợi ý sẽ được bổ sung sau khi chọn mô hình embedding và yêu cầu tìm kiếm.
Thư mục tích hợp lưu tệp cũng mới được giữ chỗ.

### Frontend

Cấu trúc frontend theo cách tổ chức của `~/Code/tendoo/Viettel/FE/merchant-cms`:
`App.tsx` ở gốc `src`, route tập trung tại `routes`, cấu hình tại `configs`, CSS tại
`styles`, mã dùng chung tại `shared`, và từng nghiệp vụ tại `features`.

- Mỗi feature đặt trang và `routes.tsx` trong thư mục riêng; thêm `components`,
  `hooks`, `services`, `types` bên trong khi có nhu cầu.
- `routes/routes.tsx` tập hợp route của các feature qua `createBrowserRouter`.
- `shared` chứa layout, provider, HTTP client, hook và kiểu dữ liệu dùng chung.
- `stores` dành cho trạng thái dùng chung phía client; hiện để trống, chưa thêm thư viện state.
- `assets` và `helper` giữ chỗ cho tài nguyên và hàm hỗ trợ theo cấu trúc tham chiếu.
- Alias `@/` trỏ đến `src/`, được cấu hình ở cả TypeScript và Vite.

React Router quản lý điều hướng; TanStack Query quản lý trạng thái dữ liệu từ máy
chủ. HTTP client dùng `fetch` có kiểu TypeScript. Các kiểu này mô tả hợp đồng API,
không thay thế việc kiểm tra dữ liệu tại thời điểm chạy. Feature `jobs` chỉ có file
`api.ts` rỗng; chưa có kiểu dữ liệu hoặc lời gọi API Job.

## Cấu trúc thư mục và chức năng

Chú thích bên cạnh từng thư mục mô tả trách nhiệm hiện tại hoặc mục đích dự kiến.
Các tệp `.gitkeep` giữ thư mục trống trong Git; `__init__.py` đánh dấu Python package.

```text
├── backend/  # Ứng dụng API FastAPI và cấu hình Python
│   ├── alembic/  # Cấu hình và lịch sử thay đổi cấu trúc cơ sở dữ liệu
│   │   ├── versions/  # Các migration; hiện chỉ bật extension pgvector
│   │   │   └── 0001_enable_vector.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── src/  # Mã nguồn Python theo cấu trúc src layout
│   │   └── app/  # Package chính của ứng dụng backend
│   │       ├── api/  # Tổ chức API theo phiên bản
│   │       │   ├── v1/  # Tập hợp router của các module dưới tiền tố /api/v1
│   │       │   │   ├── __init__.py
│   │       │   │   └── router.py
│   │       │   └── __init__.py
│   │       ├── core/  # Cấu hình, xử lý lỗi, logging và vị trí dành cho bảo mật
│   │       │   ├── __init__.py
│   │       │   ├── config.py
│   │       │   ├── exceptions.py
│   │       │   ├── logging.py
│   │       │   └── security.py
│   │       ├── db/  # ORM Base và dependency cấp session bất đồng bộ
│   │       │   ├── __init__.py
│   │       │   ├── base.py
│   │       │   └── session.py
│   │       ├── integrations/  # Ranh giới kết nối với dịch vụ và công nghệ bên ngoài
│   │       │   ├── embeddings/  # Protocol chuyển văn bản thành vector; chưa có provider cụ thể
│   │       │   │   ├── __init__.py
│   │       │   │   └── client.py
│   │       │   ├── llm/  # Protocol viết lại truy vấn bằng LLM; chưa có provider cụ thể
│   │       │   │   ├── __init__.py
│   │       │   │   └── client.py
│   │       │   ├── storage/  # Dành cho tích hợp lưu tệp/CV; chưa triển khai
│   │       │   │   └── __init__.py
│   │       │   ├── vector_store/  # Protocol tìm kiếm vector; dự kiến dùng PostgreSQL/pgvector
│   │       │   │   ├── __init__.py
│   │       │   │   └── client.py
│   │       │   └── __init__.py
│   │       ├── modules/  # Các module nghiệp vụ độc lập theo tính năng
│   │       │   ├── applications/  # Dành cho hồ sơ ứng tuyển và quy trình xử lý
│   │       │   │   ├── __init__.py
│   │       │   │   ├── router.py
│   │       │   │   ├── schemas.py
│   │       │   │   └── service.py
│   │       │   ├── auth/  # Dành cho xác thực và phân quyền; chưa có endpoint
│   │       │   │   ├── __init__.py
│   │       │   │   ├── router.py
│   │       │   │   ├── schemas.py
│   │       │   │   └── service.py
│   │       │   ├── candidates/  # Dành cho quản lý ứng viên; chưa có endpoint
│   │       │   │   ├── __init__.py
│   │       │   │   ├── router.py
│   │       │   │   ├── schemas.py
│   │       │   │   └── service.py
│   │       │   ├── jobs/  # Các file rỗng, chưa triển khai nghiệp vụ hoặc thiết kế bảng
│   │       │   │   ├── __init__.py
│   │       │   │   ├── models.py
│   │       │   │   ├── repository.py
│   │       │   │   ├── router.py
│   │       │   │   ├── schemas.py
│   │       │   │   └── service.py
│   │       │   ├── recommendations/  # Khung dịch vụ gợi ý AI; chưa triển khai thuật toán hoặc endpoint
│   │       │   │   ├── __init__.py
│   │       │   │   ├── router.py
│   │       │   │   ├── schemas.py
│   │       │   │   └── service.py
│   │       │   └── __init__.py
│   │       ├── __init__.py
│   │       └── main.py
│   ├── tests/  # Bộ kiểm thử backend
│   │   ├── integration/  # Kiểm thử HTTP, dependency và tích hợp PostgreSQL/pgvector
│   │   │   ├── test_api.py
│   │   │   └── test_database.py
│   │   └── unit/  # Giữ chỗ cho kiểm thử đơn vị khi triển khai nghiệp vụ
│   │       └── .gitkeep
│   ├── .dockerignore
│   ├── .env.example
│   ├── .python-version
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/  # Ứng dụng web React, TypeScript và Vite
│   ├── public/  # Tài nguyên tĩnh được phục vụ trực tiếp
│   │   └── .gitkeep
│   ├── src/  # Mã nguồn giao diện
│   │   ├── assets/  # Ảnh, biểu tượng và tài nguyên được import vào mã nguồn
│   │   │   └── .gitkeep
│   │   ├── configs/  # Cấu hình dùng chung, hiện có URL API từ môi trường
│   │   │   └── env.ts
│   │   ├── features/  # Mã giao diện và API được nhóm theo tính năng nghiệp vụ
│   │   │   ├── applications/  # Dành cho giao diện ứng tuyển; hiện chỉ giữ chỗ
│   │   │   │   └── .gitkeep
│   │   │   ├── auth/  # Dành cho đăng nhập và quản lý phiên; hiện chỉ giữ chỗ
│   │   │   │   └── .gitkeep
│   │   │   ├── candidates/  # Dành cho giao diện ứng viên; hiện chỉ giữ chỗ
│   │   │   │   └── .gitkeep
│   │   │   ├── home/  # Trang chủ và route của trang chủ
│   │   │   │   ├── Home.tsx
│   │   │   │   └── routes.tsx
│   │   │   ├── jobs/  # File API rỗng, chưa có code nghiệp vụ Job
│   │   │   │   └── api.ts
│   │   │   └── recommendations/  # Dành cho giao diện gợi ý AI; hiện chỉ giữ chỗ
│   │   │       └── .gitkeep
│   │   ├── helper/  # Giữ chỗ cho các hàm hỗ trợ
│   │   │   └── .gitkeep
│   │   ├── routes/  # Tập hợp route của các feature
│   │   │   └── routes.tsx
│   │   ├── shared/  # Mã dùng chung giữa các feature
│   │   │   ├── components/  # Giữ chỗ cho component dùng chung
│   │   │   │   └── .gitkeep
│   │   │   ├── constants/  # Giữ chỗ cho hằng số dùng chung
│   │   │   │   └── .gitkeep
│   │   │   ├── hooks/  # Hook dùng chung
│   │   │   │   ├── mutations/  # Giữ chỗ cho hook thay đổi dữ liệu
│   │   │   │   │   └── .gitkeep
│   │   │   │   └── queries/  # Hook truy vấn dữ liệu, hiện có useHealth
│   │   │   │       └── useHealth.ts
│   │   │   ├── layouts/  # Bố cục trang dùng chung
│   │   │   │   └── Layout.tsx
│   │   │   ├── providers/  # Provider dùng chung, hiện có TanStack Query
│   │   │   │   └── QueryProvider.tsx
│   │   │   ├── services/  # HTTP client dùng chung gọi backend
│   │   │   │   └── client.ts
│   │   │   ├── types/  # Kiểu dữ liệu dùng chung, hiện có HealthResponse
│   │   │   │   └── api.ts
│   │   │   ├── ui/  # Giữ chỗ cho các thành phần UI cơ bản
│   │   │   │   └── .gitkeep
│   │   │   └── utils/  # Giữ chỗ cho tiện ích dùng chung
│   │   │       └── .gitkeep
│   │   ├── stores/  # Giữ chỗ cho trạng thái dùng chung phía client
│   │   │   └── .gitkeep
│   │   ├── styles/  # CSS dùng chung của ứng dụng
│   │   │   └── index.css
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── .dockerignore
│   ├── .env.example
│   ├── Dockerfile
│   ├── index.html
│   ├── nginx.conf
│   ├── package-lock.json
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .gitignore
├── README.md
└── docker-compose.yml
```

Các tệp cấu hình chính:

| Tệp | Chức năng |
| --- | --- |
| `docker-compose.yml` | Khởi chạy PostgreSQL có pgvector, healthcheck và volume lưu dữ liệu |
| `.gitignore` | Loại bí mật cục bộ, dependency, cache và kết quả build khỏi Git |
| `backend/pyproject.toml` | Khai báo package Python, dependency, pytest và Ruff |
| `backend/uv.lock` | Khóa phiên bản dependency Python |
| `backend/alembic.ini` | Cấu hình đường dẫn cho Alembic |
| `backend/.python-version` | Chọn Python 3.12 cho môi trường phát triển |
| `frontend/package.json` | Khai báo dependency và các lệnh npm |
| `frontend/package-lock.json` | Khóa phiên bản dependency frontend |
| `frontend/tsconfig.json` | Cấu hình TypeScript với kiểm tra kiểu nghiêm ngặt |
| `frontend/vite.config.ts` | Cấu hình Vite, plugin React và cổng dev server |
| `frontend/index.html` | Trang HTML đầu vào của ứng dụng React |
| `frontend/nginx.conf` | Phục vụ bản build frontend và hỗ trợ điều hướng SPA |
| `Dockerfile` trong từng ứng dụng | Đóng gói backend hoặc frontend thành Docker image |
| `.dockerignore` trong từng ứng dụng | Loại dependency cục bộ và tệp môi trường khỏi ngữ cảnh build |

## Kiểm thử và quản lý migration

Kiểm tra backend:

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run alembic current
uv run alembic check
```

Khi thêm hoặc thay đổi ORM model, bảo đảm model được import trong `alembic/env.py`
rồi tạo migration:

```sh
# Chạy trong backend/
uv run alembic revision --autogenerate -m "describe schema change"
# Kiểm tra nội dung migration được sinh ra trước khi áp dụng
uv run alembic upgrade head
```

Mặc định, pytest kiểm tra health, tài liệu API và CORS mà không cần cơ sở dữ liệu. Một bài
kiểm thử cơ sở dữ liệu sẽ được bỏ qua nếu chưa đặt `TEST_DATABASE_URL`. Dùng cơ sở
dữ liệu kiểm thử riêng; bài kiểm thử chỉ thực hiện truy vấn khoảng cách vector:

```sh
# Chạy từ thư mục gốc khi PostgreSQL của Compose đang hoạt động
# Chỉ cần tạo cơ sở dữ liệu kiểm thử một lần
docker compose exec db createdb -U hr_chan hr_chan_test
cd backend
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan_test uv run pytest
```

Điều chỉnh cổng và mật khẩu trong các lệnh trên theo cấu hình cục bộ, ví dụ đổi
`5432` thành `55432` nếu đã sử dụng cổng thay thế.

Kiểm tra frontend trong terminal riêng, bắt đầu từ thư mục gốc:

```sh
cd frontend
npm run typecheck
npm run build
npm run preview
```

Đưa `backend/uv.lock` và `frontend/package-lock.json` vào Git. Dùng `uv sync --frozen`
và `npm ci` khi cần cài đúng dependency từ lockfile.

## Chạy bằng Docker

Compose hiện chỉ chạy PostgreSQL; khi phát triển, backend và frontend chạy trực
tiếp trên máy. Docker image của hai ứng dụng được cấu hình chạy bằng người dùng
không có quyền root.

Chạy các lệnh sau từ thư mục gốc:

```sh
docker build -t hr-chan-backend:local backend
docker build --build-arg VITE_API_BASE_URL=http://localhost:8000 -t hr-chan-frontend:local frontend
docker run --rm -p 8080:8080 hr-chan-frontend:local
```

Chạy backend bằng địa chỉ cơ sở dữ liệu có thể truy cập từ bên trong container;
`localhost` trong container không trỏ đến máy host:

```sh
# Thay các giá trị mẫu bằng cấu hình triển khai thực tế
docker run --rm --env-file backend/.env -e DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@DATABASE_HOST:5432/DATABASE_NAME' -p 8000:8000 hr-chan-backend:local
```

Frontend image phục vụ tệp tĩnh trên cổng 8080 và trả về `index.html` cho các route
SPA. Nếu truy cập frontend qua cổng này, thêm `http://localhost:8080` vào
`CORS_ORIGINS` của backend.

Chạy migration như một bước triển khai riêng, với tài khoản cơ sở dữ liệu có quyền
bật extension `vector`. Cần cấu hình thông tin xác thực, TLS và nhà cung cấp dịch
vụ theo môi trường trước khi triển khai thực tế; bộ khung hiện tại chưa phải một
sản phẩm hoàn chỉnh sẵn sàng vận hành production.

Dừng cơ sở dữ liệu cục bộ nhưng giữ nguyên dữ liệu:

```sh
docker compose stop db
```

## Lưu ý với database đã chạy scaffold cũ

Migration `0001` hiện chỉ bật pgvector, không tạo bảng `jobs`. Nếu đã chạy phiên bản
scaffold cũ, bảng `jobs` có thể vẫn còn trong database đó: thay đổi mã nguồn không
tự xóa bảng hoặc dữ liệu hiện có. Không chạy autogenerate rồi áp dụng thao tác xóa
bảng trên database cũ khi chưa kiểm tra. Dùng database mới để bắt đầu với schema
rỗng của scaffold hiện tại.

## Kiểm tra sau khi chỉnh cấu trúc

- `npm run build`: đạt, bao gồm kiểm tra TypeScript và build Vite.
- `uv run ruff check .`: đạt.
- `uv run pytest`: 1 bài đạt, 1 bài pgvector được bỏ qua vì chưa đặt `TEST_DATABASE_URL`.
- `uv run alembic upgrade head --sql`: sinh SQL thành công; không có bảng nghiệp vụ, chỉ có bảng phiên bản Alembic và lệnh bật pgvector.
- Starlette vẫn phát cảnh báo deprecation với HTTPX TestClient.
- Không chạy migration hoặc thay đổi dữ liệu trong database ở lần chỉnh sửa này.

## Tài liệu tham khảo

- [Vòng đời ứng dụng FastAPI](https://fastapi.tiangolo.com/advanced/events/)
- [Migration bất đồng bộ với Alembic](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
- [Hướng dẫn thiết lập Vite](https://vite.dev/guide/)
