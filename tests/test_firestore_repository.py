import unittest
from typing import Any

from worker_llm_client.app.services import build_claim_patch, build_finalize_patch
from worker_llm_client.infra.firestore import FirestoreFlowRunRepository
from worker_llm_client.workflow.domain import FlowRunInvalid


try:
    from google.api_core import exceptions as gax_exceptions
except Exception:  # pragma: no cover - fallback for environments without google-api-core
    gax_exceptions = None

try:
    from google.cloud import firestore as gcfirestore
except Exception:  # pragma: no cover - optional in minimal test envs
    gcfirestore = None


if gax_exceptions is not None:  # pragma: no cover - use real exceptions when available
    FailedPreconditionError = gax_exceptions.FailedPrecondition
    ConflictError = gax_exceptions.Conflict
else:

    class FailedPreconditionError(Exception):
        pass

    class ConflictError(Exception):
        pass

class FakeSnapshot:
    def __init__(self, data: dict, update_time: str = "t1") -> None:
        self._data = data
        self.update_time = update_time
        self.exists = True

    def to_dict(self) -> dict:
        return self._data


class FakeDocRef:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self._snapshots = snapshots
        self.updates: list[dict] = []
        self.options: list[Any] = []

    def get(self) -> FakeSnapshot:
        if self._snapshots:
            return self._snapshots.pop(0)
        return FakeSnapshot({})

    def update(self, patch: dict, option: Any | None = None) -> None:
        if getattr(self, "raise_on_update", None):
            raise self.raise_on_update
        self.updates.append(dict(patch))
        if option is not None:
            self.options.append(option)


class FakeClient:
    def __init__(self, doc_ref: FakeDocRef) -> None:
        self._doc_ref = doc_ref

    def collection(self, name: str) -> "FakeClient":
        return self

    def document(self, run_id: str) -> FakeDocRef:
        return self._doc_ref

    def write_option(self, last_update_time: Any) -> dict:
        return {"last_update_time": last_update_time}


