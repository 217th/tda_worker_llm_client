# T-033: E05 Epic 5 DoD verification + stabilization

## Summary

- Deployed new revision and executed Epic 5 demo (positive + 2 negative cases).
- Fixed deploy failure by adding Firestore client dependency.

## Goal

- Verify Epic 5 behavior in cloud: prompt/schema fetch logs without Gemini calls; negative cases surface PROMPT_NOT_FOUND / LLM_PROFILE_INVALID.

## Scope

- Update deploy of `worker-llm-client` to include Epic 5 changes.
- Trigger three demo runs via Firestore `updatedAt` patch.
- Capture Cloud Logging evidence for expected events.

## Risks

- Deployment initially failed due to missing Firestore dependency; fixed by adding `google-cloud-firestore` to requirements.

## Verify Steps

- Deploy: `gcloud functions deploy worker-llm-client ...` (update; revision `worker-llm-client-00008-duz`).
- Trigger Firestore updates (REST PATCH `updatedAt`) for:
  - `flow_runs/20251230-120000_LINKUSDT_demo8` (positive)
  - `flow_runs/20251230-120500_LINKUSDT_demo8_missing_prompt` (missing prompt)
  - `flow_runs/20251230-121000_LINKUSDT_demo8_invalid_schema` (invalid schema)
- Logs query (per runId):  
  `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="worker-llm-client" AND jsonPayload.runId="<runId>"' --freshness 10m`

## Results

- Deploy failure (revision `worker-llm-client-00007-cow`) due to `ImportError: cannot import name 'firestore' from 'google.cloud'`; fixed by adding `google-cloud-firestore` to `requirements.txt`.
- Successful deploy revision: `worker-llm-client-00008-duz` (updateTime `2025-12-30T07:20:14Z`).
- Positive run `20251230-120000_LINKUSDT_demo8`:
  - Logs: `cloud_event_parsed` → `ready_step_selected` → `prompt_fetch_started` (promptId `llm_report_prompt_v1`) → `prompt_fetch_finished ok=true` → `cloud_event_finished status=ok`.
  - No `structured_output_schema_invalid` or `llm_request_*` logs (Gemini not called).
- Negative run (missing prompt) `20251230-120500_LINKUSDT_demo8_missing_prompt`:
  - Logs: `prompt_fetch_started` (promptId `prompt_missing_v1`) → `prompt_fetch_finished ok=false error.code=PROMPT_NOT_FOUND` → `cloud_event_finished status=failed`.
- Negative run (invalid schema) `20251230-121000_LINKUSDT_demo8_invalid_schema`:
  - Logs: `prompt_fetch_started` → `prompt_fetch_finished ok=true` → `structured_output_schema_invalid error.code=LLM_PROFILE_INVALID` → `cloud_event_finished status=failed`.
- Safety: logs include IDs/flags only; no prompt text or secrets observed.

## Rollback Plan

- Revert `requirements.txt` change and redeploy previous revision if needed.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-033/README.md`
- `requirements.txt`
<!-- END AUTO SUMMARY -->
