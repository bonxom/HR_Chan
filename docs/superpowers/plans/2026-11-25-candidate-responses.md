# Candidate responses implementation plan

## Goal and references

Implement the proposed [C design](../specs/2026-11-25-candidate-responses-design.md)
after user approval. Follow the [workflow](../../engineering/workflow.md),
[backend](../../engineering/conventions/backend.md),
[frontend](../../engineering/conventions/frontend.md),
[database](../../engineering/conventions/database.md)
and [testing](../../engineering/conventions/testing.md) conventions.
The user approved the final API, renewal, cancellation, shared fake and email
proposals before implementation.

All backend paths below are relative to backend. Each task follows observed
Red → minimum implementation → Green → review. Use separate PostgreSQL databases
for migration tests and application suites, with dedicated temp directories.
Keep fixtures that remove account data reseeding dependent settings/templates.

## C1. Consent persistence

Create alembic/versions/0008_talent_pool_consent.py and
src/app/modules/candidates/consent_models.py. Register the model in alembic/env.py.
Add consent_source, talent_pool_consents and the reference unique partial index.
Insert the three missing settings with ON CONFLICT DO NOTHING.

- [x] Add tests/integration/test_consent_migration.py using a populated 0007.
- [x] Run `uv run pytest tests/integration/test_consent_migration.py -q`.
      Observe missing revision/table failure.
- [x] Apply the reviewed migration to a dedicated test target and rerun.
      Assert preserved existing data/settings, candidate FKs, expiry check,
      calendar-month calculation and active-consent uniqueness.
- [x] Use an independent NullPool connection for rolled-back schema/enum tests.
      Confirm `uv run alembic check` reports no drift.

## C2. Token reads, locks and handlers

Extend src/app/core/response_links.py with inspect and expire-under-lock.
Create src/app/core/response_handler.py for the template method.
Create src/app/modules/responses/{__init__.py,schemas.py,repository.py,service.py}.
Repository methods expose hash lookup and ordered row locking. Service exposes
resolve(token) and submit(token, action, note, policy_ver).

- [x] Add tests/unit/test_response_contract.py and
      tests/integration/test_response_transactions.py.
- [x] Run `uv run pytest tests/unit/test_response_contract.py tests/integration/test_response_transactions.py -q`,
      observing the missing behavior.
- [x] Implement public In/Out schemas and the common transaction lifecycle.
- [x] Verify read-only resolve, purpose/reference checks and fresh-time validation
      after waiting for locks, expiry equality, stale links, double-submit,
      response-versus-reissue and response-versus-expiry.
- [x] Verify a forced audit/outbox error rolls back the action and token use.
      Confirm no SQL/provider details or token in errors, logs or JSON output.

## C3. Interview responses

Create src/app/modules/responses/interview_handler.py. Extend audit schemas with
dedicated confirmation, decline, reschedule and expiry actions, retaining hidden
business metadata. Reuse working_deadline and InterviewStatus/ApplicationStatus.

- [x] Add tests/integration/test_interview_responses.py for each transition,
      blank/500/501 notes, wrong purpose, wrong state and third reschedule request.
- [x] Establish Red before applying the handler.
- [x] Implement the three actions and notify active HR with the calculated
      rescheduling deadline. Count requests under the application lock.
- [x] Verify 2 concurrent reschedule responses cannot exceed the configured limit.
      Assert confirmed and requested-reschedule interviews are protected from
      expiry of their consumed links.

## C4. Consent responses

Create src/app/modules/responses/consent_handler.py and consent_policy.py. Add
talent_pool_policy_version in src/app/core/config.py and backend/.env.example.
Use an immutable talent-pool text registry and calculate months using PostgreSQL
in Asia/Ho_Chi_Minh.

- [x] Add tests/integration/test_talent_pool_responses.py, run Red.
- [x] Implement explicit acceptance, decline and per-candidate serialization.
- [x] Verify policy changes return 409 before consuming the token. Assert a
      still-valid consent keeps its dates, an expired row is renewed only on a new
      acceptance with audited before/after values, and revoked rows remain history.
