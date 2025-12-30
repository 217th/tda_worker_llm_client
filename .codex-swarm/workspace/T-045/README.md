# T-045: E07 Implement LLMClient port + GeminiClientAdapter

## Summary

- Added LLMClient port + GeminiClientAdapter (google-genai).
- Defined provider response DTO and error classes for retry mapping.

## Goal

- Provide a provider-neutral LLM client interface and an AI Studio adapter.

## Scope

- New app/infra modules; no handler wiring yet.
- Adds google-genai to runtime requirements.

## Risks

- Adapter assumes google-genai SDK availability; runtime must include dependency.

## Verify Steps

- `rg -n "GeminiClientAdapter" worker_llm_client/infra/gemini.py`

## Rollback Plan

- Revert adapter and client interface changes if integration path changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `worker_llm_client/app/llm_client.py` (LLMClient port + errors)
- `worker_llm_client/infra/gemini.py` (Gemini adapter)
- `worker_llm_client/app/__init__.py` (exports)
- `worker_llm_client/infra/__init__.py` (exports)
- `requirements.txt` (google-genai)
<!-- END AUTO SUMMARY -->
