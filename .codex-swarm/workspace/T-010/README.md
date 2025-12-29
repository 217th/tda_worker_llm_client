# T-010: E01 Implement WorkerConfig + Gemini auth config

## Summary

- Implemented single-key Gemini auth config and runtime env validation.
- Added WorkerConfig with allowlist parsing and safe error messages.
- Wired config validation into the Cloud Functions entrypoint.

## Goal

- Implement WorkerConfig, GeminiApiKey, GeminiAuthConfig (single-key only) and validate env config at startup.

## Scope

- Add `worker_llm_client/ops/config.py` and related package init files.
- Update @main.py to validate config on import.

## Risks

- Import-time config validation will fail fast if required env vars are missing.

## Verify Steps

- N/A (tests are in T-011).

## Rollback Plan

- Revert this commit to restore the stub-only entrypoint.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- main.py
- worker_llm_client/__init__.py
- worker_llm_client/ops/__init__.py
- worker_llm_client/ops/config.py
<!-- END AUTO SUMMARY -->
