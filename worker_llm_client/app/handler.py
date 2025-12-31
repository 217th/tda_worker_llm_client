from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable, Mapping

from worker_llm_client.app.llm_client import LLMClient, RateLimited, RequestFailed, SafetyBlocked
from worker_llm_client.app.services import (
    FlowRunRepository,
    PromptRepository,
    SchemaRepository,
)
from worker_llm_client.artifacts.domain import ArtifactPathPolicy, InvalidIdentifier
from worker_llm_client.artifacts.services import ArtifactStore, ArtifactWriteFailed
from worker_llm_client.infra.cloudevents import CloudEventParser
from worker_llm_client.ops.logging import EventLogger, MAX_ARRAY_LENGTH
from worker_llm_client.ops.time_budget import TimeBudgetPolicy
from worker_llm_client.reporting.domain import (
    LLMProfile,
    LLMReportFile,
    SerializationError,
    StructuredOutputInvalid,
)
from worker_llm_client.reporting.services import UserInputAssembler
from worker_llm_client.reporting.structured_output import StructuredOutputValidator
from worker_llm_client.workflow.domain import ErrorCode, InvalidStepInputs, LLMProfileInvalid, StepError
from worker_llm_client.workflow.policies import ReadyStepSelector


def _extract_field(cloud_event: Any, name: str) -> Any:
    if hasattr(cloud_event, "get"):
        try:
            return cloud_event.get(name)
        except Exception:
            return None
    return getattr(cloud_event, name, None)


