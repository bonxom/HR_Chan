# Architecture Overview

HR_Chan is a hiring and onboarding application, organized as a monorepo with a
FastAPI backend and React frontend. Authentication, account administration, and
audit are implemented; recruitment business workflows are not. See
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
| `src/app/modules/candidates/`, `applications/`, `recommendations/` | Empty scaffolds; no business endpoints |
| `src/app/modules/jobs/` | Intentionally empty files; no Job model, repository, or endpoint |
| `src/app/integrations/email/` | SMTP adapter and invitation/recovery templates |
| `src/app/integrations/` | LLM, embedding, vector search Protocols; storage placeholder |
| `src/app/cli.py` | First-Admin bootstrap and bounded auth-record cleanup |
| `alembic/` | Migration history; `0001` enables pgvector, `0002` adds auth/account/audit tables |
| `tests/unit/`, `tests/integration/` | Rules, crypto, templates, policies, HTTP/session/concurrency tests |

[AppError](../../backend/src/app/core/exceptions.py) produces `error.code` and
`error.message` and may add safe headers such as `Retry-After`. Unexpected
exceptions are logged and return a generic 500; request validation retains
FastAPI's default 422 response.

## AI and Storage Boundaries

[RecommendationService](../../backend/src/app/modules/recommendations/service.py)
holds injected Protocol clients but does not implement a recommendation pipeline.
Providers, models, dimensions, distance metrics, filters, indexes, and ranking
rules remain undecided. There are no business/vector tables, and file/CV storage
and email beyond transactional account messages are placeholders.

## Frontend

[App.tsx](../../frontend/src/App.tsx) composes TanStack Query, the authentication
provider, and React Router. Route composition
([routes](../../frontend/src/routes/routes.tsx)) separates the public candidate
portal from the guarded internal workspace.

| Path under `frontend/src/` | Responsibility |
| --- | --- |
| `features/auth/` | In-memory session store, refresh coordination, activity reporting, guards, login/recovery/set-password/account pages |
| `features/admin/` | Real account administration and audit screens backed by the API |
| `features/jobs/`, `candidates/`, `applications/`, `interviews/`, `probation/`, `reports/`, `hr/` | Demonstration screens backed by bundled mock data |
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
