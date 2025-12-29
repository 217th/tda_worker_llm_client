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
  - observed `subject` pattern (gen2/Eventarc): `documents/<FLOW_RUNS_COLLECTION>/<runId>` (default: `documents/flow_runs/<runId>`)
  - parse `runId` from `subject` by finding the `<FLOW_RUNS_COLLECTION>` path segment and taking the next segment
  - fetch `flow_runs/{runId}` from Firestore even if the event carries document data (treat Firestore as source of truth)

## Data contracts

- Firestore `flow_runs/{runId}` JSON Schema: `contracts/flow_run.schema.json`
- LLM report file JSON Schema (canonical): `contracts/llm_report_file.schema.json`
- LLM schema registry document JSON Schema: `contracts/llm_schema.schema.json`
- Example `flow_runs/{runId}` document: `contracts/examples/flow_run.example.json`

## Prompt / instruction storage (Firestore)

The LLM step references instructions via `steps.<stepId>.inputs.llm.promptId`.

Gemini request parameters are provided via `steps.<stepId>.inputs.llm.llmProfile` (model + generation config + structured output knobs). This profile is **authoritative** for the request and is not overridden by any prompt/model defaults.

Collections (names are configurable; MVP uses Firestore for prompts and schema registry):
- `llm_prompts/{promptId}`: canonical prompt document schema is defined in:
  - machine-readable: `contracts/llm_prompt.schema.json`
  - human-readable notes: `contracts/llm_prompt.md`
  - example: `contracts/examples/llm_prompt.example.json`

- `llm_schemas/{schemaId}`: structured output schema registry (large JSON Schemas):
  - machine-readable: `contracts/llm_schema.schema.json`
  - human-readable notes: `contracts/llm_schema.md`
  - example: `contracts/examples/llm_schema.example.json`

Key rules (MVP decisions):
- `promptId` (Firestore doc ID) must be storage-safe: `^[a-z0-9_]{1,128}$` (no `/`, `.`, `:`, spaces, unicode).
- Versioning is encoded into `promptId` by convention (e.g. `llm_report_1m_v1`).
- Prompt doc stores only **instruction texts** (`systemInstruction`, `userPrompt`). Effective Gemini request config (including structured output schema reference) is taken from `inputs.llm.llmProfile`.
- Structured output schema naming convention: `llmProfile.structuredOutput.schemaId` uses `llm_report_output_v{N}`; the worker writes `metadata.schemaVersion=N` into the report artifact.
- Orchestrator must **pin explicit versions** in `promptId` / `schemaId` (no “latest” resolution in MVP).

Future (optional, post-MVP):
- `llm_profiles/{profileId}`:
  - a reusable server-side stored profile that an orchestrator could copy into `steps[*].inputs.llm.llmProfile`
  - not required for MVP (MVP uses inline `llmProfile` in the step)

See also: `spec/prompt_storage_and_context.md` for context-injection + UserInput assembly rules.

### Firestore seed docs (dev/debug)

To develop and demo Epic 5, seed **at least** these documents in Firestore.

1) `llm_prompts/{promptId}` (valid)
   - Must conform to `contracts/llm_prompt.schema.json` and `contracts/llm_prompt.md`.
   - Required fields: `schemaVersion=1`, `systemInstruction` (string), `userPrompt` (string).
   - Example source: `contracts/examples/llm_prompt.example.json`.

2) `llm_schemas/{schemaId}` (valid)
   - Must conform to `contracts/llm_schema.schema.json` and invariants in `contracts/llm_schema.md`.
   - For `kind=LLM_REPORT_OUTPUT`, the embedded `jsonSchema` must require:
     - top-level `summary` and `details`
     - `summary.markdown` (string)
   - Example source: `contracts/examples/llm_schema.example.json`.

3) `flow_runs/{runId}` (valid)
   - Must conform to `contracts/flow_run.schema.json`.
   - Must contain at least one `LLM_REPORT` step with:
     - `status=READY`
     - `inputs.llm.promptId` referencing the prompt doc above
     - `inputs.llm.llmProfile.structuredOutput.schemaId` referencing the schema doc above
     - `inputs.ohlcvStepId` and `inputs.chartsManifestStepId` referencing steps with `outputs.gcs_uri`
   - Example source: `contracts/examples/flow_run.example.json`.

Negative cases for demo:
- Missing prompt: create a run or step variant that references a non-existent `promptId` → expect `PROMPT_NOT_FOUND`.
- Invalid schema: create a schema doc that violates the invariants above (e.g., missing `summary.markdown`) and reference it → expect `LLM_PROFILE_INVALID`.

### Seed verification checklist

