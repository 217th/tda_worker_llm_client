# T-003: E00 Define dev GCP bootstrap checklist and required resources

## Summary

- Added dev bootstrap checklist and runbook steps to deployment spec.

## Goal

- Make dev environment setup reproducible before deploy steps.

## Scope

- Docs-only updates:
  - @docs/spec/deploy_and_envs.md

## Risks

- Missing bootstrap steps can block deploy or cause region/IAM misconfigurations.

## Verify Steps

- Review the checklist and ensure placeholders are used (no real IDs committed).

## Rollback Plan

- Revert the documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Documented dev bootstrap checklist:
  - docs/spec/deploy_and_envs.md
<!-- END AUTO SUMMARY -->
