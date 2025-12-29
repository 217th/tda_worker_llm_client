# T-004: E00 Add deploy pipeline command/script for Cloud Functions gen2

## Summary

- Added a deploy helper script for Cloud Functions gen2 (with optional build SA override).
- Fixed Firestore trigger path default handling in the deploy script.
- Documented how to use the deploy pipeline in the deployment spec.

## Goal

- Provide a repeatable deploy/update command aligned with the playbook.

## Scope

- New script:
  - @scripts/deploy_dev.sh
- Docs updates:
  - @docs/spec/deploy_and_envs.md
  - @docs/changelog.md

## Risks

- Script enforces required files (`main.py`, `.gcloudignore`, `requirements.txt`); deploy will fail until code is ready.

## Verify Steps

- Review script defaults and placeholders before running.
- Ensure deploy request env vars are provided (inline or file).
- If default compute SA is missing, set `BUILD_SA_EMAIL` for Cloud Build.

## Rollback Plan

- Revert the script and documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added deploy helper script and docs updates:
  - scripts/deploy_dev.sh
  - docs/spec/deploy_and_envs.md
  - docs/changelog.md
<!-- END AUTO SUMMARY -->
