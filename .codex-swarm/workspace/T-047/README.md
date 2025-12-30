# T-047: E07 Epic 7 DoD verification (dev)

## Summary

- Checklist for Epic 7 DoD verification with per-step request/response logging.

## Goal

- Execute and document Epic 7 demo scenarios (positive + negative) with traceable evidence.

## Scope

- Dev environment; Firestore + GCS + Cloud Functions gen2.
- Verification run against deployed revision `worker-llm-client-00010-xog`.

## Risks

- Requests may expose secrets if not redacted; ensure all outputs are sanitized.
- Large artifacts may exceed limits and cause early failure (expected in negative scenario 4.3).
- Prior error fields can persist after success (tracked in T-052).

## Verify Steps

- Run the checklist below and capture request/response details under “Execution log”.

## Rollback Plan

- No rollback (verification only).

## Checklist (with expected behavior/results)

### 1) Prerequisites (before any trigger)

- [x] Function revision is deployed with Epic 7 code (LLMClient + StructuredOutputValidator + UserInputAssembler).
  - Expected: function is ACTIVE, latest revision matches this repo.
- [x] GEMINI_API_KEY injected via Secret Manager; allowlist (if set) permits target model.
  - Expected: env/secret wiring present, no secret values logged.
- [x] Firestore seed docs exist:
  - llm_prompts/{promptId}
  - llm_schemas/{schemaId}
  - flow_runs/{runId} with READY LLM_REPORT step and valid input refs
  - Expected: documents readable and valid per contracts.
- [x] GCS input artifacts exist and are within size limits:
  - OHLCV JSON ≤ 64KB
  - charts manifest JSON ≤ 64KB
  - chart images ≤ 256KB each
  - Expected: objects exist; sizes under limits.
- [x] Runtime SA has GCS read access for input artifacts (bucket IAM includes objectViewer).
  - Expected: no 403 on context resolve.

### 2) Preparation

- [x] Confirm target runId/stepId/timeframe/symbol.
- [x] Confirm deterministic output URI (ARTIFACTS_PREFIX/runId/timeframe/stepId.json).
- [x] Capture baseline Firestore doc snapshot (before trigger).

### 3) Positive scenario (valid structured output + report artifact)

Steps:
- [x] Trigger flow_runs/{runId} update (e.g., patch updatedAt).
- [x] Observe logs sequence:
  - prompt_fetch_started → prompt_fetch_finished
  - context_resolve_started → gcs_read_* → context_resolve_finished ok=true
  - llm_request_started → llm_request_finished status=succeeded
  - (no structured_output_invalid)
  - gcs_write_started → gcs_write_finished ok=true
  - step_completed status=SUCCEEDED
  - cloud_event_finished status=ok
- [x] Verify Firestore:
  - steps.<stepId>.status=SUCCEEDED
  - steps.<stepId>.outputs.gcs_uri set to deterministic URI
  - steps.<stepId>.error absent
- [x] Verify GCS report object exists at deterministic URI.

Expected result:
- LLM call succeeds; structured output validates; report artifact written; Firestore updated.
- Logs contain only safe diagnostics (no raw prompt/context/output).

### 4) Negative scenarios

#### 4.1 Invalid schema (LLM_PROFILE_INVALID) — preflight, no LLM call

Steps:
- [ ] Use flow_run referencing invalid schema (e.g., missing summary.markdown requirement).
- [ ] Trigger update.
- [ ] Observe logs:
  - structured_output_schema_invalid (ERROR)
  - cloud_event_finished status=failed
  - no llm_request_started
- [ ] Verify Firestore:
  - steps.<stepId>.status=FAILED
  - steps.<stepId>.error.code=LLM_PROFILE_INVALID
- [ ] Verify no report artifact created.

Expected result:
- Preflight validation fails; no LLM call; step FAILED with LLM_PROFILE_INVALID.

#### 4.2 Invalid structured output (INVALID_STRUCTURED_OUTPUT)

Steps:
- [x] Force invalid JSON (e.g., very low maxOutputTokens to truncate).
- [x] Trigger update.
- [x] Observe logs:
  - llm_request_started → llm_request_finished
  - structured_output_invalid (WARNING) with reason.kind=json_parse or schema_validation
  - cloud_event_finished status=failed
- [x] Verify Firestore:
  - steps.<stepId>.status=FAILED
  - steps.<stepId>.error.code=INVALID_STRUCTURED_OUTPUT
  - steps.<stepId>.error.message is sanitized (no raw output)
- [x] Verify report artifact absent (unless failure‑artifact policy is explicitly enabled).

