# T-039: E06 Add artifact write stub (debug flag)

## Summary

- Added ARTIFACTS_DRY_RUN config and GCS-backed dry-run artifact write path.
- Stub writes canonical LLMReportFile JSON to deterministic GCS URI and patches outputs.gcs_uri.
- Covered config parsing with unit tests.

## Goal

- Allow Epic 6 demo to validate artifact write + Firestore patch without invoking LLMs.

## Scope

- Config: parse ARTIFACTS_DRY_RUN env flag.
- Handler: generate dry-run report JSON, write to GCS (create-only), patch Firestore outputs.gcs_uri.
- Main entrypoint: wire GCS client + artifact store when dry-run enabled.
- Tests: config parsing for ARTIFACTS_DRY_RUN.

## Risks

- Dry-run path depends on scope.symbol + step.timeframe being present in flow_run; missing fields cause failure.
- Firestore patch uses update_time precondition; concurrent updates can trigger precondition failures.

## Verify Steps

- `python3 -m unittest discover -s tests -p "test_*.py"`

## Rollback Plan

- Revert the T-039 commit(s) to remove ARTIFACTS_DRY_RUN wiring and dry-run artifact stub.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Updated: main.py, worker_llm_client/app/handler.py, worker_llm_client/ops/config.py
- Updated: tests/test_config.py
<!-- END AUTO SUMMARY -->
