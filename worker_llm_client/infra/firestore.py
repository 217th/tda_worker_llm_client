from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping

import re

from worker_llm_client.app.services import (
    ClaimResult,
    FinalizeResult,
    FlowRunRecord,
    FlowRunRepository,
    LLMPrompt,
    LLMSchema,
    PromptRepository,
    SchemaRepository,
    build_claim_patch,
    build_finalize_patch,
    is_precondition_or_aborted,
)
from worker_llm_client.workflow.domain import FlowRun, FlowRunInvalid


def _get_step_status(flow_run: Mapping[str, Any], step_id: str) -> str | None:
    steps = flow_run.get("steps")
    if not isinstance(steps, Mapping):
        return None
    step = steps.get(step_id)
    if not isinstance(step, Mapping):
        return None
    status = step.get("status")
    return status if isinstance(status, str) else None


_PROMPT_ID_RE = re.compile(
    r"^(?=.{1,128}$)llm_prompt_[1-9][0-9]*[A-Za-z]+_(report|reco)"
    r"(?:_[a-z0-9]{1,24})?_v[1-9][0-9]*_(?:0|[1-9][0-9]*)$"
)
_SCHEMA_ID_RE = re.compile(
    r"^(?=.{1,128}$)llm_schema_[1-9][0-9]*[A-Za-z]+_(report|reco)"
    r"(?:_[a-z0-9]{1,24})?_v[1-9][0-9]*_(?:0|[1-9][0-9]*)$"
)


def _is_prompt_id_safe(prompt_id: str) -> bool:
    return bool(_PROMPT_ID_RE.fullmatch(prompt_id))


def _is_schema_id_safe(schema_id: str) -> bool:
    return bool(_SCHEMA_ID_RE.fullmatch(schema_id))


