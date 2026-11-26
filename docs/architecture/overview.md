# Architecture Overview

HR_Chan is a hiring and onboarding application, organized as a monorepo with a
FastAPI backend and React frontend. Authentication, account administration, and
audit are implemented, as are job postings with versioned scoring criteria; the
remaining recruitment workflows are not. See
[backend](../engineering/conventions/backend.md),
[frontend](../engineering/conventions/frontend.md), and the
[authentication guide](../guides/authentication.md) for implementation rules and
operational detail.

## Backend

The backend is a feature-based modular monolith. The
[application factory](../../backend/src/app/main.py) configures credentialed CORS
for explicit origins, centralized errors, logging, API routing, and an async
database engine managed by lifespan. The engine is disposed at shutdown; a
[dependency](../../backend/src/app/db/session.py) supplies async sessions.

```text
HTTP request → router → service → repository → PostgreSQL
```

Services own transactions; repositories own SQL; routers translate typed service
failures into `AppError` responses after the service commits defensive state.

| Area | Endpoints |
| --- | --- |
| Health | `GET /health` — liveness only, no database or signing dependency |
| Authentication | `/api/v1/auth`: login, csrf, refresh, logout, me, activity, password change/recovery/complete |
| Administration | `/api/v1/accounts`: list, create, replace roles, lock, unlock, disable, resend invitation |
| Audit | `GET /api/v1/audit-events` — read-only, metadata-only, cursor paginated |
| Job postings (HR only) | `/api/v1/jobs`: list, create, detail, update, publish, close, save criteria, criteria versions; `GET /api/v1/interviewers`, `GET /api/v1/departments` |

