# HR_Chan Engineering Documentation Design

## Goal

Create engineering documentation shared by developers and coding agents.
`docs/` defines the workflow, conventions, and architecture; `AGENTS.md`
directs agents to those documents and explains how to apply them.
Keep spec/plan paths compatible with Superpowers. Do not add metadata,
YAML front matter, or status tables to specs or plans.

## Current State

- The repository had no `docs/` documentation system before this task.
- `AGENTS.md` combines workflow, conventions, development commands, and agent
  action boundaries, with several sections overlapping the README.
- The backend is a FastAPI modular monolith with scaffolded business modules.
  Files and routers alone do not establish implemented business behavior.
- The frontend has typecheck/build commands but no behavioral test scripts
  or dependencies.
- Existing instructions require spec and plan approval and exempt documentation-only
  changes from running the full application test suite.

## Scope

### In Scope

- Write the documentation in English, following the user's latest instruction.
  This supersedes the earlier Vietnamese documentation preference for this work.
- Move existing rules into their authoritative documents without losing constraints.
- Define workflow outputs, transition criteria, verification, and handoff.
- Create concise spec/plan templates without metadata or sample business logic.
- Reduce `AGENTS.md` to agent guidance and required reading links.
- Move detailed README content into docs while retaining an introduction,
  technology overview, quick start, and documentation links.

### Out of Scope

- Application code, APIs, Pydantic schemas, HTTP statuses, or database model changes.
- New migrations, business logic, sample data, or AI integrations.
- Installing test tools, CI/CD, formatters, or other dependencies.
- Automatic commits, pushes, deployments, or database changes.
- Introducing branch, commit, or release policies that have not been agreed upon.

No new API contract, storage model, or router → service → repository flow
is introduced. Documentation describes existing behavior and constraints.

## Structure and Responsibilities

```text
docs/
├── README.md
├── engineering/
│   ├── workflow.md
│   ├── conventions/
│   │   ├── general.md
│   │   ├── backend.md
│   │   ├── frontend.md
│   │   ├── database.md
│   │   └── testing.md
│   └── templates/
│       ├── spec.md
│       └── plan.md
├── architecture/
│   └── overview.md
├── guides/
│   └── local-development.md
└── superpowers/
    ├── specs/YYYY-MM-DD-<topic>-design.md
    └── plans/YYYY-MM-DD-<topic>.md
```

Create `architecture/decisions/` only when an actual architecture decision
record (ADR) is needed. Do not invent historical decision rationale or create
empty directories merely to match a diagram.

| Document | Responsibility |
| --- | --- |
| `docs/README.md` | Index, reading paths for developers/agents, conventions versus task records |
| `engineering/workflow.md` | Six steps, approval gates, scope changes, and handoff criteria |
| `conventions/general.md` | Scope discipline, naming consistent with existing code, dependencies/lockfiles, configuration, and secrets |
| `conventions/backend.md` | Layer boundaries, dependency injection, async sessions, transactions, errors/logging, and integration Protocols |
| `conventions/frontend.md` | Feature/shared structure, providers/routing, aliases, HTTP client, and server state |
| `conventions/database.md` | Requirements-driven schemas, migrations, target database checks, and data preservation |
| `conventions/testing.md` | Red/Green, verification by change scope, test environments, and evidence reporting |
| `architecture/overview.md` | Actual architecture, implemented behavior versus scaffolding, and relevant code references |
| `guides/local-development.md` | Setup, local execution, database ports, environment variables, Docker, testing, and migrations |
| `superpowers/specs/` | Requirements and design for individual tasks |
| `superpowers/plans/` | Implementation tasks and verification for individual tasks |

Each detailed rule has one authoritative document. Other documents link to it
instead of duplicating its full content. Verification commands belong in testing
conventions; setup instructions belong in the local development guide.
README quick-start commands must remain consistent with the detailed guide.

## Workflow

