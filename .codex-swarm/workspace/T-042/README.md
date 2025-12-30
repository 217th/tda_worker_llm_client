# T-042: E07 Implement LLMProfile + StructuredOutputSpec

## Summary

- Added LLMProfile and StructuredOutputSpec value objects with MVP validation rules.
- Exported new reporting domain types for upcoming LLM integration.

## Goal

- Provide typed, validated LLM profile/structured-output primitives for Epic 7.

## Scope

- Reporting domain only (no handler behavior change yet).
- Keep existing workflow validation unchanged to avoid behavior drift.

## Risks

- Downstream code still uses raw llmProfile mapping until later tasks integrate these objects.

## Verify Steps

- `rg -n "LLMProfile|StructuredOutputSpec" worker_llm_client/reporting/domain.py`

## Rollback Plan

- Revert reporting domain changes if integration shifts elsewhere.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `worker_llm_client/reporting/domain.py` (LLMProfile + StructuredOutputSpec)
- `worker_llm_client/reporting/__init__.py` (exports)
<!-- END AUTO SUMMARY -->