def _step_summaries(steps: list[Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for step in steps[:MAX_ARRAY_LENGTH]:
        summaries.append(
            {
                "stepId": step.step_id,
                "stepType": step.step_type,
                "status": step.status,
                "dependsOn": list(step.depends_on),
            }
        )
    return summaries


_SCHEMA_VERSION_RE = re.compile(r"^llm_report_output_v([1-9][0-9]*)$")


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_schema_version(schema_id: str) -> int | None:
    if not isinstance(schema_id, str):
        return None
    match = _SCHEMA_VERSION_RE.fullmatch(schema_id.strip())
    if not match:
        return None
    return int(match.group(1))


def _extract_symbol(flow_run: Any) -> str | None:
    raw = getattr(flow_run, "raw", None)
    if not isinstance(raw, Mapping):
        return None
    scope = raw.get("scope")
    if not isinstance(scope, Mapping):
        return None
    symbol = scope.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        return None
    return symbol.strip()


def _extract_timeframe(step: Any) -> str | None:
    raw = getattr(step, "raw", None)
    if not isinstance(raw, Mapping):
        return None
    timeframe = raw.get("timeframe")
    if not isinstance(timeframe, str) or not timeframe.strip():
        return None
    return timeframe.strip()


def _extract_model_name(llm_profile: Mapping[str, Any]) -> str:
    model_name = llm_profile.get("modelName")
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    model_name = llm_profile.get("model")
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return "dry_run"


class FlowRunEventHandler:
    """Application service for one CloudEvent invocation."""

    def __init__(
        self,
        *,
        flow_repo: FlowRunRepository,
        prompt_repo: PromptRepository,
        schema_repo: SchemaRepository,
        event_logger: EventLogger,
        flow_runs_collection: str,
        artifact_store: ArtifactStore | None = None,
        path_policy: ArtifactPathPolicy | None = None,
        artifacts_dry_run: bool = False,
        llm_client: LLMClient | None = None,
        user_input_assembler: UserInputAssembler | None = None,
        structured_output_validator: StructuredOutputValidator | None = None,
        model_allowed: Callable[[str], bool] | None = None,
        finalize_budget_seconds: int = 120,
        invocation_timeout_seconds: int = 780,
    ) -> None:
        self._flow_repo = flow_repo
        self._prompt_repo = prompt_repo
        self._schema_repo = schema_repo
        self._event_logger = event_logger
        self._flow_runs_collection = flow_runs_collection
        self._artifact_store = artifact_store
        self._path_policy = path_policy
        self._artifacts_dry_run = artifacts_dry_run
        self._llm_client = llm_client
        self._user_input_assembler = user_input_assembler
        self._structured_output_validator = structured_output_validator
        self._model_allowed = model_allowed
        self._finalize_budget_seconds = finalize_budget_seconds
        self._invocation_timeout_seconds = invocation_timeout_seconds

    def handle(self, cloud_event: Any) -> str:
        return _handle_cloud_event_impl(
            cloud_event,
            flow_repo=self._flow_repo,
            prompt_repo=self._prompt_repo,
            schema_repo=self._schema_repo,
            event_logger=self._event_logger,
            flow_runs_collection=self._flow_runs_collection,
            artifact_store=self._artifact_store,
            path_policy=self._path_policy,
            artifacts_dry_run=self._artifacts_dry_run,
            llm_client=self._llm_client,
            user_input_assembler=self._user_input_assembler,
            structured_output_validator=self._structured_output_validator,
            model_allowed=self._model_allowed,
            finalize_budget_seconds=self._finalize_budget_seconds,
            invocation_timeout_seconds=self._invocation_timeout_seconds,
        )


def handle_cloud_event(
    cloud_event: Any,
    *,
    flow_repo: FlowRunRepository,
    prompt_repo: PromptRepository,
    schema_repo: SchemaRepository,
    event_logger: EventLogger,
    flow_runs_collection: str,
    artifact_store: ArtifactStore | None = None,
    path_policy: ArtifactPathPolicy | None = None,
    artifacts_dry_run: bool = False,
    llm_client: LLMClient | None = None,
    user_input_assembler: UserInputAssembler | None = None,
    structured_output_validator: StructuredOutputValidator | None = None,
    model_allowed: Callable[[str], bool] | None = None,
    finalize_budget_seconds: int = 120,
    invocation_timeout_seconds: int = 780,
) -> str:
    """CloudEvent handler for one Firestore update invocation."""
    handler = FlowRunEventHandler(
        flow_repo=flow_repo,
        prompt_repo=prompt_repo,
        schema_repo=schema_repo,
        event_logger=event_logger,
        flow_runs_collection=flow_runs_collection,
        artifact_store=artifact_store,
        path_policy=path_policy,
        artifacts_dry_run=artifacts_dry_run,
        llm_client=llm_client,
        user_input_assembler=user_input_assembler,
        structured_output_validator=structured_output_validator,
        model_allowed=model_allowed,
        finalize_budget_seconds=finalize_budget_seconds,
        invocation_timeout_seconds=invocation_timeout_seconds,
    )
    return handler.handle(cloud_event)


def _handle_cloud_event_impl(
    cloud_event: Any,
    *,
    flow_repo: FlowRunRepository,
    prompt_repo: PromptRepository,
    schema_repo: SchemaRepository,
    event_logger: EventLogger,
    flow_runs_collection: str,
    artifact_store: ArtifactStore | None = None,
    path_policy: ArtifactPathPolicy | None = None,
    artifacts_dry_run: bool = False,
    llm_client: LLMClient | None = None,
    user_input_assembler: UserInputAssembler | None = None,
    structured_output_validator: StructuredOutputValidator | None = None,
    model_allowed: Callable[[str], bool] | None = None,
    finalize_budget_seconds: int = 120,
    invocation_timeout_seconds: int = 780,
) -> str:
    event_id = _extract_field(cloud_event, "id") or "unknown"
    event_type = _extract_field(cloud_event, "type") or "unknown"
    subject = _extract_field(cloud_event, "subject") or "unknown"

    event_logger.log(
        event="cloud_event_received",
        severity="INFO",
        eventId=event_id,
        runId="unknown",
        stepId="unknown",
        eventType=event_type,
        subject=subject,
    )

    parser = CloudEventParser(flow_runs_collection=flow_runs_collection)
    run_id = parser.run_id_from_subject(subject)
    if run_id is None:
        event_logger.log(
            event="cloud_event_ignored",
            severity="WARNING",
            eventId=event_id,
            runId="unknown",
            stepId="unknown",
            reason="invalid_subject",
        )
        return "ignored"

    record = flow_repo.get(run_id)
    if record is None:
        event_logger.log(
            event="cloud_event_ignored",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason="flow_run_not_found",
        )
        return "ignored"

    flow_run = record.flow_run
    event_logger.log(
        event="cloud_event_parsed",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId="unknown",
        flowRunFound=True,
        flowRunStatus=flow_run.status,
        flowRunSteps=_step_summaries(flow_run.iter_steps_sorted()),
    )

    if flow_run.is_terminal():
        event_logger.log(
            event="cloud_event_noop",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason="already_final",
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            status="noop",
        )
        return "noop"

    pick = ReadyStepSelector.pick(flow_run)
    if pick.step is None:
        event_logger.log(
            event="cloud_event_noop",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            reason=pick.reason or "no_ready_step",
        )
        event_logger.log(
            event="cloud_event_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId="unknown",
            status="noop",
        )
        return "noop"

    step = pick.step.step
    step_id = step.step_id
    timeframe = step.raw.get("timeframe") if isinstance(step.raw, Mapping) else None
    event_logger.log(
        event="ready_step_selected",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        stepType=step.step_type,
        timeframe=timeframe,
    )
    started_at = _now_rfc3339()
    time_budget = TimeBudgetPolicy.start_now(
        invocation_timeout_seconds=invocation_timeout_seconds,
        finalize_budget_seconds=finalize_budget_seconds,
    )

    def _log_cloud_event_finished(
        *,
        status: str,
        severity: str,
        error: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": "cloud_event_finished",
            "severity": severity,
            "eventId": event_id,
            "runId": run_id,
            "stepId": step_id,
            "status": status,
        }
        if error is not None:
            payload["error"] = dict(error)
        if reason is not None:
            payload["reason"] = reason
        event_logger.log(**payload)

    def _finalize_failed(
        code: ErrorCode, message: str, *, allow_ready: bool = False
    ) -> str:
        finished_at = _now_rfc3339()
        error = StepError.from_error_code(code, message)
        try:
            result = flow_repo.finalize_step(
                run_id,
                step_id,
                "FAILED",
                finished_at,
                error=error,
                allow_ready=allow_ready,
            )
        except Exception:
            _log_cloud_event_finished(
                status="failed",
                severity="ERROR",
                error={
                    "code": ErrorCode.FIRESTORE_FINALIZE_FAILED.value,
                    "message": "Failed to finalize step",
                },
            )
            return "failed"
        if not result.updated:
            _log_cloud_event_finished(
                status="noop",
                severity="WARNING",
                error={"code": ErrorCode.STEP_FINALIZE_CONFLICT.value},
                reason=result.reason,
            )
            return "noop"
        _log_cloud_event_finished(
            status="failed",
            severity="ERROR",
            error={"code": code.value, "message": message},
        )
        return "failed"

    def _finalize_success(outputs_gcs_uri: str | None = None) -> str:
        finished_at = _now_rfc3339()
        try:
            result = flow_repo.finalize_step(
                run_id,
                step_id,
                "SUCCEEDED",
                finished_at,
                outputs_gcs_uri=outputs_gcs_uri,
            )
        except Exception:
            _log_cloud_event_finished(
                status="failed",
                severity="ERROR",
                error={
                    "code": ErrorCode.FIRESTORE_FINALIZE_FAILED.value,
                    "message": "Failed to finalize step",
                },
            )
            return "failed"
        if not result.updated:
            _log_cloud_event_finished(
                status="noop",
                severity="WARNING",
                error={"code": ErrorCode.STEP_FINALIZE_CONFLICT.value},
                reason=result.reason,
            )
            return "noop"
        _log_cloud_event_finished(status="ok", severity="INFO")
        return "ok"

    if not time_budget.can_start_llm_call():
        event_logger.log(
            event="time_budget_exceeded",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            action="claim",
            policy=time_budget.snapshot(),
        )
        return _finalize_failed(
            ErrorCode.TIME_BUDGET_EXCEEDED,
            "Insufficient time budget for external calls",
            allow_ready=True,
        )

    claim = flow_repo.claim_step(run_id, step_id, started_at)
    if not claim.claimed:
        if claim.reason == "precondition_failed":
            _log_cloud_event_finished(
                status="noop",
                severity="WARNING",
                error={"code": ErrorCode.STEP_CLAIM_CONFLICT.value},
                reason=claim.reason,
            )
        else:
            _log_cloud_event_finished(
                status="noop",
                severity="INFO",
                reason=claim.reason,
            )
        return "noop"

    try:
        inputs = pick.step.parse_inputs(flow_run=flow_run)
    except InvalidStepInputs as exc:
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))
    except LLMProfileInvalid as exc:
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            reason={"message": str(exc)},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        return _finalize_failed(ErrorCode.LLM_PROFILE_INVALID, str(exc), allow_ready=True)

    event_logger.log(
        event="prompt_fetch_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        llm={"promptId": inputs.prompt_id},
    )

    prompt = prompt_repo.get(inputs.prompt_id)
    if prompt is None:
        event_logger.log(
            event="prompt_fetch_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            ok=False,
            error={"code": ErrorCode.PROMPT_NOT_FOUND.value},
        )
        _finalize_failed(ErrorCode.PROMPT_NOT_FOUND, "Prompt not found")
        return "prompt_not_found"

    event_logger.log(
        event="prompt_fetch_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        ok=True,
    )

    structured_output = (
        inputs.llm_profile.get("structuredOutput")
        if isinstance(inputs.llm_profile, Mapping)
        else None
    )
    schema_id = None
    if isinstance(structured_output, Mapping):
        schema_id = structured_output.get("schemaId")

    if not isinstance(schema_id, str) or not schema_id.strip():
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            llm={"schemaId": schema_id or "unknown"},
            reason={"message": "schemaId missing in llmProfile"},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        _finalize_failed(
            ErrorCode.LLM_PROFILE_INVALID, "schemaId missing in llmProfile", allow_ready=True
        )
        return "schema_invalid"

    schema = schema_repo.get(schema_id)
    if schema is None:
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            llm={"schemaId": schema_id},
            reason={"message": "schema missing or violates invariants"},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        _finalize_failed(
            ErrorCode.LLM_PROFILE_INVALID, "schema missing or violates invariants", allow_ready=True
        )
        return "schema_invalid"

    if artifact_store is None or path_policy is None:
        return _finalize_failed(ErrorCode.GCS_WRITE_FAILED, "Artifact store unavailable")

    schema_version = _parse_schema_version(schema.schema_id)
    if schema_version is None:
        event_logger.log(
            event="structured_output_schema_invalid",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            llm={"schemaId": schema.schema_id, "schemaSha256": schema.sha256},
            reason={"message": "schemaId must follow llm_report_output_v{N}"},
            error={"code": ErrorCode.LLM_PROFILE_INVALID.value},
        )
        return _finalize_failed(
            ErrorCode.LLM_PROFILE_INVALID, "Invalid schemaId format", allow_ready=True
        )

    timeframe = _extract_timeframe(step)
    symbol = _extract_symbol(flow_run)
    if timeframe is None or symbol is None:
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, "Missing timeframe or scope.symbol")

    try:
        report_uri = path_policy.report_uri(run_id, timeframe, step_id)
    except InvalidIdentifier as exc:
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))

    if artifacts_dry_run:
        llm_profile = (
            dict(inputs.llm_profile) if isinstance(inputs.llm_profile, Mapping) else {}
        )
        model_name = _extract_model_name(llm_profile)
        created_at = _now_rfc3339()
        metadata: dict[str, Any] = {
            "schemaVersion": schema_version,
            "runId": run_id,
            "stepId": step_id,
            "createdAt": created_at,
            "finishedAt": created_at,
            "symbol": symbol,
            "timeframe": timeframe,
            "llm": {
                "promptId": inputs.prompt_id,
                "modelName": model_name,
                "schemaId": schema.schema_id,
                "schemaSha256": schema.sha256,
                "llmProfile": llm_profile,
                "finishReason": "DRY_RUN",
            },
            "inputs": {
                "ohlcv_gcs_uri": inputs.ohlcv_gcs_uri,
                "charts_outputsManifestGcsUri": inputs.charts_manifest_gcs_uri,
            },
        }
        if inputs.previous_report_gcs_uris:
            metadata["inputs"]["report_gcs_uris"] = list(inputs.previous_report_gcs_uris)

        report = LLMReportFile(
            metadata=metadata,
            output={
                "summary": {"markdown": "DRY_RUN"},
                "details": {},
            },
        )
        try:
            payload = report.to_json_bytes()
        except SerializationError as exc:
            return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))

        payload_bytes = len(payload)
        event_logger.log(
            event="gcs_write_started",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            artifact={"gcs_uri": str(report_uri)},
            bytes=payload_bytes,
        )

        try:
            write_result = artifact_store.write_bytes_create_only(
                report_uri, payload, content_type="application/json"
            )
        except ArtifactWriteFailed as exc:
            event_logger.log(
                event="gcs_write_finished",
                severity="ERROR",
                eventId=event_id,
                runId=run_id,
                stepId=step_id,
                artifact={"gcs_uri": str(report_uri)},
                ok=False,
                bytes=payload_bytes,
                error={"code": ErrorCode.GCS_WRITE_FAILED.value, "retryable": exc.retryable},
            )
            return _finalize_failed(ErrorCode.GCS_WRITE_FAILED, "Artifact write failed")

        event_logger.log(
            event="gcs_write_finished",
            severity="INFO",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            artifact={"gcs_uri": str(report_uri)},
            ok=True,
            bytes=payload_bytes,
            reused=write_result.reused,
        )

        return _finalize_success(outputs_gcs_uri=str(report_uri))

    if llm_client is None or user_input_assembler is None or structured_output_validator is None:
        return _finalize_failed(ErrorCode.GEMINI_REQUEST_FAILED, "LLM client unavailable")

    try:
        llm_profile_obj = LLMProfile.from_raw(inputs.llm_profile)
        llm_profile_obj.validate_for_mvp()
    except LLMProfileInvalid as exc:
        return _finalize_failed(ErrorCode.LLM_PROFILE_INVALID, str(exc))

    if model_allowed is not None and not model_allowed(llm_profile_obj.model_name):
        return _finalize_failed(ErrorCode.LLM_PROFILE_INVALID, "Model not allowed")

    inputs_summary: dict[str, Any] = {
        "ohlcv_gcs_uri": inputs.ohlcv_gcs_uri,
        "charts_manifest_gcs_uri": inputs.charts_manifest_gcs_uri,
    }
    if inputs.previous_report_gcs_uris:
        inputs_summary["report_gcs_uris"] = list(inputs.previous_report_gcs_uris)

    event_logger.log(
        event="context_resolve_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        inputsSummary=inputs_summary,
    )

    if not time_budget.can_start_llm_call():
        event_logger.log(
            event="time_budget_exceeded",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            action="llm_call",
            policy=time_budget.snapshot(),
        )
        return _finalize_failed(
            ErrorCode.TIME_BUDGET_EXCEEDED,
            "Insufficient time budget for LLM call",
        )

    try:
        resolved = user_input_assembler.resolve(
            flow_run=flow_run,
            step=pick.step,
            inputs=inputs,
        )
    except InvalidStepInputs as exc:
        event_logger.log(
            event="context_resolve_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            ok=False,
            reason={"message": str(exc)},
        )
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))

    artifacts_summary: dict[str, Any] = {
        "ohlcv": {"uri": resolved.ohlcv.uri, "bytes": resolved.ohlcv.bytes_len},
        "charts_manifest": {
            "uri": resolved.charts_manifest.uri,
            "bytes": resolved.charts_manifest.bytes_len,
        },
        "chart_images": [
            {"uri": image.uri, "bytes": image.bytes_len} for image in resolved.chart_images
        ],
    }
    if resolved.previous_reports:
        previous_reports_summary = []
        for report in resolved.previous_reports:
            entry = {
                "uri": report.artifact.uri,
                "bytes": report.artifact.bytes_len,
            }
            if report.step_id:
                entry["stepId"] = report.step_id
            else:
                entry["source"] = "external"
            previous_reports_summary.append(entry)
        artifacts_summary["previous_reports"] = previous_reports_summary

    event_logger.log(
        event="context_resolve_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        ok=True,
        artifacts=artifacts_summary,
    )

    try:
        user_payload = user_input_assembler.assemble(
            base_user_prompt=prompt.user_prompt,
            resolved=resolved,
        )
    except InvalidStepInputs as exc:
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))

    user_parts = [user_payload.text]
    user_parts.extend(user_payload.chart_images)

    event_logger.log(
        event="llm_request_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        llm={
            "promptId": inputs.prompt_id,
            "modelName": llm_profile_obj.model_name,
            "schemaId": schema.schema_id,
        },
    )

    try:
        response = llm_client.generate(
            system=prompt.system_instruction,
            user_parts=user_parts,
            profile=llm_profile_obj,
            llm_schema=schema,
        )
    except RateLimited as exc:
        event_logger.log(
            event="llm_request_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
            error={"code": ErrorCode.RATE_LIMITED.value, "message": str(exc)},
        )
        return _finalize_failed(ErrorCode.RATE_LIMITED, "Gemini rate limited")
    except SafetyBlocked as exc:
        event_logger.log(
            event="llm_request_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
            error={"code": ErrorCode.LLM_SAFETY_BLOCK.value, "message": str(exc)},
        )
        return _finalize_failed(ErrorCode.LLM_SAFETY_BLOCK, "Gemini safety block")
    except RequestFailed as exc:
        event_logger.log(
            event="llm_request_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            status="failed",
            error={"code": ErrorCode.GEMINI_REQUEST_FAILED.value, "message": str(exc)},
        )
        return _finalize_failed(ErrorCode.GEMINI_REQUEST_FAILED, "Gemini request failed")

    event_logger.log(
        event="llm_request_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        status="succeeded",
        finishReason=response.finish_reason,
        llm={"usageMetadata": response.usage},
    )

    validated = structured_output_validator.validate(
        text=response.text,
        llm_schema=schema,
        finish_reason=response.finish_reason,
    )
    if isinstance(validated, StructuredOutputInvalid):
        event_logger.log(
            event="structured_output_invalid",
            severity="WARNING",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            reason={"kind": validated.kind, "message": validated.message},
            llm={"finishReason": response.finish_reason},
            diagnostics={
                "textBytes": validated.text_bytes,
                "textSha256": validated.text_sha256,
            },
            policy={"repairPlanned": False, "finalizeBudgetSeconds": finalize_budget_seconds},
        )
        return _finalize_failed(
            ErrorCode.INVALID_STRUCTURED_OUTPUT,
            validated.to_error_message(),
        )

    created_at = _now_rfc3339()
    metadata = {
        "schemaVersion": schema_version,
        "runId": run_id,
        "stepId": step_id,
        "createdAt": created_at,
        "finishedAt": created_at,
        "symbol": symbol,
        "timeframe": timeframe,
        "llm": {
            "promptId": inputs.prompt_id,
            "modelName": llm_profile_obj.model_name,
            "schemaId": schema.schema_id,
            "schemaSha256": schema.sha256,
            "llmProfile": dict(inputs.llm_profile),
            "finishReason": response.finish_reason,
            "usageMetadata": response.usage,
        },
        "inputs": {
            "ohlcv_gcs_uri": inputs.ohlcv_gcs_uri,
            "charts_outputsManifestGcsUri": inputs.charts_manifest_gcs_uri,
        },
    }
    if inputs.previous_report_gcs_uris:
        metadata["inputs"]["report_gcs_uris"] = list(inputs.previous_report_gcs_uris)

    report = LLMReportFile(metadata=metadata, output=validated)
    try:
        payload = report.to_json_bytes()
    except SerializationError as exc:
        return _finalize_failed(ErrorCode.INVALID_STEP_INPUTS, str(exc))

    payload_bytes = len(payload)
    event_logger.log(
        event="gcs_write_started",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        artifact={"gcs_uri": str(report_uri)},
        bytes=payload_bytes,
    )

    try:
        write_result = artifact_store.write_bytes_create_only(
            report_uri, payload, content_type="application/json"
        )
    except ArtifactWriteFailed as exc:
        event_logger.log(
            event="gcs_write_finished",
            severity="ERROR",
            eventId=event_id,
            runId=run_id,
            stepId=step_id,
            artifact={"gcs_uri": str(report_uri)},
            ok=False,
            bytes=payload_bytes,
            error={"code": ErrorCode.GCS_WRITE_FAILED.value, "retryable": exc.retryable},
        )
        return _finalize_failed(ErrorCode.GCS_WRITE_FAILED, "Artifact write failed")

    event_logger.log(
        event="gcs_write_finished",
        severity="INFO",
        eventId=event_id,
        runId=run_id,
        stepId=step_id,
        artifact={"gcs_uri": str(report_uri)},
        ok=True,
        bytes=payload_bytes,
        reused=write_result.reused,
    )

    return _finalize_success(outputs_gcs_uri=str(report_uri))
