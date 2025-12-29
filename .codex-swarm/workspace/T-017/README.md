# T-017: E02 Dev verify logging chain

## Summary

- Triggered a Firestore update on `flow_runs/20251224-061000_LINKUSDT_demo92` (`debug.lastPing`) to exercise the Firestore update trigger.
- Observed a Cloud Run request log for the function invocation (HTTP 200) at `2025-12-29T13:38:22Z`.
- No `cloud_event_received` app log found yet in Cloud Logging (stdout/stderr) within 30m.

## Goal

- Verify that a Firestore update produces an application log event (`cloud_event_received`) with safe payload fields and no prompt/raw output leakage.

## Scope

- Dev environment only; single Firestore document update to `flow_runs/{runId}`.
- Cloud Logging verification via `gcloud logging read`.

## Risks

- Log delay or logging configuration may hide app logs; risk of false-negative verification.

## Verify Steps

- Firestore update (PATCH) to set `debug.lastPing` on `flow_runs/20251224-061000_LINKUSDT_demo92` (updateTime: `2025-12-29T13:38:22Z`).
- Cloud Logging query for app event:
  - Filter: `resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" (jsonPayload.event="cloud_event_received" OR textPayload:"cloud_event_received")`
  - Result: no entries in last 30m.
- Cloud Logging query for any stdout/stderr from app:
  - Filter: `resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" logName:("run.googleapis.com/stdout" OR "run.googleapis.com/stderr")`
  - Result: no entries in last 30m.
- Cloud Logging request log confirms invocation:
  - `POST https://worker-llm-client-…run.app/?__GCP_CloudEventsMode=CE_PUBSUB_BINDING` status 200 at `2025-12-29T13:38:22Z`.

## Rollback Plan

- No changes applied to code or infra; no rollback required.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
