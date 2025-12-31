# T-058: E08 Cloud demo: orchestration + time budget

## Summary

- Run dev demo for Epic 8 orchestration and time budget behavior.

## Scope

- Re-validate Epic 7 scenarios (see @.codex-swarm/workspace/T-047/README.md):
  - Positive run: LLM success → artifact written → step SUCCEEDED.
  - Negative 4.1: invalid schema → LLM_PROFILE_INVALID, no LLM call.
  - Negative 4.2: invalid structured output → INVALID_STRUCTURED_OUTPUT (MAX_TOKENS).
  - Negative 4.3: oversized OHLCV → INVALID_STEP_INPUTS, no LLM call.
- Epic 8 scenarios:
  - Positive: normal run succeeds with sufficient time budget.
  - Negative: time budget prevents LLM call and fails step cleanly.
- Document steps, log queries, and Firestore/GCS outcomes; reuse run commands from T-047.

## Risks

- Environment misconfig may mask time-budget behavior.

## Verify Steps

- Collect Cloud Logging evidence for Epic 7 re-check + Epic 8 scenarios.
- Use the same scripts/commands as in T-047:
  - `scripts/deploy_dev.sh` (with FIRESTORE_DATABASE, INVOCATION_TIMEOUT_SECONDS, FINALIZE_BUDGET_SECONDS).
  - `gcloud functions describe ...` (revision + env vars).
  - Firestore REST PATCH (updatedAt trigger; model/schema/status changes).
  - `gsutil cp` for oversized OHLCV test artifact.
  - `gcloud logging read ... jsonPayload.event=...` filters for event chains.

## Rollback Plan

- No rollback; verification only.

## Execution log (2025-12-31)

### Environment

- Project/region: kb-agent-479608 / europe-west4
- runId / stepId: 20251230-120000_LINKUSDT_demo8 / llm_report_1m_summary_v1
- promptId / schemaId (valid): llm_report_prompt_v1 / llm_report_output_v1
- model: gemini-2.5-flash-lite
- Report URI (deterministic): gs://tda-artifacts-test/20251230-120000_LINKUSDT_demo8/1M/llm_report_1m_summary_v1.json
- Revisions used:
  - worker-llm-client-00013-vud (INVOCATION_TIMEOUT_SECONDS=780, FINALIZE_BUDGET_SECONDS=120)
  - worker-llm-client-00014-cim (INVOCATION_TIMEOUT_SECONDS=60, FINALIZE_BUDGET_SECONDS=120)
  - worker-llm-client-00015-yof (INVOCATION_TIMEOUT_SECONDS=780, FINALIZE_BUDGET_SECONDS=120)

### Commands / requests executed (redact secrets)

- Function describe (current env):
  - Request: `gcloud functions describe worker-llm-client --gen2 --region europe-west4 --project kb-agent-479608 --format="yaml(name,state,serviceConfig.environmentVariables,serviceConfig.secretEnvironmentVariables,serviceConfig.timeoutSeconds,serviceConfig.serviceAccountEmail)"`
  - Response (summary): ACTIVE; env set; secret GEMINI_API_KEY wired.
- Positive scenario trigger:
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (modelName=gemini-2.5-flash-lite, schemaId=llm_report_output_v1, maxOutputTokens=1024, status=READY, ohlcv/charts URIs, updatedAt=2025-12-31T07:39:23.908255Z).
  - Response (summary): updateTime=2025-12-31T07:39:23.908255Z.
- Deploy (time-budget guard):
  - Request: `scripts/deploy_dev.sh` with `INVOCATION_TIMEOUT_SECONDS=60, FINALIZE_BUDGET_SECONDS=120`.
  - Response (summary): revision worker-llm-client-00014-cim, updateTime=2025-12-31T07:43:38Z.
- Time-budget trigger:
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (status=READY, updatedAt=2025-12-31T07:44:01.681919Z).
  - Response (summary): updateTime=2025-12-31T07:44:01.681919Z.
- Deploy (restore normal budget):
  - Request: `scripts/deploy_dev.sh` with `INVOCATION_TIMEOUT_SECONDS=780, FINALIZE_BUDGET_SECONDS=120`.
  - Response (summary): revision worker-llm-client-00015-yof, updateTime=2025-12-31T07:48:12Z.
- Negative 4.1 (invalid schema doc):
  - Request: create llm_schemas/llm_report_output_v99 (jsonSchema missing required summary).
  - Response (summary): updateTime=2025-12-31T07:49:53Z.
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (structuredOutput.schemaId=llm_report_output_v99, status=READY, updatedAt=2025-12-31T07:52:37.951615Z).
  - Response (summary): updateTime=2025-12-31T07:52:37.951615Z.
- Negative 4.2 (structured output invalid):
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (maxOutputTokens=5, structuredOutput.schemaId=llm_report_output_v1, status=READY, updatedAt=2025-12-31T07:54:09.752495Z).
  - Response (summary): updateTime=2025-12-31T07:54:09.752495Z.
- Negative 4.3 (oversized input):
  - Request: `gsutil cp /tmp/ohlcv_big.json gs://tda-artifacts-test/20251230-120000_LINKUSDT_demo8/ohlcv_export:1M/1M_big.json` (size 100010 bytes).
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (ohlcv_export_1m.outputs.gcs_uri=.../1M_big.json, maxOutputTokens=1024, structuredOutput.schemaId=llm_report_output_v1, status=READY, updatedAt=2025-12-31T07:56:19.394831Z).
  - Response (summary): updateTime=2025-12-31T07:56:19.394831Z.
- Cleanup:
  - Request: DELETE llm_schemas/llm_report_output_v99.
  - Request: PATCH flow_runs/20251230-120000_LINKUSDT_demo8 (restore ohlcv_export_1m.outputs.gcs_uri to 1M.json).

### Logs evidence (filters used)

- `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --freshness=2h --limit 200 --format json`
- `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="time_budget_exceeded" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --freshness=30m --limit 20 --format json`
- `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="structured_output_schema_invalid" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --freshness=30m --limit 20 --format json`
- `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="structured_output_invalid" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --freshness=30m --limit 20 --format json`
- `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="context_resolve_finished" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --freshness=30m --limit 20 --format json`

### Results

- Positive (rev 00013-vud):
  - Logs: llm_request_finished (succeeded), gcs_write_finished, cloud_event_finished status=ok.
  - Firestore: status=SUCCEEDED, outputs.gcs_uri set to deterministic report URI; error cleared.
- Time budget (rev 00014-cim):
  - Logs: time_budget_exceeded, cloud_event_finished status=failed; no llm_request_started after budget failure.
  - Firestore: status=FAILED, error.code=TIME_BUDGET_EXCEEDED, error.message="Insufficient time budget for external calls".
- Negative 4.1 (rev 00015-yof):
  - Logs: structured_output_schema_invalid (LLM_PROFILE_INVALID, reason="schema missing or violates invariants").
  - Firestore: status=FAILED, error.code=LLM_PROFILE_INVALID.
- Negative 4.2 (rev 00015-yof):
  - Logs: structured_output_invalid kind=json_parse (LLM finished with MAX_TOKENS).
  - Firestore: status=FAILED, error.code=INVALID_STRUCTURED_OUTPUT.
- Negative 4.3 (rev 00015-yof):
  - Logs: context_resolve_finished ok=false, reason="ohlcv exceeds maxContextBytesPerJsonArtifact"; no llm_request_started.
  - Firestore: status=FAILED, error.code=INVALID_STEP_INPUTS.
