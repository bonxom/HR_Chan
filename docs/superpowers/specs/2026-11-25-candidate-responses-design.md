# Candidate responses and expired response links

## Goal and references

Make the interview and talent-pool URLs issued by A/B usable. The user approved
phase C and recording overdue links as EXPIRED with used_at. This document proposes
the remaining contracts for approval before implementation.

Read [context](../../context/00_CONTEXT_DU_AN.md),
[use cases and business rules](../../context/01_use_case_va_quy_tac_nghiep_vu.md)
and [previous design](2026-11-25-application-scoring-review-design.md).
The relevant flows are interview confirmation and talent-pool consent, including
their response deadlines. The current response-link core already issues hashes,
locks valid links, consumes them and invalidates replacements. The candidate action
screens currently use local demonstration state.

## Scope

Deliver public /r/{token} for interview confirmation, rescheduling request,
interview decline and talent-pool acceptance/decline, plus expired-link processing.
Google remains FakeGoogleWorkspace. Notifications use the existing encrypted outbox.
Future phases cover HR rescheduling/cancellation screens, probation offer responses,
consent withdrawal and retention deletion, and live Google/AI integration.

## Public contract and interface

Add POST /api/v1/responses/resolve with {token}. It returns ResponseViewOut with
completed=false, purpose, job_title, expires_at and allowed_actions. Interview views also contain
start_at, meet_link and whether another rescheduling request is allowed. Consent
views contain consent_mode, policy_ver, policy_text, retention_months, an opaque consent_snapshot,
and the existing consent deadline when it is still valid. The snapshot is a digest
of the server's consent state, validity, grant dates and applicable policy/retention
settings, and conveys no authorization.

Add POST /api/v1/responses/submit with
{token, action, note?, policy_ver?, consent_snapshot?}.
Action values are ACCEPTED, DECLINED and RESCHEDULE_REQUESTED. The service chooses
the handler from the stored purpose. The success result is ResponseResultOut with
outcome, resulting application/interview status when relevant and a Vietnamese
acknowledgement. It exposes no token, internal score, internal reason or storage key.

Use Pydantic schemas with extra=forbid. The token is a nonempty string with a
bounded length sufficient for the existing 32-byte token_urlsafe format. A reschedule
note is trimmed, required and at most 500 characters. Interview decline requires
a trimmed reason of at most 500 characters, matching the context's “kèm lý do”.
Consent accepts ACCEPTED or DECLINED. ACCEPTED requires the displayed policy version
and consent_snapshot. Under the candidate lock, recompute the current snapshot and
check validity at the decision instant. Changes to policy return 409 policy_changed;
changes to consent state return 409 consent_changed. Both preserve the token and
require refreshed text and another explicit click. A real note/policy error returns
422 without consuming the link.

Resolve reads without locks or writes. Opening a URL or an email scanner cannot
consume it. A used token before its original expiry returns ResponseReceiptOut
with only completed=true, outcome and completed_at, taken from its consumed link
record. This explicitly revises the earlier generic error for used tokens. A
receipt carries no candidate, job, score or current domain state. Submit replays
remain rejected. Unknown, expired, invalidated, unsupported-purpose links and
stale domain states return a generic 422 invalid_response_link. A race lost after
the page loaded returns the same response and instructs the candidate to reopen
the latest email. Temporary database failure returns a safe retryable 503.

The SPA adds a responsive ResponsePage using the current candidate typography,
layout and Tailwind components. It shows local Vietnam time and the deadline,
purpose-specific actions, note validation, a busy state and the final result.
Consent acceptance requires an explicit unchecked checkbox beside the policy text.
Capture the token into a module-scoped memory store before the router initializes,
then replace the browser URL with /r. This survives React StrictMode remounts.
A refresh at /r asks the candidate to reopen the email. Add Referrer-Policy no-referrer and
Cache-Control private,no-store to the page and API responses. API paths use a
fixed route with the token in the POST body. Query keys, analytics, logs and error
reports exclude the token. Suppress raw input values in validation error responses
for these two API routes, including model-level errors with the entire request as
input. Keep the existing error contract elsewhere. The frontend serving config
suppresses access logging of /r/{token} while retaining security headers.
An upstream proxy requires the same path redaction. Browser URL replacement cannot
erase the initial request from unconfigured proxies, email scanners or extensions.

Mutations have no automatic retry. On uncertain network outcome explain that the
action may have been recorded and provide an explicit status check through resolve.
If still unused, another submit requires another click and rechecks under lock.
If resolve returns a receipt, show the recorded outcome and time. If the link is
still open, allow a deliberate new click. If a retry loses a race, resolve again.
A generic invalid/expired error does not claim the uncertain attempt failed.

