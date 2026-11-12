# Coding Agent Instructions

These instructions apply throughout the repository. Direct user instructions take
precedence over project rules and skill defaults.

## Required Reading

Read the [README](README.md), [workflow](docs/engineering/workflow.md),
[general conventions](docs/engineering/conventions/general.md), and existing code
before editing. Use the [documentation index](docs/README.md) to select conventions
for the affected area, including testing. When resuming work, read its spec and plan.

## Skill Usage

- `brainstorming`: clarify requirements and design.
- `writing-plans`: produce an implementation plan.
- `test-driven-development`: test application behavior before implementation.
- `verification-before-completion`: verify before claiming completion.

Follow the workflow's approval gates and documentation-only exception. Skill defaults
must not override project rules, including authorization for commits and deployments.

## Action Boundaries

Preserve unrelated user changes. Do not invent business requirements or fill intentional
placeholders. Do not commit, push, deploy, or perform destructive data operations without
authorization. Apply the detailed [general](docs/engineering/conventions/general.md)
and [database](docs/engineering/conventions/database.md) safeguards.

<!-- postman-cli:installation:start -->
Postman CLI đã được cài trên thiết bị và có thể dùng cho công việc phát triển, kiểm tra API.
<!-- postman-cli:installation:end -->
