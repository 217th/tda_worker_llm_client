# `llm_prompts/{promptId}` contract (human-readable)

This document describes the Firestore prompt document used by `worker_llm_client`.

Machine-readable schema: `contracts/llm_prompt.schema.json`.

## Identity and naming

- Firestore collection: `llm_prompts`
- Document ID: `promptId` (referenced from `steps.<stepId>.inputs.llm.promptId`)
- `promptId` **must** be storage-safe: `^[a-z0-9_]{1,128}$`
  - no `/`, `.`, `:`, spaces, unicode
  - do not include file extensions like `.json` in the document ID (extensions are only for exported files)
  - versioning convention (MVP): encode version in the ID: `..._v1`, `..._v2`, ...

## Required fields

- `schemaVersion`: `1`
- `systemInstruction`: system instruction text (string)
- `userPrompt`: user prompt text (string)

## User prompt assembly (UserInput)

`userPrompt` stored in Firestore is **not** the full final prompt.

The worker builds the final user content as:

1) take `userPrompt` as-is (no templating in MVP)
2) append a generated section named `UserInput` that describes and includes resolved inputs:
   - **Time series input (OHLCV)**: explicitly state symbol + timeframe, then include JSON
   - **Charts (images)**: for each image, add a short text line describing what the chart is
     - preferred: use `description` from the charts manifest (copied from chart_template during chart export)
     - fallback: use `chartTemplateId` if no description is availableclude JSON
   - **Previous reports**: for each previous report, add a short text description (timeframe/stepId), then in

See `spec/prompt_storage_and_context.md` for the exact assembly rules and size limits.

## Structured output schema (where it belongs)

The structured output schema (if used) is part of the **effective request config**, so it lives in:
- `steps.<stepId>.inputs.llm.llmProfile` (authoritative)

Prompt docs do not store any input/output schemas in MVP.
