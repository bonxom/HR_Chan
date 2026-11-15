# Authentication and Authorization Implementation Plan

## Goal and References

Implement the approved [authentication and authorization specification](../specs/2026-11-15-authentication-authorization-design.md) through the existing FastAPI and React applications.

Use the [workflow](../../engineering/workflow.md), [backend](../../engineering/conventions/backend.md), [frontend](../../engineering/conventions/frontend.md), [database](../../engineering/conventions/database.md), and [testing conventions](../../engineering/conventions/testing.md). Execute inline with the executing-plans skill after plan approval. Each numbered task has its own Red/Green cycle; do not implement all tasks before testing.

Architecture: JWT access tokens in browser memory, rotating opaque refresh cookies, and PostgreSQL-backed session/authorization checks. Domain services own transactions; API routers use dependencies; repositories implement SQL. Reuse existing errors, configuration, session lifecycle, and UI components.

## Constraints and Dependencies

- Python 3.12+, async SQLAlchemy 2.x, PostgreSQL, FastAPI, React, TypeScript, Vite, TanStack Query, and Tailwind remain the stack.
- Add `argon2-cffi`, `PyJWT`, `email-validator`, and `aiosmtplib` for identified backend needs; update `backend/uv.lock`. Use a fixed HS256 JWT algorithm with a separately configured random signing secret of at least 32 bytes and explicit issuer/audience; never derive the algorithm from the token.
- Add Vitest, jsdom, Testing Library React/user-event/jest-dom, and Playwright as frontend development dependencies; update `frontend/pnpm-lock.yaml`. Browser tests are necessary for cross-tab refresh and cookies.
- Exact allowed email domain: `sis.hust.edu.vn`. Passwords: 8–128 Unicode characters without normalization or composition rules.
- Access JWT lifetime: five minutes. Idle session lifetime: 30 minutes. Absolute session lifetime: 12 hours. Invitation lifetime: 24 hours. Recovery/unlock link lifetime: 30 minutes.
- Only `ACTIVE` accounts authenticate. Every employee has at least one role; `PROBATION` is exclusive. Admin is a separate account type with no employee roles.
- No department storage. Include the explicit English deferral comment in the account model.
- Preserve business mock datasets and numeric IDs. Real identity/account types use UUID strings in separate frontend types; do not cast mock IDs into authenticated identities.
- No public registration, email/type changes, disabled restoration, business APIs, or automatic work handover. Never add an Admin policy bypass.
- Development convenience: `DEV_SEED_ENABLED`-gated `seed-dev-accounts`, plus a `DEV_LOGIN_ENABLED`-gated `POST /auth/dev-login` for the fixed `dev.*` personas and a quick-login panel shown only in Vite dev builds. The bypass skips only the password; status checks, sessions, and audit still apply.
- No commits, pushes, deployments, production email provisioning, or destructive application-data operations. Preserve migration `0001`, existing volumes, and any legacy `jobs` table.
- All database tests run on a separately identified, migrated test database. Do not print credentials or inspect real `.env` contents in output.
- Frontend conventions contain an outdated statement that Tailwind is absent; actual package/config already enable Tailwind. Preserve that integration and correct the stale statement in documentation.

## File and Interface Map

Paths below are exact planned files. Create package `__init__.py` files for new backend packages.