For a new or expired grant, the proposed consent text is
“Tôi đồng ý để công ty lưu hồ sơ của tôi trong
{retention_months} tháng để liên hệ khi có vị trí tuyển dụng phù hợp.” Persist the
current talent_pool_policy_version with the actual accepted record. This dedicated
setting is separate from the existing CV-processing consent_policy_version.
The proposed initial version is talent-pool-v1, within the schema's 20-character
limit. Keep an immutable version-to-text registry in consent_policy.py. Record
rendered text, months, version and grant dates in the hidden grant audit evidence.
Use default talent_pool_months=12 from reference SQL.
For an existing valid grant, show “Sự đồng ý lưu hồ sơ hiện tại có hiệu lực đến
{expires_at}. Xác nhận này giữ nguyên thời hạn và phiên bản chính sách của lần
đồng ý đó.” Show the original version and original evidence. If that text/evidence
cannot be resolved, fail closed with a safe consent_policy_unavailable response.
This mode offers one “Đã hiểu” acknowledgement button with no new grant checkbox.
It maps to ACCEPTED on the link and a distinct acknowledgement audit. It leaves
the grant policy and dates intact. Reject DECLINED while a valid grant exists.
A grant appearing or expiring after resolve returns 409 without consuming the
token, then the page refreshes to the appropriate mode and requires a new click.

The page is presented in Vietnamese without requiring a candidate account. The
approved scope introduces a new public workflow, backend handlers and background
work, so it follows the architectural design and approval path.

## Domain transitions

| Purpose and action | Interview | Application | Link |
| --- | --- | --- | --- |
| Interview ACCEPTED | SCHEDULED → CONFIRMED | INTERVIEW_INVITED → INTERVIEW_CONFIRMED | ACCEPTED, used_at |
| Interview RESCHEDULE_REQUESTED | SCHEDULED → RESCHEDULE_REQUESTED, save note | INTERVIEW_INVITED | RESCHEDULE_REQUESTED, used_at |
| Interview DECLINED | SCHEDULED → CANCELLED, save decline reason | INTERVIEW_INVITED → INTERVIEW_DECLINED | DECLINED, used_at |
| Interview expires | SCHEDULED → CANCELLED, reason “Không phản hồi trong thời hạn” | INTERVIEW_INVITED → INTERVIEW_DECLINED | EXPIRED, used_at |
| Consent ACCEPTED | — | Current application state | ACCEPTED, used_at |
| Consent DECLINED | — | Current application state | DECLINED, used_at |
| Consent expires | — | Current application state | EXPIRED, used_at |

At commit, verify the link still references its original application and interview.
Honor the configured maximum rescheduling requests, default 2. Count successful
request audit events across the application under its row lock, including prior
interviews. HR notification records the request time and working_deadline(now,
reschedule_handle_days), default 1. Phase D uses that deadline for its reminder.

An active consent already covering the candidate keeps its original consent date,
policy and expiry. Consume the new link and audit the acknowledgement. An expired
row with revoked_at NULL is renewed in place only on a new ACCEPTED response,
updating source, application, dates and policy and auditing the prior snapshot.
A revoked row remains historical and a new row is inserted. The proposal preserves
the reference partial unique index while requiring fresh permission to renew.
Serialize consent writes for the candidate across different applications.
Calculate expiry as PostgreSQL calendar months in Asia/Ho_Chi_Minh, including
month-end clipping. This uses the established business timezone throughout C.

## Transactions and external effects

Implement a ResponseHandler template method for verification, domain action,
audit and consumption. Its concrete handlers are InterviewResponseHandler and
TalentPoolResponseHandler. The services own transactions.

Read the link hash first to discover references, then lock application, interview
when applicable, candidate for consent, and link in that order. Recheck link hash,
purpose, references, domain states and deadline after all lock waits, sampling
database clock_timestamp() as the decision instant. All mutation
paths, expiry and future HR invalidation must use the same ordering. Existing
issue follows application-first ownership for invite/reject. Extend the core with
a read-only inspect and an expire-under-lock operation. Existing verify continues
to reject expired links. Expire requires used_at/invalidated_at NULL and expires_at
less than or equal to the freshly sampled decision time. It records EXPIRED and
used_at without invalidated_at.

Persist business state, version increment, link outcome, notification outbox rows
and audit in one transaction. Candidate/system actions use a null audit actor.
Set app.actor_id locally to the empty string to prevent actor leakage into history.
Keep notes and reasons in allowlisted hidden business metadata. Failed validation
or SQL rolls back link consumption and all associated writes.

For decline/expiry set needs_manual_calendar_fix=true in the same transaction as
CANCELLED. Commit the decision first. Only the worker cancels the stored event.
The candidate acknowledgement says cancellation has been recorded and calendar
cleanup is pending. Expose the current cleanup flag in the protected HR detail.
A successful idempotent cancellation clears the flag in a separate transaction
after matching the same cancelled interview and event ID. A Google failure or
process crash leaves durable recovery state. A worker sweep retries flagged
cancelled events. Log the event ID and alert HR once from the original decision
outbox. An interview missing its event ID retains the flag and alerts HR. The retry
sweep selects flagged CANCELLED rows with a nonempty google_event_id.