- [x] Compare the echoed consent_snapshot against server state under lock. Test
      expiry between resolve/submit and simultaneous consent from another
      application. Return 409 consent_changed and require another explicit click.
      Assert valid-grant UI states the real deadline and retained policy version.
- [x] Verify valid mode allows only “Đã hiểu”, distinct acknowledgement audit and
      ACCEPTED link outcome. Reject decline while valid; stale decline returns 409.
      Unknown original policy/evidence fails closed. Preserve revoked history and
      create a fresh grant only on explicit Yes under current policy.
- [x] Test concurrent acceptance from different applications, month ends and leap
      years. Decline/expiry cannot create or extend consent.

## C5. Durable cancellation, expiry and notifications

Create src/app/modules/responses/{expiry.py,calendar_sync.py}. Extend
src/app/modules/notifications/{schemas.py,seeds.py} with the four specified templates.
Wire bounded, drained jobs into src/app/worker.py using its existing runner.
Extend the fake Google only as needed to exercise idempotent retry.

- [x] Add tests/integration/test_response_expiry.py and
      tests/unit/test_response_worker.py. Run Red.
- [x] Implement transactional expiry and flagged cancellation, then startup and
      periodic sweeps. Claim parent rows before links with SKIP LOCKED.
- [x] Verify one bad row permits progress, concurrent workers process each link
      once, invalidated links skip expiry and repeated sweeps send no duplicate mail.
- [x] Inject Google failure, commit failure, crash after commit and successful
      cancel before flag clearing. Verify eventual cleanup through the existing
      flag and no repeat notifications.
- [x] Perform the remote cancel outside DB transactions. Test confirmed
      already-deleted success and ambiguous/access failure retaining the flag.
      Verify timeout and ID cursor wrap-around across bounded retry batches.
- [x] Make the worker the sole remote-cancellation caller, retain its cursor across
      sweeps and advance past failures. Protect pending event IDs from replacement.
      Expose the current cleanup flag via applications/review_service.py.
- [x] Extend src/app/integrations/google_workspace/client.py for private SQLite
      event state and src/app/integrations/factories.py for configured shared path.
      Add FAKE_GOOGLE_DB_PATH to core/config.py and backend/.env.example, and
      backend/.local/ to .gitignore. Add tests/integration/test_shared_google_fake.py
      verifying two processes create/cancel/query the same file, restart survival,
      repeated cancel success, unknown ID failure and bounded busy/locked errors.
- [x] Verify rendered candidate mail contains no internal score or notes and
      template seeds preserve edited templates on rerun.

## C6. Public API

Create src/app/modules/responses/router.py and register it in
src/app/api/v1/router.py. Add cache/referrer headers and token-free fixed paths.
Use the existing structured AppError format.

- [x] Add tests/integration/test_response_http.py and establish Red.
- [x] Implement POST /api/v1/responses/resolve and /submit.
- [x] Test anonymous requests, malformed/unknown/consumed tokens, rejected actions,
      stale policy, oversized input and missing notes. Verify full public payload
      shape, safe errors, cache headers and resolve without changes in DB.
- [x] Add ResponseReceiptOut. Resolve a used token before original expiry to only
      completed/outcome/completed_at; reject replayed mutations. Verify the receipt
      is stable across subsequent domain changes and unavailable at expiry.
- [x] Verify FastAPI validation errors exclude the token in field and model-level
      input, and uncertain submissions have a safe explicit status-check path.
- [x] Update the OpenAPI route contract test for the two new endpoints.

## C7. Candidate page

Create frontend/src/features/responses/{ResponsePage.tsx,api.ts,types.ts,routes.tsx}.
Register /r/:token and /r in frontend/src/routes/routes.tsx.
Create frontend/src/features/responses/tokenBootstrap.ts and load it first from
frontend/src/main.tsx before router/application imports initialize.
Use existing Tailwind components and the shared HTTP client. The page has an
interview summary with actions or a consent policy with an explicit checkbox.

