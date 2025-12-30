# T-031: E05 Implement SchemaRepository + FirestoreSchemaRepository

## Summary

- Added schema repository + Firestore adapter with minimal invariants validation and handler wiring for schema checks.

## Goal

- Enable `structured_output_schema_invalid` logging for missing/invalid schema docs without calling Gemini.

## Scope

- New `LLMSchema` model + `SchemaRepository` protocol with invariant validation.
- Firestore schema repository with schemaId pattern validation.
- Handler wiring to fetch schema after prompt fetch and emit error logs when invalid.

## Risks

- Schema validation is minimal and may reject schemas that only satisfy invariants indirectly.

## Verify Steps

- Not run (not requested).

## Rollback Plan

- Revert schema repository and handler schema checks; restore prompt-only flow.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-031/README.md`
- `main.py`
- `worker_llm_client/app/__init__.py`
- `worker_llm_client/app/handler.py`
- `worker_llm_client/app/services.py`
- `worker_llm_client/infra/__init__.py`
- `worker_llm_client/infra/firestore.py`
<!-- END AUTO SUMMARY -->
