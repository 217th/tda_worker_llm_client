# Implementation contract (black-box behavior)

## Scope and responsibilities

**Component:** `worker_llm_client` (Trading Decision Assistant)

Primary responsibility: execute workflow steps of `stepType=LLM_REPORT` for a given `flow_runs/{runId}`.

The worker must:
- be triggered by Firestore document update events for `flow_runs/{runId}`
- select an executable step (`READY`, dependencies satisfied)
- claim it atomically (`READY → RUNNING`) using Firestore optimistic update precondition (`update_time`)
- perform a Gemini request using instructions stored in Firestore (by `promptId`) and an **effective request profile** provided by `inputs.llm.llmProfile`
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
  - `llmProfile` (effective model + request config; authoritative; no overrides)
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

Exact schemas are to be finalized.

## Validation policy (MVP)

The worker must tolerate extra fields beyond the canonical JSON Schemas (prototype reality).

Rules:
- do not reject `flow_runs/{runId}` for unknown/extra fields
- validate only the subset required for this worker’s behavior (run status, step graph, `LLM_REPORT` inputs, and referenced `outputs.gcs_uri`)
- treat missing required fields / wrong types in the required subset as `FLOW_RUN_INVALID` (run-level) or `INVALID_STEP_INPUTS` (step-level), depending on where the violation occurs

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
   - patch `steps.<stepId>.outputs.execution.timing.startedAt = now()`
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

### Firestore step claim/finalize (recommended implementation)

This section is a concrete “by analogy” blueprint for `READY → RUNNING → SUCCEEDED/FAILED` using Firestore optimistic preconditions (no transactions).

#### Preconditions + patch shape

- The worker must **read the document before each write**, and use the document `update_time` as an optimistic precondition for `doc_ref.update(...)`.
- Firestore nested updates are performed via dotted field paths like `steps.<stepId>.status`.
  - Therefore, `stepId` must be **storage-safe** and must not contain `.` or `/` (see the `stepId` storage-safe decision in `questions/open_questions.md`). If a selected `stepId` violates this, treat the run as invalid for this worker (`FLOW_RUN_INVALID`) and do not attempt to patch.

Claim patch (minimal):
- `steps.<stepId>.status = RUNNING`
- `steps.<stepId>.outputs.execution.timing.startedAt = now()`

Finalize patch (success; minimal):
- `steps.<stepId>.status = SUCCEEDED`
- `steps.<stepId>.finishedAt = now()`
- `steps.<stepId>.outputs.gcs_uri = <gs://...>`
- `steps.<stepId>.outputs.execution = {...}` (timing + llm metadata + attempts)

Finalize patch (failure; minimal):
- `steps.<stepId>.status = FAILED`
- `steps.<stepId>.finishedAt = now()`
- `steps.<stepId>.error = {code, message, details?}` (sanitized)
- `steps.<stepId>.outputs.execution = {...}` (timing + partial metadata when available)

#### Reference code (Python; illustrative)

