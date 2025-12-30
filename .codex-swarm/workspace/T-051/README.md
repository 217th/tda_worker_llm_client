# T-051: E07 Deviation: runtime SA lacks GCS read access

## Summary

- Record and fix missing `storage.objects.get` permission for the runtime service account on the artifacts bucket.

## Scope

- Add bucket IAM bindings for runtime SA to read (and create) objects in `tda-artifacts-test`.
- Re-run Epic 7 demo scenarios after permission fix.

## Risks

- Over-permissioning the runtime SA; keep to object-level roles only.

## Verify Steps

- Trigger LLM step again and confirm `context_resolve_finished` succeeds and no GCS 403.

## Rollback Plan

- Remove the bucket IAM bindings if not needed.

## Notes

- Error observed: 403 Forbidden on `storage.objects.get` for runtime SA.
