# Observability

## Logging contract

Logging backend: **Google Cloud Logging** (structured JSON logs).

Runtime expectation:
- Log to stdout/stderr via Python `logging`; Cloud Functions gen2 / Cloud Run ingests these into Cloud Logging as `jsonPayload`.

Baseline goals:
- Provide a **stable event taxonomy** (snake_case) so dashboards/alerts can query `jsonPayload.event`.
- Support at-least-once Firestore trigger delivery (duplicate/reordered events).
- Avoid leaking secrets, full prompt text, or full artifacts.

### Required fields (every log entry)

- `service`: `worker_llm_client` (stable service name for dashboards)
- `env`: deployment environment (`dev|staging|prod` or similar)
- `component`: `worker_llm_client`
- `event`: stable event name (snake_case; see below)
- `severity`: `DEBUG|INFO|WARNING|ERROR`
- `message`: default equals `event`
- `time`: RFC3339 timestamp (UTC)
- correlation:
  - `eventId` (CloudEvent `id`)
  - `runId`
  - `stepId` (if applicable)
- `flowKey`, `timeframe`, `symbol` (required when already available from `flow_run`)
- `trace` / `spanId` (when available; rely on Cloud Run/Functions trace context)

### Recommended fields (when applicable)

- CloudEvent metadata:
  - `eventType` (CloudEvent `type`)
  - `subject` (CloudEvent `subject`)
- `stepType` (expect `LLM_REPORT`)
- `attempt` (worker attempt number within a single invocation)
- `firestore.updateTime` (claim precondition basis)
- `firestore.document`: `flow_runs/{runId}` (or full doc path if useful)
- `llm.promptId`, `llm.modelName`
- `llm.auth.mode`: `ai_studio_api_key|vertex_adc` (or similar; never log the key itself)
- `llm.schemaId`, `llm.schemaSha256` (when structured output schema registry is used)
- `llm.schemaVersion` (when known; derived from `llm.schemaId` naming)
- `llm.generationConfig` (sanitized; no secrets; summary is OK)
- `llm.requestId` (provider request ID, if available)
- `llm.usage` (input/output tokens, total tokens; naming TBD by SDK)
- `artifact.gcs_uri`
- `artifacts`: compact summaries of inputs/outputs (URIs, sizes, hashes; no full payloads)
- `durationMs`
- `error.code`, `error.message` (sanitized), `error.retryable`
- `exception` (exception info/stack trace when applicable)

### Logger safety gates (MVP)

To keep logs safe and consistent, `EventLogger` must enforce:

- Required field presence and types:
  - `service/env/component/event/severity/message/time` are non-empty strings.
  - `severity` must be one of `DEBUG|INFO|WARNING|ERROR`.
  - `env` is a short environment label (string), never an env dump or dict.
- Safe-field filtering:
  - Reject any payload containing secret-like keys anywhere in nested objects:
    - `apiKey`, `api_key`, `token`, `secret`, `authorization`, `credentials`.
  - Reject any payload containing prompt/raw-output keys:
    - `systemInstruction`, `userPrompt`, `promptText`, `candidateText`, `rawOutput`, `outputText`.
  - Allow `llm.promptId` and `llm.modelName`, but never prompt text.
- Size limits (per field; to avoid large payloads):
  - Strings: max 4096 chars (truncate or reject; MVP prefers reject).
  - Arrays: max 200 items (truncate or reject; MVP prefers reject).
- Serialization:
  - All fields must be JSON-serializable; if not, replace with a safe string summary.

These gates are enforced at logging time and must not be bypassed.

### Event names (baseline proposal)

Event names are a stable API for dashboards/alerts; keep them in **snake_case**.

CloudEvent lifecycle:
- `cloud_event_received`
- `cloud_event_parsed` (runId extracted)
- `cloud_event_ignored` (e.g., `reason=event_type_filtered|flow_run_not_found|invalid_subject`)
- `cloud_event_noop` (e.g., `reason=no_ready_step|dependency_not_succeeded|already_final`)
- `cloud_event_finished`

