# Feature or Change Design

Use the location and approval rules in the [workflow](../workflow.md). Replace
these instructions with concrete requirements and adapt relative links.

## Goal and Context

Describe the user problem, relevant existing behavior/code, actors, and desired
outcome. Distinguish implemented behavior from scaffolding.

## Scope

List what is included and excluded. State constraints and dependencies.

## Requirements and Expected Behavior

Describe inputs, observable outcomes, important edge cases, and acceptance criteria
that can be verified. Resolve questions affecting contracts or data before approval.

## Design and Alternatives

Explain the chosen approach and meaningful alternatives with trade-offs. Link to
applicable conventions and existing code. Describe layer responsibilities and the
router → service → repository flow if applicable.

## API Contract and Errors

For API changes, specify routes, methods, Pydantic request/response schemas, HTTP
statuses, validation, and failure behavior. Otherwise state why this is not applicable.

## Storage and Migration

For persistence changes, specify models, fields, relations, transactions, migration
impact, and existing-data handling. Otherwise state why this is not applicable.

## Acceptance Criteria and Verification

Give observable completion criteria and how each will be checked. Identify test
tooling or environment prerequisites, limits, and excluded checks.
