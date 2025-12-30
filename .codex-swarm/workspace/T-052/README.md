# T-052: E07 Deviation: success finalize leaves stale error

## Summary

- Step `error` field persists after a successful run; should be cleared on SUCCEEDED.

## Scope

- Update finalize logic to remove `error` on success.
- Optional: provide a helper to clear stale `error`/`finishedAt` when resetting a step to READY.

## Risks

- Ensure removal uses safe Firestore field deletion semantics.

## Verify Steps

- Run a step that previously failed, then succeeds.
- Confirm `steps.<stepId>.error` is absent when status=SUCCEEDED.

## Rollback Plan

- Revert finalize logic changes.
