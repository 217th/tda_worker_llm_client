# T-055: E08 CloudEventParser service

## Summary

- Extract CloudEvent parsing into a dedicated CloudEventParser service.

## Scope

- Implement infra/cloudevents.py with runId parsing/validation.
- Update handler to use parser and emit cloud_event_ignored on invalid subject.
- Add unit tests for valid/invalid subject handling.

## Risks

- Parser mismatch could ignore valid events.

## Verify Steps

- Unit tests for parser and handler integration.

## Rollback Plan

- Revert to inline parsing in handler.
