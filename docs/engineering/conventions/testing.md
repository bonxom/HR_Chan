# Testing and Verification Conventions

Follow the [workflow](../workflow.md). Test actual behavior that needs protection;
do not invent business logic to make tests possible.

## Red, Green, and Refactor

For application changes, write a test tied to an acceptance criterion and observe
it fail for the intended reason before implementation. An intentionally missing
application module/symbol can establish Red; unrelated import, dependency, or
service failures cannot. Implement the minimum behavior, observe Green, then
refactor while keeping relevant tests passing.

The frontend has a behavioral test runner: Vitest with jsdom and Testing Library
(`pnpm test`), plus Playwright for cookie, cross-tab, and full-stack flows
(`pnpm test:e2e`). Typecheck checks types and build checks compilation/bundling;
neither proves interaction behavior. Do not describe an intentionally introduced
type error as proof of missing UI behavior.

## Verification Matrix

| Change Scope | Required Verification |
| --- | --- |
| Backend | Targeted tests, Ruff lint/format checks, and pytest suite |
| Frontend | Typecheck, build, and relevant behavioral tests when established |
| Backend and frontend | Checks for both sides |
| Database/migration | Backend checks plus reviewed migration history/SQL and applicable tests against a dedicated migrated test database |
| Documentation only | Content, preserved rules, relative links, examples, whitespace, and changed-file review |

Run backend checks from `backend/`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Run frontend checks from `frontend/`:

```sh
pnpm run typecheck
pnpm run build
pnpm test
```

The build script also runs TypeScript checking. Browser tests need a running
backend, a dedicated database, and Mailpit; see the
[authentication guide](../../guides/authentication.md#verification).

## Database Tests

The API test verifies health, OpenAPI/docs, and CORS with an unreachable database,
demonstrating that liveness does not require a connection. The pgvector integration
test queries vector distance and is skipped without `TEST_DATABASE_URL`.

Authentication, account, audit, and limiter tests require `TEST_DATABASE_URL`
pointing at the dedicated migrated test database; they skip without it. Each test
truncates only authentication tables afterwards, and concurrency tests use
independent committed sessions rather than one enclosing transaction.

Use a separate migrated database, never an existing application database, for
database tests. Follow the [test database setup](../../guides/local-development.md).
Schema checks such as `alembic current` and `alembic check` require an explicitly
verified target; they are not prerequisites for documentation-only work.

## Documentation Checks and Evidence

For documentation-only edits, compare moved rules against the original documents,
check internal links and command examples, and run `git diff --check`.
Check newly created untracked files as well; ordinary `git diff` omits them.

At handoff, report commands actually run, results, warnings, failed checks, skipped
tests and reasons, and remaining work. Do not reuse old test summaries as fresh
evidence.
