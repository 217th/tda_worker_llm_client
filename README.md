# `LLM_REPORT` entity hierarchy (contracts + examples)

This repository implements a worker that executes `LLM_REPORT` steps stored in Firestore `flow_runs/{runId}` documents.

This README focuses on the **entity hierarchy** used to describe (and execute) a single `LLM_REPORT` step:
from the `flow_runs/{runId}` document → referenced prompt/schema documents → upstream artifacts → final report artifact.

## 1) High-level hierarchy (data contracts)

```
Firestore: flow_runs/{runId}  (FlowRun document)
└─ steps: { stepId -> step }  (map)
   ├─ <any upstream step>     (e.g., OHLCV_EXPORT / CHART_EXPORT)
   │  └─ outputs.gcs_uri      (GCS artifact pointer)
   └─ <report step>           (stepType=LLM_REPORT)
      ├─ inputs.llm.promptId  -> Firestore: llm_prompts/{promptId}
      ├─ inputs.llm.llmProfile
      │  └─ structuredOutput.schemaId -> Firestore: llm_schemas/{schemaId}
      ├─ inputs.ohlcvStepId            -> steps[ohlcvStepId].outputs.gcs_uri
      ├─ inputs.chartsManifestStepId   -> steps[chartsManifestStepId].outputs.gcs_uri
      ├─ inputs.previousReportStepIds? -> steps[stepId].outputs.gcs_uri (same workflow)
      ├─ inputs.previousReports?       -> gcs_uri (external or same workflow)
      └─ outputs.gcs_uri               -> GCS: LLMReportFile JSON (final artifact)
```

### 1.1 `flow_runs/{runId}` (FlowRun + FlowStep)

`flow_runs/{runId}` is the **aggregate document** that contains the step graph.

- `steps` is a map of `stepId -> step object` (IDs are stable within the run).
- Each step has a common envelope: `stepType`, `status`, `dependsOn`, `inputs`, `outputs`.
- For `LLM_REPORT`, the worker expects upstream step references in inputs (to resolve context artifacts) and writes the final report artifact URI into `outputs.gcs_uri`.

References:
- Schema: `docs/contracts/flow_run.schema.json`
- Human-readable notes: `docs/contracts/flow_run.md`
- Example: `docs/contracts/examples/flow_run.example.json`

### 1.2 `llm_prompts/{promptId}` (LLMPrompt)

`llm_prompts/{promptId}` stores the prompt text pieces used by the worker.

- `systemInstruction`: system instruction string.
- `userPrompt`: the base user prompt; the worker appends an auto-generated `## UserInput` section built from resolved artifacts.
- Prompt docs do **not** contain structured-output schemas in MVP (the schema lives in the step’s effective request profile).

References:
- Schema: `docs/contracts/llm_prompt.schema.json`
- Human-readable notes: `docs/contracts/llm_prompt.md`
- Example: `docs/contracts/examples/llm_prompt.example.json`
- Prompt assembly rules: `docs/spec/prompt_storage_and_context.md`

### 1.3 `llm_schemas/{schemaId}` (LLMSchema)

`llm_schemas/{schemaId}` stores the JSON Schema used for **structured output** (model-owned `output` payload).

- Step inputs reference the schema via `inputs.llm.llmProfile.structuredOutput.schemaId`.
- `kind` is used as a coarse discriminator; for reports the expected kind is `LLM_REPORT_OUTPUT`.
- The worker treats `sha256` as informational-only in MVP (logged/propagated, not enforced).
- Minimal invariants for `kind=LLM_REPORT_OUTPUT` (MVP): require top-level `summary` and `details`, and require `summary.markdown` as a string.

References:
- Schema: `docs/contracts/llm_schema.schema.json`
- Human-readable notes: `docs/contracts/llm_schema.md`
- Example: `docs/contracts/examples/llm_schema.example.json`

### 1.4 GCS report artifact: `LLMReportFile` (written by the worker)

On success, the worker writes a JSON file to `steps.<stepId>.outputs.gcs_uri`.

`LLMReportFile` has two top-level parts:

- `metadata` (worker-owned): run/step identity, timestamps, resolved input artifact URIs, LLM profile snapshot, model finish metadata.
- `output` (model-owned): validated against the JSON Schema stored in `llm_schemas/{schemaId}.jsonSchema` (plus the worker’s minimal invariants policy).

References:
- Schema: `docs/contracts/llm_report_file.schema.json`
- Example: `docs/contracts/examples/llm_report_file.example.json`

## 2) Hierarchy (runtime/domain model in code)

The code mirrors the contracts with a small domain model (MVP):

- Workflow execution:
  - `FlowRun` (aggregate root) and `FlowStep` (generic step) are in `worker_llm_client/workflow/domain.py`.
  - `LLMReportStep` is a typed wrapper for `stepType=LLM_REPORT`.
  - `LLMReportInputs` validates and resolves step references (e.g., turns `ohlcvStepId` into a concrete `gs://...` URI).
- Report generation:
  - `LLMPrompt`, `LLMSchema`, `LLMProfile`, and `LLMReportFile` live under `worker_llm_client/reporting/`.
- Artifacts:
  - `GcsUri` and deterministic artifact naming live under `worker_llm_client/artifacts/`.

Reference (overview + class allocation): `docs/static_model.md`.

## 3) Quick link index (schemas + examples)

- Flow run / steps:
  - `docs/contracts/flow_run.schema.json`
  - `docs/contracts/flow_run.md`
  - `docs/contracts/examples/flow_run.example.json`
  - Test vectors: `docs/test_vectors/inputs/flow_run.ready_llm_report.json`, `docs/test_vectors/inputs/flow_run.ready_llm_report_missing_prompt.json`
- Prompt docs:
  - `docs/contracts/llm_prompt.schema.json`
  - `docs/contracts/llm_prompt.md`
  - `docs/contracts/examples/llm_prompt.example.json`
- Schema registry:
  - `docs/contracts/llm_schema.schema.json`
  - `docs/contracts/llm_schema.md`
  - `docs/contracts/examples/llm_schema.example.json`
- Report artifact:
  - `docs/contracts/llm_report_file.schema.json`
  - `docs/contracts/examples/llm_report_file.example.json`

