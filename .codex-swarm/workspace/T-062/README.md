# T-062: Add root README for LLM_REPORT entity hierarchy

## Summary

- Added a root-level `README.md` that documents the entity hierarchy for the `LLM_REPORT` step and links to the canonical schemas + examples.

## Goal

- Provide a single “entry point” doc that explains how `LLM_REPORT` is described end-to-end: `flow_runs/{runId}` → prompt/schema registries → upstream artifacts → final report artifact.

## Scope

- Docs-only change (no runtime behavior changes).

## Risks

- Links may become stale if contract/example paths are reorganized.

## Verify Steps

- `python3 -m pytest -q`

## Rollback Plan

- Revert the commit(s) for `T-062` (or remove the root `README.md`).

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- Added `README.md`.
<!-- END AUTO SUMMARY -->