### `cloud_event_parsed` payload requirements (step summaries)

To make noisy Cloud Logging streams easier to analyze, `cloud_event_parsed` logs must include a compact summary of the current `flow_run` steps:

- include **all steps** (any `stepType`) with only:
  - `id`
  - `stepType`
  - `status`
  - `dependsOn`
- keep payload compact:
  - do **not** include `inputs` (avoid leaking prompt/context)
  - avoid embedding large structures (no full `steps` objects)
  - MVP: do not truncate `flowRunSteps` (log all step summaries)

Recommended fields for the same log entry:
- `flowRunFound`: boolean
- `flowRunStatus`: `PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED` (when found)
- `flowRunSteps`: array of step summaries as above (stable ordering: lexicographic by `id`)

Example (illustrative):

```json
{
  "service": "worker_llm_client",
  "env": "dev",
  "event": "cloud_event_parsed",
  "eventId": "8e101933-5679-46f0-bc89-089edbb2cada",
  "runId": "20251224-061000_LINKUSDT_demo92",
  "flowRunFound": true,
  "flowRunStatus": "RUNNING",
  "flowRunSteps": [
    {
      "id": "charts:1M:ctpl_price_ma1226_vol_v1",
      "stepType": "CHART_EXPORT",
      "status": "SUCCEEDED",
      "dependsOn": ["ohlcv_export:1M"]
    },
    {
      "id": "ohlcv_export:1M",
      "stepType": "OHLCV_EXPORT",
      "status": "SUCCEEDED",
      "dependsOn": []
    }
  ],
  "message": "CloudEvent parsed, runId extracted"
}
```

Step lifecycle:
- `ready_step_selected`
- `claim_attempt` (`claimed=true|false`; include `reason=precondition_failed|error`)

Prompt + context:
- `prompt_fetch_started` / `prompt_fetch_finished`
- `context_resolve_started` / `context_resolve_finished`
- `gcs_read_started` / `gcs_read_finished` (for inputs)

LLM:
- `llm_request_started`
- `llm_request_finished` (include `status=succeeded|failed`, `finishReason` if available)
- `structured_output_invalid` (structured output parse/schema/finishReason failure; include reason and safe diagnostics)
- `structured_output_schema_invalid` (schema registry/configuration invalid; fail-fast without calling Gemini)
- `structured_output_repair_attempt_started` / `structured_output_repair_attempt_finished`

Artifacts:
- `gcs_write_started`
- `gcs_write_finished`

Final status:
- `step_completed`
- `step_failed`

### Execution flow (typical ordering)

Typical successful flow (one invocation):
1. `cloud_event_received`
2. `cloud_event_parsed` (+ `flowRunSteps` summaries)
3. `ready_step_selected`
4. `claim_attempt` (`claimed=true`)
5. `prompt_fetch_started` → `prompt_fetch_finished`
6. `context_resolve_started` (+ `gcs_read_*` for referenced inputs) → `context_resolve_finished`
7. `llm_request_started` → `llm_request_finished` (`status=succeeded`)
8. `gcs_write_started` → `gcs_write_finished`
9. `step_completed`
10. `cloud_event_finished`

Expected no-op flows:
- no READY step: `cloud_event_noop` (`reason=no_ready_step`)
- dependencies not satisfied: `cloud_event_noop` (`reason=dependency_not_succeeded`)
- claim lost race: `cloud_event_noop` (`reason=claim_conflict`)

## Event catalog (MVP)

This table is the canonical event taxonomy for `worker_llm_client`.

### CloudEvent ingestion

| Event | Severity | When | Required fields (in addition to base) |
| --- | --- | --- | --- |
| `cloud_event_received` | INFO | entrypoint invoked | `eventType`, `subject` |
| `cloud_event_ignored` | WARNING | event filtered/invalid | `reason` |
| `cloud_event_parsed` | INFO | runId parsed + flowRun loaded | `flowRunFound`, `flowRunStatus`, `flowRunSteps[]` |
| `cloud_event_noop` | INFO | expected no-op | `reason` |
| `cloud_event_finished` | INFO | handler ends | `status` (`noop|ok|failed`) |

