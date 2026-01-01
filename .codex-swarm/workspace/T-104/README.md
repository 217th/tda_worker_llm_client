# T-104: Restructure LLM_REPORT UserInput format

## Summary

- Adjust UserInput assembly to the new structured format requested by the user.

## Goal

- Emit a deterministic UserInput section with metadata, OHLCV request_timestamp + data, chart template/kind list, and conditional previous reports section.

## Scope

- Update `UserInputAssembler` output and related docs/tests.

## Risks

- Prompt shape changes may affect downstream prompt quality.

## Verify Steps

- `python3 -m pytest -q`

## Rollback Plan

- Revert the commit(s) for T-104.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Created T-104 task README.
- Restructured UserInput assembly format and updated related docs/tests.
<!-- END AUTO SUMMARY -->
