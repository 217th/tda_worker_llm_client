# T-101: Investigate LLM_REPORT failure due to charts manifest GCS URI

## Summary

- Investigate why LLM_REPORT fails with INVALID_STEP_INPUTS when CHART_EXPORT emits `outputsManifestGcsUri` instead of `outputs.gcs_uri`.

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
- Created T-101 task README.
<!-- END AUTO SUMMARY -->