Expected result:
- LLM call occurs; structured output fails validation; step FAILED with INVALID_STRUCTURED_OUTPUT.

#### 4.3 Input artifacts too large (INVALID_STEP_INPUTS)

Steps:
- [x] Prepare OHLCV JSON >64KB or chart image >256KB and reference it.
- [x] Trigger update.
- [x] Observe logs:
  - context_resolve_started
  - gcs_read_* (bytes logged)
  - context_resolve_finished ok=false (or explicit INVALID_STEP_INPUTS)
  - no llm_request_started
- [x] Verify Firestore:
  - steps.<stepId>.status=FAILED
  - steps.<stepId>.error.code=INVALID_STEP_INPUTS
- [x] Verify report artifact absent.

Expected result:
- Context resolution fails due to size; step FAILED with INVALID_STEP_INPUTS; no LLM call.

## Execution log (fill during run; include request/response details)

### Environment
- Function revision:
  - gcloud: ACTIVE, python313, timeoutSeconds=60, serviceAccount=tda-worker-llm-client@kb-agent-479608.iam.gserviceaccount.com
  - revision: worker-llm-client-00010-xog (updateTime=2025-12-30T17:46:06Z)
  - env: ARTIFACTS_BUCKET=tda-artifacts-test, ARTIFACTS_DRY_RUN=false, LOG_LEVEL=INFO
  - secret env: GEMINI_API_KEY=projects/457107786858/secrets/gemini-api-key:latest
- runId / stepId: 20251230-120000_LINKUSDT_demo8 / llm_report_1m_summary_v1
- promptId / schemaId: llm_report_prompt_v1 / llm_report_output_v1
- model: gemini-2.5-flash-lite (from llmProfile in flow_run)
- ARTIFACTS_PREFIX / deterministic report URI: (no prefix) / gs://tda-artifacts-test/20251230-120000_LINKUSDT_demo8/1M/llm_report_1m_summary_v1.json

### Commands / requests executed (redact secrets)
- Deploy revision:
  - Request: `scripts/deploy_dev.sh` (env inline: PROJECT_ID/REGION/FUNCTION_NAME/FIRESTORE_DB/RUNTIME_SA_EMAIL/ARTIFACTS_BUCKET/FLOW_RUNS_COLLECTION/SECRET_ENV_VARS/ARTIFACTS_DRY_RUN=false)
  - Response (summary): deployed revision `worker-llm-client-00010-xog`, updateTime=2025-12-30T17:46:06Z.
- Function describe (gcloud):
  - Request: `gcloud functions describe worker-llm-client --gen2 --region europe-west4 --project kb-agent-479608 --format=yaml(name,state,buildConfig.runtime,serviceConfig.timeoutSeconds,serviceConfig.environmentVariables,serviceConfig.secretEnvironmentVariables,serviceConfig.serviceAccountEmail)`
  - Response (summary): state=ACTIVE, runtime=python313, timeoutSeconds=60, ARTIFACTS_DRY_RUN=false, secret env GEMINI_API_KEY set.
- Firestore PATCH (set modelName to gemini-2.5-flash-lite):
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=steps.llm_report_1m_summary_v1.inputs.llm.llmProfile.modelName`
  - Response (summary): modelName=gemini-2.5-flash-lite.
- Firestore PATCH (trigger run, reset status, clear error):
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=updatedAt&updateMask.fieldPaths=steps.llm_report_1m_summary_v1.status&updateMask.fieldPaths=steps.llm_report_1m_summary_v1.error` (Authorization: Bearer **REDACTED**)
  - Response (summary): updatedAt refreshed; status=READY; error cleared.
- GCS IAM fix (T-051 deviation):
  - Request: `gcloud storage buckets add-iam-policy-binding gs://tda-artifacts-test --member serviceAccount:tda-worker-llm-client@kb-agent-479608.iam.gserviceaccount.com --role roles/storage.objectViewer`
  - Response (summary): binding added.
- Charts manifest workaround (T-053 deviation):
  - Request: `gsutil cp /tmp/charts_manifest_demo.json gs://tda-artifacts-test/charts/20251224-061000_LINKUSDT_demo8/charts:1M:ctpl_price_ma1226_vol_v1/manifest_demo.json`
  - Response (summary): upload ok.
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=steps.charts_1m.outputs.gcs_uri` (Authorization: Bearer **REDACTED**)
  - Response (summary): charts_1m.outputs.gcs_uri points to manifest_demo.json (uses gcs_uri key).
- Firestore PATCH (trigger positive run):
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=updatedAt` (Authorization: Bearer **REDACTED**)
  - Response (summary): handler executed; step SUCCEEDED; outputs.gcs_uri set.
