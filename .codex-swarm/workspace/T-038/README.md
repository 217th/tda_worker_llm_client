# T-038: E06 Epic 6 DoD verification (dev)

## Summary

- Updated dev function to enable ARTIFACTS_DRY_RUN (revision worker-llm-client-00009-kof).
- Verified Epic 5 seed run and dry-run artifact write + Firestore patch (positive + idempotent reuse).
- Fixed missing GCS permission for runtime SA (objectCreator on tda-artifacts-test).
- Run used: runId `20251230-120000_LINKUSDT_demo8`, stepId `llm_report_1m_summary_v1`, timeframe `1M`.
- Logs: initial write failed (GCS_WRITE_FAILED at 2025-12-30T09:12:28Z); after IAM fix, write succeeded (eventId `a6238c76-...`, reused=false at 09:14:30Z) and retrigger reused path (eventId `dd0afcba-...`, reused=true at 09:14:31Z).

## Goal

- Verify Epic 6 DoD in dev: deterministic GCS artifact write + Firestore outputs.gcs_uri patching via dry-run.

## Scope

- Update deploy to set ARTIFACTS_DRY_RUN=true.
- Trigger flow_runs update for runId 20251230-120000_LINKUSDT_demo8.
- Validate logs, GCS object creation, Firestore outputs.gcs_uri, and idempotency reuse path.
- Remediate runtime SA permissions for GCS writes.

## Risks

- Runtime SA needs GCS objectCreator on artifacts bucket; missing IAM blocks artifact writes.
- Firestore update from the worker retriggers the handler; idempotency must be safe (reused path).

## Verify Steps

- Deploy update (ARTIFACTS_DRY_RUN=true) and confirm ACTIVE revision.
- Patch Firestore `flow_runs/20251230-120000_LINKUSDT_demo8` updatedAt (REST).
- Logs (Cloud Run): `gcs_write_started` → `gcs_write_finished` (ok/reused) → `cloud_event_finished`.
- GCS: `gs://tda-artifacts-test/20251230-120000_LINKUSDT_demo8/1M/llm_report_1m_summary_v1.json` exists.
- Firestore: `steps.llm_report_1m_summary_v1.outputs.gcs_uri` equals the deterministic URI.

## Rollback Plan

- Disable ARTIFACTS_DRY_RUN (env var) or roll back to prior revision if needed.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Updated: .codex-swarm/workspace/T-038/README.md
<!-- END AUTO SUMMARY -->
