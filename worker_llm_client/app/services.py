from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from worker_llm_client.workflow.domain import FlowRun, FlowRunInvalid, StepError


@dataclass(frozen=True, slots=True)
class FlowRunRecord:
    flow_run: FlowRun
    update_time: Any


@dataclass(frozen=True, slots=True)
class ClaimResult:
    claimed: bool
    status: str | None
    reason: str | None = None  # not_ready|precondition_failed


@dataclass(frozen=True, slots=True)
class FinalizeResult:
    updated: bool
    status: str | None
    reason: str | None = None  # already_final|not_running|precondition_failed


class FlowRunRepository(Protocol):
    def get(self, run_id: str) -> FlowRunRecord | None:
        ...

    def patch(
        self,
        run_id: str,
        patch: Mapping[str, Any],
        *,
        precondition_update_time: Any,
    ) -> None:
        ...

    def claim_step(self, run_id: str, step_id: str, started_at_rfc3339: str) -> ClaimResult:
        ...

    def finalize_step(
        self,
        run_id: str,
        step_id: str,
        status: str,
        finished_at_rfc3339: str,
        *,
        outputs_gcs_uri: str | None = None,
        execution: Mapping[str, Any] | None = None,
        error: StepError | Mapping[str, Any] | None = None,
    ) -> FinalizeResult:
        ...


def build_step_update(step_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
    _require_step_id_safe(step_id)
    return {f"steps.{step_id}.{key}": value for key, value in updates.items()}


def build_claim_patch(step_id: str, started_at_rfc3339: str) -> dict[str, Any]:
    if not isinstance(started_at_rfc3339, str) or not started_at_rfc3339.strip():
        raise ValueError("started_at_rfc3339 must be a non-empty string")
    return build_step_update(
        step_id,
        {
            "status": "RUNNING",
            "outputs.execution.timing.startedAt": started_at_rfc3339,
        },
    )


def build_finalize_patch(
    *,
    step_id: str,
    status: str,
    finished_at_rfc3339: str,
    outputs_gcs_uri: str | None = None,
    execution: Mapping[str, Any] | None = None,
    error: StepError | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in ("SUCCEEDED", "FAILED"):
        raise ValueError("status must be SUCCEEDED or FAILED")
    if not isinstance(finished_at_rfc3339, str) or not finished_at_rfc3339.strip():
        raise ValueError("finished_at_rfc3339 must be a non-empty string")

    updates: dict[str, Any] = {
        "status": status,
        "finishedAt": finished_at_rfc3339,
    }

    if outputs_gcs_uri is not None:
        if not isinstance(outputs_gcs_uri, str) or not outputs_gcs_uri.strip():
            raise ValueError("outputs_gcs_uri must be a non-empty string")
        updates["outputs.gcs_uri"] = outputs_gcs_uri

    if execution is not None:
        updates["outputs.execution"] = dict(execution)

    if error is not None:
        if isinstance(error, StepError):
            updates["error"] = error.to_dict()
        elif isinstance(error, Mapping):
            updates["error"] = dict(error)
        else:
            raise ValueError("error must be a StepError or mapping")

    return build_step_update(step_id, updates)


def is_precondition_or_aborted(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gax  # type: ignore

        return isinstance(exc, (gax.FailedPrecondition, gax.Conflict, gax.Aborted))
    except Exception:
        return exc.__class__.__name__ in ("FailedPrecondition", "Conflict", "Aborted")


def _require_step_id_safe(step_id: str) -> None:
    if not isinstance(step_id, str) or not step_id.strip():
        raise FlowRunInvalid("stepId must be a non-empty string")
    if "." in step_id or "/" in step_id:
        raise FlowRunInvalid("stepId must not contain '.' or '/'")
