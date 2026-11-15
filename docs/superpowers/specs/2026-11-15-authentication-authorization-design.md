# Authentication and Authorization Foundation

## Goal and Context

Provide working authentication, account administration, and reusable authorization
for the HR recruitment and onboarding platform, including the React user flows.
This specification records the decisions agreed during requirements discussion.
Detailed API and storage choices below are proposed for review with this document.

The backend currently supplies FastAPI module scaffolds, async SQLAlchemy session
dependencies, centralized errors, and Alembic. Authentication services, schemas,
and security dependencies are placeholders. Migration `0001` enables pgvector;
it creates no account tables. The frontend has demonstration users, role switching,
account administration, and business screens backed by mock data.

Follow the [engineering workflow](../../engineering/workflow.md),
[backend conventions](../../engineering/conventions/backend.md),
[frontend conventions](../../engineering/conventions/frontend.md),
[database conventions](../../engineering/conventions/database.md), and
[testing conventions](../../engineering/conventions/testing.md).

## Scope

Included:

- Login, logout, current account, password change and recovery, email invitations,
  session expiration and revocation, and temporary login throttling.
- Employee and Admin account creation, account listing, role replacement, locking,
  unlocking, disabling, and security/administrative audit viewing.
- JWT access tokens and rotating refresh tokens with server-side session checks.
- Backend role checks and an explicit integration point for resource policies.
- React authentication pages, invitation/recovery pages, account/password pages,
  real account management and audit screens, route/menu guards, and session handling.
- Local email delivery into a development mailbox, with configurable SMTP delivery.
- Database migrations, a first-Admin CLI, and behavioral tests.

Excluded:

- Public registration, email changes, account-type changes, disabled-account
  restoration, departments, business API implementations, MFA, SSO, mobile clients,
  third-party API access, dual approval, and personal audit-history pages.
- Advanced work handover and emergency-lock workflows present in frontend mocks.
- Production email credentials, deployment, commits, and destructive data operations.

Business mock screens remain available behind frontend role guards. Their bundled
data is demonstration data, not confidential data protected by backend policies.
Remove mock identity switching from the authenticated application. Do not claim
that client-side guards protect bundled mock data.

## Requirements and Expected Behavior

### Identities and roles

- Account types are `ADMIN` and `EMPLOYEE`; type cannot change after creation.
- Admin identities cannot carry employee roles or access protected business APIs.
  Admin is not a universal permission bypass.
- Admin operators are trusted to provision accounts responsibly. Preventing a
  human administrator from creating an employee identity they control is outside
  the chosen trust model.
- Employee roles are `HR`, `INTERVIEWER`, `DEPT_MANAGER`, and `PROBATION`.
- Every employee has at least one role. `PROBATION` must be the only role when
  present; the other three roles may be combined.
- Multiple roles grant the union of their permissions. A frontend role selector
  changes presentation only, never the backend authority of the account.
- Only Admin can create accounts or replace employee roles. Replace the entire
  role set atomically, including transitions out of probation.
- Resource access must satisfy a permission-granting policy for the current
  account and object. A missing policy does not authorize access. Future modules
  own assignment, ownership, and department rules; this feature does not invent them.
- Role changes preserve sessions and take effect on requests authorized after the
  change commits. Already authorized in-flight work is not retroactively canceled.

### Account information and lifecycle

Store full name, email, account type, employee roles, account status, and security
metadata. Email must belong exactly to `sis.hust.edu.vn`; subdomains are not
implicitly accepted. Configure the domain allowlist on the backend. Treat login
emails as case-insensitive, normalize before uniqueness checks, and reject
duplicates. Do not allow email modification in this release.

Do not add a department field or table. Add an English comment in the account ORM
model explicitly explaining that departments and department-scoped authorization
are deferred until organizational data and corresponding business modules exist.

| Status | Meaning | Login allowed |
| --- | --- | --- |
| `PENDING_SETUP` | Created, awaiting initial password | No |
| `ACTIVE` | Initial setup complete | Yes |
| `LOCKED` | Administratively locked | No |
| `PASSWORD_RESET_REQUIRED` | Unlocked, awaiting new password | No |
| `DISABLED` | No longer in use; retained for history | No |

