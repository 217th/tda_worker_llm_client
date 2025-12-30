# T-036: E06 Implement ArtifactStore + GcsArtifactStore

## Summary

- Added ArtifactStore port and GcsArtifactStore adapter with create-only semantics.

## Goal

- Provide idempotent GCS write/read/exists behavior with created vs reused result.

## Scope

- `worker_llm_client/artifacts/services.py` (ArtifactStore, WriteResult, errors).
- `worker_llm_client/infra/gcs.py` (GcsArtifactStore create-only write).
- Export in `worker_llm_client/infra/__init__.py`.
- Add `google-cloud-storage` dependency.

## Risks

- GCS dependency added to runtime; ensure deploy includes requirements.

## Verify Steps

- Not run (not requested).

## Rollback Plan

- Revert GCS adapter + dependency.

## Changes Summary (auto)

<!-- BEGIN AUTO SUMMARY -->
- `.codex-swarm/workspace/T-036/README.md`
- `requirements.txt`
- `worker_llm_client/artifacts/__init__.py`
- `worker_llm_client/artifacts/services.py`
- `worker_llm_client/infra/__init__.py`
- `worker_llm_client/infra/gcs.py`
<!-- END AUTO SUMMARY -->
