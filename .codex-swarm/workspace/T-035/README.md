# T-035: E06 Implement GcsUri + ArtifactPathPolicy + LLMReportFile

## Summary

- Added artifacts/reporting domain primitives: GcsUri, ArtifactPathPolicy, and LLMReportFile DTO.

## Goal

- Provide deterministic artifact URI building and canonical report DTO per static_model/contract.

## Scope

- `worker_llm_client/artifacts/domain.py` with GcsUri + ArtifactPathPolicy.
- `worker_llm_client/reporting/domain.py` with LLMReportFile serialization.
- Package `__init__` exports.

## Risks

- Timeframe token detection may be too strict/loose for future stepId formats.

## Verify Steps

- Not run (not requested).

## Rollback Plan

- Revert new artifacts/reporting modules.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-035/README.md`
- `worker_llm_client/artifacts/__init__.py`
- `worker_llm_client/artifacts/domain.py`
- `worker_llm_client/reporting/__init__.py`
- `worker_llm_client/reporting/domain.py`
<!-- END AUTO SUMMARY -->
