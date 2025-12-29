# T-012: E01 Dev verify secret injection + logging

## Summary

- Deployed updated function revision with Secret Manager → `GEMINI_API_KEY` injection.
- Verified the function config includes the secret env var and runtime env vars.
- Log-field check for `llm.auth.mode` is blocked until structured logging is implemented (Epic 2).

## Goal

- Validate Secret Manager injection and confirm logging constraints for auth fields.

## Scope

- Run @scripts/deploy_dev.sh in update mode with dev env vars and secret injection.
- Record evidence from deploy output.

## Risks

- Current stub does not emit `llm.auth.mode`; log verification will need Epic 2 logger.

## Verify Steps

- Deploy update in dev and capture output.

## Rollback Plan

- Roll back to the previous Cloud Functions gen2 revision if needed.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- .codex-swarm/workspace/T-012/README.md
<!-- END AUTO SUMMARY -->

## Evidence (dev)

- Command:
  - `ENV_VARS_MODE=inline ENV_VARS_INLINE="ARTIFACTS_BUCKET=tda-artifacts-test,FLOW_RUNS_COLLECTION=flow_runs,LLM_PROMPTS_COLLECTION=llm_prompts,LLM_MODELS_COLLECTION=llm_models,LOG_LEVEL=INFO,GEMINI_TIMEOUT_SECONDS=600,FINALIZE_BUDGET_SECONDS=120" CONFIRM_TRIGGER_UNCHANGED=true scripts/deploy_dev.sh`
- Result: update deploy completed; new revision `worker-llm-client-00003-ted` is ACTIVE.
- Secret injection confirmed in `serviceConfig.secretEnvironmentVariables`:
  - `GEMINI_API_KEY` → `projects/457107786858/secrets/gemini-api-key:latest`
- Note: `llm.auth.mode` log field cannot be verified yet (Epic 2 logging not implemented).
