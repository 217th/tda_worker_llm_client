# T-007: E00 Add minimal Cloud Functions stub for deploy testing

## Summary

- Added a minimal Cloud Functions entrypoint for deploy testing.
- Adjusted requirements to rely on the runtime-provided functions-framework.

## Goal

- Enable safe deploy pipeline testing before the full implementation lands.

## Scope

- New files:
  - @main.py
  - @requirements.txt
  - @.gcloudignore

## Risks

- Stub does not implement business logic; it only logs basic CloudEvent fields.

## Verify Steps

- Deploy the function using @scripts/deploy_dev.sh and confirm it becomes ACTIVE.

## Rollback Plan

- Remove the stub files and revert the commit.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added deploy-test stub artifacts:
  - main.py
  - requirements.txt
  - .gcloudignore
<!-- END AUTO SUMMARY -->
