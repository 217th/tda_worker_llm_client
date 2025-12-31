# T-061: Add one-command prod deploy + smoke script

## Summary

- Add a production deployment script that runs with minimal prep, includes a short smoke run (positive + negative), cleans up test artifacts, and prints a concise report.

## Scope

- Script should:
  - Perform update deploy for Cloud Functions gen2 (preserve trigger config).
  - Run smoke scenarios (1 positive, 1 negative) only when explicitly approved.
  - Clean up test artifacts (Firestore updates, GCS objects if created).
  - Emit a summary report (deploy revision + smoke results).
- Update docs in `docs/` with usage and required inputs.

## Plan

1) Define inputs + env contract
   - Add a `deploy request block` (from playbook) and a `smoke request block` for prod.
   - Require explicit `APPROVE_SMOKE_VERIFY=true` before any smoke actions.
   - Keep secrets/identifiers out of tracked docs (placeholders only).

2) Implement script
   - Create `scripts/deploy_prod.sh` (or `scripts/deploy_prod_and_smoke.sh`) that:
     - Sources an env file (e.g., `.env.prod.local`, ignored).
     - Calls `scripts/deploy_dev.sh` for update deploy (confirm trigger unchanged).
     - Runs smoke scripts if approved:
       - Positive: trigger known flow_run (patch updatedAt/status) and verify success.
       - Negative: trigger a known invalid input (e.g., invalid schema or oversized artifact) and verify failure.
     - Cleanup: restore modified Firestore fields and delete any temp docs/objects.
     - Print a summary with PASS/FAIL per scenario and revision info.

3) Docs update
   - Update @docs/spec/deploy_and_envs.md or add a dedicated runbook in `docs/`:
     - Required env vars.
     - Sample request block with placeholders.
     - Smoke scenario prerequisites and how to opt in/out.

4) Tests (if applicable)
   - Shellcheck/lint if available (optional).

## Risks

- Smoke scenario may consume paid quota if not properly gated.

## Verify Steps

- `bash scripts/deploy_prod.sh --help` (or dry-run) if added.

## Rollback Plan

- Remove the script and revert docs changes.

## Execution log

- Not run (script only; requires prod credentials + explicit smoke approval).
