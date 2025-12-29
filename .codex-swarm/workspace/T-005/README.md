# T-005: E00 Add smoke-check runbook + Cloud Logging queries

## Summary

- Added a dev smoke-check runbook with log queries and GCS checks.

## Goal

- Provide repeatable smoke verification steps after deploy/update.

## Scope

- Docs-only updates:
  - @docs/spec/deploy_and_envs.md
  - @docs/changelog.md

## Risks

- Without a runbook, deploy validation is manual and inconsistent.

## Verify Steps

- Review the runbook steps and ensure placeholders are used (no real IDs committed).

## Rollback Plan

- Revert the documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added smoke-check runbook docs:
  - docs/spec/deploy_and_envs.md
  - docs/changelog.md
<!-- END AUTO SUMMARY -->
