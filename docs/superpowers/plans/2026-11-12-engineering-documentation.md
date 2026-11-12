# Engineering Documentation Implementation Plan

Implement the [design spec](../specs/2026-11-12-engineering-documentation-design.md)
inline using the executing-plans skill. The user explicitly requested proceeding
without further intermediate approval pauses for this documentation task.

## Goal and Constraints

Create English engineering documentation, with authoritative conventions separate
from Superpowers task records. Keep specs and plans free of metadata. Preserve
existing rules and tool-managed Postman content. Do not modify application code,
dependencies, database state, or unrelated work. Do not commit or push.

This is a documentation-only task: inspect the existing documentation before
editing, then verify content and links. No artificial failing application test.

## Task 1: Establish Workflow and Conventions

Create `docs/engineering/workflow.md` and these files under
`docs/engineering/conventions/`: `general.md`, `backend.md`, `frontend.md`,
`database.md`, and `testing.md`.

- [x] Compare existing AGENTS.md rules and README instructions against the spec.
- [x] Write the six-step workflow with approval gates, scope-change handling,
  documentation-only checks, and handoff criteria.
- [x] Move existing technical constraints into the five convention documents.
- [x] Verify preservation of layer boundaries, frontend folders, safe migrations,
  secrets, intentionally empty modules, and scope-specific verification.

## Task 2: Add Architecture, Development Guide, and Templates

Create `docs/architecture/overview.md`, `docs/guides/local-development.md`,
`docs/engineering/templates/spec.md`, and `docs/engineering/templates/plan.md`.

- [x] Describe current implemented behavior separately from scaffolded modules.
- [x] Move setup, port handling, environment, Docker, and migration instructions
  from the README, preserving target-database checks and dedicated test setup.
- [x] Add spec/plan templates with concrete authoring instructions, links to
  conventions, optional contract/storage sections, and no metadata fields.
- [x] Compare documented commands with package.json, pyproject.toml, Compose,
  application entry points, and the existing tests.

## Task 3: Connect Documentation Entry Points

Create `docs/README.md`; revise root `README.md` and `AGENTS.md`.

- [x] Provide reading paths and links to all new guidance and templates.
- [x] Keep root README focused on introduction, stack, quick start, and docs links.
- [x] Keep agent-specific reading, skill usage, and action boundaries in AGENTS.md.
- [x] Preserve the Postman managed block verbatim and remove stale test-result claims.

## Task 4: Verify and Hand Off

- [x] Check relative Markdown links with a local Python path-resolution script,
  excluding external URLs and fenced filename examples.
- [x] Check all changed/new Markdown files for trailing whitespace and balanced fences.
- [x] Run `git diff --check`, inspect `git diff --stat` and `git status --short`.
- [x] Cross-review workflow, templates, and conventions for contradictions and
  compare original rules against their new locations.
- [x] Report actual checks, documentation entry points, and that application
  tests were not run because only documentation changed.

## Verification Outcome

All four tasks are complete. Checked all 15 Markdown files and 71 relative links,
including untracked documents; links, code fences, whitespace, and absence of
spec/plan front matter passed. The managed Postman block matches the original.
`git diff --check` passed. A separate read-only review found no lost original
constraints or broken links; its Red-test wording finding was corrected to allow
an acceptance test to fail on its intentionally missing application interface.

Only README.md, AGENTS.md, and docs/ changed. Application tests were not run for
this documentation-only task. No application code, dependencies, database state,
commits, pushes, or deployments were changed. No implementation tasks remain.
