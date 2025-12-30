# T-040: E07 Spike: Gemini multimodal + JSON schema path

## Summary

- Verified that Gemini multimodal input + JSON schema output works together via Google GenAI SDK.
- Local spike script produced valid JSON from a request that included inline PNG bytes.
- Note: model returned a valid schema payload but did not echo the exact model name (semantic constraint).
- Endpoint choice for MVP remains AI Studio (API key); Vertex AI remains a later hardening step.

## Goal

- Confirm the SDK/API path for multimodal + `response_json_schema` to unblock Epic 7 implementation.

## Scope

- Local prototype only (no production code changes).
- Model: `gemini-2.5-flash-lite` via AI Studio API key (`GEMINI_API_KEY`).
- Inline image bytes + JSON schema response.

## Risks

- LLM may satisfy schema but ignore semantic constraints (e.g., field values) — must validate.
- Size limits for images / request payload not yet measured.

## Verify Steps

- `GEMINI_API_KEY=... GEMINI_MODEL=gemini-2.5-flash-lite python scripts/spikes/spk_010_multimodal_json_schema.py`

## Rollback Plan

- Remove the spike script and revert the system integration note if this path is rejected.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `scripts/spikes/spk_010_multimodal_json_schema.py` (new)
- `docs/spec/system_integration.md` (validated combined multimodal + schema note)
- `docs/questions/arch_spikes.md` (mark SPK-010 resolved)
<!-- END AUTO SUMMARY -->
