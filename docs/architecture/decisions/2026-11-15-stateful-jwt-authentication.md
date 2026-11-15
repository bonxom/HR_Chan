# Stateful JWT Authentication

## Context

The internal workspace needs authenticated employees and administrators, revocable
sessions, role changes that take effect quickly, and an audit trail, using the
existing FastAPI + React + PostgreSQL stack. The frontend is a browser client; no
third-party API consumers exist in this release.

## Alternatives Considered

| Option | Trade-off |
| --- | --- |
| Opaque sessions only (cookie session id) | Simplest for a browser-only client, but every request needs a joined session lookup and there is no short-lived bearer credential for future service-to-service use |
| Stateless JWT only | No revocation; a locked account or revoked logout would stay valid until expiry |
| Redis-backed sessions | Adds an infrastructure component the project does not currently run |
| JWT access token + PostgreSQL session/refresh records | Revocable and supports a future non-browser client, at the cost of one database check per request |

## Decision

Use short-lived HS256 access JWTs (five minutes) plus rotating opaque refresh
tokens in an `HttpOnly` cookie, with sessions, refresh hashes, password links, and
throttling counters stored in PostgreSQL. Every authenticated request loads the
session and account and verifies revocation, idle/absolute expiry, account status,
and the session credential version, so authorization never relies on token
contents. Roles are read from the database on each authorization check.

Access tokens stay in browser memory and are refreshed through a serialized
Web Locks operation per origin. Refresh rotation detects reuse and revokes only the
affected session. Password change increments the current session's credential
version; recovery revokes all sessions.

## Consequences

- Authorization is correct after lock, logout, role change, and password reset
  without waiting for token expiry.
- Each protected request costs one indexed session/account lookup. Session and
  limiter tables grow with usage and need the bounded cleanup command.
- The frontend depends on the Web Locks API and on same-origin deployment (or an
  explicit proxy) for cookie-based refresh and CSRF protection.
- PostgreSQL is the availability dependency for authentication in this release; a
  future cache layer can be added behind the same service interfaces.
