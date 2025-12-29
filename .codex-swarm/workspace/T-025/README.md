# T-025: E04 Implement FlowRunRepository port + claim/finalize models

## Summary

- Implemented FlowRunRepository port with claim/finalize models and patch builders.

## Goal

- Provide repository interface and helper builders for claim/finalize patches.

## Scope

- `worker_llm_client/app/services.py` and exports.

## Risks

- Patch builder semantics may need adjustment once Firestore impl lands.

## Verify Steps

- Unit tests to be added in T-027.

## Rollback Plan

- Remove repository port and helper builders if API changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
