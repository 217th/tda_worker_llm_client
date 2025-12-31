# T-056: E08 FlowRunEventHandler class

## Summary

- Wrap orchestration logic into FlowRunEventHandler class; keep wrapper function.

## Scope

- Introduce FlowRunEventHandler in app/handler.py.
- Keep handle_cloud_event as thin wrapper.
- Update unit tests to cover class-based handler.

## Risks

- Behavior/log drift if refactor is incomplete.

## Verify Steps

- Run existing handler/logging tests; ensure no log taxonomy changes.

## Rollback Plan

- Revert to function-only handler.
