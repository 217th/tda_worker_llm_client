# T-019: E03 Spike: FlowRun validation subset + error codes

## Summary

- Documented required-subset validation rules and error mapping (run vs step).
- Updated arch spike backlog to mark SPK-011/019 resolved.
- Added ignore rules for external reference fixtures.

## Goal

- Define the minimal required fields for `flow_runs/{runId}` validation and the canonical error-code mapping (run vs step).

## Scope

- Docs-only updates: implementation contract, flow_run contract, error/retry model, arch spikes backlog.

## Risks

- Risk of misclassifying run vs step errors; mitigated by explicit mapping rules.

## Verify Steps

- Docs review: required subset list and error mapping present and consistent across specs.

## Rollback Plan

- Revert doc changes if validation policy needs rework.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
