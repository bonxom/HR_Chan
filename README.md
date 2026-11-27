# HR_Chan

An AI-assisted hiring and employee onboarding platform. The monorepo contains a
FastAPI backend and React frontend. Implemented workflows include authentication,
account administration, recruitment, CV applications and scoring, HR review,
interview invitations and candidate responses.

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

Commands use a POSIX shell (Git Bash on Windows) from the repository root unless a
step says otherwise. Use a database you can reset; never point these steps at data
you need to keep.

### 1. Services and configuration

Create local configuration files only if they do not already exist, then start
PostgreSQL, the Mailpit capture mailbox and the ClamAV virus scanner (its first start
downloads signatures and can take several minutes):

```sh
cp -n backend/.env.example backend/.env
cp -n frontend/.env.example frontend/.env
docker compose up -d --wait db
docker compose --profile mail --profile scan up -d
```

Generate independent secrets (at least 32 characters each) and the CV storage
directory. Values appended later in `backend/.env` override the empty placeholders
from the example. Keep them stable: changing `CV_ENCRYPTION_KEY` makes stored CVs
unreadable, and changing `OUTBOX_ENCRYPTION_KEY` makes queued mail undeliverable.

```sh
cd backend
for name in JWT_SECRET LIMITER_SECRET OUTBOX_ENCRYPTION_KEY CV_ENCRYPTION_KEY \
  SUBMISSION_TOKEN_SECRET OTP_SECRET; do
  printf '%s=%s\n' "$name" "$(openssl rand -base64 48)" >> .env
done
mkdir -p .local/cv
printf 'CV_STORAGE_DIR=%s\n' "$(cd .local/cv && (pwd -W 2>/dev/null || pwd))" >> .env
cd ..
```

The application form requires Cloudflare Turnstile. For local use only, Cloudflare
publishes test keys that always pass; production needs the site's own keys:

```sh
printf 'TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA\nTURNSTILE_EXPECTED_HOSTNAME=example.com\n' >> backend/.env
printf 'VITE_TURNSTILE_SITE_KEY=1x00000000000000000000AA\n' >> frontend/.env
```

Never commit `.env` files. `backend/.local/` (CV files and the development calendar
file) is ignored by Git.

### 2. Backend

Verify that `DATABASE_URL` in `backend/.env` points to your own development database,
then migrate and seed the email templates **before** creating the first Admin
(queued mail needs its template):

```sh
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed-email-templates
uv run python -m app.cli bootstrap-admin   --email admin@sis.hust.edu.vn   --name 'Initial Administrator'
```

`bootstrap-admin` refuses to run once any Admin exists. For one-click logins (Admin,
HR, Interviewer, Manager, Trainee) on a development database only, set
`DEV_LOGIN_ENABLED=true` and `DEV_SEED_ENABLED=true` in `backend/.env`, then run
`uv run python -m app.cli seed-dev-accounts`; see the
[authentication guide](docs/guides/authentication.md#development-quick-logins).
The same command creates the "Demo Recruitment" department and a sample holiday.
There is no department screen yet, so HR needs this (or a department inserted by
an operator) before creating a job posting.

Run the API and the worker in two separate terminals from `backend/`:

```sh
uv run uvicorn app.main:app --reload
uv run python -m app.worker
```

The worker delivers queued email, scores submitted CVs, closes expired postings,
expires candidate response links and retries calendar cancellations. **It also
permanently deletes CLOSED postings two years after closing, immediately at
startup**; back up any database with data you need before starting it. Restart the
API and worker after editing `backend/.env`.

### 3. Frontend

In a third terminal:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

> **Windows:** if `pnpm` is not on PATH, use `npx -y pnpm@11.21.0 install --frozen-lockfile`
> and `npm run dev`. Run Vitest from a path with an uppercase drive letter (`D:\...`).

| URL | Purpose |
| --- | --- |
| `http://localhost:5173` | Frontend (guarded workspace under `/app`, candidate portal at `/`) |
| `http://localhost:8000/docs` | Interactive API documentation |
| `http://localhost:8000/health` | Liveness without database or signing configuration |
| `http://127.0.0.1:8025` | Mailpit mailbox: invitations, OTP codes, candidate links |

Open the Admin invitation in Mailpit and set the password. The Vite dev server
proxies `/api` and `/health` to the backend so refresh cookies stay same-origin;
leave `VITE_API_BASE_URL` empty unless the API is served from another origin listed
in `CORS_ORIGINS` and `TRUSTED_ORIGINS`.

See the [local development guide](docs/guides/local-development.md) for occupied
ports, every environment variable, test databases, browser tests and Docker images.
Do not stop another service to free port 5432.

### What works end to end

| Area | Status |
| --- | --- |
| Login, sessions, password flows, Admin accounts and audit log | Real API |
| HR job postings and scoring criteria (`/app/hr/jobs`) | Real API |
| Public job board, CV upload (virus scan, CAPTCHA), email OTP, application | Real API |
| CV scoring | Runs in the worker with a **deterministic demo scorer**, not a real AI model |
| HR review, interview slots, invitation, rejection | Real API under `/api/v1/applications`, used by the HR pipeline screen (`/app/hr/applications`) |
| HR overview (`/app/hr`): counts, pending applications, stage chart | Real API (`/api/v1/applications/counts`, list, jobs); upcoming interviews not shown yet |
| Candidate responses at `/r/{token}` (interview confirm/decline/reschedule, talent-pool consent) | Real API |
| Google Calendar/Meet | Development fake stored in `FAKE_GOOGLE_DB_PATH`; no real Google events |
| HR handling of reschedule requests, consent withdrawal | Not implemented |
| Other workspace screens (interviews, probation, reports; marked MOCK) | Bundled demonstration data |

Screens marked MOCK are not backed by protected APIs; authentication and
authorization apply to their navigation only.

## Documentation

See the [documentation index](docs/README.md) for the workflow, conventions,
architecture, and templates. The
[prototype quick start](docs/guides/prototype-quickstart.md) covers running the app
and exercising each implemented flow; the
[authentication guide](docs/guides/authentication.md) covers identities, sessions,
CSRF, email delivery, audit, and operations. Coding agents must also read
[AGENTS.md](AGENTS.md).
