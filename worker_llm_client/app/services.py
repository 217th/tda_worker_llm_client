from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

try:
    from google.cloud import firestore as _firestore  # type: ignore
except Exception:  # pragma: no cover - optional in non-firestore environments
    _firestore = None

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


@dataclass(frozen=True, slots=True)
class LLMPrompt:
    prompt_id: str
    schema_version: int
    system_instruction: str
    user_prompt: str

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any], *, prompt_id: str) -> "LLMPrompt":
        if not isinstance(raw, Mapping):
            raise ValueError("prompt document must be an object")
        schema_version = raw.get("schemaVersion")
        if schema_version != 1:
            raise ValueError("prompt schemaVersion must be 1")
        system_instruction = raw.get("systemInstruction")
        if not isinstance(system_instruction, str) or not system_instruction.strip():
            raise ValueError("prompt systemInstruction must be a non-empty string")
        user_prompt = raw.get("userPrompt")
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("prompt userPrompt must be a non-empty string")
        return cls(
            prompt_id=prompt_id,
            schema_version=schema_version,
            system_instruction=system_instruction,
            user_prompt=user_prompt,
        )


class PromptRepository(Protocol):
    def get(self, prompt_id: str) -> LLMPrompt | None:
        ...


@dataclass(frozen=True, slots=True)
class LLMSchema:
    schema_id: str
    kind: str
    json_schema: Mapping[str, Any]
    sha256: str

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any], *, schema_id: str) -> "LLMSchema":
        if not isinstance(raw, Mapping):
            raise ValueError("schema document must be an object")
        raw_schema_id = raw.get("schemaId")
        if raw_schema_id is not None:
            if not isinstance(raw_schema_id, str) or not raw_schema_id.strip():
                raise ValueError("schemaId must be a non-empty string")
            if raw_schema_id != schema_id:
                raise ValueError("schemaId mismatch between doc id and payload")
        kind = raw.get("kind")
        if kind != "LLM_REPORT_OUTPUT":
            raise ValueError("schema kind must be LLM_REPORT_OUTPUT")
        json_schema = raw.get("jsonSchema")
        if not isinstance(json_schema, Mapping):
            raise ValueError("jsonSchema must be an object")
        sha256 = raw.get("sha256")
        if not _is_hex_sha256(sha256):
            raise ValueError("sha256 must be a 64-char lowercase hex string")
        _validate_llm_report_schema(json_schema)
        return cls(
            schema_id=schema_id,
            kind=kind,
            json_schema=json_schema,
            sha256=sha256,
        )

    def provider_schema(self) -> Mapping[str, Any]:
        return self.json_schema


class SchemaRepository(Protocol):
    def get(self, schema_id: str) -> LLMSchema | None:
        ...


def build_step_update(step_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
    _require_step_id_safe(step_id)
    return {f"steps.{step_id}.{key}": value for key, value in updates.items()}


def build_claim_patch(step_id: str, started_at_rfc3339: str) -> dict[str, Any]:
    if not isinstance(started_at_rfc3339, str) or not started_at_rfc3339.strip():
        raise ValueError("started_at_rfc3339 must be a non-empty string")
    updates: dict[str, Any] = {
        "status": "RUNNING",
        "outputs.execution.timing.startedAt": started_at_rfc3339,
    }
    delete_field = getattr(_firestore, "DELETE_FIELD", None)
    if delete_field is not None:
        updates["error"] = delete_field
        updates["finishedAt"] = delete_field
    else:
        updates["error"] = None
        updates["finishedAt"] = None
    return build_step_update(step_id, updates)


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
    elif status == "SUCCEEDED":
        delete_field = getattr(_firestore, "DELETE_FIELD", None)
        if delete_field is not None:
            updates["error"] = delete_field
        else:
            updates["error"] = None

    return build_step_update(step_id, updates)


def is_precondition_or_aborted(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gax  # type: ignore

        return isinstance(exc, (gax.FailedPrecondition, gax.Conflict, gax.Aborted))
    except Exception:
        return exc.__class__.__name__ in (
            "FailedPrecondition",
            "FailedPreconditionError",
            "Conflict",
            "ConflictError",
            "Aborted",
        )


def _require_step_id_safe(step_id: str) -> None:
    if not isinstance(step_id, str) or not step_id.strip():
        raise FlowRunInvalid("stepId must be a non-empty string")
    if "." in step_id or "/" in step_id:
        raise FlowRunInvalid("stepId must not contain '.' or '/'")


def _is_hex_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    allowed = set("0123456789abcdef")
    return all(ch in allowed for ch in value)


def _validate_llm_report_schema(json_schema: Mapping[str, Any]) -> None:
    required = json_schema.get("required")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError("jsonSchema.required must be an array of strings")
    if "summary" not in required or "details" not in required:
        raise ValueError("jsonSchema must require summary and details")

    properties = json_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError("jsonSchema.properties must be an object")
    summary = properties.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("jsonSchema.properties.summary must be an object")
    summary_required = summary.get("required")
    if not isinstance(summary_required, list) or "markdown" not in summary_required:
        raise ValueError("jsonSchema.properties.summary.required must include markdown")
    summary_props = summary.get("properties")
    if not isinstance(summary_props, Mapping):
        raise ValueError("jsonSchema.properties.summary.properties must be an object")
    markdown = summary_props.get("markdown")
    if not isinstance(markdown, Mapping):
        raise ValueError("jsonSchema.properties.summary.properties.markdown must be an object")
    markdown_type = markdown.get("type")
    if markdown_type != "string":
        raise ValueError("jsonSchema.summary.markdown must be a string type")