```py
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping, Literal


@dataclass(frozen=True, slots=True)
class ClaimResult:
    claimed: bool
    status: str | None
    reason: str | None = None  # not_ready|precondition_failed


@dataclass(frozen=True, slots=True)
class FinalizeResult:
    updated: bool
    status: str | None
    reason: str | None = None  # already_final|not_running|precondition_failed


def _get_step_status(flow_run: Mapping[str, Any], step_id: str) -> str | None:
    steps = flow_run.get("steps")
    if not isinstance(steps, Mapping):
        return None
    step = steps.get(step_id)
    if not isinstance(step, Mapping):
        return None
    status = step.get("status")
    return status if isinstance(status, str) else None


def _build_step_update(step_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
    # Requires storage-safe stepId (no '.'), because Firestore uses '.' as a path separator.
    return {f"steps.{step_id}.{key}": value for key, value in updates.items()}


def _is_precondition_or_aborted(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gax

        return isinstance(exc, (gax.FailedPrecondition, gax.Conflict, gax.Aborted))
    except Exception:
        return exc.__class__.__name__ in ("FailedPrecondition", "Conflict", "Aborted")


def claim_step(
    *,
    firestore_client: Any,
    flow_runs_collection: str,
    run_id: str,
    step_id: str,
    started_at_rfc3339: str,
) -> ClaimResult:
    doc_ref = firestore_client.collection(flow_runs_collection).document(run_id)
    max_attempts = 3
    base_backoff_seconds = 0.2

    last_status: str | None = None
    for attempt in range(max_attempts):
        snapshot = doc_ref.get()
        flow_run = snapshot.to_dict() if snapshot is not None else None
        flow_run = flow_run if isinstance(flow_run, dict) else {}

        status = _get_step_status(flow_run, step_id)
        last_status = status
        if status != "READY":
            return ClaimResult(claimed=False, status=status, reason="not_ready")

        update = _build_step_update(
            step_id,
            {
                "status": "RUNNING",
                "outputs.execution.timing.startedAt": started_at_rfc3339,
            },
        )
        try:
            update_time = getattr(snapshot, "update_time", None)
            if update_time is not None and hasattr(firestore_client, "write_option"):
                option = firestore_client.write_option(last_update_time=update_time)
                doc_ref.update(update, option=option)
            else:
                doc_ref.update(update)
            return ClaimResult(claimed=True, status=status)
        except Exception as exc:
            if _is_precondition_or_aborted(exc):
                if attempt < max_attempts - 1:
                    time.sleep(base_backoff_seconds * (2**attempt))
                    continue
                return ClaimResult(claimed=False, status=last_status, reason="precondition_failed")
            raise

    return ClaimResult(claimed=False, status=last_status, reason="precondition_failed")


def finalize_step(
    *,
    firestore_client: Any,
    flow_runs_collection: str,
    run_id: str,
    step_id: str,
    status: Literal["SUCCEEDED", "FAILED"],
    finished_at_rfc3339: str,
    outputs_gcs_uri: str | None = None,
    execution: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> FinalizeResult:
    doc_ref = firestore_client.collection(flow_runs_collection).document(run_id)
    max_attempts = 3
    base_backoff_seconds = 0.2

    last_status: str | None = None
    for attempt in range(max_attempts):
        snapshot = doc_ref.get()
        flow_run = snapshot.to_dict() if snapshot is not None else None
        flow_run = flow_run if isinstance(flow_run, dict) else {}

        current_status = _get_step_status(flow_run, step_id)
        last_status = current_status
        if current_status in ("SUCCEEDED", "FAILED"):
            return FinalizeResult(updated=False, status=current_status, reason="already_final")
        if current_status != "RUNNING":
            return FinalizeResult(updated=False, status=current_status, reason="not_running")

        updates: dict[str, Any] = {"status": status, "finishedAt": finished_at_rfc3339}
        if outputs_gcs_uri is not None:
            updates["outputs.gcs_uri"] = outputs_gcs_uri
        if execution is not None:
            updates["outputs.execution"] = execution
        if error is not None:
            updates["error"] = error

        update = _build_step_update(step_id, updates)
        try:
            update_time = getattr(snapshot, "update_time", None)
            if update_time is not None and hasattr(firestore_client, "write_option"):
                option = firestore_client.write_option(last_update_time=update_time)
                doc_ref.update(update, option=option)
            else:
                doc_ref.update(update)
            return FinalizeResult(updated=True, status=current_status)
        except Exception as exc:
            if _is_precondition_or_aborted(exc):
                if attempt < max_attempts - 1:
                    time.sleep(base_backoff_seconds * (2**attempt))
                    continue
                return FinalizeResult(updated=False, status=last_status, reason="precondition_failed")
            raise

    return FinalizeResult(updated=False, status=last_status, reason="precondition_failed")
```

Notes:
- The worker should treat `ClaimResult(reason=precondition_failed)` as a normal race (`STEP_CLAIM_CONFLICT`) and exit without side effects.
- The worker should treat `FinalizeResult(reason=already_final)` as a normal race (`STEP_FINALIZE_CONFLICT`) and exit without overwriting.
- Any error details persisted into `steps.<stepId>.error.details` must be safe (no secrets; no raw prompt/context; no raw model output).

### Output artifact format (canonical)

The worker writes a single JSON file to GCS for the report. Canonical schema:
- `contracts/llm_report_file.schema.json`

Notes:
- the JSON includes `output.summary.markdown` (human-readable) and a flexible `output.details` object
- the worker should embed enough `metadata` to make the file self-describing (runId/stepId/symbol/timeframe/promptId/modelName + input URIs + finish metadata like modelVersion/finishReason/usage)

### Context artifact ingestion (policy)

For JSON context artifacts (OHLCV, charts manifest, previous reports):
- worker downloads objects from GCS and injects the content as text into the prompt (or as a dedicated text-part, depending on the SDK).
- apply a hard size limit per JSON artifact: `maxContextBytesPerJsonArtifact = 64KB`; if exceeded, fail the step with `INVALID_STEP_INPUTS` (contract violation / too-large context).