- Creation produces `PENDING_SETUP` and sends an invitation.
- Successful initial setup changes `PENDING_SETUP` to `ACTIVE`.
- Locking a non-disabled, non-locked account changes it to `LOCKED`, revokes all
  sessions and outstanding password links, and requires an administrative reason.
- Unlocking is valid only from `LOCKED`. It changes the account to
  `PASSWORD_RESET_REQUIRED`, invalidates its previous password, and sends a reset
  link. Successful reset changes it to `ACTIVE`.
- Disabling any non-disabled account requires a reason, revokes sessions and links,
  and changes it to `DISABLED`. There is no restoration endpoint in this release.
- Locked and disabled accounts cannot use public password recovery. Pending setup
  and reset-required accounts can request another appropriate email.
- Admin cannot lock or disable themselves. Protect the final active Admin,
  including concurrent administrative requests. Pending Admin invitations do not
  count as active administrators.
- Admin may create and administer other Admin accounts without password
  reauthentication. Role replacement applies only to employees.
- Bootstrap the first Admin with a server-side CLI accepting name and allowed email.
  It works only when no Admin account exists, creates a pending Admin, and sends an
  invitation. Serialize concurrent bootstrap attempts. If delivery fails, the
  existing pending Admin can request another invitation through public recovery.

### Passwords and email links

- Passwords are 8–128 Unicode characters. Allow spaces, Unicode, paste, and password
  managers. Do not trim or normalize passwords or impose composition rules.
- Hash passwords with Argon2id using a maintained library; select and document its
  parameters during implementation. Never store or email plaintext passwords.
- A signed-in password change requires the existing password. Keep the performing
  session, rotate its credentials, and revoke every other session.
- Public recovery leaves an active account and its sessions unchanged until a new
  password is successfully set. Completion revokes all sessions and requires login.
- Invitation links expire after 24 hours. Recovery and post-unlock reset links
  expire after 30 minutes. Use random tokens and store only their hashes.
- Multiple unexpired links may coexist. Completing one consumes it and invalidates
  every other outstanding setup/recovery link for the account, in one transaction.
  Concurrent use must produce at most one successful completion.
- Invalid, expired, and consumed links return the same safe error and offer a path
  to request another email. Locked or disabled accounts cannot complete old links.
- Public recovery always returns the same generic accepted response, regardless
  of account existence, status, delivery outcome, or account-level throttling.
- Enforce at least 60 seconds between sends and no more than five sends per hour
  per account, across invitation and recovery entry points. Add an IP limit;
  proposed initial value is 20 public requests per hour per source IP.
- Construct email links from a configured frontend URL, not request Host headers.
  Do not log link tokens. Use a URL fragment for the frontend to read and remove
  before submitting the token in a POST body; exclude third-party resources from
  password setup/recovery pages and set an appropriate referrer policy.
- Use a local SMTP capture mailbox in development. Production delivery requires
  explicit SMTP and public URL configuration; do not send credentials in chat or
  commit them. No real email service is provisioned by this task.

### JWT and sessions

- Access tokens are signed JWTs valid for five minutes. Include subject, session
  identifier, issuance/expiration, issuer, audience, and session credential version.
  Do not use embedded roles as the authority for authorization.
- Verify the configured algorithm, signature, issuer, audience, and expiry; never
  accept an algorithm selected freely by an untrusted token. Signing secrets or
  keys are backend-only configuration, with no usable production default.
- The React app keeps access tokens in memory, not local or session storage.
- Refresh tokens are opaque random secrets in an `HttpOnly` cookie. Store only
  their hashes. Rotate on successful refresh and keep enough token-family state to
  detect reuse. Reuse revokes the associated session; it does not revoke unrelated
  devices. Serialize frontend refresh operations, including across tabs, so normal
  concurrent requests do not accidentally reuse a token.