| Boundary | Files | Responsibility |
| --- | --- | --- |
| Account domain | `backend/src/app/modules/accounts/{models,schemas,rules,repository,service,router}.py` | Identity, roles, state transitions, administration |
| Auth persistence | `backend/src/app/modules/auth/{models,repository,schemas}.py` | Sessions, refresh records, password links, response contracts |
| Auth mechanics | `backend/src/app/modules/auth/{passwords,tokens,service,sessions,password_links,rate_limits,csrf}.py` | Hashing, JWT, login, rotation, recovery, throttling, CSRF |
| Authorization | `backend/src/app/core/security.py`, `backend/src/app/modules/auth/policies.py` | Current principal and reusable explicit resource checks |
| Audit | `backend/src/app/modules/audit/{models,schemas,repository,service,router}.py` | Allowlisted audit writer and read-only Admin listing |
| Email | `backend/src/app/integrations/email/{client,templates}.py` | SMTP interface and link messages |
| Operational commands | `backend/src/app/cli.py` | Bootstrap Admin and bounded expired-auth-record cleanup |
| Auth UI | `frontend/src/features/auth/{types,api,session,refreshCoordinator,activity,AuthProvider,RequireAuth,LoginPage,RecoveryPage,CompletePasswordPage,AccountPage,routes}.tsx` | Use `.ts` instead of `.tsx` for types/api/session/refreshCoordinator/activity; authentication lifecycle and pages |
| Admin UI | `frontend/src/features/admin/{types,api}.ts`, existing `UserManagement.tsx`, `AuditLogs.tsx` | Real account and audit data |

Shared service interfaces, implemented in the tasks below:

```python
# passwords.py
hash_password(password: str) -> str
verify_password(password: str, encoded: str) -> bool
# tokens.py
issue_access_token(account_id: UUID, session_id: UUID, version: int, now: datetime) -> str
verify_access_token(token: str, now: datetime) -> AccessClaims
# security.py: Principal contains account_id, account_type, roles, session_id, credential_version
get_current_principal(request: Request, session: AsyncSession) -> Principal
require_admin(principal: Principal) -> Principal
# policies.py: policies are explicit async callables; None denies
require_resource(principal: Principal, action: str, resource: object, policy: ResourcePolicy | None) -> None
# audit/service.py: appends/flushes only; caller owns commit
record_event(session: AsyncSession, event: AuditEventInput) -> None
```

Auth services return typed results, including expected failures that must commit counters or revocations. Routers translate failure results to `AppError` only after the service transaction exits successfully. Never raise an HTTP error inside a transaction that must retain a replay revocation or failed-login counter.

## Task 1: Account Invariants, Persistence, and Migration

Dependencies: none. Supplies all models and a real PostgreSQL fixture to subsequent tasks.

Files: create account models/rules/schemas; auth models; audit models; `backend/alembic/versions/0002_auth_foundation.py`; `backend/tests/conftest.py`; `backend/tests/unit/test_account_rules.py`; `backend/tests/integration/test_auth_schema.py`. Modify `backend/alembic/env.py` and `backend/pyproject.toml`/`uv.lock` as needed for schema validation.

- [x] Write parametrized tests rejecting employee role sets `[]`, `[PROBATION, HR]`, duplicate roles, unknown roles, and Admin employee roles; accept all nonempty subsets of HR/Interviewer/Manager and probation alone. Test exact domain matching, normalized uniqueness, and password character-count bounds.
- [x] Run from `backend`: `uv run pytest tests/unit/test_account_rules.py -q`. Observe missing account rules/schema failure, not missing tooling.
- [x] Implement enums, request schemas, and ORM models for the six spec tables. Use timezone-aware timestamps and UUID keys. Add account-model comment: `Departments and department-scoped authorization are intentionally deferred until organizational data and the corresponding business modules are implemented.`
- [x] Encode database role checks without unsupported CHECK subqueries: restrict the array to allowed values, forbid null members, require one-dimensional nonempty employee arrays, and compare cardinality with the sum of the four per-role presence indicators to reject duplicates. Admin roles must be empty. Active accounts require a password hash.
- [x] Add indexes for session account/revocation, token hash, link account/expiry, audit time/ID, and limiter expiry. Import all models in Alembic. Generate/review offline SQL with `uv run alembic upgrade head --sql`; verify no changes to pre-existing tables.
- [x] Build dedicated-database fixtures with deterministic fixture IDs and targeted teardown of test-owned data. Concurrent tests require independent committed sessions, not one enclosing rollback transaction. Refuse to use the configured application database as `TEST_DATABASE_URL`.
- [x] After identifying the dedicated test target, migrate it separately, then run `uv run pytest tests/unit/test_account_rules.py tests/integration/test_auth_schema.py -q`. Direct SQL inserts must demonstrate invariant enforcement independently of Pydantic.

