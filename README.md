# HR_Chan

An AI-assisted hiring and employee onboarding platform. The monorepo contains a
FastAPI backend and React frontend. Authentication, account administration, and
security auditing are implemented; recruitment business workflows are not.

## Technology

- Backend: Python 3.12+, uv, FastAPI, Pydantic v2, pydantic-settings,
  async SQLAlchemy 2.x, asyncpg, Alembic, PyJWT, argon2-cffi, and aiosmtplib.
- Database: PostgreSQL with pgvector, running locally through Docker Compose.
- Email: SMTP with a local Mailpit capture mailbox in development.
- Frontend: Node.js 22.12+, pnpm, React, TypeScript, Vite, React Router, TanStack
  Query, and Tailwind.
- Backend quality tools: pytest, HTTPX, and Ruff. Frontend: Vitest, Testing
  Library, and Playwright.

## Quick Start

From the repository root, create local configuration files only if they do not
already exist, then start the database and development mailbox:

```sh
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up -d --wait db
docker compose --profile mail up -d
```

The API refuses credential requests until two secrets exist in `backend/.env`
(`JWT_SECRET` and `LIMITER_SECRET`, at least 32 characters each):

```sh
cd backend
printf 'JWT_SECRET=%s\nLIMITER_SECRET=%s\n' \
  "$(openssl rand -base64 48)" "$(openssl rand -base64 48)" >> .env
```

Restart the API after adding the secrets; `--reload` re-reads them only on process
restart. In a backend terminal:

```sh
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli bootstrap-admin \
  --email admin@sis.hust.edu.vn \
  --name 'Initial Administrator'
uv run uvicorn app.main:app --reload
```

The invitation is captured by Mailpit; open it from `http://127.0.0.1:8025` and set
the Admin password. `bootstrap-admin` refuses to run once any Admin exists.

For convenience, enable the development login bypass and seed the personas so the
login page offers one-click buttons (Admin, HR, Interviewer, Manager, Trainee):

```dotenv
# backend/.env
DEV_LOGIN_ENABLED=true
DEV_SEED_ENABLED=true
```

```sh
cd backend
uv run python -m app.cli seed-dev-accounts
```

Restart the API after changing these flags. The buttons exist only in the Vite dev
build and open a real session through `/auth/dev-login`, so changing a fixture
password does not break them; see the
[authentication guide](docs/guides/authentication.md#development-quick-logins).

In a separate frontend terminal:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

> **Note for Windows environments:** If `pnpm` is not in your current shell PATH, you can either:
> - Run directly with npm: `npm run dev`
> - Or prepend npm's global bin to PATH: `$env:PATH += ";$env:APPDATA\npm"` then `pnpm run dev`
> - Or invoke pnpm via its binary: `& "$env:APPDATA\npm\pnpm.cmd" run dev`

| URL | Purpose |
| --- | --- |
| `http://localhost:5173` | Frontend (guarded workspace under `/app`, candidate portal at `/`) |
| `http://localhost:8000/docs` | Interactive API documentation |
| `http://localhost:8000/health` | Liveness without database or signing configuration |
| `http://127.0.0.1:8025` | Mailpit mailbox for invitation and reset emails |

The Vite dev server proxies `/api` and `/health` to the backend so refresh cookies
stay same-origin. `VITE_API_BASE_URL` is empty by default; set it only when the API
is served from another origin that is also listed in `CORS_ORIGINS` and
`TRUSTED_ORIGINS`.

Database migrations are a separate step: verify the target database and review
migration contents before applying them. See the
[local development guide](docs/guides/local-development.md) for migrations,
occupied ports, environment variables, test database setup, Mailpit, and Docker
images. Do not stop another service to free port 5432.

Business screens under the guarded workspace still use bundled demonstration data
and mock interactions. They are not backed by protected APIs; authentication and
authorization apply to their navigation only.

## Documentation

See the [documentation index](docs/README.md) for the workflow, conventions,
architecture, and templates. The
[prototype quick start](docs/guides/prototype-quickstart.md) covers running the app
and exercising each implemented flow; the
[authentication guide](docs/guides/authentication.md) covers identities, sessions,
CSRF, email delivery, audit, and operations. Coding agents must also read
[AGENTS.md](AGENTS.md).
