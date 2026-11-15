# Authentication and Authorization

Internal identities, sessions, administration, and audit for the HR Chan monorepo.
The behavior is specified in
[the authentication design](../superpowers/specs/2026-11-15-authentication-authorization-design.md)
and implemented by `modules/auth`, `modules/accounts`, `modules/audit`,
`core/security.py`, and `integrations/email`.

## Identity Model

- Account types: `ADMIN` and `EMPLOYEE`. The type is fixed at creation.
- Employee roles: `HR`, `INTERVIEWER`, `DEPT_MANAGER`, `PROBATION`. Every employee
  has at least one role; `PROBATION` must be the only role when present. Multiple
  roles grant the union of their permissions.
- Admin accounts never carry employee roles and are not a resource-policy bypass.
- Emails must match an exact allowlisted domain (`ALLOWED_EMAIL_DOMAINS`, default
  `sis.hust.edu.vn`); subdomains are rejected. Emails are stored and compared
  case-insensitively.
- No department field is stored. Department-scoped authorization is deferred until
  organizational data and business modules exist.

| Status | Meaning | Login |
| --- | --- | --- |
| `PENDING_SETUP` | Invitation sent, password not set | No |
| `ACTIVE` | Normal operation | Yes |
| `LOCKED` | Administratively locked, sessions revoked | No |
| `PASSWORD_RESET_REQUIRED` | Unlocked; a reset link was sent | No |
| `DISABLED` | Retained for history; terminal in this release | No |

## Sessions and Tokens

- Access tokens are HS256 JWTs valid for five minutes. They carry subject, session
  id, issuer, audience, issuance/expiry, and the session credential version.
  Roles are never taken from the token; they are loaded from the database.
- Refresh tokens are opaque 32-byte secrets stored only as SHA-256 hashes and
  delivered in an `HttpOnly` cookie scoped to `/api/v1/auth`. Every refresh rotates
  the cookie; reuse of a consumed token revokes that session and records an audit
  event without affecting other devices.
- Every protected request checks session revocation, idle expiry (30 minutes),
  absolute expiry (12 hours from login), account status, and the credential
  version. Refresh and polling do not extend either timer; only `POST
  /api/v1/auth/activity` does, at most once per minute, using server time.
- Password change keeps the performing session, increments its credential version,
  rotates its refresh credentials, revokes other sessions, and invalidates
  outstanding password links. Recovery completion revokes all sessions.
- Argon2id parameters: 64 MiB memory, three iterations, parallelism four,
  32-byte digest, 16-byte salt. Hashing runs off the event loop.

## Configuration

All backend authentication settings come from environment variables in
`backend/.env` (see `backend/.env.example`). Required before any credential
endpoint works:

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | HS256 signing key, at least 32 characters, backend only |
| `LIMITER_SECRET` | HMAC key for stored throttling identifiers |
| `FRONTEND_URL` | Base URL used to build invitation/recovery links |
| `TRUSTED_ORIGINS` | Browser origins allowed to call credential endpoints |
| `CORS_ORIGINS` | Credentialed CORS allowlist; wildcards are rejected at startup |
| `ALLOWED_EMAIL_DOMAINS` | Exact accepted email domains |

Generate each secret separately with `openssl rand -base64 48` and never commit
it. `/health` keeps working without database access or authentication settings;
credential endpoints fail closed with `503 authentication_unavailable`.

`backend/.env` is resolved relative to the backend directory, not the shell's
current directory, so starting the API from the repository root behaves the same.

Other groups: session/link lifetimes (`SESSION_IDLE_SECONDS`,
`SESSION_ABSOLUTE_SECONDS`, `INVITATION_TTL_SECONDS`, `RECOVERY_TTL_SECONDS`),
throttling (`LOGIN_FAILURE_*`, `LOGIN_IP_*`, `RECOVERY_IP_*`,
`EMAIL_MIN_INTERVAL_SECONDS`, `EMAIL_HOURLY_LIMIT`), cookies (`COOKIE_SECURE`,
`COOKIE_SAMESITE`, `COOKIE_DOMAIN`), and SMTP (`SMTP_HOST`, `SMTP_PORT`,
`SMTP_STARTTLS`, `SMTP_FROM_EMAIL`, ...). Production cookies require
`COOKIE_SECURE=true` and a same-site web deployment.

### Troubleshooting `authentication_unavailable`

