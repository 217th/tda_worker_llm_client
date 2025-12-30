# T-044: E07 Implement StructuredOutputValidator + StructuredOutputInvalid

## Summary

- Added StructuredOutputValidator and StructuredOutputInvalid with sanitized diagnostics.
- JSON parsing + schema validation (jsonschema when available; minimal fallback).

## Goal

- Provide deterministic structured output validation without logging raw model output.

## Scope

- Reporting-only module; no handler integration yet.

## Risks

- Validation error mapping may need tuning as schema complexity grows.

## Verify Steps

- `rg -n "StructuredOutputValidator" worker_llm_client/reporting/structured_output.py`

## Rollback Plan

- Revert reporting structured output validation module if validation policy changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `worker_llm_client/reporting/structured_output.py` (validator + diagnostics)
- `worker_llm_client/reporting/domain.py` (StructuredOutputInvalid)
- `worker_llm_client/reporting/__init__.py` (exports)
- `requirements.txt` (jsonschema)
<!-- END AUTO SUMMARY -->
