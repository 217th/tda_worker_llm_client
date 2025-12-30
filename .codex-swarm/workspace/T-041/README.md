# T-041: E07 Spike: LLM retry/backoff within time budget

## Summary

- Defined retry/backoff envelope for Gemini within time budget (maxGeminiAttempts=1; maxRepairAttempts=1).
- Mapped google-genai error classes to retryable vs non-retryable outcomes in spec.
- Marked SPK-014 resolved with references to the updated policy.

## Goal

- Establish a Gemini retry/backoff policy that respects finalize budget and avoids runaway retries.

## Scope

- Documentation-only spike; no production code changes.
- SDK: google-genai (1.56.0) error taxonomy used for mapping.

## Risks

- API behavior and error statuses can change; retryability may need tuning after integration testing.
- Structured output still needs semantic validation despite schema compliance.

## Verify Steps

- Review `docs/spec/error_and_retry_model.md` for the Gemini mapping + retry envelope.
- Ensure `docs/questions/arch_spikes.md` records SPK-014 as resolved.

## Rollback Plan

- Revert the mapping section and reopen SPK-014 if policy changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `docs/spec/error_and_retry_model.md` (Gemini SDK error mapping + retry envelope)
- `docs/questions/arch_spikes.md` (SPK-014 resolved)
<!-- END AUTO SUMMARY -->
