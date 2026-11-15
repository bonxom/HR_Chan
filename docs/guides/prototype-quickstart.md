# Prototype Quick Start

How to run and exercise the current HR_Chan prototype: a FastAPI backend with
authentication, account administration, and audit, plus a React workspace whose
business screens still use demonstration data.

Detailed background: [authentication guide](authentication.md),
[local development](local-development.md), [architecture](../architecture/overview.md).

## Prerequisites

Python 3.12+ with `uv`, Node.js 22.12+ with `pnpm`, Docker, and `openssl`.

## 1. Start the database and mailbox

From the repository root:

```sh
POSTGRES_PORT=55432 docker compose up -d --wait db
docker compose --profile mail up -d
```

Use port 55432 when 5432 is already taken; otherwise omit `POSTGRES_PORT`.
Mailpit captures every account email locally.

| URL | Purpose |
| --- | --- |
| `http://localhost:5173` | Web app (candidate portal at `/`, workspace at `/app`) |
| `http://localhost:8000/docs` | API documentation |
| `http://localhost:8000/health` | Liveness (works without database or secrets) |
| `http://127.0.0.1:8025` | Mailpit inbox (invitation, recovery, reset links) |

## 2. Configure the backend

Create `backend/.env` from `backend/.env.example`, then set a database URL that
matches the Compose port and generate the two required secrets:

```sh
cd backend
printf 'JWT_SECRET=%s\nLIMITER_SECRET=%s\n' \
  "$(openssl rand -base64 48)" "$(openssl rand -base64 48)" >> .env
```

Development flags used by the prototype (keep them `false` for real data):

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

The API reads `backend/.env` regardless of the current directory and only
re-reads it on process restart.

## 3. Prepare the database and demo accounts

```sh
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed-dev-accounts
```

`seed-dev-accounts` creates (or restores) five `dev.*` accounts with the
development password `dev-only-password` and status `ACTIVE`.

## 4. Run both applications

```sh
# terminal 1
cd backend && uv run uvicorn app.main:app --reload

# terminal 2
cd frontend && pnpm install --frozen-lockfile && pnpm run dev
```

Open `http://localhost:5173/login`. If ports 8000/5173 are occupied, start the
backend with `--port 8001`, run `VITE_PROXY_TARGET=http://127.0.0.1:8001 pnpm dev
--port 5174`, and point `FRONTEND_URL`/`TRUSTED_ORIGINS` at the frontend port.

## 5. Sign in

The login page shows **Đăng nhập nhanh (chỉ môi trường dev)** buttons. They open a
real session through `/auth/dev-login` without a password, so changed fixture
passwords never break them.

| Button | Account | Lands on |
| --- | --- | --- |
| Admin | `dev.admin@sis.hust.edu.vn` | `/app/admin/users` |
| HR | `dev.hr@sis.hust.edu.vn` | `/app/hr` |
| Interviewer | `dev.interviewer@sis.hust.edu.vn` | `/app/interviewer` |
| Manager | `dev.manager@sis.hust.edu.vn` | `/app/manager` |
| Trainee | `dev.trainee@sis.hust.edu.vn` | `/app/trainee` |

Normal email/password login also works: try `dev.hr@sis.hust.edu.vn` /
`dev-only-password`, or create your own Admin with
`uv run python -m app.cli bootstrap-admin --email admin@sis.hust.edu.vn --name 'Initial Administrator'`
and complete the invitation from Mailpit.

## 6. What to try

- **Session handling:** sign in, open a second tab, reload both, then log out in
  one tab — the other tab returns to `/login`. Access tokens stay in memory only.
- **Role guards:** sign in as Trainee or Interviewer and open `/app/hr` in the URL;
  the workspace shows an access-denied panel instead of the section.
- **Admin / accounts:** as Admin, create an employee, replace the whole role set,
  lock with a reason, unlock, and disable. Self-lock/disable is disabled in the UI.
  Email failures show a resend option only for `PENDING_SETUP`/reset-required rows.
- **Password lifecycle:** request recovery on `/forgot-password`, open the newest
  email in Mailpit, set a new password on `/set-password`, then sign in with it.
  Locked accounts must be unlocked first; completed or stale links fail safely.
- **Password change:** `/app/account` rotates only the current session and revokes
  other devices.
- **Audit:** `/app/admin/logs` lists genuine metadata (`auth.login.*`,
  `account.*`, `auth.dev_login`, ...) with action/actor/target filters and cursor
  pagination. It contains no CV or evaluation payloads.

## 7. Verify the prototype

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

Browser tests are optional and need a running backend, Mailpit, and a dedicated
database; see [authentication guide](authentication.md#verification).

## Limits

- Candidate portal and business workspaces (HR, interviews, probation, reports)
  use bundled mock data. They are demonstration data, not API-protected records;
  only authentication, accounts, and audit talk to the backend.
- Work-handover and system-settings mocks are intentionally not routed.
- Quick login is development-only: the panel is absent from production builds and
  the backend route returns `404` unless `DEV_LOGIN_ENABLED=true`.
- No public registration, email/account-type changes, disabled-account restoration,
  MFA/SSO, or real email delivery.
