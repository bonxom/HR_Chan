# Engineering Workflow

Read existing code and the relevant [conventions](../README.md) before designing
changes. Direct user instructions take precedence over project and skill defaults.

```text
Brainstorm → Spec → Plan → Test (Red) → Code (Green) → Refactor & Verify
```

| Step | Required Output | Completion Gate |
| --- | --- | --- |
| Brainstorm | Problem, actors, constraints, expected behavior, and viable alternatives with trade-offs | Resolve unknowns affecting business rules, contracts, and data |
| Spec | Design using the [spec template](templates/spec.md) | User approves the spec before planning |
| Plan | Atomic tasks, exact files, dependencies, and verification using the [plan template](templates/plan.md) | User agrees before implementation |
| Test — Red | Tests tied to acceptance criteria | Observe failure for the intended missing behavior |
| Code — Green | Minimum implementation within approved scope | Targeted tests pass |
| Refactor & Verify | Refactor, review the diff, update affected documentation, and run applicable checks | Meet the [verification and handoff requirements](conventions/testing.md) |

Identify test-tooling gaps during planning. Use the testing conventions for valid
Red evidence and checks by change scope.

## Approvals and Scope Changes

Approvals happen in conversation; silence is not approval. If the user explicitly
changes the approval sequence for a task, follow that instruction within its scope.
When scope, contracts, or data models change during implementation, update the
spec/plan and obtain approval before continuing dependent work.

## Documentation-Only Changes

Keep clarification, spec, and plan steps. Replace the Red/Green code cycle with
inspection, editing, and the documentation checks in the testing conventions.
Application tests are unnecessary when code and execution configuration are unchanged.

## Work Records

Save specs to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and plans to
`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`. Use the same topic and link the plan
to its spec. Do not add metadata/front matter or status tables.

Keep conventions and architecture current; preserve specs/plans as task records.
For a significant architecture decision needing durable rationale, create an ADR
under `docs/architecture/decisions/` covering context, alternatives, the decision,
and consequences. Do not invent historical rationale or create an empty ADR directory.
