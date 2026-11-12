# Backend Conventions

Use Python 3.12+, FastAPI, Pydantic v2, pydantic-settings, and uv. Organize the
backend as a feature-based modular monolith under `backend/src/app/modules/`.
See the [architecture overview](../../architecture/overview.md) for current behavior.

## Layer Responsibilities

| File | Responsibility |
| --- | --- |
| `router.py` | Endpoints, HTTP concerns, and dependency injection through `Depends` |
| `schemas.py` | Pydantic request/response schemas, separate from ORM models |
| `service.py` | Business rules, orchestration, and transaction boundaries |
| `repository.py` | Data access, only when storage requirements are established |
| `models.py` | SQLAlchemy ORM models, only after the business schema is defined |

Routers must not query the database or call AI providers directly. Do not add a
base repository or generic CRUD framework without an actual requirement.
Register implemented routers in `backend/src/app/api/v1/router.py`; do not import
router objects from empty placeholder files.

## Lifecycle and Persistence

Keep the application factory and lifespan in `main.py`. Supply async sessions
through a dependency; own transactions in the service, not the router or repository.
Do not automatically commit or run migrations when the API starts.
The `/health` endpoint must remain independent of database and AI availability.
Follow [database conventions](database.md) for schema and migration work.

## Configuration, Errors, and Integrations

- Read environment configuration through `core/config.py`.
- Centralize error handling and logging in `core/`.
- Preserve the existing `AppError` response structure (`error.code`, `error.message`)
  and define expected statuses in each feature spec. Unexpected errors return a
  generic 500 response; request validation uses FastAPI's default 422 format.
- Application logs use the existing JSON logging setup; never log secrets or personal data.
- Integrate LLMs, embeddings, and vector search through Protocols in `integrations/`.
  Do not choose providers or implement recommendation algorithms without requirements.
- The backend `jobs` files are intentionally empty. Do not restore sample Job code.

Use the [testing conventions](testing.md) for verification commands and test scope.