`cloud_event_noop.reason` values (stable):
- `no_ready_step`
- `dependency_not_succeeded`
- `claim_conflict`
- `already_final`

### Step selection and claim

| Event | Severity | When | Required fields |
| --- | --- | --- | --- |
| `ready_step_selected` | INFO | READY step chosen | `stepId`, `stepType`, `timeframe` |
| `claim_attempt` | INFO/WARNING | claim attempted | `claimed` (bool), `reason` (`precondition_failed|error|ok`) |

### Prompt and context

| Event | Severity | When | Required fields |
| --- | --- | --- | --- |
| `prompt_fetch_started` | INFO | before reading `llm_prompts/{promptId}` | `llm.promptId` |
| `prompt_fetch_finished` | INFO/ERROR | after read | `ok` (bool), optional `error.code` |
| `context_resolve_started` | INFO | before resolving inputs | `inputsSummary` (URIs only) |
| `gcs_read_started` | INFO | before reading an input object | `gcs_uri`, `kind` (`ohlcv|charts_manifest|previous_report|chart_image`) |
| `gcs_read_finished` | INFO/ERROR | after reading an input object | `gcs_uri`, `kind`, `ok` (bool), `bytes`, `durationMs` |
| `context_json_validated` | INFO | JSON artifact parsed + normalized | `kind` (`ohlcv|charts_manifest|previous_report`), `bytes`, `normalizedBytes` |
| `context_json_invalid` | WARNING | JSON artifact invalid | `kind`, `error.type` |
| `context_json_too_large` | WARNING | JSON artifact exceeds size limit | `kind`, `bytes`, `maxBytes` |
| `charts_manifest_parsed` | INFO | charts manifest items extracted | `itemsTotal`, `itemsWithUri` |
| `charts_manifest_no_images` | WARNING | charts manifest contains no valid images | `itemsTotal` |
| `chart_image_loaded` | INFO | chart image downloaded | `gcs_uri`, `bytes` |
| `chart_image_too_large` | WARNING | chart image exceeds size limit | `gcs_uri`, `bytes`, `maxBytes` |
| `user_input_built` | INFO | UserInput section assembled | `chartsCount`, `previousReportsCount`, `ohlcvBytes`, `chartsManifestBytes`, `textChars` |
| `context_resolve_finished` | INFO/ERROR | after resolution | `ok` (bool), `artifacts` (sizes/hashes only) |

### LLM call

| Event | Severity | When | Required fields |
| --- | --- | --- | --- |
| `llm_request_started` | INFO | before Gemini call | `llm.modelName`, `llm.promptId` |
| `llm_request_finished` | INFO/ERROR | after Gemini call | `status` (`succeeded|failed`), optional `finishReason`, optional `llm.usage` |
| `structured_output_invalid` | WARNING | structured output validation failed (before optional repair / before finalizing as FAILED) | `reason.kind` (`finish_reason|missing_text|json_parse|schema_validation`), `reason.message` (sanitized), `llm.finishReason` (if available), `diagnostics.textBytes`, `diagnostics.textSha256`, `policy.repairPlanned` (bool), `policy.remainingSeconds`, `policy.finalizeBudgetSeconds` |
| `structured_output_schema_invalid` | ERROR | structured output schema is missing/invalid/unsupported (pre-flight; no Gemini call) | `llm.schemaId`, `llm.schemaSha256` (if available), `reason.message` (sanitized), `error.code` (`LLM_PROFILE_INVALID`) |
| `structured_output_repair_attempt_started` | INFO | before the repair Gemini call | `attempt` (=1), `policy.repairDeadlineSeconds`, `policy.remainingSeconds`, `policy.finalizeBudgetSeconds` |
| `structured_output_repair_attempt_finished` | INFO/ERROR | after the repair Gemini call | `attempt` (=1), `status` (`succeeded|failed`), optional `llm.finishReason`, optional `llm.usage` |

