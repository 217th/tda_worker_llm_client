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
  - `inputs.llm.llmProfile.responseMimeType`: should be `application/json`
  - `inputs.llm.llmProfile.structuredOutput.schemaId`: references `llm_schemas/{schemaId}` (the schema validates only `LLMReportFile.output`; `LLMReportFile.metadata` is worker-owned)
  - `inputs.llm.llmProfile.candidateCount`: if provided, must be `1` (deterministic behavior)
- `inputs.ohlcvStepId`: stepId of an `OHLCV_EXPORT` step; worker resolves `steps[ohlcvStepId].outputs.gcs_uri`.
- `inputs.chartsManifestStepId`: stepId of a `CHART_EXPORT` step; worker resolves `steps[chartsManifestStepId].outputs.gcs_uri` (charts manifest JSON).
- optional `inputs.previousReportStepIds`: stepIds of previous `LLM_REPORT` steps whose report artifacts may be included as context.

Outputs (minimum on success):
- `outputs.gcs_uri`: GCS URI for the final report artifact written by the worker.

Execution metadata is stored alongside outputs (exact structure is defined in `spec/implementation_contract.md` and may evolve).
