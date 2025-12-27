# Error and retry model

## Error taxonomy

Error classes are grouped by retryability and by how they affect the `flow_runs/{runId}` state.

Where errors are persisted:
- step-level errors: `steps.<stepId>.error.code` + `steps.<stepId>.error.message`
- run-level errors (rare): `flow_run.error.*` (only if the whole run is invalid/unrecoverable for all steps)

### 1) Non-retryable (configuration / contract)

- `FLOW_RUN_NOT_FOUND`: `flow_runs/{runId}` does not exist (stale trigger)
- `FLOW_RUN_INVALID`: `flow_run` fails validation for this worker (schema/required fields)
- `PROMPT_NOT_FOUND`: prompt doc missing for `promptId`
- `LLM_PROFILE_INVALID`: missing/invalid `inputs.llm.llmProfile` (model/config not usable)
- `INVALID_STEP_INPUTS`: required inputs missing or unusable (e.g., missing `ohlcvStepId` / `chartsManifestStepId`, missing referenced `steps[...].outputs.gcs_uri`, or invalid `previousReportStepIds` references)
- `LLM_SAFETY_BLOCK`: generation blocked by model/provider safety filters
- `INVALID_STRUCTURED_OUTPUT`: structured output is invalid (JSON parse / schema validation / incomplete payload). MVP: allow at most **one** repair attempt within the same invocation if time budget allows; otherwise finalize as `FAILED`.

Orchestrator note (MVP):
- treat `INVALID_STRUCTURED_OUTPUT` as terminal for automatic runs (no auto re-run with the same step inputs). Manual rerun should create a new run/step identity.

Structured output config note (MVP):
- if structured output is required but unsupported/unavailable for the chosen model/endpoint/SDK → `LLM_PROFILE_INVALID` (non-retryable)
- for `stepType=LLM_REPORT`, if `llmProfile.responseMimeType` is not `application/json` → `LLM_PROFILE_INVALID` (no markdown-only fallback)
- require `candidateCount=1` for deterministic behavior; other values (when specified) → `LLM_PROFILE_INVALID`
- if `structuredOutput.schemaId` is required but missing/unresolvable, or the referenced schema is invalid/unsupported → `LLM_PROFILE_INVALID`
- `structuredOutput.schemaSha256` (if present) is informational-only (loggable, but not enforced)
- if `structuredOutput.schemaId` does not follow `llm_report_output_v{N}` naming (unparseable schema version) → `LLM_PROFILE_INVALID`
- if the referenced structured-output schema does not require `summary.markdown` (and top-level `summary/details`) → `LLM_PROFILE_INVALID`
- validation source of truth: model output is validated against `llm_schemas/{schemaId}.jsonSchema` (single source of truth); do not introduce a second authoritative validator in MVP

### 2) Retryable (transient)

- `FIRESTORE_UNAVAILABLE`: transient Firestore errors (timeouts, 5xx)
- `GCS_WRITE_FAILED`: transient Cloud Storage write errors (timeouts, 5xx)
- `GEMINI_REQUEST_FAILED`: transient model API errors (timeouts, 5xx)
- `RATE_LIMITED`: quota / rate-limit (HTTP 429 / RESOURCE_EXHAUSTED)

### 3) Concurrency / benign conflicts

- `STEP_CLAIM_CONFLICT`: Firestore precondition failed during claim (expected under race)
- `STEP_FINALIZE_CONFLICT`: step is already finalized by another invocation (treat as no-op)

## Domain error codes (stable set proposal)

These are values for `steps.<stepId>.error.code` (and occasionally for `flow_run.error.code`).

Common / infrastructure:
- `FLOW_RUN_NOT_FOUND`
- `FLOW_RUN_INVALID`
- `FIRESTORE_CLAIM_FAILED` (unexpected error during `READY → RUNNING` claim, not a precondition conflict)
- `FIRESTORE_FINALIZE_FAILED` (unexpected error during final patch to `SUCCEEDED/FAILED`)
- `GCS_WRITE_FAILED`

LLM-specific (`stepType=LLM_REPORT`):
- `PROMPT_NOT_FOUND`
- `LLM_PROFILE_INVALID`
- `GEMINI_REQUEST_FAILED`
- `RATE_LIMITED`
- `LLM_SAFETY_BLOCK`
- `INVALID_STRUCTURED_OUTPUT`

No-op / not a failure (should not set `error` field):
- `NO_READY_STEP` (trigger received but nothing executable)
- `DEPENDENCY_NOT_SUCCEEDED` (dependencies not satisfied)
- `STEP_CLAIM_CONFLICT` / `STEP_FINALIZE_CONFLICT` (expected races)