Use one of these methods (console or REST) to confirm documents are present and valid:

- Console: Firestore → locate `llm_prompts`, `llm_schemas`, `flow_runs` and inspect required fields.
- REST (example):
  - `GET https://firestore.googleapis.com/v1/projects/<PROJECT_ID>/databases/<DB_ID>/documents/llm_prompts/<promptId>`
  - `GET https://firestore.googleapis.com/v1/projects/<PROJECT_ID>/databases/<DB_ID>/documents/llm_schemas/<schemaId>`
  - `GET https://firestore.googleapis.com/v1/projects/<PROJECT_ID>/databases/<DB_ID>/documents/flow_runs/<runId>`

Validation rules (quick check):
- Prompt doc: `schemaVersion=1`, `systemInstruction` and `userPrompt` are non-empty strings.
- Schema doc: `schemaVersion=1`, `kind=LLM_REPORT_OUTPUT`, `jsonSchema` present and enforces `summary/details` and `summary.markdown`.
  - `sha256` matches the canonical hash of `jsonSchema` (see `contracts/llm_schema.md`).
- Flow run: `status=RUNNING`, a `READY` LLM step exists and references the prompt/schema IDs above, and referenced steps have `outputs.gcs_uri`.

## Outbound interfaces

### Google Gemini (LLM)

The worker sends:
- resolved prompt/instructions from Firestore
- resolved `llmProfile` (effective request parameters)
- context pointers and/or embedded context (OHLCV + charts manifest + previous reports), depending on the prompt design

The worker receives:
- generated text or structured JSON
- model/usage metadata (tokens, finish reason, safety)

MVP endpoint choice:
- AI Studio (API key auth). Vertex AI (ADC/IAM) may be adopted later for production hardening.
- SDK guidance (2025-12-29): use the Google GenAI Python SDK for the Gemini Developer API.
  - Structured output is supported via `response_mime_type="application/json"` + `response_json_schema`.
  - Image inputs are supported via multipart content (inline image bytes or File API).
  - Vertex AI uses the same SDK with `vertexai=True` plus explicit project/location.
- Constraint note: structured output and image inputs are documented separately; validate the combined
  multimodal + response schema path in Epic 7 (SPK-010).
- Model allowlist (MVP): when `GEMINI_ALLOWED_MODELS` is set, the worker must reject any step whose
  `llmProfile.modelName` (or `model`) is not in the allowlist with `LLM_PROFILE_INVALID`.

### Cloud Storage artifacts

The worker writes the final report artifact to GCS and persists its URI into:
- `steps.<stepId>.outputs.gcs_uri`

Artifact naming scheme (decision):
- group artifacts by `runId` (everything for a run lives under one prefix)
- use deterministic object names derived from stable identifiers (`runId`, `timeframe`, `stepId`)
- do not include `attempt` or non-deterministic timestamps in object names
- do not store `signed_url` in Firestore; store only `gcs_uri`

Canonical shapes:
- JSON artifacts (OHLCV / charts manifest / LLM report):
  - `<ARTIFACTS_PREFIX>/<runId>/<timeframe>/<stepId>.json`
- Charts PNG artifacts (multiple per step):
  - folder: `<ARTIFACTS_PREFIX>/<runId>/<timeframe>/<stepId>/`
  - file: `<ARTIFACTS_PREFIX>/<runId>/<timeframe>/<stepId>/<generatedAt>_<symbolSlug>_<timeframe>_<chartTemplateId>.png`

Invariant:
- `steps[stepId].timeframe` must match both the `<timeframe>` path segment and the `<timeframe>` embedded in `stepId` (if present).

Recommended `stepId` canon (storage-safe):
- `<stepType>_<timeframe>_<slug>_v<major>`
  - `<stepType>` is a short stable token (e.g. `ohlcv`, `charts`, `llm_report`, `llm_recommendation`)
  - `<slug>` is a brief snake_case note (ASCII), must not include symbol

### Optional indexed metadata collections (future)

Prototype mentions possible future collections to support filtering/revision without migrating `flow_runs/{runId}`:
- `reports/{reportId}`
- `recommendations/{recoId}`

If introduced, `flow_runs/{runId}` steps may store both `reportId/recommendationId` and `gcs_uri`.

MVP decision:
- no separate indexing collections; use `flow_run` + GCS only.

## Delivery/ordering/idempotency guarantees

- Firestore update events can be duplicated and reordered; the worker must be **idempotent**.
- Concurrency control uses optimistic preconditions (doc `update_time`) for `READY → RUNNING` claiming.
- If no `READY` LLM step exists, or if dependencies are not satisfied, the worker does a **no-op**.
