# T-034: E06 Spike: artifact idempotency + path policy

## Summary

- Documented GCS create-only semantics + prefix normalization; marked SPK-002/SPK-012 resolved.

## Goal

- Lock down idempotent artifact write semantics and ArtifactPathPolicy rules for Epic 6.

## Scope

- Update specs for artifact naming + create-only write behavior.
- Clarify GcsUri / ArtifactPathPolicy invariants in static model.
- Mark SPK-002 and SPK-012 resolved in arch_spikes.

## Risks

- Docs-only change; implementation still pending in later tasks.

## Verify Steps

- Not run (docs updates only).

## Rollback Plan

- Revert spec/static_model/arch_spikes edits.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-034/README.md`
- `docs/questions/arch_spikes.md`
- `docs/spec/implementation_contract.md`
- `docs/spec/system_integration.md`
- `docs/static_model.md`
<!-- END AUTO SUMMARY -->