@dataclass(slots=True)
class FirestoreFlowRunRepository(FlowRunRepository):
    client: Any
    flow_runs_collection: str = "flow_runs"
    max_attempts: int = 3
    base_backoff_seconds: float = 0.2

    def get(self, run_id: str) -> FlowRunRecord | None:
        doc_ref = self.client.collection(self.flow_runs_collection).document(run_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            return None
        flow_run_raw = snapshot.to_dict() if snapshot is not None else None
        flow_run_raw = flow_run_raw if isinstance(flow_run_raw, Mapping) else {}
        flow_run = FlowRun.from_raw(flow_run_raw, run_id=run_id)
        update_time = getattr(snapshot, "update_time", None)
        return FlowRunRecord(flow_run=flow_run, update_time=update_time)

    def patch(
        self, run_id: str, patch: Mapping[str, Any], *, precondition_update_time: Any
    ) -> None:
        if not isinstance(patch, Mapping):
            raise ValueError("patch must be a mapping")
        doc_ref = self.client.collection(self.flow_runs_collection).document(run_id)
        if precondition_update_time is not None and hasattr(self.client, "write_option"):
            option = self.client.write_option(last_update_time=precondition_update_time)
            doc_ref.update(dict(patch), option=option)
        else:
            doc_ref.update(dict(patch))

    def claim_step(self, run_id: str, step_id: str, started_at_rfc3339: str) -> ClaimResult:
        doc_ref = self.client.collection(self.flow_runs_collection).document(run_id)
        last_status: str | None = None

        for attempt in range(self.max_attempts):
            snapshot = doc_ref.get()
            flow_run_raw = snapshot.to_dict() if snapshot is not None else None
            flow_run_raw = flow_run_raw if isinstance(flow_run_raw, Mapping) else {}
            try:
                FlowRun.from_raw(flow_run_raw, run_id=run_id)
            except FlowRunInvalid:
                raise

            status = _get_step_status(flow_run_raw, step_id)
            last_status = status
            if status != "READY":
                return ClaimResult(claimed=False, status=status, reason="not_ready")

            patch = build_claim_patch(step_id, started_at_rfc3339)
            try:
                update_time = getattr(snapshot, "update_time", None)
                self.patch(run_id, patch, precondition_update_time=update_time)
                return ClaimResult(claimed=True, status=status)
            except Exception as exc:
                if is_precondition_or_aborted(exc):
                    if attempt < self.max_attempts - 1:
                        time.sleep(self.base_backoff_seconds * (2**attempt))
                        continue
                    return ClaimResult(
                        claimed=False, status=last_status, reason="precondition_failed"
                    )
                raise

        return ClaimResult(claimed=False, status=last_status, reason="precondition_failed")

    def finalize_step(
        self,
        run_id: str,
        step_id: str,
        status: str,
        finished_at_rfc3339: str,
        *,
        outputs_gcs_uri: str | None = None,
        execution: Mapping[str, Any] | None = None,
        error: Any | None = None,
        allow_ready: bool = False,
    ) -> FinalizeResult:
        doc_ref = self.client.collection(self.flow_runs_collection).document(run_id)
        last_status: str | None = None

        for attempt in range(self.max_attempts):
            snapshot = doc_ref.get()
            flow_run_raw = snapshot.to_dict() if snapshot is not None else None
            flow_run_raw = flow_run_raw if isinstance(flow_run_raw, Mapping) else {}
            try:
                FlowRun.from_raw(flow_run_raw, run_id=run_id)
            except FlowRunInvalid:
                raise

            current_status = _get_step_status(flow_run_raw, step_id)
            last_status = current_status
            if current_status in ("SUCCEEDED", "FAILED"):
                return FinalizeResult(updated=False, status=current_status, reason="already_final")
            if current_status != "RUNNING":
                if allow_ready and current_status == "READY":
                    pass
                else:
                    return FinalizeResult(
                        updated=False, status=current_status, reason="not_running"
                    )

            patch = build_finalize_patch(
                step_id=step_id,
                status=status,
                finished_at_rfc3339=finished_at_rfc3339,
                outputs_gcs_uri=outputs_gcs_uri,
                execution=execution,
                error=error,
            )
            try:
                update_time = getattr(snapshot, "update_time", None)
                self.patch(run_id, patch, precondition_update_time=update_time)
                return FinalizeResult(updated=True, status=current_status)
            except Exception as exc:
                if is_precondition_or_aborted(exc):
                    if attempt < self.max_attempts - 1:
                        time.sleep(self.base_backoff_seconds * (2**attempt))
                        continue
                    return FinalizeResult(
                        updated=False, status=last_status, reason="precondition_failed"
                    )
                raise

        return FinalizeResult(updated=False, status=last_status, reason="precondition_failed")


@dataclass(slots=True)
class FirestorePromptRepository(PromptRepository):
    client: Any
    prompts_collection: str = "llm_prompts"

    def get(self, prompt_id: str) -> LLMPrompt | None:
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise ValueError("prompt_id must be a non-empty string")
        if not _is_prompt_id_safe(prompt_id):
            raise ValueError(
                "prompt_id must follow "
                "llm_prompt_<timeframe>_<type>[_<suffix>]_v<major>_<minor>"
            )

        doc_ref = self.client.collection(self.prompts_collection).document(prompt_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            return None
        raw = snapshot.to_dict() if snapshot is not None else None
        raw = raw if isinstance(raw, Mapping) else {}
        try:
            return LLMPrompt.from_raw(raw, prompt_id=prompt_id)
        except ValueError:
            return None


@dataclass(slots=True)
class FirestoreSchemaRepository(SchemaRepository):
    client: Any
    schemas_collection: str = "llm_schemas"

    def get(self, schema_id: str) -> LLMSchema | None:
        if not isinstance(schema_id, str) or not schema_id.strip():
            raise ValueError("schema_id must be a non-empty string")
        if not _is_schema_id_safe(schema_id):
            raise ValueError(
                "schema_id must follow "
                "llm_schema_<timeframe>_<type>[_<suffix>]_v<major>_<minor>"
            )

        doc_ref = self.client.collection(self.schemas_collection).document(schema_id)
        snapshot = doc_ref.get()
        if not getattr(snapshot, "exists", False):
            return None
        raw = snapshot.to_dict() if snapshot is not None else None
        raw = raw if isinstance(raw, Mapping) else {}
        try:
            return LLMSchema.from_raw(raw, schema_id=schema_id)
        except ValueError:
            return None