A `503` with code `authentication_unavailable` means the running API process has no
usable signing configuration. Add both secrets, then **restart the API process** —
`uvicorn --reload` only re-reads settings when the Python process restarts:

```sh
cd backend
printf 'JWT_SECRET=%s\nLIMITER_SECRET=%s\n' \
  "$(openssl rand -base64 48)" "$(openssl rand -base64 48)" >> .env
```

The error message names the missing variable. `bootstrap-admin` and
`seed-dev-accounts` also return a `warnings` list (plus a `next` hint) when secrets
are absent, so local setup problems surface before the first login attempt.

## Browser Client Requirements

- Access tokens live in memory only; nothing is written to local or session
  storage.
- Every credential-changing operation (login, refresh, logout, password change)
  runs inside one origin-wide Web Locks lock, and each tab deduplicates its own
  refresh promise. Browsers without Web Locks display an explicit unsupported
  state instead of racing refreshes.
- Logout and identity changes propagate to other tabs with `BroadcastChannel`;
  TanStack Query caches are cleared and stale responses are ignored through an
  auth-generation counter.
- On reload the app bootstraps with the refresh cookie, then loads `/auth/me`.
- Password pages read the token from the URL fragment and remove it with
  `history.replaceState`, load no third-party resources, and the nginx image sets
  `Referrer-Policy: no-referrer`.

The Vite dev server proxies `/api` and `/health` to the backend, so cookies stay
same-origin. `VITE_API_BASE_URL` defaults to empty (same origin); set it only for
a deployment that also configures CORS and trusted origins. Prefer a reverse proxy
that serves the SPA and `/api` from one origin.

## Development Quick Logins

Local development does not need remembered accounts. Enable the development bypass
in `backend/.env` and restart the API:

```dotenv
DEV_LOGIN_ENABLED=true
DEV_SEED_ENABLED=true
```

The login page then shows one click per persona: Admin, HR, Interviewer, Manager,
and Trainee. Each button calls `POST /api/v1/auth/dev-login` with
`{"persona": "<id>"}`, which opens a **normal session** for one of the fixed
`dev.*` personas without a password. Changing a fixture's password therefore never
breaks the buttons. A missing persona is created on demand; running
`uv run python -m app.cli seed-dev-accounts` instead pre-seeds all five with the
shared development password `dev-only-password` and resets their status to
`ACTIVE`.

Guardrails:

- The route returns `404 not_found` unless `DEV_LOGIN_ENABLED=true`, and only the
  five hardcoded `dev.*` identities are accepted.
- Account status still applies: `LOCKED`, `DISABLED`, `PENDING_SETUP`, or
  `PASSWORD_RESET_REQUIRED` returns `409` naming the status. Unlock the account or
  re-run the seed command.
- Sessions, revocation, roles, CSRF, and audit behave exactly like a password
  login; the event is recorded as `auth.dev_login` with the persona id.
- The panel is rendered only when Vite's `import.meta.env.DEV` is true. Production
  bundles exclude the persona list; the endpoint stays disabled by default and must
  never be enabled where real account data exists. This is a fixed development
  allowlist, not public registration.

## First Admin and Account Administration

```sh
cd backend
uv run python -m app.cli bootstrap-admin \
  --email admin@sis.hust.edu.vn \
  --name 'Initial Administrator'
```

The command serializes concurrent attempts, refuses to run when any Admin account
already exists, creates a `PENDING_SETUP` Admin, and sends an invitation. It never
accepts a password argument. If delivery fails, the pending Admin can request
another invitation through `POST /auth/password/recovery`.

Administration endpoints (all require a Bearer token from an active Admin):

| Method and route | Behavior |
| --- | --- |
| `GET /api/v1/accounts` | Keyset-paginated list with `status`/`account_type` filters |
| `POST /api/v1/accounts` | Create employee/Admin; returns `email_delivery` |
| `PUT /api/v1/accounts/{id}/roles` | Replace the whole employee role set |
| `POST /api/v1/accounts/{id}/lock` | Requires a reason; revokes sessions and links |
| `POST /api/v1/accounts/{id}/unlock` | Locked → reset required; emails a reset link |
| `POST /api/v1/accounts/{id}/disable` | Requires a reason; terminal status |
| `POST /api/v1/accounts/{id}/invitation` | Resend for pending/reset-required accounts |