HR can permanently delete DRAFT postings with `DELETE /api/v1/jobs/{id}` and the
version last read. OPEN and CLOSED postings cannot be deleted by that endpoint.
The separate worker closes expired postings and purges CLOSED postings two calendar
years after their closing day in UTC+7 (February 29 anniversaries use February 28).
Retention runs at worker startup and daily at 02:00 UTC+7. Each deletion and its
metadata-only `job.deleted` audit event commit together; system deletions have no
human actor. Criteria versions and interviewer assignments cascade only with their
posting, while individual criterion/set deletion remains protected. Foreign keys
from other workflows block deletion rather than deleting their records.
The API supplies `deletion_due_date`; the HR page shows the due day or a pending
cleanup message. See the [worker operations](../guides/local-development.md#recruitment-worker).

Authentication uses short-lived HS256 access tokens in browser memory plus
rotating opaque refresh tokens in an `HttpOnly` cookie. Sessions, refresh hashes,
password links, throttling counters, and audit events live in PostgreSQL, so
locking an account or revoking a session rejects an otherwise valid JWT. See the
[authentication decision](decisions/2026-11-15-stateful-jwt-authentication.md).

| Path under `backend/` | Responsibility and Current State |
| --- | --- |
| `src/app/api/` | Versioned router composition |
| `src/app/core/` | Settings, clock, pagination cursors, centralized exceptions, JSON logging, identity dependencies |
| `src/app/db/` | ORM Base and async session dependency |
| `src/app/modules/accounts/` | Account models, role/status rules, administration, creation, password links |
| `src/app/modules/auth/` | Passwords, JWTs, sessions, refresh rotation, CSRF, throttling, password links, resource policies |
| `src/app/modules/audit/` | Append-only allowlisted writer and Admin listing |
| `src/app/modules/recruitment/` | Job postings, criteria sets/criteria (immutable, versioned), job interviewers, expiry closing |
| `src/app/modules/departments/`, `settings/` | Read-only department reference data; `system_settings` parameters |
| `src/app/modules/candidates/`, `applications/` | Protected CV storage, public submission and OTP, application scoring against historical criteria |
| `src/app/modules/interviews/`, `core/interview_scheduler.py`, `core/response_links.py` | Interview persistence, shared scheduling and single-use response links |
| `src/app/modules/responses/`, `core/response_handler.py` | Public token-based responses, consent evidence, expiry and deferred calendar cleanup |
| `src/app/modules/recommendations/` | Interfaces for future job recommendations |
| `src/app/integrations/email/` | SMTP adapter and invitation/recovery templates |
| `src/app/integrations/` | LLM, embedding, vector search Protocols; storage placeholder |
| `src/app/cli.py` | First-Admin bootstrap and bounded auth-record cleanup |
| `alembic/` | Migration history; `0001` enables pgvector, `0002` adds auth/account/audit tables, `0003` adds departments, system settings, job postings and criteria |
| `tests/unit/`, `tests/integration/` | Rules, crypto, templates, policies, HTTP/session/concurrency tests |

[AppError](../../backend/src/app/core/exceptions.py) produces `error.code` and
`error.message` and may add safe headers such as `Retry-After`. Unexpected
exceptions are logged and return a generic 500; request validation retains
FastAPI's default 422 response.

Public response validation removes raw input and arbitrary extra-field names from
422 errors so capability tokens remain private. Response API errors and successful
responses carry private/no-store and no-referrer headers.

## AI and Storage Boundaries

[RecommendationService](../../backend/src/app/modules/recommendations/service.py)
holds injected Protocol clients but does not implement a recommendation pipeline.
Providers, models, dimensions, distance metrics, filters, indexes, and ranking
rules for job recommendations remain undecided.
`job_postings.embedding` (`vector(1536)`, HNSW cosine) exists per the schema but is
not written yet. The scoring worker uses a fake AI agent behind an interface.
CVs use encrypted storage, and the email worker delivers messages through the outbox.
HR review APIs provide protected application reads, original CV downloads, interview
invitations and rejection. The calendar interface uses a fake workspace. Interview
reservation constraints enforce one active interview per application and prevent
overlapping active meetings for the same interviewer. Review reminders deduplicate
daily outbox messages under transaction-scoped locks.

Candidate responses lock the application, relevant interview/candidate and response
link before validating a fresh database decision time. Consent-state snapshots
detect changes between rendering and submission. An already-valid grant is
acknowledged with its original evidence. New consent grants and renewals write
policy evidence and token consumption in the same transaction.

Cancelled interviews carry a durable cleanup flag. The worker calls the calendar
outside PostgreSQL transactions and conditionally clears that flag after success.
The development Google adapter shares events in a private SQLite file across API
and worker processes. Its unit-test adapter supports isolated in-memory state.

## Frontend

[App.tsx](../../frontend/src/App.tsx) composes TanStack Query, the authentication
provider, and React Router. Route composition
([routes](../../frontend/src/routes/routes.tsx)) separates the public candidate
portal from the guarded internal workspace.

| Path under `frontend/src/` | Responsibility |
| --- | --- |
| `features/auth/` | In-memory session store, refresh coordination, activity reporting, guards, login/recovery/set-password/account pages |
| `features/admin/` | Real account administration and audit screens backed by the API |
| `features/jobs/` | HR job management (`/app/hr/jobs`) and the public job board/detail (`/api/v1/public/jobs`), both backed by the API |
| `candidates/` (apply form, OTP) | Real flow: CV upload → email OTP → application, via `candidates` and `applications` APIs; capability and OTP state stay in memory |
| `applications/`, `interviews/`, `probation/`, `reports/`, `hr/` | Demonstration screens backed by bundled mock data |
| `shared/layouts/` | Candidate portal and authenticated dashboard shell |
| `shared/services/` | Typed HTTP transport with structured errors, plus the mock store for demonstration data |
| `shared/components/ui/` | Reusable Input, Button, Card, Modal, Badge, Toast |
| `configs/` | Environment configuration |

Access tokens are never persisted; refresh, login, logout, and password change run
inside an origin-wide Web Locks lock, and logout propagates to other tabs. Route
guards improve navigation only — the backend remains the authority. Mock business
datasets are demonstration data, not confidential data protected by backend
policies, and must not be described as such.

The [HTTP client](../../frontend/src/shared/services/client.ts) uses typed `fetch`
with a configured base URL and credentialed requests. TypeScript types are not
runtime response validation. Alias `@/` maps to `src/` in TypeScript and Vite.

## Runtime and Configuration

[Compose](../../docker-compose.yml) runs PostgreSQL/pgvector, plus Mailpit under an
optional development profile. Backend/frontend run directly during local
development; their Dockerfiles support separate images behind a same-site reverse
proxy. There is no complete production setup.

| File | Purpose |
| --- | --- |
| `backend/pyproject.toml`, `backend/uv.lock` | Python dependencies, tooling, and locked versions |
| `backend/.python-version`, `backend/alembic.ini` | Python selection and Alembic configuration |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | pnpm scripts (dev, build, test, e2e), dependencies, lockfile |
| `frontend/tsconfig.json`, `frontend/vite.config.ts` | Type checking, alias, dev proxy, and build configuration |
| `frontend/vitest.config.ts`, `frontend/playwright.config.ts` | Behavioral and browser-test configuration |
| `frontend/index.html`, `frontend/nginx.conf` | HTML entry point, SPA fallback, and security headers |
| Per-application `Dockerfile` and `.dockerignore` | Image build and exclusion of local files |
| `.gitignore` | Exclusion of local secrets, dependencies, caches, and build outputs |

For execution, migrations, and browser-test setup, see the
[local development guide](../guides/local-development.md).
