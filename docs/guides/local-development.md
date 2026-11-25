# Local Development

Follow the root [quick start](../../README.md#quick-start) for prerequisites,
environment files, dependency installation, service startup, and local URLs.
Use the pnpm version pinned in `frontend/package.json`. With Corepack available,
run `corepack enable` and `corepack install` from `frontend/` before installation.

Commands below run from the repository root unless specified otherwise.
Use `uv sync` or `pnpm install` when intentionally updating dependencies and retain
the corresponding lockfile changes.

## Ports and Environment

If port 5432 is occupied, leave the existing service running and use:

```sh
POSTGRES_PORT=55432 docker compose up -d --wait db
```

Update the port in `backend/.env` accordingly. For the default local-only credentials:

```dotenv
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:55432/hr_chan
```

An optional root `.env` can persist `POSTGRES_PORT=55432`. If you change
`POSTGRES_PASSWORD`, match the backend connection URL. Changing Compose variables
does not reset the password stored in an existing database volume.

| File | Configuration |
| --- | --- |
| Root `.env` (optional) | Compose port/password overrides |
| `backend/.env` | API name, database URL, CORS/trusted origins, log level, auth secrets, sessions, throttling, SMTP |
| `frontend/.env` | `VITE_API_BASE_URL`; leave empty to use the same-origin dev proxy |
| `.env.example` files | Safe setup examples, never real secrets |

`CORS_ORIGINS` and `TRUSTED_ORIGINS` are JSON arrays, for example
`["http://localhost:5173"]`. Frontend `VITE_*` values are embedded in browser
assets and are public. Never copy real environment contents into Git,
documentation, or logs.

## Authentication Configuration

Credential endpoints fail closed until these are set in `backend/.env`; `/health`
stays available:

```sh
cd backend
printf 'JWT_SECRET=%s\nLIMITER_SECRET=%s\n' \
  "$(openssl rand -base64 48)" "$(openssl rand -base64 48)" >> .env
```

The API reads `backend/.env` regardless of the current working directory, and only
re-reads it when the process restarts. Set `FRONTEND_URL=http://localhost:5173` and
keep `COOKIE_SECURE=false` only for local HTTP. See the [authentication guide](../guides/authentication.md) for the
full setting list, role/status rules, and CSRF/origin behavior.

### Local email mailbox

Development captures account emails with Mailpit instead of sending them:

```sh
docker compose --profile mail up -d
```

| Port | Purpose |
| --- | --- |
| `127.0.0.1:1025` | SMTP capture (`SMTP_HOST=localhost`, `SMTP_PORT=1025`) |
| `127.0.0.1:8025` | Mailpit web UI |

Override `MAILPIT_SMTP_PORT`/`MAILPIT_UI_PORT` if those ports are taken. The
profile does not change the database service or its volume.

### Candidate applications and email outbox

Account emails and application OTPs go through the `email_outbox` table. Start things in
this order: migrate → seed templates → API + worker + Mailpit + scanner.

```sh
cd backend
uv run alembic upgrade head
uv run python -m app.cli seed-email-templates   # idempotent; edited templates are kept
docker compose --profile mail --profile scan up -d   # Mailpit and ClamAV (loopback only)
uv run uvicorn app.main:app --reload                 # API
uv run python -m app.worker                          # delivers queued email (every 30 s)
```

Seed templates **before** the first `bootstrap-admin` or invitation: queued mail needs its
template. Account mail is `queued` (delivered by the worker, up to four attempts five minutes
apart); the OTP email is sent immediately by the API. Without a running worker, invitations stay
queued.

The application worker also scores submitted CVs with the development AI adapter.
Run it with the same CV storage directory and encryption key as the API. A submitted
application starts in `SCORING`. The worker reads the criteria version saved at
submission, stores the scores and weights, and sets the HR review deadline. The HR
note “Đạt ngưỡng – cần mời thủ công” identifies an application that meets both the
weighted threshold and every mandatory floor.

Migration 0006 assigns a floor of 50 to existing mandatory criteria, including
historical versions. HR supplies the floor explicitly when saving a new mandatory
criterion. Scores equal to the floor pass.

| Setting | Purpose |
| --- | --- |
| `EMAIL_PROVIDER=smtp`, `SMTP_*` | Real delivery. `fake` is simulation only: OTP requests then return 503 and nothing is sent |
| `OUTBOX_ENCRYPTION_KEY` | Encrypts secret values (links) while a mail is queued |
| `CV_STORAGE_DIR`, `CV_ENCRYPTION_KEY` | Encrypted CV store, outside any public path |
| `SUBMISSION_TOKEN_SECRET`, `OTP_SECRET` | Sign upload capabilities (24 h) and hash OTPs |
| `TURNSTILE_SECRET_KEY` (+ `TURNSTILE_EXPECTED_HOSTNAME`) | Server-side CAPTCHA check; missing config fails closed |
| `CLAMAV_HOST`/`CLAMAV_PORT` | Virus scan of every CV before it is stored |
| `VITE_TURNSTILE_SITE_KEY` (frontend) | Public site key for the apply form |

Use independent random values for every key (for example
`python -c "import secrets; print(secrets.token_urlsafe(32))"`); losing `CV_ENCRYPTION_KEY`
makes stored CVs unreadable, and rotating it needs a re-encryption plan. Never commit them.
Cloudflare publishes test keys for local/E2E only (site key `1x00000000000000000000AA`,
secret `1x0000000000000000000000000000000AA`; siteverify reports hostname `example.com`, so
set `TURNSTILE_EXPECTED_HOSTNAME=example.com` and leave the action unset). They exercise the
integration but do not prove production CAPTCHA, which needs a real site's keys.

For Gmail SMTP use port 587 with STARTTLS and an App Password (needs 2-step verification and
may be blocked by account policy). Personal Gmail is limited to about 500 emails per day
(see Google's [sending limits](https://support.google.com/mail/answer/22839) and
[App Passwords](https://support.google.com/accounts/answer/185833)); send only to
recipients you control.

### HR application review

After migration 0007, seed email templates again to insert the interview invitation,
thank-you and overdue-review templates. Set PUBLIC_BASE_URL to the candidate-facing
origin. Interview email contains a single-use URL. The candidate response page is
scheduled for a later phase.

The existing seed-dev-accounts command also ensures a Demo Recruitment department
and a sample 2027-01-01 holiday. Its HR and interviewer are separate accounts,
alongside the manager persona. Repeated execution preserves existing accounts.

The protected API supports list, detail, CV download, suggested interview slots,
invitation and rejection under /api/applications. The versioned review routes are
also available under /api/v1/applications. Authenticate as an employee with HR.
Use the version from the application response for invitation and rejection.

The development Google adapter starts with an empty calendar and supports
configurable busy periods and failures in tests. INTERVIEW_DURATION_MINUTES
defaults to 60. HR supplies a timezone-aware start time. The server validates the
whole meeting against configured working hours, holidays, response deadlines and
existing appointments. Suggested starts advance in 30-minute steps. Business
calendar calculations and email times use Asia/Ho_Chi_Minh.

An invitation queues email and changes the application to INTERVIEW_INVITED.
Rejection queues a thank-you email with a talent-pool consent link. The worker
queues one overdue-review digest per active HR account per working day after
opening time.

### First Admin and cleanup

```sh
cd backend
uv run python -m app.cli bootstrap-admin \
  --email admin@sis.hust.edu.vn \
  --name 'Initial Administrator'
uv run python -m app.cli cleanup-auth --batch-size 500
DEV_SEED_ENABLED=true uv run python -m app.cli seed-dev-accounts
```

Bootstrap refuses to run when any Admin exists and never accepts a password
argument; run the worker, then read the invitation from Mailpit and open the `/set-password` link.
`seed-dev-accounts` creates the `dev.*` personas behind the login page's
one-click buttons; it requires `DEV_SEED_ENABLED=true` and must never run against
real account data. The buttons themselves use `POST /auth/dev-login`, enabled by
`DEV_LOGIN_ENABLED=true`; it skips the password for the fixed personas but keeps
status checks, sessions, and audit. Both flags are development-only and must stay
`false` wherever real accounts exist.
Both commands need the authentication settings above. `cleanup-auth` is an
operator action; no scheduler is bundled.

## Migrations

Follow [database conventions](../engineering/conventions/database.md). First
verify the exact target configured by `DATABASE_URL` without exposing credentials.
From `backend/`, inspect history and schema state:

```sh
uv run alembic current
uv run alembic history
uv run alembic check
```

These commands require the appropriate database/configuration; `check` may report
schema differences that need investigation. Review migration files before applying
them. Only after confirming the target and intended changes:

```sh
uv run alembic upgrade head
```

For an approved schema change, import the intended ORM models in `alembic/env.py`,
then generate a new migration from `backend/`:

```sh
uv run alembic revision --autogenerate -m "describe schema change"
```

Inspect the generated operations before applying them. Do not rewrite shared
history. `0001` only enables `vector`; `0002` adds the account, session, refresh,
password-link, limiter, and audit tables. Older databases may still contain a
`jobs` table from a previous scaffold. Never apply an autogenerated drop or reset a
volume merely to match the current scaffold. Use a separate new database for a
clean start.

## Verification and Test Database

Use the authoritative commands in [testing conventions](../engineering/conventions/testing.md).
Default API tests do not require a database; the pgvector and authentication tests
are skipped without `TEST_DATABASE_URL`.

To prepare a dedicated test database once, with the default local Compose user:

```sh
docker compose exec db createdb -U hr_chan hr_chan_test
```

Review the migration and confirm that the following URLs point to that test
database before running from `backend/`. Adjust the port and local credentials
to match your environment; these examples use only the default local password.

```sh
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan_test uv run pytest
```

Do not point database tests at the application database. The test engine refuses
to run when `TEST_DATABASE_URL` equals the configured application database.

### Browser tests

`pnpm test:e2e` runs Playwright against a real backend. Prepare a separate database
for browser tests and start the stack yourself:

```sh
cd backend
DATABASE_URL=postgresql+asyncpg://hr_chan:local_dev_only@localhost:5432/hr_chan_e2e uv run alembic upgrade head
DATABASE_URL=... JWT_SECRET=... LIMITER_SECRET=... \
  SMTP_HOST=localhost SMTP_PORT=1025 FRONTEND_URL=http://localhost:5173 \
  uv run uvicorn app.main:app --reload
```

From `frontend/`, export the matching settings for the test run
(`E2E_PSQL_URL`, `E2E_DATABASE_URL`, `E2E_JWT_SECRET`, `E2E_LIMITER_SECRET`,
`E2E_API_URL`, `E2E_BASE_URL`) exactly as documented in the
[authentication guide](../guides/authentication.md#verification), then run:

```sh
pnpm test:e2e
```

Browser tests also need `E2E_OUTBOX_ENCRYPTION_KEY` (and the API/worker must use the same
`OUTBOX_ENCRYPTION_KEY`, SMTP to Mailpit, CV storage and keys, ClamAV, and Turnstile test
keys). Global setup seeds email templates and reference data, bootstraps the admin, and
starts the outbox worker itself (stopped at teardown). The Vite server needs
`VITE_TURNSTILE_SITE_KEY` set to the test site key. `applications.spec.ts` turns trace,
video and screenshots off because they would record the typed OTP.

Set `E2E_EXPECTED_DATABASE` to the dedicated test database name (for example,
`hr_chan_e2e`). Both database URLs and `SELECT current_database()` must match it;
the helper refuses the default `hr_chan` application database before resetting data.
If `psql` is unavailable locally, `E2E_PSQL_CONTAINER` can name the project's running
PostgreSQL container. `E2E_PYTHON` optionally selects an existing backend Python
environment instead of `uv run`. On a shared Mailpit, set `E2E_MAIL_AFTER` to the run's
start time in ISO format so earlier runs' invitation emails are ignored.

Global setup truncates `accounts` on the dedicated browser-test database, so never
point `E2E_PSQL_URL` at an application database. If ports 8000/5173 are taken by
other services, run the browser-test backend and Vite dev server on free ports and
set `E2E_API_URL`, `E2E_BASE_URL`, `E2E_DEV_COMMAND`, and `VITE_PROXY_TARGET`
accordingly.

To inspect a frontend production build locally, run `pnpm run preview` from
`frontend/` after building.

## Docker Images

Compose starts the database and the optional Mailpit profile. Build application
images separately:

```sh
docker build -t hr-chan-backend:local backend
docker build --build-arg VITE_API_BASE_URL= -t hr-chan-frontend:local frontend
docker run --rm -p 8080:8080 hr-chan-frontend:local
```

Both application images use non-root users. The frontend serves on port 8080
and falls back to `index.html` for SPA routes. Authentication cookies are
same-origin: serve the SPA and `/api` from one origin (reverse proxy), or add the
frontend origin to `CORS_ORIGINS` and `TRUSTED_ORIGINS` when previewing
cross-origin on another port.

The backend database address must be reachable from its container; `localhost`
inside a container does not refer to the host. Replace these placeholder values:

```sh
docker run --rm --env-file backend/.env -e DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@DATABASE_HOST:5432/DATABASE_NAME' -p 8000:8000 hr-chan-backend:local
```

Run reviewed migrations as a separate deployment step with an account authorized
to enable `vector`. Set authentication secrets and SMTP explicitly, enable
`COOKIE_SECURE`, and terminate TLS before production use. Business workflows still
need implementation.

Stop the local database while retaining its volume:

```sh
docker compose stop db
```

## Recruitment Worker

After reviewing migration `0004` and verifying the target database, apply migrations
separately with `uv run alembic upgrade head`. The migration changes foreign-key and
trigger rules; it does not delete existing postings. Back up retained application
data before enabling permanent deletion.

Run the worker as a separate long-running process from `backend/`:

```sh
uv run python -m app.worker
```

It closes expired OPEN postings at startup and every `JOB_EXPIRY_INTERVAL_SECONDS`
(default 60 seconds). Independently, retention runs at startup and daily at 02:00
UTC+7, permanently deleting CLOSED postings whose closing day was two calendar
years ago. A February 29 anniversary falls on February 28 in a non-leap year.
Starting this worker against an existing database therefore immediately applies
that retention policy to already eligible postings; downtime is caught up at startup.

HR can permanently delete DRAFT postings with confirmation. CLOSED postings are
removed only by retention, not the manual API. Each posting, its criteria history,
and its interviewer assignments are removed together with a `job.deleted` audit
event. Earlier audit events remain. References from other workflows block deletion;
their data is not cascaded. Failed postings are logged safely and retried on the
next sweep, without stopping cleanup of other eligible postings.

Keep both API and worker on the same reviewed schema/version. The API does not
start cleanup tasks or apply migrations. The HR list displays the backend-provided
due date and reports pending cleanup while an eligible posting still exists; this
does not prove that a worker is currently running. Deletion has no application undo.
