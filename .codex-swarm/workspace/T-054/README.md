# T-054: E08 TimeBudgetPolicy + invocation deadline config

## Summary

- Add TimeBudgetPolicy and invocation timeout configuration for orchestration guardrails.

## Scope

- Introduce INVOCATION_TIMEOUT_SECONDS in WorkerConfig and docs.
- Implement TimeBudgetPolicy (remainingSeconds, can_start_llm_call/repair).
- Add unit tests for policy + config parsing.

## Risks

- Misconfigured timeout could skip LLM calls unexpectedly.

## Verify Steps

- Unit tests for policy and config parsing.

## Rollback Plan

- Revert policy/config changes and restore previous behavior.
