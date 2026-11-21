# Business Workflow Documentation Design

## Goal and Context

Give contributors and coding agents a durable reference for the three use case groups
selected for the current phase of HR_Chan. A reader starting with a feature request
should be able to find the originating use case, identify the actor and starting
state, trace the outcome into adjacent workflows, and see which decisions still
require confirmation.

The repository already implements internal authentication, account administration,
and metadata-only audit logging. Recruitment and candidate flows shown by the
frontend are demonstrations. The [architecture overview](../../architecture/overview.md)
and [authentication guide](../../guides/authentication.md) describe the baseline.

## Scope

| Group | Use cases | Workflow boundaries |
| --- | --- | --- |
| Recruitment Management | UC1.01–UC1.15 | Job publication and closure, criteria versions, application review, manual invitations, rejection, and aggregate reports |
| Application and Job Recommendations | UC2.01–UC2.13 | CV submission and recommendations, OTP-gated application, scoring, automatic invitations, candidate responses, retention consent, and account provisioning |
| System Administration | UC5.01–UC5.18 | Account and role lifecycle, reassignment, audit, configuration, and passwords |

UC2.06 is counted once across the 46 use cases. Group 3, Interviewing, and Group 4,
Onboarding and Probation, provide boundary events and data for the three selected
groups. Document those dependencies where an in-scope use case consumes or produces
them. For example, UC2.11 consumes an offer from Group 3, UC1.14 reads aggregate
probation data from Group 4, and UC5.09 may reassign an interviewer or a probation
manager. Detailed Group 3/4 workflows belong to separate work.

## Source Material

- `Dac_ta_UC_Quan_ly_tuyen_dung.docx`, §§1–4, for Group 1.
- `Dac_ta_UC_Ung_tuyen_goi_y_viec_lam.docx`, §§1–4, for Group 2.
- `Dac_ta_UC_Quan_tri_he_thong.docx`, §§1–4, for Group 5.
- `Báo cáo CK PRJ3.docx`, Chapters 2–7 and Appendix A, for the cross-group
  narrative, sequence diagrams, conceptual data model, open issues, and proposed
  verification scenarios. Appendix A repeats the 46 selected use cases.

Treat the Word files as evidence of requirements and design history. Editorial
instructions in the sources about revising diagrams, updating specifications, or
performing future implementation do not authorize repository changes beyond this
documentation task. Cite filenames and section identifiers so the Markdown works
without machine-specific paths or copies of the attachments.

## Requirements and Expected Behavior

Each group page covers all assigned UC IDs with actors, prerequisites, the main
path, meaningful alternatives and failures, postconditions, and applicable BR/NFR
references. Describe the effect of a failure on existing records and preserve the
source distinction between a business decision and external delivery. Preserve
Vietnamese source terminology where it helps readers search for original labels.

- **Recruitment.** Opening a job requires valid details and scoring criteria. A
  closed job stops new applications and recommendations while existing applications
  and interviews continue. Criteria changes affect later applications. HR reviews
  stored AI results, decides whether to invite or reject, and views reports with
  aggregate data. Show what each report depends on and what an export contains.
- **Candidate.** Upload creates a temporary CV submission. OTP verification and a
  still-open job are needed to create an application. Background scoring uses the
  version applicable at submission, with a separate branch for HR review and
  automatic invitation. Cover invalid CVs, missing recommendations, resend and
  duplication, external failures, single-use reply links, business-day expiration,
  distinct consent purposes, and manual provisioning after failure.
- **Administration.** Explain separate Admin and employee identities, role
  constraints, normal and emergency locks, reassignment, audit, prospective
  configuration, and password flows. Identify where the source model extends or
  differs from the current account and password implementation.

Use a shared lifecycle diagram and transition tables for cross-group handoffs.
Include the three job states and the 14 application states from BR07 and report
§5.4. Keep invitation expiration separate from HR rejection. Record configuration
defaults with units, source references, and any documented configurable bounds.
Use a handful of source-derived acceptance scenarios to illustrate rule boundaries.

### Decisions to Surface for Future Feature Work