## Task 2: Password/JWT Primitives and Security Configuration

Dependencies: Task 1. Supplies `AccessClaims` and hashing/token functions from the interface map.

Files: create auth `passwords.py`, `tokens.py`; `backend/tests/unit/test_auth_crypto.py`, `test_auth_settings.py`. Modify `backend/src/app/core/config.py`, `backend/.env.example`, `backend/pyproject.toml`, `backend/uv.lock`, and existing health-test fixtures if explicit auth settings are required.

- [x] Test Unicode/space preservation, wrong passwords, distinct salted hashes, and lengths 7/8/128/129. Test JWT wrong signature, algorithm, audience, issuer, missing claims, expiry, malformed UUID/version, and future issuance.
- [x] Run `uv run pytest tests/unit/test_auth_crypto.py tests/unit/test_auth_settings.py -q`; record Red.
- [x] Implement Argon2id with documented parameters (initial target 64 MiB, three iterations, parallelism four), offloading hashing/verification from the async event loop. Use a fixed dummy hash for unknown identities. Bound HTTP password input before hashing.
- [x] Implement strict JWT encode/decode, SHA-256 hashing of high-entropy opaque tokens, and cryptographically random 32-byte token creation. Use separate secrets for JWT signing and HMAC limiter identifiers.
- [x] Add settings for secrets, issuer/audience, trusted frontend origin, cookie security, SMTP, allowlisted domains, and agreed lifetimes/limits. Auth must fail closed when unconfigured while `/health` remains available without a database or signing secret. No predictable secret defaults.
- [x] Rerun targeted tests and `uv run pytest tests/integration/test_api.py -q`. Do not change health's database independence.

## Task 3: Transactional Audit and Shared Throttling

Dependencies: Tasks 1–2. Supplies `record_event` and PostgreSQL limiter decisions.

Files: create audit schemas/repository/service; auth `rate_limits.py`; `backend/tests/integration/test_audit_writer.py`, `test_auth_rate_limits.py`.

- [x] Test audit rollback with caller transactions, metadata allowlists, secret-field rejection, simultaneous counter updates, expiry, and shared state across separate service instances.
- [x] Run `uv run pytest tests/integration/test_audit_writer.py tests/integration/test_auth_rate_limits.py -q`; observe missing behavior.
- [x] Implement explicit event schemas for login/logout, password lifecycle, account/role changes, replay, and bounded future business metadata. Actor/target identifiers are opaque; no arbitrary payloads or unknown-login email values.
- [x] Implement atomic limiter windows using locked/upserted PostgreSQL rows keyed by HMAC digests. Enforce five failures/15 minutes, 15-minute account block, 50 attempts/IP/15 minutes, 60 seconds between account emails, five account emails/hour, and 20 public recovery requests/IP/hour.
- [x] Ensure success clears only identifier login failures, public recovery masks account throttling, and no account status changes due to throttling. Trust proxy IP headers only under explicit deployment configuration.
- [x] Rerun targeted tests with independent concurrent database connections and inject audit failures to demonstrate rollback.

## Task 4: SMTP Delivery, Password Links, and First Admin

Dependencies: Tasks 1–3. Supplies bootstrap and activation so subsequent login tests can create real active identities.

Files: create email client/templates; auth `password_links.py`; account repository/service initial creation methods; `backend/src/app/cli.py`; `backend/tests/integration/test_password_links.py`, `test_account_bootstrap.py`; `backend/tests/unit/test_email_templates.py`. Modify `docker-compose.yml`, settings/example, dependency manifests/lockfile.

