# Implementation contract (black-box behavior)

## Scope and responsibilities

**Component:** `worker_llm_client` (Trading Decision Assistant)

Primary responsibility: execute workflow steps of `stepType=LLM_REPORT` for a given `flow_runs/{runId}`.

The worker must:
- be triggered by Firestore document update events for `flow_runs/{runId}`
- select an executable step (`READY`, dependencies satisfied)
- claim it atomically (`READY → RUNNING`) using Firestore optimistic update precondition (`update_time`)
- perform a Gemini request using instructions stored in Firestore (by `promptId`) and a model selected by `modelId`
- write the output artifact to Cloud Storage (JSON preferred)
- persist execution metadata and final step status back to Firestore

Non-responsibilities:
- making steps become `READY` (that is an orchestrator responsibility)
- executing non-LLM steps (`OHLCV_EXPORT`, `CHART_EXPORT`, etc.)
- managing downstream publishing of reports

## Domain entities and lifecycle

### `flow_runs/{runId}` (FlowRun)

Source of truth for:
- flow identity and scope (`flowKey`, `scope.symbol`)
- overall run status (`status`)
- step graph (`steps` map)

Schema: `contracts/flow_run.schema.json`

### `steps.<stepId>` (FlowStep)

For this component, we care about:
- `stepType`: must be `LLM_REPORT`
- `status`: `PENDING | READY | RUNNING | SUCCEEDED | FAILED | SKIPPED | CANCELLED`
- `dependsOn`: step IDs that must be `SUCCEEDED` before execution
- `inputs.llm`:
  - `promptId` (points to instruction doc in Firestore)
  - `modelId` (selects Gemini model/config)
  - optional overrides (e.g., generation config)
- `inputs` (artifact sources for prompt context):
  - `ohlcvStepId`: step ID of an `OHLCV_EXPORT` step; worker resolves `steps[ohlcvStepId].outputs.gcs_uri`
  - `chartsManifestStepId`: step ID of a `CHART_EXPORT` step; worker resolves `steps[chartsManifestStepId].outputs.gcs_uri` (charts manifest JSON)
  - optional `previousReportStepIds`: step IDs of earlier `LLM_REPORT` steps whose artifacts may be included as context
- `outputs`:
  - `gcs_uri` (output artifact)
  - optional execution metadata (see below)

### Prompt / model documents (Firestore)

Stored separately from flow runs to enable reuse and versioning:
- prompt/instruction doc referenced by `promptId`
- model config referenced by `modelId`

Exact schemas are to be finalized.

## Invariants

1. **No silent execution:** worker must never execute a step unless it is `READY` and dependencies are satisfied.
2. **At most one claimant:** only one invocation may transition a step from `READY` to `RUNNING` (enforced by precondition on `update_time`).
3. **Idempotent event handling:** duplicate/reordered Firestore update events must not produce duplicated side effects.
4. **Deterministic artifact path:** output object name must be derived from stable identifiers (at least `runId` + `timeframe` + `stepId`) to support idempotency.
5. **No sensitive data in logs:** prompt text, secrets, and large payloads are not logged; only hashes/lengths/URIs.

6. **Workers do not set `READY`:** step eligibility is decided by the orchestrator (e.g., `advance_flow`); workers only do `READY → RUNNING → SUCCEEDED/FAILED`.

## Security and privacy (minimum)

Sensitive data categories to treat as restricted:
- API keys / tokens / service account credentials
- prompt contents (may contain proprietary strategy details)
- any PII (if introduced in the future)

Hard rules:
- never log secrets or full prompt/context payloads
- do not put secrets/PII into GCS object names or Firestore IDs
- restrict GCS bucket ACLs to service accounts; no public access

## Main scenarios (happy paths)

### Scenario A: No-op (no executable step)

Input: update event for `flow_runs/{runId}` where:
- no step exists with `stepType=LLM_REPORT` and `status=READY`, or
- such step exists but at least one `dependsOn` step is not `SUCCEEDED`, or
- `flow_run.status` is not `RUNNING`

Output:
- no writes to Firestore/GCS (except logging)

### Scenario B: Execute one `READY` LLM_REPORT step

Input: update event for `flow_runs/{runId}` with at least one executable step.

Processing:
1. Load `flow_runs/{runId}` from Firestore.
2. Pick one executable step:
   - `stepType == LLM_REPORT`
   - `status == READY`
   - all `dependsOn` steps exist and have `status == SUCCEEDED`
   - if multiple, pick deterministically (lexicographic by `stepId`)
3. Claim the step:
   - patch `steps.<stepId>.status = RUNNING`
   - patch `steps.<stepId>.startedAt = now()` (field name TBD; if absent in schema, store in `outputs` or a nested `execution` object)
   - write with optimistic precondition: `last_update_time = doc.update_time`
4. Resolve prompt and model config from Firestore.
5. Load referenced context artifacts from GCS (as required by the prompt).
6. Call Gemini with generation config and structured output preference.
7. Write output artifact to GCS.
8. Patch `flow_runs/{runId}`:
   - `steps.<stepId>.outputs.gcs_uri = <gs://...>`
   - store execution metadata (duration, model, token usage, request ID, etc.)
   - `steps.<stepId>.status = SUCCEEDED`
   - `steps.<stepId>.finishedAt = now()`

### Output artifact format (canonical)

The worker writes a single JSON file to GCS for the report. Canonical schema:
- `contracts/llm_report_file.schema.json`

