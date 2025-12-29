# T-011: E01 Add unit tests for runtime config

## Summary

- Added unit tests for WorkerConfig single-key validation and safe error messaging.

## Goal

- Cover single-key happy path and missing/empty key errors without secret leakage.

## Scope

- Add tests under @tests/test_config.py using built-in unittest.

## Risks

- None beyond keeping tests aligned with config defaults.

## Verify Steps

- `python -m unittest tests.test_config`

## Rollback Plan

- Revert the commit containing the test file.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- tests/test_config.py
<!-- END AUTO SUMMARY -->
