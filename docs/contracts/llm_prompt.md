# `llm_prompts/{promptId}` contract (human-readable)

This document describes the Firestore prompt document used by `worker_llm_client`.

Machine-readable schema: `contracts/llm_prompt.schema.json`.

## Identity and naming

- Firestore collection: `llm_prompts`
- Document ID: `promptId` (referenced from `steps.<stepId>.inputs.llm.promptId`)
- `promptId` **must** be storage-safe and follow:
  `llm_prompt_<timeframe>_<type>[_<suffix>]_v<major>_<minor>`
  - regex:
    `^llm_prompt_[1-9][0-9]*[A-Za-z]+_(report|reco)(?:_[a-z0-9]{1,24})?_v[1-9][0-9]*_(?:0|[1-9][0-9]*)$`
  - total length: `<= 128`
  - no `/`, `.`, `:`, spaces, unicode
  - do not include file extensions like `.json` in the document ID (extensions are only for exported files)
  - versioning convention (MVP): encode version in the ID: `..._v1_0`, `..._v2_3`, ...

## Required fields

- `schemaVersion`: `1`
- `systemInstruction`: system instruction text (string)
- `userPrompt`: user prompt text (string)

## User prompt assembly (UserInput)

`userPrompt` stored in Firestore is **not** the full final prompt.

The worker builds the final user content as:

1) take `userPrompt` as-is (no templating in MVP)
2) append XML-tagged context blocks for OHLCV, charts (image descriptions), and any previous reports,
   followed by a `<task>` instruction block.

See `spec/prompt_storage_and_context.md` for the exact assembly rules and size limits.

## Structured output schema (where it belongs)

The structured output schema (if used) is part of the **effective request config**, so it lives in:
- `steps.<stepId>.inputs.llm.llmProfile` (authoritative)

Prompt docs do not store any input/output schemas in MVP.
