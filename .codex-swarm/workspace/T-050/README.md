# T-050: E07 Implement LLM execution path in handler

## Summary

- Implement full LLM execution flow (claim → resolve inputs → call Gemini → validate structured output → write report → finalize step).

## Scope

- Handler wiring: FlowRunRepository.claim_step / finalize_step.
- UserInputAssembler context resolution + size limits.
- LLMClient (GeminiClientAdapter) call with structured output schema.
- StructuredOutputValidator handling (invalid → FAILED).
- Artifact write for valid output, no raw payloads in logs.
- Tests for success + error mapping.

## Risks

- Cloud latency/time budget: ensure finalize on failures.
- Logging must avoid leaking raw payloads.

## Verify Steps

- Run unit tests.
- Re-run T-047 positive + 4.2/4.3 scenarios in dev.

## Rollback Plan

- Revert handler changes and associated tests.
