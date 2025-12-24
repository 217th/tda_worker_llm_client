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
- `llm_report_file.schema.json`: Canonical JSON Schema for the LLM report JSON file written to GCS.
- `examples/flow_run.example.json`: Example `flow_runs/{runId}` document.
- `examples/llm_report_file.example.json`: Example LLM report file.

## Versioning rules (draft)

- Contract changes must be backward-compatible unless a new `schemaVersion` is introduced and the worker supports both.
- Keep examples in sync with schema changes.
