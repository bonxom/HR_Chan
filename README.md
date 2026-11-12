# HR_Chan

A scaffold for an AI-assisted hiring and employee onboarding platform. The monorepo
contains a FastAPI backend and React frontend. Business workflows are not yet implemented.

## Technology

- Backend: Python 3.12+, uv, FastAPI, Pydantic v2, pydantic-settings,
  async SQLAlchemy 2.x, asyncpg, and Alembic.
- Database: PostgreSQL with pgvector, running locally through Docker Compose.
- Frontend: Node.js 22.12+, pnpm, React, TypeScript, Vite, React Router, and TanStack Query.
- Backend quality tools: pytest, HTTPX, and Ruff.

## Quick Start

From the repository root, create local configuration files only if they do not
already exist, then start the database:

```sh
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up -d --wait db
```

In a backend terminal:

```sh
cd backend
uv sync --frozen
uv run uvicorn app.main:app --reload
```

In a separate frontend terminal:

```sh
cd frontend
ppnpm install --frozen-lockfile
pnpm run dev
```

| URL | Purpose |
| --- | --- |
| `http://localhost:5173` | Frontend |
| `http://localhost:8000/docs` | Interactive API documentation |
| `http://localhost:8000/health` | Liveness without database or AI dependencies |

Database migrations are a separate step: verify the target database and review
migration contents before applying them. See the
[local development guide](docs/guides/local-development.md) for migrations,
occupied ports, environment variables, test database setup, and Docker images.
Do not stop another service to free port 5432.

## Documentation

See the [documentation index](docs/README.md) for the workflow, conventions,
architecture, and templates. Coding agents must also read [AGENTS.md](AGENTS.md).
