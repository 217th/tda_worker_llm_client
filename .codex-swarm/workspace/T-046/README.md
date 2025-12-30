# T-046: E07 Tests: profile, user input, structured output

## Summary

- Added tests for LLMProfile/StructuredOutputSpec validation.
- Added tests for UserInputAssembler context resolution + size limits.
- Added tests for StructuredOutputValidator error mapping.

## Goal

- Cover core Epic 7 domain helpers with unit tests.

## Scope

- Unit tests only; no runtime behavior changes.

## Risks

- Tests use simplified manifests; may need tweaks if manifest schema changes.

## Verify Steps

- `python -m pytest -q`

## Rollback Plan

- Revert test files if test strategy changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `tests/test_reporting_profile.py` (LLMProfile/StructuredOutputSpec)
- `tests/test_user_input_assembler.py` (UserInputAssembler)
- `tests/test_structured_output_validator.py` (StructuredOutputValidator)
<!-- END AUTO SUMMARY -->
