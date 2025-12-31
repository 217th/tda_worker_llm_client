# T-058: E08 Cloud demo: orchestration + time budget

## Summary

- Run dev demo for Epic 8 orchestration and time budget behavior.

## Scope

- Positive scenario: normal run succeeds.
- Negative scenario: time budget prevents LLM call and fails step cleanly.
- Document steps, log queries, and Firestore/GCS outcomes.

## Risks

- Environment misconfig may mask time-budget behavior.

## Verify Steps

- Collect Cloud Logging evidence for both scenarios.

## Rollback Plan

- No rollback; verification only.
