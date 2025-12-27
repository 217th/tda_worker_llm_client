# Observability

## Logging contract

Logging backend: **Google Cloud Logging** (structured JSON logs).

Runtime expectation:
- Log to stdout/stderr via Python `logging`; Cloud Functions gen2 / Cloud Run ingests these into Cloud Logging as `jsonPayload`.

### Required fields (every log entry)

- `service`: `worker_llm_client` (stable service name for dashboards)
- `env`: deployment environment (`dev|staging|prod` or similar)
- `component`: `worker_llm_client`
- `event`: stable event name (snake_case; see below)
- `severity`: `DEBUG|INFO|WARNING|ERROR`
- correlation:
  - `eventId` (CloudEvent `id`)
  - `runId`
  - `stepId` (if applicable)
- `flowKey`, `timeframe`, `symbol` (required when already available from `flow_run`)
- `trace` / `spanId` (when available; rely on Cloud Run/Functions trace context)

### Recommended fields (when applicable)

- `stepType` (expect `LLM_REPORT`)
- `attempt` (worker attempt number within a single invocation)
- `firestore.updateTime` (claim precondition basis)
- `firestore.document`: `flow_runs/{runId}` (or full doc path if useful)
- `llm.promptId`, `llm.modelName`
- `llm.generationConfig` (sanitized; no secrets; summary is OK)
- `llm.requestId` (provider request ID, if available)
- `llm.usage` (input/output tokens, total tokens; naming TBD by SDK)
- `artifact.gcs_uri`
- `durationMs`
- `error.code`, `error.message` (sanitized), `error.retryable`

### Event names (baseline proposal)

Event names are a stable API for dashboards/alerts; keep them in **snake_case**.

CloudEvent lifecycle:
- `cloud_event_received`
- `cloud_event_parsed` (runId extracted)
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

LLM:
- `llm_request_started`
- `llm_request_finished` (include `status=succeeded|failed`, `finishReason` if available)

Artifacts:
- `gcs_write_started`
- `gcs_write_finished`

Final status:
- `step_completed`
- `step_failed`

Existing “event taxonomy” from previous projects should be integrated here (open question).

## Security and privacy (minimum)

- Never log secrets (Secret Manager values, tokens, credentials).
- Avoid logging full `flow_run` payloads; if absolutely needed for diagnostics, log a small redacted preview (or just `runId` + selected `stepId` + hashes/lengths).
- Do not put secrets/PII into GCS object names or URLs.

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
