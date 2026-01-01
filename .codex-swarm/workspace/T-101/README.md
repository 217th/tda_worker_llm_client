# T-101: Investigate LLM_REPORT failure due to charts manifest GCS URI

## Summary

- Investigate why LLM_REPORT fails with INVALID_STEP_INPUTS when CHART_EXPORT emits `outputsManifestGcsUri` instead of `outputs.gcs_uri`.
- Implement compatibility fallback for charts manifest resolution and align docs/contracts.
- Add detailed context-ingestion logs and update observability spec.

## Goal

- Identify the contract or code mismatch, propose the fix, and implement a resolution that allows LLM_REPORT to resolve the charts manifest correctly.

## Scope

- Investigation + resolution for charts manifest URI resolution between CHART_EXPORT outputs and LLM_REPORT inputs.

## Risks

- Risk of widening contract acceptance beyond spec without updating validation rules.

## Verify Steps

- `python3 -m pytest -q`

## Rollback Plan

- Revert the commit(s) for `T-101`.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added fallback resolution for CHART_EXPORT outputsManifestGcsUri in LLM_REPORT inputs.
- Added test coverage for charts manifest legacy output key.
- Updated flow_run schema/docs/specs to allow legacy outputsManifestGcsUri.
- Added structured logs for context ingestion and updated observability spec.
- Adjusted tests for new logging parameters and charts manifest legacy input.
<!-- END AUTO SUMMARY -->