For image artifacts (charts):
- preferred: pass as inline bytes (file/data parts) in the LLM request (e.g., PNG bytes) when supported by the chosen SDK/endpoint.
- also add a short text description per chart into the generated `UserInput` section (preferred source: chart description copied into charts manifest during export).
- apply a hard size limit per chart image: `maxChartImageBytes = 256KB`; if exceeded, fail the step with `INVALID_STEP_INPUTS` (contract violation / image too large).

Prompt assembly note:
- `llm_prompts/{promptId}` stores `systemInstruction` + a base `userPrompt` text.
- the worker appends a generated **UserInput** section describing and including resolved inputs (see `spec/prompt_storage_and_context.md`).

### Artifact naming (decision)

- Group artifacts by `runId` and use deterministic names derived from stable identifiers.
- Canonical JSON artifact path (OHLCV / charts manifest / LLM report):
  - `<ARTIFACTS_PREFIX>/<runId>/<timeframe>/<stepId>.json`
- Do not include `attempt` or non-deterministic timestamps in JSON object names.

Invariant:
- `steps[stepId].timeframe` must match both the `<timeframe>` path segment and the `<timeframe>` embedded in `stepId` (if present).

## CloudEvent parsing (runId extraction)

Observed CloudEvent `subject` pattern (gen2/Eventarc):
- `documents/<FLOW_RUNS_COLLECTION>/<runId>` (default: `documents/flow_runs/<runId>`)

Worker derives `runId` from CloudEvent `subject` by:
1) splitting `subject` by `/`
2) finding the segment equal to `<FLOW_RUNS_COLLECTION>` (default `flow_runs`)
3) taking the next segment as `runId`
4) validating `runId` against `contracts/flow_run.schema.json` (`runId` pattern)

Notes:
- `cloud_event_received` must include `eventType` and `subject` in logs (see `spec/observability.md`)
- if `subject` cannot be parsed or `runId` fails validation, emit `cloud_event_ignored` with `reason=invalid_subject` and exit (no Firestore writes)

## LLM request parameters (decision)

The effective Gemini request config is taken from `steps.<stepId>.inputs.llm.llmProfile`.

Override policy:
- `llmProfile` is **authoritative** for the request.
- The worker does **not** merge/override it from prompt defaults or model defaults.

Supported parameter allowlist (Gemini API; map to the chosen SDK):

- `model` / `modelName`
- `temperature`
- `topP`
- `topK`
- `maxOutputTokens`
- `stopSequences`
- `candidateCount` (if supported)
- `responseMimeType` (prefer `application/json` for structured output)
- `structuredOutput.schemaId` (preferred; references `llm_schemas/{schemaId}`)
- `responseSchema` / `jsonSchema` (discouraged for MVP; large schemas should live in the registry)
- `thinkingConfig`: `includeThoughts`, `thinkingLevel`

Structured output implementation note:
- If using the `google-genai` Python SDK, configure JSON output with `response_mime_type="application/json"` and provide a schema via `response_json_schema` (MVP: sourced from `llm_schemas/{schemaId}.jsonSchema`).
- MVP requires deterministic single-candidate behavior: `candidateCount=1`. If the step `llmProfile` specifies a different value (when supported), treat as `LLM_PROFILE_INVALID` (do not override).
- Schema boundary (MVP): the provider schema validates only the model-owned `LLMReportFile.output`. The worker builds the final `LLMReportFile` by combining worker-owned `metadata` + model-owned `output`.
- Schema registry (MVP): when `structuredOutput.schemaId` is present, the worker loads `llm_schemas/{schemaId}` and uses its `jsonSchema` as the provider response schema; persist/log `llm.schemaId` + `llm.schemaSha256` and treat missing/invalid/unsupported schema as `LLM_PROFILE_INVALID`.
  - Schema minimal invariants (MVP): for `kind=LLM_REPORT_OUTPUT`, the schema must require `output.summary.markdown` (and `output.details`), otherwise treat as `LLM_PROFILE_INVALID` (pre-flight failure; do not call Gemini).
- `inputs.llm.llmProfile.structuredOutput.schemaSha256` (if present) is informational-only in MVP (loggable, but not enforced; mismatches must not cause failure).
- For `stepType=LLM_REPORT`, if `llmProfile.responseMimeType` is not `application/json`, treat as `LLM_PROFILE_INVALID` (no markdown-only fallback).

## Timeout policy (MVP)

Goal: allow up to **10 minutes** for a single Gemini call, while guaranteeing time to finalize the step (write artifact + patch Firestore).

