# Contracts

Place machine-readable schemas here (JSON Schema recommended):
- inputs
- outputs
- events
- error payloads

Also keep a human-readable explanation of key fields and versioning rules.

## Files

- `flow_run.schema.json`: Canonical JSON Schema for Firestore document `flow_runs/{runId}` used by this worker.
- `flow_run.md`: Human-readable semantics for key fields and lifecycle rules.
- `llm_prompt.schema.json`: Canonical JSON Schema for Firestore document `llm_prompts/{promptId}` (MVP: `systemInstruction` + `userPrompt` texts only).
- `llm_prompt.md`: Human-readable semantics for prompt docs (version-in-id, UserInput assembly notes).
- `llm_schema.schema.json`: Canonical JSON Schema for Firestore document `llm_schemas/{schemaId}` (structured output schema registry).
- `llm_schema.md`: Human-readable semantics for schema registry docs (immutability/versioning, usage from `llmProfile`).
- `llm_report_file.schema.json`: Canonical JSON Schema for the LLM report JSON file written to GCS.
- `examples/flow_run.example.json`: Example `flow_runs/{runId}` document.
- `examples/llm_prompt.example.json`: Example `llm_prompts/{promptId}` document.
- `examples/llm_schema.example.json`: Example `llm_schemas/{schemaId}` document.
- `examples/llm_report_file.example.json`: Example LLM report file.

## Versioning rules (draft)

- Contract changes must be backward-compatible unless a new `schemaVersion` is introduced and the worker supports both.
- Keep examples in sync with schema changes.
