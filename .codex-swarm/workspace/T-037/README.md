# T-037: E06 Tests: ArtifactPathPolicy + ArtifactStore

## Summary

- Added unit tests for GcsUri, ArtifactPathPolicy, and GcsArtifactStore create-only semantics.

## Goal

- Validate deterministic artifact naming and idempotent write behavior.

## Scope

- `tests/test_artifacts.py` for domain + store behavior.

## Risks

- Tests rely on fakes; no live GCS interaction.

## Verify Steps

- Not run (not requested).

## Rollback Plan

- Revert test file.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-037/README.md`
- `tests/test_artifacts.py`
<!-- END AUTO SUMMARY -->