- [x] Write tests for bootstrap once/concurrently, domain restrictions, multiple valid links, two simultaneous completions, expired links, state eligibility, generic public recovery outcomes, and SMTP failure preserving account state.
- [x] Run `uv run pytest tests/integration/test_password_links.py tests/integration/test_account_bootstrap.py tests/unit/test_email_templates.py -q`; observe Red.
- [x] Implement `create_account`, `request_password_email`, and `complete_password_link` service methods. Lock account before consuming links; invalidate all outstanding password links on completion. Active recovery leaves credentials/sessions untouched until completion.
- [x] Use one fixed PostgreSQL transaction advisory lock for Admin bootstrap/creation/status mutations. CLI `uv run python -m app.cli bootstrap-admin --email admin@sis.hust.edu.vn --name 'Initial Administrator'` refuses any existing Admin. Do not accept a plaintext password CLI argument.
- [x] Commit account/link/audit before bounded SMTP delivery; return explicit Admin delivery outcome without logging tokens. Public flows mask delivery failure. Render escaped email text/HTML using configured frontend URL and fragment token.
- [x] Add a pinned Mailpit image under a development Compose profile, bound to loopback SMTP/UI ports, without changing the existing database service/volume. Use fake mail delivery in automated tests and Mailpit for end-to-end verification.
- [x] Rerun all targeted tests. Verify disabled/locked links cannot complete, pending/reset-required users can request another link, and transient delivery failures do not require repeating bootstrap.

## Task 5: Login, Current Principal, Logout, and CSRF

Dependencies: Tasks 1–4. Supplies the authenticated request contract.

Files: create auth `service.py` implementation, repository, `csrf.py`; update auth schemas/router and `core/security.py`; modify `main.py`, `core/exceptions.py`, `api/v1/router.py`, existing `test_api.py`. Create `backend/tests/integration/test_auth_http.py`, `test_auth_csrf.py`.

- [x] Test login active/ineligible/unknown identities, current account, cookie attributes, absent/invalid CSRF and origins, logout twice, and rejected JWT after logout.
- [x] Run `uv run pytest tests/integration/test_auth_http.py tests/integration/test_auth_csrf.py -q`; record Red.
- [x] Implement login transaction creating session/refresh record, audit, and last-login time. Failed-login results commit counters/audit before mapping to generic 401/429. Never include hashes or administrative reasons in account responses.
- [x] Implement `get_current_principal` with JWT verification and fresh session/account/role checks. Authentication reads must not accidentally leave a transaction open that conflicts with service-owned transactions; use explicit session boundaries and immutable Principal data.
- [x] Implement signed double-submit CSRF: bootstrap a host-only HttpOnly CSRF cookie and return its matching signed proof in JSON, validate proof against cookie and trusted Origin. Scope credential cookies to `/api/v1/auth`; use Secure in production and SameSite=Lax for the supported same-site web deployment. Reject missing/untrusted Origin for unsafe browser auth routes.
- [x] Enable credentialed CORS for explicit configured origins and `X-CSRF-Token`; never combine credentials with wildcard origins. Add `Cache-Control: no-store` on credential responses. Extend AppError safely to support Retry-After without altering its JSON shape.
- [x] Implement logout by resolving the refresh-token family and revoking the session, clearing cookies even for expired/already revoked credentials. Update the OpenAPI test that currently assumes `/health` is the only route.
- [x] Rerun targeted tests plus existing API tests; check `/health` still works with unreachable PostgreSQL.

## Task 6: Refresh Rotation, Expiry, and Password Change

Dependencies: Task 5. Supplies complete session lifecycle.

Files: auth `sessions.py`, repository/service/router/schemas; `backend/tests/integration/test_auth_sessions.py`, `test_password_change.py`.

