# `flow_runs/{runId}` contract (human-readable)

This document explains the key semantics of `flow_runs/{runId}` beyond the JSON Schema.

Machine-readable schema: `flow_run.schema.json`.

## Top-level fields

- `schemaVersion`: schema version for the document format (integer).
- `runId`: Firestore document ID; used in artifact naming and logging correlation.
- `flowKey`: workflow identifier (often includes version suffix like `_v1`).
- `status`: overall run status (`PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED`).
- `steps`: map of `stepId -> step object` (step IDs are stable within a run).

### `flow_run.status` semantics (prototype)

- `PENDING`: document created, orchestration not started (or no READY step determined yet)
- `RUNNING`: there is at least one `RUNNING` step or there are `READY` steps
- `SUCCEEDED`: all required steps completed successfully
- `FAILED`: at least one step is `FAILED` and the flow policy does not allow continuation
- `CANCELLED`: run cancelled by operator/user

## Step object (common)

Common required fields:
- `stepType`: discriminator for step contract (this worker executes only `LLM_REPORT`).
- `status`: step lifecycle status:
  - `PENDING`: created, not eligible yet
  - `READY`: eligible for execution (dependencies satisfied by the orchestrator)
  - `RUNNING`: claimed/executing
  - `SUCCEEDED`: completed successfully
  - `FAILED`: completed with failure
  - `SKIPPED`: intentionally skipped (does **not** satisfy `dependsOn`)
  - `CANCELLED`: cancelled by orchestrator/user
- `dependsOn`: list of step IDs; all must be `SUCCEEDED` before the step can execute (current requirement).
- `inputs`: step-specific inputs (structure depends on `stepType`).
- `outputs`: step-specific outputs (structure depends on `stepType`).

### `steps[*].status` responsibilities

Prototype orchestration model:
- orchestrator (e.g., `advance_flow`) sets `PENDING → READY` when dependencies are satisfied
- workers perform `READY → RUNNING → SUCCEEDED/FAILED` atomically, and fill `outputs` / `error`
- workers must not set `READY`

## `LLM_REPORT` step (relevant fields)

Inputs (minimum):
- `inputs.llm.promptId`: instruction/prompt document ID in Firestore.
- `inputs.llm.llmProfile`: effective Gemini request profile (model + generation/structured-output knobs). This is **authoritative** for the request and **must not** be overridden by prompt/model defaults.
- For structured output (MVP):
  - `inputs.llm.llmProfile.responseMimeType`: must be `application/json` (otherwise `LLM_PROFILE_INVALID`; no markdown-only fallback for `LLM_REPORT`)
  - `inputs.llm.llmProfile.structuredOutput.schemaId`: references `llm_schemas/{schemaId}` (the schema validates only `LLMReportFile.output`; `LLMReportFile.metadata` is worker-owned)
  - `inputs.llm.llmProfile.structuredOutput.schemaSha256`: optional and informational-only in MVP (loggable, not enforced)
  - `inputs.llm.llmProfile.candidateCount`: if provided, must be `1` (deterministic behavior)
- `inputs.ohlcvStepId`: stepId of an `OHLCV_EXPORT` step; worker resolves `steps[ohlcvStepId].outputs.gcs_uri`.
- `inputs.chartsManifestStepId`: stepId of a `CHART_EXPORT` step; worker resolves `steps[chartsManifestStepId].outputs.gcs_uri` (charts manifest JSON).
- optional `inputs.previousReportStepIds`: stepIds of previous `LLM_REPORT` steps whose report artifacts may be included as context (same workflow). If any referenced step is missing, not `LLM_REPORT`, or missing `outputs.gcs_uri`, the worker must fail the step as `INVALID_STEP_INPUTS`.
- optional `inputs.previousReports`: explicit previous report references (external or same workflow). Each item is an object with:
  - `stepId` (optional): same-workflow `LLM_REPORT` step ID.
  - `gcs_uri` (optional): direct GCS URI of a report artifact (can be from another workflow).
  - If both `stepId` and `gcs_uri` are provided, **`gcs_uri` wins** (stepId ignored).
  - If neither is provided → `INVALID_STEP_INPUTS`.

Outputs (minimum on success):
- `outputs.gcs_uri`: GCS URI for the final report artifact written by the worker.

Execution metadata is stored alongside outputs (exact structure is defined in `spec/implementation_contract.md` and may evolve).

## Validation tolerance (MVP)

Even though `contracts/flow_run.schema.json` is strict, the worker must tolerate extra fields beyond the schema (prototype reality):
- ignore unknown fields and additional properties
- validate only the subset required for execution and safe failure modes

## Required subset for worker validation (MVP)

Run-level required fields (missing/wrong type → `FLOW_RUN_INVALID`):
- `status` (string; must be a known run status)
- `steps` (object/map)
- step IDs must be storage-safe (no `.` or `/`) because Firestore updates use dotted field paths

Step-level required fields for an executable `LLM_REPORT`:
- `stepType` (`LLM_REPORT`)
- `status` (`READY` for selection)
- `dependsOn` (array of step IDs; missing treated as empty)
- `inputs.llm.promptId` (string)
- `inputs.llm.llmProfile` (object; must pass `LLM_PROFILE_INVALID` checks)
- `inputs.ohlcvStepId` and `inputs.chartsManifestStepId` (string; referenced steps must exist with `outputs.gcs_uri`)
- optional `inputs.previousReportStepIds` (if present, each referenced step must be `LLM_REPORT` with `outputs.gcs_uri`)
- optional `inputs.previousReports` (if present, each item must provide `gcs_uri` or a valid `stepId`; invalid items → `INVALID_STEP_INPUTS`)

If a candidate READY step is missing required inputs, the worker fails that step with `INVALID_STEP_INPUTS` (step-level error).