- [x] Add ResponsePage.test.tsx and api.test.ts beside the feature.
- [x] Run `pnpm test -- src/features/responses` and observe Red.
- [x] Implement memory-only token capture, browser URL replacement and response
      actions with disabled submission while pending.
- [x] Verify opening alone never submits, consent begins unchecked, the third
      reschedule action is unavailable, and validation/server/network errors retain
      a comprehensible next action. Test Vietnamese acknowledgements and time display.
- [x] Verify token-free query keys/storage/logging, no automatic mutation retries,
      and /r after refresh asks to reopen the email.
- [x] Test React StrictMode remounts, token capture before router initialization,
      status-check after lost response and the actual consent-expiry wording.
- [x] Verify completed receipt display, explicit status check after network failure,
      manual retry for an open link and 409 refreshing consent before a new click.

## C8. Browser and complete verification

Add frontend/tests/e2e/candidate-responses.spec.ts. Seed through the existing invitation
and rejection entry points and use the queued email URL. Update
docs/guides/local-development.md, docs/architecture/overview.md and README.md for
implemented behavior and worker operations.
Update frontend/nginx.conf for entry-document no-store and token-path access-log
suppression, preserving the existing security headers. Document upstream proxy
redaction requirements and test the served headers in browser verification.

- [x] Run targeted PostgreSQL tests, then `uv run ruff check .`,
      `uv run ruff format --check .` and `uv run pytest` from backend.
- [x] Run `pnpm test`, `pnpm run typecheck`, `pnpm run build` and
      `pnpm exec playwright test tests/e2e/candidate-responses.spec.ts` from frontend.
      Verify the actual email route, cleared URL,
      form submission and consumed-link page using the real API.
- [x] Compare imported reference hashes and run `git diff --check`.
- [x] Submit changed implementation to Claude for one static review after local
      checks, subject to the user's approval for any new external code payload.
      Report unresolved findings before further fixes, as instructed by the user.
- [x] Report changed files/endpoints, exact pass/fail/skip counts, decisions and
      remaining phases. Commit and push require a new explicit instruction.

## Local verification on 26 November

The complete backend suite passed 961 tests against dedicated PostgreSQL,
with Mailpit and ClamAV smoke enabled. Alembic reported no ORM drift. Ruff lint
and format passed for 226 Python files. Two existing warnings concern Starlette's
TestClient dependency and a SHA512 test key length.

Frontend typecheck and build passed. Full Vitest passed 178 tests across 22 files
with one worker. An initial parallel run had two unrelated five-second timeouts;
the serial rerun passed without changing those tests. Vite retained its existing
large-bundle warning. Two Playwright tests passed against the actual API and
Mailpit, covering email navigation, interview confirmation, receipt, refresh and
explicit consent. Served Nginx entry headers, configuration and token-path log
suppression were checked using a synthetic canary. All eight imported reference
files matched their source hashes.

The user explicitly authorized sharing the new C source for one static Claude
review after the checks. That one review found a material fairness defect in both
ResponseExpirySweep and CalendarCancellationSweep. Each resets its cursor only
after an empty query, so a steady stream of newer eligible IDs can prevent a retry
of an older failed, locked or newly eligible row indefinitely.

The owner approved the finite-pass fix on 26 November. At pass start, capture
the highest eligible ID. Bound every batch to cursor < id <= watermark. On range
exhaustion reset cursor and watermark, then start a new finite pass. Add batch_size=1
regressions for both sweeps with continual higher-ID arrivals and recovery of the
older row. Four new regressions first failed on the old code, then passed after
the fix, covering delayed eligibility and retry after failure for both sweeps.
All 14 expiry/calendar tests and Ruff lint/format passed. Full regression
verification after this fix passed 965 tests, with the two existing warnings. The static review was performed once;
the approved fix is verified locally.

Phase C verification is complete. Transaction tests were consolidated into interview response and talent-pool response suites. The approved review finding is resolved. No commit or push has been performed for C.