class FirestoreRepositoryTests(unittest.TestCase):
    def _base_flow_run(self) -> dict:
        return {
            "runId": "run-1",
            "status": "RUNNING",
            "steps": {
                "step-1": {
                    "stepType": "LLM_REPORT",
                    "status": "READY",
                    "dependsOn": [],
                    "inputs": {},
                    "outputs": {},
                }
            },
        }

    def test_build_claim_patch_requires_started_at(self) -> None:
        with self.assertRaises(ValueError):
            build_claim_patch("step-1", "")

    def test_build_claim_patch_clears_error_and_finished_at(self) -> None:
        patch = build_claim_patch("step-1", "2025-01-01T00:00:00Z")
        error_key = "steps.step-1.error"
        finished_key = "steps.step-1.finishedAt"
        self.assertIn(error_key, patch)
        self.assertIn(finished_key, patch)
        if gcfirestore is not None:
            self.assertIs(patch[error_key], gcfirestore.DELETE_FIELD)
            self.assertIs(patch[finished_key], gcfirestore.DELETE_FIELD)
        else:
            self.assertIsNone(patch[error_key])
            self.assertIsNone(patch[finished_key])

    def test_build_finalize_patch_requires_status(self) -> None:
        with self.assertRaises(ValueError):
            build_finalize_patch(
                step_id="step-1",
                status="BAD",
                finished_at_rfc3339="2025-01-01T00:00:00Z",
            )

    def test_build_finalize_patch_clears_error_on_success(self) -> None:
        patch = build_finalize_patch(
            step_id="step-1",
            status="SUCCEEDED",
            finished_at_rfc3339="2025-01-01T00:00:00Z",
        )
        error_key = "steps.step-1.error"
        self.assertIn(error_key, patch)
        if gcfirestore is not None:
            self.assertIs(patch[error_key], gcfirestore.DELETE_FIELD)
        else:
            self.assertIsNone(patch[error_key])

    def test_claim_step_success(self) -> None:
        snapshot = FakeSnapshot(self._base_flow_run())
        doc_ref = FakeDocRef([snapshot])
        repo = FirestoreFlowRunRepository(FakeClient(doc_ref), max_attempts=1)
        result = repo.claim_step("run-1", "step-1", "2025-01-01T00:00:00Z")
        self.assertTrue(result.claimed)
        self.assertEqual(len(doc_ref.updates), 1)
        self.assertIn("steps.step-1.status", doc_ref.updates[0])

    def test_claim_step_not_ready(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["step-1"]["status"] = "RUNNING"
        snapshot = FakeSnapshot(flow_run)
        repo = FirestoreFlowRunRepository(FakeClient(FakeDocRef([snapshot])))
        result = repo.claim_step("run-1", "step-1", "2025-01-01T00:00:00Z")
        self.assertFalse(result.claimed)
        self.assertEqual(result.reason, "not_ready")

    def test_claim_step_precondition_conflict(self) -> None:
        flow_run = self._base_flow_run()
        snapshot = FakeSnapshot(flow_run)
        doc_ref = FakeDocRef([snapshot])
        doc_ref.raise_on_update = FailedPreconditionError("precondition failed")
        repo = FirestoreFlowRunRepository(FakeClient(doc_ref), max_attempts=1)
        result = repo.claim_step("run-1", "step-1", "2025-01-01T00:00:00Z")
        self.assertFalse(result.claimed)
        self.assertEqual(result.reason, "precondition_failed")

    def test_finalize_already_final(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["step-1"]["status"] = "SUCCEEDED"
        snapshot = FakeSnapshot(flow_run)
        repo = FirestoreFlowRunRepository(FakeClient(FakeDocRef([snapshot])))
        result = repo.finalize_step(
            "run-1",
            "step-1",
            "SUCCEEDED",
            "2025-01-01T00:00:00Z",
            outputs_gcs_uri="gs://x/report.json",
        )
        self.assertFalse(result.updated)
        self.assertEqual(result.reason, "already_final")

    def test_finalize_not_running(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["step-1"]["status"] = "READY"
        snapshot = FakeSnapshot(flow_run)
        repo = FirestoreFlowRunRepository(FakeClient(FakeDocRef([snapshot])))
        result = repo.finalize_step(
            "run-1",
            "step-1",
            "FAILED",
            "2025-01-01T00:00:00Z",
            error={"code": "INVALID_STEP_INPUTS", "message": "bad"},
        )
        self.assertFalse(result.updated)
        self.assertEqual(result.reason, "not_running")

    def test_finalize_ready_with_allow_ready(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["step-1"]["status"] = "READY"
        snapshot = FakeSnapshot(flow_run)
        doc_ref = FakeDocRef([snapshot])
        repo = FirestoreFlowRunRepository(FakeClient(doc_ref))
        result = repo.finalize_step(
            "run-1",
            "step-1",
            "FAILED",
            "2025-01-01T00:00:00Z",
            error={"code": "LLM_PROFILE_INVALID", "message": "schema invalid"},
            allow_ready=True,
        )
        self.assertTrue(result.updated)
        self.assertEqual(len(doc_ref.updates), 1)
        self.assertIn("steps.step-1.status", doc_ref.updates[0])

    def test_finalize_precondition_conflict(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["step-1"]["status"] = "RUNNING"
        snapshot = FakeSnapshot(flow_run)
        doc_ref = FakeDocRef([snapshot])
        doc_ref.raise_on_update = ConflictError("conflict")
        repo = FirestoreFlowRunRepository(FakeClient(doc_ref), max_attempts=1)
        result = repo.finalize_step(
            "run-1",
            "step-1",
            "FAILED",
            "2025-01-01T00:00:00Z",
            error={"code": "INVALID_STEP_INPUTS", "message": "bad"},
        )
        self.assertFalse(result.updated)
        self.assertEqual(result.reason, "precondition_failed")

    def test_invalid_step_id_rejected(self) -> None:
        flow_run = self._base_flow_run()
        flow_run["steps"]["bad.step"] = flow_run["steps"].pop("step-1")
        snapshot = FakeSnapshot(flow_run)
        repo = FirestoreFlowRunRepository(FakeClient(FakeDocRef([snapshot])))
        with self.assertRaises(FlowRunInvalid):
            repo.claim_step("run-1", "bad.step", "2025-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
