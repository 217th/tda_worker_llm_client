# Test vectors

Keep small, stable input/output examples that can be used for:
- offline validation during development
- unit/integration tests in CI
- documentation of edge cases

Suggested layout:
- `inputs/`: Firestore documents (or fragments) that represent trigger-state
- `outputs/`: expected patches / artifacts summaries (not necessarily full GCS payloads)