## Retry / backoff / rate limiting

### Step claim retries (short, no transactions)

For `READY → RUNNING` claim:
- max retries: 3–5
- delay: 100–500ms with jitter
- reason: reduce Firestore contention while keeping function latency low

If claim conflicts persist, exit without changing the step.

### External calls

For Firestore/GCS/Gemini transient failures:
- exponential backoff with jitter (example parameters below)
- cap overall step execution time to stay within Cloud Functions timeout
- do not retry indefinitely; failure should mark the step `FAILED` with an error code

MVP timeout constraints:
- Gemini request deadline is `600s` (10 minutes). Cloud Function timeout is `780s` (13 minutes) with `FINALIZE_BUDGET_SECONDS=120`.
- Because the Gemini call can take most of the invocation budget, default `maxGeminiAttempts=1` (no full retry loops).
  - Repair policy (MVP): if structured output validation fails, allow `maxRepairAttempts=1` **only** when remaining invocation time is safely above `finalizeBudgetSeconds` (see `spec/implementation_contract.md`). Repair is a bounded recovery step inside the same invocation, not a “Gemini retry loop”.

Reference-style retry parameters (suggested defaults):
- attempts: 5
- base delay: 1s
- factor: 2
- max delay: 32s

Implementation hint: `tenacity` is a good fit in Python for this policy.

### Rate limiting

If Gemini returns rate limiting:
- apply backoff
- optionally cap concurrent executions per function instance (in-process semaphore) (implementation detail)

## Partial failures (split-brain cases)

Recommended handling patterns, aligned with deterministic artifacts + at-least-once finalization:

### 1) GCS write OK, Firestore finalize FAIL

Symptoms:
- object exists in GCS (deterministic path), but step is still `RUNNING` or missing `outputs.gcs_uri`.

Handling:
- retry the finalize patch a few times within the invocation
- if still failing: let the invocation fail (so the event can be retried if retries are enabled) OR rely on the next Firestore update invocation to finalize
- next invocation must detect the existing object and finalize without re-calling the LLM

### 2) Claim OK, crash before side effects

Symptoms:
- step stuck in `RUNNING` with no outputs.

Handling:
- define a recovery policy outside this worker:
  - lease/TTL-based reset from `RUNNING → READY` (or `FAILED`) after `startedAt + ttl`
  - or a dedicated “reaper” job / orchestrator logic

### 3) External call succeeded, artifact write failed

Handling:
- retry only the failing part (GCS write) with backoff
- if still failing: mark step `FAILED` with `GCS_WRITE_FAILED`

## Firestore contention notes (409 ABORTED)

In similar workers, Firestore transactions (and sometimes high-frequency updates) can lead to:
- `Aborted (409) Too much contention on these documents`

Recommended patterns:
- avoid Firestore transactions on `flow_runs/{runId}`
- use optimistic updates with `last_update_time` preconditions and short retries
- keep patches minimal (write only the fields needed for claim/finalize)

## Idempotency model

The worker must be safe under duplicated/replayed Firestore update events and partial failures.

Mechanisms:

1. **Optimistic claim**:
   - step execution begins only after `READY → RUNNING` succeeded with `last_update_time` precondition

2. **Deterministic artifact naming**:
   - object name derived from stable identifiers (`runId`, `stepId`)
   - allows retrying without creating multiple outputs

3. **Idempotent GCS write**:
    - prefer “create-only” semantics (GCS precondition `ifGenerationMatch=0`)
    - if object already exists, treat as success and reuse it (deterministic object name; supports split-brain finalize)

4. **At-least-once Firestore patching**:
    - finalization (`RUNNING → SUCCEEDED/FAILED`) may be retried
    - if step is already `SUCCEEDED` with `outputs.gcs_uri`, do not overwrite

## Implementation hint: exception hierarchy (optional)

Even though Cloud Functions gen2 does not use “exit codes”, an internal exception hierarchy helps keep retry decisions consistent.

Example mapping:
- `ConfigurationError` / `ValidationError` → non-retryable (`FLOW_RUN_INVALID`, `INVALID_STEP_INPUTS`)
- `AuthenticationError` → non-retryable (typically `MODEL_NOT_FOUND` / IAM misconfig surfaced as config error)
- `NetworkError` → retryable (`FIRESTORE_UNAVAILABLE`, `GEMINI_REQUEST_FAILED`, `GCS_WRITE_FAILED`)
- `DataNotFoundError` → no-op (missing optional context artifact) or failure depending on the prompt contract (decision TBD)
