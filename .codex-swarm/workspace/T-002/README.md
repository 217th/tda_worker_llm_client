# T-002: E00 Spike: define least-privilege IAM for runtime/trigger SAs

## Summary

- Documented least-privilege IAM roles for runtime and trigger service accounts.
- Closed SPK-018 with an explicit decision entry.

## Goal

- Make IAM requirements explicit and reproducible for Firestore/Eventarc deployments.

## Scope

- Docs-only updates:
  - @docs/spec/deploy_and_envs.md
  - @docs/questions/open_questions.md
  - @docs/questions/arch_spikes.md

## Risks

- Missing roles cause 403s (Eventarc delivery or Firestore/GCS access).
- Over-broad roles increase blast radius.

## Verify Steps

- Validate IAM bindings (examples; do not execute here):
  - `gcloud projects add-iam-policy-binding <PROJECT_ID> --member=serviceAccount:<RUNTIME_SA_EMAIL> --role=roles/datastore.user`
  - `gcloud storage buckets add-iam-policy-binding gs://<ARTIFACTS_BUCKET> --member=serviceAccount:<RUNTIME_SA_EMAIL> --role=roles/storage.objectAdmin`
  - `gcloud secrets add-iam-policy-binding <SECRET_NAME> --member=serviceAccount:<RUNTIME_SA_EMAIL> --role=roles/secretmanager.secretAccessor`
  - `gcloud projects add-iam-policy-binding <PROJECT_ID> --member=serviceAccount:<TRIGGER_SA_EMAIL> --role=roles/eventarc.eventReceiver`
  - `gcloud run services add-iam-policy-binding <FUNCTION_NAME> --region <REGION> --member=serviceAccount:<TRIGGER_SA_EMAIL> --role=roles/run.invoker`

## Rollback Plan

- Revert the documentation changes.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Documented IAM least-privilege guidance:
  - docs/spec/deploy_and_envs.md
  - docs/questions/open_questions.md
  - docs/questions/arch_spikes.md
<!-- END AUTO SUMMARY -->