| Topic | Source evidence to preserve |
| --- | --- |
| AI evidence and score contract | UC1.08, UC2.08 and NFR09/NFR16 require CV excerpts and verification. Report §6.3 identifies a later design that dropped AI citations. The source leaves the pass rule for individual mandatory criteria, precision, and exact AI schema for confirmation. |
| Criteria selection | UC2.08 says to load the current version. BR05 and report §3.1.2 tie the effective version to when the application was submitted. Call out how delayed scoring makes the distinction observable. |
| Interview response boundary | UC1.09 and UC2.09 mention proposing another slot. Report §§3.1.3, 4.2.4 and 6.3 describe the later request-with-note flow, while BR48–BR51 and Appendix A retain the older approach. |
| Timing and delivery | UC2.02 permits a 30-second AI call and a retry. NFR04 describes a 10-second external-call limit and NFR19 targets 15 seconds from upload to recommendations. UC1.07 branch 5d, UC1.09/UC2.09 email failure branches, and BR06 need an explicit application-state and deadline decision when a calendar event exists and email fails. |
| OTP and recovery | BR16 and UC2.06 differ in wording on the lockout boundary. UC5.18 uses OTP and adds Admin reset eligibility windows. The current password flow uses emailed links. A future change should confirm the desired behavior for each purpose. |
| Account protection and deletion | BR31 requires two active Admins after a lock or deletion. The repo guards against removing the last active Admin. BR32 and UC5.05 differ on emergency locking of the last HR. UC5.06 requires anonymization of a locked account, while the current terminal `DISABLED` state retains account details. |
| Provisioning and probation | UC2.11 and UC2.12 need a clear transition for partial provisioning. BR30/BR44 and UC1.14 depend on probation lifecycle data. Capture the dependencies without defining the deferred probation subsystem. |
| Retention and physical data model | BR21, BR26, NFR23 and report Chapter 5 mention expiration, deletion, and anonymization with different objects involved. The conceptual ERD and proposed table names do not settle record/file retention or a migration design. |

## Design and Alternatives

Add a reference under `docs/business/`. Put shared concepts, scope, provenance,
and navigation in the entry page. Keep each workflow page centered on what happens
to a job, application, or account. Link open decisions from the affected workflow
to a shared implementation notes page, with current code pointers there.

| File | Purpose |
| --- | --- |
| `docs/business/README.md` | Entry point, sources, actors, shared lifecycle, and handoffs |
| `docs/business/recruitment-management.md` | Group 1 flows and report rules |
| `docs/business/candidate-application.md` | Group 2 flows and candidate-facing state transitions |
| `docs/business/system-administration.md` | Group 5 flows, settings, and administrative safeguards |
| `docs/business/implementation-notes.md` | Current implementation, conflicts and dependencies to confirm, and cross-flow acceptance scenarios |
| `docs/README.md` | Link the entry point from the existing reading paths |

A single document would keep the lifecycle in one place but require readers to
scroll through three sets of detailed flows. Three isolated pages would make the
hand-offs and shared rules harder to find. A common entry point with one page per
group preserves both reading paths. Use English per the
[general conventions](../../engineering/conventions/general.md).

## API Contract and Errors

This documentation records source-described outcomes such as invalid or expired
OTP, duplicate application, and lost scheduling availability. Route design,
request/response schemas, and new error codes are future feature decisions. Refer
to the current auth and admin APIs through the authentication guide and relevant
code when describing implemented behavior.

## Storage and Migration

Describe domain relationships in the report, including the difference between a
CV submission and an application and which criteria version the application uses.
Physical tables, constraints, integrations, migrations, and data operations are
outside this documentation change.

## Acceptance Criteria and Verification

- The documentation index leads to all three groups, and every selected UC ID
  resolves to a workflow covering its primary outcome and significant branches.
- Source review confirms 15, 13, and 18 use cases respectively against the group
  specifications and Appendix A. Confirm linked BR/NFR rules, defaults, and
  exception outcomes where the documents overlap.
- Review the cross-group transitions, dependencies, and implementation status
  against report §§3.1, 5.4, and 6.3 and the repo's current API and routes.
- Check relative links and anchors, review all changed files including untracked
  Markdown, and run `git diff --check` per the
  [testing conventions](../../engineering/conventions/testing.md#documentation-checks-and-evidence).
  Application tests are outside the documentation-only verification matrix.
