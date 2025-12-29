# T-001: E00 Spike: choose region/Eventarc routing for Firestore trigger

## Summary

- Documented the region alignment rule for Firestore, Eventarc, and Cloud Functions gen2.
- Closed SPK-017 with an explicit decision entry.

## Goal

- Make region routing requirements explicit for Firestore-triggered deploys.

## Scope

- Docs-only updates:
  - @docs/spec/deploy_and_envs.md
  - @docs/questions/open_questions.md
  - @docs/questions/arch_spikes.md

## Risks

- Deploys will fail or misroute if Firestore DB location differs from the function region.

## Verify Steps

- Check Firestore DB location matches the target region before deploy:
  - `gcloud firestore databases list --project <PROJECT_ID> --format="table(name,locationId,type)"`
- Ensure Eventarc trigger location matches function region (`--trigger-location`).

## Rollback Plan

- Revert the documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Updated region alignment decision and spike resolution docs:
  - docs/spec/deploy_and_envs.md
  - docs/questions/open_questions.md
  - docs/questions/arch_spikes.md
<!-- END AUTO SUMMARY -->
