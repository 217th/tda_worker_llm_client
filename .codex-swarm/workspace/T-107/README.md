# T-107: Allow uppercase timeframe token in prompt/schema ids

## Summary

- Update promptId/schemaId validation rules to accept uppercase letters in the timeframe token (e.g., 1M, 4H).

## Goal

- Align ID validation with the requested timeframe format flexibility (lowercase + uppercase).

## Scope

- Documentation/spec regex updates for promptId/schemaId rules.

## Risks

- Low: widened acceptance might allow inconsistent casing if callers are not normalized.

## Verify Steps

- None.

## Rollback Plan

- Revert the commit(s) for T-107.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Created T-107 task README.
<!-- END AUTO SUMMARY -->