- [x] Test one-use refresh, replay revoking only its family, concurrent refresh attempts, idle/absolute boundaries, activity timestamps, revoked-session refresh, and password change preserving only the current session with fresh credentials.
- [x] Run `uv run pytest tests/integration/test_auth_sessions.py tests/integration/test_password_change.py -q`; record Red.
- [x] Lock account then session then token consistently for competing credential operations. Password completion, lock/disable, and password change follow the same ordering. Refresh replay revocation/audit must commit before returning 401.
- [x] Implement rotation without resetting idle/absolute timers; retain consumed-token evidence until session expiry. A current session's credential version changes on password change, not on routine refresh, allowing existing five-minute access tokens across tabs.
- [x] Implement activity with server time only, a minimum one-minute persistence interval, and checks before update. Never revive expired sessions. Add injected clock support for tests without sleeps.
- [x] Verify current password, revoke other sessions, replace current session refresh credentials, increment credential version, invalidate outstanding password links, and return new JWT/cookie atomically with audit. Reject stale concurrent operations.
- [x] Rerun targeted tests, including expired JWT versus live refresh, rollback injection, and old current-session JWT denial after password change.

## Task 7: Account Administration and Resource Policies

Dependencies: Tasks 4–6. Supplies all Admin endpoints and authorization extension points.

Files: account repository/service/router/schemas; auth `policies.py`; audit repository/router/schemas; `api/v1/router.py`; `backend/tests/integration/test_account_admin.py`, `test_admin_concurrency.py`, `test_audit_api.py`; `backend/tests/unit/test_resource_policies.py`.

- [x] Test every spec route's actor matrix (anonymous, employee, Admin), employee role combinations, role update on a live session, self-lock/disable, status transitions, unlock/password reset, last-Admin concurrency, and audit filtering/pagination.
- [x] Run `uv run pytest tests/integration/test_account_admin.py tests/integration/test_admin_concurrency.py tests/integration/test_audit_api.py tests/unit/test_resource_policies.py -q`; record Red.
- [x] Implement create/list/role-replace/lock/unlock/disable/resend endpoints exactly as the spec. Revalidate the actor after acquiring the shared administration lock and before Admin mutations; two Admins racing to disable each other must not both succeed using stale principals.
- [x] Lock/unlock/disable invalidate the specified sessions/links. Unlock clears old password and creates a new reset link; delivery occurs after commit. Disabled is terminal in this API.
- [x] Use keyset pagination on `(created_at, id)` for accounts and `(timestamp, id)` for audit, validating opaque cursors and limit 1–100. Apply filters before pagination. No audit mutation endpoints.
- [x] Implement a small `ResourcePolicy` async callable protocol. Explicitly deny Admin business access, missing policies, and false results; allow a policy to grant access through any applicable employee role. Demonstrate with test-local resources only, not invented business APIs.
- [x] Rerun targeted tests and injected audit failures, confirming domain changes roll back. Verify there is no email/type modification or disabled restoration route.

## Task 8: Browser Session Client and Multi-tab Coordination

Dependencies: Tasks 5–7. Supplies React authentication state and test tooling.

Files: create auth `types.ts`, `api.ts`, `session.ts`, `refreshCoordinator.ts`, `activity.ts`, `AuthProvider.tsx`; `frontend/src/test/setup.ts`; `frontend/vitest.config.ts`; `frontend/playwright.config.ts`; `frontend/src/features/auth/session.test.ts`, `AuthProvider.test.tsx`; `frontend/tests/e2e/auth-tabs.spec.ts`. Modify shared client, App, package/lockfile and Vite dev proxy.

