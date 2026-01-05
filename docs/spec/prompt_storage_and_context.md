# Prompt storage and context injection

This document fixes the MVP rules for:
- where prompt instructions are stored (`llm_prompts/{promptId}`)
- how prompt templates are rendered
- how the worker injects context artifacts (OHLCV, charts, previous reports)
- how `flow_run.scope` is exposed to the prompt

## 1) Prompt storage (Firestore)

Collection: `llm_prompts`

- Document ID = `promptId` referenced from `steps.<stepId>.inputs.llm.promptId`
- `promptId` must match:
  `^llm_prompt_[1-9][0-9]*[A-Za-z]+_(report|reco)(?:_[a-z0-9]{1,24})?_v[1-9][0-9]*_(?:0|[1-9][0-9]*)$`

Canonical prompt document schema:
- `contracts/llm_prompt.schema.json`
- `contracts/llm_prompt.md`

### Required fields (MVP)

- `schemaVersion` = 1
- `systemInstruction` (string)
- `userPrompt` (string; **does not include UserInput**)

### Versioning rules (MVP)

- Version is encoded into `promptId` by convention: `..._v1_0`, `..._v2_3`, ...
- The worker treats `promptId` as immutable and does not attempt to resolve aliases.

## 2) Templating (MVP)

No templating in MVP:
- `systemInstruction` and `userPrompt` are used as-is.
- All dynamic artifacts (OHLCV, charts, previous reports) are provided via the generated `UserInput` section.

## 3) Context injection policy (MVP)

Baseline policy:
- The worker downloads all required artifacts from GCS itself (using `gs://...` URIs).
- The worker does **not** rely on the LLM downloading arbitrary HTTP(s) URLs.

### JSON artifacts (OHLCV, charts manifest, previous reports)

Default mechanism:
- download the JSON from GCS
- inject OHLCV + previous reports inside XML `<context>` blocks (payload goes into `<content>` as JSON)
- charts manifest JSON is **not** injected directly; it is used to find images + descriptions

Hard limits (per artifact):
- JSON: `maxContextBytesPerJsonArtifact = 65536` (64 KB)
- if exceeded: fail the step with `INVALID_STEP_INPUTS` (context too large)

Rationale:
- prevents runaway token costs and request rejection due to size
- keeps behavior deterministic and observable

Previous reports:
- Same-workflow reports can be referenced via `inputs.previousReportStepIds`.
- External reports can be referenced via `inputs.previousReports[].gcs_uri`.
- If both `stepId` and `gcs_uri` are provided for a `previousReports` entry, `gcs_uri` takes precedence.

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

1) use `userPrompt` as-is (no templating in MVP)
2) append:

```
<context>
  <data_type><timeframe> OHLCV Candles (JSON)</data_type>
  <content>
    <downloaded OHLCV JSON data payload>
  </content>
</context>

<context>
  <data_type>Technical Charts (Images)</data_type>
  <content>
    [Images attached to this message with description]
    - <chart description>
    - ...
  </content>
</context>

<context>
  <data_type>Previous Report (<label>, uri: <gs://...>) (JSON)</data_type>
  <content>
    <report JSON payload>
  </content>
</context>

<task>
Based on the context above, perform the analysis for `symbol`, `timeframe` defined in the System Instructions.
Generate the full report in JSON.
</task>
```

Notes:
- The OHLCV context embeds the JSON payload (normalized) and uses the step timeframe in `data_type`.
- The charts context lists image descriptions derived from the manifest.
- The previous reports context is included once per report (label = stepId or `external`).

## 5) `scope` integration (MVP)

Decision:
- `flow_run.scope` is **not** injected into the `UserInput` text; prompts should define `symbol`/`timeframe` in System Instructions.
- Flows and step inputs do **not** need to re-pass scope fields through `steps[*].inputs.*` unless a step needs a scope override.

In particular:
- symbol is taken from `flow_run.scope.symbol`
- timeframe is taken from `steps.<stepId>.timeframe`
