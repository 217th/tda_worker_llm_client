# T-058: E08 Cloud demo: orchestration + time budget

## Summary

- Run dev demo for Epic 8 orchestration and time budget behavior.

## Scope

- Re-validate Epic 7 scenarios (see @.codex-swarm/workspace/T-047/README.md):
  - Positive run: LLM success → artifact written → step SUCCEEDED.
  - Negative 4.1: invalid schema → LLM_PROFILE_INVALID, no LLM call.
  - Negative 4.2: invalid structured output → INVALID_STRUCTURED_OUTPUT (MAX_TOKENS).
  - Negative 4.3: oversized OHLCV → INVALID_STEP_INPUTS, no LLM call.
- Epic 8 scenarios:
  - Positive: normal run succeeds with sufficient time budget.
  - Negative: time budget prevents LLM call and fails step cleanly.
- Document steps, log queries, and Firestore/GCS outcomes; reuse run commands from T-047.

## Risks

- Environment misconfig may mask time-budget behavior.

## Verify Steps

- Collect Cloud Logging evidence for Epic 7 re-check + Epic 8 scenarios.
- Use the same scripts/commands as in T-047:
  - `scripts/deploy_dev.sh` (with FIRESTORE_DATABASE, INVOCATION_TIMEOUT_SECONDS, FINALIZE_BUDGET_SECONDS).
  - `gcloud functions describe ...` (revision + env vars).
  - Firestore REST PATCH (updatedAt trigger; model/schema/status changes).
  - `gsutil cp` for oversized OHLCV test artifact.
  - `gcloud logging read ... jsonPayload.event=...` filters for event chains.

## Rollback Plan

- No rollback; verification only.