Administrators cannot lock or disable themselves. The last active Administrator
cannot be removed; the shared transaction advisory lock plus actor revalidation
prevents two Admins from disabling each other concurrently. Role changes keep
sessions alive and apply to the next authorization check.

## Public Password Flows

- `POST /auth/password/recovery` always returns `202` with the same body,
  regardless of account existence, status, delivery outcome, or account throttling.
  Locked/disabled accounts, and accounts already active with a pending password,
  never receive a link.
- Invitation links expire after 24 hours; recovery/reset links after 30 minutes.
  Only token hashes are stored. Completing a link consumes it, invalidates every
  other outstanding link for that account, and is safe under concurrent use.
- Invalid, expired, consumed, and ineligible links return the same
  `400 invalid_password_link` message with a path to request a new email.
- Send limits: at least 60 seconds between account emails, five per hour per
  account, 20 public recovery requests per hour per IP.
- Login throttling: five failed attempts per identifier in 15 minutes block that
  identifier for 15 minutes; the IP limit defaults to 50 attempts per 15 minutes.
  Counters live in PostgreSQL so every worker shares them, and success clears the
  identifier counter.

## Audit

`modules/audit` writes append-only events inside the caller's transaction, so an
audit failure rolls back the administrative change. Metadata is allowlisted
(`reason`, `roles`, `previous_roles`, `status`, `previous_status`, `purpose`,
`email_delivery`); secrets, tokens, emails, CV content, and evaluations are never
recorded. `GET /api/v1/audit-events` is read-only, metadata-only, and
keyset-paginated. No edit/delete endpoints exist.

Recorded actions: `auth.login.succeeded`, `auth.login.failed`, `auth.logout`,
`auth.password.setup`, `auth.password.changed`,
`auth.password.recovery_requested`, `auth.refresh.replayed`, `account.created`,
`account.locked`, `account.unlocked`, `account.disabled`,
`account.roles_replaced`, `account.invitation_resent`.

## Resource Policies

Protected business APIs use `get_current_principal` (Bearer only) and an explicit
policy per resource:

```python
async def require_resource(
    principal: Principal,
    action: str,
    resource: object,
    policy: ResourcePolicy | None,
) -> None: ...
```

A missing policy, a false result, or an Admin principal is denied. Future modules
own assignment, ownership, and department rules. Business modules do not exist
yet; the mock screens remain demonstration data and are not protected API data.

## Email Delivery

Development uses Mailpit with SMTP capture:

```sh
docker compose --profile mail up -d
# SMTP 127.0.0.1:1025, UI http://127.0.0.1:8025
```

Set `SMTP_HOST=localhost` and `SMTP_PORT=1025` in `backend/.env`. Account, link,
and audit state commit before delivery; a failed send leaves the account intact and
the Admin sees `email_delivery: "failed"` with a resend option. Automatic delivery
guarantees and a background queue are out of scope. Production requires explicit
SMTP credentials and a public frontend URL; never put them in chat or Git.

## Cleanup and Operations

```sh
cd backend
uv run python -m app.cli cleanup-auth --batch-size 500
```

Removes expired limiter rows, expired password links, and refresh tokens belonging
to absolutely expired sessions. It never deletes accounts, audit events, or active
sessions. Schedule it as an operator action; no scheduler is bundled.

## Verification

Backend (dedicated migrated test database; never the application database):

```sh
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/hr_chan_test uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Frontend unit/behavioral tests and browser tests:

```sh
cd frontend
pnpm test
```

Browser tests need a running backend, Mailpit, and a dedicated database. They also
need the same secrets the backend was started with:

```sh
E2E_PSQL_URL=postgresql://USER:PASSWORD@HOST:PORT/hr_chan_e2e \
E2E_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/hr_chan_e2e \
E2E_JWT_SECRET=... E2E_LIMITER_SECRET=... \
E2E_API_URL=http://127.0.0.1:8000 E2E_BASE_URL=http://localhost:5173 \
pnpm test:e2e
```

The global setup truncates `accounts` (cascading to auth tables) on that dedicated
database, bootstraps the Admin through the CLI, and completes its invitation from
Mailpit. Never point `E2E_PSQL_URL` at an application database.

## Intentional Limitations

No public registration, email or account-type changes, disabled-account
restoration, MFA/SSO, mobile clients, third-party API access, personal audit
history, or business API implementations. Client-side route guards improve
navigation only; the backend remains the authority. Mock business datasets stay
available behind guards and are labeled demonstration data.
