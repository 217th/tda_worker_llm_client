# LLM schema registry (`llm_schemas/{schemaId}`)

Purpose: store large structured-output JSON Schemas separately from prompt docs so they are easy to inspect and troubleshoot.

## Collection

- Firestore collection: `llm_schemas`
- Document ID: `schemaId` (storage-safe, immutable, versioned by convention)

Canonical schema:
- machine-readable: `contracts/llm_schema.schema.json`
- example: `contracts/examples/llm_schema.example.json`

## Immutability / versioning (MVP)

- Treat each schema doc as **immutable**.
- Changes create a new `schemaId` (e.g., `llm_report_output_v1`, `llm_report_output_v2`).
- Naming convention (MVP): `llm_report_output_v{N}` where `N` matches the report artifact `metadata.schemaVersion` written by the worker.

## Usage (MVP)

Steps reference the schema via `steps.<stepId>.inputs.llm.llmProfile.structuredOutput.schemaId`.

The worker:
- loads the schema doc by `schemaId`
- validates it is present and usable for the selected provider/model
- passes `jsonSchema` into the Gemini generation config

Troubleshooting:
- always log and persist `schemaId` + `schemaSha256` (and never the raw output payload)
