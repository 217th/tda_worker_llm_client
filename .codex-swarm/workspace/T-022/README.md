# T-022: E03 Add unit tests for step selection + inputs

## Summary

- Added unit tests covering ReadyStepSelector and LLMReportInputs validation.

## Goal

- Validate domain selection and inputs resolution behavior with deterministic tests.

## Scope

- `tests/test_workflow_domain.py`

## Risks

- None; tests are isolated to domain logic.

## Verify Steps

- `python3 -m pytest -q tests/test_workflow_domain.py`

## Rollback Plan

- Remove the new tests if behavior needs to change.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
