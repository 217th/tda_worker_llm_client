# T-048: E07 Spike: Gemini image limits (size/count)

## Summary

- Ran a size/count sweep with inline PNGs + response_json_schema; no failures up to 8 images at 1024x1024.
- Max tested payload: 8 images, ~1,036,680 total bytes (PNG), prompt tokens ~2105, total tokens ~2166.
- Tested matrix (all OK): sizes 128/512/1024 with counts 1/4/8.
- No explicit limit encountered; upper bound still unknown.

## Goal

- Establish practical limits for image size/count in multimodal + structured output requests.

## Scope

- Local spike only, using `gemini-2.5-flash-lite` (AI Studio API key).
- Inline PNG bytes generated in-memory; response_json_schema enforced.

## Risks

- The API may allow larger images/counts; limits can change over time or differ on Vertex AI.
- Token usage is image-dependent and not proportional to byte size alone.
- Structured output passes schema but can ignore semantic constraints (e.g., image_size echoed incorrectly).

## Verify Steps

- `GEMINI_API_KEY=... GEMINI_MODEL=gemini-2.5-flash-lite SPIKE_VERBOSE=1 STOP_ON_ERROR=0 python scripts/spikes/spk_048_image_limits.py`

## Rollback Plan

- Remove the spike script and revert documentation notes about tested limits.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `scripts/spikes/spk_048_image_limits.py` (new)
- `docs/spec/system_integration.md` (limit sweep note)
- `docs/questions/arch_spikes.md` (SPK-010 limits summary)
<!-- END AUTO SUMMARY -->