The Google call occurs outside PostgreSQL transactions. Confirmed already-deleted
events count as success. Access errors and ambiguous not-found results retain the
flag. Retry every 60 seconds with a per-call timeout and a bounded batch. Carry an
in-memory interview-ID cursor across sweeps and wrap around so repeatedly failing
rows cannot starve later ones. Advance the cursor past failures and timeouts.
Capture the highest eligible ID at pass start and bound batches to that ID.
On range exhaustion reset both cursor and bound. This makes each pass finite
even while new higher-ID work keeps arriving. Apply the same rule to link expiry.
Restart resets its position, so fairness requires enough uptime to scan the backlog.
Pending event IDs cannot be replaced or discarded until cleanup is resolved. Remote
cancellation targets the exact stored event ID. HR wording says cleanup is pending.
Only the original decision transaction queues notification emails. Remote retries
send no additional emails. Atomic outbox insertion prevents duplicate enqueueing
for the same consumed link; SMTP delivery itself can still be repeated after a
lost acknowledgement.

## Shared Google fake

The current Google fake stores events in process memory. Separate API and worker
processes require shared event state for demonstrable cancellation and busy lookup.
Use Python's sqlite3 inside this development adapter, with a private file selected
by FAKE_GOOGLE_DB_PATH. The proposed default is
backend/.local/fake-google.sqlite3, shared by API and worker on one host and excluded
from Git. Application and consent persistence and integration tests use PostgreSQL.
This adds no production PostgreSQL schema or service.

Create persists its randomly generated event ID before returning it. Busy lookup
and cancel use the same file. Cancel marks a known event cancelled; a second cancel
of that event succeeds. An unknown ID raises a classified adapter error and keeps
the cleanup flag. SQLite busy/locked errors are bounded and retryable. Unit tests
may inject an in-memory store with a retained connection; two-process tests use a
temporary file. The factory provides one shared configured path across processes.

Legacy events recorded only in the previous process memory cannot be recovered
from the new file. Leave those IDs flagged and visible to HR. There is no automatic
reset of existing application/calendar data. Creation has no idempotency key in the
existing interface. Live-provider precommit orphan reconciliation is a later phase.

## Expiry and notification worker

Run expire_response_links every 60 seconds and on startup. Select only the two
implemented purposes, unused links with no invalidation, and expires_at <= now.
Process one transaction per link. Claim parent application rows with SKIP LOCKED,
recheck after locking and continue other work after one transaction failure.
Stale domain states invalidate the unused link with an audit explaining the stale
reference; they cannot change an already confirmed or replaced interview.

Consumed and invalidated links are outside the expiry query. Rescheduling requests
already consumed their link, so that deadline cannot subsequently decline them.
For each actual expiry, atomically notify active HR recipients and the candidate,
using application/purpose identifiers for deduplication through the consumed link.
Consent expiry does not create, revoke or extend a consent record.

Seed idempotently four templates with candidate-safe variables only.
INTERVIEW_RESPONSE_HR uses application_id, job_title, response, response_time,
note and handle_due_at. RESPONSE_EXPIRED_CANDIDATE uses full_name, job_title,
response_subject and response_deadline. RESPONSE_EXPIRED_HR uses application_id,
job_title, response_subject and response_deadline. CALENDAR_SYNC_REQUIRED_HR uses
application_id, interview_id and action. Successful confirmation and decline also
notify HR through INTERVIEW_RESPONSE_HR. The worker retries remote cancellation
without creating repeat notification emails.

## Persistence

Add Alembic 0008 for consent_source and talent_pool_consents, reproducing reference
columns, FKs, checks and talent_pool_one_active. Seed talent_pool_months,
max_reschedule_requests and reschedule_handle_days only when absent. Reuse existing
needs_manual_calendar_fix, reschedule_note, decline_reason and response-link columns.
The C proposal requires no replacement of shared 0001–0007 migration history.

## Acceptance and handoff

Verify anonymous GET/resolve has no mutations and unsupported actions cannot consume
a link. Exercise all transitions, note boundaries, stale policy and link states,
deadline equality, concurrent double-submit, accept-versus-expire, issue-versus-
respond and consent from two applications. Assert exactly one decision, one audit
set and the expected outbox rows. Verify rollback, cancellation retry, worker
restart recovery and safe public output. Verify 12 calendar months, leap day,
already-valid consent and expired/revoked consent cases.

Use real migrated PostgreSQL, fake Google and Mailpit or fake email. Run backend
targeted tests and full suite, Ruff lint/format, frontend behavioral tests,
typecheck/build and browser tests for the email URL through final confirmation.
Perform one static Claude review after local checks, and report remaining findings
for user approval as requested. The reference context and schema documents remain
the inputs for this implementation.

## Design discussion record

Further Claude discussion at the user's request examined multi-process fake state,
uncertain submissions and valid-grant wording. The final summarized proposal was
confirmed internally coherent with no remaining concrete internal blocker.
The discussion reviewed summaries rather than executing or inspecting code.
Explicit approval items are the shared development fake, the minimal used-token
receipt, consent-state conflicts and the valid-grant acknowledgement mode.
Retry tracking uses existing columns. Business month arithmetic uses
Asia/Ho_Chi_Minh consistently with the existing calendar design.
The withdrawal channel and upstream URL logging require decisions before a
candidate-facing external release. Phase C defines the demo workflow, and supplies
neither an invented HR contact nor a legal-compliance assurance.