### Output + finalize

| Event | Severity | When | Required fields |
| --- | --- | --- | --- |
| `gcs_write_started` | INFO | before writing report | `artifact.gcs_uri` |
| `gcs_write_finished` | INFO/ERROR | after write | `artifact.gcs_uri`, `ok` (bool), `bytes` |
| `step_completed` | INFO | after Firestore finalize success | `stepId`, `status` (`SUCCEEDED`) |
| `step_failed` | ERROR | after Firestore finalize failure | `stepId`, `status` (`FAILED`), `error.code` |

## Security and privacy (minimum)

- Never log secrets (Secret Manager values, tokens, credentials).
- Never log environment dumps (`os.environ`) or config objects that may include secrets.
- Config/validation errors for secrets must mention only the variable name / key id, never the secret value (and never its hash).
- Avoid logging full `flow_run` payloads; if absolutely needed for diagnostics, log a small redacted preview (or just `runId` + selected `stepId` + hashes/lengths).
- Do not put secrets/PII into GCS object names or URLs.

## Structured output diagnostics (MVP)

When structured output is enabled (Gemini JSON mode / response schema), failures must be **explainable from logs** without leaking the raw model output.

Rules:
- Never log raw candidate text / JSON payload, even on validation failure.
- Prefer logging **sizes + hashes** of the candidate text and a **sanitized** summary of validation errors.

Recommended fields for `structured_output_invalid`:
- `llm.schemaId`, `llm.schemaSha256` (when schema registry is used)
- `diagnostics.extractionMethod`: `candidate_parts|response_text`
- `reason.kind`: one of:
  - `finish_reason`: provider indicates generation was not successful for returning a complete payload
  - `missing_text`: no extractable candidate text found where expected
  - `json_parse`: invalid JSON (parse error)
  - `schema_validation`: JSON parsed but failed JSON Schema validation
- `reason.message`: short sanitized message, no payload excerpts
- `diagnostics.textBytes`: byte length of extracted candidate text (UTF-8)
- `diagnostics.textSha256`: SHA-256 hex of extracted candidate text (UTF-8)
- `diagnostics.validationErrors`: optional array of sanitized items (e.g. `{"path":"output.summary.markdown","error":"field required"}`), capped to a small number (e.g. 10)
- `policy.repairEligible`: boolean (true only for `reason.kind in {missing_text,json_parse,schema_validation}` and when time budget allows)
- `policy.repairExecuted`: boolean

If a repair attempt is executed:
- emit `structured_output_repair_attempt_started` and `structured_output_repair_attempt_finished`
- include `attempt=1` and a clear `status`

Additional mapping notes (MVP):
- `finishReason == SAFETY` should be treated as `LLM_SAFETY_BLOCK` (non-retryable) and is not a structured-output “repairable” case.
- truncation-like outcomes (e.g., `MAX_TOKENS`) that lead to parse/schema failure should surface as `INVALID_STRUCTURED_OUTPUT` and include `llm.finishReason` in `structured_output_invalid`.
- if structured output is required but unsupported/unavailable for the chosen model/endpoint/SDK, emit `structured_output_invalid` with `reason.kind=finish_reason` (or a dedicated `reason.kind` if preferred later) and finalize as `LLM_PROFILE_INVALID` (non-retryable).

## Metrics

Minimum recommended metrics (log-based metrics or custom):
- `step_executions_total{status,modelName,promptId}`
- `step_execution_latency_ms{modelName,promptId}` (p50/p95)
- `llm_request_latency_ms{modelName}`
- `llm_tokens_total{direction,modelName}` (`input|output`)
- `claim_conflicts_total`
- `gcs_write_failures_total`

## Alerts and dashboards

Draft alert candidates:
- high `step_execution_failed` rate (by flowKey/modelName)
- sustained `RATE_LIMITED` / `RESOURCE_EXHAUSTED`
- p95 latency increase for `llm.request`
- backlog indication: many `READY` steps older than N minutes (requires query/metric on Firestore; design TBD)
