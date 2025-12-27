# Test vectors

Keep small, stable input/output examples that can be used for:
- offline validation during development
- unit/integration tests in CI
- documentation of edge cases

Suggested layout:
- `inputs/`: Firestore documents (or fragments) that represent trigger-state
- `outputs/`: expected patches / artifacts summaries (not necessarily full GCS payloads)

Structured output negatives (MVP):
- `fixtures/structured_output_invalid/*` contains example model-owned `output` payloads that should fail validation.
- `test_vectors/outputs/step_llm_report.failed_invalid_structured_output.*.patch.example.json` contains expected Firestore patches (`error.code=INVALID_STRUCTURED_OUTPUT`).