- Negative 4.2 (force truncation):
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=steps.llm_report_1m_summary_v1.inputs.llm.llmProfile.maxOutputTokens&updateMask.fieldPaths=steps.llm_report_1m_summary_v1.status` (Authorization: Bearer **REDACTED**)
  - Response (summary): maxOutputTokens=5; status=READY.
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=updatedAt` (Authorization: Bearer **REDACTED**)
  - Response (summary): handler executed; step FAILED with INVALID_STRUCTURED_OUTPUT.
- Negative 4.3 (oversized OHLCV):
  - Request: `gsutil cp /tmp/ohlcv_big.json gs://tda-artifacts-test/20251230-120000_LINKUSDT_demo8/ohlcv_export:1M/1M_big.json`
  - Response (summary): upload ok (size 100410 bytes).
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=steps.ohlcv_export_1m.outputs.gcs_uri&updateMask.fieldPaths=steps.llm_report_1m_summary_v1.status` (Authorization: Bearer **REDACTED**)
  - Response (summary): ohlcv_export_1m.outputs.gcs_uri points to 1M_big.json; status=READY.
  - Request: `PATCH https://firestore.googleapis.com/v1/projects/kb-agent-479608/databases/tda-db-europe-west4/documents/flow_runs/20251230-120000_LINKUSDT_demo8?updateMask.fieldPaths=updatedAt` (Authorization: Bearer **REDACTED**)
  - Response (summary): handler executed; step FAILED with INVALID_STEP_INPUTS.

### LLM request/response (sanitized)
- Request summary:
  - model: gemini-2.5-flash-lite
  - responseMimeType: application/json
  - schemaId: llm_report_output_v1
  - inputs: prompt + OHLCV JSON + chart image from manifest_demo.json
  - limits: maxContextBytesPerJsonArtifact=65536, maxContextBytesPerImage=262144
- Response summary (positive):
  - finishReason: STOP
  - usage: prompt_token_count=7331, candidates_token_count=477, total_token_count=7808
  - structured output: valid (no structured_output_invalid)
- Response summary (negative 4.2):
  - finishReason: MAX_TOKENS
  - structured output: invalid (json_parse)
  - textBytes=19, textSha256=1d64bb1b8aebcdb4e2d5c0b3f820f27b8fa4bbfc1aa6f7e560e92cf933a62f3d
- Raw output: **DO NOT RECORD** (store only hash/bytes if needed)

### Logs evidence
- Log query/filters used:
  - `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --limit 200 --format json`
  - `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="structured_output_invalid" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --limit 20 --format json`
  - `gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="worker-llm-client" jsonPayload.event="context_resolve_finished" jsonPayload.runId="20251230-120000_LINKUSDT_demo8"' --limit 20 --format json`
- Key log entries (timestamps + event names):
  - 2025-12-30T17:54:35Z: cloud_event_parsed → ready_step_selected → prompt_fetch_started → prompt_fetch_finished → context_resolve_started → context_resolve_finished ok=true → llm_request_started → llm_request_finished (STOP) → gcs_write_started → gcs_write_finished (reused=true) → step_completed status=SUCCEEDED → cloud_event_finished status=ok
  - 2025-12-30T17:54:46Z: step_completed status=SUCCEEDED but error field remained (see T-052)
  - 2025-12-30T17:58:06Z: llm_request_finished (MAX_TOKENS) → structured_output_invalid kind=json_parse → cloud_event_finished status=failed
  - 2025-12-30T17:58:33Z: context_resolve_finished ok=false reason="ohlcv exceeds maxContextBytesPerJsonArtifact" → cloud_event_finished status=failed

### Results
- Positive scenario result:
  - LLM call succeeded; structured output validated; report artifact write logged.
  - Firestore step status SUCCEEDED; outputs.gcs_uri set.
  - Deviation: prior error field remained after success (T-052).
- Negative 4.1 result:
  - Previously observed structured_output_schema_invalid and cloud_event_finished status=failed.
  - Not re-run after revision 00010-xog (still valid preflight path).
- Negative 4.2 result:
  - LLM call executed; structured output invalid (json_parse); step FAILED with INVALID_STRUCTURED_OUTPUT.
- Negative 4.3 result:
  - Context resolve failed due to oversized OHLCV; step FAILED with INVALID_STEP_INPUTS; no LLM call.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-047/README.md` (verification checklist + execution log template)
<!-- END AUTO SUMMARY -->
