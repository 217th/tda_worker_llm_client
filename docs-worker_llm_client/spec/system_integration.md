# System integration

Describe how this service integrates into the larger system:
- upstream/downstream services
- contracts, schemas, events
- idempotency / ordering / delivery guarantees

## System context (Trading Decision Assistant)

TDA uses **workflows** represented by Firestore documents `flow_runs/{runId}`. Each flow run contains a set of steps; each step can produce artifacts used by later steps.

This component (`worker_llm_client`) handles only steps that require an external LLM call.

## Orchestration responsibilities (prototype alignment)

Prototype assumes an explicit orchestration function (e.g., `advance_flow`) that reacts to updates of `flow_runs/{runId}` and:
- computes which steps became executable (all `dependsOn` are `SUCCEEDED`)
- transitions steps `PENDING → READY`
- applies run-level policy (e.g., whether a failed step fails the whole run or allows branching / skipping)

This worker assumes:
- `READY` is the primary signal that a step is eligible to execute
- the worker still verifies `dependsOn` as a safety guard (no silent execution on malformed runs)

## Inbound interfaces

### Firestore trigger

- Trigger: Firestore **document update** events on `flow_runs/{runId}`.
- CloudEvent handling:
  - parse `runId` from `subject` (exact subject format is an open question; see `questions/open_questions.md`)
  - fetch `flow_runs/{runId}` from Firestore even if the event carries document data (treat Firestore as source of truth)

## Data contracts

- Firestore `flow_runs/{runId}` JSON Schema: `contracts/flow_run.schema.json`
- LLM report file JSON Schema (canonical): `contracts/llm_report_file.schema.json`
- Example `flow_runs/{runId}` document: `contracts/examples/flow_run.example.json`

## Prompt / instruction storage (Firestore)

The LLM step references instructions via `steps.<stepId>.inputs.llm.promptId` and the model via `steps.<stepId>.inputs.llm.modelId`.

Draft proposal (collections; names are configurable):
- `llm_prompts/{promptId}`:
  - prompt text and templating
  - optional input schema (what context fields are expected)
  - optional output schema (structured output contract)
  - versioning (`promptId` may embed version, e.g. `prompt_month_v1`)
- `llm_models/{modelId}`:
  - provider = `gemini`
  - model name (e.g. `gemini-2.0-flash`, `gemini-2.0-pro`)
  - default generation config (temperature, max tokens, etc.)
  - safety settings / policy defaults

Exact document schemas and versioning rules are open questions.

## Outbound interfaces

### Google Gemini (LLM)

The worker sends:
- resolved prompt/instructions from Firestore
- resolved model config (and per-step overrides)
- context pointers and/or embedded context (OHLCV + charts manifest + previous reports), depending on the prompt design

The worker receives:
- generated text or structured JSON
- model/usage metadata (tokens, finish reason, safety)

### Cloud Storage artifacts

The worker writes the final report artifact to GCS and persists its URI into:
- `steps.<stepId>.outputs.gcs_uri`

Artifact naming scheme (decision):
- use one deterministic path derived from `runId + stepId`
- do not include `attempt` or timestamps in the object name
- do not store `signed_url` in Firestore; store only `gcs_uri`

Recommended shape:
- `<ARTIFACTS_PREFIX>/<runId>/<stepId>/report.json`

### Optional indexed metadata collections (future)

Prototype mentions possible future collections to support filtering/revision without migrating `flow_runs/{runId}`:
- `reports/{reportId}`
- `recommendations/{recoId}`

If introduced, `flow_runs/{runId}` steps may store both `reportId/recommendationId` and `gcs_uri`.

## Delivery/ordering/idempotency guarantees

- Firestore update events can be duplicated and reordered; the worker must be **idempotent**.
- Concurrency control uses optimistic preconditions (doc `update_time`) for `READY → RUNNING` claiming.
- If no `READY` LLM step exists, or if dependencies are not satisfied, the worker does a **no-op**.