- Refresh and logout clear or replace the cookie as appropriate. Production cookies
  use `Secure`, explicit `SameSite`, and a narrowly scoped path. Local HTTP settings
  are development-only. Cookie-authenticated endpoints require CSRF protection
  and trusted-origin validation; CORS alone is insufficient.
- Each protected request verifies that the session is current, unrevoked, and
  unexpired, that the account is active, and that the JWT credential version matches.
  Load current roles from the database. Thus an unexpired JWT cannot bypass a lock,
  logout, password reset, or role update.
- Logout revokes the current session. Password recovery revokes all sessions.
  Password change preserves only its current session and rotates that session's
  credentials, so old access/refresh tokens for it cannot continue to be used.
- Idle expiry is 30 minutes; absolute expiry is 12 hours from initial login.
  Refresh and polling do not extend either limit by themselves.
- Visible-tab typing, clicking, and scrolling trigger a rate-limited authenticated
  activity signal, proposed at most once per minute. Persist activity server-side;
  never trust a client-supplied timestamp or revive an expired session. The signal
  represents reported UI activity, not proof of a human presence.
- On reload, bootstrap authentication with the refresh cookie and then fetch the
  current account. Expired sessions require login. Do not automatically replay a
  mutation whose previous result is unknown.

### Login throttling

- Use a generic login failure for unknown email, incorrect password, and accounts
  that cannot log in. Perform comparable password-verification work for unknown
  accounts to reduce obvious enumeration differences.
- Five failed attempts within 15 minutes temporarily block login attempts for that
  normalized identifier for 15 minutes. This is separate from account status and
  does not require Admin intervention or password reset. Successful login clears
  the identifier failure counter.
- Add a separate IP limit; proposed initial value is 50 login attempts per 15
  minutes. Only trust forwarded IP headers from explicitly configured proxies.
- Share throttling state across backend workers. Do not rely on process-local
  counters. Apply bounded retention to limiter entries.

### Audit and failure handling

- Admin can view security, administrative, and future business event metadata:
  actor identifier, action, timestamp, outcome, and opaque target identifier/type.
  Explicitly allowlist extra fields; do not serialize arbitrary domain objects.
- Record login success/failure, explicit logout, password setup/change/reset,
  account creation/status changes, role changes, and refresh-token replay events.
  Do not record plaintext passwords, tokens, CV contents, evaluations, or arbitrary
  submitted email addresses in failed-login logs.
- Admin reasons belong to administrative audit events. Do not expose them through
  ordinary current-account responses. No audit-edit/delete API is provided.
- Commit administrative/security state mutations and their audit records together.
  An audit persistence failure rolls back the corresponding state change.
- Do not send SMTP inside a database transaction. Persist the account/link/audit
  first, then attempt delivery. A failed send leaves the account intact; Admin sees
  a safe delivery-failure result and can retry, while public recovery stays generic.
  Automatic delivery guarantees and a background email queue are outside this release.
- Existing mock business events are not imported as genuine audit records. Future
  business modules call the shared audit writer in their own transactions.

## Design and Alternatives

Use the existing modular monolith and router → service → repository flow. Routers
handle HTTP and dependency injection; services own transactions and state rules;
repositories own SQL access. Reuse `AppError`, settings, async sessions, and the
application lifecycle. Keep `/health` independent of database availability.

- `modules/auth`: login, tokens, password links, credentials, sessions, and schemas.
- `modules/accounts`: account models, role/status rules, administration, and CLI support.
- `core/security.py`: small reusable identity/permission dependencies and policy
  interfaces delegating domain decisions to services; no generic policy engine.
- `modules/audit`: append-only application writer and Admin list API.
- `integrations/email`: configurable SMTP adapter and message templates.
- Frontend auth feature/provider: in-memory token, serialized refresh, activity
  reporting, login/recovery/setup/password pages, and route guards. Existing Admin
  screens use the real accounts/audit APIs and remove unsupported mock operations.

