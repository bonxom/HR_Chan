# Implementation Notes for Business Workflows

Use the [business index](README.md) and relevant group page to establish intent.
Use the code links below to verify the baseline for a new feature spec. The
[engineering workflow](../engineering/workflow.md) governs decisions that affect
behavior, contracts, and data.

## Repository Baseline

| Area | Code-backed behavior and gaps |
| --- | --- |
| Authentication | [Auth router](../../backend/src/app/modules/auth/router.py), [account lifecycle service](../../backend/src/app/modules/accounts/service.py), and [auth service](../../backend/src/app/modules/auth/service.py) implement internal login, sessions, password change, and email-link setup and recovery. [Authentication guide](../guides/authentication.md) |
| Account administration | [Accounts router](../../backend/src/app/modules/accounts/router.py) and [Admin UI API](../../frontend/src/features/admin/api.ts) support listing, employee/Admin creation, role replacement, lock, unlock, disable, and resend. The current account schema has no department or work ownership. Role validation allows standalone `PROBATION`, with the offer and conclusion restrictions still pending. |
| Authorization | [Identity dependencies](../../backend/src/app/core/security.py) resolve the principal from a live session. [Resource policy](../../backend/src/app/modules/auth/policies.py) denies business access for Admin and denies when a policy is absent. Department and assignment checks need business data and per-resource policies. |
| Activity log | [Audit API](../../backend/src/app/modules/audit/router.py) lists append-only events for Admin. [Audit metadata schema](../../backend/src/app/modules/audit/schemas.py) limits exposed metadata. The source's detailed change reports, business access events, and Excel/PDF export require additional work. |
| Recruitment and candidate flows | [API composition](../../backend/src/app/api/v1/router.py) registers the candidate, application, and recommendation scaffolds. Job module files are empty and the router is absent from the API. [Recommendation service](../../backend/src/app/modules/recommendations/service.py) holds integration interfaces without a scoring or recommendation pipeline. |
| Frontend demonstrations | [Routes](../../frontend/src/routes/routes.tsx) and the [mock store](../../frontend/src/shared/services/mockStore.ts) illustrate journeys for jobs, applicants, interviews, and reports. Admin's settings and work reassignment have no registered routes. Frontend demonstration states, scores, roles, IDs, and simulated OTP behavior carry no authority for backend contracts. |
| External services and storage | SMTP currently serves account messages. CV file storage, candidate OTP, business email delivery workers, Google Workspace provisioning and scheduling, and recruitment persistence need feature work. [Architecture overview](../architecture/overview.md#ai-and-storage-boundaries) |

## Open Decisions

### Criteria versioning

UC2.08 step 1 says to load the current criteria. BR05, report §3.1.2, and S2
tie the intended result to the version applicable when the application was
submitted. A queued job can run after HR saves a new version. Specify how the
application retains its effective version and threshold, and clarify whether
booking uses the current interviewer assignment after an update or reassignment.
Report S1 updates job interviewer assignments separately from the criteria
version. Keep already-scored results reproducible.

### AI scoring and evidence

UC1.08, UC2.08, NFR09, and NFR16 show CV excerpts and verification. Report
§6.3 and the later score design in Figure 4.7 describe dropping evidence
excerpts, while retaining per-criterion score and explanation. Confirm what
must be returned, verified, persisted, and displayed. Define what counts as
meeting an individual mandatory criterion, score precision, and handling of
incomplete AI results. The source establishes the weighted calculation and
eligibility gate, and HR owns rejection under either evidence choice.

UC2.02 supports OCR and partial extraction. Report §5.2.2 describes files with
a text layer. Confirm scan-only support and what partial extraction can feed
to recommendations and scoring. UC2.02 allows a 30-second timeout and a retry,
while NFR19 targets 15 seconds end-to-end for suggestions. Group 1 NFR04 gives
a 10-second cap for external calls. Set budgets by operation, including the
candidate fallback when the budget is spent. UC2.08 and report S2 also need
a shared definition of total attempts versus retries.

### Invitation delivery

UC1.07 branch 5d leaves an incomplete operation in *Chờ HR duyệt*. UC1.09 and
UC2.09 retain an existing booking and flag failed email after retries.
Report S3 advances the application after queueing the email, while the detailed
happy paths describe acceptance by the email service before advancing. BR06
also says that failed automatic invitations fall back to HR. Specify application
and booking state after queueing, permanent email failure, and manual resend.
Keep HR decisions and applications through provider errors (NFR03, NFR21).
BR23 measures from the day the email is sent, so define the deadline and
slot-validity behavior if delivery is delayed or never succeeds.

UC2.05 promises an emailed result within five working days of applying.
BR25 and UC2.08 start the five-working-day HR review clock when the record
enters the queue and specify reminders for missed deadlines. Confirm the
candidate message and the end-to-end service target separately from the
review deadline.

### Interview response boundary

UC1.09 and UC2.09 mention proposing an alternate slot. Group 3 BR48–BR51
and Appendix A preserve the older one-or-two-slot flow. Report §§3.1.3,
4.2.4, and 6.3 describe the later request-with-note design, with HR choosing
the new slot and the prior link invalidated on successful rescheduling.
Confirm wording and handoff payload when the invitation feature connects to
Group 3. The current phase needs the invitation and its reply deadline
and expiry behavior. Group 3 owns the detailed change and result flows.

### Job and report contracts

UC1.02 allows title-only draft creation. UC1.03 references full validation on
update as well as on publication. Confirm whether ordinary draft updates can
remain incomplete, and define the time zone and cutoff for a date-only job
deadline. The report's conceptual required fields and multiplicities need to
accommodate incomplete drafts.

UC1.12–UC1.14 name metrics and filters. A reporting spec needs the time basis,
cohorts, denominators, and behavior when Group 3/4 events are unavailable.
UC1.12 starts with temporary CV uploads, which may lack a job or be purged
under BR26. Define aggregation for that stage before filtering by position
or department. The Group 1 source §4.1 supplies the NFR01–NFR02 numeric
targets. Report §6.2 marks those entries as missing. Confirm the performance
workload and use the group source values as traceable input.

### OTP and passwords

BR16 says at most five wrong attempts, while UC2.06 branch 6b says more than
five. Confirm the lockout boundary and which operation and identity each
quota applies to. For candidate submission, specify how successful proof is
scoped to the chosen email and application attempt. For internal recovery,
preserve the generic outward response even where the source discusses invalid
addresses or locked-account email (BR42, UC5.18).

The implemented accounts use `PENDING_SETUP` and `PASSWORD_RESET_REQUIRED`,
with single-use emailed links for setup and recovery. The current defaults are
24 hours for an invitation link and 30 minutes for a recovery link. The
Group 5 source uses an OTP and distinguishes a 72-hour Admin initial setup
window from an Admin-authorized reset window of 30 minutes. Current public
recovery has no UC5.07 Admin window check. Confirm whether the current link
flow or the source OTP/eligibility model is intended for internal users.
Candidate application OTP is a separate purpose and a new business path.

Current password validation is length-based, and password change keeps and
rotates the performing session. UC5.17 adds a different-password and
letters-and-digits requirement, a current-password failure limiter, and an
email notice. NFR28 says all sessions are revoked, whereas UC5.17 describes
revoking other sessions. Confirm the password and session scope before
changing the current implementation.

### Account protection and reassignment

BR31 leaves at least two active Admins after lock or deletion. The current
account service protects the last active Admin and blocks self-lock and
self-disable. BR32 protects the last active HR and UC5.05 branch 2b permits
an emergency exception. Confirm both floors and how HR access is recovered
if emergency locking of the last HR is allowed.

UC5.06 anonymizes a locked account and keeps its identifier. Current
`DISABLED` is terminal, can be reached without a prior lock, and retains
the identity fields. Confirm anonymization and email reuse together,
because UC2.12 also calls for avoiding addresses previously used by deleted
accounts. Confirm how to preserve history without re-exposing removed values.

UC5.05, UC5.08, and UC5.09 rely on work ownership and eligible replacements.
Confirm the work types available in this phase, department membership,
and how multiple work changes and the originating lock or role change
succeed together. Check the approved administrative data view for audit
and reassignment. The existing audit allowlist and account schema have
limited metadata and no department.

### Probation handoffs

UC2.11 shows the application going to *Đang thử việc* on acceptance and
then to *Chờ cấp tài khoản* after provisioning failure. Report §§3.1.4 and
5.3 connect the probation period to account provisioning. Confirm durable
states for offer acceptance, mailbox creation, internal account creation,
and notification delivery, and the exact event that creates or starts the
period. Decide how manual recovery reuses a partially provisioned mailbox
and how first-login mailbox credentials are delivered. UC2.12 describes a
temporary mailbox password sent to the personal email.

UC1.14, UC5.08–UC5.09, and BR44 need aggregate probation outcomes, assigned
managers, and pass/fail conclusion events from Group 4. Keep these as
dependencies until the producer feature is specified. BR30 says the role
can be removed only after a conclusion. UC5.08 describes manual
replacement on a pass, and BR44 describes locking after a fail.

### Retention

Distinguish the temporary upload, application-linked CV, and CV retained
for future recruitment. BR26 exempts submitted CVs from temporary cleanup.
BR21 and NFR23 require consent and expiration or withdrawal for future
recruitment. Report §5.2.1 describes anonymization of candidate details.
Confirm the treatment of the binary file, extracted content, recommendations,
application history, and aggregate counts for each retention trigger.
Confirm the withdrawal and in-flow consent paths. UC1.10 mentions consent
at submission, and the detailed opt-ins are in UC2.03 and UC2.13.

### Physical data and configuration

Report Chapters 4–5 describe conceptual entities and proposed tables and
operations. Use them to trace relationships, then confirm API and persistence
design against the existing account and audit modules before creating
migrations. Confirm time zones, working-day arithmetic, and all bounds
omitted in UC5.13–UC5.16. BR47 treats several values as configurable
defaults, while the individual configuration use cases name a narrower set
of editable fields. Derive the configuration surface from an agreed list.

## Shared Safeguards

| Source | Safeguard |
| --- | --- |
| NFR13–NFR14 | Validate input type, shape, and length on the server. Use ORM or parameterized queries. |
| NFR15, NFR18, BR46 | Escape inserted text for its display context and strip line breaks from email headers. Check required variables on template saves. |
| NFR16 | Treat CV content as untrusted data and validate the shape of AI outputs. Confirm the evidence contract above. |
| NFR07, NFR17, NFR23 | Verify file content type, scan uploads, use randomized private storage, encrypt at rest, use HTTPS, and apply consent and retention rules. |
| BR27–BR29, NFR05–NFR06, NFR26, NFR30 | Enforce permission checks on the server. Audit application access, review decisions, and administrative operations. Keep Admin audit and handover views within their data boundaries. |

## Source-Derived Acceptance Scenarios

Use these expected outcomes as inputs to feature-level tests after the relevant
contract is confirmed. Test fixtures and performance results belong to their
feature work.

| Scenario | Expected result | Source |
| --- | --- | --- |
| HR publishes a job without a valid criteria set | Publication fails and the job stays unavailable to candidates. An incomplete new draft can be saved with its title. | UC1.02, UC1.05, BR01–BR04 |
| HR closes an Open job with pending applications | Candidate listing and recommendations exclude it and application creation is denied. Existing review and interview records remain actionable. | UC1.04, UC2.04–UC2.05, BR01, BR03 |
| Candidate uploads a valid CV, then abandons before OTP | A temporary submission can exist. No application or scoring task is created. The temporary expiry applies unless there is retention consent. | UC2.01, UC2.05, BR19, BR26 |
| Two requests try to submit the same email to the same job | At most one application is created after successful OTP. | UC2.05, BR17, BR19 |
| HR saves a new criteria version before previously queued scoring runs | The earlier application remains associated with the version applicable to its submission. A later application uses the new version. | BR05, report §3.1.2 |
| High score misses a mandatory criterion, or the scoring provider stays unavailable | The application goes to HR review and records the applicable reason. Only HR can reject it. | BR06, BR08, UC2.08 |
| Automatic scheduling finds no slot that meets the working-day gap | The application goes to HR review with the manual invitation note and no active interview is created. | UC2.09, BR06, BR09 |
| HR rejects the application and the email provider is down | Preserve the decision and internal reason. Record and surface the notification failure according to retries. | UC1.10, BR08, BR11, NFR03 |
| An interview invitation sent on Friday receives no response before Tuesday closing, with Monday and Tuesday working days | The default deadline falls at Tuesday closing. When it expires, record interview decline, invalidate the reply link, and cancel the event. | BR20, BR23–BR24, NFR33 |
| Two replies target one valid offer link | One confirmed response consumes the link. A later request sees the recorded response, and acceptance causes one provisioning flow. | UC2.10–UC2.12, BR20 |
| Company mailbox exists and internal account creation repeatedly fails | Keep the mailbox, set the application to *Chờ cấp tài khoản*, and alert Admin for UC5.02 recovery. | UC2.11–UC2.12, BR30 |
| Admin attempts to read an application CV | Server denies business resource access. | BR29, NFR05, NFR26 |
| Normal lock has unfinished work but no eligible successor | Block the lock and explain the missing replacement. An authorized emergency lock instead leaves work pending handover where allowed. | UC5.05, UC5.09, BR32–BR35 |
| Admin updates OTP lifetime while a code is outstanding | Keep the expiry that was set on the issued code. Apply the selected lifetime to later codes. | UC5.15, BR45 |