- [x] Add Vitest/jsdom/Testing Library and scripts `test` (vitest run), `test:e2e` (playwright test). Preserve Vite/Tailwind and existing `apiGet` callers. First write a behavior test proving unauthenticated initialization and expired-session handling; observe Red after tooling itself works.
- [x] Run from `frontend`: `pnpm test src/features/auth/session.test.ts src/features/auth/AuthProvider.test.tsx`.
- [x] Add explicit AuthAccount/EmployeeRole types using string UUIDs. Shared HTTP transport supports JSON, bearer tokens, credentials, AbortSignal, structured errors and 204; auth state owns only in-memory access tokens.
- [x] Coordinate all credential-changing operations using Web Locks with a shared origin-wide lock name. Inside the lock, fetch fresh CSRF proof and refresh using the latest shared cookie. Use BroadcastChannel for logout/account-change invalidation, not persistent token storage. Abort/ignore stale responses with an auth-generation counter so late requests cannot restore a logged-out session.
- [x] Within each tab, deduplicate refresh promises. Across tabs, serial refresh requests may each rotate the cookie; old access JWTs remain valid within their lifetime. Login, logout and password change also participate in the lock. If Web Locks are unavailable, display an explicit unsupported-browser state rather than silently falling back to unsafe concurrent refresh.
- [x] Refresh before requests when access token is expired; do not retry unknown-result mutations. On rejected access, clear/refresh identity deliberately; on 403 refresh `/auth/me` for navigation without replaying the denied action. Clear TanStack Query caches on logout/identity changes.
- [x] Report visible-tab keyboard/click/scroll activity at most once/minute using server endpoint; bootstrap and polling are not activity. Refresh `/auth/me` on focus to reconcile changed roles without claiming real-time push updates.
- [x] Use same-origin `/api` dev proxy to FastAPI for predictable cookie behavior and retain configured backend URL support. Document same-site deployment requirements.
- [x] Run unit tests then `pnpm test:e2e tests/e2e/auth-tabs.spec.ts` against dedicated backend/database/Mailpit. Verify two tabs refreshing do not trigger replay revocation, logout propagates, and no JWT is written to local/session storage.

## Task 9: Authentication Pages and Route Guards

Dependencies: Task 8. Supplies usable auth flows and guarded mock business navigation.

Files: create auth `LoginPage.tsx`, `RecoveryPage.tsx`, `CompletePasswordPage.tsx`, `AccountPage.tsx`, `RequireAuth.tsx`, `routes.tsx`, `pages.test.tsx`, `guards.test.tsx`; modify `frontend/src/routes/routes.tsx`, `shared/layouts/DashboardLayout.tsx`, `CandidateLayout.tsx` if its internal-entry link needs updating, and `frontend/nginx.conf` for security headers.

- [x] Write interaction tests for login, generic recovery success, link completion/expiry, current-password change, current account, unauthorized deep links, role union, and loading/expired states.
- [x] Run `pnpm test src/features/auth/pages.test.tsx src/features/auth/guards.test.tsx`; observe Red.
- [x] Reuse Input/Button/Card/Toast with Tailwind. Add `/login`, `/forgot-password`, `/set-password`, and `/app/account`. Read fragment token into memory and immediately remove it with history replacement; never store it in logs or persistent browser state. Show safe resend/login paths.
- [x] Replace dashboard mock-user subscription/switcher with real AuthProvider identity and logout. Remove department display. Choose `/app` landing from account type and permitted roles; guard HR, interviewer, manager, trainee and Admin routes separately. Employee role unions permit all corresponding sections.
- [x] Preserve public candidate demonstration routes; label mock business data clearly. Hide/remove Admin work-handover and system-settings routes from the authenticated release because they expose unsupported mock operations. Do not delete their source or implement those workflows.
- [x] Apply no-referrer behavior to password pages and avoid external resources. Form submission preserves exact password characters and supports password-manager autocomplete.
- [x] Rerun page/guard tests plus typecheck. Verify browser history/back navigation cannot reveal cached account data after logout.

## Task 10: Real Account and Audit Screens

Dependencies: Tasks 7–9. Completes full-stack administration.

Files: create `frontend/src/features/admin/types.ts`, `api.ts`, `UserManagement.test.tsx`, `AuditLogs.test.tsx`; modify existing `UserManagement.tsx`, `AuditLogs.tsx`; create `frontend/tests/e2e/auth-admin.spec.ts`.

