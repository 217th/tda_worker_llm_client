# Prompt storage and context injection

This document fixes the MVP rules for:
- where prompt instructions are stored (`llm_prompts/{promptId}`)
- how prompt templates are rendered
- how the worker injects context artifacts (OHLCV, charts, previous reports)
- how `flow_run.scope` is exposed to the prompt

## 1) Prompt storage (Firestore)

Collection: `llm_prompts`

- Document ID = `promptId` referenced from `steps.<stepId>.inputs.llm.promptId`
- `promptId` must match: `^[a-z0-9_]{1,128}$`

Canonical prompt document schema:
- `contracts/llm_prompt.schema.json`
- `contracts/llm_prompt.md`

### Required fields (MVP)

- `schemaVersion` = 1
- `systemInstruction` (string)
- `userPrompt` (string; **does not include UserInput**)

### Versioning rules (MVP)

- Version is encoded into `promptId` by convention: `..._v1`, `..._v2`, ...
- The worker treats `promptId` as immutable and does not attempt to resolve aliases.

## 2) Templating (MVP)

No templating in MVP:
- `systemInstruction` and `userPrompt` are used as-is.
- All dynamic values (symbol/timeframe/URIs/artifacts) are provided via the generated `UserInput` section.

## 3) Context injection policy (MVP)

Baseline policy:
- The worker downloads all required artifacts from GCS itself (using `gs://...` URIs).
- The worker does **not** rely on the LLM downloading arbitrary HTTP(s) URLs.

### JSON artifacts (OHLCV, charts manifest, previous reports)

Default mechanism:
- download the JSON from GCS
- inject as a dedicated **text part** (or plain text appended to user content) inside a fenced block:
  - include the `gs://...` URI and a short description
  - include the JSON text (UTF-8)

Hard limits (per artifact):
- JSON: `maxContextBytesPerJsonArtifact = 65536` (64 KB)
- if exceeded: fail the step with `INVALID_STEP_INPUTS` (context too large)

Rationale:
- prevents runaway token costs and request rejection due to size
- keeps behavior deterministic and observable

### Images (charts)

Preferred mechanism:
- pass images as **inline bytes** (file/data parts) to the LLM request, with correct mime type (e.g. `image/png`)

Hard limits (per image):
- `maxChartImageBytes = 262144` (256 KB)
- if exceeded: fail the step with `INVALID_STEP_INPUTS` (image too large)

The worker also adds a short textual description per image into **UserInput**:
- preferred: use `description` that chart export step stored in the charts manifest (copied from chart_template at generation time)
- fallback: use `chartTemplateId` if no description is available

If the chosen SDK/endpoint cannot send image bytes:
- treat as a configuration error (non-MVP fallback is to embed base64 as text, but this is discouraged due to token bloat)

## 4) UserInput section assembly (MVP)

The prompt doc (`llm_prompts/{promptId}`) stores `userPrompt` **without** UserInput.

The worker builds the final user prompt as:

1) render `userPrompt` template (Mustache context above)
2) append:

```
## UserInput

Symbol: <scope.symbol>
Timeframe: <step.timeframe>

### OHLCV (time series)
Source: <resolved_inputs.ohlcv.gcs_uri>
```json
<downloaded ohlcv JSON>
```

### Charts (images)
- <description 1> (uri: <gs://...>)
- <description 2> (uri: <gs://...>)
...

### Previous reports
<one block per report, if any>
```

Notes:
- The OHLCV section must explicitly state it is a time series and name symbol + timeframe.
- The charts section must list each chart and what it represents (using chart_template description).
- Previous reports must be described (which timeframe/step) before including JSON.

## 5) `scope` integration (MVP)

Decision:
- `flow_run.scope` is injected into the prompt via the generated `UserInput` section (e.g., `Symbol: <scope.symbol>`).
- Flows and step inputs do **not** need to re-pass scope fields through `steps[*].inputs.*` unless a step needs a scope override.

In particular:
- symbol is taken from `flow_run.scope.symbol`
- timeframe is taken from `steps.<stepId>.timeframe`
