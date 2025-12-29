# T-020: E03 Implement workflow domain models

## Summary

- Implemented workflow domain entities and validation helpers for Epic 3.

## Goal

- Provide FlowRun/FlowStep/LLMReport* domain models with minimal validation per spec.

## Scope

- New `worker_llm_client/workflow/domain.py` and exports.

## Risks

- Validation semantics may need adjustment once tests land in T-022.

## Verify Steps

- Unit tests to be added in T-022.

## Rollback Plan

- Remove workflow domain module and revert tasks if validation logic changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