The chosen JWT-plus-refresh design follows the user's preference and supports
server-side revocation. It intentionally does not provide stateless authorization.
Opaque sessions alone would be simpler for a browser-only client; Redis-backed
sessions would introduce infrastructure not currently required. PostgreSQL holds
session and limiter state, avoiding Redis in this release.

## API Contract and Errors

All routes below are under `/api/v1`. JSON responses use snake_case, with explicit
frontend mapping where existing presentation types use camelCase. IDs are UUIDs;
timestamps are UTC ISO 8601. Password/token fields are write-only.

`AccountRead` contains `id`, `full_name`, `email`, `account_type`, `roles`, `status`,
`created_at`, and `last_login_at`. Admin accounts return an empty employee-role list;
the frontend derives Admin presentation from `account_type`.

| Method and route | Input | Success and behavior |
| --- | --- | --- |
| `POST /auth/login` | `email`, `password` | 200: `access_token`, `token_type: bearer`, `expires_in`, `account`; set refresh/CSRF cookies |
| `GET /auth/csrf` | None | 200: bootstrap CSRF protection for cookie-based flows; no account details |
| `POST /auth/refresh` | Refresh cookie and CSRF proof | 200: new access token metadata; rotate refresh cookie |
| `POST /auth/logout` | Refresh cookie and CSRF proof | 204: revoke current session and clear cookies; safe when already absent/revoked |
| `GET /auth/me` | Bearer token | 200: `AccountRead` |
| `POST /auth/activity` | Bearer token; no timestamp | 204: report activity without extending absolute expiry |
| `POST /auth/password/change` | Bearer token, `current_password`, `new_password` | 200: replacement access token metadata and refresh cookie; revoke other sessions |
| `POST /auth/password/recovery` | `email` | 202: generic response; send setup/recovery link when eligible |
| `POST /auth/password/complete` | `token`, `new_password` | 204: complete setup/reset; require login |
| `GET /accounts` | Admin; `cursor`, `limit`, optional `status`, `account_type` | 200: paginated `AccountRead` items and `next_cursor` |
| `POST /accounts` | Admin; `full_name`, `email`, `account_type`, `roles` | 201: `account`, `email_delivery: sent or failed` |
| `PUT /accounts/{id}/roles` | Admin; complete `roles` array | 200: updated `AccountRead`; employee only |
| `POST /accounts/{id}/lock` | Admin; nonempty `reason` | 200: updated `AccountRead` |
| `POST /accounts/{id}/unlock` | Admin | 200: `account`, `email_delivery: sent or failed` |
| `POST /accounts/{id}/disable` | Admin; nonempty `reason` | 200: updated `AccountRead` |
| `POST /accounts/{id}/invitation` | Admin | 200: delivery result; pending setup/reset-required only |
| `GET /audit-events` | Admin; `cursor`, `limit`, optional `actor_id`, `action`, `target_type`, `target_id`, `from`, `to` | 200: metadata-only items and `next_cursor` |

Login and other browser-origin authentication flows also validate trusted origins.
Any endpoint that relies on or changes cookie-held credentials uses the CSRF
mechanism. Bearer-only protected APIs do not silently fall back to cookie authentication.

Bound full names to 1–200 characters after trimming, reasons to 1–1000 characters,
and page sizes to 1–100 with a default of 25. Validate roles against the fixed enum;
reject duplicates and invalid combinations. Admin creation requires an empty roles
list; employee creation requires a valid nonempty list.

Preserve `AppError` as `error.code` and `error.message`; request-schema validation
retains FastAPI's 422 format. Use 401 for invalid credentials/sessions, 403 for
insufficient permission or invalid CSRF proof, 404 for missing Admin-managed targets,
409 for duplicate email, invalid status transitions, and protected-Admin conflicts,
400 for invalid password links, and 429 with `Retry-After` for exposed throttles.
Public recovery masks account-specific throttles; IP throttles may return 429.
Unexpected errors return the existing generic 500 without secrets.

## Storage and Migration

Proposed persistence:

| Table | Principal fields and constraints |
| --- | --- |
| `accounts` | UUID PK, unique normalized email, full name, immutable account type, status, nullable password hash, employee-role array, created/updated timestamps, last login timestamp |
| `auth_sessions` | UUID PK, account FK, credential version, created/last-activity/absolute-expiry timestamps, revocation timestamp and reason |
| `auth_refresh_tokens` | UUID PK, session FK, unique token hash, issued/expiry/consumed timestamps; retain consumed records for replay detection until session expiry |
| `auth_password_links` | UUID PK, account FK, purpose, unique token hash, created/expiry/consumed/invalidated timestamps |
| `auth_rate_limits` | Keyed action/identifier or IP digest, window counters and block expiry; bounded cleanup |
| `audit_events` | UUID PK, nullable actor/target identifiers, action, outcome, timestamp, allowlisted metadata |

Use a fixed role array with database checks for known values, distinct entries,
nonempty employee roles, Admin exclusion, and probation exclusivity. This avoids a
generic editable roles/permissions framework while enforcing invariants in storage.
Application permissions remain code-defined and extensible by future modules.

Lock the account row for password-link consumption and competing credential/status
changes. Lock session/token rows for refresh rotation. Use one transaction-scoped
administration lock for Admin creation and active-Admin status changes, then recheck
the final-Admin invariant; a count performed outside that lock is insufficient.
Persist role/status changes and their audit events atomically. Failed authentication
and replay events must commit their defensive state even when the API returns an error.

Add a new migration after `0001`, import models into Alembic metadata, and review
generated SQL and checks. Do not alter shared migration history, drop an existing
legacy `jobs` table, reset volumes, or assume local application data is disposable.
Apply only reviewed migrations to an explicitly verified database. Tests use a
separate migrated PostgreSQL database. No schema changes run on API startup.

## Acceptance Criteria and Verification

- A CLI-created Admin can set a password through the local mailbox, log in, create
  employee/Admin accounts, and view their genuine audit events through React.
- Only exact allowed-domain addresses are accepted; email uniqueness is
  case-insensitive. Invitations and recovery do not create unrequested accounts.
- Role combinations and all lifecycle transitions follow the rules above. ORM
  comments document intentional department deferral.
- A valid JWT is rejected after session revocation/account locking; role changes
  affect the next authorization check without forcing login.
- Password change preserves and rotates only its current session; recovery revokes
  all sessions. Old credentials and consumed/revoked links cannot be reused.
- Refresh rotation/replay protection works under concurrent requests and normal
  multi-tab use. Access tokens never enter browser persistent storage.
- Idle and absolute expiry are independently tested with controlled time. Background
  refresh/polling cannot keep a session alive; reported UI activity cannot revive it.
- Self-lock/disable, concurrent loss of the final active Admin, duplicate bootstrap,
  duplicate normalized emails, and simultaneous password-link use are covered by
  PostgreSQL integration tests.
- Unknown-account and ineligible-account public recovery responses are equivalent.
  Throttling is shared across app instances and does not change account status.
- CSRF, origin validation, cookie settings, JWT validation, role denial, and default
  resource-policy denial have explicit negative tests.
- Email failure preserves account state and offers retry; audit failure rolls back
  administrative mutations. Audit responses contain no sensitive business payloads.
- React tests cover login/logout, setup/recovery/change-password, session expiry,
  role-driven navigation, account management, and delivery failures. Add a frontend
  behavioral test runner during implementation; typecheck/build alone are insufficient.
- Keep `/health` working without database connectivity. Run targeted tests, full
  pytest, Ruff lint/format, frontend typecheck/build, behavioral tests, migration SQL
  review, and dedicated database integration checks per project conventions.
- Update architecture and local-development guidance, including SMTP capture,
  allowed domains, signing configuration, CSRF/origins, CLI bootstrap, session
  cleanup, test database setup, and the mock-data limitation.

The next step after user approval of this specification is an implementation plan
with exact files and verification commands. No application implementation, commit,
deployment, or migration application is authorized by creation of this document alone.
