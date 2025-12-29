# T-006: E00 Verify dev deploy pipeline + smoke scenario (DoD)

## Summary

- Verified dev deploy pipeline with a Firestore update trigger.
- Eventarc delivered a CloudEvent to the function (request log observed).
- Stub app did not emit a visible stdout log line; runId was not captured in app logs.

## Goal

- Confirm deploy + trigger wiring works in dev.

## Scope

- Smoke verification in dev (Cloud Logging + trigger delivery).

## Risks

- Stub logging is not visible in stdout; runId correlation is limited to Eventarc request logs.

## Verify Steps

- Firestore update (user-provided):
  - runId: `20251224-061000_LINKUSDT_demo92`
  - time: 2025-12-29 ~11:45 UTC (approx; see request log timestamp)
- Cloud Logging evidence (Eventarc delivery):
  - request log entry at `2025-12-29T11:45:36.713659Z`
  - `resource.type=cloud_run_revision`, `service_name=worker-llm-client`
  - `cloud_event_source=//firestore.googleapis.com/projects/kb-agent-479608/databases/tda-db-europe-west4`
- Query used:
  - `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="worker-llm-client"' --project kb-agent-479608 --limit 20 --freshness 30m`

## Rollback Plan

- No rollback required (verification only).

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Recorded dev smoke verification evidence:
  - .codex-swarm/workspace/T-006/README.md
<!-- END AUTO SUMMARY -->
