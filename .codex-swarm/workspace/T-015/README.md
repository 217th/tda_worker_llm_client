# T-015: E02 Implement structured EventLogger

## Summary

- Implemented EventLogger + CloudLoggingEventLogger with safety gates.
- Wired cloud_event_received logging into the stub entrypoint.

## Goal

- Provide structured logging with required envelope fields and safety gates.

## Scope

- Add @worker_llm_client/ops/logging.py and export in @worker_llm_client/ops/__init__.py.
- Update @main.py to emit `cloud_event_received` logs.

## Risks

- Logger rejects payloads that violate safety gates; callers must supply safe fields.

## Verify Steps

- N/A (tests are in T-016).

## Rollback Plan

- Revert the commit to return to the previous stub logger.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- main.py
- worker_llm_client/ops/__init__.py
- worker_llm_client/ops/logging.py
<!-- END AUTO SUMMARY -->
