# T-103: Add depth-5 simplified llm_report_output schema example

## Summary

- Add a simplified llm_report_output schema example with data nesting depth <= 5 for experiments.

## Goal

- Provide a low-nesting schema example to test Gemini nesting limits.

## Scope

- New example file only; no runtime changes.

## Risks

- Example may diverge from production schema expectations; use for experiments only.

## Verify Steps

- None (docs-only).

## Rollback Plan

- Remove the example file.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added depth-5 schema example file.
- Reduced example schema depth to 4 by flattening nested arrays/objects.
<!-- END AUTO SUMMARY -->
