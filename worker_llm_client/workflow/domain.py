from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


RUN_STATUSES = {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


class FlowRunInvalid(ValueError):
    """Raised when a flow_run document is invalid for this worker."""


class StepInvalid(ValueError):
    """Raised when a step object is missing required fields."""


class InvalidStepInputs(ValueError):
    """Raised when LLM_REPORT inputs are missing or invalid."""


class LLMProfileInvalid(ValueError):
    """Raised when an LLM profile is invalid for LLM_REPORT."""


class ErrorCode(str, Enum):
    FLOW_RUN_NOT_FOUND = "FLOW_RUN_NOT_FOUND"
    FLOW_RUN_INVALID = "FLOW_RUN_INVALID"
    FIRESTORE_CLAIM_FAILED = "FIRESTORE_CLAIM_FAILED"
    FIRESTORE_FINALIZE_FAILED = "FIRESTORE_FINALIZE_FAILED"
    FIRESTORE_UNAVAILABLE = "FIRESTORE_UNAVAILABLE"
    GCS_WRITE_FAILED = "GCS_WRITE_FAILED"
    PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
    LLM_PROFILE_INVALID = "LLM_PROFILE_INVALID"
    GEMINI_REQUEST_FAILED = "GEMINI_REQUEST_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    LLM_SAFETY_BLOCK = "LLM_SAFETY_BLOCK"
    INVALID_STRUCTURED_OUTPUT = "INVALID_STRUCTURED_OUTPUT"
    INVALID_STEP_INPUTS = "INVALID_STEP_INPUTS"
    STEP_CLAIM_CONFLICT = "STEP_CLAIM_CONFLICT"
    STEP_FINALIZE_CONFLICT = "STEP_FINALIZE_CONFLICT"
    NO_READY_STEP = "NO_READY_STEP"
    DEPENDENCY_NOT_SUCCEEDED = "DEPENDENCY_NOT_SUCCEEDED"

    def is_retryable(self) -> bool:
        return self in {
            ErrorCode.FIRESTORE_UNAVAILABLE,
            ErrorCode.GCS_WRITE_FAILED,
            ErrorCode.GEMINI_REQUEST_FAILED,
            ErrorCode.RATE_LIMITED,
        }


@dataclass(frozen=True, slots=True)
class StepError:
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None

    @classmethod
    def from_error_code(
        cls, code: ErrorCode | str, message: str, details: dict[str, Any] | None = None
    ) -> "StepError":
        if isinstance(code, str):
            code = ErrorCode(code)
        return cls(code=code, message=message, details=details)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


def _is_step_id_safe(step_id: str) -> bool:
    return "." not in step_id and "/" not in step_id


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StepInvalid(f"{label} must be an object")
    return value


def _parse_depends_on(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise StepInvalid("dependsOn must be an array of strings")
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise StepInvalid("dependsOn must contain non-empty strings")
        values.append(item.strip())
    return tuple(values)


@dataclass(frozen=True, slots=True)
class FlowStep:
    step_id: str
    step_type: str
    status: str
    depends_on: tuple[str, ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_raw(cls, step_id: str, raw: Mapping[str, Any]) -> "FlowStep":
        if not isinstance(step_id, str) or not step_id.strip():
            raise StepInvalid("stepId must be a non-empty string")
        if not _is_step_id_safe(step_id):
            raise StepInvalid("stepId must not contain '.' or '/'")
        raw = _require_mapping(raw, label="step")
        step_type = raw.get("stepType")
        status = raw.get("status")
        if not isinstance(step_type, str) or not step_type.strip():
            raise StepInvalid("stepType is required")
        if not isinstance(status, str) or not status.strip():
            raise StepInvalid("status is required")
        depends_on = _parse_depends_on(raw.get("dependsOn"))
        return cls(
            step_id=step_id,
            step_type=step_type,
            status=status,
            depends_on=depends_on,
            raw=raw,
        )

    def is_ready(self) -> bool:
        return self.status == "READY"

    def is_running(self) -> bool:
        return self.status == "RUNNING"

    def is_succeeded(self) -> bool:
        return self.status == "SUCCEEDED"

    def is_failed(self) -> bool:
        return self.status == "FAILED"

    @property
    def inputs(self) -> Mapping[str, Any]:
        inputs = self.raw.get("inputs")
        return inputs if isinstance(inputs, Mapping) else {}

    @property
    def outputs(self) -> Mapping[str, Any]:
        outputs = self.raw.get("outputs")
        return outputs if isinstance(outputs, Mapping) else {}


@dataclass(frozen=True, slots=True)
class FlowRun:
    status: str
    steps: Mapping[str, Mapping[str, Any]]
    run_id: str | None = None
    raw: Mapping[str, Any] | None = None

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any], *, run_id: str | None = None) -> "FlowRun":
        if not isinstance(raw, Mapping):
            raise FlowRunInvalid("flow_run must be an object")
        status = raw.get("status")
        if not isinstance(status, str) or status not in RUN_STATUSES:
            raise FlowRunInvalid("status must be a valid run status")
        steps = raw.get("steps")
        if not isinstance(steps, Mapping):
            raise FlowRunInvalid("steps must be an object")
        for step_id in steps.keys():
            if not isinstance(step_id, str) or not step_id.strip():
                raise FlowRunInvalid("stepId must be a non-empty string")
            if not _is_step_id_safe(step_id):
                raise FlowRunInvalid("stepId must not contain '.' or '/'")
        doc_run_id = raw.get("runId")
        if doc_run_id is not None:
            if not isinstance(doc_run_id, str) or not doc_run_id.strip():
                raise FlowRunInvalid("runId must be a non-empty string")
            if run_id is not None and doc_run_id != run_id:
                raise FlowRunInvalid("runId mismatch between doc id and payload")
        return cls(
            status=status,
            steps=steps,
            run_id=doc_run_id or run_id,
            raw=raw,
        )

    def get_step(self, step_id: str) -> FlowStep | None:
        raw_step = self.steps.get(step_id)
        if not isinstance(raw_step, Mapping):
            return None
        try:
            return FlowStep.from_raw(step_id, raw_step)
        except StepInvalid:
            return None

    def iter_steps_sorted(self) -> list[FlowStep]:
        steps: list[FlowStep] = []
        for step_id in sorted(self.steps.keys()):
            raw_step = self.steps.get(step_id)
            if not isinstance(raw_step, Mapping):
                continue
            try:
                steps.append(FlowStep.from_raw(step_id, raw_step))
            except StepInvalid:
                continue
        return steps

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES


@dataclass(frozen=True, slots=True)
class LLMReportInputs:
    prompt_id: str
    llm_profile: Mapping[str, Any]
    ohlcv_step_id: str
    charts_manifest_step_id: str
    previous_report_step_ids: tuple[str, ...]
    ohlcv_gcs_uri: str
    charts_manifest_gcs_uri: str
    previous_report_gcs_uris: tuple[str, ...]

    @classmethod
    def from_raw(
        cls, inputs: Mapping[str, Any], *, flow_run: FlowRun
    ) -> "LLMReportInputs":
        if not isinstance(inputs, Mapping):
            raise InvalidStepInputs("inputs must be an object")
        llm = inputs.get("llm")
        if not isinstance(llm, Mapping):
            raise InvalidStepInputs("inputs.llm must be an object")

        prompt_id = llm.get("promptId")
        if not isinstance(prompt_id, str) or not prompt_id.strip():
            raise InvalidStepInputs("inputs.llm.promptId is required")

        llm_profile = llm.get("llmProfile")
        if not isinstance(llm_profile, Mapping):
            raise LLMProfileInvalid("inputs.llm.llmProfile is required")
        _validate_llm_profile(llm_profile)

        ohlcv_step_id = _require_string(inputs.get("ohlcvStepId"), label="inputs.ohlcvStepId")
        charts_manifest_step_id = _require_string(
            inputs.get("chartsManifestStepId"), label="inputs.chartsManifestStepId"
        )
        previous_report_step_ids = _parse_optional_step_ids(inputs.get("previousReportStepIds"))

        ohlcv_gcs_uri = _resolve_output_uri(flow_run, ohlcv_step_id)
        charts_manifest_gcs_uri = _resolve_output_uri(flow_run, charts_manifest_step_id)
        previous_report_gcs_uris = tuple(
            _resolve_output_uri(flow_run, step_id, require_llm_report=True)
            for step_id in previous_report_step_ids
        )

        return cls(
            prompt_id=prompt_id,
            llm_profile=llm_profile,
            ohlcv_step_id=ohlcv_step_id,
            charts_manifest_step_id=charts_manifest_step_id,
            previous_report_step_ids=previous_report_step_ids,
            ohlcv_gcs_uri=ohlcv_gcs_uri,
            charts_manifest_gcs_uri=charts_manifest_gcs_uri,
            previous_report_gcs_uris=previous_report_gcs_uris,
        )


@dataclass(frozen=True, slots=True)
class LLMReportStep:
    step: FlowStep

    @classmethod
    def from_flow_step(cls, step: FlowStep) -> "LLMReportStep":
        if step.step_type != "LLM_REPORT":
            raise StepInvalid("stepType must be LLM_REPORT")
        return cls(step=step)

    def parse_inputs(self, *, flow_run: FlowRun) -> LLMReportInputs:
        return LLMReportInputs.from_raw(self.step.inputs, flow_run=flow_run)


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidStepInputs(f"{label} is required")
    return value.strip()


def _parse_optional_step_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise InvalidStepInputs("inputs.previousReportStepIds must be an array")
    values: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidStepInputs("inputs.previousReportStepIds must contain non-empty strings")
        values.append(item.strip())
    return tuple(values)


def _resolve_output_uri(
    flow_run: FlowRun, step_id: str, *, require_llm_report: bool = False
) -> str:
    step = flow_run.get_step(step_id)
    if step is None:
        raise InvalidStepInputs(f"Referenced step not found: {step_id}")
    if require_llm_report and step.step_type != "LLM_REPORT":
        raise InvalidStepInputs(f"Referenced step is not LLM_REPORT: {step_id}")
    outputs = step.outputs
    gcs_uri = outputs.get("gcs_uri")
    if not isinstance(gcs_uri, str) or not gcs_uri.strip():
        raise InvalidStepInputs(f"Referenced step missing outputs.gcs_uri: {step_id}")
    return gcs_uri


def _validate_llm_profile(profile: Mapping[str, Any]) -> None:
    response_mime = profile.get("responseMimeType")
    if response_mime != "application/json":
        raise LLMProfileInvalid("llmProfile.responseMimeType must be application/json")
    candidate_count = profile.get("candidateCount")
    if candidate_count is not None and candidate_count != 1:
        raise LLMProfileInvalid("llmProfile.candidateCount must be 1")
    structured_output = profile.get("structuredOutput")
    if not isinstance(structured_output, Mapping):
        raise LLMProfileInvalid("llmProfile.structuredOutput is required")
    schema_id = structured_output.get("schemaId")
    if not isinstance(schema_id, str) or not schema_id.strip():
        raise LLMProfileInvalid("llmProfile.structuredOutput.schemaId is required")
