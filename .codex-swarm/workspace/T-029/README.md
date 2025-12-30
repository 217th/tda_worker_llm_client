# T-029: E05 Spike: prompt/schema registry invariants

## Summary

- Documented Firestore seed docs list + verification checklist for Epic 5 demo.
- Clarified schema sha256 policy and version pinning.
- Marked SPK-006/016 resolved in arch spikes.
- Seeded Firestore (dev) with prompt/schema/flow_run documents for demo.

## Goal

- Define prompt/schema registry policies and seed data requirements for dev/debug and demo.

## Scope

- Docs: system integration, llm schema contract, arch spikes backlog.

## Risks

- Incorrect seed guidance could block demos; mitigated by explicit schema references.

## Verify Steps

- Docs review: seed docs list, schema sha256 policy, and version pinning present.
- Firestore (dev) seeded with the following IDs:
  - llm_prompts: `llm_report_prompt_v1`
  - llm_schemas (valid): `llm_report_output_v1`
  - llm_schemas (invalid): `llm_report_output_v2`
  - flow_runs (valid): `20251230-120000_LINKUSDT_demo8`
  - flow_runs (missing prompt): `20251230-120500_LINKUSDT_demo8_missing_prompt`
  - flow_runs (invalid schema): `20251230-121000_LINKUSDT_demo8_invalid_schema`

## Rollback Plan

- Revert doc changes if policies change.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- (no file changes)
<!-- END AUTO SUMMARY -->
