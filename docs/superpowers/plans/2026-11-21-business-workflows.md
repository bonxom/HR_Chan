# Business Workflow Documentation Plan

## Goal and References

Build the reference described in the
[approved design](../specs/2026-11-21-business-workflows-design.md).
Follow the [workflow](../../engineering/workflow.md),
[general conventions](../../engineering/conventions/general.md), and
[documentation checks](../../engineering/conventions/testing.md#documentation-checks-and-evidence).

## Constraints and Dependencies

- Use the three detailed specifications and the final report listed in the design.
  Keep original UC, BR, and NFR IDs. Quote short Vietnamese names and status labels
  where they support traceability. Write the explanations in English.
- Cover groups 1, 2, and 5. Show the specific outcomes or inputs that connect to
  groups 3 and 4, including missing data dependencies, without specifying their
  detailed workflows.
- Keep research evidence, observed repository behavior, and unresolved choices
  identifiable at the point of use. Keep routes, migrations, implementation code,
  tests, infrastructure, and attachments outside the change.

## Task 1 Business Entry Point and Shared Lifecycle

Create `docs/business/README.md` and add its link to `docs/README.md`.

- [x] List the four source filenames and their relevant sections, all three group
  pages, and the route from source requirements to a future feature spec.
- [x] Explain actor boundaries, relationships between submissions, applications,
  criteria versions, and interviews, and the handoffs between groups.
- [x] Add a lifecycle diagram with a transition table covering the 14 application
  states in report §5.4. Mark the interview and probation boundary events. Show
  the different outcomes of HR rejection and an expired candidate reply.
- [x] Check that the shared lifecycle agrees with each group page after Tasks 2–4.

## Task 2 Recruitment Management

Create `docs/business/recruitment-management.md` from Group 1 §§2–4 and report
§§3.1, 4.2.1, 4.2.3 and 5.4.

- [x] Cover UC1.01–UC1.05 with list filters, draft and publication rules, update
  conflicts, close-out effects, scoring criteria validation, and prospective
  versioning. Preserve the Vietnamese job state names alongside report identifiers.
- [x] Cover UC1.06–UC1.10 with the application list, audit on access, oldest-first
  review queue, score detail, manual scheduling, rejection, and their failure
  branches. Link shared scheduling and email semantics from the candidate page.
- [x] Cover UC1.11–UC1.15 with filters, calculation inputs, small cohorts,
  probation data dependency, and the aggregate-only export contract.
- [x] Verify 15 use case headings and traceability to BR01–BR13 and Group 1 NFRs.

## Task 3 Candidate Application and Recommendations

Create `docs/business/candidate-application.md` from Group 2 §§2–4 and report
§§3.1, 4.2.2–4.2.3 and 5.2–5.4.

- [x] Cover UC2.01–UC2.04 with validation before AI, partial and failed extraction,
  recommendation filtering, jobs closed during browsing, and a manual browse
  path. Explain separate temporary submission and application lifecycles.
- [x] Cover UC2.05–UC2.09 with duplicate detection, purpose-bound OTP and resend,
  submission then background scoring, criteria version selection, HR fallback,
  shared scheduling rules, retry handling, and commitments after delivery fails.
- [x] Cover UC2.10–UC2.13 with link validity, consumption and expiration, separate
  effects of each kind of expired invitation, provisioning outcomes and fallback
  to UC5.02, and consent to retain a CV for later recruitment.
- [x] Verify 13 use case headings and traceability to BR14–BR26 and Group 2 NFRs.

## Task 4 System Administration

Create `docs/business/system-administration.md` from Group 5 §§2–4 and report
§§5.2.10 and 6.1.5.

- [x] Cover UC5.01–UC5.09 with employee and Admin accounts, role restrictions,
  normal and emergency locks, reassignments, status and identity changes, reset
  windows, audit records, and the provisioning handoff.
- [x] Cover UC5.10–UC5.16 with audit search and export, working calendar, email
  templates, time limits, and AI threshold configuration. Record documented
  defaults and bounds and when a new value takes effect.
- [x] Cover UC5.17–UC5.18 with separate change and recovery paths, session effects,
  recovery eligibility and OTP reuse. Link differences from current behavior.
- [x] Verify 18 use case headings and traceability to BR27–BR47 and Group 5 NFRs.

## Task 5 Implementation Notes and Verification

Create `docs/business/implementation-notes.md`. Read the current
`backend/src/app/api/v1/router.py`, account and auth services, resource policy,
audit schemas, and frontend routing and data sources where claims depend on them.

- [x] Point readers to the live account/auth/audit code, demonstration screens,
  and business scaffolds. Compare with source expectations for passwords, Admin
  safeguards, disabled versus anonymized accounts, role and work handover, and
  audit and settings.
- [x] List the unresolved choices in the design with their source references and
  the use case that needs the decision. Include a compact table of source-derived
  feature acceptance scenarios with expected outcomes.
- [x] From the repo root, run `git diff --check` and `git status --short`. Use
  `python3` with `pathlib` and `re` to check links, anchors, and trailing whitespace
  in all added and changed Markdown, including untracked files. Compare the sets
  of `### UC1.xx`, `### UC2.xx`, and `### UC5.xx` headings with the IDs extracted
  from the three source documents. Review each new file and the index diff for
  scope, behavior, and source fidelity.
- [x] Report the index, the three group references, decisions still pending for
  feature work, and the checks actually run. The documentation-only verification
  matrix applies.
