# Documentation

This directory is the shared engineering reference for developers and coding agents.
The root [README](../README.md) provides the introduction and quick start;
[AGENTS.md](../AGENTS.md) adds agent-specific instructions.

## Reading Paths

New contributors: read the [prototype quick start](guides/prototype-quickstart.md),
[architecture overview](architecture/overview.md),
[local development guide](guides/local-development.md), and
[workflow](engineering/workflow.md), then the conventions for your change.
Authentication work starts with the [authentication guide](guides/authentication.md).

## Engineering Reference

| Document | Purpose |
| --- | --- |
| [Workflow](engineering/workflow.md) | Six steps, approval gates, scope changes, and handoff |
| [General conventions](engineering/conventions/general.md) | Scope, naming, dependencies, configuration, secrets, and documentation |
| [Backend conventions](engineering/conventions/backend.md) | Module/layer responsibilities, lifecycle, errors, and integrations |
| [Frontend conventions](engineering/conventions/frontend.md) | Feature/shared structure, routing, configuration, and data access |
| [Database conventions](engineering/conventions/database.md) | Schemas, transactions, migrations, and data preservation |
| [Testing conventions](engineering/conventions/testing.md) | Red/Green, verification commands, test environments, and evidence |
| [Architecture](architecture/overview.md) | Current system and unimplemented scaffolding |
| [Prototype quick start](guides/prototype-quickstart.md) | Run the app and exercise the implemented flows |
| [Authentication](guides/authentication.md) | Identities, sessions, CSRF, email, audit, and operations |
| [Authentication decision](architecture/decisions/2026-11-15-stateful-jwt-authentication.md) | Why stateful JWT sessions were chosen |
| [Local development](guides/local-development.md) | Setup, ports, environment, migrations, and Docker |

## Work Records and Templates

Use the [spec template](engineering/templates/spec.md) and
[plan template](engineering/templates/plan.md) for new work.

- [Specs](superpowers/specs/): `YYYY-MM-DD-<topic>-design.md`.
- [Plans](superpowers/plans/): `YYYY-MM-DD-<topic>.md`, linked to the related spec.

Conventions describe current rules; architecture describes the current system;
specs and plans preserve individual task context. See the workflow for approval
and document-maintenance rules.
