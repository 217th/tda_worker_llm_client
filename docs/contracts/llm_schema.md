# LLM schema registry (`llm_schemas/{schemaId}`)

Purpose: store large structured-output JSON Schemas separately from prompt docs so they are easy to inspect and troubleshoot.

Decision (MVP): `llm_schemas/{schemaId}.jsonSchema` is the **single source of truth** for validating the model-owned `output` payload.

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

## SHA-256 policy (MVP)

`llm_schemas/{schemaId}.sha256` is the SHA-256 hex of the **canonical JSON encoding** of `jsonSchema`.

Canonicalization rules (authoring time):
- serialize `jsonSchema` with stable key ordering and no extra whitespace
- UTF-8 bytes are hashed

Reference implementation (Python):

```py
import hashlib, json

def schema_sha256(json_schema: dict) -> str:
    payload = json.dumps(json_schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Policy:
- `sha256` is computed and stored when the schema doc is authored.
- the worker **does not** recompute or enforce the hash in MVP; it logs/propagates it for drift detection.

## Usage (MVP)

Steps reference the schema via `steps.<stepId>.inputs.llm.llmProfile.structuredOutput.schemaId`.

The worker:
- loads the schema doc by `schemaId`
- validates it is present and usable for the selected provider/model
- passes `jsonSchema` into the Gemini generation config

### Minimal invariants for `kind=LLM_REPORT_OUTPUT` (MVP)

To keep downstream consumers stable, the schema must enforce at least:
- top-level required keys: `summary` and `details`
- `summary.markdown` is required and is a string

If the schema does not enforce these invariants, treat it as invalid configuration (`LLM_PROFILE_INVALID`) and do not call Gemini.

### `details` contract (MVP)

- `details` is intentionally **free-form** (`additionalProperties=true`).
- Do not require stable keys inside `details` on MVP.
- If stable machine-readable fields are needed later, introduce them by tightening the structured output schema in a new version (`llm_report_output_v{N}`) and bumping `metadata.schemaVersion`.

Troubleshooting:
- always log and persist `schemaId` + `schemaSha256` (and never the raw output payload)