Recommended defaults:
- Cloud Function timeout (deployment): `780s` (13 minutes)
- Gemini request deadline: `600s` (10 minutes)
- Finalize budget: `120s` reserved for:
  - writing the artifact to GCS (or handling write failure)
  - patching `steps.<stepId>.outputs.*`, `steps.<stepId>.error` (if any), and step status

Guardrail:
- if remaining invocation time is less than `finalizeBudgetSeconds`, the worker must not start new external calls (especially Gemini) and should proceed to finalize the step as `FAILED` with an appropriate error code.

Suggested per-call timeouts (upper bounds; retries must still fit into the overall budget):
- Firestore:
  - read flow_run: `10s`
  - claim patch: `10s` (with short claim retries on precondition contention)
  - finalize patch: `15s`
- GCS:
  - download an input artifact (JSON/PNG): `20s` per object
  - upload final report JSON: `60s`

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
  - `attempts.total` (integer): 1 normally; 2 if a structured-output repair attempt was executed
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

### Reuse existing implementations (MVP)

To minimize production issues, implementation should reuse proven code from existing workers via **copy-paste** (no shared library required for MVP):

- Source projects:
  - `worker_chart_export`
  - `worker_ohlcv_export`
- Expected reuse targets (copy-paste + adapt field names to this worker’s contracts):
  - structured logging utilities (`JsonFormatter`/`log_event`-style wrapper) and stable `event` taxonomy aligned with `spec/observability.md`
  - CloudEvent parsing (`subject`/`eventType` handling) and `runId` extraction rules aligned with `spec/system_integration.md`
  - Firestore claim/finalize helpers using optimistic preconditions (`update_time`) and short jittered retries (no transactions)
  - common no-op/ignored reasons (`cloud_event_noop`, `cloud_event_ignored`) and consistent error mapping (`error.code`)

Rule:
- Any copied implementation must be adjusted to match this spec pack’s contracts (schemas, error codes, log fields). If a source worker behaves differently, the spec wins.

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
- For structured output failures, `steps.<stepId>.error.message` should contain only a short sanitized summary (e.g., `kind=json_parse` / `kind=schema_validation` + finishReason), never the raw model output.

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
- mark step `FAILED` as a configuration error (non-retryable), using `error.code=INVALID_STEP_INPUTS`

### Missing upstream artifact references (LLM_REPORT inputs)

For `LLM_REPORT` execution, if any required upstream references are missing or unusable, finalize as `FAILED` with `error.code=INVALID_STEP_INPUTS`:
- `inputs.ohlcvStepId` points to a missing step
- `inputs.chartsManifestStepId` points to a missing step
- referenced steps exist but `steps[...].outputs.gcs_uri` is missing/empty

### Previous report references (LLM_REPORT inputs)

If `inputs.previousReportStepIds[*]` contains any invalid reference, finalize as `FAILED` with `error.code=INVALID_STEP_INPUTS`:
- referenced step does not exist
- referenced step exists but `stepType != LLM_REPORT`
- referenced step exists but `outputs.gcs_uri` is missing/empty

### Step already completed

If a step is not `READY` (e.g., already `RUNNING/SUCCEEDED/FAILED`), the worker must not modify it.

### Output write succeeded but Firestore update failed

If the artifact is written to GCS but the final Firestore patch fails:
- the next invocation must detect the existing deterministic artifact and finalize Firestore without re-calling the LLM

### Split-brain recovery: step is RUNNING but report artifact exists

If `steps.<stepId>.status == RUNNING` and the deterministic report artifact already exists in GCS at the expected path:
- do not call Gemini
- finalize Firestore using the existing `gcs_uri`
- treat this as a normal completion path (idempotent recovery)

### Structured output mismatch

If Gemini returns invalid JSON / violates the expected schema:
- treat as a model-output error: finalize step as `FAILED` with `error.code=INVALID_STRUCTURED_OUTPUT` unless a bounded repair attempt is allowed

#### MVP policy: validation + repair (at most one)

When structured output is enabled (JSON mode + response schema), the worker must implement a deterministic validation pipeline:

1) Extract candidate text (the JSON string) from the provider SDK response.
2) Check provider `finishReason` (if present) and treat incomplete/blocked generations as invalid output.
3) Parse JSON.
4) Validate the parsed JSON against the expected JSON Schema from the registry (`llm_schemas/{schemaId}.jsonSchema`) and the minimal-invariants policy.

##### Candidate text extraction (MVP)

