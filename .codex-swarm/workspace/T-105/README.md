# T-105: Create minimal llm_schema v5 and upload

## Summary

- Create a minimal llm_report_output_v5 schema document that passes validation and upload it to Firestore.

## Goal

- Provide the smallest valid schema for experiments and ensure it is available in llm_schemas.

## Scope

- Add example JSON in docs and upload to Firestore.

## Risks

- Minimal schema may be too permissive for production use; use only for experiments.

## Verify Steps

- None (docs-only).

## Rollback Plan

- Delete llm_schemas/llm_report_output_v5 and remove the example file.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Created T-105 task README.
- Added minimal v5 schema example file.
<!-- END AUTO SUMMARY -->
