# Feature or Change Implementation Plan

Use the location and approval rules in the [workflow](../workflow.md). Replace
these instructions with exact tasks and commands; adapt relative links.

## Goal and References

Link to the approved spec using a relative Markdown link, for example a sibling
file in `../specs/`. Link to the applicable conventions and summarize the outcome.

## Constraints and Dependencies

Carry forward the spec's constraints, prerequisite tasks, and environment/tooling
requirements. Identify files that must remain unchanged.

## Task 1: Concrete Deliverable

Repeat this section for each atomic task. Name exact files to create, modify, and
test. Explain what earlier tasks supply and what later tasks depend on.

- [ ] Write the test for a specified acceptance criterion.
- [ ] Run the exact targeted command; record the expected behavioral failure.
- [ ] Implement the minimum approved behavior in the named files.
- [ ] Rerun the targeted command and confirm Green.
- [ ] Refactor if needed and rerun the applicable checks.

For documentation-only tasks, replace the above code cycle with inspection of
existing content, concrete edits, and content/link checks. Define an observable
completion criterion for every task.

## Final Verification and Handoff

List exact commands and working directories for all affected areas, using the
[testing conventions](../conventions/testing.md). Include documentation updates
and diff/link review.