Notes:
- the JSON includes `output.summary.markdown` (human-readable) and a flexible `output.details` object
- the worker should embed enough `metadata` to make the file self-describing (runId/stepId/symbol/timeframe/promptId/modelId + input URIs + finish metadata like modelVersion/finishReason/usage)

### Context artifact ingestion (policy)

For JSON context artifacts (OHLCV, charts manifest, previous reports):
- worker downloads objects from GCS and injects the content as text into the prompt (or as a dedicated text-part, depending on the SDK).
- apply a hard size limit per artifact (e.g., `maxContextBytesPerArtifact`, default 32KB); if exceeded, fail the step with `INVALID_STEP_INPUTS` (contract violation / too-large context).

### Artifact naming (decision)

- Group artifacts by `runId` and use deterministic names derived from stable identifiers.
- Canonical JSON artifact path (OHLCV / charts manifest / LLM report):
  - `<ARTIFACTS_PREFIX>/<runId>/<timeframe>/<stepId>.json`
- Do not include `attempt` or non-deterministic timestamps in JSON object names.

Invariant:
- `steps[stepId].timeframe` must match both the `<timeframe>` path segment and the `<timeframe>` embedded in `stepId` (if present).

## CloudEvent parsing (runId extraction)

Worker derives `runId` from CloudEvent `subject` by extracting the last path segment after `flow_runs/`.

Notes:
- subject format differs between trigger types/SDKs; keep parsing strict enough to avoid false positives but flexible enough for known Firestore subjects
- if `runId` cannot be parsed, log an error and exit (no Firestore writes)

## LLM request parameters (proposal)

The effective Gemini request config is computed as:
`model defaults` ⟶ overridden by `prompt config` ⟶ overridden by `step.inputs.llm` overrides.

Recommended parameters to support:

- `model` / `modelName` (selected by `modelId`)
- `temperature`
- `topP`
- `topK`
- `maxOutputTokens`
- `stopSequences`
- `candidateCount` (if supported)
- `responseMimeType` (prefer `application/json` for structured output)
- `responseSchema` / `jsonSchema` (when using structured output)
- `safetySettings` (policy-driven defaults, optionally overrideable)

Structured output implementation note:
- If using the `google-genai` Python SDK, configure JSON output with `response_mime_type="application/json"` and provide a schema via `response_json_schema` (often generated from Pydantic).

## Execution metadata persisted to Firestore (proposal)

Persist under `steps.<stepId>.outputs` (or `steps.<stepId>.outputs.execution`):

- `artifact`:
  - `gcs_uri`
  - optional `contentType` (`application/json`, `text/markdown`)
  - optional `sha256`/`md5`
- `llm`:
  - `finishReason`
  - `modelVersion` (if available)
  - `usageMetadata` (token counts; at minimum `promptTokenCount` and `totalTokenCount`, plus optional `thoughtsTokenCount`)
  - `requestId` / `operationId` (if available; for correlation)
  - optional `safety` (safety ratings/blocks, if available)
- `timing`:
  - `startedAt`, `finishedAt`, `durationMs`
- `errors` (if failed):
  - `code`, `message` (sanitized), `retryable`

### Prototype note: “only last status + last error”

Prototype guidance suggests keeping `flow_run` minimal: store only the current status and the last error, and rely on Cloud Logging for detailed troubleshooting.

Decision (2025-12-24): persist **extended** LLM execution metadata in `flow_run` (tokens/finishReason/safety/requestId/latency, etc.) in addition to logs.

## Implementation conventions (Python)

These conventions are not part of the runtime contract, but they help keep the worker implementation consistent and maintainable.

### Code style

- Follow PEP 8
- Use type hints for all function signatures
- Prefer max line length 100
- Naming:
  - `snake_case` for functions/variables
  - `PascalCase` for classes
  - `UPPERCASE` for constants

### Docstrings

- Public functions/classes: docstrings required
- Prefer Google-style docstrings (`Args/Returns/Raises`)

### Error handling

- Avoid bare `except`; catch specific exception types where possible
- Normalize exceptions into stable `error.code` values (see `spec/error_and_retry_model.md`)
- Keep error messages sanitized (no secrets, no full prompt/context payloads)

### Logging

- Use module-level logger (`logging.getLogger(__name__)`)
- Prefer structured JSON logs with the contract from `spec/observability.md`
- Avoid logging full request payloads; log summaries/hashes/URIs instead

## Edge cases

### Claim conflict (concurrency)

If Firestore precondition fails during `READY → RUNNING`:
- treat as a benign race
- retry a few times with short jitter (do not use a Firestore transaction)
- if still failing, exit (next invocation will pick it up)

### Dependency graph inconsistencies

If `dependsOn` contains unknown step IDs:
- do not execute
- mark step `FAILED` only if this is considered a configuration error for the flow (decision pending)

### Step already completed

If a step is not `READY` (e.g., already `RUNNING/SUCCEEDED/FAILED`), the worker must not modify it.

### Output write succeeded but Firestore update failed

If the artifact is written to GCS but the final Firestore patch fails:
- the next invocation should be able to detect/reuse the existing artifact by deterministic object name (or by checking for an existing `gcs_uri` in outputs)

### Structured output mismatch

If Gemini returns invalid JSON / violates the expected schema:
- treat as a model-output error
- decide whether to retry with a repair prompt or mark step `FAILED` (open question)
