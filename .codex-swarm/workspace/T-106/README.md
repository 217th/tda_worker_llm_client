# T-106: Update llm_schema upload instructions (consent + depth handling)

## Summary

- Update the schema upload checklist to forbid modifying user-provided jsonSchema without explicit consent and to require proposing depth-reduction options when depth validation fails.

## Goal

- Ensure the workflow is safe (no silent schema rewrites) and predictable when handling schema nesting limits.

## Scope

- Docs-only changes under `docs/checklists/`.

## Risks

- None (documentation change only).

## Verify Steps

- None.

## Rollback Plan

- Revert the commit(s) for T-106.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Created T-106 task README.
- Updated llm_schema upload checklist to require explicit consent for schema structure changes and to propose depth-reduction options.
<!-- END AUTO SUMMARY -->
