# T-030: E05 Implement PromptRepository + FirestorePromptRepository

## Summary

- Added prompt repository + Firestore adapter and wired handler to fetch prompts for READY LLM_REPORT steps.

## Goal

- Enable prompt fetch logging (`prompt_fetch_*`) for Epic 5 smoke runs without invoking Gemini.

## Scope

- New `LLMPrompt` model + `PromptRepository` protocol.
- Firestore prompt repository with promptId validation.
- CloudEvent handler flow: parse runId → select READY LLM step → fetch prompt → emit logs.
- Entrypoint now uses Firestore client + repos.

## Risks

- Prompt fetch runs without claim/finalize yet; repeated events can log multiple times.

## Verify Steps

- Not run (not requested).

## Rollback Plan

- Revert repository and handler wiring commits; restore previous `main.py` stub handler.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `main.py`
- `worker_llm_client/app/__init__.py`
- `worker_llm_client/app/handler.py`
- `worker_llm_client/app/services.py`
- `worker_llm_client/infra/__init__.py`
- `worker_llm_client/infra/firestore.py`
<!-- END AUTO SUMMARY -->
