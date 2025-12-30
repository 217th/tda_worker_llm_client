# T-049: E07 Deviation: schema invalid does not finalize step

## Summary

- Track deviation found during Epic 7 verification: invalid schema preflight logs error but does not finalize the step in Firestore.

## Scope

- Update handler/finalization path to mark the step as FAILED with error.code=LLM_PROFILE_INVALID when structured_output_schema_invalid occurs.
- Ensure no LLM call or artifact write happens on this path.
- Add/adjust tests to cover the preflight invalid schema behavior.

## Risks

- Firestore patch ordering/precondition handling could be sensitive; ensure idempotency and correct error codes.

## Verify Steps

- Re-run T-047 negative scenario 4.1:
  - Use schema missing summary.markdown.
  - Expect structured_output_schema_invalid and cloud_event_finished status=failed.
  - Expect Firestore step status=FAILED and error.code=LLM_PROFILE_INVALID.
  - Confirm no llm_request_* logs and no new report artifact.

## Rollback Plan

- Revert handler changes and associated tests.

## Notes

- Observed in dev on 2025-12-30T17:12:37Z (runId 20251230-120000_LINKUSDT_demo8, step llm_report_1m_summary_v1).