- [x] Write user-interaction tests for account type/role inputs, every lifecycle action, mandatory reasons, delivery failure/resend, audit pagination, and denied operations.
- [x] Run `pnpm test src/features/admin/UserManagement.test.tsx src/features/admin/AuditLogs.test.tsx`; observe Red.
- [x] Replace account and audit mockStore calls with TanStack Query requests and explicit snake_case mapping. Remove department inputs, emergency lock/handover, editable emails and arbitrary state toggles. Represent all five statuses distinctly.
- [x] Send whole role sets and display probation exclusivity without bypassing backend validation. Admin records have empty employee roles. Disable self-lock/self-disable controls but retain backend protection as the authority.
- [x] Show post-commit email failure without inviting duplicate account creation. Offer resend only for pending/reset-required accounts. Present safe 409/429/validation outcomes without raw exception content.
- [x] Audit screen renders genuine metadata only, with filters/cursor pagination and no mock fallback. Never show CV/evaluation payloads or invent events for mock business clicks.
- [x] Run targeted tests and `pnpm test:e2e tests/e2e/auth-admin.spec.ts`: bootstrap through CLI, retrieve invitation from local Mailpit, activate/login, create employee, activate in another browser context, change roles, lock/unlock and complete mandatory reset. Verify actual backend denial using the employee's previously issued JWT.

## Task 11: Cleanup Command, Documentation, and Release Verification

Dependencies: Tasks 1–10.

Files: extend `backend/src/app/cli.py`; create `backend/tests/integration/test_auth_cleanup.py`; update `README.md`, `docs/README.md`, `docs/architecture/overview.md`, `docs/guides/local-development.md`, `docs/engineering/conventions/frontend.md`, `docs/engineering/conventions/testing.md`; create `docs/guides/authentication.md` and `docs/architecture/decisions/2026-11-15-stateful-jwt-authentication.md`.

- [x] Test bounded cleanup preserves active refresh families and audit/account data, and removes only expired limiter/link/session-token records safe to purge. Run `uv run pytest tests/integration/test_auth_cleanup.py -q` to record Red, implement `uv run python -m app.cli cleanup-auth --batch-size 500`, then confirm Green on a dedicated database.
- [x] Document configuration names, secret generation without committing values, issuer/audience, Argon2 parameters, exact origins, CSRF, same-site cookies, Web Locks browser requirement, trusted proxies, SMTP capture ports/profile, bootstrap and recovery from email delivery failure.
- [x] Document migration target verification, separate test database and browser-test environment, cleanup scheduling as an operator action, permission-policy integration, metadata-only audit writing, and intentional mock/business limitations.
- [x] Correct stale architecture/frontend statements, preserve intentional placeholders, and link the new guide/ADR from documentation index. ADR explains JWT preference plus mandatory database checks, rejected alternatives, and resulting availability/performance tradeoffs.
- [x] Review the complete diff for secrets, accidental mock-to-auth ID conversions, swallowed audit failures, transaction rollback on replay, untrusted headers, unsafe redirects, cookie path mismatches, and test cleanup targeting application data.

## Final Verification and Handoff

Run commands only after required tooling is installed and dedicated targets are verified. Record actual outcomes; do not report skipped database/browser tests as passing.

From `backend/`:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run alembic upgrade head --sql
```

For the dedicated migrated test database, explicitly point `DATABASE_URL` to the verified test target without printing credentials before running:

```sh
uv run alembic current
uv run alembic check
```

Review migration SQL before any application, and use a clean dedicated test database for schema parity checks. An unrelated legacy table in an application database is not permission to drop it.

From `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
pnpm test
pnpm test:e2e
```

From repository root:

```sh
git diff --check
git status --short
```

Check new untracked files for whitespace and relative Markdown links as well. Inspect responsive login/password/Admin pages and record browser evidence. Verify the local-mailbox flow, cross-tab session behavior, expired-session redirects, and denied API requests independently of hidden menus.

Handoff lists completed acceptance criteria, commands/results, skipped/failed checks with reasons, configuration required before real use, and outstanding limitations. Do not commit or deploy. Obtain agreement to this plan before implementation as required by the repository workflow.
