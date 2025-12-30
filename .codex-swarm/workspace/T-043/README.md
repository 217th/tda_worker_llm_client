# T-043: E07 Implement UserInputAssembler + context resolution

## Summary

- Implemented UserInputAssembler with context resolution (OHLCV, charts manifest, chart images, previous reports).
- Enforced per-artifact size limits and JSON validation per spec.

## Goal

- Provide deterministic UserInput assembly and GCS context resolution for LLM_REPORT steps.

## Scope

- New reporting service module only (no handler integration yet).
- Uses ArtifactStore for reads and returns text + image payloads.

## Risks

- Charts manifest parsing is best-effort; unknown manifest shapes may require adjustment.
- Missing/invalid chart image URIs currently fail the step.

## Verify Steps

- `rg -n "UserInputAssembler" worker_llm_client/reporting/services.py`

## Rollback Plan

- Revert reporting services module changes if assembly rules change.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `worker_llm_client/reporting/services.py` (UserInputAssembler + context resolution)
- `worker_llm_client/reporting/__init__.py` (exports)
<!-- END AUTO SUMMARY -->
