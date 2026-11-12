# Architecture Overview

HR_Chan is a hiring and onboarding application scaffold, organized as a monorepo
with a FastAPI backend and React frontend. Business workflows are not complete.
See [backend](../engineering/conventions/backend.md) and
[frontend conventions](../engineering/conventions/frontend.md) for implementation rules.

## Backend

The backend is a feature-based modular monolith. The
[application factory](../../backend/src/app/main.py) configures CORS, centralized
errors, logging, API routing, and an async database engine managed by lifespan.
The engine is disposed at shutdown; a
[dependency](../../backend/src/app/db/session.py) supplies async sessions.
Creating the engine does not require connecting to the database for `/health`.

The only implemented application endpoint is `GET /health`, returning
`{"status": "ok"}`. FastAPI also exposes API documentation and OpenAPI.
The [versioned router](../../backend/src/app/api/v1/router.py) assembles scaffolded
module routers under `/api/v1`; these do not yet expose business endpoints.

The intended flow for future persistence-backed features is:

```text
HTTP request → router → service → repository → PostgreSQL
```

| Path under `backend/` | Responsibility and Current State |
| --- | --- |
| `src/app/api/` | Versioned router composition |
| `src/app/core/` | Settings, centralized exceptions, JSON application logging, security placeholder |
| `src/app/db/` | ORM Base and async session dependency |
| `src/app/modules/` | Feature modules; auth, candidates, applications, and recommendations are scaffolds |
| `src/app/modules/jobs/` | Intentionally empty files; no Job model, repository, or endpoint |
| `src/app/integrations/` | LLM, embedding, and vector search Protocols; storage placeholder |
| `alembic/` | Migration environment and history; `0001` only enables pgvector |
| `tests/integration/` | API/CORS/liveness checks and optional pgvector check |
| `tests/unit/` | Placeholder for future unit tests |

[AppError](../../backend/src/app/core/exceptions.py) produces `error.code` and
`error.message`. Unexpected exceptions are logged and return a generic 500;
request validation retains FastAPI's default 422 response. Application logs use
JSON while Uvicorn retains its server logging format.

## AI and Storage Boundaries

[RecommendationService](../../backend/src/app/modules/recommendations/service.py)
holds injected Protocol clients but does not implement a recommendation pipeline.
Its intended stages are query rewriting, embedding, vector search, and business
ranking. Providers, models, dimensions, distance metrics, filters, indexes, and
ranking rules remain undecided. There are no business/vector tables or working
recommendation endpoints. File/CV storage is also a placeholder.

## Frontend

[App.tsx](../../frontend/src/App.tsx) composes TanStack Query and React Router.
[Route composition](../../frontend/src/routes/routes.tsx) connects feature routes.
The current home feature uses shared infrastructure; `features/jobs/api.ts` is empty.

See [frontend directory responsibilities](../engineering/conventions/frontend.md)
for the source layout.

The [HTTP client](../../frontend/src/shared/services/client.ts) uses typed `fetch`
with a configured base URL. TypeScript types are not runtime response validation.
Alias `@/` maps to `src/` in TypeScript and Vite.

## Runtime and Configuration

[Compose](../../docker-compose.yml) runs PostgreSQL/pgvector only, with a healthcheck
and persistent volume. Backend/frontend run directly during local development;
their Dockerfiles support separate images. There is no complete production setup.

| File | Purpose |
| --- | --- |
| `backend/pyproject.toml`, `backend/uv.lock` | Python dependencies, tooling, and locked versions |
| `backend/.python-version`, `backend/alembic.ini` | Python selection and Alembic configuration |
| `frontend/package.json`, `frontend/package-lock.json` | npm scripts, dependencies, and locked versions |
| `frontend/tsconfig.json`, `frontend/vite.config.ts` | Type checking, alias, and dev/build configuration |
| `frontend/index.html`, `frontend/nginx.conf` | HTML entry point and container SPA serving |
| Per-application `Dockerfile` and `.dockerignore` | Image build and exclusion of local files |
| `.gitignore` | Exclusion of local secrets, dependencies, caches, and build outputs |

For execution and migration instructions, see the
[local development guide](../guides/local-development.md).
