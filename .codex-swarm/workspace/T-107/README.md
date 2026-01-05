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
- Updated prompt/schema ID validation regexes and schemaVersion parsing to support the new structured IDs (uppercase timeframe allowed).
- Aligned contracts/spec docs and JSON schemas with the new promptId/schemaId format (major/minor versions).
- Refreshed examples, test vectors, and unit tests to use the new IDs.
<!-- END AUTO SUMMARY -->