Goal: define a deterministic way to obtain the JSON payload string without fragile “regex extraction”.

Rules:
- MVP requires `candidateCount=1`, so the worker uses only `candidates[0]`.
- Primary method: concatenate all `candidates[0].content.parts[*].text` values in order.
- Do not strip/unwrap code fences; do not attempt to “find JSON inside text” via regex.
- Do not trim/normalize whitespace; hashes/lengths are computed on the exact concatenated UTF-8 bytes.
- Fallback: if there are no `text` parts (or content/parts missing), use `response.text`.
- If the extracted text is still missing/empty: treat as invalid output (`reason.kind=missing_text`) and apply the repair/FAIL policy.

If any of these steps fails:
- Emit `structured_output_invalid` (see `spec/observability.md`) with:
  - `reason.kind` and a sanitized `reason.message`
  - `llm.finishReason` when available
  - safe diagnostics: `diagnostics.textBytes` and `diagnostics.textSha256`
  - policy snapshot: `policy.finalizeBudgetSeconds`, `policy.remainingSeconds`, `policy.repairPlanned`
- Never log the raw candidate text or full validation error dumps.

Repair attempt:
- Allow **at most one** repair attempt (a second Gemini call) within the same invocation.
- Execute it only when remaining invocation time is safely above the `finalizeBudgetSeconds` reserve.
- Log repair boundaries:
  - `structured_output_repair_attempt_started` (include `attempt=1`)
  - `structured_output_repair_attempt_finished` (include `attempt=1`, `status`)

If the repair attempt still fails validation, finalize the step as `FAILED` with `INVALID_STRUCTURED_OUTPUT`.

`finishReason` mapping (MVP):
- if `finishReason == SAFETY`: finalize the step as `FAILED` with `error.code=LLM_SAFETY_BLOCK` (no repair)
- any outcome that results in invalid JSON / schema failure (including truncation like `MAX_TOKENS`) is `INVALID_STRUCTURED_OUTPUT` (repair allowed per policy)

No fallback policy (MVP):
- If structured output is required by the step profile but is unsupported/unavailable for the chosen model/endpoint/SDK, do not fall back to markdown-only generation; finalize the step as `FAILED` with `error.code=LLM_PROFILE_INVALID`.

Failure artifact policy (MVP):
- do not write raw model output to GCS (neither success path logs nor failure artifacts)
- optional: write a standard `llm_report_file` artifact containing only:
  - a short summary markdown saying structured output validation failed
  - `output.details` with safe debug fields (reason kind, finishReason, `textBytes`, `textSha256`, sanitized validation errors)

`output.summary.html` policy (MVP):
- Do not require or generate `output.summary.html`.
- If present in the model output (non-MVP), treat it as optional and do not render it server-side without sanitization.

Model output data safety (MVP):
- Treat raw model output (candidate text / JSON) as sensitive: do not log it and do not persist it on failures.
- Rely on safe diagnostics (hash/len + sanitized validation errors) for troubleshooting.

Schema versioning (MVP):
- The worker writes `metadata.schemaVersion` into the `llm_report_file` artifact (worker-owned).
- `metadata.schemaVersion` represents the version of the model-owned `output` format (structured output schema).
- `llmProfile.structuredOutput.schemaId` must follow `llm_report_output_v{schemaVersion}`; if it does not match this convention or is unparseable, treat as `LLM_PROFILE_INVALID`.

#### Repair prompt contract (MVP)

Definition:
- “Repair” is a **second Gemini call** to regenerate the structured output (it is not a client-side JSON fixer).

Eligibility (in addition to time budget checks):
- repair applies only to structured-output validation failures with:
  - `reason.kind in {missing_text, json_parse, schema_validation}`
- repair does **not** apply to:
  - `finishReason == SAFETY` (handled as `LLM_SAFETY_BLOCK`)

Repair request contents:
- The worker generates the repair prompt in code (not stored in Firestore).
- The worker must reiterate: “return **only JSON** matching the schema; no markdown; no extra text”.
- The worker provides:
  - `schemaId` and the schema (`llm_schemas/{schemaId}.jsonSchema`)
  - the invalidation reason (`reason.kind`) and a sanitized `reason.message`
  - sanitized validation errors (capped; e.g. 10 items)
  - optionally, the previous candidate text **in-memory only** (never logged/persisted)

Result handling:
- if the repair output validates, proceed as a normal success (write standard `llm_report_file`)
- otherwise, finalize as `FAILED` with `INVALID_STRUCTURED_OUTPUT`