| Step | Output | Transition Criteria |
| --- | --- | --- |
| Brainstorm | Context, requirements, alternatives, and trade-offs | Resolve questions affecting business behavior, APIs, and data |
| Spec | Scope, behavior, design, and acceptance criteria | User approves the spec |
| Plan | Atomic tasks, affected files, completion criteria, and verification commands | User approves the plan |
| Test — Red | Expected-behavior tests and observed failures | Failures reflect missing behavior, not environment errors |
| Code — Green | Minimal implementation within approved scope | Targeted tests pass |
| Refactor & Verify | Appropriate checks, updated documentation, and handoff | Report actual evidence, limitations, and skipped checks |

- Approval happens in conversation; do not add status, approver, or timestamp fields.
- If scope/contracts change, update the affected sections and obtain approval
  before continuing dependent implementation.
- For documentation-only changes, retain clarification, spec, and plan steps.
  Replace Red/Green with before-and-after documentation checks. Do not manufacture
  failing tests or require application tests when code and execution configuration
  remain unchanged.
- For application code, test behavior before implementation. Typecheck/build
  establish type correctness and buildability, not frontend behavior. Required
  test tooling must be addressed in the relevant task's spec and plan.
- Backend verification includes Ruff, format checking, and pytest. Frontend
  verification includes typecheck/build and behavioral tests when available.
  Changes spanning both sides require checks on both. Database tests use a
  dedicated test database; explicitly report skips due to missing configuration.
- Historical README test results are not evidence for a new change.

## Templates and Superpowers Integration

The spec template includes goals/context, scope, requirements/behavior, design,
contracts and storage where applicable, error handling, acceptance criteria,
and verification. Mark irrelevant sections as not applicable with a brief reason;
do not fill them with invented business requirements.

The plan template includes a spec link, goals, ordered tasks, affected files,
per-task verification, and handoff checks. Behavioral implementation tasks follow
Red → Green → Refactor; documentation tasks use content/link checks. Templates
provide a minimum structure and allow skills to add relevant detail.

Use a shared topic name to associate specs and plans. Plans link to their specs
and relevant conventions. Do not add front matter, status tables, or replacement
metadata. Project rules and direct user instructions take precedence over skill
defaults, including no automatic commits and required spec/plan approval.

## AGENTS.md and Root README

`AGENTS.md` directs agents to read the README, documentation index, workflow,
and scope-specific conventions. Retain skill activation guidance, preservation
of existing changes, restrictions on inventing business requirements, and
boundaries for commits, pushes, deployments, and data operations. Link detailed
rules to their authoritative documents. Preserve tool-managed Postman content.

The README retains the introduction, technology overview, quick start, and
documentation entry point. Migration instructions must retain the requirement
to verify the target database and inspect migrations before applying them.
Replace historical verification results with a link to verification instructions
so they cannot be mistaken for current evidence.

## Acceptance Criteria

1. Developers can find workflow, conventions, and local development instructions
   from the README without reading `AGENTS.md`.
2. Agents have explicit links to required documents for their task scope.
3. Existing rules for layer boundaries, frontend structure, migrations, secrets,
   business scaffolding, and action authorization remain intact.
4. The workflow defines spec/plan approval, valid Red evidence, the documentation-only
   exception, and the limits of typecheck/build.
5. Specs/plans use Superpowers paths without metadata. Templates contain no sample
   business logic or unapproved technology choices.
6. Internal links and actual code references resolve. Template filename examples
   are distinguishable from links to existing files.
7. Architecture reflects the current system, without presenting scaffolding as
   completed functionality.
8. Application code, dependencies, databases, and unrelated work remain unchanged.
9. Documents created or rewritten in this task are in English, except tool-managed
   content that must be preserved.

## Verification

- Compare original and revised AGENTS.md/README content to detect missing rules.
- Check relative links and actual file references throughout the documentation.
- Cross-read workflow, testing conventions, and templates for contradictions.
- Inspect diffs, whitespace, and changed files. Application tests are unnecessary
  for this documentation-only change.
- Report the main documents, checks performed, and work not yet implemented.
