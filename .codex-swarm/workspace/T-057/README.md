# T-057: E08 Time budget gating in handler

## Summary

- Enforce time budget guardrails before external calls (LLM/repair).

## Scope

- Integrate TimeBudgetPolicy into handler.
- Decide and document error code for time-budget failure.
- Add unit tests for guard path and logging.

## Risks

- Guard could block legitimate calls if budgets are mis-set.

## Verify Steps

- Unit tests for guard path (no llm_request_started, FAILED with expected code).

## Rollback Plan

- Disable guard and revert policy wiring.
